# Figure captions — detection model build (Builder C, 2026-10-22)

All figures below are **confirmatory** (PREREG §4 H1, H2, H3, H7, H8; spec fixed before any wartime C1/T1/T2 download).
Detection = ≥1 VIIRS fire (S-NPP/NOAA-20/NOAA-21, confidence n/h) within 1,000 m of the event and acquired in
[event date 00:00 UTC − 12 h, event date 24:00 UTC + 12 h]. V-test = the 14 seeded test months (events_v_meta.json).

**h1_recall_strata.png** — **confirmatory.** Left: recall of FIRMS against V-test events by PREREG H1 condition stratum.
best = min ERA5 tcc over the window < 0.5, no snow, ≥1 clear night overpass, Jun–Sep; worst = (tcc ≥ 0.5 or snow),
no clear night overpass, Nov–Feb; other = everything else. Wilson 95% CIs; n above each bar. Right: recall by calendar
month, V-test months only (months 2, 9 and 10 have no test month). Source: data/derived/results/h1_recall.csv.

**h1_recall_event_type.png** — **confirmatory.** Recall by coarse event type (Builder A mapping), V-test, Wilson 95% CIs.

**h2_roc_calibration.png** — **confirmatory.** Left: ROC on V-test for the primary logistic model (statsmodels, PREREG H2
feature list: min tcc, snow flag, hours since previous overpass, share of night overpasses, land cover, event type,
month) and the secondary LightGBM with the same features; AUC in the legend (bootstrap CIs in h2_auc.json).
Right: calibration by decile of predicted P(detect) on V-test; dotted line = perfect calibration.

**h2_coefficients.png** — **confirmatory.** The 20 largest logistic coefficients with 95% CIs. Numeric terms are per
train-set standard deviation; categorical terms are relative to the modal reference level (built_up, strike, month 3).

**h3_concordance.png** — **confirmatory.** Paired-look concordance (DESIGN D11 / PREREG H3): share of S-NPP detections
with a NOAA-20 detection within 1 km on a NOAA-20 pass over the same res-6 cell 30–70 min away under ERA5 tcc < 0.3,
by season × day/night, Wilson 95% CIs (dark); reverse direction NOAA-20 → S-NPP (red). Grey band = PREREG 40–70%.
Source detections sampled to 200,000 per direction (seed 20261014).

**h7_transfer_predictions.png** — **confirmatory (prediction filed before T1/T2 download).** Predicted recall for strike
events in Karabakh (Sep 27–Nov 10 2020, S-NPP only) and Sudan Darfur/Kordofan (2023-04-15 → 2025-12-31, three
satellites) from the H2 logistic model with ERA5 covariates for those AOIs and Ukraine overpass templates; error bars =
90% interval from coefficient draws; × = sensitivity with local land cover (Karabakh tree/grass, Sudan grass/bare).
Grey bar = observed Ukraine V-test recall for scale. Source: predictions/transfer_v1.json.

**h8_recall_noSNPP.png** — **confirmatory (descriptive, no success criterion).** V-test recall with the full constellation
and with S-NPP removed from both fires and overpasses, overall and by season / north-east oblasts. Deltas with cell
block-bootstrap CIs in h8_recall_noSNPP.csv.

**h8_blind_season.png** — **confirmatory (descriptive).** Weekly share of in-Ukraine res-6 cells (top) and north-east
cells (Kharkiv, Luhansk, Donetsk, Sumy; bottom) whose median daily detection opportunity in the ISO week is ≤ the C1
25th percentile of cell-day opportunity (which is 0, so blind = median day has no clear overpass), full constellation
vs without S-NPP. Source: h8_blind_share_week.csv.

# Figure captions — C1 panel tests (Builder E, 2026-10-23)

**h5_monthly_ratio.png** — **confirmatory.** H5 (PREREG §4): ratio of S-NPP fire counts in C1 front cells (centroid ≤ 15 km from the weekly VIINA RU|UA line) to the same cells' mean same-ISO-week S-NPP count in 2012–2021, by calendar month, with cell block-bootstrap 95% CIs (2,000 draws). Dashed line = the pre-stated 3× criterion (≥ 9 of 12 months). Source: data/derived/results/h5_monthly_ratio.csv.

**h14_frp_floor.png** — **confirmatory.** H14 (PREREG §4): left, 5th-percentile FRP of VIIRS S-NPP detections in Ukraine 2012–2021 (baseline B, conf n/h) by month × day/night with bootstrap 95% CIs (1,000 draws); the pre-stated test is summer-day (May–Oct) ≥ 1.5 × winter-night (Nov–Apr). Right, re-check on V events: p5 FRP of the matched fire for detected events (circles) and of the nearest fire 1–5 km away inside the window for missed events (crosses), by season × day/night. Source: data/derived/results/h14_frp_floor.csv.

**h4_blindspot.png** — **confirmatory.** H4 (PREREG §4): share of Russian km² gained in C1 (Σ positive weekly net gain over front_15 cell-weeks) by quartile of weekly detection opportunity; the bottom quartile (opportunity ≤ 58) carries the 95% cell block-bootstrap CI (2,000 draws). Dashed = the 30% criterion. Gate regression (log1p fires on opportunity, cell + week-of-year FE): β = 0.0037, wild-bootstrap p = 0.000. Source: data/derived/results/h4_blindspot.json.

**h6_lead.png** — **confirmatory.** H6 and H6b (PREREG §4, pre-registered null): β on log1p(fires at t) in a two-way FE regression of net Russian km² gain over t+1..t+4 on fires, 4 outcome lags and detection opportunity, C1 front_15 cell-weeks. Bars = 90% CIs under CRV1 by cell (blue) and Driscoll–Kraay lag 4 (orange); grey dashed = outer hull of the H6b interval propagated through 1,000 draws of the H2 logit coefficients (P(detect) clipped at 0.02). Green band = ±SESOI. Source: data/derived/results/h6_lead.json.

**h12_kyiv.png** — **confirmatory (left) / exploratory (right).** H12 (PREREG §4): coefficients on log1p(weekly FIRMS detections inside Kyiv city) at leads/lags −4..+4 in a regression of national weekly net Russian km² gain (VIINA) with week-of-year FE and 4 outcome lags, Newey–West(4) 90% CIs. Left: C1 weeks (confirmatory). Right: full span through 2025 (exploratory; most Kyiv fires are in 2025). Green band = ±national SESOI = 1.70 km² × 114 median front cells per week = 194 km². Source: data/derived/results/h12_kyiv.csv.

**h13_deep.png** — **exploratory.** H13 (PREREG §4, exploratory; E period 2024-07-08..2025-12-31): left, national weekly count of FIRMS detections ≥ 16.33 MW more than 30 km from the RU|UA line in RU-held or Russian territory (dominated by agricultural burning in Russia). Right, β on log1p of that count in a regression of front-cell net Russian km² gain over t+1..t+4 with 4 outcome lags, opportunity, cell and week-of-year FE; 90% CIs under CRV1 by cell and Driscoll–Kraay(4); green = ±SESOI. Source: data/derived/results/h13_deep.json.

**h9_leads.png** — **confirmatory.** H9 (PREREG §4): β on log1p(fires) at leads 0, 1, 2, 3, 4, 6 and 8 weeks, C1 front_15 cell-weeks, two-way FE with 4 outcome lags and opportunity. Left: joint distributed-lead regression (primary; fires at t−k on net gain at t). Right: one regression per lead (check; fires at t on net at t+k). Bars = 90% CIs under CRV1 by cell (blue) and Driscoll–Kraay lag 4 (orange); green band = ±0.65 km², the 1-week SESOI. Joint peak at lead 8. Source: data/derived/results/h9_leads.csv.

**h10_size_side.png** — **confirmatory.** H10 (PREREG §4): coefficients on log1p of the four front-cell fire counts (FRP ≥/< the season × day/night p75; fire's Voronoi polygon UA- or RU-held that week) entered together in the H6 specification with outcome net Russian km² gain over t+1..t+3. Prediction: big-UA-side > 0, small-RU-side < 0. Bars = 90% CIs (CRV1 by cell, Driscoll–Kraay lag 4). Source: data/derived/results/h10_size_side.csv.

**h11_phase.png** — **confirmatory.** H11 and H11s (PREREG §4): β on log1p(fires) by phase (A manoeuvre 2022-04-03..2022-11-30; B attrition 2022-12-01..2024-07-07) and by season within phase (summer May–Oct), H6 specification on C1 front_15 cell-weeks. Prediction: β_A > 0, β_B < 0; |β_summer| > |β_winter| within phase. Bars = 90% CIs (CRV1 by cell, Driscoll–Kraay lag 4); green band = ±SESOI. Source: data/derived/results/h11_phase.csv.
