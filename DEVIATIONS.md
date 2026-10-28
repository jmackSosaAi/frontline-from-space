# Deviations from prereg-v1

Dated log of every change made after `PREREG.md` was signed and tagged `prereg-v1` (2026-10-22). Newest last.

## 2026-10-22: Telegram public posts added as an additional validation-event source

- **What:** after prereg-v1, public Telegram posts from these official and monitoring channels were added as an additional validation-event source (manifest set `V-telegram`) for H1, H2 and H12: `@kpszsu` (Air Force of the AFU), `@VA_Kyiv` (Kyiv City MA), `@synegubov` (Kharkiv ODA), `@odeskaODA` (Odesa ODA), `@dnipropetrovskaODA` (Dnipropetrovsk ODA), `@zoda_gov_ua` (Zaporizhzhia OVA), `@kozytskyy_maksym_official` (Lviv OVA), `@war_monitor` and `@monitoringwar` (volunteer monitoring, unofficial).
- **How:** no-login public web preview `https://t.me/s/<handle>?before=<msg_id>` (`scripts/fetch_telegram_preview.py`), one request at a time, ~2 s between pages, contact address in the User-Agent. Stored fields: channel, msg_id, date_utc, text, views, has_media, forwarded_from_channel. No user or author data. `@DeepStateUA` (territorial-control data) is excluded and was not scraped.
- **Scope:** not used to define any confirmatory outcome. The confirmatory set V stays as frozen in PREREG §2–§3 (GeoConfirmed and Bellingcat). Any Telegram-derived recall estimate is reported separately as secondary/exploratory and is not pooled with V.
- **AI use:** an LLM is used only for inference-time extraction (date, place, weapon, hit/debris) from post text. No model is trained or fine-tuned on the corpus (Telegram API Terms §1.5).

## 2026-10-22: H8 blind-season threshold, operational definitions, and an H7 scoring note

- **H8 threshold.** PREREG §4 defines a blind week as one whose median daily detection opportunity is *below* the C1 25th percentile of cell-days. That percentile is 0 (44% of C1 cell-days have no clear overpass), so "strictly below" is an empty set. Used "median daily opportunity ≤ 0" (no clear look at all). Stated in `data/derived/results/h8_summary_meta.json`. The predicted "10–25 pp" winter recall drop was written against an imagined winter baseline far above the realised 0.5%; the realised drop is reported in pp and relative terms. No success criterion was attached to H8, so nothing changes in what counts as support.
- **Operational definitions fixed before any test was run** (not changes to PREREG, but choices it left open): detection window = fires with `acq_ts` in [event date 00:00 UTC − 12 h, 24:00 UTC + 12 h] within 1,000 m (EPSG:3035); "night" in the H1 strata = the event had at least one clear night overpass in its window; covariates come from the event's H3 res-6 cell over that window (min tcc for "tcc at overpass", share of night overpasses for day/night). GeoConfirmed event types were recovered from icon template codes because the API returns no type text (mapping in `scripts/analysis/01_events.py`). All recorded in the result metas.
- **H7 scoring note.** `predictions/transfer_v1.json` predicts recall at the model's own definition (1 km, 48 h). PREREG scores Karabakh at 5 km / ±2 days, a looser rule, so realised Karabakh recall should exceed the prediction for definitional reasons alone; the prediction is filed as is and the mismatch will be stated when T1 is scored. The prereg text also predicted "high" recall for Sudan; the model says 11.3%. Both filed before any T1/T2 download.
- **Data note.** Two Bellingcat ids appear twice with different coordinates; events are keyed by row, both kept.

## 2026-10-23: robustness item 7 (res-6 panel) deferred

PREREG §5 item 7 re-runs the panel tests on H3 res-6 cells. On that panel (98,182 C1 front cell-weeks, 1,888 clusters) the Webb wild-cluster bootstrap used more than 21 GB of memory and did not finish in two attempts (9,999 draws, then 999). Items 1–6 finished and are reported in `data/derived/results/robustness.csv`; item 7 rows are marked "not run". If item 7 is run later it will use CRV1 and Driscoll–Kraay only, and that change will be logged here before the result is read.

## 2026-10-27: H7 scoring — Karabakh event set, event precision, Sudan cadence

Written when `scripts/analysis/20_score_h7.py` was built; the event-set and precision choices below were fixed before the first run, and the criterion (±15 pp of the filed point prediction, both cases) is unchanged.
- **Karabakh event set.** PREREG names "dated settlement captures" for T1. No such list is on disk (searched `data/raw` and the manifests; only the scouting note in `planning/scout_transfer_cases.md` describes one). Karabakh is scored on UCDP GED 26.1 events with country Azerbaijan or Armenia inside the T1 AOI and window instead, at the PREREG H7 rule (5 km / ±2 days). UCDP events are battle and shelling locations, not settlement captures, so the denominator is a different kind of event than the one named.
- **Event precision (both cases, operational).** Primary = UCDP `where_prec` 1 (exact place) and `date_prec` 1 (single day): Karabakh n = 40, Sudan (adm_1 Darfur or Kordofan) n = 680. Sensitivity = `where_prec` ≤ 2 and `date_prec` ≤ 2, with the window spanning date_start..date_end. A 1 km rule on events placed only to within 25 km or a province would measure geocoding error, not the sensor.
- **Sudan cadence mismatch.** The filed Sudan prediction assumed S-NPP + NOAA-20 + NOAA-21 overpasses; the T2 fires on disk (PREREG T2: "S-NPP Sudan 2023–25") are S-NPP only. This pushes observed Sudan recall below the prediction for cadence reasons alone. The prediction is not refit.
- **"Karabakh lower".** The PREREG prediction's "Karabakh within band but lower" is read as lower than Sudan under the same detection rule (true at both 1 km and 5 km). The cross-rule primary comparison (Karabakh at 5 km vs Sudan at 1 km) is reported too, and goes the other way.
- **Inference.** Cluster bootstrap over event-days, 2,000 draws, percentile 95%; distances in a local azimuthal-equidistant projection centred on each AOI.

## 2026-10-27: ACLED added as an exploratory independent grader

- **What:** ACLED Ukraine events (shelling/missile, air/drone strike, battles; day-precise; town-level geo-precision primary) were matched to raw FIRMS detections with the H1 rule, with a ±7-day same-place placebo for the chance rate, and broken down by detection opportunity and H1 condition stratum. The same placebo was run on the V set for comparison. Script `scripts/analysis/21_acled_grade.py`.
- **Scope:** exploratory only. PREREG did not name ACLED; no hypothesis, criterion or confirmatory result changes. ACLED is not used to train, tune or score any model. Under the ACLED licence, all ACLED-derived outputs stay in gitignored `data/interim/acled/` and `figures/private_acled/`; the paper may cite aggregate numbers with attribution.

## 2026-10-27: Model v2 for P(detect) (exploratory, outside PREREG)

- **What:** `scripts/analysis/22_model_v2.py` fits a v2 detection model with features not in PREREG §4 H2 (sensor fire-mask cloud calibration of ERA5 tcc, cross-track swath position from CMR footprints with pixel-area weighting, WorldCover burnable/built-up fraction within 500 m, season × night and cloud × snow interactions). Approved by Jackson and noted in planning/DETECTION_MODEL.md (2026-10-22).
- **Why it is a deviation:** it was built after the confirmatory H2 result (logit AUC 0.737, criterion ≥ 0.75 not met) was known. It is labelled exploratory everywhere, does not change H2 or `verdicts.json`, and is reported next to v1, not instead of it.
- **Guardrails:** same events, drop rule and month-level split as H2 (seed 20261014); all feature-set and hyperparameter choices from 5-fold month-grouped CV on train months only; the test set scored once per final model; no ACLED or other external outcome data used.
- **Feasibility notes:** the sensor's own cloud flag exists only for sampled granules (2 days per ISO week per satellite) inside the 32.5–40E / 46.3–50.5N corridor (~18% of window overpass rows in the corridor); elsewhere a pooled calibration curve is used. Scan angle is approximated by cross-track ground-distance fraction from the 4-corner footprints (no per-pixel geolocation on disk). Burnable fraction is a 500 m disk around the event point, as in the DETECTION_MODEL note, not the whole h3 cell.
- **Result (exploratory):** test AUC v2 logit 0.765 [0.751–0.777], v2 LightGBM 0.765 [0.750–0.779] vs v1 logit 0.737 [0.724–0.749]; paired Δ (v2 − v1 logit) +0.028 [0.021–0.034].

## 2026-10-27: paper draft v1, notes the analysis agents reported but did not log

- **Model v2 pooled cloud curve.** The pooled fire-mask-vs-ERA5 calibration curve used for overpasses without a sampled granule was built from all sampled granules, test months included. It holds weather only (no detection labels), so no outcome leaks, but the test set is not fully untouched by v2's feature construction. Exploratory result; no verdict depends on it.
- **Placebo chance rate (exploratory).** The ±7-day same-place placebo reported next to H1 in the paper is not a PREREG criterion and is not matched on detection opportunity (cloudy event days sit next to clearer placebo days). H1's verdict is unchanged; the placebo is shown as context only.
- **H12 reading.** The H12 "opposite" answer is reported in the paper with the note already in `verdicts.json`: coefficients are negative at every lead and lag, so it is read as a period-level association, not timing. The criterion and the answer are unchanged.
- **verdicts.json coverage.** H1, H2, H3 and H8 verdicts live in `h1_recall_meta.json`, `h2_auc.json`, `h3_summary.json` and `h8_summary.json`, not in `verdicts.json`. The paper's scorecard reads them from there; no verdict was changed.
