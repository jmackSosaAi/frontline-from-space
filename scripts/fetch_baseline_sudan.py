"""Fetch pre-war FIRMS yearly country CSVs for Sudan (set B baseline, allowed pre-tag).

PREREG set B: VIIRS S-NPP Sudan 2012-2022. T2 (Sudan 2023-04-15 ->) is gated until the
prereg-v1 tag, so this script refuses any year >= 2023.

Idempotent: files already on disk or already in data/MANIFEST.json are skipped. New manifest
records go to data/manifest_parts/baseline-sudan.json (MANIFEST.json is merged separately).

NOAA-20 Sudan (FIRMS path viirs-jpss1/) is NOT part of set B as registered (S-NPP only) and the
Ukraine baseline has no NOAA-20 files (fetch_baseline.py used the dead viirs-noaa20/ path, 404).
It is off by default; pass --noaa20 only after a decision to extend set B for all countries.
"""
import datetime, hashlib, json, os, pathlib, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/firms_country"
MAN = ROOT / "data/MANIFEST.json"
PART = ROOT / "data/manifest_parts/baseline-sudan.json"
GATE_YEAR = 2023  # T2 starts 2023-04-15; whole calendar year 2023+ is gated


def contact():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("CONTACT_EMAIL="):
                return line.split("=", 1)[1].strip().strip('"\'')
    return os.environ.get("CONTACT_EMAIL", "jmackney@uchicago.edu")


JOBS = [("viirs-snpp", y) for y in range(2012, 2023)]
if "--noaa20" in sys.argv:
    JOBS += [("viirs-jpss1", y) for y in range(2018, 2023)]
assert all(y < GATE_YEAR for _, y in JOBS), "gated year requested"

OUT.mkdir(parents=True, exist_ok=True)
PART.parent.mkdir(parents=True, exist_ok=True)
in_manifest = {m["file"] for m in json.loads(MAN.read_text())} if MAN.exists() else set()
part = json.loads(PART.read_text()) if PART.exists() else []
in_part = {m["file"] for m in part}
ua = f"frontline-from-space research ({contact()})"

for sensor, y in JOBS:
    fn = f"{sensor}_{y}_Sudan.csv"
    path = OUT / fn
    if path.exists() or fn in in_manifest:
        print("skip (have)", fn)
        continue
    url = f"https://firms.modaps.eosdis.nasa.gov/data/country/{sensor}/{y}/{fn}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=300) as r:
            status, b = r.status, r.read()
    except Exception as e:
        print("FAIL", fn, e)
        time.sleep(2)
        continue
    if status != 200 or not b or not b.startswith(b"latitude"):
        print("BAD", fn, status, b[:80])
        continue
    lines = b.rstrip().split(b"\n")
    dates = sorted({ln.split(b",")[5] for ln in lines[1:]})
    if dates and (dates[0][:4] != str(y).encode() or dates[-1][:4] != str(y).encode()):
        print("BAD dates", fn, dates[0], dates[-1])
        continue
    path.write_bytes(b)
    if fn not in in_part:
        part.append({"file": fn, "url": url, "bytes": len(b), "rows": len(lines) - 1,
                     "sha256": hashlib.sha256(b).hexdigest(), "set": "baseline",
                     "retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")})
        PART.write_text(json.dumps(part, indent=1))
    print("ok", fn, len(b))
    time.sleep(1)

if not PART.exists():
    PART.write_text("[]")
print(f"manifest part: {PART} ({len(part)} new records)")
