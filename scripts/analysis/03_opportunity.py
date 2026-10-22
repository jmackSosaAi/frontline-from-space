"""03_opportunity.py — Builder B, tier 1+2 observability (DETECTION_MODEL.md, PREREG §3, DESIGN D9).

Outputs
  data/interim/analysis/overpasses_r6.parquet/            one row per (h3_r6 cell, granule), hive-partitioned by year
  data/interim/analysis/opportunity_r6_day.parquet        full cell × day grid (zeros filled) with opportunity per PREREG §3
  data/derived/observability/opportunity_r5_week.csv      res-5 × ISO-week sums (published panel covariate)
Each output gets a <name>_meta.json beside it.

Run from repo root:  .venv/bin/python -I scripts/analysis/03_opportunity.py
"""
from __future__ import annotations
import datetime as dt, hashlib, json, os, sys, time, zipfile, io
from pathlib import Path

import numpy as np, pandas as pd, geopandas as gpd, shapely, xarray as xr, h3
from shapely import STRtree
from shapely.ops import transform as shp_transform
import pyarrow as pa, pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim" / "analysis"
DERIVED = ROOT / "data" / "derived" / "observability"
SEED = 20261014
BUFFER_KM = 50
TCC_CLEAR = 0.5       # PREREG §3: tcc at overpass hour < 0.5
SDE_CLEAR_CM = 1.0    # PREREG §3: snow depth < 1 cm
SATS = {"S-NPP": "N", "NOAA-20": "N20", "NOAA-21": "N21"}
PRODUCTS = ["VNP14IMG", "VJ114IMG", "VJ214IMG"]
YEARS = [2022, 2023, 2024, 2025]

# ---- meta helper (inline; _common.py is Builder A's and may not exist yet) -------------------------------------
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _common import write_meta, sha256_file, log  # type: ignore
except Exception:  # pragma: no cover
    def sha256_file(p: Path, chunk: int = 1 << 20) -> str:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for b in iter(lambda: f.read(chunk), b""):
                h.update(b)
        return h.hexdigest()

    def write_meta(out_path: Path, *, inputs: dict, counts: dict, extra: dict | None = None) -> Path:
        meta = {"output": str(out_path.relative_to(ROOT)),
                "written_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "script": os.path.basename(sys.argv[0]),
                "inputs": {k: {"path": str(Path(v).resolve().relative_to(ROOT)), "sha256": sha256_file(Path(v))}
                           for k, v in inputs.items()},
                "counts": counts}
        if extra:
            meta.update(extra)
        mp = out_path.with_name(out_path.stem + "_meta.json") if out_path.suffix else out_path.with_name(out_path.name + "_meta.json")
        mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str))
        return mp

    def log(msg: str) -> None:
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


# ---- 1. cell grid ---------------------------------------------------------------------------------------------
def build_cells() -> gpd.GeoDataFrame:
    ukr = gpd.read_file(RAW / "boundaries/geoboundaries/geoBoundaries-UKR-ADM0.geojson").to_crs(4326)
    ukr_geom = ukr.geometry.union_all()
    ne = gpd.read_file(f"zip://{RAW / 'boundaries/naturalearth/ne_10m_admin_0_countries.zip'}")
    rus_geom = ne[ne["ADM0_A3"] == "RUS"].geometry.union_all()
    ukr_buf = gpd.GeoSeries([ukr_geom], crs=4326).to_crs(3035).buffer(BUFFER_KM * 1000).to_crs(4326).iloc[0]
    # h3 fill (centroid containment) of the buffered polygon, then classify centroids
    cells = sorted(h3.geo_to_cells(ukr_buf, 6))
    latlng = np.array([h3.cell_to_latlng(c) for c in cells])
    pts = shapely.points(latlng[:, 1], latlng[:, 0])
    in_ukr = shapely.contains(ukr_geom, pts)
    in_rus = shapely.contains(rus_geom, pts)
    keep = in_ukr | in_rus
    g = gpd.GeoDataFrame({"h3_r6": np.array(cells)[keep], "lat": latlng[keep, 0], "lon": latlng[keep, 1],
                          "in_ukraine": in_ukr[keep]}, geometry=pts[keep], crs=4326)
    g["h3_r5"] = [h3.cell_to_parent(c, 5) for c in g.h3_r6]
    log(f"cells: {len(cells)} in buffered polygon, kept {keep.sum()} (Ukraine {in_ukr.sum()}, Russia within {BUFFER_KM} km {(in_rus & ~in_ukr).sum()}, dropped non-UA/RU {(~keep).sum()})")
    return g.reset_index(drop=True)


# ---- 2. footprints --------------------------------------------------------------------------------------------
def fix_antimeridian(geoms: np.ndarray) -> tuple[np.ndarray, dict]:
    """Polygons whose lon span exceeds 180° straddle the dateline when drawn in naive lon/lat. Shift negative
    longitudes by +360 so the polygon is contiguous in 0..360 space; test points (all at 22–41E) are unaffected
    because the fixed polygon then lies far from Ukraine. Invalid geometries get buffer(0); empties are dropped."""
    b = shapely.bounds(geoms)
    span = b[:, 2] - b[:, 0]
    crossing = np.where(span > 180)[0]
    fixed = geoms.copy()
    for i in crossing:
        fixed[i] = shp_transform(lambda x, y, z=None: (np.where(np.asarray(x) < 0, np.asarray(x) + 360, x), y), geoms[i])
    invalid = ~shapely.is_valid(fixed)
    fixed[invalid] = shapely.make_valid(fixed[invalid]) if invalid.any() else fixed[invalid]
    empty = shapely.is_empty(fixed)
    return fixed, {"antimeridian_crossing_fixed": int(len(crossing)), "invalid_repaired": int(invalid.sum()),
                   "empty_dropped": int(empty.sum())}


def load_footprints() -> tuple[pd.DataFrame, dict]:
    fp = pd.read_parquet(RAW / "cmr_footprints/viirs_granule_footprints_2022_2025.parquet")
    n0 = len(fp)
    fp = fp[(fp.is_latest == 1) & fp["product"].isin(PRODUCTS)].copy()
    fp = fp.drop_duplicates("granule_ur").sort_values("start_utc").reset_index(drop=True)
    geoms = shapely.from_wkt(fp.footprint_wkt.values)
    geoms, fixlog = fix_antimeridian(geoms)
    ok = ~shapely.is_empty(geoms)
    fp = fp[ok].reset_index(drop=True)
    fp["geom"] = geoms[ok]
    fp["sat"] = fp.satellite.map(SATS)
    assert fp.sat.notna().all(), fp.satellite.unique()
    fp["start_utc"] = pd.to_datetime(fp.start_utc, utc=True)
    fixlog.update({"footprint_rows_total": n0, "footprints_used": len(fp),
                   "by_satellite": fp.satellite.value_counts().to_dict(), "by_day_night": fp.day_night.value_counts().to_dict()})
    log(f"footprints: {fixlog}")
    return fp, fixlog


# ---- 3. ERA5 ----------------------------------------------------------------------------------------------------
def load_era5():
    tcc = xr.concat([xr.open_dataset(RAW / f"era5/era5_tcc_{y}.nc")["tcc"].load() for y in YEARS], dim="valid_time")
    sde = xr.concat([xr.open_dataset(RAW / f"era5/era5land_snowdepth_{y}.nc")["sde"].load() for y in YEARS], dim="valid_time")
    tcc = tcc.sortby("valid_time"); sde = sde.sortby("valid_time")
    log(f"ERA5 tcc {tcc.shape} ({tcc.valid_time.values[0]} → {tcc.valid_time.values[-1]}); sde {sde.shape}")
    return tcc, sde


def nearest_index(coord: np.ndarray, vals: np.ndarray, tol: float) -> np.ndarray:
    """Index of nearest grid coordinate (coord may be descending). -1 if farther than tol."""
    order = np.argsort(coord)
    cs = coord[order]
    j = np.clip(np.searchsorted(cs, vals), 1, len(cs) - 1)
    left, right = cs[j - 1], cs[j]
    jj = np.where(np.abs(vals - left) <= np.abs(vals - right), j - 1, j)
    idx = order[jj]
    idx[np.abs(coord[idx] - vals) > tol] = -1
    return idx


def solar_elevation_deg(ts_utc: np.ndarray, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Approximate solar elevation (NOAA low-precision formula), vectorised. Used only to split 'Both' granules."""
    t = pd.DatetimeIndex(ts_utc)
    doy = t.dayofyear.values + (t.hour.values + t.minute.values / 60) / 24
    gamma = 2 * np.pi / 365 * (doy - 1)
    decl = (0.006918 - 0.399912 * np.cos(gamma) + 0.070257 * np.sin(gamma) - 0.006758 * np.cos(2 * gamma)
            + 0.000907 * np.sin(2 * gamma) - 0.002697 * np.cos(3 * gamma) + 0.00148 * np.sin(3 * gamma))
    eqt = 229.18 * (0.000075 + 0.001868 * np.cos(gamma) - 0.032077 * np.sin(gamma) - 0.014615 * np.cos(2 * gamma) - 0.040849 * np.sin(2 * gamma))
    tst = (t.hour.values * 60 + t.minute.values + eqt + 4 * lon) % 1440
    ha = np.deg2rad(tst / 4 - 180)
    latr = np.deg2rad(lat)
    cosz = np.sin(latr) * np.sin(decl) + np.cos(latr) * np.cos(decl) * np.cos(ha)
    return 90 - np.rad2deg(np.arccos(np.clip(cosz, -1, 1)))


# ---- main --------------------------------------------------------------------------------------------------------
def main():
    t0 = time.time()
    INTERIM.mkdir(parents=True, exist_ok=True); DERIVED.mkdir(parents=True, exist_ok=True)
    cells = build_cells()
    fp, fixlog = load_footprints()
    tcc, sde = load_era5()

    # ERA5 grid indices per cell (nearest grid point; -1 → outside ERA5 extent → tcc/sde NaN)
    c_iy = nearest_index(tcc.latitude.values, cells.lat.values, 0.126)
    c_ix = nearest_index(tcc.longitude.values, cells.lon.values, 0.126)
    s_iy = nearest_index(sde.latitude.values, cells.lat.values, 0.051)
    s_ix = nearest_index(sde.longitude.values, cells.lon.values, 0.051)
    tcc_ok = (c_iy >= 0) & (c_ix >= 0); sde_ok = (s_iy >= 0) & (s_ix >= 0)
    log(f"cells outside ERA5 tcc grid: {(~tcc_ok).sum()}, outside ERA5-Land grid: {(~sde_ok).sum()}")
    tcc_t = tcc.valid_time.values.astype("datetime64[ns]"); sde_t = sde.valid_time.values.astype("datetime64[D]")
    tcc_arr = tcc.values; sde_arr = sde.values  # (T, lat, lon)

    # granule → ERA5 time index (nearest available hour to granule start) and sde day index
    g_start = fp.start_utc.dt.tz_convert(None).values.astype("datetime64[ns]")
    j = np.clip(np.searchsorted(tcc_t, g_start), 1, len(tcc_t) - 1)
    g_it = np.where(np.abs(g_start - tcc_t[j - 1]) <= np.abs(g_start - tcc_t[j]), j - 1, j)
    g_tcc_gap_h = np.abs((g_start - tcc_t[g_it]).astype("timedelta64[m]").astype(float)) / 60
    g_day = g_start.astype("datetime64[D]")
    g_is = np.searchsorted(sde_t, g_day)
    g_is_ok = (g_is < len(sde_t)) & (sde_t[np.clip(g_is, 0, len(sde_t) - 1)] == g_day)
    log(f"ERA5 hour match: median gap {np.median(g_tcc_gap_h):.2f} h, >1 h for {(g_tcc_gap_h > 1).sum()} granules; "
        f"granules without an ERA5-Land day: {(~g_is_ok).sum()}")

    pts = cells.geometry.values
    out_dir = INTERIM / "overpasses_r6.parquet"
    if out_dir.exists():
        for p in out_dir.rglob("*.parquet"): p.unlink()
    last_seen = np.full(len(cells), np.datetime64("NaT"), dtype="datetime64[ns]")
    day_frames = []
    n_rows = 0; n_pairs_by_month = {}
    fp["ym"] = fp.start_utc.dt.strftime("%Y-%m")
    for ym, grp in fp.groupby("ym", sort=True):
        idx = grp.index.values
        tree = STRtree(grp.geom.values)
        q_cell, q_fp = tree.query(pts, predicate="within")  # q_fp indexes into grp
        fp_i = idx[q_fp]
        d = pd.DataFrame({"cell_i": q_cell.astype(np.int32), "fp_i": fp_i.astype(np.int32)})
        d["start_utc"] = g_start[fp_i]
        d.sort_values(["cell_i", "start_utc"], inplace=True, kind="stable")
        # tcc / sde gather
        ci = d.cell_i.values
        it = g_it[d.fp_i.values]
        tccv = np.full(len(d), np.nan, dtype=np.float32)
        m = tcc_ok[ci]
        tccv[m] = tcc_arr[it[m], c_iy[ci[m]], c_ix[ci[m]]]
        sdev = np.full(len(d), np.nan, dtype=np.float32)
        isd = g_is[d.fp_i.values]
        m2 = sde_ok[ci] & g_is_ok[d.fp_i.values]
        sdev[m2] = sde_arr[isd[m2], s_iy[ci[m2]], s_ix[ci[m2]]] * 100.0
        d["tcc"] = tccv; d["sde_cm"] = sdev
        d["sat"] = fp.sat.values[d.fp_i.values]
        d["day_night"] = fp.day_night.values[d.fp_i.values]
        # hours since previous overpass of the same cell (any satellite), carried across months
        prev = np.empty(len(d), dtype="datetime64[ns]")
        first = np.r_[True, ci[1:] != ci[:-1]]
        prev[~first] = d.start_utc.values[:-1][~first[1:]]
        prev[first] = last_seen[ci[first]]
        d["hours_since_prev"] = ((d.start_utc.values - prev).astype("timedelta64[s]").astype(float) / 3600).astype(np.float32)
        # update last_seen with the last overpass per cell in this month
        last_idx = np.r_[ci[1:] != ci[:-1], True]
        last_seen[ci[last_idx]] = d.start_utc.values[last_idx]
        # resolve day/night per (cell, granule): granule flag, 'Both' split by solar elevation at the centroid
        both = d.day_night.values == "Both"
        is_day = d.day_night.values == "Day"
        if both.any():
            el = solar_elevation_deg(d.start_utc.values[both], cells.lat.values[ci[both]], cells.lon.values[ci[both]])
            is_day[both] = el > 0
        d["is_day"] = is_day
        # write granule-level rows
        year = int(ym[:4])
        w = pd.DataFrame({"h3_r6": cells.h3_r6.values[ci], "granule_ur": fp.granule_ur.values[d.fp_i.values],
                          "satellite": d.sat.values, "start_utc": pd.DatetimeIndex(d.start_utc.values, tz="UTC"),
                          "day_night": d.day_night.values, "tcc": d.tcc.values, "sde_cm": d.sde_cm.values,
                          "hours_since_prev": d.hours_since_prev.values, "covered": np.ones(len(d), dtype=np.int8)})
        part = out_dir / f"year={year}" / f"{ym}.parquet"; part.parent.mkdir(parents=True, exist_ok=True)
        w.to_parquet(part, index=False, compression="zstd")
        n_rows += len(d); n_pairs_by_month[ym] = len(d)
        # cell-day aggregate
        d["date"] = d.start_utc.values.astype("datetime64[D]")
        clear = ((d.tcc < TCC_CLEAR) & (d.sde_cm < SDE_CLEAR_CM)).astype(np.int16)
        d["clear"] = clear
        for s in ["N", "N20", "N21"]:
            d[f"opp_{s}"] = (clear * (d.sat == s)).astype(np.int16)
            d[f"n_{s}"] = (d.sat == s).astype(np.int16)
        d["n_night"] = (~d.is_day).astype(np.int16); d["n_day"] = d.is_day.astype(np.int16)
        d["tcc_known"] = d.tcc.notna().astype(np.int16)
        agg = d.groupby(["cell_i", "date"], sort=False).agg(
            n_overpasses=("fp_i", "size"), n_clear_overpasses=("clear", "sum"), n_night=("n_night", "sum"),
            n_day=("n_day", "sum"), min_tcc=("tcc", "min"), hours_since_prev_overpass_mean=("hours_since_prev", "mean"),
            sde_cm=("sde_cm", "max"), n_tcc_known=("tcc_known", "sum"),
            opp_N=("opp_N", "sum"), opp_N20=("opp_N20", "sum"), opp_N21=("opp_N21", "sum"),
            n_N=("n_N", "sum"), n_N20=("n_N20", "sum"), n_N21=("n_N21", "sum")).reset_index()
        day_frames.append(agg)
        log(f"{ym}: {len(grp)} granules, {len(d):,} cell-granule rows, {len(agg):,} cell-days  [{time.time()-t0:.0f}s]")

    ov_meta = write_meta(out_dir, inputs={"footprints": RAW / "cmr_footprints/viirs_granule_footprints_2022_2025.parquet",
                                          "ukr_adm0": RAW / "boundaries/geoboundaries/geoBoundaries-UKR-ADM0.geojson",
                                          **{f"era5_tcc_{y}": RAW / f"era5/era5_tcc_{y}.nc" for y in YEARS},
                                          **{f"era5land_sde_{y}": RAW / f"era5/era5land_snowdepth_{y}.nc" for y in YEARS}},
                         counts={"rows": n_rows, "cells": len(cells), "granules": len(fp), "rows_by_month": n_pairs_by_month},
                         extra={"footprints": fixlog, "layout": "hive-partitioned by year; columns h3_r6, granule_ur, satellite {N,N20,N21}, start_utc, day_night (granule flag), tcc, sde_cm, hours_since_prev, covered=1",
                                "notes": ["cells = h3 res-6 cells whose centroid is inside Ukraine ADM0 or inside Russia within a 50 km buffer of Ukraine",
                                          "tcc = ERA5 at the nearest 0.25° grid point to the cell centroid, nearest available hour to granule start",
                                          "sde_cm = ERA5-Land daily snow depth (m×100) at nearest 0.1° grid point, same UTC date",
                                          "hours_since_prev = hours since the previous overpass of the same cell by any satellite (NaN for first overpass of the series)",
                                          f"cells outside ERA5 grids: tcc {int((~tcc_ok).sum())}, sde {int((~sde_ok).sum())} (NaN → not counted as clear)"]})

    # ---- cell-day full grid --------------------------------------------------------------------------------------
    log("building full cell × day grid")
    days = np.arange(np.datetime64("2022-01-01"), np.datetime64("2026-01-01"), dtype="datetime64[D]")
    agg = pd.concat(day_frames, ignore_index=True)
    agg["date"] = agg.date.values.astype("datetime64[D]")
    full = pd.DataFrame({"cell_i": np.repeat(np.arange(len(cells), dtype=np.int32), len(days)),
                         "date": np.tile(days, len(cells))})
    full = full.merge(agg, on=["cell_i", "date"], how="left")
    cnt_cols = ["n_overpasses", "n_clear_overpasses", "n_night", "n_day", "n_tcc_known", "opp_N", "opp_N20", "opp_N21", "n_N", "n_N20", "n_N21"]
    for c in cnt_cols:
        full[c] = full[c].fillna(0).astype(np.int16)
    full["opportunity"] = full.n_clear_overpasses
    # snow_day from ERA5-Land directly (so days with no overpass still get the flag)
    ci = full.cell_i.values
    di = np.searchsorted(sde_t, full.date.values.astype("datetime64[D]"))
    ok = (di < len(sde_t)) & sde_ok[ci]
    ok &= sde_t[np.clip(di, 0, len(sde_t) - 1)] == full.date.values.astype("datetime64[D]")
    sd = np.full(len(full), np.nan, dtype=np.float32)
    sd[ok] = sde_arr[di[ok], s_iy[ci[ok]], s_ix[ci[ok]]] * 100
    full["sde_cm"] = sd
    full["snow_day"] = (sd >= SDE_CLEAR_CM).astype(np.int8)
    full["snow_day"] = full.snow_day.where(~np.isnan(sd), other=np.int8(-1))  # -1 unknown
    full["h3_r6"] = cells.h3_r6.values[ci]; full["h3_r5"] = cells.h3_r5.values[ci]
    full["in_ukraine"] = cells.in_ukraine.values[ci]
    full["date"] = pd.to_datetime(full.date)
    full = full[["h3_r6", "h3_r5", "in_ukraine", "date", "n_overpasses", "n_clear_overpasses", "opportunity", "n_night", "n_day",
                 "min_tcc", "hours_since_prev_overpass_mean", "sde_cm", "snow_day", "n_tcc_known",
                 "n_N", "n_N20", "n_N21", "opp_N", "opp_N20", "opp_N21"]]
    out_day = INTERIM / "opportunity_r6_day.parquet"
    full.to_parquet(out_day, index=False, compression="zstd")
    # report stats
    full["year"] = full.date.dt.year
    full["season"] = np.where(full.date.dt.month.isin([5, 6, 7, 8, 9, 10]), "summer", "winter")
    mean_ov = full.groupby("year")[["n_overpasses", "n_N", "n_N20", "n_N21", "opportunity"]].mean().round(3)
    zero_share = full.groupby(["season"]).apply(lambda g: pd.Series({"share_opp0": (g.opportunity == 0).mean(),
                                                                       "share_no_overpass": (g.n_overpasses == 0).mean()})).round(4)
    zero_share_ys = full.groupby(["year", "season"]).apply(lambda g: (g.opportunity == 0).mean()).round(4).unstack()
    log(f"mean overpasses/day by year:\n{mean_ov}\nshare opportunity==0 by season:\n{zero_share}\nby year×season:\n{zero_share_ys}")
    write_meta(out_day, inputs={"overpasses_meta": ov_meta},
               counts={"rows": len(full), "cells": len(cells), "days": len(days), "cells_in_ukraine": int(cells.in_ukraine.sum()),
                       "cell_days_with_overpass": int((full.n_overpasses > 0).sum()), "cell_days_opportunity_0": int((full.opportunity == 0).sum())},
               extra={"definitions": {"opportunity": f"n_clear_overpasses = Σ overpasses with tcc<{TCC_CLEAR} and sde<{SDE_CLEAR_CM} cm (PREREG §3); overpasses with unknown tcc/sde count as not clear",
                                      "snow_day": f"ERA5-Land sde ≥ {SDE_CLEAR_CM} cm that day; -1 = outside ERA5-Land grid",
                                      "n_day/n_night": "granule Day/Night flag; 'Both' granules split by solar elevation at the cell centroid at granule start",
                                      "hours_since_prev_overpass_mean": "mean over the day's overpasses of hours since the cell's previous overpass (any satellite)",
                                      "season": "summer May–Oct, winter Nov–Apr"},
                      "report": {"mean_per_day_by_year": json.loads(mean_ov.to_json()),
                                 "share_opportunity_0_by_season": json.loads(zero_share.to_json()),
                                 "share_opportunity_0_by_year_season": json.loads(zero_share_ys.to_json())}})

    # ---- res-5 × ISO week (published) -----------------------------------------------------------------------------
    iso = full.date.dt.isocalendar()
    full["iso_year"] = iso.year.astype(int); full["iso_week"] = iso.week.astype(int)
    wk = full.groupby(["h3_r5", "iso_year", "iso_week"]).agg(
        n_cells=("h3_r6", "nunique"), n_cell_days=("date", "size"), n_overpasses=("n_overpasses", "sum"),
        n_clear_overpasses=("n_clear_overpasses", "sum"), opportunity=("opportunity", "sum"),
        n_night=("n_night", "sum"), n_day=("n_day", "sum"), opp_N=("opp_N", "sum"), opp_N20=("opp_N20", "sum"),
        opp_N21=("opp_N21", "sum"), n_N=("n_N", "sum"), n_N20=("n_N20", "sum"), n_N21=("n_N21", "sum"),
        snow_cell_days=("snow_day", lambda s: int((s == 1).sum())), cell_days_opportunity_0=("opportunity", lambda s: int((s == 0).sum())),
        mean_min_tcc=("min_tcc", "mean"), share_in_ukraine=("in_ukraine", "mean")).reset_index()
    wk["week_start"] = [dt.date.fromisocalendar(int(y), int(w), 1).isoformat() for y, w in zip(wk.iso_year, wk.iso_week)]
    wk["mean_min_tcc"] = wk.mean_min_tcc.round(4); wk["share_in_ukraine"] = wk.share_in_ukraine.round(3)
    out_wk = DERIVED / "opportunity_r5_week.csv.gz"
    wk.to_csv(out_wk, index=False)
    write_meta(out_wk, inputs={"opportunity_r6_day_meta": out_day.with_name(out_day.stem + "_meta.json")},
               counts={"rows": len(wk), "cells_r5": int(wk.h3_r5.nunique()), "weeks": int(wk[["iso_year", "iso_week"]].drop_duplicates().shape[0])},
               extra={"definition": "sum over res-6 children (centroid in Ukraine or ≤50 km into Russia) and the 7 UTC days of the ISO week; opportunity per PREREG §3",
                      "publication_unit": "res-5 × ISO week (DESIGN D16 compliant)"})
    log(f"done in {time.time()-t0:.0f}s; wrote {out_dir}, {out_day}, {out_wk}")


if __name__ == "__main__":
    main()
