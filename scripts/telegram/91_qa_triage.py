#!/usr/bin/env python
"""L7 QA triage: sort the hand-check sample into "agree" and "iffy" so research assistants (RAs) check less.

Plan and decision rules: planning/QA_HANDCHECK.md. Seed 20261014.

Two independent checks on every sampled row (the RA sheets from 90_qa_sample.py):
  1. Rule checks (no LLM): does the extracted place / weapon / casualty number literally appear in the post,
     did the geocoder resolve the place to exactly one settlement, is the event date within 2 days of the post.
  2. Second model: the same post re-extracted by a different, stronger model (llm.MODEL_ADJUDICATE) with the
     same prompt and schema (impacts_v1). Inference only, no training (Telegram ToS §1.5). Cached on disk.
A row is "agree" only if every rule check passes AND the second model gives the same answer on every field.
Everything else is "iffy". RAs then check ALL iffy rows plus a random AUDIT sample of agree rows (default 30),
shuffled together with the bucket hidden, so they cannot tell which is which. 92_qa_score.py turns the filled
sheets into error rates for the whole sample (stratified by bucket).

Usage (from repo root):
  .venv/bin/python -I scripts/telegram/91_qa_triage.py --dry-run     # cost estimate + 3 example requests, no network
  .venv/bin/python -I scripts/telegram/91_qa_triage.py --run         # second-model pass + RA packet
  .venv/bin/python -I scripts/telegram/91_qa_triage.py --rules-only  # RA packet from rule checks alone (no API)

Outputs (raw text -> data/interim, gitignored):
  data/interim/telegram/qa/triage_impacts.csv      every sampled row + checks + bucket (for us, not RAs)
  data/interim/telegram/qa/ra_packet/ra_impacts.csv, ra_empty.csv, ra_typing.csv   (give these to RAs)
  data/interim/telegram/qa/ra_packet/_key.csv      row_id -> sheet, bucket (DO NOT give to RAs)
"""
from __future__ import annotations
import argparse, re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
import llm
from _common import INTERIM, write_meta, log
from _llm_common import load_prompt, row_user, estimate_cost, print_cost, print_requests

SEED = 20261014
QA = INTERIM / "qa"
PACKET = QA / "ra_packet"
PROMPT_VERSION = "impacts_v1"
MODEL2 = llm.MODEL_ADJUDICATE
N_TYPING = 100
FIELDS = ["place", "weapon", "target_type", "casualties", "time"]
IMP_BLANK = ["chk_place_ok", "chk_weapon_ok", "chk_target_type_ok", "chk_casualties_ok", "chk_time_ok",
             "chk_missed_incidents_in_post", "chk_note"]


def _schema():
    import importlib.util
    spec = importlib.util.spec_from_file_location("x23", pathlib.Path(__file__).parent / "23_extract_impacts.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m.SCHEMA, m.MAX_TOKENS


def norm(s) -> str:
    return re.sub(r"[^\w]+", " ", str(s or "").casefold()).strip()


def stem_in(raw, text: str, k: int = 4) -> bool:
    """The longest word of `raw` (first k chars, to absorb Ukrainian case endings) occurs in the text."""
    words = sorted((w for w in norm(raw).split() if len(w) >= 3), key=len, reverse=True)
    return bool(words) and words[0][:k] in norm(text)


CASUALTY_WORDS = re.compile(r"загин|загибл|вбит|убит|поранен|травм|постраждал|госпіталізов|жертв", re.I)


def num_in(n, text: str) -> bool:
    """Nonzero count: the digit appears, or (small counts are often spelled out) a casualty word appears."""
    if pd.isna(n) or int(n) == 0:
        return True
    t = str(text)
    return re.search(rf"(?<!\d){int(n)}(?!\d)", t) is not None or (int(n) <= 10 and CASUALTY_WORDS.search(t) is not None)


def rule_checks(r) -> dict:
    t = r.text
    place = r.settlement_raw if pd.notna(r.settlement_raw) and str(r.settlement_raw).strip() else r.raion_raw
    c = {
        "rule_place_in_text": True if (pd.isna(place) or r.location_withheld is True) else stem_in(place, t),
        "rule_place_unique_geo": (pd.notna(r.geo_n_cand) and r.geo_n_cand == 1) or pd.isna(place),
        "rule_weapon_in_text": True if pd.isna(r.weapon_raw) or not str(r.weapon_raw).strip() else stem_in(r.weapon_raw, t),
        "rule_casualties_in_text": num_in(r.killed, t) and num_in(r.wounded, t),
        "rule_date_near_post": abs((pd.to_datetime(r.event_date) - pd.to_datetime(r.post_ts_utc).tz_localize(None)
                                    .normalize()).days) <= 2 if pd.notna(r.event_date) else False,
    }
    return c


def place_text(d) -> str:
    return " ".join(str(d.get(k) or "") for k in ("settlement", "raion", "oblast"))


def place_match(r, a: dict) -> bool:
    """The first model's place (settlement, else raion) appears anywhere in the second model's place fields, or back."""
    mine = r.settlement_raw if pd.notna(r.settlement_raw) and str(r.settlement_raw).strip() else r.raion_raw
    theirs = a.get("settlement") or a.get("raion")
    if pd.isna(mine) and not theirs:
        return True
    return stem_in(mine, place_text(a)) or stem_in(theirs, " ".join(str(x) for x in (r.settlement_raw, r.raion_raw, r.oblast_raw)))


def pair(r, incs: list) -> dict | None:
    """Second-model incident that corresponds to this row: place match first, else same position if counts agree."""
    hits = [a for a in incs if place_match(r, a)]
    if hits:
        return hits[0]
    if len(incs) == int(r.n_incidents_in_post) and int(r.incident_idx) < len(incs):
        return incs[int(r.incident_idx)]
    return None


def model_checks(r, out: dict | None) -> dict:
    if out is None:
        return {f"m2_{f}": None for f in FIELDS} | {"m2_n_incidents_same": None}
    incs = out.get("incidents") or []
    a = pair(r, incs)
    eq = lambda x, y: (pd.isna(x) and y in (None, "")) or (pd.notna(x) and y is not None and str(x).strip().casefold() == str(y).strip().casefold())
    num = lambda x: 0 if x is None or pd.isna(x) else int(x)
    return {
        "m2_place": a is not None and place_match(r, a),
        "m2_weapon": a is not None and (eq(r.weapon_raw, a.get("weapon_raw")) or
                                        (pd.notna(r.weapon_raw) and stem_in(r.weapon_raw, str(a.get("weapon_raw") or ""))) or
                                        (bool(a.get("weapon_raw")) and stem_in(a.get("weapon_raw"), str(r.weapon_raw)))),
        "m2_target_type": a is not None and eq(r.target_type, a.get("target_type")),
        "m2_casualties": a is not None and all(num(getattr(r, k)) == num(a.get(k)) for k in ("killed", "wounded")),
        "m2_time": a is not None and eq(r.event_date, a.get("event_date")),
        "m2_n_incidents_same": len(incs) == int(r.n_incidents_in_post),
    }


def load():
    imp = pd.read_csv(QA / "qa_impacts_sample.csv")
    emp = pd.read_csv(QA / "qa_impacts_empty_sample.csv")
    typ = pd.read_csv(QA / "qa_typing_sample.csv")
    full = pd.read_parquet(INTERIM / "extract/impacts.parquet",
                           columns=["channel", "msg_id", "incident_idx", "post_ts_utc", "geo_n_cand", "geo_method"])
    imp = imp.merge(full, on=["channel", "msg_id", "incident_idx"], how="left")
    posts = pd.read_parquet(INTERIM / "posts.parquet")
    keys = pd.concat([imp[["channel", "msg_id"]], emp[["channel", "msg_id"]]]).drop_duplicates()
    posts = posts.merge(keys, on=["channel", "msg_id"])
    return imp, emp, typ, posts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true"); g.add_argument("--run", action="store_true")
    g.add_argument("--rules-only", action="store_true")
    ap.add_argument("--audit", type=int, default=30, help="random 'agree' rows the RAs also check")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    imp, emp, typ, posts = load()
    system = load_prompt(PROMPT_VERSION)
    schema, max_tokens = _schema()
    users = {(r.channel, int(r.msg_id)): row_user(r) for r in posts.itertuples()}
    log(f"sample: {len(imp)} incident rows from {imp.msg_id.nunique()} posts, {len(emp)} empty posts, "
        f"{len(users)} unique posts for the second model ({MODEL2})")

    if a.dry_run:
        ex = list(users.items())[:3]
        print_requests([(f"{k[0]}/{k[1]}", u) for k, u in ex], system, schema, MODEL2, max_tokens=max_tokens,
                       effort="low", cache_system=True)
        from _llm_common import PRICES, est_tokens
        if MODEL2 in PRICES:
            print_cost(estimate_cost(MODEL2, system, list(users.values()), out_tokens_per_call=500, chars_per_token=2.4,
                                     cache_system=True, label=f"91_qa_triage second pass, {len(users)} posts"))
        else:
            tin = sum(est_tokens(u, 2.4) for u in users.values()) + est_tokens(system, 2.4)
            print(f"{MODEL2} has no price in _llm_common.PRICES; ~{tin:,} input tokens (system prompt cached) "
                  f"+ ~{500 * len(users):,} output tokens for {len(users)} calls")
        return

    out2 = {}
    if a.run:
        from concurrent.futures import ThreadPoolExecutor
        def one(item):
            k, u = item
            try:
                return k, llm.call(PROMPT_VERSION + "_qa2", system, u, schema, MODEL2, max_tokens=max_tokens,
                                   effort="low", meta={"channel": k[0], "msg_id": k[1]})
            except Exception as e:                                   # refusal / API error -> row stays iffy
                log(f"second model failed for {k}: {type(e).__name__}"); return k, None
        with ThreadPoolExecutor(a.workers) as ex:
            out2 = dict(ex.map(one, users.items()))
        n_fail = sum(v is None for v in out2.values())
        if n_fail > 0.1 * len(out2):                                 # e.g. no API credit: don't write a bogus packet
            sys.exit(f"second model failed on {n_fail}/{len(out2)} posts; packet NOT written. Fix the API issue and "
                     f"re-run (successful calls are cached), or use --rules-only.")

    rows = []
    for r in imp.itertuples():
        rc = rule_checks(r)
        mc = model_checks(r, out2.get((r.channel, int(r.msg_id)))) if a.run else {}
        reasons = [k for k, v in {**rc, **mc}.items() if v is False or (a.run and v is None)]
        rows.append({**rc, **mc, "reasons": ";".join(reasons), "bucket": "iffy" if reasons else "agree"})
    tri = pd.concat([imp.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    tri.to_csv(QA / "triage_impacts.csv", index=False)

    emp = emp.copy()
    if a.run:
        emp["m2_n"] = [len(out2[(r.channel, int(r.msg_id))].get("incidents") or [])
                       if out2.get((r.channel, int(r.msg_id))) is not None else None for r in emp.itertuples()]
        emp["bucket"] = np.where(emp.m2_n == 0, "agree", "iffy")
    else:
        emp["bucket"] = "iffy"                                     # no independent check without the model
    rng = np.random.default_rng(SEED)

    # RA packet: all iffy + audit sample of agree, shuffled, bucket hidden
    PACKET.mkdir(parents=True, exist_ok=True)
    keys = []
    def pick(df, sheet):
        agree = df[df.bucket == "agree"]
        aud = agree.sample(min(a.audit, len(agree)), random_state=SEED) if len(agree) else agree
        sel = pd.concat([df[df.bucket == "iffy"], aud]).sample(frac=1, random_state=SEED).reset_index(drop=True)
        sel.insert(0, "row_id", [f"{sheet}-{i+1:03d}" for i in range(len(sel))])
        keys.append(sel[["row_id", "channel", "msg_id"] + (["incident_idx"] if "incident_idx" in sel else []) + ["bucket"]]
                    .assign(sheet=sheet, n_bucket_total=sel.bucket.map(df.bucket.value_counts())))
        return sel

    ri = pick(tri, "imp")
    show = ["row_id", "url", "text", "event_date", "event_time", "oblast_raw", "raion_raw", "settlement_raw",
            "location_withheld", "weapon_raw", "target_type", "killed", "wounded", "is_debris_only", "n_incidents_in_post"]
    ri[show + IMP_BLANK].to_csv(PACKET / "ra_impacts.csv", index=False)
    re_ = pick(emp, "emp")
    re_[["row_id", "url", "text", "chk_has_incident", "chk_note"]].to_csv(PACKET / "ra_empty.csv", index=False)
    rt = typ.sample(min(N_TYPING, len(typ)), random_state=SEED).reset_index(drop=True)
    rt.insert(0, "row_id", [f"typ-{i+1:03d}" for i in range(len(rt))])
    keys.append(rt[["row_id", "channel", "msg_id"]].assign(sheet="typ", bucket="random", n_bucket_total=len(typ)))
    rt[["row_id", "url", "text", "post_type", "human_ok", "human_post_type", "human_note"]].to_csv(PACKET / "ra_typing.csv", index=False)
    pd.concat(keys).to_csv(PACKET / "_key.csv", index=False)

    counts = {"impacts": tri.bucket.value_counts().to_dict(), "empty": emp.bucket.value_counts().to_dict(),
              "ra_rows": {"impacts": len(ri), "empty": len(re_), "typing": len(rt)}, "audit": a.audit,
              "mode": "run" if a.run else "rules-only", "model2": MODEL2 if a.run else None}
    write_meta(QA / "triage_impacts.csv", inputs={"qa_impacts_sample": QA / "qa_impacts_sample.csv"}, counts=counts,
               prompt_version=PROMPT_VERSION + "_qa2" if a.run else None)
    log(f"triage: {counts}")
    log(f"RA packet in {PACKET} (give RAs ra_*.csv and docs/RA_GUIDE.md + tools/qa_checker.html; never _key.csv)")


if __name__ == "__main__":
    main()
