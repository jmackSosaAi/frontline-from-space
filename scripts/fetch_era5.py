"""Fetch observability covariates (set O, allowed pre-tag; PREREG data-set table, DESIGN D9 tier 2).

  * ERA5 single levels `total_cloud_cover` (tcc), hourly at VIIRS overpass hours
  * ERA5-Land `snow_depth` (m of snow), daily at 12 UTC

Ukraine bbox N53 W22 S44 E41, 2022-01-01 -> 2025-12-31, one NetCDF per dataset-year.
These are reanalysis fields (no fire detections, no control maps), so nothing here is gated.

Overpass hours: S-NPP/NOAA-20/NOAA-21 cross at ~01:30 and ~13:30 local solar time.
Over 22-41 E that is ~22:45-00:00 UTC (night) and ~10:45-12:00 UTC (day); off-nadir
orbits shift this by up to ~1.5 h, so we keep 22,23,00,01,02 and 09,10,11,12,13 UTC.

Re-runnable: submits CDS requests asynchronously, stores request ids in
data/raw/era5/requests.json, downloads what has completed, skips files already valid.
    .venv/bin/python -I scripts/fetch_era5.py            # submit + one pass
    .venv/bin/python -I scripts/fetch_era5.py --wait 3h  # keep polling up to 3 h
Manifest records go to data/manifest_parts/observability-era5.json (merged elsewhere).
Needs CDS_API_KEY in .env and the ERA5 / ERA5-Land (CC BY 4.0) licences accepted."""
import argparse, datetime, hashlib, json, pathlib, sys, time
from ecmwf.datastores import Client

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/era5"; OUT.mkdir(parents=True, exist_ok=True)
STATE = OUT / "requests.json"
PART = ROOT / "data/manifest_parts/observability-era5.json"; PART.parent.mkdir(parents=True, exist_ok=True)
ENV = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
KEY = ENV["CDS_API_KEY"].strip().strip('"\'')
URL = "https://cds.climate.copernicus.eu/api"
AREA = [53, 22, 44, 41]  # N, W, S, E
YEARS = range(2022, 2026)
HOURS_TCC = [f"{h:02d}:00" for h in (22, 23, 0, 1, 2, 9, 10, 11, 12, 13)]
MONTHS = [f"{m:02d}" for m in range(1, 13)]
DAYS = [f"{d:02d}" for d in range(1, 32)]

def jobs():
    for y in YEARS:
        yield (f"era5_tcc_{y}.nc", "reanalysis-era5-single-levels",
               {"product_type": ["reanalysis"], "variable": ["total_cloud_cover"], "year": [str(y)],
                "month": MONTHS, "day": DAYS, "time": HOURS_TCC, "area": AREA,
                "data_format": "netcdf", "download_format": "unarchived"})
        yield (f"era5land_snowdepth_{y}.nc", "reanalysis-era5-land",
               {"variable": ["snow_depth"], "year": [str(y)], "month": MONTHS, "day": DAYS,
                "time": ["12:00"], "area": AREA, "data_format": "netcdf", "download_format": "unarchived"})

def valid(p):
    """NetCDF3 ('CDF') or NetCDF4/HDF5 signature, and opens with one time-like dim > 300."""
    if not p.exists() or p.stat().st_size < 10_000: return None
    head = p.read_bytes()[:8]
    if not (head.startswith(b"CDF") or head.startswith(b"\x89HDF\r\n\x1a\n")): return None
    try:
        import netCDF4
        with netCDF4.Dataset(p) as ds:
            dims = {k: len(v) for k, v in ds.dimensions.items()}
            vars_ = [v for v in ds.variables if v in ("tcc", "sde", "sd")]
    except Exception:
        return None
    t = max((n for k, n in dims.items() if "time" in k), default=0)
    return {"dims": dims, "vars": vars_} if t > 300 and vars_ else None

def load(p, default): return json.loads(p.read_text()) if p.exists() else default
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def record(fn, coll, rid, info):
    man = [m for m in load(PART, []) if m["file"] != fn]
    b = (OUT / fn).read_bytes()
    man.append({"file": fn, "url": f"{URL}/retrieve/v1/jobs/{rid} ({coll})", "bytes": len(b),
                "sha256": hashlib.sha256(b).hexdigest(), "set": "observability",
                "retrieved_utc": now(), "dims": info["dims"], "variables": info["vars"]})
    PART.write_text(json.dumps(man, indent=1))

def one_pass(c, state):
    pending = 0
    man = {m["file"] for m in load(PART, [])}
    for fn, coll, req in jobs():
        p = OUT / fn
        if fn in man and valid(p): continue
        s = state.get(fn)
        if s is None:
            try:
                r = c.submit(coll, req)
            except Exception as e:
                print("SUBMIT-FAIL", fn, str(e)[:300]); pending += 1; continue
            state[fn] = s = {"request_id": r.request_id, "collection": coll, "submitted_utc": now()}
            STATE.write_text(json.dumps(state, indent=1)); print("submitted", fn, r.request_id)
            time.sleep(2); pending += 1; continue
        try:
            r = c.get_remote(s["request_id"]); st = r.status
        except Exception as e:
            print("POLL-FAIL", fn, str(e)[:200]); pending += 1; continue
        s["status"] = st; STATE.write_text(json.dumps(state, indent=1))
        if st == "successful":
            tmp = p.with_suffix(".part")
            r.download(str(tmp)); tmp.replace(p)
            info = valid(p)
            if info: record(fn, coll, s["request_id"], info); print("ok", fn, p.stat().st_size, info["dims"])
            else: print("BAD", fn, p.read_bytes()[:16]); p.unlink(); pending += 1
        elif st in ("failed", "rejected", "dismissed", "deleted"):
            print("FAILED", fn, st, "- resubmitting next pass"); state.pop(fn); STATE.write_text(json.dumps(state, indent=1)); pending += 1
        else:
            print("waiting", fn, s["request_id"], st); pending += 1
        time.sleep(1)
    return pending

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--wait", default="0", help="poll up to e.g. 90m / 3h")
    a = ap.parse_args(); w = a.wait
    limit = float(w[:-1]) * (3600 if w.endswith("h") else 60) if w[-1] in "hm" else float(w)
    c = Client(url=URL, key=KEY, progress=False)
    state = load(STATE, {}); t0 = time.time()
    while True:
        pending = one_pass(c, state)
        if not pending or time.time() - t0 > limit: break
        time.sleep(120)
    print("pending:", pending); sys.exit(0)

if __name__ == "__main__": main()
