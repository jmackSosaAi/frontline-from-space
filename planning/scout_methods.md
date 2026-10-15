# Scout: methods and tooling for "Front line from space"

Written 2026-10-13. Ground truth read first: `Conflict_Data_Feasibility/frontline/VERDICT.md`, `FIRST_PASS.md`, `SOURCES.md`, the panel CSVs under `frontline/out/`, and `airdefense/VERDICT.md`.

What the feasibility pass established, in numbers this scout designs around:

| Fact | Value | Source |
|---|---|---|
| Panel | 22 sectors × 77 weeks = 1,694 sector-weeks (1,606 in regressions after lags) | `out/sector_week_panel.csv` |
| Outcome mean | 3.89 km² net change per sector-week | VERDICT |
| Zero-front-fire sector-weeks | 43.7% | VERDICT |
| Weekly front vs rear fire correlation | 0.826 (0.94 on logs) | FIRST_PASS |
| Primary spec so far (C: sector FE + week FE + momentum, clustered by sector) | log-fires coef 0.848, p = 0.0485; within-R² 0.452 → 0.458 | VERDICT |
| Momentum coefficient | 0.54 | `out/panel_regressions.csv` |
| Fragility | drop sector 10 (Pokrovsk): coef 0.39, p 0.079 | VERDICT |
| Lead-lag curve | flat 0.09–0.13 from −4 to +4 weeks; no peak at positive lags | `out/panel_xcorr.csv` |
| Front/rear density ratio | 5–17× every month | `out/monthly_front_vs_rear.csv` |
| Known design flaws | Voronoi rear strips land in neighbouring cells on the Donbas bend (8 Donetsk sectors have ~0 rear fires); FIRMS "Ukraine" file stops at the border; DeepState batches edits; ~10 specs already tried on this sample | FIRST_PASS |

The one-line design consequence: **the sample that has already been searched (Jul 2024–Dec 2025, S-NPP only) is now the exploratory set. The pre-registered confirmatory test has to run on data not yet touched: 2022–mid-2024 DeepState via the API, plus NOAA-20/21 detections, plus a second theatre.** Everything below is organised around that split.

---

## Part A. Analytic designs

### A0. Decision map: which question gets which method

| Question (from the project framing) | Primary method | Supporting methods | Output |
|---|---|---|---|
| Q1. How well do fires locate active fighting? | Pre-war per-pixel baseline → excess-fire classification; precision/recall of "excess-fire cells" against the DeepState line and (if obtainable) ACLED/UCDP events | KDE / point-process contrast, front-vs-rear density ratios, distance-to-line decay curves | Spatial skill scores by month; a "where was the front according to fires" map |
| Q2. Do fires lead territorial change? | Two-way FE panel with momentum, clustered + Driscoll-Kraay SEs; distributed-lag (leads+lags) spec; out-of-sample forecast test vs momentum-only baseline | Event studies around named offensives; Granger on the sector series; ML (gradient boosting, temporal CV) | A pre-registered coefficient table and a forecast-skill table; expected result is a defended null or "concurrent, not leading" |
| Q3. When/where is the sensor blind? | Detection-opportunity product: per cell-day expected number of usable looks (overpasses × clear-sky × fuel × daylight/night) | Change-point detection on seasonality; comparison of blind-window weeks against map changes that happened anyway | A coverage raster/H3 layer by week; a "share of advances that happened in blind sector-weeks" statistic |
| Q4. Does the method transfer? | Re-run Q1 and Q3 on Sudan (and optionally Kursk / Myanmar) with UCDP GED or ACLED events as the outcome, since no DeepState-equivalent exists | Within-Ukraine transfer: 2022 manoeuvre phases (Kharkiv Sep 2022, Kherson Nov 2022) vs 2024–25 attrition | A transfer table: same pipeline, different war, same pre-specified metrics |

### A1. Fixed-effects panel (the workhorse)

**Model.** For sector *i*, week *t*:

```
net_{i,t+h} = β·log(1 + fires_{i,t}) + ρ·net_{i,t} + α_i + γ_t + ε_{i,t}
```

- α_i absorbs sector level (terrain, fuel, how DeepState draws that stretch). γ_t absorbs the national season, the weather week, and any Ukraine-wide shock. That is why the national-series correlation disappears and the within-sector correlation survives.
- Momentum ρ·net_{i,t} is the whole game: it carries almost all the predictive power (coef 0.54). Any claim about fires is a claim about β **conditional on momentum**.
- Horizon h ∈ {1, 2, 4} weeks; h = 4 as a cumulative sum (spec E in the first pass) is the right one given DeepState batching, because a 1-week lead is below the outcome's timing resolution.

**Standard errors.** With N = 22 clusters and T = 77:
- Cluster-by-sector (CRV1) is what has been used. 22 clusters is on the low side; CRV1 over-rejects a little below ~30–40 clusters. Remedies, in order of cost: (i) CRV3 / jackknife cluster correction; (ii) wild cluster bootstrap (Webb weights, 9,999 draws) — `wildboottest` is wired into pyfixest; (iii) report both.
- Spatial correlation across neighbouring sectors is real (adjacent sectors share weather and the same offensive). Cluster-by-sector ignores it. Driscoll–Kraay (DK) handles cross-sectional dependence of arbitrary form plus serial correlation, and needs T large (R fixest docs say a minimum of about 20 periods; T = 77 qualifies, 2022–25 backfill gives ~190). Default lag is T^0.25 ≈ 3; pre-register lag = 4.
- Conley (distance-based) SEs are the other option; fixest supports them; pyfixest status unverified. Not needed if DK is reported.
- **Recommendation: report CRV1-by-sector and DK(4) side by side; call the result significant only if both p < 0.05.** That is a pre-registrable rule.

**Nickell bias.** Momentum (lagged dependent variable) with sector FE gives Nickell bias of order 1/T ≈ 1.3% with T = 77. Small enough to note and ignore; do not reach for Arellano–Bond. Say so in the brief, because an interviewer may ask.

**Count outcome variants.** `net_km2` is heavy-tailed with mass at zero (69 flat days nationally; many zero sector-weeks). Robustness: (a) linear probability / logit of P(advance > 1 km²), already run (+0.030 per log unit, p 0.041); (b) inverse hyperbolic sine of net km² instead of levels; (c) winsorise at the 99th percentile. All three go in the robustness list, not the primary spec.

**Treatment variable variants.** log(1+front fires) is fine. Alternatives: fires per 100 km² of front band (normalises band area, which varies with line curvature); night-only detections (cleaner combat signal, far fewer agricultural fires); FRP-weighted sum; excess fires over the pre-war baseline (section A5), which is the strongest candidate because it removes the agricultural component before it enters the regression.

### A2. Distributed-lag / Granger / lead-lag

- **Distributed lag with leads (the Sims test).** Include fires at t−2…t+2 jointly. If fires "lead", coefficients on past fires are positive and on future fires are zero. The first pass ran this (lf_l1 −0.11, lf 0.85, lf_f1 −0.32, lf_f2 0.10) and it shows the contemporaneous coefficient only, which is the "concurrent, not leading" pattern. Keep it; it is the single most legible table for a reader.
- **Panel Granger causality.** Dumitrescu–Hurlin (2012) is the standard heterogeneous-panel Granger test; no mature Python implementation that this scout could verify — R `plm::pgrangertest` exists. Simpler and defensible: the joint F/Wald test on lags 1–4 of fires in the FE regression with momentum lags 1–4, clustered. Report both directions (fires→area, area→fires). The first pass found the reverse direction significant (p 0.015), which is itself a finding: advances generate fires.
- **Lead-lag cross-correlogram** after two-way demeaning (already done). Keep as a figure; add bootstrap bands by resampling sectors (block bootstrap over weeks within sector, block length 4).
- **Caveat to state:** Granger tests on a batched, revised outcome (DeepState) are tests about the map editor's timing as much as the ground.

### A3. Event studies around known offensives

Pick 6–10 named operations with reasonably well-documented start dates (from ISW daily assessments, which are public, and the DeepState changelog). Candidates:
- Kharkiv counteroffensive (Sep 6 2022), Kherson withdrawal (Nov 9–11 2022), Bakhmut fall (May 2023), Zaporizhzhia counteroffensive (Jun 4 2023), Avdiivka fall (Feb 17 2024), Kharkiv/Vovchansk incursion (May 10 2024), Kursk incursion (Aug 6 2024; needs the Russian-Federation FIRMS file), Vuhledar (Oct 1 2024), Kurakhove (Jan 2025), Pokrovsk envelopment (summer 2025).

Design: stack sector-weeks within ±8 weeks of each event date, estimate

```
y_{i,t} = Σ_{k=-8..8} δ_k · 1[t − T_event = k] + α_i + γ_cal(t) + ε
```

separately for y = front fires and y = net km², plot δ_k with CIs. The question is whether the fire curve rises before week 0. Controls: same calendar weeks in non-event sectors (that is what γ_cal does with a stacked design). Date selection must be fixed before looking at fire series — list the events and dates in the pre-registration file.

Honesty note: the event dates themselves come from the same human sources that feed DeepState; this is a descriptive check, not identification.

### A4. Spatial point-process and kernel-density approaches

These address Q1 (location skill) rather than Q2.

- **Distance-decay curves.** For each week, histogram fire detections by signed distance to the line of contact (negative = Ukrainian-held side). The shape (peak at 0–10 km, decay by 30 km) is the cleanest picture of "fires mark the front". Compute it monthly; the width of the peak is a measurable quantity that can be compared with Sudan.
- **KDE front estimate.** Kernel-density of the week's detections (bandwidth 10 km, Gaussian), take the ridge or the 90th-percentile contour, and measure Hausdorff / mean distance to the DeepState line. This gives a "front from fires alone" product with an error metric in km. Expect it to work in Jul–Sep and fail Nov–Feb; quantifying that failure is the deliverable.
- **Ripley's K / L and pair-correlation** inside the front band versus the rear band: are front fires more clustered (strike patterns) than agricultural fires (field-sized, regular)? `pointpats` (PySAL) does K/L/G/F with Monte Carlo envelopes but its `k_test` edge correction is "not yet implemented"; R `spatstat` is the mature option if this matters. Keep this as optional.
- **Inhomogeneous Poisson regression (log-Gaussian Cox is overkill).** On an H3 res-7 grid (≈5 km cells), Poisson/negative-binomial GLM of weekly counts on distance-to-line bins, land cover, and the pre-war baseline, with cell and week FE. This is the raster-scale twin of the sector panel and is a natural robustness check against sector-definition choices.

### A5. Pre-war per-pixel baseline (the Economist approach)

Verified from the Economist repo (`github.com/TheEconomist/the-economist-war-fire-model`, MIT code / CC-BY-4.0 data): 0.1° × 0.1° grid cells; a cell-day is flagged when its fire count has <5% chance under a normal year; the excess must recur at least twice within 50 km and 7–180 days; fires in the same cell within 10 days are also flagged. Secondary sources describe an ensemble of 100 gradient-boosted models trained on 10 non-war years (arXiv 2408.17022). The repo publishes `output-data/ukraine_war_fires.csv` with one row per event, so **the Economist's classification can be downloaded and used directly as a treatment variable**, and the project can also build its own lighter version:

1. Pull FIRMS VIIRS S-NPP 2012–2021 for Ukraine (10 non-war years; country yearly CSVs from the archive tool, roughly 20–90k rows/year, tens of MB total).
2. Grid to H3 res 6 (~36 km² cells) or the Economist's 0.1°; count detections per cell × ISO week.
3. Baseline per cell-week: empirical distribution across the 10 years (median, 95th percentile) — or a quantile GBM on (cell, week-of-year, land cover, ERA5 dryness) if more smoothing is wanted. The empirical version is the right primary choice: transparent, no tuning.
4. Excess = observed − 95th-percentile baseline, floored at zero. This is the regressor that replaces the broken rear-strip control.

Why this beats the Voronoi rear strip: the control is the same cell in the same calendar week, so crop type, fuel, and harvest timing are held fixed; and it does not break on the Donbas bend.

Threat: pre-war agricultural practice in Donetsk/Luhansk (2014–21 line) was already abnormal; and fields near the 2022–25 line are unharvested, so the baseline overstates expected agricultural burning there. State it; test it by excluding a 30 km buffer around the 2021 line in a robustness run.

### A6. Change-point detection

Use for Q3 and for describing regimes, not for inference.
- `ruptures` (BSD-2, PELT with `min_size`, `jump`; docs at ctruong.perso.math.cnrs.fr/ruptures) on the weekly national and sector series of (a) front fires, (b) excess fires, (c) area change. PELT with an L2 or RBF cost and a penalty chosen by BIC.
- Also Bayesian online change-point (bocd implementations are small; or just a CUSUM) on the detection-opportunity series to date the start and end of each blind season objectively.
- Report: dated regime boundaries per year (fire season on/off), and whether DeepState activity regime changes line up with them. Expectation: they do not (advances peaked Nov 2024 and May–Jul 2025 while fires peak Jul–Sep).

### A7. ML baselines with proper temporal CV

Purpose: show, in forecast-skill units, that fires add nothing (or something) beyond momentum. This is the table a Palantir/Anduril interviewer will understand fastest.

- **Targets:** next-week net km² (regression) and P(advance > 1 km²) (classification), per sector.
- **Baselines (fix in advance):** (B0) zero / sector mean; (B1) momentum-only: net_{t}, net_{t−1..t−4}, sector FE as one-hot; (B2) B1 + front fires lags 0–4; (B3) B2 + rear/excess fires + ERA5 dryness + detection opportunity; (B4) B3 + night-only fires and FRP.
- **Learner:** LightGBM with small trees (num_leaves 15, lr 0.05, 300–500 rounds, early stopping on the validation fold). Ridge regression as the linear counterpart so the comparison is not about the learner.
- **CV:** rolling-origin, expanding window, 8-week test blocks, 4-week gap between train and test to kill leakage through lags and DeepState revisions. `sklearn.model_selection.TimeSeriesSplit(gap=4)` does this. Never random K-fold; never shuffle. Also do **leave-one-sector-out** as a spatial generalisation check.
- **Metrics:** MAE and RMSE in km²; for the binary target, Brier score and PR-AUC (base rate 0.30). Report the skill score vs B1: `1 − MAE(Bk)/MAE(B1)`.
- **Pre-register the success criterion:** fires "add forecast value" only if B2 beats B1 by ≥5% MAE on the held-out 2022–24 backfill period and on 2025, in both. Anything below that is reported as null.
- SHAP values for B3 are fine for the dashboard but are description, not evidence.

### A8. The detection-opportunity / blind-spot product

This is the piece with no published precedent and the one that transfers to any theatre. Build it as a per-cell-per-day (then aggregated to sector-week) expected number of usable looks:

```
opportunity_{c,d} = Σ_{overpasses p on day d} clear_{c,p} · observable_{c,p}
```

Components, with where to get each:

| Component | Source | Notes |
|---|---|---|
| Overpass count and local time | S-NPP, NOAA-20, NOAA-21 share the 1:30 am / 1:30 pm orbit; NOAA-20 is about 50 minutes ahead of S-NPP (NASA LANCE forum). Mid-latitudes get 3–4 looks/day per satellite because of swath overlap (VIIRS user guide FAQ). | Simplest proxy: count of distinct (satellite, acq_time) combinations that produced any detection anywhere in a 200 km box that day — this is a cheap empirical "the swath covered us" flag. Rigorous version: pull granule bounding boxes from LAADS/CMR for VNP14IMG, VJ114IMG, VJ214IMG. Orbital propagation with `skyfield` + TLEs from CelesTrak is the fully offline option. |
| Cloud | VNP14IMG fire mask class 4 = Cloud; class 0 = not processed; class 1 = bow-tie deletion (Table 1, VIIRS C2 375 m user guide v1.2, June 2025). The swath product gives the per-pixel cloud decision the fire algorithm itself used. | VNP14IMG is on LP DAAC/LAADS (not in GEE — unverified, no catalog hit). Downloading swaths for Ukraine 2022–25 is heavy (each granule tens of MB; several per day). Cheaper proxies: GEE `NASA/VIIRS/002/VNP09GA` QF1 bits 2–3 (cloud confidence, same sensor, daily, 1 km) — bit layout came from a secondary mirror, verify against LP DAAC; or ERA5 total cloud cover at the overpass hour (0.25°, free, CDS). |
| Fuel / land cover | ESA WorldCover 10 m (GEE `ESA/WorldCover/v200`) or Copernicus CLC; cropland share, tree share, built-up share per cell. | Built-up and water cells cannot produce vegetation-fire detections; conversely urban combat produces type≠0 detections that the first pass dropped — reconsider keeping type 1–3 for urban sectors. |
| Dryness | ERA5-Land soil moisture layer 1 (0.1°, hourly, CDS `cdsapi`, free account); or CEMS/GEFF Fire Weather Index from the CDS "Fire danger indices historical data" (not re-verified in this pass). | Fuel moisture decides whether a strike ignites anything. Snow cover (ERA5-Land `snow_depth`) is the hard blind flag for Dec–Feb. |
| Day length / night | `astral` or `skyfield` sunrise/sunset per cell-day. | Night overpasses are far more sensitive (VNP14IMG detects ~17× more night fire pixels than VNP14 per the user guide); in winter the 1:30 am pass is the only useful one and the 1:30 pm pass is near-useless over snow. |

Outputs:
1. `opportunity.parquet`: H3 res-6 cell × day × satellite with looks, clear-fraction, snow flag, FWI/soil moisture, day-length.
2. Sector-week aggregate joined to the panel as a covariate and as a weight (weight observations by opportunity; or interact fires × opportunity).
3. A map/animation: "fraction of the front observable this week" through the war. The headline number: share of DeepState advances (km²) that occurred in sector-weeks with opportunity below some threshold.

Validation: regress log front fires on opportunity with sector and week-of-year FE; the coefficient should be strongly positive. If it is not, the product is wrong.

### A9. Recommended primary spec and robustness specs

**Primary (confirmatory), fixed before touching the 2022–24 backfill:**

```
net4_{i,t+1..t+4} = β·log(1 + front_fires_{i,t}) + Σ_{k=0..3} ρ_k·net_{i,t−k}
                    + θ·opportunity_{i,t} + α_i + γ_t + ε_{i,t}
```
- Sectors: 50 km segments of the reference line, but **replace Voronoi cells with perpendicular-buffer corridors** (segment buffered 90 km each side, clipped by bisectors between neighbouring segment endpoints) so rear strips cannot escape into neighbouring cells.
- Front band: ±15 km of that week's line. Rear: replaced by the pre-war baseline (A5) for the excess-fires robustness; retained as a 50–90 km strip only for the descriptive density table.
- Satellites: S-NPP + NOAA-20 + NOAA-21 pooled, type 0 only, confidence nominal or high.
- Sample: all available weeks (2022-W15 to latest), estimated separately on (a) 2022-04 → 2024-07 (new data) and (b) 2024-07 → 2025-12 (already-seen data), then pooled.
- Inference: CRV1 by sector and DK(4); significance requires both p < 0.05 in sample (a).
- Effect-size criterion: β is "practically meaningful" only if a doubling of fires implies ≥ 2 km² additional 4-week advance (≈ the sample mean of one week), AND forecast MAE improves ≥ 5% vs momentum-only in the rolling CV. Otherwise the pre-registered conclusion is "concurrent indicator, not a leading one".

**Robustness specs (also fixed in advance):**
1. Treatment = excess fires over pre-war baseline (A5) instead of raw front fires; and night-only fires.
2. Outcome = P(advance > 1 km² in the next 4 weeks), logit with FE (or LPM); and IHS(net km²).
3. Sector width 25 km and 100 km; front band 10 km and 25 km (a 2×2 grid, reported in one table, not cherry-picked).
4. Leads-and-lags (Sims) spec with fires t−4..t+4 and a joint test that lead coefficients = 0.
5. Drop-one-sector jackknife of β (plot the 22 estimates); drop Donetsk entirely.
6. Phase split: manoeuvre (2022-09 to 2022-12) vs attrition (2023-06 onward); interaction β × phase.
7. Raster twin: H3 res-7 cell × week Poisson/NB panel with cell and week FE (A4).

Everything else is exploratory and labelled as such.

### A10. Pre-registration template

Save as `planning/PREREG.md`, commit it, and tag the commit before the backfill download starts; the commit hash is the timestamp. (OSF registrations are free and give an external timestamp; optional.)

```
# Pre-registration: Front line from space
Commit: <hash>   Date: <date>   Author: Jackson Mackney

1. Hypotheses
 H1 (location): within each month, VIIRS detection density within 15 km of the DeepState line
    exceeds the same-cell pre-war baseline by a factor ≥ 3 in ≥ 9 of 12 months.
 H2 (lead): β in the primary spec > 0 with p < 0.05 under both CRV1-by-sector and DK(4),
    in the 2022-04..2024-07 confirmatory sample. Prediction: H2 is NOT supported.
 H3 (forecast value): LightGBM/Ridge with fires beats momentum-only by ≥ 5% MAE in
    rolling-origin CV. Prediction: not supported.
 H4 (blind spot): ≥ 30% of total km² gained occurs in sector-weeks whose detection
    opportunity is in the bottom quartile.
 H5 (transfer): in Sudan, the front-band / baseline density ratio around UCDP GED event
    clusters is ≥ 3 in the dry season (Nov–May) and the lead-lag curve on events is flat.

2. Data, fixed
 FIRMS VIIRS 375 m S-NPP, NOAA-20, NOAA-21; type = 0; confidence ∈ {n, h}; Ukraine +
 Russian Federation country files; standard-quality where available, NRT otherwise (flagged).
 DeepState: cyterat mirror daily files 2024-07-08→; DeepState history API 2022-04-03→2024-07-07.
 Pre-war baseline: VIIRS S-NPP 2012–2021.
 Natural Earth 1:50m admin-0 for the border/coast cut (3 km inside border).
 Covariates: ERA5-Land soil moisture L1 and snow depth; ESA WorldCover v200.
 Transfer: FIRMS Sudan 2023–2025; UCDP GED 25.1/26.1 (and ACLED if the account is approved).

3. Unit definitions, fixed
 Week = ISO Mon–Sun; snapshot = last map in week. Line of contact as in first_pass.py.
 Sectors: 50 km segments of the 2024-12-30 line (Ukraine) and perpendicular corridors.
 Front band ±15 km of that week's line. Outcome = net km² gained by Russia, 4-week sum.

4. Primary specification: as in scout_methods.md §A9 (copy it in full here).
5. Robustness list: §A9 items 1–7, no additions after this commit.
6. Inference rules: both SEs; effect-size floor; MAE skill floor. Multiple-testing: the five
   hypotheses are separate claims; no family-wise correction, but no new hypotheses added.
7. Exploratory analyses will be labelled "exploratory" in every figure caption.
8. What would make me abandon the project: FIRMS NOAA-20/21 pull fails AND DeepState API
   backfill fails. What would make me change the primary spec: nothing after this commit;
   deviations are logged in DEVIATIONS.md with dates.
9. Known confounders and how they are handled: season (week FE + baseline), map latency
   (4-week outcome), spatial dependence (DK), sample search (confirmatory split), border
   and coast (3 km cut), Kursk (Russian-Federation file), urban fires (type filter sensitivity).
```

### A11. Generalisation: how the plan answers "too Ukraine-specific"

1. **Blind-spot product is physics, not Ukraine.** Overpass geometry, cloud, snow and fuel moisture apply everywhere; present the Ukraine coverage map next to the Sudan one.
2. **Within-war transfer.** 2022 manoeuvre phases vs 2024–25 attrition is a built-in test of the "type of war" objection, and is the single best use of the DeepState backfill.
3. **Cross-war transfer.** Sudan has no DeepState-equivalent (this pass found only hand-drawn control maps from Political Geography Now / Thomas van Linge / Sudans Post, no open polygons), so the Sudan outcome is UCDP GED events (open, no key, ged251 29 MB, ged261 39 MB verified by HEAD in SOURCES.md) and ACLED if approved. The transferable metrics are the Q1 and Q3 ones (density ratio, distance-decay width, blind-season dates), not β.
4. **Name the confounders that do not travel** (Gerbera-era FPV strikes setting fields alight, DeepState editorial cadence) and the ones that do (agricultural burning seasons, cloud climatology).

---

## Part B. Tooling

### B1. Recommended stack (with reasons)

| Layer | Pick | Why | Alternative |
|---|---|---|---|
| Environment | **uv** (already installed at `/opt/homebrew/bin/uv`), Python 3.11 or 3.12, `pyproject.toml` + `uv.lock` | geopandas/shapely/rasterio/pyproj wheels bundle GDAL/PROJ so uv is enough; one lockfile; fast; what the feasibility venv already used (py 3.10). | **pixi** if the GDAL CLI, extra GDAL drivers, or an R+Python mix is needed; pixi uses uv underneath for PyPI. Not installed; ~1 h to adopt. |
| Vector geo | **geopandas 1.1 + shapely 2.1 + pyproj 3.7** (already used) | Vectorised shapely 2 handles 100k points × line distance fast; `union_all`, `substring`, STRtree are all used in `first_pass.py`. | — |
| Tabular / joins | **DuckDB** with `spatial` and `h3` (community) extensions | Read 300k+ FIRMS rows and GeoParquet without pandas memory games; `INSTALL h3 FROM community; LOAD h3;` gives `h3_latlng_to_cell`, `h3_cell_to_boundary_wkt`, `h3_polygon_wkt_to_cells`. Fast H3 binning for the baseline and the opportunity product. | polars + `h3` Python package. |
| Hex grid | **H3** res 6 (~36 km²) for baseline and opportunity, res 7 (~5 km²) for the raster twin | Equal-area-ish, hierarchical, trivially joinable in DuckDB; avoids reprojection headaches across Ukraine and Sudan. | 0.1° lat/lon grid (matches the Economist). |
| Raster | **rasterio + rioxarray/xarray** | ERA5-Land NetCDF, WorldCover GeoTIFFs, zonal stats to H3 via `exactextract` or `rasterstats`. | — |
| Cloud-scale pulls | **Google Earth Engine (Python `earthengine-api` + `geemap`)**, non-commercial registration | WorldCover, VNP09GA cloud QF, ERA5 daily aggregates, and `ee.ImageCollection("FIRMS")` (1 km rasterised LANCE detections, not the 375 m points) reduced to H3/sector polygons server-side. Free for research/education per the catalog text; register a Cloud project as non-commercial. The community catalog's FIRMS vector archive (`projects/sat-io/open-datasets/VIIRS/VNP14IMGTDL_NRT_YYYY`) only runs 2012–2021 and is NRT, so it is a baseline-years convenience, not a primary source. | Download rasters and do zonal stats locally (slower, fine for Ukraine-sized AOIs). |
| Econometrics | **pyfixest** (`pf.feols("y ~ x | sector + week", vcov={"CRV1": "sector"})`, wild cluster bootstrap via `wildboottest`) for FE models; **linearmodels `PanelOLS`** with `cov_type="kernel"` (Bartlett, bandwidth 4) for Driscoll–Kraay — this cov_type name is verified from linearmodels docs; **statsmodels** for logit/GLM/NB. | pyfixest's README lists "robust, cluster-robust, and HAC" estimators and CCV, but this scout could not verify a documented DK option, so DK goes through linearmodels. | **R fixest** (`vcov = DK(4) ~ week`, `vcov = conley(50)`), `plm::pgrangertest`, `spatstat`. R is installed at `/usr/local/bin/R`. Use R only for DK/Conley cross-checks if linearmodels misbehaves. |
| ML | **LightGBM** + scikit-learn `TimeSeriesSplit(gap=4)`; `shap` optional | Standard, fast, interviewers know it. | Ridge only (acceptable minimum). |
| Change-points | **ruptures** (PELT) | Small, well documented. | — |
| Point patterns | **pointpats** (PySAL) for KDE and K/L envelopes | Fine for the descriptive use; note missing edge correction. | R spatstat. |
| Orbits / sun | **skyfield** (TLEs from CelesTrak) and **astral** | Pure Python, offline, cheap. | Granule metadata via NASA CMR API. |
| Data versioning | **Plain manifest** (`data/MANIFEST.json`: URL, sha256, bytes, retrieved-at, license) + `make data` fetch script; raw data gitignored; processed Parquet < 100 MB committed or released as GitHub Release assets | DVC adds a remote, a cache and a second CLI for a 1-person project with ~500 MB of raw data. Git LFS costs quota. A manifest with hashes gives the same reproducibility claim and is readable by an interviewer in 30 s. | DVC if the project outlives 6 weeks or gains a collaborator. |
| Orchestration | **Makefile** (`make data`, `make panel`, `make models`, `make figs`, `make brief`) | Explicit DAG, zero dependencies, mirrors the Economist repo's layout. | `snakemake` or `doit`. |
| Testing | **pytest** on geometry invariants (sectors partition the band; areas sum; no sector-week duplicated; weekly snapshots monotone-ish), plus a 3-sector fixture that runs the whole pipeline in < 30 s; `ruff` for lint; GitHub Actions running tests on push | What "defensible" means in code form. | — |
| Reports | **Quarto** (`.qmd` → PDF via typst or LaTeX, and HTML) for the 5–8 page brief; figures from matplotlib/plotnine | One source, two outputs, citations handled. | Markdown + pandoc. |
| Dashboard | **Static site on GitHub Pages**: MapLibre GL JS + PMTiles (or plain GeoJSON < 10 MB) + Observable Plot / Plotly JS, data pre-baked to JSON/Parquet by the pipeline | Zero cost, no sleeping app, survives after graduation, no server to defend. | Streamlit Community Cloud (free, public apps, sleeps after ~12 h idle, ~1 GB RAM, US-hosted) if interactivity is needed fast; marimo/`panel` as middle ground. |
| Docker | Optional `Dockerfile` with `uv sync --frozen` | Only if an interviewer might run it; otherwise `uv.lock` + a README "setup in 4 commands" is enough. | — |
| Notebooks | Jupyter only for exploration; nothing load-bearing lives in a notebook; `nbstripout` on commit | Reproducibility. | marimo (pure-Python, deterministic) if starting from scratch. |

### B2. Data access specifics the stack must handle

- **FIRMS archive**: country-year CSVs (used already; Ukraine VIIRS 2023–25 = 43k/86k/68k rows). NOAA-20 coverage 1 Apr 2018→, NOAA-21 17 Jan 2024→ (archive page). NRT is replaced by standard quality with ~5-month lag, so 2026 pulls will be NRT and must be flagged. The API (`/api/area/csv/<MAP_KEY>/<source>/<bbox>/<days≤10>/<date>`) is limited to 5,000 transactions per 10 minutes per MAP_KEY and multi-day requests count as multiple transactions; sources include `VIIRS_NOAA21_NRT`. A full 2024–25 NOAA-20/21 backfill through the API is ~150 requests per sensor at 10-day chunks: trivial.
- **DeepState history API**: 1,785 snapshots 2022-04-03→2026-10-13 at ~200 KB–1 MB each (~0.5–1.5 GB total). Needs polite rate limiting (1 req/s), caching to disk, and a style-based filter to keep only occupied-area polygons. Budget one evening plus retries. License unclear — attribution only, do not redistribute raw snapshots; publish derived sector-week tables.
- **ACLED**: free registration with a use category; non-commercial; redistribution prohibited; download caps depend on category (2023 FAQ). Apply on day 1 as academic; design the Sudan test so UCDP GED alone suffices.
- **GEE**: non-commercial Cloud project registration takes a day or two; export reductions as CSV to Drive.
- **CDS (ERA5-Land)**: free account, `.cdsapirc`; 2026 forum threads report intermittent outages and slow queues; pull once, cache as NetCDF/Zarr.

### B3. Learning curve for a competent-but-not-expert Python user

| Tool | Already used? | Hours to productive | Notes |
|---|---|---|---|
| geopandas / shapely 2 | Yes (feasibility scripts) | 0–4 | Learn STRtree queries and `to_crs` discipline (ETRS89 LAEA 3035 for Ukraine, UTM/Africa Albers for Sudan). |
| DuckDB + spatial + h3 | No | 4–8 | SQL you already know; the only new thing is `ST_*` and `h3_*` functions. Biggest productivity win in the list. |
| pyfixest / linearmodels | statsmodels yes | 3–6 | formula syntax `y ~ x \| fe1 + fe2`; understanding CRV1 vs DK vs wild bootstrap is the real cost, ~3 h of reading. |
| LightGBM + TimeSeriesSplit | Probably basic | 3–5 | The discipline (gap, expanding window, no shuffle) matters more than the API. |
| Google Earth Engine | No | 8–16 | The client-server model trips everyone; `geemap` helps. Budget two evenings, and keep a local fallback. |
| rasterio / xarray | No | 4–8 | Only needed for ERA5 and WorldCover zonal stats. |
| skyfield / astral | No | 2–3 | Small APIs. |
| ruptures / pointpats | No | 1–2 each | Small APIs. |
| uv + Makefile + pytest + Actions | Partly | 4–6 | Set up once in week 1. |
| Quarto | No | 3–4 | Install, one template, done. |
| MapLibre + PMTiles static dashboard | No | 10–20 | The largest unknown; cap it. Fallback: Plotly HTML export or Streamlit, 4–6 h. |
| R fixest (cross-check only) | No | 2–4 | Only if DK/Conley via linearmodels fails. |

Total new-tool overhead: roughly 45–80 hours spread over the 4–6 weeks, of which GEE and the dashboard are the discretionary half. Dropping GEE (local rasters) and using Plotly/Streamlit for the dashboard cuts it to ~25–35 h.

### B4. Repo layout (so the plan is concrete)

```
frontline-from-space/
  pyproject.toml  uv.lock  Makefile  README.md  LICENSE (MIT code, CC-BY-4.0 data)
  planning/PREREG.md  planning/DEVIATIONS.md
  data/MANIFEST.json  data/raw/ (gitignored)  data/processed/*.parquet
  src/ffs/  ingest_firms.py  ingest_deepstate.py  loc.py (line of contact)  sectors.py
            baseline.py  opportunity.py  panel.py  models.py  transfer.py  figs.py
  tests/  (fixtures: 3 sectors × 20 weeks)
  notebooks/ (exploratory only)
  report/brief.qmd  report/intercept-note.qmd
  site/ (static dashboard build)
  .github/workflows/ci.yml
```

---

## Flags: what this scout could not verify

- **pyfixest Driscoll–Kraay syntax.** README says HAC estimators exist; the docs pages returned 404 on the URLs tried. Use linearmodels `cov_type="kernel"` (verified) or R fixest `DK ~ week` (verified) until checked.
- **Scientific Reports 2026 VIIRS Nightfire paper** (`nature.com/articles/s41598-026-42172-0`, cited in VERDICT.md): the fetch hit a login redirect, and the only Nightfire/Ukraine items found were a 2026 *Remote Sensing Applications: Society and Environment* paper (Dingemanse & Cerra, offshore structures) and a March 2026 Payne Institute post on frontline/urban combat. Re-check the citation before quoting it in the brief.
- **VNP14IMG swath availability in Earth Engine**: no catalog hit; assume LP DAAC/LAADS download only. VNP09GA QF1 bit layout came from a secondary mirror.
- **NOAA-21 offset within the orbit**: 50-minute spacing is documented for NOAA-20 vs S-NPP only.
- **CDS Fire Weather Index dataset name and ESA WorldCover GEE asset ID**: from memory, not re-verified (web search budget ran out).
- **ACLED 2026 terms and student category**: sources are 2023; check the live access guide.
- **Sudan territorial-control polygons**: none found in open form; plan assumes event data as the outcome.
- **Streamlit Community Cloud limits**: secondhand 2026 figures.

## Sources

- Feasibility ground truth: `/Users/jacksonmackney/D3/Conflict_Data_Feasibility/frontline/{VERDICT,FIRST_PASS,SOURCES}.md`, `out/*.csv`, `scripts/first_pass.py`
- Economist war-fire model repo: https://github.com/TheEconomist/the-economist-war-fire-model ; secondary method description https://smallwarsjournal.com/2026/03/25/fire-detection-as-a-proxy-for-combat-the-economist/ ; arXiv 2408.17022 https://arxiv.org/pdf/2408.17022
- VIIRS C2 375 m Active Fire User Guide v1.2 (June 2025): https://www.earthdata.nasa.gov/s3fs-public/2025-06/VIIRS_C2_AF-375m_User_Guide_1.2.pdf
- FIRMS archive download and sensor coverage: https://firms.modaps.eosdis.nasa.gov/download/ ; API: https://firms.modaps.eosdis.nasa.gov/api/area/csv ; 5,000/10-min limit: https://appliedsciences.nasa.gov/sites/default/files/2025-05/Part%203%20FIRMS%202025%20Q%26A%20Session.docx.pdf ; NOAA-21 availability: https://wiki.earthdata.nasa.gov/spaces/FIRMS/blog/2024/02/08/343475617/NOAA-21+VIIRS+Active+Fire+Detection+Data+Now+Available
- NOAA-20 ~50 min ahead of S-NPP: https://forum.earthdata.nasa.gov/viewtopic.php?p=18077 ; S-NPP crossing times: https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/viirs/
- GEE FIRMS 1 km collection: https://developers.google.com/earth-engine/datasets/catalog/FIRMS ; VNP14A1: https://developers.google.com/earth-engine/datasets/catalog/NASA_VIIRS_002_VNP14A1 ; VNP09GA: https://developers.google.com/earth-engine/datasets/catalog/NASA_VIIRS_002_VNP09GA ; community FIRMS vector archive: https://gee-community-catalog.org/projects/firms_vector/
- MCD64A1 cropland validation in Ukraine (large omission/commission errors, why burned-area products are not used here): https://bsosdev1.umd.edu/sites/geog.umd.edu/files/pubs/1-s2.0-S0303243421001501-main.pdf
- fixest standard errors (DK, NW, Conley, T ≥ ~20): https://search.r-project.org/CRAN/refmans/fixest/html/vcov.fixest.html ; https://search.r-project.org/CRAN/refmans/fixest/html/vcov_hac.html
- linearmodels PanelOLS covariance (`kernel` = Driscoll–Kraay): https://bashtage.github.io/linearmodels/panel/panel/linearmodels.panel.model.PanelOLS.fit.html
- pyfixest README (CRV1 syntax, wild bootstrap, HAC claim): https://raw.githubusercontent.com/py-econometrics/pyfixest/master/README.md ; PyPI https://pypi.org/project/pyfixest/
- DuckDB spatial: https://duckdb.org/docs/extensions/spatial ; H3 community extension: https://duckdb.org/community_extensions/extensions/h3
- ruptures: https://arxiv.org/pdf/1801.00826 ; https://pypi.org/project/ruptures/
- pointpats: https://pysal.org/pointpats/api.html ; https://pysal.org/pointpats/generated/pointpats.k_test.html
- uv vs pixi for geospatial: https://pydevtools.com/handbook/explanation/uv-vs-pixi-vs-conda-for-scientific-python/
- DVC vs Git LFS discussion: https://discuss.dvc.org/t/dvc-compared-with-gitlfs-for-storage-and-versioning-only/241
- ERA5-Land via CDS: https://ecmwf-models.readthedocs.io/en/latest/download.html ; https://forum.ecmwf.int/t/cds-api-era5-land-dataset-end-dates/11007
- ACLED access model: https://acleddata.com/knowledge-base/acled-access-guide ; FAQ PDF https://developer.acleddata.com/rehd/cms/views/acled_api/documents/FAQs_ACLED-Registration-and-Access-Model_11.2021.pdf
- Sudan control maps (hand-drawn, no open polygons found): https://controlmaps.polgeonow.com/?p=9147 ; https://www.euaa.europa.eu/country-guidance-sudan/21-map-areas-control-and-influence
- Streamlit Community Cloud limits (secondhand): https://livemy.app/blog/deploy-streamlit-app ; https://pandastack.io/blog/best-streamlit-hosting-2026
- VIIRS Nightfire / Ukraine (Payne Institute): https://payneinstitute.mines.edu/conflict-monitoring-with-viirs-nightfire-the-war-in-ukraine/
