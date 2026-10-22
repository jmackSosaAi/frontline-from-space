"""Shared helpers for scripts/analysis (paths, hashing, _meta.json, h3, seeds).

Pattern copied from scripts/telegram/_common.py. Spec: planning/DETECTION_MODEL.md, PREREG.md §3.
"""
from __future__ import annotations
import hashlib, json, os, sys, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim" / "analysis"
DERIVED = ROOT / "data" / "derived"
MODELS = INTERIM / "models"

SEED = 20261014
V_START, V_END = "2022-02-24", "2025-12-31"          # PREREG §2, set V
FIRES_START, FIRES_END = "2022-01-01", "2025-12-31"  # DETECTION_MODEL.md, fires.parquet
BASELINE_YEARS = range(2012, 2022)                   # set B, Ukraine


def sha256_file(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def _rel(p: Path) -> str:
    p = Path(p).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def write_meta(out_path: Path, *, inputs: dict[str, Path] | dict[str, list[Path]], counts: dict,
               extra: dict | None = None, hash_inputs: bool = True) -> Path:
    """Write <stem>_meta.json beside out_path. `inputs` values may be a Path or a list of Paths
    (lists are hashed per file; for very many files pass hash_inputs=False to record only names + sizes)."""
    def one(v: Path) -> dict:
        v = Path(v)
        d = {"path": _rel(v), "bytes": v.stat().st_size}
        if hash_inputs:
            d["sha256"] = sha256_file(v)
        return d
    inp = {}
    for k, v in inputs.items():
        if isinstance(v, (list, tuple)):
            inp[k] = {"n_files": len(v), "files": [one(x) for x in v]}
        else:
            inp[k] = one(v)
    meta = {
        "output": _rel(out_path),
        "written_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "script": os.path.basename(sys.argv[0]) if sys.argv and sys.argv[0] else "<stdin>",
        "seed": SEED,
        "inputs": inp,
        "counts": counts,
    }
    if extra:
        meta.update(extra)
    mp = out_path.with_name(out_path.stem + "_meta.json")
    mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str))
    return mp


def log(msg: str) -> None:
    print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def h3_cells(lat, lon, res: int = 6):
    """h3 v4 API, elementwise. Returns list of hex strings for the given res."""
    import h3
    return [h3.latlng_to_cell(float(a), float(b), res) for a, b in zip(lat, lon)]


def h3_parent(cells, res: int = 5):
    import h3
    return [h3.cell_to_parent(c, res) for c in cells]


def season(month) -> str:
    """PREREG §3: summer May–Oct, winter Nov–Apr. Works on ints or pandas Series."""
    try:
        import pandas as pd
        if isinstance(month, pd.Series):
            return month.between(5, 10).map({True: "summer", False: "winter"})
    except ImportError:
        pass
    return "summer" if 5 <= int(month) <= 10 else "winter"


def ukraine_adm0():
    """GeoBoundaries ADM0 polygon (EPSG:4326), prepared for fast contains()."""
    import geopandas as gpd, shapely
    g = gpd.read_file(RAW / "boundaries/geoboundaries/geoBoundaries-UKR-ADM0.geojson")
    poly = shapely.make_valid(g.geometry.union_all())
    shapely.prepare(poly)
    return poly


WORLDCOVER_CLASSES = {
    10: "tree_cover", 20: "shrubland", 30: "grassland", 40: "cropland", 50: "built_up",
    60: "bare_sparse", 70: "snow_ice", 80: "water", 90: "herbaceous_wetland", 95: "mangroves",
    100: "moss_lichen", 0: "nodata",
}


def worldcover_at(lat, lon) -> list[int]:
    """ESA WorldCover 2021 class code at each point; tiles are 3°×3°, named by lower-left corner.
    Points with no tile on disk get 0 (nodata)."""
    import numpy as np, rasterio
    lat = np.asarray(lat, float); lon = np.asarray(lon, float)
    out = np.zeros(len(lat), dtype=np.int16)
    t_lat = (np.floor(lat / 3) * 3).astype(int); t_lon = (np.floor(lon / 3) * 3).astype(int)
    for (la, lo) in set(zip(t_lat.tolist(), t_lon.tolist())):
        ns = f"{'N' if la >= 0 else 'S'}{abs(la):02d}"; ew = f"{'E' if lo >= 0 else 'W'}{abs(lo):03d}"
        p = RAW / "worldcover" / f"ESA_WorldCover_10m_2021_v200_{ns}{ew}_Map.tif"
        m = (t_lat == la) & (t_lon == lo)
        if not p.exists():
            log(f"worldcover: no tile {ns}{ew} for {int(m.sum())} points -> nodata")
            continue
        with rasterio.open(p) as r:
            vals = np.array([v[0] for v in r.sample(zip(lon[m], lat[m]))], dtype=np.int16)
        out[m] = vals
    return out.tolist()
