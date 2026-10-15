# DESIGN — Front line from space

**Written:** 2026-10-14 · **Owner:** Jackson Mackney · **Ship:** Tue 2026-11-10 · **Budget:** $0
**Supersedes:** `planning/plan_draft_{ship,rigor,novelty}.md` (kept for reference). `PREREG.md` is derived from this file.

## 0. The question

> How reliable a witness is a free thermal satellite feed (NASA FIRMS, VIIRS) to a ground war, and what does an honest accounting of its blind spots change about what it can tell an analyst?

Every published use of FIRMS in war (Bellingcat 2022, The Economist's war-fire model, Tomchenko 2023, Dingemanse et al. 2026) treats the sensor as a reliable witness: a detection is a fire, a zero is no fire. None measures how often the sensor misses a real event, or separates "looked and saw nothing" from "could not look." This project measures that, corrects for it, and then re-asks the question those studies asked.

**The arc: measure → correct → infer → transfer.** Ukraine is the test case. The product is about the sensor.

**Not the question:** predicting Russian advances. The feasibility pass (`Conflict_Data_Feasibility/frontline/VERDICT.md`) showed fires add ~0.5 pp of explained variance over momentum; that result is kept as a pre-registered null, not a pitch.

## 1. Design decisions

Each row: the choice, the alternatives, the reason. Changes from the Oct-13 drafts are marked **[changed]**.

| # | Decision | Choice | Rejected | Why |
|---|---|---|---|---|
| D1 | Framing | Sensor-first: FIRMS as the thing measured | Ukraine-first; forecasting | Transfers to any war; survives a null; addresses "too Ukraine-specific" in the title |
| D2 | Primary outcome (what fires are compared to) | **Two outcomes [changed]:** (a) confirmed geolocated events (GeoConfirmed, Bellingcat TimeMap) for the recall/detection model; (b) territorial change (km²/cell-week) for the lead-lag test | Oryx losses (no coordinates); strike datasets alone | (a) needs no permission and directly measures the sensor; (b) is the question prior work asked |
| D3 | Spatial unit | **H3 hex grid, res 5 (~250 km²) for the panel; res 6 (~36 km²) for the recall model and hot sectors [changed]** | 22 fixed 50 km sectors | Fixed sectors break when the line moves 2022→2024; hexes are line-independent and allow finer resolution where data are dense |
| D4 | Temporal unit | Week (ISO) for the panel; day for event studies and the recall model | Daily panel | DeepState updates in batches; weekly matches the outcome's true resolution |
| D5 | "Front" definition | Cells whose centroid is within 15 km of the weekly-median control line; 10/25 km as robustness | Fixed sectors | Same rule for every week and every war |
| D6 | Reference for "normal" fire | **Same-cell pre-war baseline, 2012–2021 VIIRS, same ISO week [changed]**; stratified by land cover | Rear strip 50–90 km (feasibility pass) | Rear strip is contaminated by strikes and agriculture; the pre-war baseline is what the Economist used and is already downloaded |
| D7 | Fire definition | All VIIRS 375 m detections, nominal+high confidence, day+night, **all three satellites (S-NPP, NOAA-20, NOAA-21) [changed]**; `type` 0–3 kept and tagged | S-NPP only; vegetation-only | NOAA-21 SP exists from 2023-03 (verified today); urban combat produces type≠0 detections |
| D8 | Control-map sources | DeepState history API (primary, permission requested 2026-10-14); ISW/CTP timelapse (cross-check, permission requested); **Economist `areas_of_control_daily_summary.csv` (CC BY 4.0, 2022-02→2023-11) as the guaranteed floor [changed]** | ISW-only; Liveuamap (paid, scraping forbidden); ACLED (EULA) | Both polygon sources are permission-gated; the Economist file cannot be blocked |
| D9 | Observability (the novel product) | **Three tiers:** (1) overpass count from granule footprints (CMR/LAADS metadata); (2) ERA5 `tcc` at overpass hour + ERA5-Land snow depth; (3) **VNP14IMG/VJ114IMG fire-mask classes (cloud / not-processed / clear-no-fire) on a stratified granule sample [changed: promoted from stretch to core]** | GEE (account + learning curve); Economist cloud series alone (black box) | Tier 3 is the sensor's own cloud decision; nobody has used it; LAADS access is set up |
| D10 | Detection model | Logistic/GBM model of P(FIRMS detection within 1 km & ±12 h of a confirmed event) on: cloud at overpass, hours since last overpass, day/night, land cover, snow, FRP-relevant fuel, event type | Occupancy model (full) | Logistic first; N-mixture/occupancy as exploratory if time allows |
| D11 | Paired-look test | NOAA-20 leads S-NPP by ~50 min in the same orbit plane: for each S-NPP detection, was there a NOAA-20 detection within 1 km on the paired pass, and vice versa? | — | Direct measurement of detection stochasticity, no ground truth needed; nearly free |
| D12 | Corrected index | Observability-adjusted expected fire count per cell-week with a 90% interval: `fires_raw / P(detect)` with propagation of model uncertainty | Raw counts only | Turns the blind-spot map into a usable product |
| D13 | Inference for the lead-lag test | Two-way FE (cell, week), 4 momentum lags, opportunity covariate; CRV by cell with wild-cluster bootstrap **and** Driscoll–Kraay(4); TOST equivalence; run on raw and corrected fires | Single SE; no equivalence | A null must be a bounded claim |
| D14 | Transfer cases | Nagorno-Karabakh 2020 (manoeuvre war, S-NPP only) and **Sudan 2023– (arid, raiding) [changed: added]**, both as out-of-sample predictions of the detection model filed before download | Myanmar, Sahel, Ethiopia | Two contrasting climates test whether the detection model is a sensor model or a Ukraine model |
| D15 | S-NPP shutdown (≈1–2 Nov 2026) | Quantify constellation loss: recall and blind-season with and without S-NPP | Ignore | Timely, concrete, falls out of D10 |
| D16 | Publication unit | Cell-week or coarser, ≥7-day lag; no point-level front detections; no DeepState/ISW geometry redistributed | Point-level | OPSEC and licence (see `planning/scout_risks_ethics.md`) |
| D17 | Pre-registration | Git tag `prereg-v1` + OSF registration (private project https://osf.io/3whtz/ exists) | Tag only | External timestamp |
| D18 | Stack | Python 3.12, DuckDB, GeoPandas, h3-py, pyfixest + linearmodels (DK), statsmodels, LightGBM, rasterio/xarray for ERA5 & granules, Quarto → HTML+PDF, static MapLibre dashboard, GitHub Actions, Zenodo | R, Streamlit, GEE | No build step, interviewer can read the source |
| D19 | Cut | "Predict advances" framing; air-defense side note; dashboard polish beyond a clean static map; CNAS Pathfinder essay unless Jackson chooses to write it | — | None produce knowledge |

## 2. Data sets and their roles

| Set | Content | Period | Status | Role |
|---|---|---|---|---|
| **B** baseline | VIIRS S-NPP Ukraine 2012–21; Azerbaijan/Armenia 2012–19; Sudan 2012–22 (to pull) | pre-war | Ukraine + Caucasus **downloaded 2026-10-14**, hashed in `data/MANIFEST.json` | D6 reference; definitions |
| **E** exploratory | S-NPP + DeepState (cyterat mirror) | 2024-07-08 → 2025-12-31 | Analysed in feasibility pass | Build pipeline, fit nothing confirmatory |
| **V** validation events | GeoConfirmed Ukraine (60,783 placemarks); Bellingcat TimeMap (2,517) | 2022 → | To pull (no key; ask GeoConfirmed re terms) | D2a outcome for recall + detection model; split 70/30 by month for fit/test |
| **C1** confirmatory | S-NPP + NOAA-20 (+NOAA-21 from 2023-03) with DeepState API or ISW or Economist control | 2022-04-03 → 2024-07-07 | **Untouched until tag** | Lead-lag test raw + corrected |
| **O** observability | CMR granule footprints; ERA5 tcc + ERA5-Land snow; VNP14IMG/VJ114IMG sample (2 days/ISO week/satellite over the front corridor) | 2022 → 2025 | To pull | D9 |
| **T1** Karabakh | S-NPP Azerbaijan+Armenia 2020; settlement capture list | 2020-09-27 → 11-10 | **Untouched until tag** | D14 transfer |
| **T2** Sudan | S-NPP Sudan 2023–25; UCDP GED events Darfur/Kordofan | 2023-04-15 → | **Untouched until tag** | D14 transfer |

## 3. Hypotheses (summary; formal versions in `PREREG.md`)

- **H1 Recall.** FIRMS detects a minority of confirmed events overall, with recall varying by at least 3× between best and worst conditions (clear summer night vs. cloudy winter day).
- **H2 Detection model.** Cloud at overpass, snow, and hours-since-overpass explain most of the variance in detection; the model predicts held-out months with AUC ≥ 0.75.
- **H3 Paired looks.** Concordance between S-NPP and NOAA-20 on paired passes is well below 1 (prediction: 40–70%), i.e. single-satellite zeros are weak evidence.
- **H4 Blind spot.** ≥30% of territorial change in C1 occurs in cell-weeks in the bottom opportunity quartile.
- **H5 Location.** Front-band density ≥3× pre-war baseline in ≥9 of 12 months (calibration, already published elsewhere).
- **H6 Lead (pre-registered null).** Fires do not lead territorial change at a practically meaningful size (TOST bound ±2.9 km²/log-unit), on raw **and** corrected fires.
- **H7 Transfer.** The Ukraine-fit detection model predicts Karabakh and Sudan recall within ±15 pp, filed before download.
- **H8 Constellation loss.** Removing S-NPP lowers recall by a measurable amount and lengthens the blind season; magnitude reported with CI.

## 4. Four-week plan

| Week | Claude | Jackson |
|---|---|---|
| **1** Oct 14–20 | DESIGN + PREREG; repo + CI + manifest; pull E, V, B(Sudan), CMR footprints, ERA5; hex grid; recall pipeline on E; paired-look test | Sign PREREG (by Thu for OSF before maintenance); DeepState form; ISW email; GitHub account decision |
| **2** Oct 21–27 | Tag → pull C1 + T1 + T2; detection model fit on V-train; VNP14IMG sample pull; corrected index v1 | Review recall curve; 1-hr methods check with econ-stats instructor |
| **3** Oct 28–Nov 3 | Confirmatory run once (raw + corrected); transfer predictions filed then checked; S-NPP loss quantified; all figures | Review every number; draft brief intro in own voice; pick reviewers |
| **4** Nov 4–10 | Brief (Quarto), dashboard, README/LIMITS/FAQ, Zenodo, outreach drafts | External review (2 people); final edits; publish Tue Nov 10 |

Hard gate: **no C1/T1/T2 wartime download before `prereg-v1` is tagged.** Download timestamps are logged to `data/MANIFEST.json`.

## 5. Risks and fallbacks

| Risk | Trigger | Fallback |
|---|---|---|
| DeepState silent/no | No reply by Oct 24 | ISW if approved; else Economist summary (national/regional) for 2022–23 + cyterat mirror for 2024–25; `DEVIATIONS.md` entry |
| ISW no | Reply | Drop cross-check; report single-source caveat |
| VNP14IMG too heavy | <5 granules/min or >15 MB each | Shrink sample to 1 day/fortnight on 10 corridor cells; ERA5 remains tier 2 |
| GeoConfirmed objects to use | Reply | Bellingcat TimeMap only (2,517 events; enough for recall, thin for the model) |
| Detection model AUC < 0.65 | Week 2 | Report as finding ("detection is not predictable from available covariates"); corrected index becomes a bounds product |
| S-NPP shutdown date shifts | NASA alert | Analysis frozen; only the living layer is affected |

## 6. Attribution block (every figure, README, brief)

Fire detections: NASA FIRMS / LANCE, VIIRS 375 m (S-NPP, NOAA-20, NOAA-21). Cloud and snow: ERA5 / ERA5-Land, Copernicus Climate Change Service (contains modified C3S information). Territorial control: DeepStateMap.live (DEEPSTATEUATECH LLC), derived aggregates only; Institute for the Study of War and AEI's Critical Threats Project (if permitted); The Economist war-fire model (CC BY 4.0). Events: GeoConfirmed; Bellingcat. Land cover: ESA WorldCover 2021 (CC BY 4.0). Contact: jmackney@uchicago.edu.
