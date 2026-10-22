#!/usr/bin/env python
"""L3 (LLM): impact extraction from regional-administration prose. One post -> list of incidents.

Reads   data/interim/telegram/posts_typed_final.parquet (after 11_type_llm.py): regional channels, post_type == impact_report
        (--candidates-only: skip the typing step and use the raw regional candidates in posts_typed.parquet)
Writes  data/interim/telegram/extract/impacts.parquet         one row per incident (tier A), schema = TELEGRAM_PIPELINE.md §L3
        data/interim/telegram/extract/impacts_posts.parquet   one row per processed post (n_incidents, failed) incl. empty lists
        ... each with a *_meta.json (input hashes, row counts, prompt_version=impacts_v1).

Model: Sonnet-class (llm.MODEL_EXTRACT), strict JSON schema (output_config.format), few-shot prompt in
prompts/impacts_v1.md. Determinism: Sonnet 5.5 rejects temperature, so it is effort=low + the on-disk cache keyed by
(prompt_version, model, user message); a re-run reads the cache and costs nothing. The few-shot system prompt is marked
as an API prompt-cache prefix (cache_system) so it is billed at the cache-read rate.

Time: the model returns event_date / event_time (Kyiv local). Script builds event_ts_kyiv/utc with zoneinfo:
  clock time stated                      -> exact, time_is_post_time = 0
  no time, date null or == post date     -> post timestamp, time_is_post_time = 1
  no time, date != post date             -> event_ts null (use event_date), time_is_post_time = 0
Casualties are "as last edited" (edit_ts_utc kept, `edited` flag). No casualty names exist in the schema.

  python -I scripts/telegram/23_extract_impacts.py --dry-run     # 5 exact requests + cost estimate, no network
  python -I scripts/telegram/23_extract_impacts.py --batch       # Message Batches API, half price (preferred)
  python -I scripts/telegram/23_extract_impacts.py [--limit N] [--workers 6]
"""
from __future__ import annotations
import argparse, re, sys, pathlib, datetime as dt
from zoneinfo import ZoneInfo

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pandas as pd
import llm
from _common import INTERIM, write_meta, log
from _llm_common import PROMPTS, load_prompt, row_user, estimate_cost, print_cost, print_requests, run_calls

PROMPT_VERSION = "impacts_v1"
MODEL = llm.MODEL_EXTRACT
MAX_TOKENS = 4096          # long daily reports can hold ~10 incidents; thinking tokens count against this
EFFORT = "low"
REGIONAL = ["VA_Kyiv", "dnipropetrovskaODA", "kozytskyy_maksym_official", "odeskaODA", "synegubov", "zoda_gov_ua"]
KYIV = ZoneInfo("Europe/Kyiv")
IN_FINAL = INTERIM / "posts_typed_final.parquet"
IN_RULES = INTERIM / "posts_typed.parquet"
OUT_DIR = INTERIM / "extract"
OUT = OUT_DIR / "impacts.parquet"
OUT_POSTS = OUT_DIR / "impacts_posts.parquet"
TARGETS = ["residential", "energy", "industrial", "military", "transport", "agri", "other", "unknown"]


def nullable(t: str) -> dict:
    return {"anyOf": [{"type": t}, {"type": "null"}]}


INCIDENT = {
    "type": "object",
    "properties": {
        "event_date": nullable("string"),            # YYYY-MM-DD
        "event_time": nullable("string"),            # HH:MM Kyiv local, only if stated
        "oblast": nullable("string"),
        "raion": nullable("string"),
        "settlement": nullable("string"),
        "location_withheld": {"type": "boolean"},
        "weapon_raw": nullable("string"),
        "target_type": {"type": "string", "enum": TARGETS},
        "killed": nullable("integer"),
        "wounded": nullable("integer"),
        "is_debris_only": {"type": "boolean"},
        "is_update": {"type": "boolean"},
        "damage_text_short": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["event_date", "event_time", "oblast", "raion", "settlement", "location_withheld", "weapon_raw",
                 "target_type", "killed", "wounded", "is_debris_only", "is_update", "damage_text_short", "confidence"],
    "additionalProperties": False,
}
SCHEMA = {"type": "object",
          "properties": {"incidents": {"type": "array", "items": INCIDENT}},
          "required": ["incidents"], "additionalProperties": False}


def to_ts(date_s, time_s, post_ts):
    """-> (event_ts_kyiv | NaT, time_is_post_time, date_ok, time_ok)."""
    d_ok = bool(date_s) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_s) is not None
    t_ok = bool(time_s) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", time_s) is not None
    try:
        d = dt.date.fromisoformat(date_s) if d_ok else None
    except ValueError:
        d, d_ok = None, False
    post_date = post_ts.date()
    if t_ok:
        day = d if d is not None else post_date
        h, m = map(int, time_s.split(":"))
        return pd.Timestamp(dt.datetime(day.year, day.month, day.day, h, m, tzinfo=KYIV)), 0, d_ok, True
    if d is None or d == post_date:
        return post_ts, 1, d_ok, False
    return pd.NaT, 0, d_ok, False


def load_input(a) -> pd.DataFrame:
    if not a.candidates_only and IN_FINAL.exists():
        df = pd.read_parquet(IN_FINAL)
        df = df[df.channel.isin(REGIONAL) & (df.post_type == "impact_report")]
        return df
    if not a.dry_run and not a.candidates_only:
        sys.exit(f"{IN_FINAL.name} not found: run 11_type_llm.py first (or pass --candidates-only to extract "
                 "from every unconfirmed regional candidate).")
    df = pd.read_parquet(IN_RULES)
    return df[df.channel.isin(REGIONAL) & (df.post_type == "impact_report")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print 5 exact requests + cost estimate; no network, no key")
    ap.add_argument("--candidates-only", action="store_true", help="use raw regional candidates (skip LLM typing)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--batch", action="store_true",
                    help="use the Message Batches API (-50%% on every token; async, usually <1 h per chunk)")
    ap.add_argument("--chars-per-token", type=float, default=2.4, help="Ukrainian text estimate for dry-run costs")
    ap.add_argument("--out-tokens", type=int, default=400, help="assumed output+thinking tokens per call (dry-run)")
    ap.add_argument("--expected-posts", type=int, default=20000, help="expected confirmed posts for the headline estimate")
    ap.add_argument("--seed", type=int, default=20261014)
    a = ap.parse_args()

    system = load_prompt(PROMPT_VERSION)
    df = load_input(a).sort_values(["channel", "msg_id"])
    if a.limit:
        df = df.head(a.limit)
    log(f"posts to extract: {len(df):,}  {df.channel.value_counts().to_dict()}")

    if a.dry_run:
        pick = pd.concat([df[df.channel == ch].sample(1, random_state=a.seed)
                          for ch in REGIONAL if (df.channel == ch).any()]).head(5)
        posts = [(f"{r.channel}/{r.msg_id}", row_user(r)) for r in pick.itertuples()]
        print_requests(posts, system, SCHEMA, MODEL, max_tokens=MAX_TOKENS, effort=EFFORT, cache_system=True)
        users = [row_user(r) for r in df.itertuples()]
        c_all = estimate_cost(MODEL, system, users, out_tokens_per_call=a.out_tokens, chars_per_token=a.chars_per_token,
                              cache_system=True, label=f"23_extract_impacts, all {len(users):,} regional candidates/impacts")
        print_cost(c_all)
        k = min(a.expected_posts, len(users))
        print_cost(estimate_cost(MODEL, system, users, out_tokens_per_call=a.out_tokens,
                                 chars_per_token=a.chars_per_token, cache_system=True, n_calls=k,
                                 label=f"23_extract_impacts, expected ~{k:,} LLM-confirmed posts"))
        print(f"assumptions: chars/token={a.chars_per_token}, output+thinking={a.out_tokens} tok/call, "
              f"system prompt cached after first call (5-min TTL, calls run continuously)")
        return

    def one(user, meta):
        return llm.call(PROMPT_VERSION, system, user, SCHEMA, MODEL, max_tokens=MAX_TOKENS, effort=EFFORT, meta=meta)

    items = [((r.channel, int(r.msg_id)), row_user(r), {"channel": r.channel, "msg_id": int(r.msg_id)})
             for r in df.itertuples()]
    if a.batch:
        res = llm.call_batch(PROMPT_VERSION, system, items, SCHEMA, MODEL, max_tokens=MAX_TOKENS, effort=EFFORT,
                             log=log, batch_ids_file=OUT_DIR / "batch_ids.tsv")
    else:
        res = run_calls(items, one, model=MODEL, workers=a.workers, prompt_version=PROMPT_VERSION)

    inc_rows, post_rows, bad_date, bad_time = [], [], 0, 0
    for r in df.itertuples():
        o = res.get((r.channel, int(r.msg_id)))
        incs = o["incidents"] if o else []
        post_rows.append({"channel": r.channel, "msg_id": int(r.msg_id), "n_incidents": len(incs),
                          "failed": o is None, "type_method": r.type_method})
        for i, x in enumerate(incs):
            ts, is_post, d_ok, t_ok = to_ts(x["event_date"], x["event_time"], r.ts_kyiv)
            bad_date += int(bool(x["event_date"]) and not d_ok)
            bad_time += int(bool(x["event_time"]) and not t_ok)
            inc_rows.append({
                "channel": r.channel, "msg_id": int(r.msg_id), "incident_idx": i, "n_incidents_in_post": len(incs),
                "post_ts_utc": r.ts_utc, "event_date": x["event_date"] if d_ok else None,
                "event_time": x["event_time"] if t_ok else None,
                "event_ts_kyiv": ts, "event_ts_utc": ts.tz_convert("UTC") if pd.notna(ts) else pd.NaT,
                "time_is_post_time": is_post,
                "oblast_raw": x["oblast"], "raion_raw": x["raion"], "settlement_raw": x["settlement"],
                "location_withheld": x["location_withheld"], "weapon_raw": x["weapon_raw"],
                "target_type": x["target_type"], "killed": x["killed"], "wounded": x["wounded"],
                "is_debris_only": x["is_debris_only"], "is_update": x["is_update"],
                "damage_text_short": x["damage_text_short"], "confidence": x["confidence"],
                "tier": "A", "edited": bool(pd.notna(r.edit_ts_utc)), "edit_ts_utc": r.edit_ts_utc,
                "source_msg_ids": [int(r.msg_id)], "prompt_version": PROMPT_VERSION,
            })
    imp, posts = pd.DataFrame(inc_rows), pd.DataFrame(post_rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for frame, path in ((imp, OUT), (posts, OUT_POSTS)):
        tmp = path.with_suffix(".tmp"); frame.to_parquet(tmp, index=False); tmp.replace(path)

    counts = {"posts": len(posts), "posts_failed": int(posts.failed.sum()),
              "posts_zero_incidents": int(((posts.n_incidents == 0) & ~posts.failed).sum()),
              "incidents": len(imp), "invalid_date_dropped": bad_date, "invalid_time_dropped": bad_time,
              "time_is_post_time_share": float(imp.time_is_post_time.mean()) if len(imp) else None,
              "by_channel": imp.channel.value_counts().to_dict() if len(imp) else {},
              "llm_stats_this_run": dict(llm.STATS)}
    inputs = {"posts_typed": IN_FINAL if IN_FINAL.exists() and not a.candidates_only else IN_RULES,
              "prompt": PROMPTS / f"{PROMPT_VERSION}.md"}
    extra = {"model": MODEL, "effort": EFFORT, "candidates_only": a.candidates_only, "batch_api": a.batch}
    write_meta(OUT, inputs=inputs, counts=counts, extra=extra, prompt_version=PROMPT_VERSION)
    write_meta(OUT_POSTS, inputs=inputs, counts=counts, extra=extra, prompt_version=PROMPT_VERSION)
    log(f"done: {counts['incidents']:,} incidents from {counts['posts']:,} posts "
        f"({counts['posts_zero_incidents']:,} empty, {counts['posts_failed']:,} failed)")


if __name__ == "__main__":
    main()
