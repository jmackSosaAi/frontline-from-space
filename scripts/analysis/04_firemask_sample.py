"""04_firemask_sample.py — Builder B, tier 3 observability (DESIGN D9: the sensor's own cloud decision).

For each sampled VNP14IMG/VJ114IMG granule (data/raw/firemask, 2 days per ISO week per satellite over the front
corridor 32.5–40E / 46.3–50.5N) compute the share of corridor pixels in each fire-mask class and the mean ERA5 tcc over
the same pixels at the nearest hour, then a tcc-vs-sensor-cloud calibration table by month × day/night.

GEOLOCATION (flagged approximation): the VNP14IMG/VJ114IMG granules carry NO per-pixel lat/lon (only the 4 GRing corner
points and lat/lon of fire pixels); the companion VNP03IMG geolocation product is not on disk. Pixel positions are
therefore approximated: the 4 GRing corners are mapped to the image corners (order learned from the fire-pixel
line/sample ↔ lat/lon pairs), the along-track position is linear in line, the cross-track position follows the VIIRS
I-band scan geometry (aggregation zones 1:1/2:1/3:1, ±56.28° scan, 830 km orbit) and the interpolation is done along
great circles on the unit sphere. Where a granule has ≥5 fire pixels, the median residual of the model at those
pixels is removed as a constant offset. Validation against fire-pixel lat/lon: median error ≈12 km before and a few km
after the offset correction (reported in meta). Pixels are evaluated in 16×16 blocks (≈6 km nadir) — adequate for a
600 × 470 km corridor but NOT for anything finer. Column `geoloc_method` records this.

Outputs
  data/interim/analysis/firemask_granule_cloud.parquet     one row per sampled granule
  data/derived/observability/firemask_vs_era5.csv          calibration by month × day/night (+ tcc-bin curve rows)

Run from repo root:  .venv/bin/python -I scripts/analysis/04_firemask_sample.py
"""
from __future__ import annotations
import datetime as dt, hashlib, json, os, sys, time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

import numpy as np, pandas as pd, xarray as xr, netCDF4

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim" / "analysis"
DERIVED = ROOT / "data" / "derived" / "observability"
YEARS = [2022, 2023, 2024, 2025]
CORRIDOR = dict(lon_min=32.5, lon_max=40.0, lat_min=46.3, lat_max=50.5)
NS_DEFAULT, BLK = 6400, 16
TCC_CLEAR = 0.5
CLASSES = {0: "not_processed_missing", 1: "not_processed_bowtie", 2: "not_processed_other", 3: "water", 4: "cloud",
           5: "clear_land", 6: "unknown", 7: "fire_low", 8: "fire_nominal", 9: "fire_high"}
GRING_PERM = (2, 3, 0, 1)   # GRing point index for image corners (line0,samp0), (line0,sampMax), (lineMax,sampMax), (lineMax,samp0)
TCC_BINS = np.linspace(0, 1, 11)

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

    def write_meta(out_path: Path, *, inputs: dict, counts: dict, extra: dict | None = None, hash_inputs: bool = True) -> Path:
        meta = {"output": str(out_path.relative_to(ROOT)), "written_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "script": os.path.basename(sys.argv[0]),
                "inputs": {k: {"path": str(Path(v).resolve().relative_to(ROOT)), "sha256": sha256_file(Path(v))} for k, v in inputs.items()},
                "counts": counts}
        if extra:
            meta.update(extra)
        mp = out_path.with_name(out_path.stem + "_meta.json"); mp.write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str)); return mp

    def log(msg: str) -> None:
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


# ---- scan geometry: cross-track coordinate u ∈ [-1,1] per I-band sample ------------------------------------------
def scan_u() -> np.ndarray:
    agg = np.r_[np.ones(1280), 2 * np.ones(736), 3 * np.ones(2368), 2 * np.ones(736), np.ones(1280)]
    native_center = np.cumsum(agg) - agg / 2
    theta = (native_center / agg.sum() - 0.5) * np.deg2rad(112.56)
    R, h = 6371.0, 830.0
    gamma = np.arcsin(np.clip(np.sin(np.abs(theta)) * (R + h) / R, -1, 1)) - np.abs(theta)
    return np.sign(theta) * gamma / gamma.max()


U_SCAN = scan_u()


def to_xyz(lon, lat):
    lo, la = np.deg2rad(lon), np.deg2rad(lat)
    return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1)


def to_ll(x):
    x = x / np.linalg.norm(x, axis=-1, keepdims=True)
    return np.rad2deg(np.arctan2(x[..., 1], x[..., 0])), np.rad2deg(np.arcsin(np.clip(x[..., 2], -1, 1)))


def slerp(a, b, t):
    om = np.arccos(np.clip(a @ b, -1, 1)); so = np.sin(om)
    if so < 1e-12:
        return np.broadcast_to(a, (len(t), 3)).copy()
    return (np.sin((1 - t) * om) / so)[:, None] * a + (np.sin(t * om) / so)[:, None] * b


def geolocate(corners_lonlat: np.ndarray, u: np.ndarray, v: np.ndarray):
    """corners in image order (l0,s0),(l0,sMax),(lMax,sMax),(lMax,s0); u cross-track [-1,1], v along-track [0,1]."""
    X = to_xyz(corners_lonlat[:, 0], corners_lonlat[:, 1])
    L = slerp(X[0], X[3], v); Rr = slerp(X[1], X[2], v)
    a = (u + 1) / 2
    om = np.arccos(np.clip((L * Rr).sum(1), -1, 1)); so = np.sin(om)
    P = (np.sin((1 - a) * om) / so)[:, None] * L + (np.sin(a * om) / so)[:, None] * Rr
    return to_ll(P)


def err_km(plo, pla, lo, la):
    return np.hypot(pla - la, (plo - lo) * np.cos(np.deg2rad(la))) * 111.2


# ---- per-granule worker ------------------------------------------------------------------------------------------
_ERA5 = {}


def _load_era5():
    if not _ERA5:
        tcc = xr.concat([xr.open_dataset(RAW / f"era5/era5_tcc_{y}.nc")["tcc"].load() for y in YEARS], dim="valid_time").sortby("valid_time")
        _ERA5["t"] = tcc.valid_time.values.astype("datetime64[ns]")
        _ERA5["lat"] = tcc.latitude.values; _ERA5["lon"] = tcc.longitude.values
        _ERA5["arr"] = tcc.values
    return _ERA5


def process_granule(path: str) -> dict:
    e = _load_era5()
    d = netCDF4.Dataset(path)
    out = {"granule": os.path.basename(path), "product": d.ShortName, "satellite": d.PlatformShortName,
           "day_night_flag": d.DayNightFlag, "start_utc": pd.Timestamp(d.StartTime, tz="UTC"),
           "fire_pixels_total": int(d.variables["FP_line"].shape[0]), "geoloc_method": "gring_scan_gc_blocks16"}
    NL, NS = d.variables["fire mask"].shape  # lines vary (6464 or 6496); NS is 6400
    out["n_lines"] = int(NL)
    glat = np.array(d.GRingPointLatitude, dtype=float); glon = np.array(d.GRingPointLongitude, dtype=float)
    corners = np.c_[glon[list(GRING_PERM)], glat[list(GRING_PERM)]]
    # fire-pixel validation / offset
    n_fp = out["fire_pixels_total"]
    dlon = dlat = 0.0; err_before = err_after = np.nan
    if n_fp >= 1:
        fla = np.array(d.variables["FP_latitude"][:]); flo = np.array(d.variables["FP_longitude"][:])
        fli = np.array(d.variables["FP_line"][:]).astype(int); fsa = np.array(d.variables["FP_sample"][:]).astype(int)
        plo, pla = geolocate(corners, U_SCAN[np.clip(fsa, 0, NS - 1)], (fli + 0.5) / NL)
        err_before = float(np.median(err_km(plo, pla, flo, fla)))
        if n_fp >= 5:
            dlon = float(np.median(flo - plo)); dlat = float(np.median(fla - pla))
            err_after = float(np.median(err_km(plo + dlon, pla + dlat, flo, fla)))
            out["geoloc_method"] = "gring_scan_gc_blocks16+fp_offset"
    out.update(geoloc_err_km_before=err_before, geoloc_err_km_after=err_after, geoloc_offset_lon=dlon, geoloc_offset_lat=dlat)
    # block-centre geolocation
    nbl, nbs = NL // BLK, NS // BLK
    assert NL % BLK == 0 and NS % BLK == 0, (NL, NS)
    bl = (np.arange(nbl) * BLK + BLK / 2); bs = (np.arange(nbs) * BLK + BLK / 2).astype(int)
    V = np.repeat((bl + 0.5) / NL, nbs); Uu = np.tile(U_SCAN[np.clip(bs, 0, NS - 1)], nbl)
    blo, bla = geolocate(corners, Uu, V)
    blo = blo + dlon; bla = bla + dlat
    inc = (blo >= CORRIDOR["lon_min"]) & (blo <= CORRIDOR["lon_max"]) & (bla >= CORRIDOR["lat_min"]) & (bla <= CORRIDOR["lat_max"])
    out["n_blocks_corridor"] = int(inc.sum())
    for k, name in CLASSES.items():
        out[f"n_{name}"] = 0
    out.update(n_pixels_corridor=0, mean_tcc=np.nan, share_tcc_ge_05=np.nan, sensor_cloud_share=np.nan, sensor_cloud_share_land=np.nan)
    for b in range(len(TCC_BINS) - 1):
        out[f"bin{b}_n"] = 0; out[f"bin{b}_cloud"] = 0.0
    if inc.sum() == 0:
        return out
    fm = d.variables["fire mask"][:]
    fm = np.asarray(fm.filled(0) if np.ma.isMaskedArray(fm) else fm, dtype=np.uint8)
    blocks = fm.reshape(nbl, BLK, nbs, BLK).transpose(0, 2, 1, 3).reshape(nbl * nbs, BLK * BLK)[inc]  # (n_inc, 256)
    counts = np.stack([np.bincount(r, minlength=10)[:10] for r in blocks])  # (n_inc, 10)
    tot = counts.sum(0)
    for k, name in CLASSES.items():
        out[f"n_{name}"] = int(tot[k])
    out["n_pixels_corridor"] = int(tot.sum())
    processed = counts[:, 3:].sum(1)  # water, cloud, clear land, unknown, fires
    land_proc = counts[:, [4, 5, 6, 7, 8, 9]].sum(1)
    out["sensor_cloud_share"] = float(tot[4] / tot[3:].sum()) if tot[3:].sum() else np.nan
    out["sensor_cloud_share_land"] = float(tot[4] / tot[[4, 5, 6, 7, 8, 9]].sum()) if tot[[4, 5, 6, 7, 8, 9]].sum() else np.nan
    # ERA5 tcc at block centres, nearest hour to granule start
    t0 = np.datetime64(out["start_utc"].tz_convert(None).to_datetime64(), "ns")
    j = int(np.clip(np.searchsorted(e["t"], t0), 1, len(e["t"]) - 1))
    it = j - 1 if abs(t0 - e["t"][j - 1]) <= abs(t0 - e["t"][j]) else j
    out["era5_hour_gap_h"] = float(abs((t0 - e["t"][it]).astype("timedelta64[m]").astype(float)) / 60)
    iy = np.abs(e["lat"][None, :] - bla[inc][:, None]).argmin(1); ix = np.abs(e["lon"][None, :] - blo[inc][:, None]).argmin(1)
    tcc = e["arr"][it, iy, ix]
    out["mean_tcc"] = float(np.nanmean(tcc)); out["share_tcc_ge_05"] = float(np.nanmean(tcc >= TCC_CLEAR))
    # calibration curve: block cloud share by tcc bin (blocks with ≥ 64 processed pixels)
    ok = processed >= 64
    bshare = np.where(ok, counts[:, 4] / np.maximum(processed, 1), np.nan)
    bi = np.clip(np.digitize(tcc, TCC_BINS) - 1, 0, len(TCC_BINS) - 2)
    for b in range(len(TCC_BINS) - 1):
        m = ok & (bi == b)
        out[f"bin{b}_n"] = int(m.sum()); out[f"bin{b}_cloud"] = float(bshare[m].sum()) if m.any() else 0.0
    # block-level agreement: sensor says cloudy (share>0.5) vs ERA5 tcc≥0.5
    sc = bshare[ok] > 0.5; ec = tcc[ok] >= TCC_CLEAR
    out["n_blocks_valid"] = int(ok.sum()); out["agree_blocks"] = int((sc == ec).sum())
    out["sensor_cloudy_era5_clear"] = int((sc & ~ec).sum()); out["sensor_clear_era5_cloudy"] = int((~sc & ec).sum())
    return out


def main():
    t0 = time.time()
    INTERIM.mkdir(parents=True, exist_ok=True); DERIVED.mkdir(parents=True, exist_ok=True)
    plan = pd.read_csv(RAW / "firemask/granules_full.csv")
    files = sorted(str(p) for p in (RAW / "firemask").glob("*/*/*.nc"))
    on_disk = {os.path.basename(f) for f in files}
    missing = sorted(set(plan.granule) - on_disk)
    log(f"sample plan {len(plan)} granules, on disk {len(files)}, missing {len(missing)}")
    rows = []
    with ProcessPoolExecutor(max_workers=min(6, os.cpu_count() or 2)) as ex:
        for i, r in enumerate(ex.map(process_granule, files, chunksize=8)):
            rows.append(r)
            if (i + 1) % 400 == 0:
                log(f"{i+1}/{len(files)} granules [{time.time()-t0:.0f}s]")
    g = pd.DataFrame(rows)
    g = g.merge(plan[["granule", "iso_year", "iso_week", "date", "day_night"]].rename(columns={"day_night": "plan_day_night"}), on="granule", how="left")
    g["satellite"] = g.satellite.map({"SUOMI-NPP": "N", "Suomi-NPP": "N", "NPP": "N", "NOAA-20": "N20", "JPSS-1": "N20", "J1": "N20"}).fillna(g.satellite)
    g["month"] = g.start_utc.dt.strftime("%Y-%m")
    g["day_night"] = g.day_night_flag.str.capitalize()
    for k, name in CLASSES.items():
        g[f"share_{name}"] = g[f"n_{name}"] / g.n_pixels_corridor.replace(0, np.nan)
    out_g = INTERIM / "firemask_granule_cloud.parquet"
    g.to_parquet(out_g, index=False, compression="zstd")
    valid = g[g.n_pixels_corridor > 0]
    err = {"n_granules_with_fp>=5": int((g.fire_pixels_total >= 5).sum()),
           "median_geoloc_err_km_before_offset": float(np.nanmedian(g.geoloc_err_km_before)),
           "median_geoloc_err_km_after_offset": float(np.nanmedian(g.geoloc_err_km_after)),
           "p90_geoloc_err_km_before_offset": float(np.nanpercentile(g.geoloc_err_km_before.dropna(), 90))}
    log(f"granules with corridor pixels: {len(valid)}/{len(g)}; geoloc {err}")
    write_meta(out_g, inputs={"granule_list": RAW / "firemask/granules_full.csv", "sample_plan": RAW / "firemask/sample_plan_full.csv",
                              **{f"era5_tcc_{y}": RAW / f"era5/era5_tcc_{y}.nc" for y in YEARS}},
               counts={"granules": len(g), "granules_missing_on_disk": len(missing), "granules_with_corridor_pixels": len(valid),
                       "by_satellite": g.satellite.value_counts().to_dict(), "by_day_night": g.day_night.value_counts().to_dict(),
                       "corridor_pixels_total": int(g.n_pixels_corridor.sum())},
               extra={"geolocation": {"method": "APPROXIMATION — no per-pixel lat/lon in VNP14IMG/VJ114IMG and VNP03IMG not on disk. "
                                                "4 GRing corners → image corners (perm learned from fire pixels), along-track linear in line, "
                                                "cross-track from VIIRS I-band aggregation-zone scan geometry (±56.28°, 830 km), great-circle "
                                                "interpolation on the sphere, evaluated at 16×16-pixel block centres; per-granule constant "
                                                "offset from fire pixels when ≥5 available.",
                                      "gring_perm": GRING_PERM, "validation": err, "corridor": CORRIDOR, "block_px": BLK},
                      "fire_mask_classes": CLASSES,
                      "definitions": {"sensor_cloud_share": "cloud / (water+cloud+clear_land+unknown+fires) over corridor pixels",
                                      "sensor_cloud_share_land": "cloud / (cloud+clear_land+unknown+fires)",
                                      "mean_tcc": "mean ERA5 tcc (nearest 0.25° point, nearest hour to granule start) over corridor block centres",
                                      "binK_n / binK_cloud": "blocks with ≥64 processed pixels whose ERA5 tcc falls in bin K of 10 equal bins; sum of block cloud shares",
                                      "agree_blocks": "blocks where (sensor cloud share>0.5) == (ERA5 tcc≥0.5)"}})

    # ---- calibration table (published) ---------------------------------------------------------------------------
    v = valid.copy()
    bin_n = v[[f"bin{b}_n" for b in range(10)]].to_numpy(); bin_c = v[[f"bin{b}_cloud" for b in range(10)]].to_numpy()
    v["pix_cloud"] = v.n_cloud; v["pix_proc"] = v[[f"n_{CLASSES[k]}" for k in range(3, 10)]].sum(1)
    v["pix_land_proc"] = v[[f"n_{CLASSES[k]}" for k in [4, 5, 6, 7, 8, 9]]].sum(1)
    v["pix_notproc"] = v[[f"n_{CLASSES[k]}" for k in range(0, 3)]].sum(1)
    v["tcc_x_blocks"] = v.mean_tcc * v.n_blocks_valid.fillna(0)
    v["tcc_ge05_x_blocks"] = v.share_tcc_ge_05 * v.n_blocks_valid.fillna(0)
    agg = v.groupby(["month", "day_night"]).agg(
        n_granules=("granule", "size"), n_blocks=("n_blocks_valid", "sum"), pix_corridor=("n_pixels_corridor", "sum"),
        pix_cloud=("pix_cloud", "sum"), pix_proc=("pix_proc", "sum"), pix_land_proc=("pix_land_proc", "sum"), pix_notproc=("pix_notproc", "sum"),
        pix_water=("n_water", "sum"), pix_fire=("n_fire_low", "sum"), tcc_x=("tcc_x_blocks", "sum"), tcc05_x=("tcc_ge05_x_blocks", "sum"),
        agree=("agree_blocks", "sum"), sc_ec=("sensor_cloudy_era5_clear", "sum"), scl_ecl=("sensor_clear_era5_cloudy", "sum"),
        fp5=("geoloc_err_km_after", lambda s: int(s.notna().sum()))).reset_index()
    fires = v.groupby(["month", "day_night"])[["n_fire_low", "n_fire_nominal", "n_fire_high"]].sum().sum(1).values
    agg["pix_fire"] = fires
    agg["sensor_cloud_share"] = (agg.pix_cloud / agg.pix_proc).round(4)
    agg["sensor_cloud_share_land"] = (agg.pix_cloud / agg.pix_land_proc).round(4)
    agg["not_processed_share"] = (agg.pix_notproc / agg.pix_corridor).round(4)
    agg["era5_mean_tcc"] = (agg.tcc_x / agg.n_blocks).round(4)
    agg["era5_share_tcc_ge_05"] = (agg.tcc05_x / agg.n_blocks).round(4)
    agg["block_agreement"] = (agg.agree / agg.n_blocks).round(4)
    agg["share_sensor_cloudy_era5_clear"] = (agg.sc_ec / agg.n_blocks).round(4)
    agg["share_sensor_clear_era5_cloudy"] = (agg.scl_ecl / agg.n_blocks).round(4)
    agg = agg.drop(columns=["tcc_x", "tcc05_x", "agree", "sc_ec", "scl_ecl"]).rename(columns={"fp5": "n_granules_fp_offset"})
    agg["table"] = "month_daynight"
    # tcc-bin calibration curve by day/night (all months) and by season
    v["season"] = np.where(v.start_utc.dt.month.isin([5, 6, 7, 8, 9, 10]), "summer", "winter")
    curve_rows = []
    for (dn, se), sub in v.groupby(["day_night", "season"]):
        n = sub[[f"bin{b}_n" for b in range(10)]].sum().to_numpy(); c = sub[[f"bin{b}_cloud" for b in range(10)]].sum().to_numpy()
        for b in range(10):
            curve_rows.append({"table": "tcc_bin_curve", "day_night": dn, "season": se, "tcc_bin_lo": round(TCC_BINS[b], 1), "tcc_bin_hi": round(TCC_BINS[b + 1], 1),
                               "n_blocks": int(n[b]), "sensor_cloud_share": round(float(c[b] / n[b]), 4) if n[b] else np.nan})
    curve = pd.DataFrame(curve_rows)
    cal = pd.concat([agg, curve], ignore_index=True)
    out_c = DERIVED / "firemask_vs_era5.csv"
    cal.to_csv(out_c, index=False)
    # summary for the log
    tot_blocks = agg.n_blocks.sum()
    summ = {"overall_block_agreement": round(float((agg.block_agreement * agg.n_blocks).sum() / tot_blocks), 4),
            "overall_sensor_cloud_share": round(float(agg.pix_cloud.sum() / agg.pix_proc.sum()), 4),
            "overall_era5_mean_tcc": round(float((agg.era5_mean_tcc * agg.n_blocks).sum() / tot_blocks), 4),
            "overall_era5_share_tcc_ge_05": round(float((agg.era5_share_tcc_ge_05 * agg.n_blocks).sum() / tot_blocks), 4),
            "by_day_night": json.loads(agg.groupby("day_night").apply(lambda s: pd.Series({
                "sensor_cloud_share": s.pix_cloud.sum() / s.pix_proc.sum(), "era5_mean_tcc": (s.era5_mean_tcc * s.n_blocks).sum() / s.n_blocks.sum(),
                "block_agreement": (s.block_agreement * s.n_blocks).sum() / s.n_blocks.sum(), "n_granules": s.n_granules.sum()}), include_groups=False).round(4).to_json()),
            "curve": json.loads(curve.pivot_table(index=["day_night", "season"], columns="tcc_bin_lo", values="sensor_cloud_share").round(3).to_json(orient="index"))}
    # correlation of granule-level means
    cc = v[["sensor_cloud_share", "mean_tcc"]].dropna()
    summ["granule_level_pearson_r"] = round(float(np.corrcoef(cc.sensor_cloud_share, cc.mean_tcc)[0, 1]), 4)
    summ["granule_level_n"] = int(len(cc))
    log(f"calibration summary: {json.dumps(summ, indent=1)}")
    write_meta(out_c, inputs={"firemask_granule_cloud_meta": out_g.with_name(out_g.stem + "_meta.json")},
               counts={"rows": len(cal), "month_daynight_rows": len(agg), "curve_rows": len(curve), "granules_used": len(v)},
               extra={"tier": "exploratory tier 3 (DESIGN D9)", "summary": summ,
                      "geolocation_caveat": "pixel geolocation is approximated from GRing corners (see firemask_granule_cloud_meta.json); corridor-level shares only"})
    log(f"done in {time.time()-t0:.0f}s; wrote {out_g}, {out_c}")


if __name__ == "__main__":
    main()
