"""Fetch VIIRS granule footprints from NASA CMR (metadata only, no granule files).
Set O (observability, tier 1), allowed before the prereg tag: overpass counts over the
Ukraine bbox (22-41E, 44-53N), 2022-01-01 -> 2025-12-31.

Products: S-NPP VNP03IMG + VNP14IMG, NOAA-20 VJ114IMG, NOAA-21 VJ214IMG (from 2023-02).
Only geometry/time fields are kept. Granule file sizes are deliberately DROPPED: for the
fire products (xx14IMG) the file size scales with the number of fire pixels, which would leak
wartime fire information (C1) before the tag.

Raw: data/raw/cmr_footprints/<product>/<YYYY-MM>.jsonl.gz (one trimmed record per granule)
Tidy: data/raw/cmr_footprints/viirs_granule_footprints_2022_2025.csv (+ .parquet); count overpasses
      with is_latest == 1 (CMR keeps duplicate reprocessed copies of some granules)
Manifest records: data/manifest_parts/observability-footprints.json (not MANIFEST.json).
Idempotent: a month already on disk is skipped. Run with: python3 -I scripts/fetch_cmr_footprints.py
"""
import csv, datetime, gzip, hashlib, io, json, pathlib, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/cmr_footprints"
PART = ROOT / "data/manifest_parts/observability-footprints.json"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
BBOX = "22,44,41,53"
START, END = (2022, 1), (2025, 12)
PRODUCTS = {  # product: (collection concept id, satellite)
    "VNP03IMG": ("C2105092163-LAADS", "S-NPP"),
    "VNP14IMG": ("C2734202914-LPCLOUD", "S-NPP"),
    "VJ114IMG": ("C2734197957-LPCLOUD", "NOAA-20"),
    "VJ214IMG": ("C2831626262-LPCLOUD", "NOAA-21"),
}
FIRST = {"VJ214IMG": (2023, 2)}  # collection starts 2023-02-10


def contact():
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("CONTACT_EMAIL="):
            return line.split("=", 1)[1].strip().strip('"')
    return "jmackney@uchicago.edu"


UA = {"User-Agent": f"frontline-from-space research ({contact()})", "Accept": "application/json"}


def months():
    y, m = START
    while (y, m) <= END:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def wkt(spatial):
    geom = spatial.get("HorizontalSpatialDomain", {}).get("Geometry", {})
    polys = []
    for gp in geom.get("GPolygons", []):
        pts = gp["Boundary"]["Points"]
        ring = ", ".join(f"{p['Longitude']} {p['Latitude']}" for p in pts)
        if pts[0] != pts[-1]:
            ring += f", {pts[0]['Longitude']} {pts[0]['Latitude']}"
        polys.append(f"(({ring}))")
    for br in geom.get("BoundingRectangles", []):
        w, e, n, s = br["WestBoundingCoordinate"], br["EastBoundingCoordinate"], br["NorthBoundingCoordinate"], br["SouthBoundingCoordinate"]
        polys.append(f"(({w} {s}, {e} {s}, {e} {n}, {w} {n}, {w} {s}))")
    if not polys:
        return ""
    return "POLYGON " + polys[0] if len(polys) == 1 else "MULTIPOLYGON (" + ", ".join(polys) + ")"


def trim(item, product, sat):
    u = item["umm"]
    t = u["TemporalExtent"]["RangeDateTime"]
    return {"concept_id": item["meta"]["concept-id"], "granule_ur": u["GranuleUR"], "product": product,
            "satellite": sat, "start_utc": t["BeginningDateTime"], "end_utc": t.get("EndingDateTime", ""),
            "day_night": u.get("DataGranule", {}).get("DayNightFlag", ""), "footprint_wkt": wkt(u["SpatialExtent"])}


def fetch_month(product, cid, sat, y, m):
    t0 = f"{y:04d}-{m:02d}-01T00:00:00Z"
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    t1 = f"{ny:04d}-{nm:02d}-01T00:00:00Z"
    q = urllib.parse.urlencode({"collection_concept_id": cid, "bounding_box": BBOX, "temporal": f"{t0},{t1}",
                                "page_size": 2000, "sort_key": "start_date"})
    url = f"{CMR}?{q}"
    recs, after, hits = [], None, None
    while True:
        h = dict(UA)
        if after:
            h["CMR-Search-After"] = after
        r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120)
        if r.status != 200 or "json" not in r.headers.get("Content-Type", ""):
            raise RuntimeError(f"bad response {r.status} {r.headers.get('Content-Type')}")
        hits = int(r.headers["CMR-Hits"])
        d = json.loads(r.read())
        recs += [trim(it, product, sat) for it in d["items"]]
        after = r.headers.get("CMR-Search-After")
        time.sleep(0.5)
        if not d["items"] or len(recs) >= hits or not after:
            break
    # temporal is inclusive at both ends in CMR; keep granules starting inside the month
    recs = [x for x in recs if t0[:7] == x["start_utc"][:7]]
    if len(recs) == 0 or len({x["concept_id"] for x in recs}) != len(recs):
        raise RuntimeError(f"empty or duplicate result (hits={hits}, n={len(recs)})")
    if any(not x["footprint_wkt"] for x in recs):
        raise RuntimeError("granule without footprint")
    return url, recs


def gz_bytes(lines):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as g:
        g.write(("\n".join(lines) + "\n").encode())
    return buf.getvalue()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def main():
    PART.parent.mkdir(parents=True, exist_ok=True)
    man = json.loads(PART.read_text()) if PART.exists() else []
    by_file = {m["file"]: m for m in man}
    all_recs = []
    for product, (cid, sat) in PRODUCTS.items():
        (OUT / product).mkdir(parents=True, exist_ok=True)
        for y, m in months():
            if (y, m) < FIRST.get(product, START):
                continue
            rel = f"cmr_footprints/{product}/{y:04d}-{m:02d}.jsonl.gz"
            p = OUT / product / f"{y:04d}-{m:02d}.jsonl.gz"
            if p.exists() and rel in by_file:
                b = p.read_bytes()
                if hashlib.sha256(b).hexdigest() == by_file[rel]["sha256"]:
                    all_recs += [json.loads(l) for l in gzip.decompress(b).decode().splitlines() if l]
                    continue
            try:
                url, recs = fetch_month(product, cid, sat, y, m)
            except Exception as e:
                print("FAIL", product, y, m, e)
                continue
            b = gz_bytes(json.dumps(x, sort_keys=True) for x in recs)
            p.write_bytes(b)
            by_file[rel] = {"file": rel, "url": url, "bytes": len(b), "rows": len(recs),
                            "sha256": hashlib.sha256(b).hexdigest(), "set": "observability",
                            "retrieved_utc": now()}
            PART.write_text(json.dumps(list(by_file.values()), indent=1))
            all_recs += recs
            print("ok", product, f"{y}-{m:02d}", len(recs))
    # tidy table
    # CMR holds several reprocessed copies of some granules (same product + start time,
    # different production stamp in the GranuleUR). Flag the newest copy as the overpass to count.
    newest = {}
    for x in all_recs:
        k = (x["product"], x["start_utc"])
        if k not in newest or x["granule_ur"] > newest[k]:
            newest[k] = x["granule_ur"]
    for x in all_recs:
        x["is_latest"] = int(newest[(x["product"], x["start_utc"])] == x["granule_ur"])
    cols = ["concept_id", "granule_ur", "product", "satellite", "start_utc", "end_utc", "day_night", "is_latest", "footprint_wkt"]
    all_recs.sort(key=lambda x: (x["product"], x["start_utc"], x["granule_ur"]))
    s = io.StringIO()
    w = csv.DictWriter(s, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    w.writerows(all_recs)
    b = s.getvalue().encode()
    csv_path = OUT / "viirs_granule_footprints_2022_2025.csv"
    csv_path.write_bytes(b)
    rel = "cmr_footprints/viirs_granule_footprints_2022_2025.csv"
    by_file[rel] = {"file": rel, "url": f"derived from {CMR} (bbox {BBOX}); see per-month files",
                    "bytes": len(b), "rows": len(all_recs), "sha256": hashlib.sha256(b).hexdigest(),
                    "set": "observability", "retrieved_utc": now()}
    try:
        import pandas as pd
        df = pd.DataFrame(all_recs, columns=cols)
        for c in ("start_utc", "end_utc"):
            df[c] = pd.to_datetime(df[c], utc=True)
        pq = OUT / "viirs_granule_footprints_2022_2025.parquet"
        df.to_parquet(pq, index=False)
        pb = pq.read_bytes()
        relp = "cmr_footprints/viirs_granule_footprints_2022_2025.parquet"
        by_file[relp] = {"file": relp, "url": by_file[rel]["url"], "bytes": len(pb), "rows": len(df),
                         "sha256": hashlib.sha256(pb).hexdigest(), "set": "observability", "retrieved_utc": now()}
    except Exception as e:
        print("parquet skipped:", e)
    PART.write_text(json.dumps(list(by_file.values()), indent=1))
    print("tidy rows", len(all_recs))


if __name__ == "__main__":
    main()
