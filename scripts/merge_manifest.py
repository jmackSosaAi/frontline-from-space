"""Merge data/manifest_parts/*.json into data/MANIFEST.json and audit data/raw for gated data.

Re-runnable: records already in MANIFEST (by `file`) are skipped; a part record is appended only if the file
exists under data/raw with matching bytes and sha256. Part files are never modified.
`file` keys are kept as written by each fetcher; they are resolved against data/raw/<file>, then
data/raw/<subdir>/<file> for a unique match by relative suffix.

Gate audit (report only, never deletes):
  - every CSV under data/raw whose header has acq_date (FIRMS-style): min/max acq_date, flagged if
    Ukraine/Russia >= 2022-02-24, Azerbaijan/Armenia in 2020, Sudan >= 2023-04-15;
  - control-map files (viina, deepstate, isw, economist, frontline, control) not present in the 2026-10-14
    commit of MANIFEST.json;
  - files on disk not listed in MANIFEST.json (after merge).

Run:  python3 -I scripts/merge_manifest.py [--dry-run]
Writes data/derived/merge_report.json.
"""
import csv, datetime as dt, glob, hashlib, io, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"; MAN = ROOT / "data/MANIFEST.json"; PARTS = ROOT / "data/manifest_parts"
REPORT = ROOT / "data/derived/merge_report.json"
DRY = "--dry-run" in sys.argv


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


all_files = [p for p in RAW.rglob("*") if p.is_file() and p.name != ".DS_Store"]
rel = {p.relative_to(RAW).as_posix(): p for p in all_files}


def resolve(name):
    if name in rel:
        return [rel[name]]
    return [p for r, p in rel.items() if r.endswith("/" + name)]


man = json.loads(MAN.read_text())
have = {e["file"] for e in man}
added, mismatches, dupes = [], [], []
for part in sorted(PARTS.glob("*.json")):
    for e in json.loads(part.read_text()):
        if e["file"] in have:
            dupes.append((part.name, e["file"])); continue
        c = resolve(e["file"])
        if len(c) != 1:
            mismatches.append({"part": part.name, "file": e["file"], "problem": f"{len(c)} files on disk match"}); continue
        p = c[0]; sz = p.stat().st_size
        if sz != e.get("bytes"):
            mismatches.append({"part": part.name, "file": e["file"], "problem": f"bytes disk {sz} != {e.get('bytes')}"}); continue
        if sha(p) != e.get("sha256"):
            mismatches.append({"part": part.name, "file": e["file"], "problem": "sha256 differs"}); continue
        added.append(e); have.add(e["file"])
if not DRY and added:
    MAN.write_text(json.dumps(man + added, indent=1))
man_all = man + added

# which on-disk files does the manifest cover?
covered = set()
for e in man_all:
    for p in resolve(e["file"]):
        covered.add(p)
# economist entries describe a whole repo snapshot; treat economist/ as covered by its records
unlisted = sorted(p.relative_to(RAW).as_posix() for p in all_files if p not in covered
                  and not p.relative_to(RAW).as_posix().startswith("economist/"))

# gate audit 1: FIRMS-style CSVs
LIMITS = {"Ukraine": ("2022-02-24", None), "Russia": ("2022-02-24", None), "Russian_Federation": ("2022-02-24", None),
          "Azerbaijan": ("2020-01-01", "2020-12-31"), "Armenia": ("2020-01-01", "2020-12-31"),
          "Sudan": ("2023-04-15", None)}
firms, gate_hits = [], []
for p in all_files:
    if p.suffix.lower() != ".csv":
        continue
    with open(p, "r", errors="replace") as f:
        head = f.readline()
        if "acq_date" not in head:
            continue
        cols = next(csv.reader([head])); i = cols.index("acq_date")
        lo = hi = None; n = 0
        for row in csv.reader(f):
            if len(row) <= i: continue
            d = row[i][:10]; n += 1
            lo = d if lo is None or d < lo else lo; hi = d if hi is None or d > hi else hi
    r = p.relative_to(RAW).as_posix(); firms.append({"file": r, "rows": n, "min": lo, "max": hi})
    country = next((c for c in LIMITS if c in p.name), None)
    if r.startswith("economist/"):
        country = country or "Ukraine"  # economist repo files are Ukraine-war files present since 10-14
    if country and hi:
        start, end = LIMITS[country]
        if hi >= start and (end is None or lo <= end):
            gate_hits.append({"file": r, "country": country, "min": lo, "max": hi,
                              "pre_2026_10_14": r.startswith("economist/")})

# gate audit 2: control maps not in the 10-14 manifest
orig = json.loads(subprocess.run(["git", "-C", str(ROOT), "show", "ee17dcd:data/MANIFEST.json"],
                                 capture_output=True, text=True, check=True).stdout)
orig_files = {e["file"] for e in orig}
ctl_re = re.compile(r"viina|deepstate|isw|control|frontline|front_line|occupied|territor", re.I)
new_control = [r for r in rel if ctl_re.search(r) and not r.startswith("economist/") and r not in orig_files]

# disk by set
setof = {}
for e in man_all:
    for p in resolve(e["file"]):
        setof[p] = e["set"]
by_set = {}
for p in all_files:
    r = p.relative_to(RAW).as_posix()
    s = setof.get(p) or ("economist" if r.startswith("economist/") else "UNLISTED")
    b = by_set.setdefault(s, [0, 0]); b[0] += 1; b[1] += p.stat().st_size

rep = {"run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "dry_run": DRY,
       "manifest_before": len(man), "added": len(added), "manifest_after": len(man_all),
       "already_present": len(dupes), "mismatches": mismatches, "unlisted_on_disk": unlisted,
       "firms_csvs": sorted(firms, key=lambda x: x["file"]), "gate_hits": gate_hits,
       "new_control_files": sorted(new_control), "by_set": by_set}
if not DRY:
    REPORT.parent.mkdir(parents=True, exist_ok=True); REPORT.write_text(json.dumps(rep, indent=1))
print(json.dumps({k: v for k, v in rep.items() if k != "firms_csvs"}, indent=1))
