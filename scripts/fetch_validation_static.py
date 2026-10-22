"""Fetch set V refresh + static layers (all allowed before the prereg tag; no fire or control data).
  (a) Bellingcat TimeMap incidents: refetch; keep old file, save a dated copy only if content changed.
      Do No Harm License -> LICENSES/.
  (b) ESA WorldCover 2021 v200 10 m tiles covering Ukraine (+ any tile holding a V event), AWS open bucket.
  (c) Natural Earth 10 m admin0 / admin1.
  (d) Ukraine admin boundaries: HDX COD-AB (OCHA) + geoBoundaries gbOpen UKR ADM0-3.
  (e) GeoNames UA.zip gazetteer.
Idempotent: skips files already recorded in data/manifest_parts/validation-static.json and present on disk.
Writes manifest records to that part file (not MANIFEST.json; other fetchers run in parallel).
Run with: python3 -I scripts/fetch_validation_static.py"""
import datetime, hashlib, json, pathlib, sys, time, urllib.request, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
PART = ROOT / "data/manifest_parts/validation-static.json"
LIC = ROOT / "LICENSES"
MAX_BYTES = 30 * 1024**3


def contact():
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("CONTACT_EMAIL="):
            return line.split("=", 1)[1].strip().strip('"\'')
    return "jmackney@uchicago.edu"


UA = f"frontline-from-space research ({contact()})"
man = json.loads(PART.read_text()) if PART.exists() else []
done = {m["file"]: m for m in man}
total = 0


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def save_part():
    PART.parent.mkdir(parents=True, exist_ok=True)
    PART.write_text(json.dumps(man, indent=1))


def get(url, dest, sig, set_="static", rows=None, force=False):
    """Stream url to dest; validate status, size, signature; record. Returns manifest entry or None."""
    global total
    rel = str(dest.relative_to(RAW))
    if not force and rel in done and dest.exists():
        return done[rel]
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    h = hashlib.sha256(); n = 0
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
            if r.status != 200:
                print("FAIL", rel, "HTTP", r.status); return None
            head = None
            while True:
                b = r.read(1 << 20)
                if not b: break
                if head is None: head = b[:16]
                f.write(b); h.update(b); n += len(b)
    except Exception as e:
        print("FAIL", rel, e); tmp.unlink(missing_ok=True); return None
    if n == 0 or not any(head.startswith(s) for s in sig):
        print("BAD", rel, n, head); tmp.unlink(missing_ok=True); return None
    tmp.replace(dest); total += n
    e = {"file": rel, "url": url, "bytes": n}
    if rows is not None:
        e["rows"] = rows(dest)
    e.update({"sha256": h.hexdigest(), "set": set_, "retrieved_utc": now()})
    man[:] = [m for m in man if m["file"] != rel]; man.append(e); done[rel] = e
    save_part(); print("ok", rel, n); time.sleep(1)
    if total > MAX_BYTES:
        sys.exit("STOP: group byte budget exceeded")
    return e


ZIP = [b"PK\x03\x04"]; JSONSIG = [b"{", b"["]; TIF = [b"II*\x00", b"MM\x00*", b"II+\x00"]
TXT = [b""]  # any non-empty text


def zip_rows(member):
    def f(p):
        with zipfile.ZipFile(p) as z:
            with z.open(member) as fh:
                return sum(1 for _ in fh)
    return f


# ---------- (a) Bellingcat TimeMap ----------
BC_URL = "https://bellingcat-embeds.ams3.cdn.digitaloceanspaces.com/production/ukr/timemap/api.json"
old = RAW / "events/bellingcat_timemap.json"
old_sha = hashlib.sha256(old.read_bytes()).hexdigest() if old.exists() else None
stamp = datetime.date.today().isoformat()
cand = RAW / f"events/bellingcat_timemap_{stamp}.json"
if not cand.exists():
    e = get(BC_URL, cand, JSONSIG, "validation", rows=lambda p: len(json.loads(p.read_text())), force=True)
    if e and e["sha256"] == old_sha:
        print("Bellingcat unchanged since previous pull; dropping duplicate copy")
        cand.unlink(); man[:] = [m for m in man if m["file"] != e["file"]]; done.pop(e["file"], None); save_part()
LIC.mkdir(exist_ok=True)
get("https://raw.githubusercontent.com/bellingcat/ukraine-timemap/main/LICENSE.md",
    RAW / "licenses/bellingcat_ukraine-timemap_LICENSE.md", TXT, "license")
lic_src = RAW / "licenses/bellingcat_ukraine-timemap_LICENSE.md"
if lic_src.exists():
    (LIC / "bellingcat_ukraine-timemap_DoNoHarm_LICENSE.md").write_bytes(lic_src.read_bytes())

# ---------- (d) boundaries (before WorldCover: ADM0 picks the tiles) ----------
gb = RAW / "boundaries/geoboundaries"
meta = get("https://www.geoboundaries.org/api/current/gbOpen/UKR/ALL/", gb / "gbOpen_UKR_ALL_api.json", JSONSIG)
if meta:
    for lvl in json.loads((gb / "gbOpen_UKR_ALL_api.json").read_text()):
        t = lvl["boundaryType"]
        get(lvl["gjDownloadURL"], gb / f"geoBoundaries-UKR-{t}.geojson", JSONSIG)
        get(lvl["staticDownloadLink"], gb / f"geoBoundaries-UKR-{t}-all.zip", ZIP)
cod = RAW / "boundaries/cod_ab_ukr"
try:
    req = urllib.request.Request("https://data.humdata.org/api/3/action/package_show?id=cod-ab-ukr", headers={"User-Agent": UA})
    pkg = json.loads(urllib.request.urlopen(req, timeout=120).read())["result"]
    cod.mkdir(parents=True, exist_ok=True)
    (cod / "hdx_package_show.json").write_text(json.dumps(pkg, indent=1))
    for r in pkg["resources"]:
        if r["name"].endswith((".shp.zip", ".xlsx")):
            get(r["url"], cod / r["name"], ZIP)
except Exception as ex:
    print("FAIL COD-AB metadata", ex)

# ---------- (c) Natural Earth ----------
ne = RAW / "boundaries/naturalearth"
for n in ("ne_10m_admin_0_countries", "ne_10m_admin_1_states_provinces"):
    get(f"https://naciscdn.org/naturalearth/10m/cultural/{n}.zip", ne / f"{n}.zip", ZIP)

# ---------- (e) GeoNames ----------
get("https://download.geonames.org/export/dump/UA.zip", RAW / "gazetteer/geonames_UA.zip", ZIP, rows=zip_rows("UA.txt"))
get("https://download.geonames.org/export/dump/readme.txt", RAW / "gazetteer/geonames_readme.txt", TXT, "license")

# ---------- (b) ESA WorldCover 2021 ----------
WC = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021"
wc = RAW / "worldcover"
get(f"{WC}/esa_worldcover_grid.geojson", wc / "esa_worldcover_grid.geojson", JSONSIG)


def rings(geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return [ring for poly in polys for ring in poly]


def inside(x, y, rs):
    c = False
    for ring in rs:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
    return c


adm0 = json.loads((gb / "geoBoundaries-UKR-ADM0.geojson").read_text())["features"][0]["geometry"]
urs = rings(adm0)
pts = [tuple(p) for r in urs for p in r]
ev = []  # V events, so every event has land cover even just over the border
for p in [RAW / "events/bellingcat_timemap.json"]:
    for e in json.loads(p.read_text()):
        try: ev.append((float(e["longitude"]), float(e["latitude"])))
        except Exception: pass
try:
    gc = json.loads((RAW / "events/geoconfirmed_Ukraine.json").read_text())
    recs = gc if isinstance(gc, list) else gc.get("placemarks") or gc.get("items") or []
    for e in recs:
        lat = e.get("latitude", e.get("lat")); lon = e.get("longitude", e.get("lon", e.get("lng")))
        if lat is not None and lon is not None: ev.append((float(lon), float(lat)))
except Exception as ex:
    print("note: geoconfirmed coords not parsed:", ex)
ev = [(x, y) for x, y in ev if 20 <= x <= 42 and 43 <= y <= 54]  # Ukraine + border strip; drop outliers
grid = json.loads((wc / "esa_worldcover_grid.geojson").read_text())["features"]
tiles = []
for f in grid:
    xs = [p[0] for r in rings(f["geometry"]) for p in r]; ys = [p[1] for r in rings(f["geometry"]) for p in r]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    if x1 < 21 or x0 > 41 or y1 < 43 or y0 > 53.5: continue
    m = 0.1
    hit = any(x0 - m <= x <= x1 + m and y0 - m <= y <= y1 + m for x, y in pts) \
        or inside((x0 + x1) / 2, (y0 + y1) / 2, urs) \
        or any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in ev)
    if hit: tiles.append(f["properties"]["ll_tile"])
print("WorldCover tiles:", len(tiles), sorted(tiles))
for t in sorted(tiles):
    fn = f"ESA_WorldCover_10m_2021_v200_{t}_Map.tif"
    get(f"{WC}/map/{fn}", wc / fn, TIF)
print("DONE; bytes this run:", total, "; records in part:", len(man))
