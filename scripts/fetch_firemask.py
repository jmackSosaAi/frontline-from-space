"""Fetch VIIRS 375 m fire-mask granules (VNP14IMG = S-NPP, VJ114IMG = NOAA-20, collection 002)
from LAADS for the observability tier-3 stratified sample (set O, allowed pre-tag; DESIGN D9, PREREG s2).

Sample (DESIGN s2 / PREREG s2): 2 days per ISO week per satellite, ISO weeks 2022-W01 .. 2025-W52,
days drawn with random.Random(20261014) independently per satellite and week. Only granules whose
footprint intersects the front corridor (CMR spatial search) are downloaded.

Fallback (DESIGN s5): if the first 5 downloads run at < 5 granules/min or any is > 15 MB, run with
--fallback: 1 day per fortnight per satellite on the core Donbas box only.

Gate note: these files are the fire algorithm's per-pixel mask (classes 0-9). They also carry the
fire-pixel (FP_*) arrays. This script only checks the file signature; it never opens the contents.
Analysis of mask classes 7-9 or FP_* for C1 dates (2022-04-03 .. 2024-07-07) must wait for prereg-v1.

Idempotent: files already on disk with the expected size and HDF5 signature are skipped.
Manifest records go to data/manifest_parts/observability-firemask.json (not MANIFEST.json).
Usage: python3 -I scripts/fetch_firemask.py [--plan-only] [--limit N] [--fallback] [--workers K]
"""
import argparse, csv, datetime as dt, hashlib, json, os, pathlib, random, sys, time, threading
import urllib.request, urllib.parse, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/firemask"
PART = ROOT / "data/manifest_parts/observability-firemask.json"
SEED = 20261014
PRODUCTS = {"S-NPP": ("VNP14IMG", "C2734202914-LPCLOUD"), "NOAA-20": ("VJ114IMG", "C2734197957-LPCLOUD")}
# Fixed front corridor (W,S,E,N): Kherson - Zaporizhzhia - Donetsk - Luhansk - Kharkiv arc, drawn from
# geography only (no wartime control data). Fallback box = core Donbas.
CORRIDOR = (32.5, 46.3, 40.0, 50.5)
CORE_BOX = (36.5, 47.3, 39.0, 49.3)
FIRST_WEEK, LAST_WEEK = (2022, 1), (2025, 52)
LAADS = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5200"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
HDF5_SIG = b"\x89HDF\r\n\x1a\n"


def load_env():
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1); env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env()
UA = f"frontline-from-space research ({ENV.get('CONTACT_EMAIL', 'jmackney@uchicago.edu')})"
TOKEN = ENV["EARTHDATA_TOKEN"]


def get(url, auth=False, timeout=300, tries=4):
    h = {"User-Agent": UA}
    if auth: h["Authorization"] = f"Bearer {TOKEN}"
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
            return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404): return e.code, b""
            err = e
        except Exception as e:
            err = e
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"{url}: {err}")


def iso_weeks():
    d = dt.date.fromisocalendar(*FIRST_WEEK, 1)
    end = dt.date.fromisocalendar(*LAST_WEEK, 7)
    while d <= end:
        yield d.isocalendar()[:2], d
        d += dt.timedelta(days=7)


def sample_plan(fallback):
    rng = random.Random(SEED)
    rows = []
    for sat in PRODUCTS:
        for (y, w), monday in iso_weeks():
            if fallback:
                if w % 2 == 0: continue  # one day per fortnight (odd ISO weeks)
                days = [rng.randrange(14)]
            else:
                days = sorted(rng.sample(range(7), 2))
            for k in days:
                d = monday + dt.timedelta(days=k)
                rows.append({"satellite": sat, "product": PRODUCTS[sat][0], "iso_year": y, "iso_week": w,
                             "date": d.isoformat(), "doy": d.timetuple().tm_yday})
    return rows


def cmr_granules(concept, date, box):
    q = urllib.parse.urlencode({"collection_concept_id": concept, "bounding_box": ",".join(map(str, box)),
                                "temporal": f"{date}T00:00:00Z,{date}T23:59:59Z", "page_size": 100})
    st, b = get(f"{CMR}?{q}")
    if st != 200: raise RuntimeError(f"CMR {st}")
    return [(e["producer_granule_id"], e["time_start"], e.get("day_night_flag", ""), e.get("granule_size", ""))
            for e in json.loads(b)["feed"]["entry"]]


def build_granule_list(plan, box, path):
    """CMR spatial search per satellite-day; LAADS URL built from the granule id (LAADS file name = CMR
    producer_granule_id + .nc, same production timestamp; checked 2026-10-21). Day = the id's A-date."""
    if path.exists():
        return list(csv.DictReader(path.open()))
    out = []
    for i, p in enumerate(plan):
        for gid, t0, dn, mb in cmr_granules(PRODUCTS[p["satellite"]][1], p["date"], box):
            yd = gid.split(".")[1][1:]  # A2022004 -> 2022004
            if int(yd[:4]) != int(p["date"][:4]) or int(yd[4:]) != p["doy"]: continue  # CMR edge overlap
            out.append({**p, "granule": gid + ".nc", "time_start": t0, "day_night": dn, "cmr_mb": mb,
                        "url": f"{LAADS}/{p['product']}/{yd[:4]}/{yd[4:]}/{gid}.nc"})
        if i % 50 == 0: print(f"  searched {i + 1}/{len(plan)} sat-days, {len(out)} granules", flush=True)
        time.sleep(0.2)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    return out


LOCK = threading.Lock()


def save_part(man):
    PART.parent.mkdir(parents=True, exist_ok=True)
    tmp = PART.with_suffix(".tmp"); tmp.write_text(json.dumps(man, indent=1)); tmp.replace(PART)


def fetch(g, man, done):
    fn = g["granule"]; dest = OUT / g["product"] / g["date"][:4] / fn
    if fn in done and dest.exists(): return "skip", 0, 0.0
    t0 = time.time()
    st, b = get(g["url"], auth=True)
    el = time.time() - t0
    if st != 200: return f"HTTP{st}", 0, el
    if not b: return "EMPTY", 0, el
    if not b.startswith(HDF5_SIG): return "BADSIG", len(b), el
    if g["cmr_mb"] and abs(len(b) / 2**20 - float(g["cmr_mb"])) > 0.05 * float(g["cmr_mb"]) + 0.01:
        return "SIZE_MISMATCH", len(b), el
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part"); tmp.write_bytes(b); tmp.replace(dest)
    rec = {"file": fn, "url": g["url"], "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(), "set": "O",
           "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "satellite": g["satellite"], "granule_date": g["date"], "day_night": g["day_night"]}
    with LOCK:
        man.append(rec); done.add(fn); save_part(man)
    time.sleep(0.5)
    return "ok", len(b), el


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan-only", action="store_true"); ap.add_argument("--fallback", action="store_true")
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    tag = "fallback" if a.fallback else "full"
    box = CORE_BOX if a.fallback else CORRIDOR
    plan = sample_plan(a.fallback)
    plan_csv = OUT / f"sample_plan_{tag}.csv"
    with plan_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(plan[0])); w.writeheader(); w.writerows(plan)
    print(f"plan: {len(plan)} satellite-days -> {plan_csv}")
    gl = build_granule_list(plan, box, OUT / f"granules_{tag}.csv")
    tot = sum(float(g["cmr_mb"] or 0) * 2**20 for g in gl)
    print(f"granules intersecting corridor: {len(gl)}, listed size {tot / 1e9:.2f} GB")
    if a.plan_only: return
    if tot > 30e9: sys.exit("listed size exceeds 30 GB budget; run with --fallback")
    man = json.loads(PART.read_text()) if PART.exists() else []
    done = {m["file"] for m in man}
    todo = [g for g in gl if g["granule"] not in done]
    if a.limit: todo = todo[:a.limit]
    t_start = time.time(); n_ok = 0; bad = []
    with ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(fetch, g, man, done): g for g in todo}
        for i, fu in enumerate(as_completed(futs), 1):
            g = futs[fu]
            try: st, nb, el = fu.result()
            except Exception as e: st, nb, el = f"ERR {e}", 0, 0
            if st == "ok": n_ok += 1
            elif st != "skip": bad.append((g["granule"], st)); print("FAIL", g["granule"], st, flush=True)
            if i % 100 == 0 or i == len(todo):
                rate = n_ok / max(time.time() - t_start, 1) * 60
                print(f"  {i}/{len(todo)} ok={n_ok} fail={len(bad)} rate={rate:.1f}/min", flush=True)
    rate = n_ok / max(time.time() - t_start, 1) * 60
    print(f"done: ok={n_ok} fail={len(bad)} rate={rate:.1f} granules/min")
    if bad:
        (OUT / f"failures_{tag}.csv").write_text("granule,status\n" + "".join(f"{g},{s}\n" for g, s in bad))


if __name__ == "__main__":
    main()
