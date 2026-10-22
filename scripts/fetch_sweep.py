"""Sweep fetch: extra validation-event (set V), covariate, E-period and static sources. All judged pre-tag-ok.

Gate (PREREG.md): nothing here is a fire detection or a territorial-control series for C1 (2022-04-03..2024-07-07),
Karabakh 2020 fires or Sudan 2023+ fires/events. Dated, geolocated incident data (set V) is allowed pre-tag
even when it covers C1 dates. VIINA: ONLY control_latest_2025.zip (E period, for the pre-tag SESOI recompute),
plus README and the GeoNames tessellation key (gn_UA_tess.geojson). Never the 2022-2024 control files.

GATED, deliberately not fetched (see GATED below): World Bank / UMD / JRC village-council cropland damage
(replication ZIP and 1.8 GB raw ZIP): the package holds bi-weekly ISW/DeepState village occupation indicators
for 2022-2024 and a FIRMS-stratified 2022 burnt-area validation table.

Idempotent: skips files already recorded in data/manifest_parts/sweep.json and present on disk.
Writes manifest records to that part file only (never data/MANIFEST.json). Licence texts -> LICENSES/.
Keys/emails come from .env and are never printed.

Run:  python3 -I scripts/fetch_sweep.py              (all file sources)
      python3 -I scripts/fetch_sweep.py --telegram   (also the @mod_russia public-preview scrape, ~1.5 h, resumable)
"""
import csv, datetime, hashlib, html, io, json, pathlib, re, sys, time, urllib.parse, urllib.request, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
PART = ROOT / "data/manifest_parts/sweep.json"
LIC = ROOT / "LICENSES"
MAX_BYTES = 30 * 1024**3
C1_START, C1_END = "2022-04-03", "2024-07-07"


def env(key, default=""):
    try:
        for line in (ROOT / ".env").read_text().splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"\'')
    except FileNotFoundError:
        pass
    return default


UA = f"frontline-from-space research ({env('CONTACT_EMAIL', 'jmackney@uchicago.edu')})"
man = json.loads(PART.read_text()) if PART.exists() else []
done = {m["file"]: m for m in man}
total = 0
skipped = []  # (name, reason)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def save_part():
    PART.parent.mkdir(parents=True, exist_ok=True)
    PART.write_text(json.dumps(man, indent=1, ensure_ascii=False))


def opener(url, headers=None, timeout=300):
    h = {"User-Agent": UA}
    h.update(headers or {})
    for attempt in range(5):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and attempt < 4:
                time.sleep(int(e.headers.get("Retry-After") or 0) or 15 * (attempt + 1)); continue
            raise


def record(rel, url, n, sha, set_, rows):
    e = {"file": rel, "url": url, "bytes": n}
    if rows is not None:
        e["rows"] = rows
    e.update({"sha256": sha, "set": set_, "retrieved_utc": now()})
    man[:] = [m for m in man if m["file"] != rel]; man.append(e); done[rel] = e
    save_part()
    return e


def get(url, dest, sig, set_, rows=None, force=False, pause=1.0):
    """Stream url to dest; validate status, size cap, signature; record. Returns manifest entry or None."""
    global total
    rel = str(dest.relative_to(RAW))
    if not force and rel in done and dest.exists():
        return done[rel]
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    h = hashlib.sha256(); n = 0; head = b""
    try:
        with opener(url) as r, open(tmp, "wb") as f:
            if r.status != 200:
                print("FAIL", rel, "HTTP", r.status); skipped.append((rel, f"HTTP {r.status}")); return None
            cl = int(r.headers.get("Content-Length") or 0)
            if cl and total + cl > MAX_BYTES:
                print("SKIP (size cap)", rel, cl); skipped.append((rel, f"over 30 GB cap ({cl} B)")); return None
            while True:
                b = r.read(1 << 20)
                if not b: break
                if not head: head = b[:16]
                f.write(b); h.update(b); n += len(b)
    except Exception as e:
        print("FAIL", rel, e); tmp.unlink(missing_ok=True); skipped.append((rel, f"error: {e}")); return None
    if n == 0 or not any(head.startswith(s) for s in sig):
        print("BAD", rel, n, head); tmp.unlink(missing_ok=True); skipped.append((rel, f"bad signature {head!r}")); return None
    tmp.replace(dest); total += n
    try:
        nrows = rows(dest) if rows else None
    except Exception as ex:
        print("note: row count failed", rel, ex); nrows = None
    e = record(rel, url, n, h.hexdigest(), set_, nrows)
    print("ok", rel, n, "rows=" + str(nrows)); time.sleep(pause)
    if total > MAX_BYTES:
        sys.exit("STOP: 30 GB byte budget exceeded")
    return e


def lic_copy(src, name):
    if src.exists():
        LIC.mkdir(exist_ok=True); (LIC / name).write_bytes(src.read_bytes())


def lic_note(name, text):
    LIC.mkdir(exist_ok=True); (LIC / name).write_text(text)


# ---------- signatures and row counters ----------
ZIP = [b"PK\x03\x04"]; RAR = [b"Rar!\x1a\x07"]; PDF = [b"%PDF"]; XML = [b"<?xml", b"\xef\xbb\xbf<?xml"]
JSONSIG = [b"{", b"[", b"\xef\xbb\xbf{", b"\xef\xbb\xbf["]; TXT = [b""]  # any non-empty text


def csv_rows(p):
    with open(p, newline="", encoding="utf-8", errors="replace") as f:
        return max(0, sum(1 for _ in csv.reader(f)) - 1)


def json_rows(p):
    d = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(d, list): return len(d)
    for k in ("features", "items", "data", "results"):
        if isinstance(d.get(k), list): return len(d[k])
    return None


def xlsx_rows(p):
    import openpyxl
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    n = 0
    for ws in wb.worksheets:
        mr = ws.max_row
        if not mr or mr <= 1:  # read_only dims missing: count non-empty rows
            mr = sum(1 for r in ws.iter_rows(values_only=True) if any(v is not None for v in r))
        n += max(0, mr - 1)
    wb.close()
    if n == 0:  # some writers emit sheets openpyxl reads as empty; count <row> tags directly
        with zipfile.ZipFile(p) as z:
            n = sum(max(0, len(re.findall(rb"<(?:\w+:)?row[ >]", z.read(m))) - 1)
                    for m in z.namelist() if m.startswith("xl/worksheets/sheet") and m.endswith(".xml"))
    return n


def xml_items(p):
    return p.read_text(encoding="utf-8").count("<state>")


def zip_csv_rows(p):
    with zipfile.ZipFile(p) as z:
        return sum(max(0, sum(1 for _ in z.open(m)) - 1) for m in z.namelist() if m.lower().endswith(".csv"))


def hdx(dataset):
    with opener(f"https://data.humdata.org/api/3/action/package_show?id={dataset}", timeout=120) as r:
        return json.loads(r.read())["result"]


def safe(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")


CC = {"cc-by-4.0": "https://creativecommons.org/licenses/by/4.0/legalcode.txt",
      "cc-by-sa-4.0": "https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt",
      "cc-by-igo-3.0": "https://creativecommons.org/licenses/by/3.0/igo/legalcode"}
for k, u in CC.items():
    ext = ".txt" if u.endswith(".txt") else ".html"
    if get(u, RAW / f"licenses/{k}_legalcode{ext}", TXT, "license"):
        lic_copy(RAW / f"licenses/{k}_legalcode{ext}", f"{k}_legalcode{ext}")

# ---------- 1. Militarnyi Deep Strike Map (set V; covers 2022-02-25 -> now) ----------
mil = RAW / "militarnyi"
for lang in ("en", "uk"):
    get(f"https://map.militarnyi.com/api/strikes/?lang={lang}", mil / f"strikes_{lang}.json", JSONSIG, "validation", json_rows)
get("https://map.militarnyi.com/api/taxonomy/", mil / "taxonomy.json", JSONSIG, "validation")
lic_note("militarnyi_deepstrike_NOTICE.md",
         "# Militarnyi Deep Strike Map (map.militarnyi.com)\n\nNo licence stated (checked 2026-10-22). Editorial content of "
         "Militarnyi (militarnyi.com). Use: cite as source; do not redistribute raw records without permission; publish "
         "derived aggregates only. robots.txt: 404. No ToS found banning automated access.\n\nGate note: records dated "
         f"{C1_START}..{C1_END} are set V (events) and allowed pre-tag, but must NOT be joined to FIRMS before the prereg-v1 tag.\n")

# ---------- 2. Saltan 2026 deep-strike replication package (2026 only) ----------
sz = RAW / "saltan2026_deepstrikes"
fn = "Russia_Ukraine_Deep_Strikes_Zenodo_v1.0.1.zip"
if get(f"https://zenodo.org/api/records/22377030/files/{fn}/content", sz / fn, ZIP, "validation", zip_csv_rows):
    with zipfile.ZipFile(sz / fn) as z:
        for m in z.namelist():
            base = m.rsplit("/", 1)[-1]
            if base in ("LICENSE.md", "LICENSE_CODE_MIT.txt", "THIRD_PARTY_DATA_NOTICE.md"):
                lic_note(f"saltan2026_deepstrikes_{base}", z.read(m).decode("utf-8", "replace"))

# ---------- 3. Kyiv city air-alert history (KMDA / Kyiv Digital) ----------
kv = RAW / "kyiv_air_alerts"
get("https://kyiv.digital/open-api/air-alert/history", kv / "kyiv_digital_air_alert_history.xml", XML, "validation", xml_items)
time.sleep(10)  # data.kyivcity.gov.ua Crawl-Delay 10; resource download link, not /api/
get("https://data.kyivcity.gov.ua/dataset/bb0f27d3-00e2-414a-9d6e-a8b6633f8a2a/resource/5e4fb8a8-f0c8-4a12-885f-192d1f0dba75/download/airalerts.json",
    kv / "kyivcity_airalerts.json", JSONSIG, "validation", json_rows, pause=10)
lic_note("kyiv_air_alerts_NOTICE.md",
         "# Kyiv city air-alert statistics (data.kyivcity.gov.ua dataset statystyka-povitrianykh-tryvoh-u-misti-kyievi-dep-municipal; "
         "kyiv.digital open-api)\n\nMunicipal open data of the Kyiv City State Administration. The portal's licence field is empty "
         "(checked 2026-10-22). Treat as open government data: attribute 'Kyiv City State Administration / Kyiv Digital'. "
         "Portal robots.txt disallows /api/ (Crawl-Delay 10); only the resource download link and the kyiv.digital open-api are used.\n")

# ---------- 4. Insecurity Insight (HDX, CC BY-SA) ----------
ii = RAW / "insecurity_insight"
try:
    pkg = hdx("ukraine-data-on-attacks-on-aid-operations-education-health-and-protection")
    ii.mkdir(parents=True, exist_ok=True); (ii / "hdx_package_show.json").write_text(json.dumps(pkg, indent=1))
    for r in pkg["resources"]:
        if r["url"].lower().endswith(".xlsx"):
            nm = safe(r["name"]); nm = nm if nm.lower().endswith(".xlsx") else nm + ".xlsx"
            get(r["url"], ii / nm, ZIP, "validation", xlsx_rows)
except Exception as ex:
    print("FAIL Insecurity Insight metadata", ex); skipped.append(("insecurity_insight", str(ex)))
lic_note("insecurity_insight_HDX_NOTICE.md", "# Insecurity Insight Ukraine incident data (HDX)\n\nLicence: CC BY-SA 4.0 (HDX "
         "'Creative Commons Attribution Share-Alike'); full text in cc-by-sa-4.0_legalcode.txt. Derived tables must be shared alike. "
         "Coordinates are censored (oblast-day use only).\n")

# ---------- 5. Sydorenko 2025 'Wildfires of war' (Zenodo, CC BY 4.0; static land cover, no FIRMS/control) ----------
sy = RAW / "sydorenko2025_wildfires_of_war"
for key, sig in [("Stable_frontline_for_AOI.rar", RAR), ("Files descriptions.docx", ZIP),
                 ("Landscape_level_Fuel_complexes_change_2016_2024.rar", RAR), ("LULC_Raster_datasets.rar", RAR)]:
    get(f"https://zenodo.org/api/records/16156197/files/{urllib.parse.quote(key)}/content", sy / safe(key), sig, "static")
lic_note("sydorenko2025_wildfires_of_war_NOTICE.md", "# Sydorenko 2025 'Wildfires of war' data, Zenodo 10.5281/zenodo.16156197\n\n"
         "Licence: CC BY 4.0 (cc-by-4.0_legalcode.txt). The single fixed AOI front-line vector is not a control time series.\n")

# ---------- 6. ICESat-2 3-D building damage (figshare 33442996, CC BY 4.0) ----------
fg = RAW / "icesat2_building_damage"
get("https://ndownloader.figshare.com/files/68249965", fg / "Figs_and_Data.zip", ZIP, "static")
get("https://ndownloader.figshare.com/files/68249962", fg / "Code.zip", ZIP, "static")
lic_note("icesat2_building_damage_figshare33442996_NOTICE.md", "# ICESat-2 building damage, figshare article 33442996\n\n"
         "Licence: CC BY 4.0 (cc-by-4.0_legalcode.txt). Contains UNOSAT damage points re-used by the authors; cite UNOSAT too.\n")

# ---------- 7. Russian fuel crisis refinery strikes (brawlerleg CSV + Wikipedia page) ----------
rf = RAW / "russian_fuel_crisis"
GH = "https://raw.githubusercontent.com/brawlerleg/Russian-Fuel-Crisis-2026/main"
get(f"{GH}/dataset.csv", rf / "brawlerleg_dataset.csv", TXT, "validation", csv_rows)
get(f"{GH}/getStrikes.py", rf / "brawlerleg_getStrikes.py", TXT, "license")
if get(f"{GH}/LICENSE", rf / "brawlerleg_LICENSE.txt", TXT, "license"):
    lic_copy(rf / "brawlerleg_LICENSE.txt", "brawlerleg_Russian-Fuel-Crisis-2026_MIT_LICENSE.txt")
page = urllib.parse.quote("2025–2026_Russian_fuel_crisis")
get(f"https://en.wikipedia.org/w/api.php?action=parse&page={page}&prop=text|wikitext|revid&format=json&formatversion=2",
    rf / "wikipedia_2025-2026_Russian_fuel_crisis_parse.json", JSONSIG, "validation")
lic_note("wikipedia_2025-2026_Russian_fuel_crisis_NOTICE.md", "# Wikipedia '2025–2026 Russian fuel crisis'\n\nText licence: "
         "CC BY-SA 4.0 (cc-by-sa-4.0_legalcode.txt); attribute Wikipedia contributors and the revision id stored in the parse JSON.\n")

# ---------- 8. Vadimkin air-raid sirens (MIT) ----------
vs = RAW / "air_raid_sirens_vadimkin"
VG = "https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main"
for f in ("datasets/official_data_en.csv", "datasets/volunteer_data_en.csv"):
    get(f"{VG}/{f}", vs / f.split("/")[-1], TXT, "validation", csv_rows)
get(f"{VG}/datasets/README.md", vs / "datasets_README.md", TXT, "license")
if get(f"{VG}/LICENSE", vs / "LICENSE.txt", TXT, "license"):
    lic_copy(vs / "LICENSE.txt", "vadimkin_ukrainian-air-raid-sirens-dataset_MIT_LICENSE.txt")

# ---------- 9. WHO SSA attacks on health care (HDX, CC BY) ----------
wh = RAW / "who_ssa"
try:
    pkg = hdx("ukraine-who-ssa")
    wh.mkdir(parents=True, exist_ok=True); (wh / "hdx_package_show.json").write_text(json.dumps(pkg, indent=1))
    for r in pkg["resources"]:
        if r["name"].lower().endswith(".csv"):
            get(r["url"], wh / safe(r["name"]), TXT, "validation", csv_rows)
        elif r["name"].lower().endswith(".pdf"):
            get(r["url"], wh / safe(r["name"]), PDF, "license")
except Exception as ex:
    print("FAIL WHO SSA metadata", ex); skipped.append(("who_ssa", str(ex)))
lic_note("who_ssa_NOTICE.md", "# WHO Surveillance System for Attacks on Health Care, Ukraine (HDX ukraine-who-ssa)\n\n"
         "Licence: CC BY (HDX 'Creative Commons Attribution International'); cc-by-4.0_legalcode.txt. Attribute WHO.\n")

# ---------- 10. Ivaniuk Russian losses (MIT; claimed figures) ----------
iv = RAW / "ivaniuk_losses"
IG = "https://raw.githubusercontent.com/PetroIvaniuk/2022-Ukraine-Russia-War-Dataset/main"
for f in ("russia_losses_equipment.json", "russia_losses_equipment_correction.json",
          "russia_losses_equipment_oryx.json", "russia_losses_personnel.json"):
    get(f"{IG}/data/{f}", iv / f, JSONSIG, "covariate", json_rows)
get(f"{IG}/README.md", iv / "README.md", TXT, "license")
if get(f"{IG}/LICENSE", iv / "LICENSE.txt", TXT, "license"):
    lic_copy(iv / "LICENSE.txt", "petroivaniuk_2022-Ukraine-Russia-War-Dataset_MIT_LICENSE.txt")

# ---------- 11-14. NRC buffer, NRC proximity, AQLITY, OCHA security incidents (HDX) ----------
for ds, folder, set_, lic in [
        ("nrc-frontline-hromada-buffer-analysis", "nrc_frontline_buffer", "E", "cc-by-4.0"),
        ("ukraine-nrc-humanitarian-proximity-analysis-data", "nrc_proximity", "E", "cc-by-4.0"),
        ("ukraine", "aqlity_frontline_monitoring", "E", "cc-by-igo-3.0"),
        ("ukraine-security-incidents", "ocha_security_incidents_2017_2021", "covariate", "cc-by-4.0")]:
    d = RAW / folder
    try:
        pkg = hdx(ds)
        d.mkdir(parents=True, exist_ok=True); (d / "hdx_package_show.json").write_text(json.dumps(pkg, indent=1))
        for r in pkg["resources"]:
            if r["url"].lower().endswith(".xlsx"):
                nm = safe(r["name"]); nm = nm if nm.lower().endswith(".xlsx") else nm + ".xlsx"
                # gate: NRC front-distance snapshots must be inside E (>= 2024-07-08)
                m = re.search(r"(20\d\d)", nm)
                if folder.startswith("nrc") and m and int(m.group(1)) < 2024:
                    skipped.append((nm, "gated: pre-E snapshot")); continue
                get(r["url"], d / nm, ZIP, set_, xlsx_rows)
        lic_note(f"{folder}_HDX_NOTICE.md", f"# HDX dataset {ds}\n\nLicence: {pkg.get('license_title')}; full text in {lic}_legalcode.txt. "
                 f"Source org: {(pkg.get('organization') or {}).get('title')}.\n")
    except Exception as ex:
        print("FAIL", ds, ex); skipped.append((ds, str(ex)))

# ---------- 15. VIINA: 2025 control ONLY + README + GeoNames tessellation key ----------
vi = RAW / "viina"
if get("https://media.githubusercontent.com/media/zhukovyuri/VIINA/main/Data/control_latest_2025.zip",
       vi / "control_latest_2025.zip", ZIP, "E", zip_csv_rows):
    # post-check: the file must not carry any C1 dates
    with zipfile.ZipFile(vi / "control_latest_2025.zip") as z:
        for m in z.namelist():
            with z.open(m) as fh:
                hdr = fh.readline().decode("utf-8", "replace")
                dates = set(re.findall(r"(20\d\d)-?(\d\d)-?(\d\d)", hdr))
                first = fh.readline().decode("utf-8", "replace")
                dates |= set(re.findall(r"\b(20\d\d)-?(\d\d)-?(\d\d)\b", first))
            ds_ = sorted("-".join(t) for t in dates)
            bad = [x for x in ds_ if C1_START <= x <= C1_END]
            print("VIINA 2025", m, "dates seen in header/first row:", ds_[:2], "...", ds_[-2:], "C1 hits:", len(bad))
            if bad:
                print("!! GATE: VIINA 2025 file contains C1 dates; review before use")
get("https://raw.githubusercontent.com/zhukovyuri/VIINA/main/README.md", vi / "README.md", TXT, "license")
get("https://raw.githubusercontent.com/zhukovyuri/VIINA/main/Data/gn_UA_tess.geojson", vi / "gn_UA_tess.geojson", JSONSIG, "static", json_rows)
if (vi / "README.md").exists():
    t = (vi / "README.md").read_text(encoding="utf-8")
    i = t.find("## Open Data Commons Open Database License")
    lic_note("viina_ODbL_NOTICE.md", "# VIINA (Zhukov), github.com/zhukovyuri/VIINA\n\nNo LICENSE file in the repo; the README states "
             "ODbL 1.0 for the database and DbCL 1.0 for contents. README licence section follows.\n\n" + (t[i:] if i >= 0 else ""))
if get("https://opendatacommons.org/licenses/odbl/1-0/", RAW / "licenses/odc-odbl-1.0.html", TXT, "license"):
    lic_copy(RAW / "licenses/odc-odbl-1.0.html", "odc-odbl-1.0.html")

# ---------- GATED (not fetched) ----------
GATED = [
    ("World Bank/UMD/JRC village-council cropland damage, replication ZIP (reproducibility.worldbank.org/catalog/375, 64 MB)",
     "README: holds bi-weekly village-council occupation / frontline indicators built from ISW and DeepState reports for "
     "2022-2024 (C1 territorial control) and dataset_with_dist_annual.csv stratified by FIRMS fire detections (2022). Gated."),
    ("World Bank DDH dataset 0066913 raw data ZIP (1.8 GB)",
     "Same package contents on DDH (conflict/occupation indicators 2022-2024, FIRMS-stratified validation). Gated."),
]
for n_, why in GATED:
    skipped.append((n_, "GATED: " + why))


# ---------- 16. @mod_russia public preview scrape (optional, resumable) ----------
def tg_scrape(channel="mod_russia", stop_date="2022-01-01", delay=2.0):
    out = RAW / f"telegram/{channel}_posts.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    seen = {}
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            try: p = json.loads(line); seen[p["id"]] = p
            except Exception: pass
    before = min(seen) if seen else None
    if seen and min(p["date"] for p in seen.values()) < stop_date:
        before = None  # backfill done; only refresh the head
    post_re = re.compile(r'data-post="%s/(\d+)"(.*?)(?=data-post="%s/|\Z)' % (channel, channel), re.S)
    pages = 0
    with open(out, "a", encoding="utf-8") as fo:
        url = f"https://t.me/s/{channel}"
        while True:
            u = url + (f"?before={before}" if before else "")
            try:
                with opener(u, timeout=60) as r:
                    page = r.read().decode("utf-8", "replace")
            except Exception as ex:
                print("TG fail", u, ex); time.sleep(30); continue
            pages += 1
            got = []
            for pid, body in post_re.findall(page):
                pid = int(pid)
                tm = re.search(r'<time datetime="([^"]+)"', body)
                tx = re.search(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', body, re.S)
                vw = re.search(r'class="tgme_widget_message_views">([^<]+)<', body)
                text = html.unescape(re.sub(r"<br\s*/?>", "\n", tx.group(1))) if tx else ""
                text = re.sub(r"<[^>]+>", "", text)
                got.append({"id": pid, "date": tm.group(1) if tm else None, "text": text, "views": vw.group(1) if vw else None})
            new = [g for g in got if g["id"] not in seen]
            for g in new:
                seen[g["id"]] = g; fo.write(json.dumps(g, ensure_ascii=False) + "\n")
            fo.flush()
            if pages % 50 == 0:
                print("TG pages", pages, "posts", len(seen), "oldest", min(p["date"] or "z" for p in seen.values()))
            if not got:
                break
            oldest = min(g["id"] for g in got)
            dmin = min((g["date"] or "9") for g in got)
            if dmin < stop_date or oldest <= 1 or (before is not None and oldest >= before):
                break
            if not new and before is None and seen and min(p["date"] for p in seen.values()) < stop_date:
                break  # head refresh caught up with existing data
            before = oldest
            time.sleep(delay)
    # rewrite deduplicated, sorted
    rows = sorted(seen.values(), key=lambda p: p["id"])
    out.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in rows), encoding="utf-8")
    b = out.read_bytes()
    record(str(out.relative_to(RAW)), f"https://t.me/s/{channel}", len(b), hashlib.sha256(b).hexdigest(), "validation", len(rows))
    lic_note(f"telegram_{channel}_NOTICE.md", f"# Telegram @{channel} public preview (t.me/s/{channel})\n\nGovernment communications "
             "of the Russian MoD; every number is a propaganda claim. Collected via the public web preview (t.me robots.txt 404), "
             "~2 s/page. Telegram terms: do not use data obtained from Telegram to train or fine-tune AI/ML models.\n")
    print("TG done", channel, "posts", len(rows), "pages", pages)


# backfill row counts that an earlier run could not compute (xlsx with missing dimensions)
for m in man:
    if m["file"].endswith(".xlsx") and not m.get("rows") and (RAW / m["file"]).exists():
        try: m["rows"] = xlsx_rows(RAW / m["file"])
        except Exception as ex: print("note: rows", m["file"], ex)
save_part()

if "--telegram" in sys.argv:
    tg_scrape()

print("\nSKIPPED / GATED:")
for n_, why in skipped:
    print(" -", n_, "|", why)
print("DONE; bytes this run:", total, "; records in part:", len(man))
