#!/usr/bin/env python
"""L2 (rules): posts.parquet -> posts_typed.parquet

Adds post_type, type_method ('rule' | None), type_conf. Rules live in taxonomy.yaml
(`type_rules`, evaluated in order, first match wins; `impact_candidate` marks regional
prose for the LLM typer with type_method=None, type_conf=0.5).
Also writes a coverage report (channel x post_type) to data/interim/telegram/qa_type_coverage.csv.
"""
from __future__ import annotations
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import regex as re
import yaml
import pandas as pd
from _common import INTERIM, TAXONOMY, write_meta, log

FLAGS = re.IGNORECASE | re.UNICODE


def load_rules(tax: dict):
    groups = tax["channel_groups"]
    rules = []
    for r in tax["type_rules"]:
        ch = r["channels"]
        if ch == "all":
            chans = None
        elif isinstance(ch, str):
            chans = set(groups[ch])
        else:
            chans = set(ch)
        rules.append({
            "name": r["name"], "chans": chans, "post_type": r["post_type"], "conf": float(r["conf"]),
            "re": re.compile(r["pattern"], FLAGS),
            "min_chars": r.get("min_chars", 0), "max_chars": r.get("max_chars", 10**9),
            "method": r.get("method", "rule"),   # None => candidate for the LLM typer
        })
    ic = tax["impact_candidate"]
    cand = {"chans": set(groups[ic["channels"]]) if isinstance(ic["channels"], str) else set(ic["channels"]),
            "re": re.compile(ic["pattern"], FLAGS), "min_chars": ic.get("min_chars", 0)}
    return rules, cand


def type_one(channel: str, text: str, n: int, rules, cand):
    for r in rules:
        if r["chans"] is not None and channel not in r["chans"]:
            continue
        if n < r["min_chars"] or n > r["max_chars"]:
            continue
        if r["re"].search(text):
            return r["post_type"], r["method"], r["conf"], r["name"]
    if channel in cand["chans"] and n >= cand["min_chars"] and cand["re"].search(text):
        return "impact_report", None, 0.5, "impact_candidate"
    return None, None, None, None


def main() -> None:
    tax = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    rules, cand = load_rules(tax)
    src = INTERIM / "posts.parquet"
    df = pd.read_parquet(src)
    log(f"typing {len(df)} posts with {len(rules)} rules (taxonomy {tax['version']})")
    # only the first 600 chars matter for typing; keeps the regexes fast and anchored to the lead
    heads = df["text_norm"].str.slice(0, 600)
    out = [type_one(c, t, n, rules, cand) for c, t, n in zip(df["channel"], heads, df["n_chars"])]
    df["post_type"] = [o[0] for o in out]
    df["type_method"] = [o[1] for o in out]
    df["type_conf"] = [o[2] for o in out]
    df["type_rule"] = [o[3] for o in out]   # which rule fired (debug / QA; dropped nowhere)
    dst = INTERIM / "posts_typed.parquet"
    df.to_parquet(dst, index=False)

    # coverage report
    cov = (df.assign(pt=df["post_type"].fillna("<untyped>"),
                     m=df["type_method"].fillna("none"))
             .groupby(["channel", "pt", "m"]).size().rename("n").reset_index())
    cov.to_csv(INTERIM / "qa_type_coverage.csv", index=False)
    rule_share = (df.groupby("channel")["type_method"].apply(lambda s: (s == "rule").mean())).round(4)
    counts = {"rows": int(len(df)),
              "rule_typed": int((df["type_method"] == "rule").sum()),
              "impact_candidates": int(((df["type_method"].isna()) & (df["post_type"] == "impact_report")).sum()),
              "untyped": int(df["post_type"].isna().sum()),
              "rule_share_by_channel": rule_share.to_dict(),
              "by_type": df["post_type"].fillna("<untyped>").value_counts().to_dict()}
    write_meta(dst, inputs={"posts": src, "taxonomy": TAXONOMY}, counts=counts,
               extra={"taxonomy_version": tax["version"], "n_rules": len(rules)})
    log(f"rule share by channel: {rule_share.to_dict()}")
    log(f"wrote {dst}")


if __name__ == "__main__":
    main()
