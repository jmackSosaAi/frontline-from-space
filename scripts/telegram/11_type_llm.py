#!/usr/bin/env python
"""L2 (LLM): typing of the residual posts the rules could not type.

Reads   data/interim/telegram/posts_typed.parquet (10_type_rules.py output)
Writes  data/interim/telegram/posts_typed_llm.parquet    one row per LLM-typed post (no text): labels + confidence
        data/interim/telegram/posts_typed_final.parquet  posts_typed with post_type/type_method/type_conf overwritten
                                                          where the LLM answered (rule label kept in post_type_rule)
        ... each with a *_meta.json beside it (input hashes, row counts, prompt_version).

Residual set (default, matches the L2 contract report):
  A. kpszsu / war_monitor / monitoringwar posts with post_type NaN                         (8,187)
  B. regional impact_report CANDIDATES (type_method NaN, conf 0.5)                         (28,013)
Optional: --include-low-conf-launch-intel re-checks rule-typed launch_intel with conf < 0.9;
          --include-regional-untyped also sends the ~36.8k regional untyped non-candidates.

Model: Haiku-class (llm.MODEL_TYPING), fixed 10-label enum from taxonomy.yaml, one call per post, run through a
thread pool; every call is cached on disk by (prompt_version, model, user message), so the script is resumable and a
re-run costs nothing. No key is read in --dry-run.

  python -I scripts/telegram/11_type_llm.py --dry-run          # prints 5 exact requests + cost estimate, no network
  python -I scripts/telegram/11_type_llm.py [--limit N] [--workers 8]
"""
from __future__ import annotations
import argparse, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pandas as pd
import yaml
import llm
from _common import INTERIM, TAXONOMY, write_meta, log
from _llm_common import (PROMPTS, load_prompt, row_user, estimate_cost, print_cost, print_requests, run_calls)

PROMPT_VERSION = "type_v1"
MODEL = llm.MODEL_TYPING
MAX_TOKENS = 1024          # headroom for adaptive thinking at effort=low plus the ~25-token JSON
EFFORT = "low"
CONF = {"high": 0.95, "medium": 0.75, "low": 0.5}
IN_PATH = INTERIM / "posts_typed.parquet"
OUT_LLM = INTERIM / "posts_typed_llm.parquet"
OUT_FINAL = INTERIM / "posts_typed_final.parquet"
UNTYPED_CHANNELS = ["kpszsu", "war_monitor", "monitoringwar"]


def load_labels() -> tuple[list[str], str]:
    tax = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    pt = tax["post_types"]
    labels = list(pt)
    return labels, "\n".join(f"- `{k}`: {v}" for k, v in pt.items()), tax["version"]


def build_schema(labels: list[str]) -> dict:
    return {"type": "object",
            "properties": {"post_type": {"type": "string", "enum": labels},
                           "confidence": {"type": "string", "enum": ["high", "medium", "low"]}},
            "required": ["post_type", "confidence"], "additionalProperties": False}


def select_residual(df: pd.DataFrame, a) -> pd.DataFrame:
    m_a = df.post_type.isna() & df.channel.isin(UNTYPED_CHANNELS)
    m_b = (df.post_type == "impact_report") & df.type_method.isna()
    m = m_a | m_b
    if a.include_low_conf_launch_intel:
        m |= (df.post_type == "launch_intel") & (df.type_method == "rule") & (df.type_conf < 0.9)
    if a.include_regional_untyped:
        m |= df.post_type.isna() & ~df.channel.isin(UNTYPED_CHANNELS)
    grp = pd.Series("C_optional", index=df.index)
    grp[m_a] = "A_af_monitor_untyped"
    grp[m_b] = "B_regional_candidate"
    sel = df[m].copy()
    sel["residual_group"] = grp[m]
    return sel


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print 5 exact requests + cost estimate; no network, no key")
    ap.add_argument("--limit", type=int, help="only the first N residual posts (smoke test)")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--include-low-conf-launch-intel", action="store_true")
    ap.add_argument("--include-regional-untyped", action="store_true")
    ap.add_argument("--chars-per-token", type=float, default=2.4, help="Ukrainian text estimate for dry-run costs")
    ap.add_argument("--out-tokens", type=int, default=120, help="assumed output+thinking tokens per call (dry-run)")
    ap.add_argument("--seed", type=int, default=20261014)
    a = ap.parse_args()

    labels, label_block, tax_version = load_labels()
    system = load_prompt(PROMPT_VERSION, LABELS=label_block)
    schema = build_schema(labels)

    df = pd.read_parquet(IN_PATH)
    sel = select_residual(df, a)
    if a.limit:
        sel = sel.head(a.limit)
    log(f"residual posts: {len(sel):,}  {sel.groupby('residual_group').size().to_dict()}")
    users = [row_user(r) for r in sel.itertuples()]

    if a.dry_run:
        pick = pd.concat([sel[sel.residual_group.str.startswith("A")].sample(3, random_state=a.seed),
                          sel[sel.residual_group.str.startswith("B")].sample(2, random_state=a.seed)])
        posts = [(f"{r.channel}/{r.msg_id} group={r.residual_group}", row_user(r)) for r in pick.itertuples()]
        print_requests(posts, system, schema, MODEL, max_tokens=MAX_TOKENS, effort=EFFORT, cache_system=True)
        # Haiku's minimum cacheable prefix is unknown to us: price the system prompt as NOT cached (conservative).
        c = estimate_cost(MODEL, system, users, out_tokens_per_call=a.out_tokens,
                          chars_per_token=a.chars_per_token, cache_system=False, label="11_type_llm full residual")
        print_cost(c)
        print("by group:", sel.groupby("residual_group").size().to_dict(),
              "| assumptions: chars/token=%.1f, output+thinking=%d tok/call, no prompt caching" % (
                  a.chars_per_token, a.out_tokens))
        return

    def one(user, meta):
        return llm.call(PROMPT_VERSION, system, user, schema, MODEL, max_tokens=MAX_TOKENS, effort=EFFORT, meta=meta)

    items = [((r.channel, int(r.msg_id)), u, {"channel": r.channel, "msg_id": int(r.msg_id)})
             for r, u in zip(sel.itertuples(), users)]
    res = run_calls(items, one, model=MODEL, workers=a.workers, prompt_version=PROMPT_VERSION)

    rows = []
    for r in sel.itertuples():
        o = res.get((r.channel, int(r.msg_id)))
        rows.append({"channel": r.channel, "msg_id": int(r.msg_id), "residual_group": r.residual_group,
                     "prior_post_type": r.post_type, "prior_type_method": r.type_method,
                     "llm_post_type": o["post_type"] if o else None,
                     "llm_conf_label": o["confidence"] if o else None,
                     "llm_conf": CONF[o["confidence"]] if o else None,
                     "llm_failed": o is None})
    out = pd.DataFrame(rows)
    tmp = OUT_LLM.with_suffix(".tmp"); out.to_parquet(tmp, index=False); tmp.replace(OUT_LLM)

    fin = df.copy()
    fin["post_type_rule"] = fin["post_type"]
    ok = out[~out.llm_failed].set_index(["channel", "msg_id"])
    idx = pd.MultiIndex.from_frame(fin[["channel", "msg_id"]])
    hit = idx.isin(ok.index)
    lab = ok.reindex(idx[hit])
    fin.loc[hit, "post_type"] = lab["llm_post_type"].to_numpy()
    fin.loc[hit, "type_method"] = "llm"
    fin.loc[hit, "type_conf"] = lab["llm_conf"].to_numpy()
    tmp = OUT_FINAL.with_suffix(".tmp"); fin.to_parquet(tmp, index=False); tmp.replace(OUT_FINAL)

    counts = {"residual": len(sel), "llm_typed": int((~out.llm_failed).sum()), "failed": int(out.llm_failed.sum()),
              "by_label": out.llm_post_type.value_counts().to_dict(),
              "candidates_confirmed_impact": int(((out.residual_group == "B_regional_candidate")
                                                  & (out.llm_post_type == "impact_report")).sum()),
              "llm_stats_this_run": dict(llm.STATS), "final_rows": len(fin),
              "final_untyped": int(fin.post_type.isna().sum())}
    extra = {"model": MODEL, "effort": EFFORT, "taxonomy_version": tax_version}
    inputs = {"posts_typed": IN_PATH, "taxonomy": TAXONOMY, "prompt": PROMPTS / f"{PROMPT_VERSION}.md"}
    write_meta(OUT_LLM, inputs=inputs, counts=counts, extra=extra, prompt_version=PROMPT_VERSION)
    write_meta(OUT_FINAL, inputs={**inputs, "posts_typed_llm": OUT_LLM}, counts=counts, extra=extra,
               prompt_version=PROMPT_VERSION)
    log(f"done: {counts['llm_typed']:,} typed, {counts['failed']:,} failed; rerun to retry failures (cached calls are free)")


if __name__ == "__main__":
    main()
