"""Post-tag pull: gated C1 / T1 / T2 data. See planning/POST_TAG_PULL.md for the list, order and rationale.

REFUSES TO RUN unless:
  - git tag prereg-v1 exists and the working-tree PREREG.md equals the tagged one;
  - OSF project 3whtz has at least one registration (OSF_TOKEN from .env), or --osf-ok is passed;
  - for steps t1/t2/ucdp: predictions/transfer_v1.json is committed (H7: predictions before T data).

Idempotent: files on disk and recorded in data/manifest_parts/post_tag.json are skipped; FIRMS NRT chunks that
end within 3 days of today are refetched. Writes only the manifest part, never data/MANIFEST.json. Keys come from
.env and are never printed or written (URLs are recorded with {MAP_KEY}).

Run:  python3 -I scripts/fetch_post_tag.py                      (all steps except t1/t2/ucdp if no transfer_v1.json)
      python3 -I scripts/fetch_post_tag.py --only viina,firms_ua
      python3 -I scripts/fetch_post_tag.py --dry-run             (print plan, no network)
      python3 -I scripts/fetch_post_tag.py --owl-daily           (all Owl KMZ files instead of one per ISO week)
      python3 -I scripts/fetch_post_tag.py --register-acled data/raw/acled/<file>.csv
Steps (in order): viina firms_ua firms_ua_yearly economist perimeters owl matsala texty firms_ru firms_ru_yearly
                  t1 t2 ucdp
"""
import argparse, datetime as dt, hashlib, json, pathlib, subprocess, sys, time, urllib.error, urllib.parse, \
    urllib.request, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
PART = ROOT / "data/manifest_parts/post_tag.json"
LIC = ROOT / "LICENSES"
MAX_BYTES = 5 * 1024**3
FIRMS = "https://firms.modaps.eosdis.nasa.gov"
BBOX = {"ukraine": "22,44,41,53", "west_russia": "27,41,60,64", "sudan": "21.8,8.6,38.7,22.3"}
WAR_START = dt.date(2022, 2, 24)
NOAA21_SP_START = dt.date(2023, 3, 1)
SP_END_FALLBACK = dt.date(2026, 6, 30)
TODAY = dt.datetime.now(dt.timezone.utc).date()
STEPS = ["viina", "firms_ua", "firms_ua_yearly", "economist", "perimeters", "owl", "matsala", "texty",
         "firms_ru", "firms_ru_yearly", "t1", "t2", "ucdp"]
TRANSFER_STEPS = {"t1", "t2", "ucdp"}


def env(key, default=""):
    try:
        for line in (ROOT / ".env").read_text().splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"\'')
    except FileNotFoundError:
        pass
    return default


MAP_KEY = env("FIRMS_MAP_KEY")
UA = f"frontline-from-space research ({env('CONTACT_EMAIL', 'jmackney@uchicago.edu')})"
man = json.loads(PART.read_text()) if PART.exists() else []
done = {m["file"]: m for m in man}
total = 0
failures = []
DRY = False


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def redact(url):
    return url.replace(MAP_KEY, "{MAP_KEY}") if MAP_KEY else url


def save_part():
    PART.parent.mkdir(parents=True, exist_ok=True)
    PART.write_text(json.dumps(man, indent=1, ensure_ascii=False))


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)


def opener(url, headers=None, timeout=300):
    h = {"User-Agent": UA}
    h.update(headers or {})
    for attempt in range(5):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(int(e.headers.get("Retry-After") or 0) or 15 * (attempt + 1)); continue
            raise
        except urllib.error.URLError:
            if attempt < 4:
                time.sleep(15 * (attempt + 1)); continue
            raise


def get_json(url, headers=None):
    with opener(url, headers) as r:
        return json.loads(r.read())


def record(rel, url, n, sha, set_, serves, rows=None, extra=None):
    e = {"file": rel, "url": redact(url), "bytes": n}
    if rows is not None:
        e["rows"] = rows
    e.update({"sha256": sha, "set": set_, "serves": serves, "retrieved_utc": now()})
    e.update(extra or {})
    man[:] = [m for m in man if m["file"] != rel]; man.append(e); done[rel] = e
    save_part()
    return e


# ---------- signatures / validators ----------
ZIP = [b"PK\x03\x04"]; JSONSIG = [b"{", b"[", b"\xef\xbb\xbf{", b"\xef\xbb\xbf["]; ANY = [b""]
CSVSIG = [b"latitude"]; SHP = [b"\x00\x00\x27\x0a"]; DBF = [b"\x03", b"\x83", b"\x8b", b"\xf5"]


def csv_rows(p):
    with open(p, "rb") as f:
        return max(0, sum(1 for _ in f) - 1)


def zip_csv_rows(p):
    with zipfile.ZipFile(p) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        return sum(max(0, sum(1 for _ in z.open(n)) - 1) for n in names) if names else None


def fetch(url, dest, sig, set_, serves, rows=None, force=False, pause=1.0, extra=None):
    """Stream url to dest; check status, size cap, signature; record. Returns manifest entry or None."""
    global total
    rel = str(dest.relative_to(RAW))
    if not force and rel in done and dest.exists():
        return done[rel]
    if DRY:
        print("would fetch", rel, "<-", redact(url)); return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    h = hashlib.sha256(); n = 0; head = b""
    try:
        with opener(url) as r, open(tmp, "wb") as f:
            cl = int(r.headers.get("Content-Length") or 0)
            if cl and total + cl > MAX_BYTES:
                failures.append((rel, f"over cap ({cl} B)")); print("SKIP (cap)", rel); return None
            while True:
                b = r.read(1 << 20)
                if not b: break
                if len(head) < 16: head = (head + b)[:16]
                f.write(b); h.update(b); n += len(b)
    except Exception as e:
        tmp.unlink(missing_ok=True); failures.append((rel, f"error: {redact(str(e))}")); print("FAIL", rel); return None
    if n == 0 or not any(head.startswith(s) for s in sig):
        tmp.unlink(missing_ok=True); failures.append((rel, f"bad signature {head!r}")); print("BAD", rel, head); return None
    tmp.replace(dest); total += n
    try:
        nrows = rows(dest) if rows else None
    except Exception as ex:
        print("note: row count failed", rel, ex); nrows = None
    e = record(rel, url, n, h.hexdigest(), set_, serves, nrows, extra)
    print("ok", rel, n, "rows=" + str(nrows)); time.sleep(pause)
    if total > MAX_BYTES:
        sys.exit("STOP: byte cap exceeded")
    return e


def lic_note(name, text):
    if DRY: return
    LIC.mkdir(exist_ok=True)
    p = LIC / name
    if not p.exists(): p.write_text(text)


# ---------- gates ----------
def check_tag_gate(osf_ok):
    if git("rev-parse", "-q", "--verify", "refs/tags/prereg-v1").returncode != 0:
        sys.exit("GATE: tag prereg-v1 does not exist. Nothing fetched.")
    if git("diff", "--quiet", "prereg-v1", "--", "PREREG.md").returncode != 0:
        sys.exit("GATE: PREREG.md differs from prereg-v1. Put changes in DEVIATIONS.md, restore PREREG.md.")
    if osf_ok:
        print("gate: OSF registration check skipped by --osf-ok"); return
    tok = env("OSF_TOKEN")
    try:
        d = get_json("https://api.osf.io/v2/nodes/3whtz/registrations/",
                     {"Authorization": f"Bearer {tok}"} if tok else None)
        n = len(d.get("data", []))
    except Exception as e:
        sys.exit(f"GATE: could not verify OSF registration ({type(e).__name__}). Re-run with --osf-ok if registered.")
    if n < 1:
        sys.exit("GATE: OSF project 3whtz has no registration yet.")
    print(f"gate: prereg-v1 ok, OSF registrations: {n}")


def transfer_gate_ok():
    p = "predictions/transfer_v1.json"
    if not (ROOT / p).exists():
        return False, "predictions/transfer_v1.json missing"
    c = git("log", "-1", "--format=%H", "--", p).stdout.strip()
    if not c:
        return False, "transfer_v1.json not committed"
    if git("diff", "--quiet", "HEAD", "--", p).returncode != 0:
        return False, "transfer_v1.json has uncommitted changes"
    if git("merge-base", "--is-ancestor", "prereg-v1", c).returncode != 0:
        return False, "transfer_v1.json commit is not after prereg-v1"
    return True, c


# ---------- FIRMS API ----------
_calls = 0


def firms_throttle():
    """Every 20 calls, check mapkey_status; wait while near the 5,000 / 10 min limit."""
    global _calls
    _calls += 1
    if _calls % 20:
        return
    while True:
        try:
            s = get_json(f"{FIRMS}/mapserver/mapkey_status/?MAP_KEY={MAP_KEY}")
            if int(s.get("current_transactions", 0)) < int(s.get("transaction_limit", 5000)) - 600:
                return
            print("throttle: transactions", s.get("current_transactions"), "- waiting 60 s")
        except Exception:
            print("throttle: status check failed - waiting 60 s")
        time.sleep(60)


def firms_availability():
    """{source: (start, end)} from the data_availability endpoint; falls back to known boundaries."""
    out = {}
    try:
        with opener(f"{FIRMS}/api/data_availability/csv/{MAP_KEY}/ALL") as r:
            for line in r.read().decode().splitlines()[1:]:
                p = line.split(",")
                if len(p) >= 3 and p[0].startswith("VIIRS"):
                    out[p[0]] = (dt.date.fromisoformat(p[1]), dt.date.fromisoformat(p[2]))
    except Exception as e:
        print("note: data_availability failed, using fallbacks:", type(e).__name__)
    return out


def firms_plan(region, start, sensors, avail):
    """List of (source, chunk_start, ndays) covering start..today: SP to SP end, NRT after."""
    jobs = []
    for s in sensors:
        sp = f"VIIRS_{s}_SP"; nrt = f"VIIRS_{s}_NRT"
        sp_start = max(start, NOAA21_SP_START if s == "NOAA21" else start)
        sp_end = avail.get(sp, (None, SP_END_FALLBACK))[1]
        nrt_end = min(avail.get(nrt, (None, TODAY))[1], TODAY)
        for src, a, b in ((sp, sp_start, sp_end), (nrt, max(sp_end + dt.timedelta(1), start), nrt_end)):
            d = a
            while d <= b:
                n = min(5, (b - d).days + 1)
                jobs.append((src, d, n)); d += dt.timedelta(n)
    return jobs


def firms_validate(p, d0, n):
    lines = p.read_bytes().rstrip(b"\n").split(b"\n")
    hdr = lines[0].split(b",")
    if b"acq_date" not in hdr:
        return False, None
    i = hdr.index(b"acq_date"); lo, hi = d0.isoformat().encode(), (d0 + dt.timedelta(n - 1)).isoformat().encode()
    bad = sum(1 for ln in lines[1:] if not (lo <= ln.split(b",")[i] <= hi))
    return bad == 0, len(lines) - 1


def firms_api(region, start, sensors, set_, serves, avail):
    jobs = firms_plan(region, start, sensors, avail)
    print(f"FIRMS API {region}: {len(jobs)} chunks")
    for src, d0, n in jobs:
        rel_dir = RAW / "firms_api" / region / src / str(d0.year)
        dest = rel_dir / f"{d0.isoformat()}_{n}d.csv"
        rel = str(dest.relative_to(RAW))
        live = src.endswith("_NRT") and d0 + dt.timedelta(n - 1) >= TODAY - dt.timedelta(3)
        if rel in done and dest.exists() and not live:
            continue
        if DRY:
            print("would fetch", rel); continue
        firms_throttle()
        url = f"{FIRMS}/api/area/csv/{MAP_KEY}/{src}/{BBOX[region]}/{n}/{d0.isoformat()}"
        e = fetch(url, dest, CSVSIG, set_, serves, force=live, pause=0.3,
                  extra={"source": src, "bbox": BBOX[region], "chunk_start": d0.isoformat(), "days": n})
        if e is None:
            continue
        ok, nrows = firms_validate(dest, d0, n)
        if not ok:
            failures.append((rel, "dates outside chunk window")); print("BAD dates", rel)
        e["rows"] = nrows; e["final"] = not live; save_part()


def firms_yearly(country, sensors, years, set_, serves):
    for sensor in sensors:
        for y in years:
            fn = f"{sensor}_{y}_{country}.csv"
            fetch(f"{FIRMS}/data/country/{sensor}/{y}/{fn}", RAW / "firms_country_post_tag" / fn, CSVSIG,
                  set_, serves, csv_rows)


# ---------- steps ----------
def step_viina():
    for y in (2022, 2023, 2024, 2026):
        set_ = "C1" if y <= 2024 else "E-ext"
        fetch(f"https://media.githubusercontent.com/media/zhukovyuri/VIINA/main/Data/control_latest_{y}.zip",
              RAW / "viina" / f"control_latest_{y}.zip", ZIP, set_,
              "H4 H5 H6 H6b H9-H12 outcome; robustness 5" if y <= 2024 else "H13 / E extension", zip_csv_rows)


def step_economist():
    repo = "TheEconomist/the-economist-war-fire-model"
    files = ["ukraine_war_fires.csv", "control_status_of_fires_II.csv", "cloud_cover_in_ukraine_by_day.csv",
             "areas_of_control_daily_summary.csv", "firms_update_RU.csv"]
    have = {f for f in files if any(m["file"].startswith("economist/post_tag/") and m["file"].endswith("/" + f)
                                    and (RAW / m["file"]).exists() for m in man)}
    if have == set(files):
        return
    if DRY:
        print("would resolve", repo, "master SHA and fetch", sorted(set(files) - have)); return
    sha = get_json(f"https://api.github.com/repos/{repo}/commits?sha=master&per_page=1")[0]["sha"]
    for f in files:
        if f in have: continue
        fetch(f"https://raw.githubusercontent.com/{repo}/{sha}/output-data/{f}",
              RAW / "economist/post_tag" / sha[:10] / f, ANY, "C1+E",
              "robustness 5; war_fire benchmark; cloud vs ERA5 (H4); side-of-line check (H10); RU check (H13)",
              csv_rows, extra={"commit": sha})
    lic_note("economist_war_fire_model_CC-BY-4.0_NOTICE.md",
             "# The Economist war-fire model\n\ngithub.com/TheEconomist/the-economist-war-fire-model. Data CC BY 4.0, "
             "code MIT. Credit The Economist / Sondre Solstad.\n")


def zenodo(record_id, subdir, set_, serves):
    if DRY:
        print("would list zenodo record", record_id); return
    d = get_json(f"https://zenodo.org/api/records/{record_id}")
    for f in d["files"]:
        k = f["key"]; ext = k.rsplit(".", 1)[-1].lower()
        sig = {"zip": ZIP, "shp": SHP, "shx": SHP, "dbf": DBF}.get(ext, ANY)
        e = fetch(f["links"]["self"], RAW / subdir / k, sig, set_, serves)
        if e and f.get("checksum", "").startswith("md5:"):
            md5 = hashlib.md5((RAW / subdir / k).read_bytes()).hexdigest()
            if md5 != f["checksum"][4:]:
                failures.append((e["file"], "md5 mismatch vs Zenodo")); print("BAD md5", k)


def step_perimeters():
    serves = "H2 size/land-cover truth (FRP vs burned area); H10 occupied/buff30 flags; H5. Not recall."
    zenodo(8298835, "fire_perimeters_ukraine/2022", "C1", serves)
    zenodo(10514571, "fire_perimeters_ukraine/2023", "C1", serves)
    lic_note("zibtsev_fire_perimeters_ukraine_CC-BY-4.0_NOTICE.md",
             "# Ukraine Fire Perimeters 2022/2023\n\nZibtsev, Myroniuk, Soshenskyi, Kalchuk; Regional Eastern Europe "
             "Fire Monitoring Center. Zenodo 8298835, 10514571. CC BY 4.0.\n")


def step_owl(daily):
    repo = "owlmaps/UAControlMapBackups"
    if DRY:
        print("would list", repo, "year folders 2022..", TODAY.year, "daily" if daily else "weekly"); return
    picks = {}
    for y in range(2022, TODAY.year + 1):
        for f in get_json(f"https://api.github.com/repos/{repo}/contents/{y}?ref=master"):
            nm = f["name"]
            if not nm.endswith(".kmz"): continue
            try:
                d = dt.datetime.strptime(nm[:6], "%y%m%d").date()
            except ValueError:
                continue
            key = d.isoformat() if daily else "%d-W%02d" % d.isocalendar()[:2]
            if key not in picks or nm > picks[key][0]:
                picks[key] = (nm, f["download_url"], y)
    print(f"Owl: {len(picks)} files")
    for key in sorted(picks):
        nm, url, y = picks[key]
        fetch(url, RAW / "owl_uacontrolmap" / str(y) / nm, ZIP,
              "C1" if nm[:6] <= "240707" else "E", "robustness 5: fourth control source", pause=0.5)
    lic_note("owlmaps_UAControlMapBackups_NOTICE.md",
             "# Project Owl UAControlMap backups\n\ngithub.com/owlmaps/UAControlMapBackups. No licence file. "
             "Volunteer work: internal use only; ask Project Owl before redistributing anything derived.\n")


def step_matsala():
    zenodo(8132956, "matsala_war_fire_risk", "C1", "H2 covariate benchmark; exploratory")


def step_texty():
    base = "https://raw.githubusercontent.com/texty/project_Mykolaiv_shelling_web/main/"
    for p in ["data/shelling_points.geojson", "data/shelling_triangles.geojson", "data/shelling_triangles_2.geojson",
              "artilerry position.geojson", "front_line.geojson"]:
        fetch(base + urllib.parse.quote(p), RAW / "texty_mykolaiv" / p.replace(" ", "_"), JSONSIG, "V/C1",
              "H1 small V-set check, Mykolaiv 2022")
    lic_note("texty_mykolaiv_NOTICE.md", "# Texty.org.ua Mykolaiv shelling\n\nNo licence stated. Internal use only.\n")


def step_t1():
    for c in ("Azerbaijan", "Armenia"):
        fn = f"viirs-snpp_2020_{c}.csv"
        fetch(f"{FIRMS}/data/country/viirs-snpp/2020/{fn}", RAW / "firms_country_post_tag" / fn, CSVSIG, "T1",
              "H7 Karabakh", csv_rows)


def step_t2(avail):
    firms_yearly("Sudan", ["viirs-snpp"], [2023, 2024, 2025], "T2", "H7 Sudan")
    firms_api("sudan", dt.date(2026, 1, 1), ["SNPP"], "T2-ext", "H7 Sudan, 2026 (beyond T2, exploratory)", avail)


def step_ucdp():
    fetch("https://ucdp.uu.se/downloads/ged/ged261-csv.zip", RAW / "ucdp" / "ged261-csv.zip", ZIP, "T2",
          "H7 Sudan events (recall denominator)", zip_csv_rows)
    lic_note("ucdp_ged_CC-BY-4.0_NOTICE.md", "# UCDP GED 26.1\n\nCC BY 4.0. Cite Davies, Pettersson & Oberg 2026; "
             "Sundberg & Melander 2013.\n")


def register_acled(path):
    p = pathlib.Path(path).resolve()
    if RAW / "acled" not in p.parents:
        sys.exit("put the ACLED export under data/raw/acled/ first")
    b = p.read_bytes()
    record(str(p.relative_to(RAW)), "browser export: acleddata.com Data Export Tool (Jackson's session); "
           "Ukraine+Russia 2022-02-24..latest in tier", len(b), hashlib.sha256(b).hexdigest(), "V/C1",
           "H1/H2 V extension; H12/H13 timing checks. Raw data NOT redistributable (ACLED terms).",
           max(0, b.count(b"\n") - 1))
    lic_note("acled_TERMS_NOTICE.md", "# ACLED\n\nacleddata.com. Terms of Use forbid redistributing raw data; "
             "derived aggregates with attribution only.\n")
    print("registered", p.name)


def main():
    global DRY
    ap = argparse.ArgumentParser()
    ap.add_argument("--only"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--owl-daily", action="store_true"); ap.add_argument("--osf-ok", action="store_true")
    ap.add_argument("--register-acled")
    a = ap.parse_args()
    DRY = a.dry_run
    if not DRY:
        check_tag_gate(a.osf_ok)
    if a.register_acled:
        register_acled(a.register_acled); return
    steps = STEPS if not a.only else [s for s in STEPS if s in a.only.split(",")]
    if a.only and set(a.only.split(",")) - set(STEPS):
        sys.exit(f"unknown step(s): {set(a.only.split(',')) - set(STEPS)}")
    if any(s.startswith("firms") or s == "t2" for s in steps) and not MAP_KEY:
        sys.exit("FIRMS_MAP_KEY missing from .env")
    ok_t, why = transfer_gate_ok()
    if not ok_t and TRANSFER_STEPS & set(steps):
        print(f"GATE (H7): skipping t1/t2/ucdp: {why}")
        steps = [s for s in steps if s not in TRANSFER_STEPS]
    avail = {} if DRY else firms_availability()
    if not DRY:
        record(f"_gate/run_{now()}", "git tag prereg-v1", 0, git("rev-parse", "prereg-v1^{commit}").stdout.strip(),
               "gate", "start of post-tag pull", extra={"transfer_v1_commit": why if ok_t else None})
    run = {
        "viina": step_viina,
        "firms_ua": lambda: firms_api("ukraine", WAR_START, ["SNPP", "NOAA20", "NOAA21"], "C1+E",
                                      "H1 H2 H3 H4 H5 H6 H6b H8 H9-H12 H14", avail),
        "firms_ua_yearly": lambda: firms_yearly("Ukraine", ["viirs-snpp", "viirs-jpss1"], range(2022, 2026),
                                                "C1+E", "completeness check on firms_ua"),
        "economist": step_economist, "perimeters": step_perimeters, "owl": lambda: step_owl(a.owl_daily),
        "matsala": step_matsala, "texty": step_texty,
        "firms_ru": lambda: firms_api("west_russia", WAR_START, ["SNPP", "NOAA20", "NOAA21"], "C1+E",
                                      "H13 deep strikes; H10 Russian-held side; H5", avail),
        "firms_ru_yearly": lambda: firms_yearly("Russian_Federation", ["viirs-snpp", "viirs-jpss1"],
                                                range(2022, 2026), "C1+E", "Russia coverage; check on firms_ru"),
        "t1": step_t1, "t2": lambda: step_t2(avail), "ucdp": step_ucdp,
    }
    for s in steps:
        print(f"== {s}")
        run[s]()
    print(f"\nnew bytes this run: {total:,}; manifest part: {PART} ({len(man)} records)")
    if failures:
        print(f"{len(failures)} failures:")
        for f, why_ in failures:
            print("  ", f, "-", why_)
    print("ACLED is a browser export: see planning/POST_TAG_PULL.md step 10, then --register-acled.")


if __name__ == "__main__":
    main()
