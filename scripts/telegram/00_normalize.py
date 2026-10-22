#!/usr/bin/env python
"""L1: data/raw/telegram_api/*.jsonl -> data/interim/telegram/posts.parquet

One row per post, all channels, war period only (>= 2022-02-24 Kyiv date).
Drops empty-text posts (album photos). Idempotent; writes posts_meta.json.
"""
from __future__ import annotations
import json, unicodedata, re
from zoneinfo import ZoneInfo
import pandas as pd
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import RAW_DIR, INTERIM, write_meta, log

KYIV = ZoneInfo("Europe/Kyiv")
WAR_START = pd.Timestamp("2022-02-24", tz=KYIV)
WS = re.compile(r"[ \t  ​‌‍﻿]+")
NL = re.compile(r"\s*\n\s*")
# anything non-alphanumeric, non-punctuation, non-space counts as a symbol/emoji lead
_VS = {"️", "︎", "‍"}


def norm_text(t: str) -> str:
    t = unicodedata.normalize("NFC", t)
    t = WS.sub(" ", t)
    t = NL.sub("\n", t)
    return t.strip()


def lead_emoji(t: str) -> str | None:
    """First grapheme if it is a symbol/emoji (category So/Sk or a flag), else None."""
    t = t.lstrip()
    if not t:
        return None
    ch = t[0]
    cat = unicodedata.category(ch)
    if cat in ("So", "Sk") or 0x1F1E6 <= ord(ch) <= 0x1F1FF:
        # strip variation selectors / skin tones that follow
        out = ch
        for c in t[1:3]:
            if c in _VS or 0x1F3FB <= ord(c) <= 0x1F3FF:
                out += c
            else:
                break
        return out.replace("️", "")
    return None


def main() -> None:
    INTERIM.mkdir(parents=True, exist_ok=True)
    files = sorted(RAW_DIR.glob("*.jsonl"))
    frames, counts = [], {}
    for f in files:
        ch = f.stem
        rows = []
        n_raw = n_empty = n_prewar = 0
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                n_raw += 1
                text = (r.get("text") or "")
                if not text.strip():
                    n_empty += 1
                    continue
                ts = pd.Timestamp(r["date_utc"])
                if ts.tzinfo is None:
                    ts = ts.tz_localize("UTC")
                ts_utc = ts.tz_convert("UTC")
                ts_kyiv = ts_utc.tz_convert(KYIV)
                if ts_kyiv < WAR_START:
                    n_prewar += 1
                    continue
                ed = r.get("edit_date_utc")
                ed_ts = pd.Timestamp(ed).tz_convert("UTC") if ed else pd.NaT
                tn = norm_text(text)
                rows.append({
                    "channel": ch,
                    "msg_id": int(r["msg_id"]),
                    "ts_utc": ts_utc,
                    "ts_kyiv_str": ts_kyiv.isoformat(),
                    "date_kyiv": ts_kyiv.date().isoformat(),
                    "text": text,
                    "text_norm": tn,
                    "n_chars": len(tn),
                    "has_media": bool(r.get("has_media")),
                    "edit_ts_utc": ed_ts,
                    "fwd_from": r.get("forwarded_from_channel"),
                    "lead_emoji": lead_emoji(tn),
                    "views": r.get("views"),
                    "year": ts_kyiv.year,
                })
        counts[ch] = {"raw": n_raw, "dropped_empty_text": n_empty, "dropped_prewar": n_prewar, "kept": len(rows)}
        log(f"{ch}: raw={n_raw} empty={n_empty} prewar={n_prewar} kept={len(rows)}")
        frames.append(pd.DataFrame(rows))
    df = pd.concat(frames, ignore_index=True)
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    df["edit_ts_utc"] = pd.to_datetime(df["edit_ts_utc"], utc=True)
    # ts_kyiv as tz-aware column (parquet stores UTC instant + tz metadata)
    df["ts_kyiv"] = df["ts_utc"].dt.tz_convert(KYIV)
    df = df.drop(columns=["ts_kyiv_str"])
    df = df.sort_values(["channel", "msg_id"]).reset_index(drop=True)
    df = df.drop_duplicates(["channel", "msg_id"])
    cols = ["channel", "msg_id", "ts_utc", "ts_kyiv", "date_kyiv", "text", "text_norm", "n_chars",
            "has_media", "edit_ts_utc", "fwd_from", "lead_emoji", "views", "year"]
    df = df[cols]
    out = INTERIM / "posts.parquet"
    df.to_parquet(out, index=False)
    total = {"rows": int(len(df)),
             "dropped_empty_text": int(sum(c["dropped_empty_text"] for c in counts.values())),
             "dropped_prewar": int(sum(c["dropped_prewar"] for c in counts.values())),
             "per_channel": counts}
    write_meta(out, inputs={f.stem: f for f in files}, counts=total,
               extra={"timezone": "Europe/Kyiv (zoneinfo)", "war_start_kyiv": "2022-02-24"})
    log(f"wrote {out} rows={len(df)}")


if __name__ == "__main__":
    main()
