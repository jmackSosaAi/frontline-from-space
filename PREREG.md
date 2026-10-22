# Pre-registration — Front line from space

**Version:** v1 DRAFT, 2026-10-14, revised 2026-10-21 (VIINA control source; H9–H13 added) · **Derived from:** `DESIGN.md` · **Status:** signed by Jackson Mackney 2026-10-22; tagged `prereg-v1`.
**Gate:** no wartime data for C1, T1 or T2 (defined below) is downloaded before this file is committed and tagged `prereg-v1` and registered on OSF (project https://osf.io/3whtz/). Download timestamps are logged in `data/MANIFEST.json`.

## 1. Question

How reliable a witness is NASA FIRMS (VIIRS 375 m active fire) to a ground war, and what does accounting for its blind spots change about what it can tell an analyst? Ukraine 2022–2025 is the test case; Nagorno-Karabakh 2020 and Sudan 2023– are out-of-sample transfer checks.

## 2. Data and the exploratory/confirmatory split

| Set | Period | Sources | Status at tag | Role |
|---|---|---|---|---|
| B (baseline) | 2012–2021 Ukraine; 2012–2019 Azerbaijan/Armenia; 2012–2022 Sudan | VIIRS S-NPP yearly country files | Downloaded (Ukraine, Caucasus); Sudan allowed pre-tag | Definitions; pre-war reference |
| E (exploratory) | 2024-07-08 → 2025-12-31 | S-NPP; DeepState mirror | Analysed (~10 specs) | Pipeline; no confirmatory claims |
| V (validation events) | 2022-02-24 → 2025 | GeoConfirmed; Bellingcat TimeMap | Allowed pre-tag | Recall and detection model; split by calendar month 70/30 train/test, months drawn by seeded RNG (seed 20261014) |
| O (observability) | 2022 → 2025 | CMR granule footprints; ERA5 tcc; ERA5-Land snow; VNP14IMG/VJ114IMG sample | Allowed pre-tag | Covariates |
| **C1 (confirmatory)** | 2022-04-03 → 2024-07-07 | S-NPP + NOAA-20 (+NOAA-21 from 2023-03); **VIINA** daily settlement control (Zhukov, ODbL; majority-vote `status`) | **Untouched** | H4, H5, H6, H9–H12 |
| **T1** | 2020-09-27 → 2020-11-10, Karabakh AOI | S-NPP Azerbaijan + Armenia 2020; dated settlement captures | **Untouched** | H7 |
| **T2** | 2023-04-15 → 2025-12-31, Darfur + Kordofan | S-NPP Sudan 2023–25; UCDP GED | **Untouched** | H7 |

**Disclosure (pre-tag):** a snapshot of The Economist war-fire repo (commit `8b431f9`, fetched 2026-10-14, logged in `data/MANIFEST.json`) is on disk and includes files covering C1 dates (`ukraine_war_fires.csv`, `control_status_of_fires_II.csv`, `areas_of_control_daily_summary.csv`, `war_fires_by_ADM3.csv`). They have not been used in any analysis. Before the tag, only 2025 VIINA and E-period FIRMS were used to fix the constants in §3. Validation-event sets (V) that span C1 dates (e.g. Militarnyi strikes, air-raid sirens) were downloaded pre-tag as allowed, and have not been joined to fires.

## 3. Fixed definitions

- **Grid:** H3 resolution 5 for the panel; resolution 6 for the detection model.
- **Control source:** VIINA (github.com/zhukovyuri/VIINA), daily control status of ~33k GeoNames settlements, majority-vote `status`. DeepStateMap declined API permission (2026-10); ISW geodata requires written consent (requested, unanswered). Each settlement gets a Voronoi (Thiessen) polygon clipped to Ukraine's border, so control is expressed in km².
- **Control line:** each week, the boundary between Voronoi polygons of Russian-controlled and Ukrainian-controlled settlements (weekly modal status per settlement). **Front cells:** centroid within 15 km of the line (10 km and 25 km as robustness).
- **Fire:** VIIRS 375 m detection, confidence nominal or high, any `type`, any satellite; `daynight` and `satellite` retained.
- **Event (V):** a GeoConfirmed or Bellingcat record with date and coordinates. **Detected** = at least one fire within 1 km and within −12/+12 h of the event date's overpass window.
- **Detection opportunity (cell-day):** Σ over overpasses of [swath covers cell] × [ERA5 tcc at overpass hour < 0.5] × [snow depth < 1 cm]. Aggregated to cell-week by sum.
- **Outcome (C1):** net km² of settlement-Voronoi area in the cell that changed from Ukrainian to Russian control (negative if reverse) per ISO week.
- **SESOI (fixed 2026-10-22):** **1.70 km²** per log-unit = half the mean absolute 4-week change of front cell-weeks (3.41 km²; n = 6,028 cell-weeks, 143 H3 res-5 cells) on VIINA 2025 (inside E, not C1). Replaces the earlier DeepState-sector value of 2.9, which was on a different unit. Sensitivity: 10 km band 2.31, 25 km band 1.06, 1-week horizon 0.65 (used for H9's ≥2-week equivalence on the 1-week outcome). Script: `scripts/prereg_constants.py`; output `data/derived/prereg_constants.json`.
- **Big / small fire:** FRP at or above / below the 75th percentile of front-cell FRP in E, computed separately for each season × day/night cell (so a seasonal shift in the detection floor, H14, cannot masquerade as a change in fire size). Fixed 2026-10-22 (MW, S-NPP E-period front-cell fires, confidence n/h): summer day **11.20** (n 22,638), summer night **1.72** (n 9,140), winter day **10.60** (n 1,346), winter night **2.03** (n 334, thinnest stratum). For NOAA-20/21 the same cutoffs are applied.
- **Phases (fixed by date):** A, manoeuvre = 2022-04-03 → 2022-11-30; B, attrition = 2022-12-01 → 2024-07-07. Summer = May–Oct, winter = Nov–Apr.
- **Kyiv fires:** detections inside Kyiv city's administrative boundary, all confidence ≥ nominal, summed per ISO week.
- **Momentum:** outcome lags 1–4.

## 4. Hypotheses, tests, and pre-stated predictions

**H1 Recall.** Overall recall of FIRMS against V-test events is below 50%, and recall in the best condition stratum (clear, night, Jun–Sep) is at least 3× recall in the worst (tcc ≥ 0.5 or snow, day, Nov–Feb).
- Test: stratified recall with Wilson 95% CIs; ratio with bootstrap CI (1,000 draws over events).
- Supported if both hold; otherwise reported as is. **Prediction:** supported.

**H2 Detection model.** A logistic model of detection on {tcc at overpass, snow flag, hours since last overpass, day/night, land-cover class, event type, month} achieves AUC ≥ 0.75 on V-test.
- Also fit LightGBM with the same features; report both. Primary is logistic.
- **Prediction:** supported (AUC 0.75–0.85). If AUC < 0.65, the corrected index (H6b) is reported as bounds only.

**H3 Paired looks.** For S-NPP detections with a NOAA-20 overpass covering the same cell within 30–70 minutes under tcc < 0.3, the share with a NOAA-20 detection within 1 km is between 40% and 70%.
- Test: concordance share with Wilson CI, by season and day/night.
- **Prediction:** inside the band. Outside either way is reported.

**H4 Blind spot.** ≥30% of total km² gained by Russia in C1 falls in cell-weeks in the bottom quartile of detection opportunity.
- Validation gate first: regression of log(1+fires) on opportunity with cell FE and week-of-year FE has coefficient > 0, p < 0.01. If the gate fails, H4 is "not testable with this product."
- Test: share with cell block-bootstrap CI (2,000 draws). Supported if CI excludes 30% from below.
- **Prediction:** supported.

**H5 Location (calibration).** Front-cell fire density is ≥3× the same cells' 2012–2021 same-ISO-week baseline in ≥9 of 12 calendar months of C1.
- Test: monthly ratio with cell block-bootstrap CI.
- **Prediction:** supported; already published in descriptive form elsewhere.

**H6 Lead (pre-registered null).** Primary specification on C1:
`net_{t+1..t+4} ~ β·log1p(front_fires_t) + Σ_{k=1..4} γ_k·net_{t−k} + δ·opportunity_t | cell FE + week FE`
- Inference: (a) CRV1 by cell with wild-cluster bootstrap (Webb weights, 9,999 draws); (b) Driscoll–Kraay lag 4. "Significant" requires p < 0.05 under both.
- SESOI: β = 1.70 km² per log-unit (a doubling of fires ⇒ ≈ 1.2 km² additional 4-week gain).
- Outcomes: (i) supported if significant and β ≥ SESOI; (ii) **equivalence** if the 90% CI lies within ±SESOI; (iii) inconclusive otherwise.
- **H6b:** the same specification with the observability-corrected fire index (D12) in place of raw fires. Reported alongside; a change in category between H6 and H6b is a headline result.
- **Prediction:** (ii) or (iii) for both.

**H7 Transfer.** Before T1/T2 download, the H2 model fit on Ukraine produces predicted recall for Karabakh (Oct–Nov 2020, mountain, autumn) and Sudan (Darfur/Kordofan, arid). Filed in `predictions/transfer_v1.json` with timestamp.
- Test: realised recall against UCDP GED (Sudan) and dated settlement captures (Karabakh, detection within 5 km / ±2 days) is within ±15 pp of predicted.
- **Prediction:** within band for Sudan (predicted high recall); Karabakh within band but lower.

**H8 Constellation loss.** Recomputed recall (H1) and blind-season length (months with median opportunity below the C1 25th percentile) with S-NPP removed.
- Descriptive with CIs; no success criterion. **Prediction:** recall falls by 10–25 pp in winter; blind season lengthens by ≥2 weeks in the north-east.


### Jackson's directional predictions (added 2026-10-21, before tag)

**H9 Lead time.** Strikes and front-line gains happen almost together. In a distributed-lead version of H6 (separate β for the same week and for leads of 1, 2, 3, 4, 6 and 8 weeks), the largest positive β is at 0 or 1 week, and β at 2+ weeks is within ±SESOI.
- Test: same FE and inference as H6. Supported if the peak β is at 0–1 week and significant under both inference methods, and leads ≥2 weeks pass the equivalence test. **Prediction:** supported (any lead is ≤1 week). The same-week term is descriptive (co-movement, not a lead).

**H10 Fire size tells you whose fire it is.** Split front-cell fires into big and small (FRP threshold in §3) and by side of the line. (a) Big fires on the Ukrainian-held side → more Russian gain over t+1…t+3. (b) Small fires on the Russian-held side (Ukraine hitting vehicles and equipment) → less Russian gain.
- Test: H6 specification with the four fire terms (big/small × side) entered together. **Prediction:** (a) β > 0, (b) β < 0, both significant.

**H11 Phase flip.** H6 with a phase interaction: in phase A, more fire → more movement (β_A > 0); in phase B, more fire → less movement (β_B < 0), because heavy fire marks failed attacks.
- Test: β_A > 0 and β_B < 0, and β_A − β_B > 0, each at p < 0.05 under both inference methods. **Prediction:** supported.
- **H11s Summer.** Within each phase, the fire–movement relationship is stronger in summer (May–Oct) than in winter (Nov–Apr): |β_summer| > |β_winter|, interaction p < 0.05. **Prediction:** supported; if H11 shows anything, it shows up in summer.

**H12 Kyiv strikes (open question, no directional prediction).** Are fires in Kyiv timed with Russian advances, opposite to them, or random? Regress national weekly net Russian gain on Kyiv fires at leads and lags −4…+4 weeks, with week-of-year FE and 4 lags of the outcome.
- Report all coefficients with CIs; the answer is "coordinated" (positive), "opposite" (negative) or "no relationship" (every 90% CI within ±SESOI scaled to national level). Loose guess: it depends on the season (season interaction reported). Cross-check with Ukrainian Air Force strike counts if a dataset is obtained. Mechanism (morale vs coordination vs air-defence drain) cannot be separated with these data.

**H14 Seasonal detection floor.** The smallest fires VIIRS reports (5th-percentile FRP of detections) vary by season and day/night: in summer daytime, hot ground hides small fires, so only large ones are detected; at winter night, small fires show up when it's clear.
- Test on pre-war baseline B (Ukraine 2012–2021, no war data needed): 5th-percentile FRP by month × day/night, bootstrap CIs; supported if summer-day floor ≥ 1.5× winter-night floor. Re-checked on V events (FRP of detected vs missed-nearby). **Prediction:** supported. Consequence: H10's big/small cutoff is season-specific (§3).

**H13 Deep strikes (exploratory: the campaign is mostly 2025, after C1).** Big fires from Ukrainian strikes on Russian depots and refineries (Russian-held or Russian territory, >30 km from the line, FRP ≥ **16.33 MW**, the 90th percentile of E-period front-cell fires) have no meaningful effect on Russian gains over t+1…t+4.
- Test on E (2024-07-08 → 2025-12-31): equivalence, 90% CI within ±SESOI. **Prediction:** equivalence (economic damage doesn't slow Russia's war effort). Exploratory label throughout.

## 5. Robustness (fixed list; no additions)

1. Front band 10 km and 25 km. 2. Rear-strip reference instead of pre-war baseline. 3. Night-only fires. 4. Drop-one-oblast jackknife. 5. VIINA's single-source columns (`status_dsm`, `status_isw`, `status_wiki`) in place of the majority `status`, same spec; Economist national area series as a 2022–23 sanity check. 6. Reverse direction (area → fires) and lead-2 placebo. 7. H3 res 6 panel.

## 6. Exploratory (labelled as such everywhere)

FRP-weighted fires beyond H10; full occupancy/N-mixture model; VNP14IMG class decomposition beyond the sample; forecast-skill comparison (LightGBM vs momentum).

## 7. Rules

No hypotheses added after the tag. Deviations in `DEVIATIONS.md`, dated. Every figure caption marked **confirmatory** or **exploratory**. Publication at cell-week or coarser with ≥7-day lag; no point-level front detections; no DeepState/ISW geometry used or redistributed; VIINA derivatives shared under ODbL with attribution.

## 8. Sign-off (Jackson)

- [x] SESOI 1.70 km²/log-unit accepted (half the mean 4-week front-cell change, VIINA 2025)
- [x] H1 threshold "recall < 50%" and "3× ratio" accepted
- [x] H3 band 40–70% accepted
- [x] Register on OSF (recommended; before Fri Oct 16 15:00 UTC maintenance or after Mon Oct 19)
- [x] VIINA as control source and H9–H14 accepted
- [x] "I approve this as prereg-v1." Jackson Mackney  Date: 2026-10-22

Jackson confirmed on 2026-10-22 that no one opened the Economist files downloaded on 2026-10-14.
