#!/usr/bin/env python
"""L7 QA scoring: turn the research assistants' filled sheets into error rates. No network, no LLM.

Reads data/interim/telegram/qa/ra_packet/{ra_impacts,ra_empty,ra_typing}.csv (filled by RAs; "y"/"n" cells)
and _key.csv (bucket of every row, written by 91_qa_triage.py). Plan and decision rules: planning/QA_HANDCHECK.md.

Impacts: per field, accuracy in the "iffy" bucket (every row checked) and in the "agree" bucket (random audit),
combined into one estimate for the whole sample weighted by bucket size, with a 95% interval
(Wilson per bucket, combined by the normal approximation). Two RAs on the same row: disagreements are listed for
adjudication, and the score uses "n" if either says "n" (conservative) until adjudicated.
Decision rule: if the audit finds the "agree" bucket's 95% error upper bound above 12% for a field (with 30 audit rows
that means any error at all), the "agree" label is not
trusted for that field and the report says to check every agree row for it.

Outputs (aggregates only, safe to commit): data/derived/telegram/qa/qa_scores.csv, REPORT.md
"""
from __future__ import annotations
import sys, pathlib, math
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pandas as pd
from _common import INTERIM, DERIVED, write_meta, log

PACKET = INTERIM / "qa" / "ra_packet"
OUT = DERIVED / "qa"
FIELDS = ["chk_place_ok", "chk_weapon_ok", "chk_target_type_ok", "chk_casualties_ok", "chk_time_ok"]
MAX_AGREE_ERR = 0.12   # 30/30 clean audit rows -> upper bound 11.4%; one error -> ~17% (fails)


def yn(v):
    s = str(v).strip().lower()
    return True if s in ("y", "yes", "1", "true") else False if s in ("n", "no", "0", "false") else None


def wilson(k, n, z=1.96):
    if n == 0:
        return (math.nan, math.nan, math.nan)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (p, (c - h) / d, (c + h) / d)


def load(name):
    """All filled copies of a sheet: ra_impacts.csv, ra_impacts_<initials>.csv, ... -> one row per row_id."""
    files = sorted(PACKET.glob(f"{name}*.csv"))
    if not files:
        return None, []
    dfs = [pd.read_csv(f, dtype=str).assign(_rater=f.stem) for f in files]
    allr = pd.concat(dfs)
    return allr, files


def combine(allr, cols):
    """Per row_id: True only if every rater said y; list disagreements."""
    out, dis = [], []
    for rid, g in allr.groupby("row_id"):
        rec = {"row_id": rid}
        for c in cols:
            vals = [yn(v) for v in g[c] if yn(v) is not None]
            rec[c] = None if not vals else all(vals)
            if len(set(vals)) > 1:
                dis.append((rid, c))
        out.append(rec)
    return pd.DataFrame(out), dis


def stratified(df, col, key):
    d = df.merge(key[["row_id", "bucket", "n_bucket_total"]], on="row_id")
    d = d[d[col].notna()]
    parts, N = {}, 0
    for b, g in d.groupby("bucket"):
        k, n = int(g[col].sum()), len(g)
        Nb = int(g.n_bucket_total.iloc[0]); N += Nb
        parts[b] = (k, n, Nb, *wilson(k, n))
    if not parts:
        return None
    est = sum(p[3] * p[2] for p in parts.values()) / N
    var = sum((p[2] / N) ** 2 * p[3] * (1 - p[3]) / max(p[1], 1) * (1 - p[1] / p[2] if p[2] else 1)
              for p in parts.values())
    return est, max(0, est - 1.96 * math.sqrt(var)), min(1, est + 1.96 * math.sqrt(var)), parts


def main() -> None:
    key = pd.read_csv(PACKET / "_key.csv", dtype={"msg_id": str})
    rows, notes = [], []
    allr, files = load("ra_impacts")
    if allr is not None:
        imp, dis = combine(allr, FIELDS)
        notes += [f"rater disagreement: {r} {c}" for r, c in dis]
        for c in FIELDS:
            s = stratified(imp, c, key[key.sheet == "imp"])
            if s is None:
                continue
            est, lo, hi, parts = s
            ag = parts.get("agree")
            trusted = ag is None or (1 - ag[4]) <= MAX_AGREE_ERR      # error upper bound = 1 - accuracy lower bound
            rows.append({"sheet": "impacts", "field": c.removeprefix("chk_").removesuffix("_ok"), "accuracy": est,
                         "lo95": lo, "hi95": hi, "agree_checked": ag[1] if ag else 0,
                         "agree_acc": ag[3] if ag else None, "iffy_checked": parts.get("iffy", (0, 0))[1],
                         "iffy_acc": parts["iffy"][3] if "iffy" in parts else None, "agree_label_trusted": trusted})
            if not trusted:
                notes.append(f"{c}: audit error upper bound > {MAX_AGREE_ERR:.0%}; check every 'agree' row for this field")
        allf, _ = combine(allr, ["chk_all_found"]) if "chk_all_found" in allr else (pd.DataFrame(), [])
        if len(allf) and allf.chk_all_found.notna().any():
            f = allf.chk_all_found.dropna(); p, lo, hi = wilson(int(f.sum()), len(f))
            rows.append({"sheet": "impacts", "field": "all_strikes_found_in_post", "accuracy": p, "lo95": lo, "hi95": hi,
                         "iffy_checked": len(f)})
        missed = allr.assign(m=pd.to_numeric(allr.chk_missed_incidents_in_post, errors="coerce")).groupby("row_id").m.max().fillna(0)
        rows.append({"sheet": "impacts", "field": "missed_incidents_per_post", "accuracy": missed.mean(),
                     "lo95": None, "hi95": None})
    allr, _ = load("ra_empty")
    if allr is not None:
        emp, dis = combine(allr, ["chk_has_incident"])
        notes += [f"rater disagreement: {r} {c}" for r, c in dis]
        e = emp.chk_has_incident.dropna()
        p, lo, hi = wilson(int(e.sum()), len(e))
        rows.append({"sheet": "empty", "field": "missed_post_rate", "accuracy": p, "lo95": lo, "hi95": hi,
                     "iffy_checked": len(e)})
    allr, _ = load("ra_typing")
    if allr is not None:
        typ, dis = combine(allr, ["human_ok"])
        notes += [f"rater disagreement: {r} {c}" for r, c in dis]
        t = typ.human_ok.dropna()
        p, lo, hi = wilson(int(t.sum()), len(t))
        rows.append({"sheet": "typing", "field": "post_type", "accuracy": p, "lo95": lo, "hi95": hi,
                     "iffy_checked": len(t)})

    OUT.mkdir(parents=True, exist_ok=True)
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "qa_scores.csv", index=False)
    na = lambda x: x is None or (isinstance(x, float) and math.isnan(x))
    fmt = lambda x: "" if na(x) else f"{x:.1%}"
    cnt = lambda n, acc: "" if na(n) or not n else f"{int(n)} ({fmt(acc)})"
    lines = ["# Telegram extraction QA: hand-check results", "",
             "Generated by `scripts/telegram/92_qa_score.py` from the research assistants' sheets. Method: "
             "`planning/QA_HANDCHECK.md`. Accuracy is for the whole 200-row impact sample, weighted by triage bucket.", "",
             "| sheet | field | accuracy | 95% CI | agree rows checked (acc) | iffy rows checked (acc) | agree label trusted |",
             "|---|---|---|---|---|---|---|"]
    for r in res.to_dict("records"):
        acc = f"{r['accuracy']:.2f}" if r["field"] == "missed_incidents_per_post" else fmt(r["accuracy"])
        lines.append(f"| {r['sheet']} | {r['field']} | {acc} | "
                     f"{fmt(r.get('lo95'))}–{fmt(r.get('hi95'))} | {cnt(r.get('agree_checked'), r.get('agree_acc'))} | "
                     f"{cnt(r.get('iffy_checked'), r.get('iffy_acc'))} | {'' if na(r.get('agree_label_trusted')) else r.get('agree_label_trusted')} |")
    lines += ["", "## Notes", *[f"- {n}" for n in notes or ["none"]]]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_meta(OUT / "qa_scores.csv", inputs={f.name: f for f in sorted(PACKET.glob("*.csv"))}, counts={"rows": len(res), "notes": len(notes)})
    log(f"wrote {OUT/'REPORT.md'}; {len(notes)} notes")


if __name__ == "__main__":
    main()
