# Front line from space — project plan (novelty-first draft)

**Key:** novelty · **Written:** 2026-10-13 · **Planner angle:** own a claim nobody has published, then make it rigorous and shippable.
**Inputs read:** all eight `scout_*.md` files in this folder; `Conflict_Data_Feasibility/frontline/{VERDICT,FIRST_PASS,SOURCES}.md` and `out/*.csv`; `Conflict_Data_Feasibility/airdefense/VERDICT.md`. Five web checks run today are cited inline and flagged where they changed the plan.

**Verification tags used below:** [V] verified by a scout or by me today (URL fetched, file sized, or number recomputed); [S] scout finding not independently re-verified; [U] unverified, confirm before relying on it.

---

## 0. The claim we are going to own

Every published use of satellite fire data in war (Bellingcat 2022, The Economist's war-fire model, Tomchenko 2023, Dingemanse/Zhizhin/Cerra 2026, Yale HRL, Myanmar Witness) treats a zero as a zero. None of them separates **"the sensor looked and saw no fire"** from **"the sensor did not look"** (cloud, snow, no overpass, bow-tie deletion, not processed) from **"it looked, saw fire, and the fire was agriculture."** The feasibility pass found that 44% of Ukraine sector-weeks have zero front-band detections and that the sensor is effectively blind November–February. Nobody knows how much of that blindness is physics (no clear look) versus fuel (clear look, nothing burning) versus war type (fighting that does not burn). That decomposition is the claim. In one sentence:

> **The first observability-adjusted assessment of a free thermal satellite feed in a war: for every 50 km sector and week of the Russia–Ukraine war since April 2022, how many clear looks the VIIRS constellation actually had, what share of territorial change happened in sector-weeks the sensor could not see, and whether the same accounting transfers to a maneuver war (Nagorno-Karabakh 2020) and a raiding war (Sudan 2023–).**

Three things make this claim ownable rather than merely new:

1. **It is built from the fire algorithm's own cloud decisions.** The VNP14IMG 375 m fire-mask SDS has ten classes: 0 not processed, 1 bow-tie deletion, 2 sun glint, 3 water, 4 cloud, 5 land, 6 unclassified, 7–9 fire at low/nominal/high confidence [V — VIIRS C2 375 m Active Fire User Guide v1.2, June 2025, Table 1, extracted today from https://www.earthdata.nasa.gov/s3fs-public/2025-06/VIIRS_C2_AF-375m_User_Guide_1.2.pdf]. FIRMS distributes only classes 7–9 as points. The other classes are the "did it look" record and they sit unused in the LAADS archive. Reading them turns the FIRMS point file into a two-sided instrument.
2. **It is timely.** NOAA/NESDIS will cease Suomi NPP science-data delivery at 13:00 UTC on 2 November 2026 [V — NASA Earthdata alert, updated 5 Oct 2026, https://www.earthdata.nasa.gov/data/alerts-outages/suomi-npp-observations-cease-november-2-2026]. Every FIRMS war analysis to date rests on S-NPP. The project ships a sensor-continuity check (does NOAA-20 + NOAA-21 reproduce S-NPP's front-band density and seasonal envelope?) three weeks after the switch-off. No one else will have this ready.
3. **It is the generalization answer.** Overpass geometry, cloud climatology, snow and fuel are physics, not Ukraine. The same ledger, run on Nagorno-Karabakh 2020 (autumn, mountains, 44-day maneuver war) and Sudan 2023– (arid, inverted fire season, raiding), is the direct response to "your results are Ukraine-specific."

The pre-registered lead-lag null (does fire lead territorial change?) remains in the plan as the disciplined companion result, because it is the question an interviewer will ask and because a null with placebo, reverse and equivalence tests is itself unpublished. But it is the second chapter, not the title.

### 0.1 Thesis paragraph (for the brief and README)

A free 375 m thermal feed shows where a war is burning but is widely read as if "no detection" meant "nothing happened." Using NASA FIRMS active-fire detections (S-NPP, NOAA-20, NOAA-21), the fire algorithm's own per-pixel cloud and quality masks, and two independent open codings of territorial control (DeepStateMap and ISW/CTP), this project builds a sector-week **observability ledger** for the Russia–Ukraine line of contact from April 2022 to the present, decomposing every sector-week into clear looks, obscured looks, and no looks, and classifying detections against a 2012–2021 pre-war baseline. We then (i) measure how much of Russia's territorial gain occurred in sector-weeks the sensor could not see, (ii) run a pre-registered fixed-effects panel test of whether front-band fire leads territorial change once observability and momentum are controlled, with placebo, reverse-direction and equivalence tests, (iii) test sensor continuity across the S-NPP shutdown, and (iv) run the same ledger on Nagorno-Karabakh 2020 and Sudan 2023– to show which parts of the answer are physics and which are Ukraine. Deliverables: a public repository with a reproducible pipeline, a dashboard with a weekly observability strip, a 5–8 page brief, a Zenodo DOI, and a two-page side note documenting a reporting-regime break in Ukraine's drone intercept statistics.

### 0.2 Pre-registered hypotheses (lock these in `PREREG.md` before pulling any new data)

Each hypothesis has a stated prediction, a success criterion, and a failure criterion. "Confirmatory sample" = 2022-W14 to 2024-W27 (DeepState API backfill + NOAA-20), which no one has analysed. The Jul 2024–Dec 2025 panel already searched (~10 specs) is labelled exploratory everywhere.

| # | Hypothesis | Prediction | Success criterion | Failure criterion | Stamp of the mechanism |
|---|---|---|---|---|---|
| **H1 Observability** | A material share of territorial change occurs when the sensor cannot see. | ≥30% of Russian km² gained 2022-04→2025-12 falls in sector-weeks with observability in the bottom quartile (fewer than Q1 clear looks). | ≥30% and the observability index predicts log front fires with sector + week-of-year FE, coefficient >0, p<0.01 (validity check). | <15% of gains in low-observability weeks: the sensor is blind to fuel, not to the war; reframe the product as a fuel calendar. | Physics: High · mechanical |
| **H2 Decomposition** | Winter zeros are mostly "no clear look," not "clear look, no fire." | In Nov–Feb, ≥60% of zero-detection front sector-weeks have <2 clear looks. | As predicted. | <40%: winter blindness is fuel/snow, which still transfers but shifts the brief's language from cloud to fuel. | Physics: High · mechanical |
| **H3 Lead** | Front fires do not lead territorial change beyond momentum. | β on log(1+front fires) in the primary spec (4-week cumulative outcome, momentum lags 0–3, observability covariate, sector + week FE) is not significant under both CRV1-by-sector and Driscoll–Kraay(4); 90% CI inside the equivalence bound of ±2 km² per doubling. | Null confirmed under both SEs and the equivalence bound → "concurrent indicator, not leading." | β>0, p<0.05 under both SEs **and** rolling-origin MAE improves ≥5% vs momentum-only → report a positive lead, with the phase split (H4) as the explanation. | D008 saturated-linear regime: High · documentary; D011 symmetry: Med · elicited |
| **H4 Phase** | Lead exists, if anywhere, only in maneuver phases. | β is larger in sector-weeks coded `porous-linear`/collapse (Kharkiv Sep–Oct 2022, Kherson Oct–Nov 2022, Zaporizhzhia Jun–Aug 2023 breach sectors) than in `saturated-linear` weeks. Pre-registered expectation: fires **trail** the Kharkiv advance. | Interaction β×phase significant and positive. | No phase difference → the lead is absent in all regimes; the method is a locator, full stop. | D008/D011 as above |
| **H5 Continuity** | NOAA-20/21 reproduce S-NPP. | Monthly front/rear density ratio from NOAA-20 alone is within ±25% of S-NPP's for every month Jul 2024–Dec 2025; seasonal envelope correlation >0.9. | As predicted. | Ratios diverge >25% in ≥3 months: document the break; it becomes a finding about the sensor transition, not a failure. | Mechanical |
| **H6 Transfer (physics)** | The blind-season calendar is a climate property. | Sudan nodes (El Fasher, Khartoum, Kordofan corridors) have <15% zero-detection weeks in Oct–May; Ukraine front has >40% in Nov–Feb. NK 2020 shows ≥3× anomaly vs 2012–19 baseline in 26 Oct–4 Nov, reproducing CEOBS's 447-fire count ±10%. | Both. | Sudan shows comparable blindness → the limit is overpass cadence, not fuel; VERDICT's "arid theatres improve it" claim is wrong and we say so. | D015 Gate 1: Med-High · elicited |
| **H7 Transfer (war type)** | In a maneuver war fires trail the advance. | NK 2020: fire anomaly within 5 km of captured settlements peaks after announced capture date (median lag >0 days). | Median lag >0 with bootstrap CI excluding 0. | Median lag ≤0 → fires lead in maneuver war; strengthens H4 if H4 also positive. | D011 asymmetric branch: Med · elicited |
| **H8 Side piece** | Ukraine's drone intercept rate changed when the reporting category set changed. | Destroyed-only rate dips exactly when the "EW-lost" category appears (2024 Q4) and recovers when it exits (2025 Q4); destroyed+EW-lost is flat 2024–26. Mirror B and KAS monthly figures show the same timing. | Both mirrors agree. | Mirror B shows the dip without the category change → the dip is real; publish that instead. | D010 mode 9: Med-High · elicited |

Inference rules, fixed: significance requires both CRV1-by-sector and DK(4) p<0.05; wild cluster bootstrap (Webb, 9,999 draws) reported alongside because N=22 clusters. Effect-size floor: a doubling of fires must imply ≥2 km² additional 4-week advance (one sample-mean week) to count as "practically meaningful." No new hypotheses after the pre-registration commit; deviations go in `DEVIATIONS.md` with dates.

---

## 1. Scope

### In
- Ukraine line of contact, 2022-04-03 (first DeepState API snapshot) to the latest complete week; Russian-side border sectors (Kursk, Belgorod) via the Russian Federation FIRMS file.
- Three VIIRS satellites, type 0 (vegetation) primary; type 2/3 retained for a sensitivity run in urban sectors.
- Observability ledger at H3 res-6 (~36 km²) cell × day × satellite, aggregated to sector-week.
- Pre-war baseline 2012–2021 (S-NPP) per cell × ISO week.
- Two control codings: DeepState (primary) and ISW/CTP ArcGIS timelapse (secondary, for latency and measurement-error checks).
- Primary panel test + seven fixed robustness specs (listed in §5).
- Transfer: Nagorno-Karabakh 2020 (primary, 1–2 days), Sudan 2023– (secondary, 4–6 days, cut first if behind).
- Sensor-continuity check across the 2 Nov 2026 S-NPP switch-off.
- Deliverables: repo, dashboard, brief, DOI, FAQ, side note.

### Out
- Any point-level or sub-weekly front-band publication (OPSEC rule, see §8).
- ACLED (2025 EULA bars direct access, requires non-reverse-engineerable derivatives; UCDP GED is CC BY 4.0 and sufficient) [V, scout_risks §2.4].
- Liveuamap (paid, scraping breaches terms), Maxar/Planet/Umbra (no conflict collections), Sentinel-1 processing (use Dietrich et al. heatmap only if stretch time appears).
- Gaza, Yemen, Libya, DRC, Sahel as analysis cases; each gets at most one appendix figure from the blind-season calendar.
- Any casualty, "who is winning," or forecast-of-advance claim.
- A production system. The dashboard is a static site with a daily cron; say so.

### Stretch (only after the minimum ships)
- VIIRS Nightfire (EOG) temperature-resolved night detections as a "what kind of fire" robustness arm.
- Economist `war_fire` label as an alternative treatment variable (CC BY 4.0, one download).
- WorldCover stratification of the front band (crop/grass/tree/built-up).
- GeoConfirmed (60,783 placemarks) and Bellingcat civilian-harm JSON (2,517 incidents) as event-level recall tests: share of dated, geolocated strikes with a FIRMS detection within 1 km / ±1 day, by season and target class.
- PMTiles of all points; DuckDB-WASM in-browser queries.
- Syria, if ACLED sub-district control or Carter Center locality history turns out to be downloadable (30-minute check in week 1).

---

## 2. Work breakdown by phase and week

Assumptions: Jackson ≈ 15–20 h/week part-time; Claude drafts code, pulls data, writes first drafts, runs checks; Jackson owns decisions, reviews, geometry sanity checks, writing voice, and every outreach email. Six weeks: **Week 1 = 14–20 Oct 2026 … Week 6 = 18–24 Nov 2026; ship date Tuesday 24 Nov 2026.** A fixed four-week variant is given in §8 (time runs short).

Hard external dates inside the window: CNAS/Breaking Defense Pathfinder essay 8 Nov [V, scout_audience]; AFK early-career abstracts 11 Nov [S]; S-NPP shutdown 2 Nov [V]; USGIF GEOINT poster application opens 20 Jan 2027 [S].

### Phase A — Lock, license, pull (Week 1: 14–20 Oct)

| # | Task | Owner | Hrs | Inputs | Outputs | Done when |
|---|---|---|---|---|---|---|
| A1 | Create repo `frontline-from-space` (MIT code, CC BY 4.0 data), `uv` env, Makefile skeleton, `.github/workflows/ci.yml` | Claude | 3 | scout_infra §2 | repo, green CI on empty test | `make test` passes |
| A2 | Port `first_pass.py` into `src/ffs/{loc,sectors,panel}.py`; reproduce `sector_week_panel.csv` byte-for-byte; pytest invariants (sectors partition band; areas sum; no duplicate sector-weeks) | Claude | 6 | feasibility scripts, `out/` | `tests/`, frozen coefficient test (β=0.8409 ±1e-4) | CI reproduces Spec C |
| A3 | Write `PREREG.md` (hypotheses H1–H8 above, fixed definitions, inference rules, abandonment criteria); commit and tag `prereg-v1`; mirror on OSF Registries using the "existing data" template (OSF lists an existing-data template among its 11 [V, COS blog via search today]) | Jackson writes, Claude drafts | 4 | §0.2 | tagged commit, OSF URL | Hash in README |
| A4 | Write `LIMITS.md` skeleton (ten items from scout_risks §3.2), `PUBLICATION_RULES.md` (sector-week only, ≥7-day lag, no point-level front data, no FRP/time tables, no event annotation), `LICENSES.md`, attribution block | Claude drafts, Jackson approves | 2 | scout_risks | three files | Committed before any new data |
| A5 | Register FIRMS MAP_KEY; call `/api/data_availability/csv/{KEY}/ALL`; record per-source start dates and whether `VIIRS_NOAA21_SP` exists (currently only `_NRT` listed [V, FIRMS API page fetched today]) | Jackson (signup), Claude (calls) | 1 | — | `data/firms_availability.csv` | File committed |
| A6 | Email DeepState via https://api.deepstatemap.live/request: non-commercial student research use of the history API + publication of derived sector-week aggregates with attribution. Save the email in `LICENSES/`. Proceed regardless; publish derived only. | Jackson | 1 | scout_risks §2.2 draft | sent email | Sent and logged |
| A7 | Pull FIRMS yearly CSVs: Ukraine 2012–2025 S-NPP (+MODIS 2012–2025 as fallback), Russian Federation 2022–2025 (~76 MB/yr), Azerbaijan + Armenia 2012–2020, Sudan 2012–2025, plus Chad 2023–25 for West Darfur. Write `data/manifest.yaml` with URL, sha256, bytes, retrieved_at, product (SP) | Claude | 3 | URL pattern `https://firms.modaps.eosdis.nasa.gov/data/country/<sensor>/<year>/<sensor>_<year>_<Country>.csv` [V] | ~600 MB raw, manifest | `make data` idempotent |
| A8 | FIRMS API loop: `VIIRS_NOAA20_SP` and `VIIRS_NOAA21_NRT` for bbox 22–41 E, 44–53 N, 2018-04-01→present in 5-day chunks (~1,000 calls/sensor; limit 5,000 per 10 min [V]); same for NK bbox 2018–2020 and Sudan bbox 2018–present. Flag NRT vs SP per row. | Claude | 4 | MAP_KEY | `data/raw/firms_api/*.parquet`, ~150–250 MB | Row counts logged; NRT share per year in manifest |
| A9 | DeepState API backfill: `GET /api/history/public` (1,785 IDs [V]); fetch each `/api/history/<id>/geojson` at 1 req / 2–3 s with descriptive User-Agent; cache; filter occupied-area polygons by `name`/`styleUrl` ("Окуповано", CADR, CALR, Crimea); validate against cyterat mirror on 30 overlapping dates (area difference <1%) | Claude (run overnight), Jackson (spot-check 10 snapshots in QGIS/geopandas plot) | 5 | scout_data §2.1 | `data/interim/deepstate_daily_2022_2024.parquet`, ~0.5–1 GB raw | Overlap test passes; gaps listed |
| A10 | ISW/CTP ArcGIS pull: `UkrainianCoTTimelapse_FEB_2022_to_DEC_2024_view/FeatureServer/0` (7,540 polygons, `datetime` field [V]) paginated at 2,000 records; monthly 2025–26 timelapse services. Record copyright notice; derived-only use. | Claude | 3 | scout_data §2.3 | `data/interim/isw_control_daily.parquet` | Daily area series plotted against Economist `areas_of_control_daily_summary.csv` (ISW-derived, 2022-02-24→2023-11-05 [V]) and matches within 2% |
| A11 | Clone Economist repo (`output-data/`, CC BY 4.0): `cloud_cover_in_ukraine_by_day.csv`, `ukraine_war_fires.csv` (71 MB), `control_status_of_fires_II.csv`, `firms_update_RU.csv` | Claude | 1 | https://github.com/TheEconomist/the-economist-war-fire-model [V] | `data/external/economist/` | Manifest entries |
| A12 | UCDP GED 26.1 (39 MB, CC BY 4.0) + Candidate 26.0.8; Natural Earth already on disk; HDX COD-AB Sudan ADM1–3; GeoNames AZ/SD | Claude | 1 | scout_data §3.2 | files + two required UCDP citations in `LICENSES.md` | Done |
| A13 | Ukraine phase table (`planning/ukraine_phase_table.md`): phases coded by D008's written mechanical test **before any regression**, with ISW daily-assessment dates as sources: 2022-02→04 maneuver (RU); 2022-09→11 maneuver (UA; Kharkiv 6 Sep, Kherson 9–11 Nov); 2022-12→2023-05 saturated-linear (Bakhmut); 2023-06→08 failed penetration (Zaporizhzhia, Robotyne); 2023-09→2024-07 saturated-linear (Avdiivka); 2024-08→2025-03 Kursk salient; 2024-07→present saturated-linear | Jackson (coding), Claude (sources) | 3 | corpus D008:79–86; ISW archive | phase table with per-sector-week regime labels | Committed and referenced in PREREG |
| A14 | Decision meeting (30 min): D1 title/anchor, D2 control source order, D3 transfer case, D5 GEE vs local, D6 Pathfinder essay (see §9) | Jackson | 1 | this plan | decisions logged in `planning/DECISIONS.md` | Logged |

Week 1 total: Jackson ≈ 12 h; Claude ≈ 30 h of tool time. Go/no-go at end of week 1 = scout_risks §9 checklist.

### Phase B — Geometry, baseline, observability ledger (Week 2: 21–27 Oct)

| # | Task | Owner | Hrs | Inputs | Outputs | Done when |
|---|---|---|---|---|---|---|
| B1 | Rebuild sectors as **perpendicular corridors**, not Voronoi: 50 km segments of the 2024-12-30 reference line, buffered 90 km each side, clipped by bisectors at segment endpoints; also 25 km and 100 km variants for robustness. Front band ±15 km of that week's line (10/25 km variants). Rear strip 50–90 km retained for the descriptive table only. | Claude builds, Jackson checks map | 5 | A2, A9 | `data/processed/sectors_{25,50,100}km.gpkg`, weekly front lines 2022-W14→ | No sector has zero rear area; map reviewed |
| B2 | Weekly line of contact 2022-04→present from DeepState (3 km inside border, coast removed); same from ISW; disagreement statistics per sector-week (area difference, week-of-change offset) | Claude | 4 | A9, A10 | `fronts_weekly_deepstate.topojson`, `fronts_weekly_isw.topojson`, `control_disagreement.csv` | Median DeepState–ISW week-of-change lag reported per sector |
| B3 | Pre-war baseline: S-NPP 2012–2021 detections → H3 res-6 cell × ISO week; empirical median and 95th percentile per cell-week; excess = max(0, observed − p95). Robustness: exclude 30 km buffer around the 2021 line. | Claude | 4 | A7 | `baseline_h3r6.parquet`, `excess_weekly.parquet` | Validity: excess in rear strip ≈ 0 in Jul–Sep 2019 holdout year |
| B4 | **Observability ledger, Tier 1 (cheap, whole period):** per H3 res-6 cell × day × satellite: (a) overpass flag = any detection by that satellite within a 200 km box that day (empirical swath proxy) **and** skyfield TLE propagation for the strict version; (b) cloud = ERA5 `tcc` at the nearest hour to the 01:30/13:30 local pass (CDS API, CC BY 4.0, bbox 22–42 E / 44–53 N, 2 timesteps/day ≈ 150 MB) **and** the Economist national/eastern daily cloud series as a cross-check; (c) snow = ERA5-Land `snow_depth`; (d) daylength via `astral`. Define `clear_looks = Σ overpass × (1 − tcc) × (1 − snow_flag)`. | Claude | 10 | A8, CDS account (Jackson creates), scout_methods A8 | `observability_h3r6_daily.parquet`; sector-week aggregate joined to panel | Validity regression: log front fires ~ clear_looks with sector + week-of-year FE, coefficient >0, p<0.01 |
| B5 | **Observability ledger, Tier 2 (the ownable part, sampled):** download VNP14IMG / VJ114IMG L2 swath granules from LAADS for a stratified sample — 2 days per ISO week per satellite over the Donbas corridor, 2022-04→2025-12 (~390 weeks × 2 × 3 sats ≈ 2,300 granules; the fire-mask SDS is 6,400 × ~6,464 8-bit, so ≈40 MB uncompressed, likely 5–15 MB compressed [U — measure on first download]; budget 10–30 GB). Read class 4 (cloud), 0 (not processed), 1 (bow-tie), 6 (unclassified) per cell. Calibrate Tier 1 against Tier 2: regression and confusion table. If agreement >0.8 (cell-day cloud fraction correlation), Tier 1 is used for the full period and Tier 2 reported as validation; if not, expand Tier 2 to full coverage on the front corridor only. | Claude (download + parse), Jackson (Earthdata login, decision on expansion) | 10 | Earthdata login; https://ladsweb.modaps.eosdis.nasa.gov; User Guide Table 1 [V] | `vnp14img_sample_classes.parquet`, `tier1_vs_tier2.md` | Calibration table committed |
| B6 | Alternative cloud source in GEE if CDS queues stall: `NASA/VIIRS/002/VNP09GA` QF cloud bits and `MODIS/061/MOD09GA` state bits reduced to H3 res-6 per day [U — VNP09GA bit layout from a secondary mirror; verify against LP DAAC]. Only if B4(b) is late by >3 days. | Claude | 6 (contingent) | GEE non-commercial project (Jackson registers in week 1, 1–2 day approval) | same schema as B4 | Same validity test |
| B7 | Dashboard skeleton (Observable Framework **or** single HTML + MapLibre + Observable Plot; decision D4): sector map, weekly front, observability strip; deploy to GitHub Pages | Claude | 6 | B1, B2, B4 | live URL | Loads <3 MB, works on phone |

Week 2 total: Jackson ≈ 10 h; Claude ≈ 45 h.

### Phase C — Confirmatory analysis, Ukraine (Week 3: 28 Oct – 3 Nov)

| # | Task | Owner | Hrs | Inputs | Outputs | Done when |
|---|---|---|---|---|---|---|
| C1 | Build the full panel 2022-W14→latest: sectors × weeks with net km² (DeepState and ISW), front fires by satellite and day/night, excess fires, observability, phase label, Kursk sectors from the Russia file | Claude | 5 | B1–B5, A13 | `panel_sector_week.parquet` (~22–26 sectors × ~190 weeks) | Invariants pass; row count logged |
| C2 | **H1/H2 observability results:** share of km² gained by observability quartile; winter zero decomposition (no-look vs look-no-fire); figures 1–3 | Claude runs, Jackson reads | 4 | C1 | `results/h1_h2.csv`, figures | Numbers in PREREG template filled |
| C3 | **H3 primary spec** on the confirmatory sample (2022-W14→2024-W27) with pyfixest (CRV1, wild bootstrap) and linearmodels PanelOLS `cov_type="kernel"` bandwidth 4 for DK [V — linearmodels docs]; then on the exploratory sample; then pooled. Equivalence test. | Claude | 4 | C1 | `results/h3_primary.csv` | Both SEs reported; equivalence bound stated |
| C4 | Seven robustness specs (fixed in PREREG): (1) excess fires and night-only as treatment; (2) P(advance>1 km² in 4 wks) logit/LPM and IHS(net); (3) 2×2 sector width × band width; (4) Sims leads-and-lags t−4..t+4 with joint test; (5) drop-one-sector jackknife plot, drop Donetsk; (6) phase interaction (**H4**); (7) H3 res-7 cell × week Poisson/NB raster twin. Plus control-source swap (ISW outcome). | Claude | 8 | C1 | `results/robustness_*.csv`, one combined table | All seven present, none added |
| C5 | Forecast-skill table: LightGBM (num_leaves 15, lr 0.05, early stopping) and Ridge; baselines B0 zero, B1 momentum-only, B2 +fires, B3 +observability/excess/dryness, B4 +night/FRP; `TimeSeriesSplit(gap=4)`, 8-week test blocks; leave-one-sector-out; MAE/RMSE, Brier/PR-AUC; skill = 1 − MAE(Bk)/MAE(B1) | Claude | 5 | C1 | `results/forecast_skill.csv` | ≥5% floor applied as pre-registered |
| C6 | Event studies around the phase table's dated operations (±8 weeks, stacked, calendar-week FE) for fires and net km² | Claude | 3 | A13, C1 | figure | Dates match PREREG list |
| C7 | **S-NPP switch-off day (2 Nov):** snapshot the `missing_data` and `data_availability` endpoints before and after; start the H5 continuity table (S-NPP vs NOAA-20 monthly front/rear ratio Jul 2024–Oct 2026) | Claude | 2 | A5, A8 | `results/h5_continuity.csv` | Table filled through Oct 2026 |
| C8 | Send PREREG + first H1 figure to three critics with one specific question each (Solstad: does the 0.1° baseline treat Nov–Feb as structurally zero? Van Den Hoek: where would you break the observability ledger? Zhukov: VIINA vs DeepState latency by sector?) | Jackson | 2 | scout_audience C.4 template | three emails, Rolodex entries | Sent by 1 Nov |
| C9 | Optional: Pathfinder essay (800–1,000 words, deadline 8 Nov, must be unpublished and exclusive, no gen-AI text) — "Free satellite data is a sensor the US does not treat as one: an observability standard for open thermal monitoring" | Jackson writes alone | 5 (contingent on D6) | C2 figures | submitted essay | Submitted by 7 Nov |

Week 3 total: Jackson ≈ 12 h (+5 if essay); Claude ≈ 30 h.

### Phase D — Transfer and side piece (Week 4: 4–10 Nov)

| # | Task | Owner | Hrs | Inputs | Outputs | Done when |
|---|---|---|---|---|---|---|
| D1 | **Nagorno-Karabakh 2020 (H6/H7):** clip AZ+AM FIRMS 2012–2020 to former NKAO + 7 districts; per-week baseline 2012–19; reproduce CEOBS 447 fires 26 Oct–4 Nov vs 203 for 2012–19 [S]; geocode Wikipedia timeline capture list via GeoNames `AZ.txt`; event study ±14 days per settlement, 5 km radius; observability ledger Tier 1 for the 44 days | Claude builds, Jackson codes the capture-date table (~60 settlements, 2 h) | 10 | A7, A8 | `results/nk2020_*.csv`, 2 figures | CEOBS number reproduced ±10%; median lag with bootstrap CI |
| D2 | **Sudan 2023– (H6):** settlement list (HDX/GeoNames SD); 5 km buffers; per-settlement ISO-week baseline 2012–2022 (mean, p95); flag 2023–25 exceedances; precision/recall vs UCDP GED events (where_prec ≤2) by season (Nov–Feb burning / Mar–May dry-clear / Jun–Sep wet) and region (Darfur / Khartoum–Gezira / Kordofan); validation against hand-compiled Yale HRL + CIR + HRW dated village list (~60–100 rows, Jackson 3 h); El Fasher ring sub-test (15 km band vs 50–90 km rear); observability ledger Tier 1 (ERA5 over Sudan bbox) | Claude, Jackson (village table) | 14 | A7, A8, A12 | `results/sudan_*.csv`, 3 figures, `data/processed/sudan_village_burnings.csv` (CC BY 4.0, our compilation) | Precision/recall table by season; zero-week share vs Ukraine |
| D3 | Global blind-season figure: monthly probability of zero S-NPP detections per 1° cell, 2019–2021, by climate zone; one map | Claude | 3 | FIRMS all-countries zips 2019–21 (~385 MB each [S]) or GEE community FIRMS vector archive | figure A1 | Rendered |
| D4 | **Side piece (H8):** refresh Ivaniuk dataset (Kaggle `piterfm`, free account) to Oct 2026; recompute destroyed-only vs destroyed+EW-lost by quarter; test Mirror B and KAS monthly figures; night-clustered CIs; write `report/intercept-note.qmd` (2–3 pages, one figure) framed as a reporting-regime break (D010 mode 9) | Claude (compute), Jackson (write) | 6 | airdefense/ outputs | note HTML+PDF | Both mirrors checked; CSIS 0.64 figure addressed without a "takedown" tone |
| D5 | Living layer: `refresh.yml` daily cron 04:17 UTC — FIRMS NRT last 30 days (3 sources) + today's cyterat file → rebuild last-30-days layer and observability strip, lagged 7 days; commit; redeploy. MAP_KEY as repo secret. Analysis layer frozen in tagged releases. | Claude | 5 | B7 | daily commits, "last refresh" badge | Three consecutive successful runs |

Week 4 total: Jackson ≈ 12 h; Claude ≈ 38 h. **If behind schedule at the end of week 3, D2 (Sudan) is cut first, then D3.**

### Phase E — Write, review, harden (Week 5: 11–17 Nov)

| # | Task | Owner | Hrs | Inputs | Outputs | Done when |
|---|---|---|---|---|---|---|
| E1 | `report/brief.qmd` → HTML (embed-resources) + Typst PDF; 5–8 pages, 2,500–3,500 words, 6–8 code-generated figures with underlying CSVs; structure in §6 | Jackson writes, Claude drafts sections and figures | 12 | all results | brief | Renders both formats; every number traceable to a `results/` file |
| E2 | `docs/FAQ.md` (interviewer attacks: why 15 km, why not Voronoi, Nickell bias, NRT vs SP mixing, permutation vs serial correlation, Pokrovsk dependence, what would change the result) | Claude drafts, Jackson edits | 3 | VERDICT, LIMITS | FAQ | 15+ Q&As |
| E3 | External reads: one methods (econ-stats instructor or grad student), one subject-matter (whoever replied from C8). Incorporate; log in `CHANGELOG.md`. | Jackson | 3 | E1 draft | revised brief | Two reads received or deadline passed |
| E4 | README as 30-second interview; landing page; `CITATION.cff`; correction policy paragraph; attribution block on every artefact | Claude | 3 | — | README, `site/index` | Reviewed by Jackson |
| E5 | Figure polish: one sequential palette (viridis), diverging for change, grey hatching for "unobserved"; consistent sector colours across map, dashboard, brief | Claude | 3 | E1 | final figures | Checked colour-blind safe |
| E6 | Update H5 continuity table with first two weeks of NOAA-only data (post 2 Nov) | Claude | 1 | C7 | table | Filled |

Week 5 total: Jackson ≈ 16 h; Claude ≈ 22 h.

### Phase F — Ship and outreach (Week 6: 18–24 Nov)

| # | Task | Owner | Hrs | Inputs | Outputs | Done when |
|---|---|---|---|---|---|---|
| F1 | Tag `v1.0`; GitHub Release with processed Parquet; Zenodo DOI via GitHub integration; update brief with DOI | Claude | 2 | all | DOI | DOI resolves |
| F2 | Publish: repo public → landing page → LinkedIn post (honest-null hook; posts live in `~/Jackson Mackney/LinkedIn/posts/`) → Bellingcat pitch (submissions@bellingcat.com, 300–500 words, no attachments) → CSIS Futures Lab memo (intercept note) → MWI as fallback → one X/Bluesky thread + HN "Show HN" + r/CredibleDefense (read sidebar first) the same day | Jackson | 5 | scout_audience B | sent/posts logged | All sent on ship day |
| F3 | Thank-you/results emails to the critics who replied; Rolodex updates | Jackson | 1 | C8 | emails | Sent |
| F4 | Calendar: USGIF GEOINT 2027 student poster (apply 20 Jan–3 Mar 2027); Bellingcat Tech Fellowship call (expected Dec–Jan); Shield AI / Palantir summer-2027 internship postings | Jackson | 0.5 | — | calendar entries | Done |
| F5 | Resume bullet and interview pitch finalised with actual numbers (§13) | Jackson | 1 | brief | `docs/PITCH.md` | Done |

Totals across six weeks: **Jackson ≈ 75–85 h** (within 15–20 h/week), **Claude ≈ 190 h of tool time**. New-tool learning for Jackson is kept to DuckDB/pyfixest/Quarto (≈12 h, inside the estimates); GEE is contingent only.

---

## 3. Data plan

| Source | How obtained | Size | Storage | License / attribution | Role |
|---|---|---|---|---|---|
| NASA FIRMS yearly country CSVs (S-NPP 2012–2025, MODIS) for Ukraine, Russian_Federation, Azerbaijan, Armenia, Sudan, Chad | `https://firms.modaps.eosdis.nasa.gov/data/country/<sensor>/<year>/<sensor>_<year>_<Country>.csv` [V]; `make data` via pooch registry with sha256 | ~600 MB | `data/raw/firms/` (gitignored) | NASA open; acknowledgment text in `LICENSES.md`; SP product | Detections, baseline |
| FIRMS API `VIIRS_NOAA20_SP`, `VIIRS_NOAA21_NRT`, `VIIRS_SNPP_SP/NRT` | area endpoint, 5-day chunks, free MAP_KEY, 5,000 transactions/10 min [V] | ~250 MB | `data/raw/firms_api/*.parquet` with `product` column | same; NRT disclaimer | Multi-satellite, 2026, observability overpass proxy |
| FIRMS `data_availability`, `missing_data` endpoints | API [V, listed on API page today] | KB | `data/firms_availability.csv` | — | Sensor outages for the ledger |
| VNP14IMG / VJ114IMG L2 swath (fire mask classes 0–9) | LAADS DAAC (Earthdata login), bbox + date search, sampled | 10–30 GB sampled [U] | `data/raw/vnp14img/` (gitignored, external drive OK) | NASA open; DOI 10.5067/VIIRS/VNP14IMG.002 [V] | Tier-2 cloud/no-look truth |
| ERA5 single-levels `tcc`, ERA5-Land `snow_depth`, soil moisture L1 | CDS API (`cdsapi`), free account, two timesteps/day | ~150 MB per theatre | `data/raw/era5/*.nc` | CC BY 4.0, C3S/ECMWF | Tier-1 cloud, snow, dryness |
| DeepState history API | `/api/history/public` → 1,785 `/api/history/<id>/geojson` [V]; polite 1 req/2–3 s | 0.5–1 GB | `data/raw/deepstate_api/` (gitignored, never redistributed) | DeepState license: derived aggregates only, attribution with link/logo; permission email sent | Primary control 2022-04→2024-07 |
| DeepState cyterat mirror | daily GeoJSON 2024-07-08→ [V] | 41 MB+ | `data/raw/deepstate_mirror/` (fetched, not vendored; mirror is GPL-3.0) | as above | Primary control 2024-07→ |
| ISW/CTP ArcGIS feature services | REST `f=geojson`, 2,000-record pages [V] | ~200 MB | `data/raw/isw/` (gitignored) | © ISW/AEI CTP, no license text [U]; publish agreement statistics only | Second control coding, latency |
| Economist war-fire repo `output-data/` | `git clone` [V] | ~250 MB | `data/external/economist/` | MIT code / CC BY 4.0 data; cite Solstad 2023 | Cloud series cross-check; `war_fire` alt treatment (stretch) |
| UCDP GED 26.1, Candidate 26.0.8 | https://ucdp.uu.se/downloads/ [V] | 41 MB | `data/raw/ucdp/` | CC BY 4.0; cite Davies/Pettersson/Öberg 2026 and Sundberg & Melander 2013 | Sudan outcome |
| Natural Earth 50m admin-0 | on disk [V] | 3 MB | `data/raw/naturalearth/` | public domain; note Crimea coding | Border/coast cut |
| HDX COD-AB Sudan, GeoNames AZ/SD | HDX CKAN API, GeoNames dumps | <50 MB | `data/raw/admin/` | CC BY / CC BY | Transfer geometry |
| Yale HRL / CIR / HRW village-burning reports | manual compilation from public PDFs | 1 CSV | `data/processed/sudan_village_burnings.csv` (committed, CC BY 4.0, cites each report) | our compilation of public facts | Sudan positive-control set |
| Wikipedia NK 2020 timeline settlement captures | manual, geocoded | 1 CSV | `data/processed/nk2020_captures.csv` (committed) | CC BY-SA text → facts only | NK outcome |
| Ivaniuk missile/drone dataset (Kaggle `piterfm`) + mirrors | Kaggle account | ~5 MB | `data/raw/airdefense/` | Kaggle dataset license [U — check]; publish aggregates | Side piece |
| ESA WorldCover 2021 v200 (stretch) | GEE `ESA/WorldCover/v200` or COG tiles | ~2 GB Ukraine | gitignored | CC BY 4.0 | Fuel stratification |
| CelesTrak TLEs (S-NPP, NOAA-20, NOAA-21) | https://celestrak.org | KB | `data/raw/tle/` | free | Strict overpass computation (skyfield) |

Total on disk ≈ 2–4 GB without Tier-2 granules, 12–35 GB with them; everything $0. Repo stays <100 MB: processed Parquet/TopoJSON/CSV committed when <10 MB each; larger processed files as GitHub Release assets and on Zenodo.

Storage layout follows scout_infra §2.1 (`data/{raw,interim,processed,external,sample}`, `src/ffs/`, `tests/`, `site/`, `report/`, `results/`, `planning/`). `data/sample/` holds 2 weeks of FIRMS + 3 DeepState days + 10 VNP14IMG cells so CI runs `make all` in <5 min.

---

## 4. Analysis plan

### 4.1 Observability ledger (the anchor; scout_methods A8 extended)

For H3 res-6 cell *c*, day *d*, satellite *s*:

```
looks[c,d,s]        = 1 if the satellite swath covered c on day d (empirical: any detection within 200 km box; strict: skyfield pass with sensor zenith < 60°)
clear[c,d,s]        = 1 − cloud_fraction at overpass hour (Tier 1: ERA5 tcc; Tier 2: share of VNP14IMG class-4 pixels in c)
processed[c,d,s]    = 1 − share of class 0/1/6 pixels (Tier 2 only; Tier 1 assumes 1 except on dates listed by /api/missing_data)
fuel_ok[c,d]        = 1 − snow_flag (ERA5-Land snow_depth > 1 cm) 
clear_looks[c,d]    = Σ_s looks × clear × processed
observable[c,d]     = clear_looks × fuel_ok
```

Sector-week aggregates: sum of `clear_looks`, mean `observable`, and three mutually exclusive states for each zero-detection sector-week: **NO-LOOK** (clear_looks < 1), **LOOK-NO-FIRE** (clear_looks ≥ 1, fuel_ok, zero type-0 detections), **LOOK-FUEL-OUT** (clear_looks ≥ 1, snow). Detections themselves are then split by the pre-war baseline into **EXCESS** vs **BASELINE** (agriculture-plausible).

Validation (pre-registered): `log(1+front_fires) ~ clear_looks | sector + week_of_year`, coefficient >0, p<0.01. If that fails the ledger is wrong and we say so.

Outputs: `observability_sector_week.csv`, `h1_gains_by_observability_quartile.csv`, `h2_zero_decomposition_by_month.csv`, and the dashboard strip ("fraction of the front observable this week").

### 4.2 Primary specification (H3)

```
net4_{i,t+1..t+4} = β·log(1+front_fires_{i,t}) + Σ_{k=0..3} ρ_k·net_{i,t−k} + θ·clear_looks_{i,t} + α_i + γ_t + ε_{i,t}
```
Sectors = 50 km perpendicular corridors; front band ±15 km of that week's line; satellites pooled; type 0; confidence n/h; sample (a) confirmatory 2022-W14→2024-W27, (b) exploratory 2024-W28→2025-W52, (c) pooled. SEs: CRV1 by sector + wild cluster bootstrap (pyfixest) and Driscoll–Kraay lag 4 (linearmodels `cov_type="kernel"`). Nickell bias ≈1/T ≈ 0.5% at T≈190; note and ignore. Equivalence bound ±2 km² per doubling.

### 4.3 Robustness (fixed list, §2 C4)
1. Treatment = excess over baseline; night-only. 2. Binary and IHS outcomes. 3. 2×2 sector × band widths. 4. Sims leads/lags with joint lead=0 test. 5. Drop-one-sector jackknife; drop Donetsk. 6. Phase interaction (H4). 7. H3 res-7 Poisson/NB raster twin. Plus: ISW as outcome; weight by observability; Economist `war_fire` as treatment (stretch).

### 4.4 Forecast skill (§2 C5), event studies (§2 C6), change points
PELT (`ruptures`) on weekly observability and fire series to date blind-season onset/offset objectively per year; compare with DeepState activity regimes.

### 4.5 Blind-spot product (public deliverable)
Monthly × sector probability that a fighting-week (defined as net |Δkm²| > 1 or ISW-assessed advance) produces ≥1 detection, decomposed into NO-LOOK vs LOOK-NO-FIRE; H3 res-6 map per month; dashboard slider; hatching for unobserved. Published at monthly × sector or coarser (OPSEC rule). Global 1° blind-season map from 2019–21 as the generalization figure.

### 4.6 Transfer tests
- **NK 2020:** same ledger; baseline 2012–19; CEOBS replication; event study on announced capture dates (±2 days noise); pre-registered expectation: fires trail.
- **Sudan:** per-settlement anomaly detection (p95 of 2012–22 same week) vs UCDP GED events; precision/recall by season/region; Yale/CIR/HRW list as labelled positives; El Fasher ring front-band test; ledger shows zero-week share. Transferable metrics are location skill and blind-season dates, **not β** (there is no area outcome).
- **Within-Ukraine phases (H4):** the cleanest war-type test, sensor and cartographer held fixed.

### 4.7 Sensor continuity (H5)
Monthly front/rear ratio and seasonal envelope by satellite; NOAA-20-only vs S-NPP-only Jul 2024–Oct 2026; first NOAA-only weeks after 2 Nov 2026 appended in week 5.

---

## 5. Deliverables (exact formats)

| # | Deliverable | Format | Location |
|---|---|---|---|
| 1 | Public repo | GitHub, MIT (code) + CC BY 4.0 (derived data), `uv.lock`, Makefile, pytest, CI badge, `PREREG.md` (tagged), `LIMITS.md`, `PUBLICATION_RULES.md`, `LICENSES.md`, `DEVIATIONS.md`, `CHANGELOG.md`, `CITATION.cff`, `docs/FAQ.md` | `github.com/<user>/frontline-from-space` |
| 2 | Processed data release | Parquet (zstd): `panel_sector_week.parquet`, `observability_sector_week.parquet`, `baseline_h3r6.parquet`; TopoJSON weekly fronts (derived, our geometry); CSVs behind every figure | GitHub Release `v1.0` + Zenodo DOI |
| 3 | Dashboard | Static site (Observable Framework build or plain HTML + MapLibre GL JS + Observable Plot), <3 MB first load, Tier-A aggregates; daily cron refresh of last-30-days layer and observability strip, 7-day lag; "last refresh" badge | GitHub Pages |
| 4 | Brief | Quarto `.qmd` → self-contained HTML + Typst PDF, 5–8 pages, 2,500–3,500 words, 6–8 figures (SVG + 300-dpi PNG), structure: BLUF + headline figure (observability-decomposed seasonality); question, hypotheses, data, geometry; results in H order; limitations table; "what this means for an analyst" (5 bullets); reproducibility box; appendix tables | `report/brief.qmd`; site |
| 5 | Side note | Quarto, 2–3 pages, one figure (destroyed-only vs destroyed+EW-lost by quarter) | `report/intercept-note.qmd`; site |
| 6 | Blind-spot product | H3 res-6 monthly GeoJSON/JSON (<2 MB) + global 1° PNG | site, repo |
| 7 | Transfer appendix | NK 2020 and Sudan figures + CSVs; `sudan_village_burnings.csv` (CC BY 4.0) | repo |
| 8 | Landing page | One URL: headline figure, three sentences, buttons Dashboard / Brief HTML / Brief PDF / Repo / DOI | GitHub Pages root |
| 9 | Outreach artefacts | Bellingcat pitch (300–500 words), CSIS memo (2 pages), LinkedIn post, X/Bluesky thread, optional Pathfinder essay (800–1,000 words) | `outreach/` (private folder, not in repo) |

---

## 6. Brief outline (so E1 is not a blank page)

1. **BLUF** (150 words) + Figure 1: monthly front-band detections per 1,000 km² with the zero weeks decomposed into NO-LOOK / LOOK-NO-FIRE / LOOK-FUEL-OUT (stacked), 2022–2026.
2. **What a thermal feed is and is not** (D015 chain: detect → identify → custody → effect; one number per link). Half page.
3. **Data and geometry** (Figure 2: sectors, corridors, bands; DeepState vs ISW disagreement inset).
4. **H1/H2 Observability** (Figure 3: share of km² gained by observability quartile; Figure 4: H3 monthly blind-spot map, 4 panels Jan/Apr/Jul/Oct).
5. **H3/H4 Lead** (Table 1: primary + robustness; Figure 5: drop-one-sector jackknife and Sims leads/lags; Table 2: forecast skill vs momentum).
6. **H5 Continuity** (Figure 6: S-NPP vs NOAA-20 monthly ratio; the 2 Nov switch-off).
7. **H6/H7 Transfer** (Figure 7: NK 2020 event study; Figure 8: Sudan precision/recall by season; appendix: global blind-season map).
8. **Limitations** table (NRT/SP mix, map latency, Pokrovsk dependence, baseline contamination near the 2014–21 line, Tier-1 cloud is reanalysis, one-sided border file, ISW Nov 2025 edit incident, specifications previously tried, elicited corpus frames).
9. **For the analyst**: five bullets on when to open FIRMS and when not to.
10. **Reproducibility and how to cite**; correction policy.

---

## 7. Tooling decisions, alternatives rejected

| Decision | Choice | Rejected | Why |
|---|---|---|---|
| Environment | `uv` + Python 3.12 + `pyproject.toml` (already installed) | pixi, conda | Wheels bundle GDAL/PROJ; one lockfile; feasibility venv already works |
| Geometry | geopandas 1.1 + shapely 2.1 (STRtree, `substring`) | PostGIS | Already used; 100k points × line distance is fast enough |
| Tabular/joins | DuckDB + `spatial` + `h3` community extension | pandas-only, polars | SQL keyword coverage for CSIS/Govini/Anduril postings; H3 binning in one query; reads Parquet without memory games |
| Grid | H3 res-6 (ledger, baseline), res-7 (raster twin) | 0.1° lat/lon | Equal-area-ish; same code for Ukraine, NK, Sudan. Economist's 0.1° kept only for the `war_fire` comparison |
| Cloud/observability | Tier 1 ERA5 `tcc` + skyfield overpasses, calibrated against Tier 2 VNP14IMG fire-mask classes (sampled) | Full VNP14IMG for all days; GEE VNP09GA; Sentinel-3 SLSTR | Full swath archive is 100+ GB [U]; the sampled calibration gives the ownable "algorithm's own cloud decision" with a laptop budget. GEE kept as fallback (B6). SLSTR adds 1 km looks at heavy format cost; skip |
| Econometrics | pyfixest (CRV1, wild bootstrap) + linearmodels PanelOLS kernel (DK) + statsmodels (logit/NB) | R fixest as primary | Python keeps one pipeline; R used only if DK via linearmodels misbehaves (R is installed). **One spec also ported to R** for CSIS Futures Lab keyword ("intermediate R") — decision D9 |
| ML | LightGBM + sklearn `TimeSeriesSplit(gap=4)`; Ridge counterpart | Deep models | The discipline matters, not the learner; interviewers know LightGBM |
| Change-points | `ruptures` PELT | bocd | Small API, documented |
| Orbits/sun | skyfield + CelesTrak TLEs; `astral` | NASA CMR granule polygons; FIRMS swath-outline layer | FIRMS swath outlines exist only in the map viewer, no API [V — Earthdata blog fetched today]; CMR polygons are approximate per NASA; skyfield is offline and exact enough |
| Data versioning | pooch registry + `manifest.yaml` with sha256 | DVC, git LFS | One person, <5 GB without granules; LFS quota dies under cloners |
| Orchestration | Makefile | snakemake | Zero deps; mirrors Economist repo |
| Dashboard | Observable Framework → static `dist/` on GitHub Pages (fallback: single HTML + MapLibre + Plot) | Streamlit Community Cloud (sleeps after 12 h [S]); Felt (no embed on free); kepler.gl (reads as "uploaded a CSV") | Static, $0, never sleeps; Framework activity slowed in 2026 [S] but builds; fallback is one file |
| Living refresh | GitHub Actions cron (free on public repos; auto-disables after 60 days inactivity, prevented by bot commits) | Cloudflare Workers cron (10 ms CPU) | Compute needs Python |
| Brief | Quarto → HTML + Typst PDF (upgrade Quarto 1.8.26 → 1.9) | LaTeX, Word | One source, two outputs, no TeX install |
| Pre-registration | Git tag + OSF Registries "existing data" template | Tag only | External timestamp costs 1 hour |
| Hosting | GitHub Pages (1 GB, 100 GB/mo soft) + Zenodo DOI | Cloudflare Pages/R2 | Only needed if PMTiles >25 MiB (stretch) |
| Event data | UCDP GED (CC BY 4.0) | ACLED | ACLED EULA incompatible with a public reproducible pipeline [V] |

---

## 8. Contingencies

| Risk | Trigger | Fallback |
|---|---|---|
| **DeepState API backfill fails or is refused** | >20% of 2022–24 snapshot fetches fail, or DeepState replies "no" by end of week 2 | Use ISW/CTP full-length timelapse (7,540 polygons, 2022-02-24→2024-12-31 [V]) as the control source for the confirmatory sample; DeepState remains for 2024-07→; state the swap in `DEVIATIONS.md`. If ISW terms also forbid derived use [U]: VIINA settlement-day control (ODbL) for 2022 and a smaller confirmatory window |
| **FIRMS API unavailable / NOAA-20 SP not back to 2018** | `data_availability` shows NOAA-20 SP start later than 2022-04, or sustained 504s | FIRMS Archive Download tool (Earthdata login, emailed CSV; one request per sensor); if both fail, run the panel on S-NPP only and keep the ledger from Tier 1; H5 reduced to the post-2 Nov NRT weeks |
| **LAADS granules too big or slow** | First 50 VNP14IMG granules exceed 15 MB each or download <5 granules/min | Shrink Tier 2 to one day per fortnight per satellite on 10 Donbas cells (~400 granules); if still blocked, GEE VNP09GA/MOD09GA cloud bits (B6) become Tier 2 and the "algorithm's own cloud decision" claim is dropped to a footnote |
| **Observability ledger fails validation** | `clear_looks` does not predict front fires (p>0.01) | Debug overpass proxy first (switch to skyfield strict), then cloud source (ERA5 → GEE). If still failing, publish the ledger as a cloud/snow calendar only, reframe H1 as "share of gains in snow/cloud months," and say the look-level product did not validate |
| **Null everywhere** (H3 null, H4 no phase difference, H7 no lag) | All as stated | This is the pre-registered expectation for H3; H4/H7 nulls are reported as "fires locate, never lead, in any regime tested." The anchor claim (H1/H2 ledger) and H5/H6 do not depend on a positive β. Brief title stays about the sensor |
| **Positive β survives everything** | β>0 under both SEs, MAE skill ≥5% | Report it as pre-registered; lean hard on phase split, jackknife, and equivalence bands; invite the critics to break it before publishing (C8) |
| **Transfer case fails** | NK: CEOBS count not reproduced ±10% (likely a clip-polygon or confidence-filter difference); Sudan: UCDP geo-precision too coarse for 5 km matching | NK: report the discrepancy and our definition; the event-study still runs. Sudan: widen to 15 km / admin-3 match; if precision/recall is uninformative, keep only the zero-week share (H6 physics) and the El Fasher band test |
| **Time runs short** (behind at end of week 3) | Phase C not complete by 3 Nov | Four-week plan: cut Sudan (D2), global map (D3), stretch items, Pathfinder essay; keep NK (1–2 days), side piece (already 80% done), brief, dashboard, DOI. Ship 10 Nov with "v1.0 (Ukraine + NK)" and a dated "Sudan planned" line |
| **Licensing problem surfaces late** (DeepState objects after publication; ISW objects to cross-check) | Written objection | Remove the objected derived layer within 48 h (correction policy); the ledger and FIRMS-only products are unaffected; control swap per row 1 |
| **OPSEC concern raised** (a reader argues the blind-spot map aids targeting) | Any credible public or private complaint | Point to `PUBLICATION_RULES.md` (monthly × sector, 7-day lag, no points), to the fact that FIRMS and the Economist publish point-level daily, and to the marginal-contribution-zero argument already in the brief; do not debate in replies; log in `CHANGELOG.md` |
| **S-NPP shutdown date moves** | NESDIS changes the 2 Nov date ("subject to change" [V]) | H5 table runs on whatever months exist; the continuity test is still novel on NOAA-20 vs S-NPP overlap 2024–26 |
| **CDS queue stalls** | ERA5 request >3 days in queue | B6 GEE path, or the Economist daily cloud series (national/eastern) as a coarse interim covariate with a flagged deviation |
| **Critics do not reply** | No reply by week 5 | Proceed; the brief says "pre-registration was sent to the authors of the prior art on <date>" and lists who was sent, not who replied |

---

## 9. Decision points for Jackson (options and recommendation)

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Title and anchor claim | (a) "Front line from space: what FIRMS can and cannot tell an analyst" with the lead-lag test first; (b) **"Did the satellite look? An observability-adjusted assessment of free thermal data in the Russia–Ukraine war"** with the ledger first and the null second; (c) sensor-transition framing ("Suomi NPP's last war") | **(b).** It is the only unpublished claim with a positive, generalizable answer; (a) leads with a null, (c) is a hook not a thesis (use it in the LinkedIn post) |
| D2 | Control-source order | (a) DeepState API backfill first, ISW as check; (b) ISW first (clean `datetime`, no license email dependency), DeepState as check | **(a)**, because DeepState is finer and the mirror already underlies the exploratory panel; but start the ISW pull the same day so the swap in §8 row 1 costs nothing |
| D3 | Transfer case(s) | (a) NK only; (b) Sudan only; (c) both, Sudan cut first; (d) Syria check first | **(c)** with the 30-minute Syria check in week 1; NK is 1–2 days and tests war type; Sudan tests season and is what D023 says most future war looks like |
| D4 | Dashboard framework | (a) Observable Framework; (b) single HTML + MapLibre + Plot; (c) Streamlit | **(a) if Jackson is fine with a node build step, else (b).** Never (c) |
| D5 | GEE account | (a) register now as fallback; (b) skip GEE entirely | **(a)**; registration is free and takes 1–2 days; it costs nothing until B6 triggers |
| D6 | Pathfinder essay (8 Nov) | (a) write it (5 h, must be Jackson's own prose, no gen-AI text, exclusive); (b) skip | **(a) only if week 3 is on schedule by 31 Oct**; the $1,000 prize matters less than the CNAS byline and the forced one-paragraph thesis |
| D7 | ACLED | (a) register privately for a robustness footnote; (b) do not touch | **(b)**; nothing in the plan needs it and the EULA is a liability for a public repo |
| D8 | Side piece | (a) slot in week 4 (6 h); (b) drop | **(a)**; it is 80% done, theatre-agnostic, and gives CSIS Futures Lab a reason to read the main piece |
| D9 | R spec | (a) port the primary spec to R fixest (2–4 h) for CSIS/Govini keyword coverage and as a DK cross-check; (b) Python only | **(a)**, in week 5 if time allows |
| D10 | OSF registration visibility | (a) public immediately; (b) embargoed until publication | **(a)**; the whole point is an external timestamp others can see |
| D11 | Tier-2 expansion | after B5 calibration: expand VNP14IMG to full front-corridor coverage (+10–20 GB, +6 h) or stop at the sample | Decide on the calibration number: expand only if Tier 1–Tier 2 correlation <0.8 |
| D12 | Project email and identity | (a) separate project email, 2FA, personal-info audit; (b) use existing | **(a)**, per scout_risks §6 |

---

## 10. Publishing and outreach

Order (from scout_audience, adapted):
1. **Ship day (24 Nov):** repo public, `v1.0` tag, Zenodo DOI, landing page, dashboard live with ≥3 days of cron history.
2. **Same day:** LinkedIn post (hook: "44% of Ukraine's front-line weeks show no fire from space. Here is how much of that is the satellite not looking." — honest, numeric, non-partisan); one X thread and Bluesky mirror with three figures, tagging only prior-art authors (@Sondreus, @bradyafr, Payne Institute); Show HN; r/CredibleDefense after reading rules.
3. **Week of 24 Nov:** Bellingcat pitch to submissions@bellingcat.com (300–500 words, working headline, one-sentence topline, no attachments) framed as a Resources follow-up to their 2022 FIRMS guide with an open tool; CSIS Futures Lab two-page memo (intercept note) to Atalan/Jensen via LinkedIn/staff page framed as "extending your model past Oct 2024 with a denominator fix."
4. **If Bellingcat declines (allow 3 weeks):** Modern War Institute (600–2,500 words, MWIsubmissions@westpoint.edu) as "sensor literacy for staff officers"; Small Wars Journal as last fallback. War on the Rocks not pitched (students without non-academic experience are rejected [V]).
5. **Preprint:** SSRN (free) or SocArXiv; arXiv only if the econ-stats instructor endorses.
6. **Dated follow-ons:** AFK early-career abstract (11 Nov, if the essay is skipped); USGIF GEOINT 2027 student poster (20 Jan–3 Mar 2027) — the room is GEOINT recruiters; Bellingcat Tech Fellowship call (expected Dec–Jan) pitching the observability ledger as the tool.
7. **Critic loop:** PREREG sent in week 3 (C8); results sent on ship day; every contact logged in Rolodex with date and reply; foreign professional contacts logged for a future SF-86.
8. **Conduct rules:** one neutral promotion post per channel; no reply-debates; corrections via repo; Ukrainian transliterations throughout; no travel to RU/BY/occupied territory while public.

---

## 11. How the Future_of_War corpus is used

The corpus has never touched fire data (grep for FIRMS/VIIRS/MODIS returns nothing [V, scout_corpus]); it contributes frames, hypotheses and comparisons, never numbers.

- **Spine of the brief:** D015's detect → identify → custody → effect chain (`D015_transparency_reconciliation.md:81`), one measured number per link. The observability ledger is the *detect* and *custody* links made quantitative; the lead-lag null is the *effect* link.
- **Why the null is the regime behaving as predicted:** D008 force-to-space regimes (`D008:79–90`, High · documentary, one of four stamps that survived D022). Ukraine 2024–25 coded `saturated-linear` by D008's own test → momentum-dominated, small change. Phase table (A13) uses D008's written test, coded before regression.
- **The when-fires-lead hypothesis:** D011 symmetry branch (`D011:58`, Med · elicited, scope riders D019:187–194 and FORWARD-1 at D019:231 honoured: we name the branch, carry a coded symmetry forecast per phase, and name the counter-move).
- **Why Sudan is not optional:** D023 verdict (civil war first on frequency and consequence); `04_rest_of_world.md:152` ("corridor- and node-based density regimes … should not be analyzed with a European linear-front denominator") justifies the node-radius redesign.
- **Side piece framing:** D010 mode 9 (filmable-weapon kill-claim inflation, `D010:309–316`) and `03_middle_east.md:29` denominator discipline.
- **Honesty apparatus:** D022 two-axis stamp (`mechanical / documentary / definitional / elicited`; elicited never High) adopted in every results table and in §0.2 above; the G1 "disclosure has replaced correction" critique is answered by letting named failure modes drive design (pre-registration, baseline, transfer).
- **Historical comparisons (one paragraph each, Med · documentary):** WWI Western vs Eastern Front (`ww1_1914.md:78`), Iran–Iraq's ~1,100 km line (`iran_iraq_1980.md:33`), Korea's maneuver → saturated-linear transition (`korean_war_1950.md:69`), Yemen's custody problem (`yemen_civil_war.md:86`).
- **Watchboard:** the weekly sector panel is a live TRNS-2/MANV-3 feed the parent project specified and never ran (`09_watchboard_population.md:17–31`); one sentence in the brief.
- **Never cited:** census counts, cross-tabs, any census High stamp, "triangulated," landscape chapters' D011 applications, S-### IDs without resolving against `01_source_log.md`. `planning/corpus_frames.md` will hold the verbatim quoted blocks with file:line (A13 companion, 1 h).

---

## 12. Air-defense side piece: slotted in

Slotted into week 4 (D4, 6 h) as a 2–3 page Quarto note, hypothesis H8, deliverable 5. Rationale: the finding is already in hand and reproduces (destroyed-only 0.68/0.67/0.89 vs destroyed+EW-lost 0.93/0.86/0.89 by year; EW-lost share 0.09 → 0.40 in 2024 Q4 → 0.00 in 2025 Q4 [V, airdefense/VERDICT.md]); it is theatre-agnostic ("defender-reported intercept rates are not a stable measurement"); it corrects a widely cited CSIS 0.64 figure in a collegial way, which gives Futures Lab a reason to open the main brief; and it costs one Kaggle refresh plus a Mirror B/KAS check. What remains: pre-register the break dates in `PREREG.md` (H8), add night-clustered CIs, drop the Fig-1 multi-theatre overlay the airdefense verdict criticised. Drop trigger: if the project is in the four-week fallback **and** Mirror B does not refresh past June 2026, publish the existing numbers as a blog post instead of a note.

---

## 13. Resume bullet and 60-second pitch (numbers to be replaced with final values)

**Resume bullet (one line):**
> *Front line from space* — built an open, reproducible pipeline (Python/GeoPandas/DuckDB, pyfixest, GitHub Actions) fusing ~600k NASA FIRMS thermal detections from three satellites, the fire algorithm's own cloud masks, and two independent territorial-control codings into a 22-sector × 190-week panel of the Russia–Ukraine front; shipped the first observability-adjusted assessment of a free thermal feed in a war (X% of territorial change occurred when the sensor could not see), pre-registered and falsified a lead-lag hypothesis with fixed-effects, clustered and Driscoll–Kraay inference, and tested transfer to Nagorno-Karabakh 2020 and Sudan. Public repo, dashboard, 7-page brief, Zenodo DOI.

**60-second interview pitch:**
> "Everyone who uses NASA's free fire-detection feed to watch a war — Bellingcat, The Economist, the academic papers — reads a zero as 'nothing burned.' I asked a different question: did the satellite actually look? I pulled the detections from all three VIIRS satellites for the whole Russia–Ukraine line since April 2022, went back to the Level-2 swath product for the fire algorithm's own cloud and quality classes, and built a ledger of clear looks for every 50 km sector and week. Then I joined it to two independent open codings of territorial control. Three results. First, X% of Russia's territorial gains happened in sector-weeks where the sensor had fewer than N clear looks — the feed wasn't blind to the war, it was looking elsewhere, and I can show you exactly when. Second, I pre-registered a test of whether fires lead territorial change and it came back null under both clustered and Driscoll–Kraay errors, with placebo and reverse checks: fires tell you where the fight is this week, not where the line moves next month, and I can bound how big a lead I'd have detected. Third, I ran the same ledger on Nagorno-Karabakh 2020 and Sudan, so I can say which parts of that answer are physics and which are Ukraine. The whole thing is open data, open code, reproducible in three commands, and the dashboard updates daily with a one-week lag by design. The sensor it all rested on, Suomi NPP, was switched off on 2 November; I shipped the continuity check three weeks later."

---

## 14. Flags: what this plan could not verify

1. VNP14IMG granule compressed size and LAADS download throughput — drives B5; measure on the first 50 granules.
2. Whether `VIIRS_NOAA20_SP` via the area API reaches back to 2018-04 (needs the MAP_KEY call in A5).
3. ISW/CTP reuse terms for ArcGIS layers (Cloudflare-blocked for scouts); agreement statistics only until confirmed.
4. DeepState's position on student research use of the history API; email in A6 settles it or does not.
5. VNP09GA cloud QF bit positions in GEE (fallback only).
6. CEOBS 447/203 fire counts and clip polygon (scout_transfer [S]); replication in D1 tests it.
7. Observable Framework maintenance trajectory (last push 2026-05-15 [S]).
8. Kaggle license on the Ivaniuk dataset.
9. The exact S-NPP cessation date is "subject to change" per NASA; the plan does not depend on it.
10. Novelty itself: scouts ran ~35 prior-art sources and I found no detection-opportunity accounting for conflict fires today (NASA's own 2024 FIRMS blog on cloud and the Jasper fire is wildfire-only); "no one has published this" is a strong claim and the brief should say "we found no published …" with the search described.

## Sources added by this planner (beyond the scout files)
- VIIRS C2 375 m Active Fire User Guide v1.2, Table 1 fire-mask classes: https://www.earthdata.nasa.gov/s3fs-public/2025-06/VIIRS_C2_AF-375m_User_Guide_1.2.pdf
- Suomi NPP observations cease 2 Nov 2026 (NASA Earthdata alert, updated 5 Oct 2026): https://www.earthdata.nasa.gov/data/alerts-outages/suomi-npp-observations-cease-november-2-2026
- FIRMS API endpoint list (area, data_availability, kml_fire_footprints, missing_data, map_key): https://firms.modaps.eosdis.nasa.gov/api/
- FIRMS satellite swath outlines (map viewer only, no API): https://www.earthdata.nasa.gov/news/blog/new-firms-data-product-satellite-swath-outlines
- NASA FIRMS blog, impact of cloud on active fire detections (Jasper 2024): https://wiki.earthdata.nasa.gov/spaces/FIRMS/blog/2024/08/07/382276882/The+Impact+of+Cloud+on+Active+Fire+Detections
- VNP14IMG V002 DOI: https://doi.org/10.5067/VIIRS/VNP14IMG.002
- VIIRS L2 cloud mask continuity products (CLDMSK_L2_VIIRS_SNPP/NOAA20/NOAA21, 750 m, 6-min): https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/CLDMSK_L2_VIIRS_NOAA21/
- OSF preregistration templates incl. existing-data template: https://www.cos.io/blog/choosing-preregistration-template-guide-for-researchers
