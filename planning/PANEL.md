# C1 panel build and tests (H4, H5, H6/H6b, H9–H14, robustness) — contract

Spec is PREREG.md §3–§5 (fixed) and DESIGN.md D3–D8, D12, D13. This file fixes file names, schemas and order.
Written 2026-10-22 after `prereg-v1` and `transfer-v1`. **This is the first time wartime control data (VIINA, C1
dates) is joined to fires.** Nothing here may be re-specified after seeing a result; exploratory extras are labelled.

Run with `~/D3/Frontline_From_Space/.venv/bin/python -I` from the repo root. Scripts in `scripts/analysis/` numbered
from 10. Meta JSON beside every output (`scripts/analysis/_common.py`). Published outputs (`data/derived/`) are
cell-week or coarser with a ≥7-day lag; cell-week tables may be published (PREREG §7 allows cell-week), but no
point-level fire or control geometry, and no DeepState/ISW geometry. VIINA derivatives carry an ODbL attribution line
in their meta.

## Inputs
| What | Path | Notes |
|---|---|---|
| VIINA daily control | `data/raw/viina/control_latest_{2022..2026}.zip` (one CSV each: geonameid, date YYYYMMDD, status_wiki/boost/dsm/isw, status) | majority `status` ∈ {UA, RU, CONTESTED}; 2022 file starts 2022-02-24 |
| VIINA tessellation | `data/raw/viina/gn_UA_tess.geojson` | 33,141 settlements (points + attributes); Voronoi is **ours**, clipped to Ukraine ADM0 incl. Crimea; working code in `scripts/prereg_constants.py` (Voronoi, weekly modal status, RU|UA shared edges, front cells) — reuse it |
| Fires | `data/interim/analysis/fires.parquet` (2022–25, N/N20/N21, conf n/h), `fires_baseline.parquet` (2012–21 S-NPP) | |
| Opportunity | `data/interim/analysis/opportunity_r6_day.parquet`; published `data/derived/observability/opportunity_r5_week.csv.gz` | |
| H2 model | `data/interim/analysis/models/` (logit v1, sha256 in `predictions/transfer_v1.json`) | for the corrected index |
| Constants | `data/derived/prereg_constants.json` | SESOI 1.70 (10 km 2.31, 25 km 1.06, 1-wk 0.65); FRP p75 by season × day/night; H13 cutoff 16.33 |
| Kyiv city | geoBoundaries ADM1 feature `shapeName == "Kyiv"` | H12 |
| Telegram Kyiv series | `data/derived/telegram/kyiv_strikes_week.csv` | H12 cross-check (exploratory) |
| Deep strikes | `data/raw/militarnyi/strikes_en.json`, `data/raw/saltan2026_deepstrikes/` | H13 descriptive cross-check only |

## Builder D — panel (`10_control_weekly.py`, `11_panel_r5_week.py`)
1. `10_control_weekly.py` → `data/interim/analysis/control_weekly.parquet`: settlement × ISO week (Mon–Sun) modal
   `status` (ties → status on the latest day, as in prereg_constants.py), for all weeks 2022-02-21 → latest 2026 week;
   plus the same for `status_dsm`, `status_isw`, `status_wiki` (robustness 5). Voronoi area km² per settlement
   (EPSG:3035) saved once in `voronoi_area.parquet` (geonameid, area_km2, h3_r5 of the settlement point, h3_r6).
   Weekly RU|UA control line = shared Voronoi edges between RU and UA settlements (CONTESTED counts as neither side
   for the line; its area is reported separately). Front flags per res-5 cell × week at 10/15/25 km (centroid to line).
2. `11_panel_r5_week.py` → `data/interim/analysis/panel_r5_week.parquet` and published
   `data/derived/panel/panel_r5_week.csv.gz` (same columns, no geometry). One row per H3 res-5 cell × ISO week,
   2022-02-21 → 2025-12-31 (C1 flag for 2022-04-03 → 2024-07-07, E flag for 2024-07-08 → 2025-12-31). Columns:
   - control: `ru_km2, ua_km2, contested_km2, net_ru_gain_km2` (= ru_km2(t) − ru_km2(t−1), positive = RU gain),
     `net_fwd_1..4` (sum of net over t+1..t+k), `net_lag_1..4`; same with `_dsm/_isw/_wiki` suffixes for ru_km2 and net.
   - geometry flags: `front_10, front_15, front_25` (bool), `dist_to_line_km`, `side` ∈ {UA, RU, mixed} by majority
     area, `rear_strip` (50–90 km from the line, robustness 2), `oblast_iso` (majority area), `in_ukraine`.
   - fires (all satellites unless suffixed): `fires, fires_night, fires_day, fires_snpp, frp_sum, fires_big, fires_small`
     (season × day/night p75 cutoffs from constants), `fires_big_ua_side, fires_small_ua_side, fires_big_ru_side,
     fires_small_ru_side` (side = control status of the Voronoi polygon the fire falls in that week; CONTESTED → own
     column `fires_contested`), `fires_deep_ru` (H13: fires ≥16.33 MW in RU-held Ukrainian territory or in Russia
     >30 km from the line; Russia cells come from fires.parquet's Russian rows, assign to res-5 cells outside Ukraine).
   - baseline (H5): `base_fires_mean` = mean same-ISO-week fire count 2012–2021 in the cell (S-NPP only, so also give
     `fires_snpp` for a like-for-like ratio), `base_fires_sd`.
   - observability: `opportunity, n_overpasses, n_clear, share_zero_days` from the res-6 cell-days in the res-5 cell
     (sum over child cells and days), plus cell-week means of the H2 covariates (`min_tcc_mean, snow_share,
     hours_since_prev_mean, share_night, landcover_mode`) so the logit can be scored per cell-week.
   - `week_start, iso_year, iso_week, season` (summer May–Oct), `phase` (A/B/E/none).
   Also `panel_r6_week.parquet` (robustness 7) with the control and fire columns only.
3. `12_national_kyiv_week.py` → `data/derived/panel/national_week.csv`: ISO week × national `ru_km2, net_ru_gain_km2`,
   `kyiv_fires` (detections inside the Kyiv city polygon, conf n/h), `kyiv_fires_night`, `kyiv_opportunity`,
   joined to `kyiv_strikes_week.csv` columns (prefixed `tg_`), and Air Force national launched totals from
   `data/derived/telegram/national_night.csv` summed per week (prefixed `af_`).
4. Report: cells × weeks, front-cell counts per week (median, by year), national RU km² path (sanity: 2022-04 ≈ Mar
   2022 peak ~ 120–130k km² incl. Crimea+Donbas; check against the Economist national series in
   `data/raw/economist/keep/areas_of_control_daily_summary.csv` for 2022–23 as PREREG robustness 5 allows), fires per
   front cell-week by phase, share of cell-weeks with net ≠ 0. Append a dated "Builder D log" to this file.

## Builder E — tests (`13_h5_h14_descriptive.py`, `14_h4_blindspot.py`, `15_h6_lead.py`, `16_h9_h11.py`, `17_h12_kyiv.py`, `18_h13_deep.py`, `19_robustness.py`)
- Inference exactly as PREREG H6: two-way FE (cell, week) via `pyfixest.feols`, CRV1 by cell with wild-cluster bootstrap
  (Webb weights, 9,999 draws, seed 20261014; pyfixest `wildboottest` or `wildboottest` package), AND Driscoll–Kraay
  lag 4 (`linearmodels.PanelOLS` with `cov_type="kernel"`, bandwidth 4). "Significant" needs p < 0.05 under both.
  Equivalence = 90% CI within ±SESOI (band-specific SESOI for 10/25 km; 0.65 for 1-week outcomes).
- Sample for H6/H9–H11: C1 cell-weeks with `front_15` (robustness: 10/25). Outcome `net_fwd_4`. Regressor
  `log1p(fires)`; momentum `net_lag_1..4`; `opportunity`. H6b: the corrected index `fires / P(detect)` where P(detect)
  is the H2 logit scored on the cell-week covariates (clip P at 0.02 and state it), with a 90% interval from 1,000
  coefficient draws propagated to β (report β's interval as the union of the 5th/95th across draws).
- H4: gate regression first; then share of C1 RU km² gained (sum of positive net over front cells) that falls in
  cell-weeks in the bottom quartile of `opportunity`, cell block-bootstrap 2,000 draws.
- H5: monthly ratio front-cell `fires_snpp` density to `base_fires_mean`, ≥3× in ≥9 of 12 months, cell block-bootstrap.
- H9: distributed leads 0,1,2,3,4,6,8 weeks (outcome `net` at t+k, one regression per k, or joint — do both, say which is
  primary: joint per PREREG wording "separate β").
- H10: four fire terms (big/small × side) together. H11: phase interaction A/B; H11s season interaction within phase.
- H12: national weekly `net_ru_gain_km2` on `kyiv_fires` at leads/lags −4…+4, week-of-year FE, 4 outcome lags, Newey–West;
  SESOI scaled to national = SESOI × median number of front cells per week (state the number). Season interaction.
  Cross-check columns `tg_*`, `af_*` (exploratory).
- H13 (exploratory, E period): `net_fwd_4` on `log1p(fires_deep_ru)` with the H6 controls; equivalence.
- H14: baseline B, 5th-percentile FRP by month × day/night, bootstrap CIs; summer-day ≥ 1.5 × winter-night; re-check on
  V events using `data/interim/analysis/events_detect.parquet` (FRP of the matched fire vs the nearest missed-nearby).
- Robustness list PREREG §5, items 1–7, each as one table row per hypothesis it applies to.
- Outputs `data/derived/results/h{4,5,6,9,10,11,12,13,14}_*.{csv,json}`, `robustness.csv`, figures + CAPTIONS.md
  (**confirmatory** / **exploratory** on every caption). Verdict per hypothesis against the pre-stated criterion and
  against Jackson's prediction, in `data/derived/results/verdicts.json`. Append a dated "Builder E log" here.

## Conventions
Seed 20261014. ISO weeks Monday-start. EPSG:3035 for area and distance. Positive net = Russian gain. Report km².
Any ambiguity: resolve, state it in the meta and the log, do not change the hypothesis.
