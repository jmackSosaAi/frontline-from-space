# Front line from space: when a free fire satellite is blind to a war, and what it still shows

**Draft v1, 2026-10-27.** Jackson Mackney, University of Chicago (jmackney@uchicago.edu). Pre-registered as `prereg-v1` (git tag, 2026-10-22) and on OSF (registration https://osf.io/xd2zj/). Not peer reviewed.

> Status of this draft: every number below comes from a file in `data/derived/results/`, `data/derived/telegram/` or `predictions/` (or, for ACLED, a private aggregate in `data/interim/acled/`). Results marked **exploratory** were not in the pre-registration or were built after seeing a confirmatory result. Everything else is **confirmatory** and is scored against the criterion written before the data were opened.

## Abstract

Analysts and journalists use NASA's free FIRMS fire feed (VIIRS, 375 m) as a witness to the war in Ukraine. Nobody had measured how often it misses. We pre-registered 14 hypotheses and scored them against 45,876 geolocated strike and battle events, a weekly settlement-control panel, and two wars it was never fit on. FIRMS caught 5.0% of held-out confirmed events. Under clear night skies in summer it caught 7.4%. On cloudy or snowy winter days it caught 0.06%. A pre-registered detection model reached AUC 0.737, short of the 0.75 we set. Two satellites passing 30–70 minutes apart under clear sky agreed on 54% of fires. Russia's territorial gains did not cluster in the weeks the sensor was blind (22%, against the 30% we predicted). What the fire record still says is mostly no. Front fires are elevated (2.1× the pre-war same-week baseline) but not 3×. Fires do not lead Russian gains at a size that matters: with raw fires the test is inconclusive, and after correcting for what the sensor could see, the 90% interval sits inside the smallest effect we pre-registered as meaningful (equivalence). An exploratory ±7-day placebo matches 3.8% of events at the same place on other days, against 5.0% on the event day, so most of the raw match rate is background fire. FIRMS is a real but thin witness. Read its zeros as "could not see" before "nothing happened."

## 1. The question

How reliable a witness is a free thermal satellite feed to a ground war, when is it blind, and what can it still tell an analyst?

Published work that uses FIRMS in war treats a detection as a fire and a zero as no fire (Bellingcat 2022; The Economist war-fire model; Tomchenko 2023; Dingemanse et al. 2026). None of it measures how often the sensor misses a real event, or separates "looked and saw nothing" from "could not look." This paper measures that.

The paper has two halves and keeps to them.

1. **A blindness map.** When and where FIRMS cannot see the war, and why.
2. **What the fire record alone still reveals.** Where fire sits relative to the front, and whether it tells you anything about where the front is going.

Other sources (GeoConfirmed, Bellingcat, Telegram, ACLED, UCDP) appear here only to grade the satellite. They do not replace it.

## 2. Data

| Set | What | Period | Role |
|---|---|---|---|
| Fires | VIIRS 375 m active fire, S-NPP, NOAA-20, NOAA-21 (from 2023-03), confidence nominal or high | 2012–2025 | The witness being tested |
| B | S-NPP Ukraine 2012–2021 | pre-war | Same-cell, same-week baseline; H14 |
| V | GeoConfirmed and Bellingcat TimeMap geolocated events, 45,876 in Ukraine | 2022-02-24 → 2025 | Ground truth for recall (H1, H2, H8); split by calendar month 70/30, seed 20261014; test set n = 14,736 |
| O | CMR granule footprints (overpasses), ERA5 total cloud cover, ERA5-Land snow depth, VNP14IMG/VJ114IMG fire-mask sample | 2022 → 2025 | Detection opportunity |
| C1 | Fires + VIINA daily settlement control (Zhukov), Voronoi km² | 2022-04-03 → 2024-07-07 | Confirmatory panel (H4–H6, H9–H12); untouched until the tag |
| E | Fires + VIINA 2025 | 2024-07-08 → 2025-12-31 | Fixing constants; H13 (exploratory) |
| T1 | S-NPP Azerbaijan/Armenia + UCDP GED | 2020-09-27 → 2020-11-10 | Transfer test, Karabakh (H7) |
| T2 | S-NPP Sudan + UCDP GED, Darfur and Kordofan | 2023-04-15 → 2025-12-31 | Transfer test, Sudan (H7) |

Territorial control comes from VIINA, not DeepStateMap or ISW. DeepState declined API permission and ISW geodata needs written consent, which we asked for and did not receive. No DeepState or ISW geometry is used or redistributed.

Two more event sources are used only as exploratory graders: public Telegram posts from Ukrainian official and monitoring channels (DEVIATIONS 2026-10-22), and ACLED (DEVIATIONS 2026-10-27).

## 3. Methods

**Pre-registration.** `PREREG.md` was signed on 2026-10-22, tagged `prereg-v1` and registered on OSF before any C1, T1 or T2 data were downloaded. It fixes the grid, the front definition, the matching rule, the smallest effect size of interest (SESOI) and a prediction for every hypothesis. Every change after the tag is dated in `DEVIATIONS.md`. Every figure caption says whether it is confirmatory or exploratory.

**Holdouts.** Three sets were untouched at the tag: C1 (the Ukraine panel), T1 (Karabakh) and T2 (Sudan). The V events were split by calendar month into train and test months with a seeded draw. The detection model was fit on train months and scored once on test months.

**Matching rule.** An event counts as detected if at least one VIIRS fire lies within 1 km and was acquired between 12 hours before the event date starts and 12 hours after it ends (a 48-hour window, because the events are dated to the day, not the hour). The H7 Karabakh rule, written in PREREG, is looser: 5 km and ±2 days.

**Detection opportunity.** For each H3 cell and day: the number of overpasses whose swath covers the cell, with ERA5 cloud cover below 0.5 at the overpass hour and snow depth below 1 cm. Summed to cell-week for the panel.

**Panel.** H3 resolution-5 cells (~250 km²) by ISO week. Front cells have a centroid within 15 km of the weekly line between Russian- and Ukrainian-held settlement polygons (10 and 25 km as robustness). The outcome is net km² that changed from Ukrainian to Russian control. The lead–lag specification (H6) regresses net gain over t+1..t+4 on log(1+fires) at t, four lags of the outcome and detection opportunity, with cell and week fixed effects. Inference uses both a wild-cluster bootstrap by cell (Webb weights, 9,999 draws) and Driscoll–Kraay standard errors (lag 4); "significant" means p < 0.05 under both. The SESOI is 1.70 km² per log-unit of fire, half the mean absolute 4-week change in front cells in 2025, fixed before C1 was opened. H6b swaps raw fires for a corrected index: raw fires divided by the modelled probability of detection, with model uncertainty propagated.

## 4. Results, part 1: the blindness map

### 4.1 How often FIRMS sees a confirmed event (H1, confirmatory)

FIRMS caught **5.0%** of V-test events (95% CI 4.7–5.4; n = 14,736). In the best conditions, clear sky, a clear night overpass, June to September, it caught **7.4%** (n = 3,389). In the worst, cloud or snow, no clear night look, November to February, it caught **0.06%** (n = 3,147). The best/worst ratio is 117 (bootstrap lower bound 44; the upper bound is undefined because 13.5% of draws had zero worst-stratum detections).

**Verdict: supported** (criterion: overall recall < 50% and best ≥ 3× worst). Figure: `figures/h1_recall_strata.png`, `figures/h1_recall_event_type.png`.

Most confirmed strikes are small, short, or not fires at all. A 375 m sensor that passes a few times a day was never going to see most of them. The point is the gradient. In a Ukrainian winter the sensor is effectively off.

### 4.2 Can you predict when it misses? (H2, confirmatory)

A logistic model on the pre-registered features (cloud at overpass, snow, hours since the last overpass, day/night, land cover, event type, month) reached test AUC **0.737** (95% CI 0.724–0.749). LightGBM with the same features reached 0.727 (0.712–0.743).

**Verdict: not supported** (criterion: logit AUC ≥ 0.75). The AUC is above the 0.65 floor, so the corrected index in H6b is reported as a point estimate with intervals, not as bounds only. Figures: `figures/h2_roc_calibration.png`, `figures/h2_coefficients.png`.

**Exploratory: model v2.** After seeing the H2 result we built a second model with features PREREG did not name: a cloud term calibrated to the sensor's own fire-mask cloud flag, cross-track position in the swath (edge pixels are about 4.2× the area of nadir pixels), the burnable and built-up fraction within 500 m, and season × night and cloud × snow interactions. All choices were made by cross-validation on train months only, with one exception: the pooled cloud calibration curve used for overpasses without a sampled granule was built from weather data in all months, test months included (no detection labels; DEVIATIONS 2026-10-27). On the same test set, v2 reached AUC **0.765** for both the logit (0.751–0.777) and LightGBM (0.750–0.779). The paired gain over v1 logit is +0.028 (0.021–0.034). The largest gain was in summer. Built-up fraction was the strongest new feature by LightGBM gain, which may partly stand in for what kind of place was hit (cities, depots, refineries) rather than fire physics. **v2 does not rescue H2.** It was designed after the result was known, and H2 stays not supported. Figure: `figures/model_v2_vs_v1.png`. Source: `data/derived/results/model_v2.json`.

### 4.3 Do two satellites agree? (H3, confirmatory)

For S-NPP detections with a NOAA-20 pass over the same cell 30–70 minutes away under cloud cover below 0.3, **53.6%** had a NOAA-20 detection within 1 km (95% CI 53.3–54.0; n = 82,247 pairs). The reverse direction gives 52.4%. All four season × day/night strata fall inside the band.

**Verdict: supported** (criterion: 40–70%). Figure: `figures/h3_concordance.png`.

This needs no ground truth. Two near-identical sensors looking at the same ground within an hour, with a clear sky, agree only about half the time. Single detections are noisy. A single zero means very little.

### 4.4 The sensor's floor moves with the season (H14, confirmatory)

On pre-war Ukraine fires (2012–2021), the 5th-percentile fire radiative power was **2.22 MW** on summer days and **0.58 MW** on winter nights, a ratio of **3.83** (95% CI 3.75–3.83). On V events the same ratio for detected fires was 3.03.

**Verdict: supported** (criterion: ratio ≥ 1.5). Figure: `figures/h14_frp_floor.png`.

Hot summer ground hides small fires by day. So the summer-day fire record is a record of big fires only. That is why the big/small cutoff in H10 is set separately for each season and day/night.

### 4.5 Losing a satellite (H8, confirmatory, descriptive)

S-NPP is expected to stop in early November 2026. With S-NPP removed from both fires and overpasses, V-test recall fell from 5.0% to **4.3%** (−0.69 pp, CI −0.92 to −0.48; a 14% relative drop). In November–February it fell from 0.52% to 0.43%. A blind week here is one where the median day has no clear overpass at all, since the pre-registered 25th-percentile threshold is zero (DEVIATIONS 2026-10-22). Without S-NPP, north-east cells gain **1.1** blind weeks a year on average (20.8 → 21.9), and 2.3 weeks in 2022.

H8 had no success criterion. Both directional predictions missed: the winter recall drop is far below the predicted 10–25 pp, because winter recall was already near zero, and the north-east blind season grew by less than the predicted 2 weeks on average. Figures: `figures/h8_recall_noSNPP.png`, `figures/h8_blind_season.png`.

Ukraine is blind for about 21 weeks a year with the full constellation.

### 4.6 Did Russia gain ground while the sensor was blind? (H4, confirmatory)

The validation gate passed: more detection opportunity means more fires recorded (β = 0.0037 per unit, p < 0.001 under both methods). Then: **21.8%** of the 29,911 km² Russia gained in C1 front cells fell in the bottom quartile of detection opportunity (95% CI 17.6–26.2). Those cell-weeks are 25.0% of all front cell-weeks, so gains fell there at about their share of time.

**Verdict: not supported** (criterion: CI excludes 30% from below). Single-source control columns give 12.8% (DeepState via VIINA), 17.7% (ISW via VIINA) and 25.5% (Wikipedia via VIINA). Figure: `figures/h4_blindspot.png`.

Russia did not gain disproportionately while the satellite could not see. The blind spot is real, but gains did not concentrate in it, at least at this resolution.

### 4.7 Blindness outside Ukraine (H7, confirmatory)

Before downloading the Karabakh and Sudan data, we used the Ukraine model to file predicted recall for both (`predictions/transfer_v1.json`, written 2026-10-22). Scored on UCDP GED events with an exact location and a single-day date:

| Case | Rule | Observed | Predicted (90% interval) | Gap |
|---|---|---|---|---|
| Karabakh 2020 | 5 km / ±2 d (PREREG) | **12.5%** (2.9–22.5), n = 40 | 3.0% (2.3–3.9) | +9.5 pp |
| Sudan, Darfur/Kordofan | 1 km / ±12 h (PREREG §3) | **2.9%** (1.3–5.1), n = 680 | 11.3% (10.6–12.2) | −8.3 pp |
| Karabakh | 1 km / ±12 h | 0.0% (0/40) | – | – |
| Sudan | 5 km / ±2 d | 17.6% (14.2–21.5) | – | – |

**Verdict: supported** (criterion: both cases within ±15 pp of the filed prediction). Figures: `figures/h7_transfer.png`, `figures/h7_transfer_predictions.png`.

This pass is weak evidence and should be read that way. The band's floor is zero for both predictions, so the test could only fail from above. The two cases miss in opposite directions. Neither observed value falls inside its filed 90% interval. The pre-registration called Sudan recall "high"; it is 2.9%. The Karabakh prediction was filed at the model's 1 km / 48 h definition but is scored at the PREREG 5 km / ±2 d rule, so that comparison is not like for like; at the prediction's own 1 km rule Karabakh caught 0 of 40 (DEVIATIONS 2026-10-22). Part of the Sudan gap is mechanical: the prediction assumed three satellites, the T2 data are S-NPP only. And Karabakh is scored on UCDP battle and shelling locations, not the dated settlement captures PREREG named, because no capture list exists on disk (DEVIATIONS 2026-10-27). We read "Karabakh lower" as a comparison under one common detection rule, the only like-for-like reading, and on that reading it holds (0% vs 2.9% at 1 km; 12.5% vs 17.6% at 5 km).[^karabakh]

[^karabakh]: Across each case's primary rule (Karabakh at 5 km / ±2 d, Sudan at 1 km / ±12 h) Karabakh is higher, 12.5% vs 2.9%. Comparing across rules mixes sensor recall with window size, so we do not use it.

The honest summary: the band passed, the model's calibration did not transfer. What did transfer is the main finding of part 1. In two very different wars, FIRMS sees a small minority of events.

### 4.8 Independent graders (exploratory)

**ACLED.** We matched ACLED Ukraine events (shelling and missile, air and drone strikes, armed clashes, territorial change; day-precise; town-level coordinates) to FIRMS with the H1 rule. ACLED was not used to train, tune or score any model. For geo-precision 1 events from 2022-02-24 to 2025-12-31 (n = 91,447), recall was **3.0%** (95% CI 2.9–3.1).

It shows the same blindness map, built by different people from different sources. Recall rises steadily with the number of clear overpasses on the event day: 0.8%, 1.9%, 2.0% and 4.9% for 0, 1, 2 and 3+ overpasses (all 45,876 V events, train and test: 2.2%, 4.7%, 5.9%, 9.8%). The 3+ vs 0 ratio is 6.2 for ACLED and 4.5 for all V events (5.6 for V-test). In the H1 worst stratum ACLED recall is 0.17%, against 5.9% in the best (all V events: 0.73% vs 12.5%). Winter recall is 1.1% against 4.6% in summer.

**Most raw matches are background fire (exploratory).** We re-ran the match at the same place with the window shifted 7 days earlier and 7 days later. That placebo hits 2.3% of ACLED events, against 3.0% real recall. On V-test events, the placebo is **3.8%** against H1's 5.0%. Recall clearly beats chance only with 3+ clear overpasses or in the H1 best stratum, at about 1.4–1.5× chance for both sources. With zero clear overpasses, recall falls below the placebo. One likely reason is that the placebo is not matched on opportunity: a cloudy event day sits next to clearer placebo days. This does not change the H1 verdict (H1 had no chance-rate criterion), but it changes how H1 should be read: a match at the same spot on a nearby day (3.8%) is nearly as common as a match on the event day (5.0%), so most of the 5% match rate cannot be credited to the event itself.

Week to week, ACLED event counts and FIRMS counts on front cells barely agree (Pearson on log counts 0.21; 0.14 after removing cell and week means). ACLED records the war's tempo. Fires record that plus season and farming.

Source: Armed Conflict Location & Event Data (ACLED); acleddata.com, accessed 2026-10-26. Only aggregate numbers are reported; no ACLED-derived file is published.

**Telegram.** Of 18,404 geocoded strikes reported by Ukrainian regional administrations and monitoring channels, FIRMS matched **1.26%** within 1 km / ±12 h, against a placebo of 0.65% (`data/derived/telegram/firms_match_cellweek_meta.json`). Most of these reports are of residential targets (9,009 of 18,404), and the largest classified weapon type is Shahed-type drones (4,206; 8,642 are unclassified). The sensor almost never sees them.

## 5. Results, part 2: what the fire record still reveals

### 5.1 Where the war burns (H5, confirmatory)

Front-cell fire density in C1 was **2.12×** the same cells' 2012–2021 same-week baseline overall. The ratio reached 3× in **2 of 12** calendar months (0 of 12 with the CI lower bound at 3).

**Verdict: not supported** (criterion: ≥ 3× in ≥ 9 of 12 months). Figure: `figures/h5_monthly_ratio.png`.

We expected this to pass; it had been shown descriptively before. Fire on the front is clearly elevated, roughly double, but less than we thought once the baseline is the same cell and the same week, so farm burning cancels out. ACLED intensity does not explain the monthly pattern (Spearman −0.09 across C1 months, exploratory; ACLED attribution in §4.8).

### 5.2 Do fires lead territorial change? (H6 and H6b, confirmatory, pre-registered null)

With raw fires, β = **0.98** km² per log-unit (90% CI 0.13–1.82 under CRV1; −0.09–2.04 under Driscoll–Kraay; p = 0.057 wild bootstrap, 0.131 Driscoll–Kraay). **H6: inconclusive.** The CI neither excludes zero under both methods nor fits inside ±1.70.

With the corrected index, β = **0.13** (90% CI −0.29–0.55, including model uncertainty). **H6b: equivalence.** The effect is inside ±SESOI.

Prediction ("equivalence or inconclusive for both"): correct. The category changed between H6 and H6b, which PREREG flagged as a headline result. Once you account for when the sensor could see, the small raw association between fires and next month's Russian gains shrinks toward zero, which suggests some of the raw signal was the sensor's visibility, not the war. Two cautions: the two β are on different regressors (log raw fires vs log corrected index), so their sizes are not directly comparable; and the raw-fire category is itself fragile, since H6 reaches equivalence in four robustness variants (§6). Figure: `figures/h6_lead.png`.

### 5.3 Lead time (H9, confirmatory)

Jackson predicted that strikes and gains happen almost together: the largest β at lead 0 or 1 week, and nothing meaningful from 2 weeks on. The largest β was at **8 weeks** (0.98, significant under both methods). Leads 0 and 1 were small (0.13 and 0.32, neither significant). Only 1 of 5 leads at 2+ weeks passed the equivalence test.

**Verdict: not supported.** Figure: `figures/h9_leads.png`. An 8-week lead was not predicted by anyone. It may reflect seasonal timing of offensives rather than fire causing anything, and we do not interpret it further here.

### 5.4 Fire size and side of the line (H10, confirmatory)

Prediction: (a) big fires on the Ukrainian-held side lead to more Russian gain; (b) small fires on the Russian-held side lead to less. Result: (a) β = −1.33 (p = 0.056 / 0.069), wrong sign; (b) β = −2.83 (p < 0.001 / 0.035), holds. The largest term was one nobody predicted: small fires on the Ukrainian-held side, β = 4.41 (p < 0.001 under both).

**Verdict: not supported** (both (a) and (b) required). Figure: `figures/h10_size_side.png`. The small-fire Ukrainian-side term is a post-hoc observation and is treated as exploratory.

### 5.5 Phase and season (H11, H11s, confirmatory)

Prediction: in the manoeuvre phase (to 2022-11-30) more fire means more movement; in the attrition phase after it, more fire means less. Result: β_A = 1.16 (not significant), β_B = 0.87 (significant under both), difference 0.28 (p = 0.83). Both positive. **H11: not supported.** Prediction that summer is stronger than winter within each phase: interactions not significant in either phase. **H11s: not supported.** Figure: `figures/h11_phase.png`.

### 5.6 Kyiv strikes (H12, confirmatory, open question)

National weekly Russian gain regressed on FIRMS fires inside Kyiv city at leads and lags of −4 to +4 weeks gives negative coefficients at every lead and lag (for example −2,722 km² per log-unit in the same week, 90% CI −4,009 to −1,435). The pre-registered rule labels this **"opposite."**

That label should not be read as timing. C1 contains only 29 Kyiv fires, in 19 of 118 weeks, and all nine lead and lag terms are fit together on those weeks. The coefficients are similar in size and negative both before and after the gain, which looks like a period-level association rather than timing (an interpretation; we did not test which periods drive it). Night fires only, or the DeepState-only outcome, turn it inconclusive. Over the full span to 2025 (301 fires, exploratory) the answer is inconclusive. Telegram Kyiv strike counts and Air Force launch totals show no relationship (exploratory). Figure: `figures/h12_kyiv.png`.

### 5.7 Deep strikes (H13, exploratory by pre-registration)

H13 used 2024-07 to 2025-12 data, which were not held out, so it was exploratory from the start. Big fires more than 30 km behind the Russian side of the line were counted nationally each week. Cell-panel β = 3.0, inconclusive. The national-level version gives a positive association (566 km² per log-unit). **Verdict: inconclusive** against the predicted equivalence. Russian agricultural burning dominates this count, so it is a poor measure of Ukrainian deep strikes. Figure: `figures/h13_deep.png`.

### 5.8 Scorecard

| H | Question | Verdict | Prediction right? |
|---|---|---|---|
| H1 | Recall < 50%, best ≥ 3× worst | supported | yes |
| H2 | Detection model AUC ≥ 0.75 | not supported (0.737) | no |
| H3 | Paired looks agree 40–70% | supported (53.6%) | yes |
| H4 | ≥ 30% of gains in blind weeks | not supported (21.8%) | no |
| H5 | Front fires ≥ 3× baseline in 9/12 months | not supported (2/12) | no |
| H6 | Fires lead gains (raw) | inconclusive | yes |
| H6b | Fires lead gains (corrected) | equivalence | yes |
| H7 | Transfer within ±15 pp | supported (weak) | band yes; "Sudan high" no; "Karabakh lower" yes under a common rule (4.7) |
| H8 | Constellation loss | descriptive | both directions missed |
| H9 | Lead ≤ 1 week | not supported (peak 8 weeks) | Jackson no |
| H10 | Fire size × side | not supported | Jackson no |
| H11 / H11s | Phase flip / summer | not supported | Jackson no |
| H12 | Kyiv strikes | "opposite" (period effect) | no prediction |
| H13 | Deep strikes (exploratory) | inconclusive | no |
| H14 | Seasonal FRP floor ≥ 1.5× | supported (3.83×) | yes |

Source: `data/derived/results/verdicts.json` plus the H1–H3 and H8 summaries.

## 6. Robustness

The pre-registered list (front band 10/25 km, rear-strip reference, night-only fires, drop-one-oblast jackknife, single-source control columns, reverse direction and lead-2 placebo) ran 135 rows. Seven rows are flagged as flips: six variants that changed a verdict plus the jackknife summary row (`data/derived/results/robustness_summary.json`):
- H6 moves from inconclusive to equivalence with a 10 km band, when dropping either of two oblasts, or with DeepState-only control. It never moves toward "supported."
- H12 moves from "opposite" to inconclusive with night-only fires or DeepState-only control.

H4, H5, H9, H10, H11 and H11s kept their verdicts in every variant that was run (a few night-only variants could not be built for H5, H10 and H13). H6b stayed at equivalence in all 13 variants. Item 7 (a res-6 panel) was not run: the wild bootstrap used more than 21 GB of memory twice (DEVIATIONS 2026-10-23).

## 7. Limitations

- **Filmed-event bias.** GeoConfirmed and Bellingcat geolocate what someone filmed and posted. That favours daytime, dramatic and urban events. The recall here is recall of filmed events, not of all violence.
- **Day-precision dates.** Most events are dated to the day, so the window is 48 hours. A wider window raises recall and also raises chance matches, as the placebo shows.
- **Chance rate not pre-registered.** The ±7-day placebo came after H1 and is not matched on opportunity.
- **Control data.** VIINA is settlement-level and majority-vote across sources. It is coarse at the edge of the line.
- **Small samples where it matters.** Karabakh has 40 events; Kyiv has 29 fires in C1.
- **Model v2's strongest feature** (built-up fraction) may encode what was hit, not what the sensor can see.
- **Terms of use.** ACLED's licence bars sharing derived data and using it to train or test models, so ACLED appears as aggregates only. Telegram posts are used under Telegram's terms: no model was trained on them and only cell-week aggregates are published.

## 8. Future work

- Score H6/H6b on the res-6 panel with CRV1 and Driscoll–Kraay only (logged before reading).
- Repeat the H8 blindness map after S-NPP actually stops, against the prediction made here.
- A second instrument that sees through cloud, such as Sentinel-1 radar change or an existing damage-assessment product, as a third witness (a separate project).

## 9. Data and code availability

**Public** (GitHub, after release): all code (MIT); pre-registration, deviations and predictions; derived data at cell-week or coarser with at least a 7-day lag (CC BY 4.0; VIINA derivatives under ODbL); result tables and figures in `data/derived/` and `figures/`.

**Not public, and why:**
- Raw FIRMS, ERA5 and CMR files: public at source; re-fetch with `scripts/` and check against `data/MANIFEST.json`.
- Point-level V events and matched detections: point-level front data are an operational-security risk and are kept out on purpose.
- Telegram post text: kept private; only cell-week and week aggregates are published.
- ACLED: licence. Nothing ACLED-derived is published; the numbers in §4.8 are cited with attribution.
- DeepStateMap and ISW geometry: not used and not redistributed.

## 10. References and sources

- NASA FIRMS / LANCE, VIIRS 375 m active fire product (S-NPP, NOAA-20, NOAA-21). Schroeder, W., Oliva, P., Giglio, L. and Csiszar, I. (2014). The New VIIRS 375 m active fire detection data product. *Remote Sensing of Environment* 143: 85–96.
- Hersbach, H. et al. (2020). The ERA5 global reanalysis. *QJRMS* 146: 1999–2049. Contains modified Copernicus Climate Change Service information.
- Muñoz-Sabater, J. et al. (2021). ERA5-Land. *Earth System Science Data* 13: 4349–4383.
- Zhukov, Y. VIINA: Violent Incident Information from News Articles, github.com/zhukovyuri/VIINA (ODbL). [verify preferred citation]
- Sundberg, R. and Melander, E. (2013). Introducing the UCDP Georeferenced Event Dataset. *Journal of Peace Research* 50(4): 523–532. UCDP GED version 26.1.
- Raleigh, C., Linke, A., Hegre, H. and Karlsen, J. (2010). Introducing ACLED. *Journal of Peace Research* 47(5): 651–660. Armed Conflict Location & Event Data (ACLED); acleddata.com, accessed 2026-10-26.
- GeoConfirmed (geoconfirmed.org); Bellingcat, Civilian Harm in Ukraine TimeMap.
- ESA WorldCover 2021 (CC BY 4.0). [verify: Zanaga et al. 2022, v200]
- NASA CMR granule metadata for VNP14IMG / VJ114IMG / VJ214IMG.
- The Economist war-fire model, github.com/TheEconomist (CC BY 4.0). Used only as a 2022–23 national sanity check.
- Webb, M. D. (2023). Reworking wild bootstrap-based inference for clustered errors. *Canadian Journal of Economics* 56(3).
- Driscoll, J. C. and Kraay, A. C. (1998). Consistent covariance matrix estimation with spatially dependent panel data. *Review of Economics and Statistics* 80(4): 549–560.
- Ke, G. et al. (2017). LightGBM. *NeurIPS*.
- Uber H3 hierarchical hexagonal grid.
- Prior FIRMS-in-war work named in §1: Bellingcat (2022); Tomchenko (2023); Dingemanse et al. (2026). [verify full citations]
- Pre-registration: OSF registration https://osf.io/xd2zj/ (project https://osf.io/3whtz/); git tag `prereg-v1`.
