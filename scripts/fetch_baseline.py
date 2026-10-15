"""Fetch pre-war FIRMS yearly country CSVs (baseline only, allowed before prereg tag).
Ukraine 2012-2021; Azerbaijan/Armenia 2012-2019 (NOT 2020: contains the war).
Logs every download (url, bytes, sha256, UTC timestamp) to data/MANIFEST.json."""
import hashlib, json, time, urllib.request, datetime, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/firms_country"; MAN = ROOT / "data/MANIFEST.json"
JOBS = [("viirs-snpp", y, "Ukraine") for y in range(2012, 2022)]
JOBS += [("viirs-noaa20", y, "Ukraine") for y in range(2018, 2022)]
JOBS += [("viirs-snpp", y, c) for c in ("Azerbaijan", "Armenia") for y in range(2012, 2020)]
man = json.loads(MAN.read_text()) if MAN.exists() else []
done = {m["file"] for m in man}
for sensor, y, c in JOBS:
    fn = f"{sensor}_{y}_{c}.csv"
    if fn in done: continue
    url = f"https://firms.modaps.eosdis.nasa.gov/data/country/{sensor}/{y}/{fn}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "frontline-from-space research (jmackney@uchicago.edu)"})
        b = urllib.request.urlopen(req, timeout=180).read()
    except Exception as e:
        print("FAIL", fn, e); continue
    if not b.startswith(b"latitude"):
        print("BAD", fn, b[:80]); continue
    (OUT / fn).write_bytes(b)
    man.append({"file": fn, "url": url, "bytes": len(b), "rows": b.count(b"\n") - 1,
                "sha256": hashlib.sha256(b).hexdigest(), "set": "baseline",
                "retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")})
    MAN.write_text(json.dumps(man, indent=1))
    print("ok", fn, len(b)); time.sleep(1)
