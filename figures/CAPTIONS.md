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
