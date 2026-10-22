"""Shared helpers for scripts/telegram (paths, hashing, _meta.json)."""
from __future__ import annotations
import hashlib, json, os, sys, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "telegram_api"
INTERIM = ROOT / "data" / "interim" / "telegram"
DERIVED = ROOT / "data" / "derived" / "telegram"
TAXONOMY = Path(__file__).resolve().parent / "taxonomy.yaml"


def sha256_file(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def write_meta(out_path: Path, *, inputs: dict[str, Path], counts: dict, extra: dict | None = None,
               prompt_version: str | None = None) -> Path:
    meta = {
        "output": str(out_path.relative_to(ROOT)),
        "written_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "script": os.path.basename(sys.argv[0]),
        "inputs": {k: {"path": str(Path(v).resolve().relative_to(ROOT)), "sha256": sha256_file(Path(v))}
                   for k, v in inputs.items()},
        "prompt_version": prompt_version,
        "counts": counts,
    }
    if extra:
        meta.update(extra)
    mp = out_path.with_name(out_path.stem + "_meta.json")
    mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str))
    return mp


def log(msg: str) -> None:
    print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


# --- Kyiv city vs oblast flags for track rows (TELEGRAM_PIPELINE.md §5 "Oblast != city"; shared by 40_ and 50_) ---
import re as _re
KYIV_OBLAST_RE = _re.compile(r"Київщин|Київськ", _re.I)
KYIV_CITY_RE = _re.compile(r"(?<![А-Яа-яІіЇїЄєҐґ'’])Ки[їє]в(а|у|ом|і)?(?![А-Яа-яІіЇїЄєҐґ])", _re.I)


def kyiv_flags(tr):
    """Returns (kyiv_city, kyiv_heading, kyiv_oblast) boolean Series for a tracks frame with columns
    oblast_iso, settlement_raw, settlement_role, heading_raw.
    city    = oblast_iso UA-30, or settlement Київ in a bare/location role with no oblast resolved
    heading = heading_raw names Київ/Києва (not Київщина), or settlement Київ in a target role; never also city
    oblast  = UA-32 or Київщина anywhere (kept separate, never folded into city)"""
    sett = tr.settlement_raw.fillna(""); head = tr.heading_raw.fillna("")
    sett_city = sett.map(lambda s: bool(KYIV_CITY_RE.search(s)) and not KYIV_OBLAST_RE.search(s))
    city = (tr.oblast_iso == "UA-30") | (sett_city & tr.settlement_role.isin(["bare", "location"]) & tr.oblast_iso.isna())
    heading = (head.map(lambda s: bool(KYIV_CITY_RE.search(s)) and not KYIV_OBLAST_RE.search(s)) | (sett_city & tr.settlement_role.eq("target"))) & ~city
    oblast = (tr.oblast_iso == "UA-32") | sett.map(lambda s: bool(KYIV_OBLAST_RE.search(s))) | head.map(lambda s: bool(KYIV_OBLAST_RE.search(s)))
    return city.astype(bool), heading.astype(bool), oblast.astype(bool)
