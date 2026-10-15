# Pre-registration — Front line from space

**Version:** v1 DRAFT, 2026-10-14 · **Derived from:** `DESIGN.md` · **Status:** awaiting Jackson's sign-off. Not committed, not tagged.
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
| **C1 (confirmatory)** | 2022-04-03 → 2024-07-07 | S-NPP + NOAA-20 (+NOAA-21 from 2023-03); DeepState API → ISW → Economist summary, in that order of availability | **Untouched** | H4, H5, H6 |
| **T1** | 2020-09-27 → 2020-11-10, Karabakh AOI | S-NPP Azerbaijan + Armenia 2020; dated settlement captures | **Untouched** | H7 |
| **T2** | 2023-04-15 → 2025-12-31, Darfur + Kordofan | S-NPP Sudan 2023–25; UCDP GED | **Untouched** | H7 |

## 3. Fixed definitions

- **Grid:** H3 resolution 5 for the panel; resolution 6 for the detection model.
- **Control line:** weekly median of the daily control polygon boundary. **Front cells:** centroid within 15 km of the line (10 km and 25 km as robustness).
- **Fire:** VIIRS 375 m detection, confidence nominal or high, any `type`, any satellite; `daynight` and `satellite` retained.
- **Event (V):** a GeoConfirmed or Bellingcat record with date and coordinates. **Detected** = at least one fire within 1 km and within −12/+12 h of the event date's overpass window.
- **Detection opportunity (cell-day):** Σ over overpasses of [swath covers cell] × [ERA5 tcc at overpass hour < 0.5] × [snow depth < 1 cm]. Aggregated to cell-week by sum.
- **Outcome (C1):** net km² of the cell that changed from Ukrainian to Russian control (negative if reverse) per ISO week.
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
- SESOI: β = 2.9 km² per log-unit (a doubling of fires ⇒ ≥ 2 km² additional 4-week gain).
- Outcomes: (i) supported if significant and β ≥ 2.9; (ii) **equivalence** if the 90% CI lies within ±2.9; (iii) inconclusive otherwise.
- **H6b:** the same specification with the observability-corrected fire index (D12) in place of raw fires. Reported alongside; a change in category between H6 and H6b is a headline result.
- **Prediction:** (ii) or (iii) for both.

**H7 Transfer.** Before T1/T2 download, the H2 model fit on Ukraine produces predicted recall for Karabakh (Oct–Nov 2020, mountain, autumn) and Sudan (Darfur/Kordofan, arid). Filed in `predictions/transfer_v1.json` with timestamp.
- Test: realised recall against UCDP GED (Sudan) and dated settlement captures (Karabakh, detection within 5 km / ±2 days) is within ±15 pp of predicted.
- **Prediction:** within band for Sudan (predicted high recall); Karabakh within band but lower.

**H8 Constellation loss.** Recomputed recall (H1) and blind-season length (months with median opportunity below the C1 25th percentile) with S-NPP removed.
- Descriptive with CIs; no success criterion. **Prediction:** recall falls by 10–25 pp in winter; blind season lengthens by ≥2 weeks in the north-east.

## 5. Robustness (fixed list; no additions)

1. Front band 10 km and 25 km. 2. Rear-strip reference instead of pre-war baseline. 3. Night-only fires. 4. Drop-one-oblast jackknife. 5. ISW or Economist control in place of DeepState, same spec. 6. Reverse direction (area → fires) and lead-2 placebo. 7. H3 res 6 panel.

## 6. Exploratory (labelled as such everywhere)

Manoeuvre-phase interaction (Kharkiv/Kherson 2022); FRP-weighted fires; full occupancy/N-mixture model; VNP14IMG class decomposition beyond the sample; forecast-skill comparison (LightGBM vs momentum).

## 7. Rules

No hypotheses added after the tag. Deviations in `DEVIATIONS.md`, dated. Every figure caption marked **confirmatory** or **exploratory**. Publication at cell-week or coarser with ≥7-day lag; no point-level front detections; no DeepState/ISW geometry redistributed.

## 8. Sign-off (Jackson)

- [ ] SESOI 2.9 km²/log-unit accepted (≈ half the mean 4-week change in E)
- [ ] H1 threshold "recall < 50%" and "3× ratio" accepted
- [ ] H3 band 40–70% accepted
- [ ] Register on OSF (recommended; before Fri Oct 16 15:00 UTC maintenance or after Mon Oct 19)
- [ ] "I approve this as prereg-v1." ______  Date: ______
