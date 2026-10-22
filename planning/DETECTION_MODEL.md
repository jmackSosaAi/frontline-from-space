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

## Builder A log

**2026-10-22.** Built `scripts/analysis/_common.py` (ROOT/RAW/INTERIM paths, `write_meta` with per-file sha256 or
name+size for large file lists, `h3_cells`/`h3_parent` on the h3 v4 API, `season`, `ukraine_adm0`, `worldcover_at`),
`01_events.py` and `02_fires.py`; ran both from the repo root with the project venv (`-I`). Outputs and metas are in
`data/interim/analysis/` (events_v, fires, fires_baseline, plus `events_v_summary.csv` and
`fires_summary_by_sat_year.csv`). Runtime: events 8 s, fires + baseline 42 s.
*Events:* GeoConfirmed 60,805 placemarks (60,744 with date and coordinates) and Bellingcat 2,517; in the V window
50,889 + 2,517; 255 GeoConfirmed exact (date, lat, lon) duplicates collapsed; 683 Bellingcat–GeoConfirmed pairs within
100 m (EPSG:3035) on the same date merged into 683 Bellingcat events (651 GeoConfirmed ids moved to `dup_ids`); 6,624
events outside geoBoundaries ADM0 dropped (Belgorod/Kursk, Black Sea, Transnistria etc.); **45,876 events** kept
(bellingcat 2,396; geoconfirmed 43,480), all with an oblast (ADM1 `shapeISO`, no seam fills needed). Coarse types:
strike 16,633, other 11,629, vehicle_loss 8,468, infrastructure 8,235, aircraft_loss 709, shelling 202. Land cover:
built-up 36 %, tree cover 26 %, cropland 22 %, grassland 14 %, water 1 %. Split: 47 months, 14 test months drawn by
`default_rng(20261014).choice` over the sorted month list (test = 2022-06, 2022-08, 2023-05, 2023-07, 2023-08,
2023-11, 2023-12, 2024-01, 2024-03, 2024-04, 2024-05, 2025-01, 2025-04, 2025-12) → train 31,140 / test 14,736.
*Ambiguities resolved:* (1) the GeoConfirmed API returns `name: null` for every icon, so the type is the template
PNG basename (numeric codes 01…203, `moto`, flags, and 21 custom UUID icons). No legend exists on disk; I viewed the
public icon templates and read the scheme off them (category = leading digits, last digit 1 intact / 2 damaged / 3
destroyed) and fixed the full code → (raw label, coarse type) table in the script and in `events_v_meta.json`
(`event_type_mapping`). Judgement calls: intact artillery/MLRS positions → shelling; damaged/destroyed vehicles,
ships, trains, SAMs, radars → vehicle_loss; damaged/destroyed helicopters, jets, UAVs (fixed-wing, quadcopter,
loitering munitions) → aircraft_loss; explosions, munition impacts and all missile icons (incl. intercepts) →
strike; bridges, buildings, industrial sites, fortifications → infrastructure; intact equipment, photo/video
markers, persons, casualties, camps, flags → other. (2) Bellingcat coarse type: infrastructure when any `impact[]`
item names a civilian object class, otherwise strike (empty, Undefined, Military); raw = impact list joined by `|`.
(3) Cross-source duplicates keep the Bellingcat row (dated, typed record); GeoConfirmed exact duplicates keep the
first id by sort and join the raw types with `|`. (4) Inside-Ukraine test uses geoBoundaries ADM0 (includes Crimea).
*Fires:* 16 country files + 1,544 API SP files (no NRT within 2022–2025; NRT only exists for 2026). Confidence n/h,
clipped to the union pull box lon 22–60 E / lat 41–64 N (the Russian_Federation country file spans all of Russia;
"western Russia" = the west_russia pull box). 4,810,304 rows → dedup on (satellite, acq_ts_utc, lat, lon rounded to
5 dp), keep country > API SP > API NRT, removed 2,432,140 → **2,376,955 fires** (N 847,810; N20 886,546; N21 642,599;
day 1,223,884 / night 1,153,071; type 0: 1,722,592, 2: 570,824, 3: 83,539). By year — N: 192,844 / 191,935 /
236,381 / 226,650; N20: 211,762 / 188,292 / 257,749 / 228,743; N21: 0 / 182,520 / 244,816 / 215,263 (2022–2025).
Inside Ukraine ADM0: 670,417 (N 49,398 / 40,962 / 82,468 / 62,362; N20 56,221 / 39,941 / 90,225 / 63,240; N21 0 /
39,636 / 86,659 / 59,305). Dedup audit: 296,142 S-NPP/NOAA-20 rows survive only from the API pulls; none has a
country-file row within 0.5 km at the same minute, 99 % lie outside Ukraine and Russia (Kazakhstan, Romania, sea,
Turkey, Belarus … inside the boxes) and 2,918 lie inside Ukraine (genuine archive-vs-API differences, kept).
`fire_id` is the row index after sorting by (acq_ts_utc, satellite, lat, lon); `type` is Int8. Baseline
`fires_baseline.parquet`: S-NPP Ukraine 2012–2021, 951,774 rows (68,838 / 60,815 / 158,605 / 161,389 / 91,539 /
110,918 / 69,053 / 95,263 / 90,393 / 44,961), no duplicates. Nothing under `data/derived/` or `data/raw/viina` was
touched; nothing committed.

## Builder B log

**2026-10-22 — observability tiers 1–3 built (`scripts/analysis/03_opportunity.py`, `04_firemask_sample.py`).**
*Cells:* h3 res-6 cells whose centroid is inside Ukraine ADM0 (geoBoundaries, incl. Crimea) **or** inside Russia
(Natural Earth 10m) within a 50 km EPSG:3035 buffer of Ukraine → **20,327 cells** (18,302 Ukraine + 2,025 Russia;
5,126 buffer cells in Belarus/Poland/Moldova/Romania/sea dropped). *Footprints:* 31,782 of 44,714 rows used
(`is_latest==1`, VNP14IMG 11,538 / VJ114IMG 11,773 / VJ214IMG 8,471; VNP03IMG duplicates and 1,395 superseded rows
dropped). Antimeridian guard (lon span > 180° → shift negative lons +360) found **0 crossing, 0 invalid, 0 dropped**
— the pull was already regional. Coverage = centroid `within` the 5-vertex CMR polygon (STRtree, one tree per month).
ERA5 `tcc`: nearest 0.25° point to the centroid, nearest available hour to granule start (median gap 0.3 h, none > 1 h;
every cell inside the grid). ERA5-Land `sde`: nearest 0.1° point, same UTC date, ×100 → cm. `overpasses_r6.parquet`
is hive-partitioned by year (**272.6 M cell-granule rows**, 401 MB zstd) with `hours_since_prev` (previous overpass of
that cell by any satellite, carried across months). `opportunity_r6_day.parquet` is the **full 20,327 × 1,461-day grid
(29.7 M rows, zeros filled)**: `opportunity = n_clear_overpasses` = overpasses with tcc < 0.5 and sde < 1 cm (PREREG §3,
unknown → not clear), `n_day/n_night` from the granule flag with the 3,110 "Both" granules split by solar elevation at
the centroid, `snow_day` from ERA5-Land directly, `min_tcc`, per-satellite `n_*`/`opp_*`. Mean overpasses per
cell-day: 2022 **7.11** (N 3.51, N20 3.61), 2023 **10.45** (N 3.66, N20 3.59, N21 3.20 from its 2023-02 start), 2024
10.60, 2025 10.85; mean opportunity 2.03 / 3.45 / 3.64 / 3.66. **Share of cell-days with opportunity 0: summer 21.3 %,
winter 67.0 %** (2022 25.4/69.8, 2023 19.1/69.3, 2024 19.1/64.6, 2025 21.5/64.3); no cell-day lacks an overpass.
Published `data/derived/observability/opportunity_r5_week.csv`: 3,052 res-5 cells × 210 ISO weeks = 640,920 rows
(60 MB; the two boundary weeks 2021-W52 and 2026-W01 are partial — `n_cell_days` shows it), columns include
`opportunity`, per-satellite `opp_*`, `snow_cell_days`, `cell_days_opportunity_0`, `share_in_ukraine`. Runtime 9.5 min,
< 4 GB.
*Fire-mask sample (tier 3):* all 4,365 granules on disk match `granules_full.csv`. **Ambiguity resolved:** the
VNP14IMG/VJ114IMG files carry no per-pixel lat/lon (only the 4 GRing corners and the fire pixels' lat/lon) and VNP03IMG
is not on disk, so pixel geolocation is **approximated** — GRing corners mapped to image corners (order
`(2,3,0,1)` learned from the fire-pixel line/sample↔lat/lon pairs, 88 % of granules agree), along-track linear in line
(6,464 or 6,496 lines), cross-track from the VIIRS I-band aggregation-zone scan geometry (±56.28°, 830 km), great-circle
interpolation, evaluated at 16×16-pixel block centres, plus a per-granule constant offset from the fire pixels when
≥ 5 exist (4,202 granules). Validation against fire-pixel positions: median error 10.9 km before / **5.5 km after**
the offset (p90 9.1 km, max 24 km) — fine for corridor shares, not for anything finer; flagged in `geoloc_method`
and both meta files. Plain lon/lat bilinear was rejected (median error 160 km). 4,340 granules have corridor pixels
(25 do not). Over the corridor the **sensor flags 45.5 % of processed pixels as cloud vs ERA5 mean tcc 0.60**
(share tcc ≥ 0.5: 0.60); block-level agreement of (sensor cloud share > 0.5) with (tcc ≥ 0.5) is **74.2 %** (day 76.1,
night 71.6); granule-level Pearson r between sensor cloud share and mean tcc **0.78** (n 4,337). The tcc-bin curve is
monotone in every season × day/night stratum (e.g. day-summer 0.03 → 0.67 from tcc 0–0.1 to 0.9–1), but the intercept
is high in winter nights (31 % sensor-cloud at tcc < 0.1 — cold/snow surfaces flagged as cloud by the fire algorithm's
night test), so ERA5 tcc < 0.5 overstates winter-night clear looks. Published `firemask_vs_era5.csv` (194 rows:
month × day/night table + tcc-bin curve by season × day/night). Runtime 2 min on 6 workers. Nothing committed;
`_common.py` (Builder A) was imported for meta/log only; 01/02 untouched.

## Builder C log

**2026-10-22 — tests H1, H2, H3, H8, H7 run (`scripts/analysis/05_recall_h1.py` … `09_transfer_h7.py`, shared helpers in
`_detect.py`).** Results in `data/derived/results/h{1,2,3,7,8}_*` (strata / oblast-year / month level only; no coordinates, no
event ids), figures in `figures/` with `figures/CAPTIONS.md` (all **confirmatory**), models in `data/interim/analysis/models/`,
event-level tables `events_detect.parquet` and `events_detect_noSNPP.parquet` in `data/interim/analysis/` (gitignored).
Total runtime ≈ 2.5 min (05: 6 s, 06: 16 s, 07: 9 s, 08: 52 s, 09: 68 s); seed 20261014 throughout. Nothing committed.
*Operationalisation (stated in every meta):* detected = ≥1 fire (N/N20/N21, conf n/h, any type) within 1,000 m (EPSG:3035,
cKDTree) and `acq_ts_utc` in [date 00:00Z − 12 h, date 24:00Z + 12 h]. Covariates = `overpasses_r6` rows of the event's
h3_r6 in that window: min/mean tcc, any snow (sde ≥ 1 cm), n overpasses (mean 19.6), n clear, share night ("Both" granules
by UTC hour 20–04), mean `hours_since_prev` with the sentinel values (≤ 0 or > 1000 h; the first overpass of a cell carries
−2.6e15) dropped. H1 day/night: night = ≥ 1 clear *night* overpass in the window, day = none; under this definition the worst
stratum's "day" is automatic (no clear look at all), so a sensitivity `stratum_alt` uses the day/night flag of the
lowest-tcc overpass. 24 events (8 test) sit in border cells with no overpass rows (cell centroid outside Ukraine and the
Russia buffer): kept in H1 as stratum `no_overpass`, dropped from H2. `event_id` is not unique (two Bellingcat ids, CIV1151
and CIV1553, appear twice with different coordinates) — all joins key on the row index `uid`. Primary H1/H2 = V-test, all
event types (PREREG); all-V, train and a restricted set (strike+shelling+infrastructure+vehicle_loss) reported alongside.
*H1 — supported.* V-test overall recall **5.0 %** (737/14,736; Wilson 4.7–5.4 %). best 7.4 % (252/3,389; 6.6–8.4), worst
**0.06 %** (2/3,147; 0.02–0.23), other 5.8 %. Ratio **117** (bootstrap 2.5th pct 44; upper bound unbounded because 13.5 % of
draws have zero worst-stratum detections; 100 % of draws ≥ 3). stratum_alt: best 8.1 %, worst 0.08 %, ratio 99 (lower 29).
Restricted set: 4.6 %, ratio 86 (lower 32). All V: 6.6 %, best 12.5 % / worst 0.73 %, ratio 17 (13.4–22.8). By type (test):
other 6.5, strike 5.5, vehicle_loss 3.8, aircraft_loss 3.3, infrastructure 3.3, shelling 1.9 %. Season × day/night (test):
summer-night 7.9, summer-day 4.6, winter-night 5.6, winter-day 0.4 %. Both PREREG criteria hold; the headline is that FIRMS
sees one event in twenty, and essentially none under winter cloud.
*H2 — not supported (AUC 0.737 < 0.75), above the 0.65 bounds-only trigger.* Logistic on train 31,124 / test 14,728: AUC
**0.737** (bootstrap 0.724–0.749), train 0.790, pseudo-R² 0.15, Brier 0.049 (base rate test 5.0 %, train 7.3 %). LightGBM
0.727 (0.711–0.743), train 0.903 (overfits). Restricted set: logit 0.748 (0.732–0.763), LGBM 0.734. Largest coefficients
(odds ratios): month=1 0.03, month=12 0.20, month=11 0.21, month=2 0.39, month=10 0.42, month=7 1.84 (all vs the modal month, March); landcover water 0.19, cropland 0.24, grassland 0.40, tree_cover 0.61 (vs built_up); **min_tcc 0.42 per
SD** (z = −18, the strongest single term); hours_since_prev and share_night small. LightGBM gain: min_tcc 28 %, hours_since_
prev 26 %, month 25 %, land cover 9 %. Calibration is good to the 8th decile and over-predicts in the top decile (mean 0.25
predicted vs 0.07 observed) — month effects learned on train months extrapolate poorly to the held-out months. Since AUC is
in [0.65, 0.75), H6b proceeds with the corrected index as a point product, flagged as below the pre-stated bar.
*H3 — supported.* S-NPP → NOAA-20: 259,247 S-NPP detections in overpass cells, 200,000 sampled, 125,731 with a NOAA-20 pass
of the same cell 30–70 min away, **82,247** with tcc < 0.3 on that pass; concordance **53.6 %** (53.3–54.0). Strata:
summer-night 65.1, winter-night 62.0, summer-day 49.2, winter-day 46.9 % — all four inside 40–70. Reverse NOAA-20 → S-NPP
52.4 % (52.0–52.7), same ordering. Concordance falls with tcc even below 0.3 (55.7 → 43.1 %) and rises with FRP ≥ 10 MW (59 %).
Pair = nearest qualifying pass per direction; concordant = target detection within 1 km with acq_ts in [pass start − 10 min,
start + 16 min].
*H8 — descriptive.* Without S-NPP (N20+N21 only in fires and overpasses): V-test recall 5.00 → **4.32 %**, Δ −0.69 pp (cell
block-bootstrap −0.92 to −0.48), i.e. −14 % relative; winter Nov–Feb Δ −0.09 pp (0.52 → 0.43 %), winter Nov–Apr −0.41 pp,
summer −1.00 pp, north-east −0.58 pp. The PREREG "10–25 pp in winter" cannot be met at a 0.5 % winter baseline; relative
drop 14–17 %. Best/worst ratio under the reduced constellation 202. Blind season: C1 cell-day 25th percentile of
opportunity is **0** (44 % of cell-days have no clear overpass), so "below" is empty and blind = median daily opportunity
≤ 0; blind ISO weeks per cell-year: Ukraine 20.9 → **22.2 (+1.23, CI 1.22–1.24)**, north-east 20.8 → 21.9 (+1.09, 1.07–1.11);
by year, +2.37 (2022, NOAA-20 alone left), +1.45 (2023), +0.57 (2024), +0.53 (2025); NE +2.34 / +1.20 / +0.46 / +0.36.
The "≥ 2 weeks in the NE" prediction holds only for the two-satellite 2022 configuration, not pooled. Published tables:
oblast × year (`h8_blind_season_oblast_year.csv`), national/NE weekly blind share, recall deltas.
*H7 — filed.* `predictions/transfer_v1.json` (written 2026-10-22T22:52Z, model sha256 4094506d…): Karabakh 2020
predicted recall **3.0 %** (90 % 2.3–3.9; local land-cover sensitivity 2.2 %), Sudan 2023–25 **11.3 %** (10.6–12.2;
grass/bare sensitivity 8.1 %). Method: 20,000 synthetic strike events per case = (ERA5 grid point in AOI, day in window) with
the overpass pattern of a random Ukraine event window (S-NPP rows only for Karabakh; all three satellites and same calendar
year for Sudan), UTC times shifted by the longitude difference, ERA5 tcc at the nearest hour, ERA5-Land snow that day,
Ukraine strike land-cover mix, month = synthetic date. Karabakh: mean min tcc 0.15, 7.1 overpasses/48 h, mean gap 5.8 h,
Oct/Nov month effects pull it down; Sudan: min tcc 0.06, 20.9 overpasses, Jul peak 24 %, Nov–Jan 4–6 %. Sudan 2025 ERA5
had arrived, so all three years were used (no fallback). Caveats in the JSON: the interval covers coefficient uncertainty
only; the H7 test defines Karabakh realised recall at 5 km / ±2 days, a looser rule than the 1 km / 48 h used here, so the
±15 pp comparison should be read with that in mind. ERA5 for the AOIs was fetched by the lead's poller (not by me);
`data/manifest_parts/observability-era5.json` shows modified in git from that poller, not from these scripts.
*Not done / open:* no committing (lead's call); no DEVIATIONS entry written — the H8 "below the 25th percentile" wording and
the H7 1 km-vs-5 km definition mismatch may deserve one, lead to decide.
