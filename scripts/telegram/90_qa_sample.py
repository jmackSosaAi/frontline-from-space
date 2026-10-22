#!/usr/bin/env python
"""L7 QA samples for the human checker (seed 20261014). No network, no LLM.

Typing:   50 posts per post_type (all of them if fewer), stratified on post_type, from posts_typed_final.parquet
          (falls back to posts_typed.parquet if 11_type_llm.py has not run; a note is printed).
Impacts:  200 incident rows from extract/impacts.parquet, stratified by channel (min 20 per channel, rest
          proportional) + 50 posts where the model returned an empty list (to measure missed incidents).
          Skipped with a message if 23_extract_impacts.py has not run.

Raw post text is needed by the checker, so the CSVs WITH text go to data/interim/telegram/qa/ (gitignored).
data/derived/telegram/qa/ gets text-free key copies (channel, msg_id, labels, blank columns) that can be committed.
Blank columns (human_*, chk_*) are for the checker: y/n, or the corrected value. Re-running overwrites with the same
sample (fixed seed) but never touches a filled-in sheet: if <name>.csv already has any non-blank human/chk cell the
fresh sample is written to <name>.new.csv instead.
"""
from __future__ import annotations
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from _common import INTERIM, DERIVED, write_meta, log

SEED = 20261014
PER_TYPE = 50
N_IMPACTS = 200
MIN_PER_CHANNEL = 20
N_EMPTY = 50
QA_INT = INTERIM / "qa"
QA_DER = DERIVED / "qa"
TYPED_FINAL = INTERIM / "posts_typed_final.parquet"
TYPED_RULES = INTERIM / "posts_typed.parquet"
IMPACTS = INTERIM / "extract" / "impacts.parquet"
IMPACTS_POSTS = INTERIM / "extract" / "impacts_posts.parquet"

TYPE_BLANK = ["human_post_type", "human_ok", "human_note"]
IMP_BLANK = ["chk_place_ok", "chk_weapon_ok", "chk_target_type_ok", "chk_casualties_ok", "chk_time_ok",
             "chk_missed_incidents_in_post", "chk_note"]
EMPTY_BLANK = ["chk_has_incident", "chk_note"]


def url(ch, mid):
    return f"https://t.me/{ch}/{int(mid)}"


def alloc(sizes: pd.Series, total: int, floor: int) -> pd.Series:
    n = sizes.clip(upper=floor).astype(int)
    rest = total - int(n.sum())
    room = (sizes - n).clip(lower=0)
    while rest > 0 and room.sum() > 0:
        add = np.floor(room / room.sum() * rest).astype(int).clip(upper=room)
        if add.sum() == 0:
            add = pd.Series(0, index=room.index); add[room.idxmax()] = 1
        n += add; room -= add; rest -= int(add.sum())
    return n


def write_sheet(df: pd.DataFrame, name: str, blanks: list[str], key_cols: list[str], inputs: dict, counts: dict):
    QA_INT.mkdir(parents=True, exist_ok=True); QA_DER.mkdir(parents=True, exist_ok=True)
    for c in blanks:
        df[c] = ""
    path = QA_INT / f"{name}.csv"
    if path.exists():
        old = pd.read_csv(path, dtype=str).fillna("")
        if any(c in old and (old[c] != "").any() for c in blanks):
            path = QA_INT / f"{name}.new.csv"
            log(f"{name}.csv already has human entries: writing the fresh sample to {path.name} instead")
    df.to_csv(path, index=False)
    key = QA_DER / f"{name}_key.csv"
    df[[c for c in key_cols + blanks if c in df.columns]].to_csv(key, index=False)
    write_meta(key, inputs=inputs, counts=counts, extra={"seed": SEED, "text_free": True,
                                                         "sheet_with_text": str(path.relative_to(INTERIM.parents[2]))})
    log(f"{name}: {len(df)} rows -> {path.name} (with text) + derived key")


def typing_sample():
    src = TYPED_FINAL if TYPED_FINAL.exists() else TYPED_RULES
    if src == TYPED_RULES:
        log("NOTE: posts_typed_final.parquet missing; sampling rule-typed posts only (candidates stay unconfirmed)")
    d = pd.read_parquet(src)
    d = d[d.post_type.notna()]
    parts = [g.sample(min(PER_TYPE, len(g)), random_state=SEED) for _, g in d.groupby("post_type")]
    s = pd.concat(parts).sort_values(["post_type", "channel", "msg_id"]).reset_index(drop=True)
    s["url"] = [url(c, m) for c, m in zip(s.channel, s.msg_id)]
    s["date_kyiv"] = s.date_kyiv.astype(str)
    cols = ["post_type", "type_method", "type_conf", "channel", "msg_id", "date_kyiv", "url", "text"]
    out = s[cols].copy()
    write_sheet(out, "qa_typing_sample", TYPE_BLANK,
                ["post_type", "type_method", "type_conf", "channel", "msg_id", "date_kyiv", "url"],
                {"typed": src}, {"rows": len(out), "per_type": out.post_type.value_counts().to_dict()})


def impacts_sample():
    if not IMPACTS.exists():
        log("impacts.parquet not found (23_extract_impacts.py not run): skipping impacts sample")
        return
    imp = pd.read_parquet(IMPACTS)
    typed = pd.read_parquet(TYPED_FINAL if TYPED_FINAL.exists() else TYPED_RULES, columns=["channel", "msg_id", "text"])
    sizes = imp.channel.value_counts()
    n = alloc(sizes, N_IMPACTS, MIN_PER_CHANNEL)
    s = pd.concat([imp[imp.channel == ch].sample(int(k), random_state=SEED) for ch, k in n.items()])
    s = s.merge(typed, on=["channel", "msg_id"], how="left").sort_values(["channel", "msg_id", "incident_idx"])
    s["url"] = [url(c, m) for c, m in zip(s.channel, s.msg_id)]
    model_cols = ["incident_idx", "n_incidents_in_post", "event_date", "event_time", "time_is_post_time",
                  "oblast_raw", "raion_raw", "settlement_raw", "location_withheld", "weapon_raw", "target_type",
                  "killed", "wounded", "is_debris_only", "is_update", "damage_text_short", "confidence"]
    cols = ["channel", "msg_id", "url"] + model_cols + ["text"]
    out = s[cols].reset_index(drop=True)
    write_sheet(out, "qa_impacts_sample", IMP_BLANK, ["channel", "msg_id", "url"] + model_cols,
                {"impacts": IMPACTS}, {"rows": len(out), "by_channel": out.channel.value_counts().to_dict()})

    posts = pd.read_parquet(IMPACTS_POSTS)
    z = posts[(posts.n_incidents == 0) & ~posts.failed]
    z = z.sample(min(N_EMPTY, len(z)), random_state=SEED).merge(typed, on=["channel", "msg_id"], how="left")
    z["url"] = [url(c, m) for c, m in zip(z.channel, z.msg_id)]
    z = z.sort_values(["channel", "msg_id"])[["channel", "msg_id", "url", "text"]].reset_index(drop=True)
    write_sheet(z, "qa_impacts_empty_sample", EMPTY_BLANK, ["channel", "msg_id", "url"],
                {"impacts_posts": IMPACTS_POSTS}, {"rows": len(z)})


if __name__ == "__main__":
    typing_sample()
    impacts_sample()
