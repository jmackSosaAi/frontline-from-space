"""02_fires.py — build data/interim/analysis/fires.parquet (2022-01-01 -> 2025-12-31, Ukraine + western
Russia, all VIIRS satellites) and fires_baseline.parquet (S-NPP Ukraine 2012–2021, set B).

Contract: planning/DETECTION_MODEL.md (Builder A); fire definition PREREG.md §3 (VIIRS 375 m, confidence
nominal or high, any `type`, any satellite; daynight and satellite retained).

Sources merged for fires.parquet:
  - FIRMS country files  data/raw/firms_country_post_tag/viirs-{snpp,jpss1}_{2022..2025}_{Ukraine,Russian_Federation}.csv
  - FIRMS API area pulls data/raw/firms_api/{ukraine,west_russia}/VIIRS_{SNPP,NOAA20,NOAA21}_{SP,NRT}/<year>/*.csv
    (the API pulls are the only NOAA-21 source; S-NPP/NOAA-20 API rows duplicate the country files)
  Dedup key: (satellite, acq_ts_utc, round(lat,5), round(lon,5)); keep order country > API SP > API NRT.
  Spatial clip: union of the two pull boxes, lon 22–60 E, lat 41–64 N (the Russian_Federation country file
  covers all of Russia; "western Russia" = the west_russia pull box 27–60 E / 41–64 N).

Run:  ~/D3/Frontline_From_Space/.venv/bin/python -I scripts/analysis/02_fires.py
"""
from __future__ import annotations
import sys, time, glob
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, RAW, INTERIM, FIRES_START, FIRES_END, BASELINE_YEARS, write_meta, log, h3_cells, h3_parent

COUNTRY = RAW / "firms_country_post_tag"
API = RAW / "firms_api"
BASE = RAW / "firms_country"
OUT = INTERIM / "fires.parquet"
OUT_B = INTERIM / "fires_baseline.parquet"
LON0, LON1, LAT0, LAT1 = 22.0, 60.0, 41.0, 64.0
USECOLS = ["latitude", "longitude", "bright_ti4", "scan", "track", "acq_date", "acq_time", "satellite",
           "confidence", "frp", "daynight", "type"]
DTYPES = {"latitude": "float64", "longitude": "float64", "bright_ti4": "float32", "scan": "float32",
          "track": "float32", "acq_date": "string", "acq_time": "string", "satellite": "string",
          "confidence": "string", "frp": "float32", "daynight": "string", "type": "string"}
SAT_NORM = {"N": "N", "N20": "N20", "N21": "N21", "NPP": "N", "NOAA-20": "N20", "NOAA-21": "N21",
            "1": "N20", "2": "N21"}
COLS = ["fire_id", "satellite", "acq_ts_utc", "lat", "lon", "h3_r5", "h3_r6", "frp", "bright_ti4",
        "confidence", "daynight", "type", "scan", "track", "source_file"]


def read_one(p: Path, priority: int) -> pd.DataFrame:
    hdr = pd.read_csv(p, nrows=0).columns
    use = [c for c in USECOLS if c in hdr]
    df = pd.read_csv(p, usecols=use, dtype={c: DTYPES[c] for c in use})
    if "type" not in df.columns:  # NRT files carry no `type`
        df["type"] = pd.array([pd.NA] * len(df), dtype="string")
    n0 = len(df)
    df = df[df.confidence.isin(["n", "h"])]
    df = df[df.latitude.between(LAT0, LAT1) & df.longitude.between(LON0, LON1)]
    t = df.acq_time.str.zfill(4)
    df["acq_ts_utc"] = pd.to_datetime(df.acq_date + " " + t.str[:2] + ":" + t.str[2:], format="%Y-%m-%d %H:%M", utc=True)
    df["satellite"] = df.satellite.map(SAT_NORM).fillna(df.satellite)
    df["source_file"] = str(p.relative_to(ROOT))
    df["_prio"] = np.int8(priority)
    df["_n_raw"] = n0
    return df.drop(columns=["acq_date", "acq_time"])


def finish(df: pd.DataFrame, lo: str, hi: str) -> tuple[pd.DataFrame, dict]:
    c: dict = {"rows_after_conf_bbox": int(len(df))}
    df = df[(df.acq_ts_utc >= pd.Timestamp(lo, tz="UTC")) & (df.acq_ts_utc < pd.Timestamp(hi, tz="UTC") + pd.Timedelta(days=1))]
    c["rows_in_window"] = int(len(df))
    df = df.assign(_lat=df.latitude.round(5), _lon=df.longitude.round(5))
    df = df.sort_values(["_prio", "source_file"], kind="stable")
    before = len(df)
    df = df.drop_duplicates(["satellite", "acq_ts_utc", "_lat", "_lon"], keep="first")
    c["dedup_removed"] = int(before - len(df))
    df = df.sort_values(["acq_ts_utc", "satellite", "_lat", "_lon"]).reset_index(drop=True)
    df = df.rename(columns={"latitude": "lat", "longitude": "lon"})
    log(f"h3 for {len(df):,} rows")
    df["h3_r6"] = h3_cells(df.lat, df.lon, 6); df["h3_r5"] = h3_parent(df.h3_r6, 5)
    df["fire_id"] = np.arange(len(df), dtype=np.int64)
    df["type"] = pd.to_numeric(df["type"], errors="coerce").astype("Int8")
    df["satellite"] = df.satellite.astype("category"); df["confidence"] = df.confidence.astype("category")
    df["daynight"] = df.daynight.astype("category"); df["source_file"] = df.source_file.astype("category")
    return df[COLS], c


def main() -> None:
    t0 = time.time()
    INTERIM.mkdir(parents=True, exist_ok=True)

    # ---------------- fires 2022–2025 --------------------------------------------------------------
    country = sorted(COUNTRY.glob("viirs-*_20[2][2-5]_*.csv"))
    api_sp = sorted(p for p in API.glob("*/VIIRS_*_SP/*/*.csv") if 2022 <= int(p.parent.name) <= 2025)
    api_nrt = sorted(p for p in API.glob("*/VIIRS_*_NRT/*/*.csv") if 2022 <= int(p.parent.name) <= 2025)
    log(f"files: {len(country)} country, {len(api_sp)} API SP, {len(api_nrt)} API NRT")
    parts, raw_rows = [], {}
    for prio, group in ((0, country), (1, api_sp), (2, api_nrt)):
        for p in group:
            d = read_one(p, prio)
            raw_rows[str(p.relative_to(ROOT))] = int(d._n_raw.iloc[0]) if len(d) else 0
            parts.append(d.drop(columns=["_n_raw"]))
    df = pd.concat(parts, ignore_index=True); del parts
    log(f"concat {len(df):,} rows (conf n/h, in bbox)")
    fires, c = finish(df, FIRES_START, FIRES_END); del df
    fires.to_parquet(OUT, index=False)
    yr = fires.acq_ts_utc.dt.year
    by_sat_year = fires.groupby([fires.satellite, yr], observed=True).size().unstack(fill_value=0)
    by_sat_year.columns = [str(x) for x in by_sat_year.columns]
    by_sat_year.to_csv(INTERIM / "fires_summary_by_sat_year.csv")
    ukr_box = fires.lat.between(44, 53) & fires.lon.between(22, 41)
    # dedup audit: S-NPP/NOAA-20 rows that survive only from the API pulls should sit outside the country
    # polygons (bbox pulls include third countries + sea); count those inside Ukraine ADM0.
    import shapely
    from _common import ukraine_adm0
    ua = ukraine_adm0()
    api_only = fires.source_file.astype(str).str.contains("firms_api") & (fires.satellite != "N21")
    in_ua = shapely.contains(ua, shapely.points(fires.lon.values, fires.lat.values))
    c.update(
        in_ukraine_adm0=int(in_ua.sum()),
        api_only_snpp_noaa20_rows=int(api_only.sum()),
        api_only_snpp_noaa20_inside_ukraine=int((api_only & in_ua).sum()),
    )
    c.update(
        fires=int(len(fires)), by_satellite=fires.satellite.value_counts().to_dict(),
        by_satellite_year={s: {k: int(v) for k, v in r.items()} for s, r in by_sat_year.iterrows()},
        by_daynight=fires.daynight.value_counts().to_dict(), by_confidence=fires.confidence.value_counts().to_dict(),
        by_type=fires["type"].value_counts(dropna=False).rename(lambda x: str(x)).to_dict(),
        in_ukraine_pull_box=int(ukr_box.sum()),
        by_source_group={"country": int(fires.source_file.str.startswith("data/raw/firms_country_post_tag").sum()),
                         "api_sp": int(fires.source_file.str.contains("_SP/").sum()),
                         "api_nrt": int(fires.source_file.str.contains("_NRT/").sum())},
        raw_rows_per_file_total=int(sum(raw_rows.values())),
    )
    write_meta(OUT, inputs={"country_files": country, "api_sp_files": api_sp, "api_nrt_files": api_nrt},
               counts=c, hash_inputs=False, extra={
        "window": [FIRES_START, FIRES_END], "bbox_lon_lat": [LON0, LAT0, LON1, LAT1],
        "filter": "confidence in {n,h}; any type; any daynight",
        "dedup": "key (satellite, acq_ts_utc, round(lat,5), round(lon,5)); keep first after sorting country < API SP < API NRT",
        "satellite_codes": {"N": "Suomi-NPP", "N20": "NOAA-20 (JPSS-1)", "N21": "NOAA-21 (JPSS-2)"},
        "type_note": "NRT files have no `type` column -> NA (only 2026 NRT exists on disk, outside the window)",
        "runtime_s": round(time.time() - t0, 1),
    })
    print(by_sat_year.to_string()); print("dedup removed:", c["dedup_removed"], "fires:", c["fires"])

    # ---------------- baseline 2012–2021 (S-NPP Ukraine) --------------------------------------------
    t1 = time.time()
    base_files = [BASE / f"viirs-snpp_{y}_Ukraine.csv" for y in BASELINE_YEARS]
    base_files = [p for p in base_files if p.exists()]
    db = pd.concat([read_one(p, 0).drop(columns=["_n_raw"]) for p in base_files], ignore_index=True)
    base, cb = finish(db, f"{min(BASELINE_YEARS)}-01-01", f"{max(BASELINE_YEARS)}-12-31"); del db
    base.to_parquet(OUT_B, index=False)
    byr = base.acq_ts_utc.dt.year.value_counts().sort_index()
    cb.update(fires=int(len(base)), by_year={int(k): int(v) for k, v in byr.items()},
              by_daynight=base.daynight.value_counts().to_dict(), by_satellite=base.satellite.value_counts().to_dict())
    write_meta(OUT_B, inputs={"baseline_files": base_files}, counts=cb, extra={
        "window": [f"{min(BASELINE_YEARS)}-01-01", f"{max(BASELINE_YEARS)}-12-31"], "bbox_lon_lat": [LON0, LAT0, LON1, LAT1],
        "filter": "confidence in {n,h}; any type", "dedup": "same key as fires.parquet",
        "runtime_s": round(time.time() - t1, 1)})
    print("baseline by year:", cb["by_year"], "dedup removed:", cb["dedup_removed"])
    print(f"done in {time.time() - t0:.0f}s -> {OUT.relative_to(ROOT)}, {OUT_B.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
