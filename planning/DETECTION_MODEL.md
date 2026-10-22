# Detection model build (H1, H2, H3, H7, H8) — contract

Spec is PREREG.md §3–§4 (fixed; do not reinterpret) and DESIGN.md D9–D12, D15. This file only fixes file names,
schemas and the order of work so parallel builders fit together. Written 2026-10-22, after tag `prereg-v1`.

Run everything with `~/D3/Frontline_From_Space/.venv/bin/python -I` (geopandas, shapely 2.1, xarray, netCDF4,
rasterio, scikit-learn, lightgbm, statsmodels, scipy, duckdb, pyfixest, linearmodels, h3 installed). Scripts live
in `scripts/analysis/`, numbered. Every output gets a `<name>_meta.json` beside it (inputs with sha256, counts,
script, written_utc) via a small helper in `scripts/analysis/_common.py` (copy the pattern from
`scripts/telegram/_common.py`). Nothing under `data/derived/` finer than cell-week or oblast-day (PREREG §7);
event-level and cell-day tables live under `data/interim/analysis/` (gitignored).

## Confirmatory firewall
C1 territorial outcomes (VIINA 2022–2024-07-07) are **not** touched in this build. The detection model uses only
V (events), O (observability) and FIRMS detections. FIRMS rows in C1 dates are used only as *detections near
events* and for H3 paired looks; no fires-vs-control join is made here.

## Inputs on disk
| What | Path | Notes |
|---|---|---|
| GeoConfirmed Ukraine | `data/raw/events/geoconfirmed_Ukraine.json` | list of factions → `icons[]` (icon name = event type) → `placemarks[] {id, date, la, lo, ds}`; `date` is day precision |
| Bellingcat TimeMap | `data/raw/events/bellingcat_timemap.json` | 2,517 `{id, date, latitude, longitude, impact[], weapon_system[], location}` |
| FIRMS S-NPP + NOAA-20 country files | `data/raw/firms_country_post_tag/viirs-{snpp,jpss1}_{2022..2025}_{Ukraine,Russian_Federation}.csv` | standard FIRMS columns, `acq_time` HHMM UTC |
| FIRMS NOAA-21 (and NRT) | `data/raw/firms_api/ukraine/VIIRS_{NOAA20,NOAA21}_{SP,NRT}/<year>/*.csv` | API area pulls; SP to 2026-06-30, NRT after; drop SP/NRT duplicates |
| FIRMS baseline | `data/raw/firms_country/viirs-snpp_{2012..2021}_Ukraine.csv` | B set |
| Granule footprints | `data/raw/cmr_footprints/viirs_granule_footprints_2022_2025.parquet` | 44,714 rows: product (VNP14IMG S-NPP, VJ114IMG NOAA-20, VJ214IMG NOAA-21, VNP03IMG dup of VNP14IMG), satellite, start_utc, end_utc, day_night, is_latest, footprint_wkt. **Use is_latest==1 and the *14IMG products only.** |
| ERA5 tcc | `data/raw/era5/era5_tcc_{2022..2025}.nc` | var `tcc`, 0.25°, lat 44–53, lon 22–41, hourly at overpass hours (3,650 steps/yr) |
| ERA5-Land snow depth | `data/raw/era5/era5land_snowdepth_{2022..2025}.nc` | var `sde` (m), daily, 0.1° |
| Fire-mask sample | `data/raw/firemask/{VNP14IMG,VJ114IMG}/<year>/*.nc`, plan in `data/raw/firemask/sample_plan_full.csv`, list in `granules_full.csv` | 4,365 granules, corridor 32.5–40E / 46.3–50.5N, 2 days per ISO week per satellite |
| WorldCover 2021 | `data/raw/worldcover/ESA_WorldCover_10m_2021_v200_*_Map.tif` | 24 tiles, 10 m, class codes 10..100 |
| Ukraine boundary, oblasts, Kyiv city | `data/raw/boundaries/geoboundaries/geoBoundaries-UKR-ADM{0,1,2}.geojson`; Natural Earth in `naturalearth/` | Kyiv city = ADM1 feature for Kyiv (misto) |

## Outputs and owners

### Builder A — events, fires, land cover (`scripts/analysis/01_events.py`, `02_fires.py`)
- `data/interim/analysis/events_v.parquet`: one row per V event, 2022-02-24 → 2025-12-31, inside Ukraine ADM0.
  Columns: `event_id, source {geoconfirmed,bellingcat}, event_type_raw (icon name / impact list joined by '|'),
  event_type (coarse: strike, shelling, vehicle_loss, aircraft_loss, infrastructure, other — mapping table in the
  script, printed in meta), date, lat, lon, h3_r5, h3_r6, oblast_iso, landcover_code (WorldCover class at the point),
  landcover_class (text), split {train,test}`.
  Split: calendar months 2022-02 … 2025-12 drawn 70/30 by `numpy.random.default_rng(20261014)`; list the test months in meta.
  Dedup rule: GeoConfirmed placemarks with identical (date, lat, lon) are one event; a Bellingcat and a GeoConfirmed
  record within 100 m on the same date are one event (keep both ids in `dup_ids`).
- `data/interim/analysis/fires.parquet`: all VIIRS detections 2022-01-01 → 2025-12-31 for Ukraine + western Russia
  (both country files + API pulls, SP/NRT deduped on (satellite, acq_datetime, lat, lon)), confidence n/h only, all
  `type`. Columns: `fire_id, satellite {N,N20,N21}, acq_ts_utc, lat, lon, h3_r5, h3_r6, frp, bright_ti4, confidence,
  daynight, type, scan, track, source_file`. Plus `fires_baseline.parquet` for 2012–2021 Ukraine (same columns).
- Report: event counts by source/type/year, fires by satellite/year, land-cover mix of events.

### Builder B — observability (`scripts/analysis/03_opportunity.py`, `04_firemask_sample.py`)
- `data/interim/analysis/overpasses_r6.parquet`: one row per (h3_r6 cell, granule) for every res-6 cell whose
  centroid is inside Ukraine ADM0 (plus a 50 km buffer into Russia), from footprints with `is_latest==1`,
  products VNP14IMG/VJ114IMG/VJ214IMG, 2022–2025. Columns: `h3_r6, granule_ur, satellite, start_utc, day_night,
  tcc (ERA5 at the cell centroid, nearest hour), sde_cm (ERA5-Land, that day), covered=1`.
  Method: shapely STRtree of footprints vs cell centroids; the footprint WKT crosses the dateline for some
  granules — fix with `shapely.ops`/split or by testing in a projected CRS; log how many were fixed/dropped.
- `data/interim/analysis/opportunity_r6_day.parquet`: cell-day aggregate per PREREG §3: `n_overpasses,
  n_clear_overpasses (tcc<0.5 & sde<1 cm), opportunity (= n_clear_overpasses), n_night, n_day, min_tcc,
  hours_since_prev_overpass_mean, snow_day (sde≥1 cm)`, per satellite too (`opp_N, opp_N20, opp_N21`) so H8 can drop S-NPP.
- `data/derived/observability/opportunity_r5_week.csv`: res-5 × ISO week sums (published; this is the panel covariate).
- `data/interim/analysis/firemask_granule_cloud.parquet` (`04_firemask_sample.py`): for each sampled VNP14IMG/VJ114IMG
  granule, the share of corridor pixels in each fire-mask class (0–9: not processed, cloud, water, clear-no-fire,
  fire low/nominal/high, …) and the mean ERA5 tcc over the same pixels at that hour → a tcc-vs-sensor-cloud
  calibration table `data/derived/observability/firemask_vs_era5.csv` (by month, day/night). Exploratory tier 3.
- Report: cells × days covered, mean overpasses/day by satellite and year, share of cell-days with opportunity 0,
  tcc-vs-fire-mask agreement.

### Builder C — tests (after A and B): `05_recall_h1.py`, `06_model_h2.py`, `07_paired_h3.py`, `08_constellation_h8.py`, `09_transfer_h7.py`
- Detection per PREREG §3: event detected if ≥1 fire within 1 km and within −12/+12 h of the event date's overpass
  window (operationalise: any fire with acq_ts in [date 00:00 − 12 h, date 24:00 + 12 h] UTC within 1 km; state it).
- H1 strata, Wilson CIs, bootstrap ratio (1,000 draws over events, seed 20261014).
- H2 logistic (statsmodels, standardised) + LightGBM, features exactly as listed in PREREG H2; AUC on `split==test`;
  calibration plot; feature table. Save model objects under `data/interim/analysis/models/`.
- H3 paired looks: S-NPP detections with a NOAA-20 overpass of the same res-6 cell 30–70 min later (or earlier),
  tcc<0.3; share with a NOAA-20 detection within 1 km; by season × day/night, Wilson CI.
- H8: recompute H1 recall and blind-season length with S-NPP rows removed from fires and overpasses.
- H7: `predictions/transfer_v1.json` = predicted recall for Karabakh (Oct–Nov 2020 AOI) and Sudan Darfur/Kordofan
  (2023-04-15 → 2025-12-31) from the H2 model with climatological covariates. **ERA5 for those AOIs is not on disk**;
  fetch tcc/snow for the two AOIs with `scripts/fetch_era5.py` (observability data, allowed) before predicting.
  Commit the predictions file **before** `fetch_post_tag.py` pulls T1/T2.
- All results to `data/derived/results/h{1,2,3,8}_*.{csv,json}` with figures in `figures/`; captions marked
  **confirmatory**.

## Conventions
- Seed 20261014 everywhere. UTC timestamps; `acq_date`+`acq_time` → `acq_ts_utc`.
- h3 via `h3.latlng_to_cell(lat, lon, res)` (h3 v4 API).
- Distances in EPSG:3035 or haversine; 1 km means ≤ 1,000 m.
- Season: summer May–Oct, winter Nov–Apr. H1 "best" = tcc<0.5 & no snow & night & Jun–Sep; "worst" = (tcc≥0.5 or snow) & day & Nov–Feb.
- Write what was done and any ambiguity resolved into the meta JSON and a dated paragraph at the bottom of this file.
