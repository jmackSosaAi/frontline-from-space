# Front Line From Space — Project Plan (RIGOR-FIRST draft)

**Key:** `rigor` · **Written:** 2026-10-13 · **Author:** Claude (planner), for Jackson Mackney
**Angle:** optimise for a result that survives a hostile technical reviewer and could stand as a working paper. Pre-registration with a timestamp that precedes the confirmatory data pull, an explicit exploratory/confirmatory split, equivalence bounds so a null is a finding rather than an absence, dual inference, a blinded pipeline build, and a transfer test that is a genuine out-of-sample forecast rather than a re-description.

**Inputs read in full:** `Conflict_Data_Feasibility/frontline/{VERDICT,FIRST_PASS,SOURCES}.md` and `out/*.csv`; `Conflict_Data_Feasibility/airdefense/{VERDICT,FIRST_PASS}.md`; all eight scouts in this folder (`scout_data_sources`, `scout_prior_art`, `scout_methods`, `scout_transfer_cases`, `scout_audience_venues`, `scout_infra_deliverables`, `scout_risks_ethics`, `scout_corpus_assets`).

**New facts verified today (2026-10-13) that the scouts did not have:**
1. **Suomi-NPP science data delivery ceases 1 Nov 2026 at 13:00 UTC** (NOAA NESDIS announcement 3 Aug 2026, relayed by NASA Earthdata: https://www.earthdata.nasa.gov/data/alerts-outages/suomi-npp-data-product-delivery-cease-november-1-2026). The date is "subject to change." This lands in week 3 of this plan. The frozen analysis (archive S-NPP through 2025) is unaffected; the living dashboard layer must be designed around NOAA-20/21 from day one; and it is a genuinely interesting fact for the brief ("the sensor every published war-fire study runs on goes dark in November").
2. **FIRMS area API sources** (https://firms.modaps.eosdis.nasa.gov/api/area/): `MODIS_NRT`, `MODIS_SP`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA20_SP`, `VIIRS_NOAA21_NRT`, `VIIRS_SNPP_NRT`, `VIIRS_SNPP_SP`, `LANDSAT_NRT`. **No `VIIRS_NOAA21_SP`.** DAY_RANGE 1–5. 5,000 transactions per 10 min. So NOAA-20 can enter the confirmatory sample as science-quality data; NOAA-21 (from 2024-01-17) is NRT-only and goes in robustness, flagged.
3. **DeepState licence** (https://deepstatemap.live/license-en.html, re-read): free API use is named only for "Volunteer and charitable activities" and "Activities for the defense of Ukraine, its sovereignty, and territorial integrity"; commercial use needs prior approval via https://api.deepstatemap.live/request; research/student use is not mentioned; "The creation of identical objects that completely match the Objects is prohibited."
4. **OSF secondary-data preregistration template** exists at osf.io/x4gzt (Weston, Mellor, Bakker, van den Akker et al. 2020; tutorial: van den Akker et al. 2021, *Meta-Psychology*, doi:10.15626/MP.2020.2625; 25 non-mandatory questions). I did not load the live OSF page; confirm it resolves in week 1.
5. **pyfixest Driscoll–Kraay**: still unverified (reference page 404'd; PyPI page says pyfixest mirrors R `fixest` "with only one small exception," unnamed). R `fixest` supports `vcov = DK(4) ~ week` and recommends ≥20 periods (https://search.r-project.org/CRAN/refmans/fixest/html/vcov_hac.html). `wildboottest` (PyPI) implements WCR/WCU variants with CRV1/CRV3 and the CRV3-jackknife; p-values only, no CIs, no multiway clustering. Plan below uses linearmodels for DK in Python and R `fixest` as the cross-implementation.

Everything else in this plan that is not verified is marked **[UNVERIFIED]** inline.

---

## 1. Thesis and pre-registered hypotheses

### 1.1 Thesis (one paragraph)

A free 375 m thermal feed (NASA FIRMS, VIIRS active fire) is a reliable *locator* of where a land war is being fought and an unreliable *leading indicator* of where territory will change hands; the boundary between the two is set by sensor physics (overpass cadence, cloud, snow, fuel) and by the type of war (saturated-linear attrition versus manoeuvre), not by anything specific to Ukraine. The project tests this with a pre-registered, two-way fixed-effects sector-week panel against two independent open territorial-control codings (DeepState, ISW/CTP) on data not touched in the exploratory pass; converts the expected null into a bounded claim via an equivalence test; builds the first quantified detection-opportunity ("blind-spot") product for a conflict, decomposed into *not observed* versus *observed, no fire*; and runs the identical pipeline as an out-of-sample forecast on a manoeuvre war (Nagorno-Karabakh 2020) and an arid raiding war (Sudan 2023–). The deliverable is a sensor-triage brief for an analyst, a reproducible repository, and a dashboard that refreshes only its descriptive layer, so the pre-registered results never drift.

### 1.2 The exploratory/confirmatory split (the design decision everything hangs on)

| Set | Period | Sensors | Status | Role |
|---|---|---|---|---|
| **E (exploratory)** | 2024-07-08 → 2025-12-31 | S-NPP only | ~10 specifications already tried (FIRST_PASS) | Used to fix definitions, build the pipeline, run the power simulation, and report as "exploratory" with every caveat. **No new inferential claim is drawn from E.** |
| **C1 (confirmatory, primary)** | 2022-04-03 → 2024-07-07 (DeepState API history; ISW timelapse) | S-NPP SP + NOAA-20 SP | Untouched | The pre-registered test of H2/H3. ~118 weeks × 22 sectors ≈ 2,600 sector-weeks before lag losses. Contains manoeuvre (Sep–Nov 2022), attrition (Bakhmut, Avdiivka), failed penetration (summer 2023). |
| **C2 (confirmatory, replication)** | 2026-01-01 → 2026-09-30 | S-NPP NRT→SP + NOAA-20 + NOAA-21 NRT | Untouched | Same spec run once more; NRT flagged. Pre-registered as a replication, not pooled with C1. |
| **T1 (transfer, out-of-sample)** | Nagorno-Karabakh 27 Sep – 10 Nov 2020 | S-NPP SP | Untouched (CEOBS's 447-fire count is the only published number) | Pre-registered predictions filed before the 2020 Azerbaijan/Armenia FIRMS files are downloaded. |
| **T2 (transfer, blind-spot)** | Sudan 2023-04-15 → 2025-12-31 | S-NPP SP | Untouched | Pre-registered blind-season forecast from the 2012–2022 baseline, checked against wartime detections and UCDP GED events. |

**Hard rule:** the pre-registration commit (and OSF registration) must be timestamped **before** any of the C1, C2, T1 or T2 wartime files are downloaded. Baseline-year files (Ukraine 2012–2021, Azerbaijan/Armenia 2012–2019, Sudan 2012–2022) may be downloaded earlier because they are inputs to the pre-registered definitions, not test data. The download script logs retrieval timestamps to `data/MANIFEST.json`, so the ordering is auditable.

### 1.3 Hypotheses, success criteria, failure criteria

All five are separate claims; no family-wise correction; no hypothesis may be added after the pre-registration commit. Deviations go in `DEVIATIONS.md` with dates. Every hypothesis has a *pre-stated prediction*, so a confirmed null is a success for the project even where it is a failure for the hypothesis.

**H1 — Location.** *Within each calendar month, VIIRS detection density within 15 km of the control line exceeds the same-cell pre-war (2012–2021) baseline for the same ISO weeks by a factor ≥ 3 in at least 9 of 12 months, in C1.*
- Success: criterion met with the lower 95% bootstrap CI (sector block bootstrap, 2,000 draws) of the ratio above 3 in ≥ 9 months.
- Failure: fewer than 9 months. Either way, report the monthly ratio curve with CIs. Prediction: supported.
- Already-published analogue (Bellingcat, Economist, Dingemanse) — H1 is a calibration claim, not the novelty.

**H2 — Lead (the primary pre-registered test).** *In the primary specification (§5.1) estimated on C1, the coefficient β on log(1 + front-band fires at week t) predicting cumulative net km² gained by Russia in weeks t+1…t+4, conditional on four momentum lags, detection opportunity, sector and week fixed effects, is positive and distinguishable from zero under both inference rules.*
- Significance rule: p < 0.05 under **both** (a) CRV1 clustered by sector with a wild-cluster-bootstrap p-value (Webb weights, 9,999 draws, WCR11) and (b) Driscoll–Kraay with lag 4.
- Practical-significance rule: β ≥ **β_SESOI = 2.9 km² per log-unit** (equivalently: a doubling of front fires, +0.693 log units, is associated with ≥ 2 km² of additional 4-week advance per sector, which is about half the sample-mean 4-week change of ~15.6 km² in E).
- Equivalence rule: the 90% CI for β lies entirely within (−2.9, +2.9) → the pre-registered conclusion is **"fires are not a practically meaningful leading indicator (TOST equivalence established)."**
- Three admissible outcomes, all pre-written: (i) supported (both significance and SESOI), (ii) equivalence established (null bounded), (iii) **inconclusive** (CI covers both 0 and β_SESOI). Outcome (iii) is reported as such; it is not spun either way.
- Prediction: (ii) or (iii). Reason given in advance: the E-sample coefficient 0.85 (weekly) and 3.16 (4-week, p 0.10), flat lead-lag curve, and D008's saturated-linear regime.

**H3 — Forecast value.** *A gradient-boosted model (LightGBM) or ridge regression with fire features beats a momentum-only model by ≥ 5% MAE in rolling-origin cross-validation (expanding window, 8-week test blocks, 4-week gap) on C1, and separately on E.*
- Success: skill ≥ 5% in both. Failure: < 5% in either. Prediction: not supported.
- Also report leave-one-sector-out skill (spatial generalisation).

**H4 — Blind spot.** *At least 30% of total km² gained by Russia in C1 occurs in sector-weeks whose detection opportunity (§5.3) is in the bottom quartile of the C1 distribution.*
- Success: share ≥ 30% with bootstrap CI excluding 30%. Failure: share < 30%. Prediction: supported (advances peaked Nov 2024 and Jun–Jul 2025 in E, fires peak Jul–Sep).
- Validation gate (must pass before H4 is reported): a regression of log front fires on detection opportunity with sector and week-of-year FE returns a positive coefficient with p < 0.01. If it does not, the opportunity product is wrong and H4 is reported as "not testable with this product."

**H5 — Transfer (two pre-registered sub-tests, both out-of-sample).**
- **H5a (Nagorno-Karabakh 2020, manoeuvre war):** (1) weekly excess detections (observed minus 95th-percentile 2012–2019 same-week baseline) in the Karabakh AOI exceed zero in ≥ 4 of the 7 war weeks; (2) in an event study around the 30 dated settlement captures (Azerbaijani MoD announcements), the mean excess-detection count within 5 km is **higher in the 7 days after** the announced capture than in the 7 days before. Prediction: both hold — fires *trail* the advance in manoeuvre war. Failure for the prediction (fires lead) would itself be the most interesting outcome; it is pre-written too.
- **H5b (Sudan, arid raiding/siege war):** (1) a blind-season forecast made from the 2012–2022 Sudan baseline alone (months in which the median settlement-5-km-buffer in Darfur/Kordofan has zero detections) is filed *before* the wartime files are downloaded; the realised 2023–2025 zero-share by month correlates with the forecast at Spearman ρ ≥ 0.7; (2) the share of settlement-weeks with zero detections around UCDP GED event locations in Darfur/Kordofan is **lower** than Ukraine's 44% (lower 95% CI bound of the difference > 0). Prediction: both hold. (3) Exploratory: precision/recall of FIRMS anomalies against the hand-compiled Yale HRL / HRW / CIR village-burning list.

**What would make me abandon the project (pre-written):** NOAA-20 API pull fails *and* the DeepState backfill fails *and* the ISW timelapse service is withdrawn. Probability judged low; fallbacks in §8.

---

## 2. Scope

### In scope (ships in 6 weeks regardless)
- Pre-registration (OSF + tagged commit) with the five hypotheses above.
- Confirmatory panel C1 on DeepState history with ISW/CTP as a second control coding; primary spec, seven fixed robustness specs, equivalence test, two inference rules, cross-implementation in Python and R.
- Detection-opportunity (blind-spot) product for Ukraine 2022–2025 at H3 res-6 cell × day, aggregated to sector-week and sector-month; validated.
- Transfer T1 (Nagorno-Karabakh) and the blind-season half of T2 (Sudan).
- 5–8 page brief (Quarto → HTML + Typst PDF), public repo (MIT code / CC BY 4.0 derived data), Zenodo DOI, static dashboard with a weekly-refreshed descriptive layer, `LIMITS.md`, `PUBLICATION_RULES.md`, `FAQ.md`.
- Replication C2 (2026 NRT) reported as replication.
- Map-latency measurement: DeepState vs ISW week-of-change agreement by sector-week.
- Global blind-season map (half a day; FIRMS 2019–2021, by climate zone).

### Out of scope (explicitly, with the reason stated in the brief)
- Any claim to *forecast* territorial change operationally.
- Point-level, sub-weekly or event-annotated front-band products (OPSEC rule; see §8).
- ACLED (2025 EULA incompatible with a public reproducible repo; UCDP GED is CC BY).
- Gaza, Yemen, Libya, DRC, Sahel as analysis cases (fuel-limited, urban, or season-swamped; each gets at most one sentence or one appendix figure from the global blind-season map).
- Sentinel-1/2 processing, VIIRS Nightfire, Economist model re-estimation. Nightfire and the Economist `war_fire` label are *comparison columns* only if time allows (stretch).
- The census of the Future_of_War corpus as a data source (see §11).

### Stretch (only after the in-scope items are green)
- Economist `war_fire` label as an alternative treatment column (CC BY 4.0, one join).
- Sudan precision/recall against the hand-compiled arson list (H5b-3).
- H3 res-7 raster-twin Poisson panel (robustness spec 7; built in week 2, may be cut).
- Night-only and FRP-weighted treatment variants (robustness spec 1b).
- Air-defence reporting-artifact note (§12).
- PMTiles raw-point layer; DuckDB-WASM in-browser queries.
- VNF (Nightfire) temperature-class comparison for a 2-week window.

---

## 3. Work breakdown by phase and week

Calendar: today is Tue 2026-10-13. Six weeks: **W1 Oct 14–20, W2 Oct 21–27, W3 Oct 28–Nov 3, W4 Nov 4–10, W5 Nov 11–17, W6 Nov 18–24.** Ship date **Mon 24 Nov 2026** (before US Thanksgiving). External dates inside the window: S-NPP cutoff **1 Nov** (W3); CNAS Pathfinder essay **8 Nov** (W4); AFK early-career abstracts **11 Nov** (W5).

Owner key: **J** = Jackson (decisions, writing, emails, review, anything requiring his judgment or identity); **C** = Claude (code, data pulls, analysis runs, drafts). Hours are estimates of attention time: Jackson's are wall-clock hours he must spend; Claude's are agent-session hours. Jackson budget ≈ 14 h/week ≈ 84 h total; Claude ≈ 25–35 h/week.

### Phase 0 — Decisions (Oct 13–14)

| ID | Task | Owner | Hrs | Inputs | Outputs | Done when |
|---|---|---|---|---|---|---|
| 0.1 | Read this plan; make the ten decisions in §9 (or accept recommendations) | J | 2 | this file | `planning/DECISIONS.md` | every D-item has a choice and a date |
| 0.2 | Create project email, enable 2FA on GitHub, create public repo `frontline-from-space` (empty, MIT licence) | J | 0.5 | — | repo URL | repo exists; Claude has push access |
| 0.3 | Register FIRMS MAP_KEY (https://firms.modaps.eosdis.nasa.gov/api/map_key), CDS account (https://cds.climate.copernicus.eu), GEE non-commercial project (optional, D2), OSF account | J | 1 | project email | keys in `.env` (gitignored) | `curl` of `/api/data_availability/csv/{KEY}/ALL` returns a table; save it to `data/raw/firms/data_availability_2026-10-14.csv` as the authoritative sensor-start-date record |

### Phase 1 — Foundations and pre-registration (W1, Oct 14–20)

The whole week has one purpose: a pre-registration that is frozen before any confirmatory data is touched. Nothing from C1/C2/T1/T2 is downloaded this week.

| ID | Task | Owner | Hrs | Inputs | Outputs | Done when |
|---|---|---|---|---|---|---|
| 1.1 | Repo skeleton: `uv init`, `pyproject.toml`, Makefile targets (`data`, `panel`, `opportunity`, `models`, `transfer`, `figs`, `brief`, `site`, `test`), `data/MANIFEST.json` schema, pytest scaffold, `ci.yml` | C | 4 | scout_infra §2 | green CI on empty pipeline | `make test` passes in GitHub Actions |
| 1.2 | Port `first_pass.py` into `src/ffs/{ingest_firms,ingest_deepstate,loc,sectors,panel}.py`; reproduce E panel **byte-for-byte** (`sector_week_panel.csv`, Spec C coef 0.8409, p 0.0484) | C | 6 | feasibility scripts + raw data | `tests/test_reproduce_e.py` | coefficient reproduces to 1e-6; test is in CI |
| 1.3 | Download baseline-year FIRMS files (Ukraine S-NPP 2012–2021; Azerbaijan + Armenia 2012–2019; Sudan 2012–2022) and Economist repo `output-data/` (cloud series, `areas_of_control_daily_summary.csv`) | C | 2 | URL pattern `https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/<yr>/viirs-snpp_<yr>_<Country>.csv`; https://github.com/TheEconomist/the-economist-war-fire-model | `data/raw/firms/baseline/*.csv`, manifest rows with sha256 + retrieved_at | all files hashed; sizes logged (Ukraine ~8 MB/yr; AZ ~0.4 MB/yr; Sudan ~10–15 MB/yr) |
| 1.4 | **Sector geometry redesign** for a moving front (D1): perpendicular-corridor sectors replacing Voronoi; phase-specific reference lines; unit tests that corridors partition the band and rear strips never leave their corridor | C | 8 | `loc.py`, DeepState E files, Natural Earth | `sectors.py`, `tests/test_sectors.py`, `figs/sector_corridors_E.png` | all 8 Donetsk sectors that had zero rear fires under Voronoi now have rear area > 0; test passes |
| 1.5 | **Power / MDE simulation** on E: resample sector blocks, inject β ∈ {0, 1, 2, 2.9, 4} per log unit on the 4-week outcome, estimate power at N ≈ 2,400 under CRV1-wild and DK(4) | C | 4 | E panel | `planning/POWER.md` with a table and the MDE at 80% power | MDE stated; if MDE > β_SESOI, the pre-registration says so and names outcome (iii) as likely |
| 1.6 | **Ukraine phase table** coded by D008's written mechanical test *before* any fire data for C1 is seen: phases 2022-04→2022-08 (post-Kyiv withdrawal, Donbas push), 2022-09→2022-11 (Kharkiv, Kherson: manoeuvre), 2022-12→2023-05 (Bakhmut: saturated-linear), 2023-06→2023-10 (Zaporizhzhia counteroffensive: failed penetration), 2023-11→2024-07 (Avdiivka, attrition), 2024-08→2025-03 (Kursk salient, RU-side file), with ISW daily-assessment URLs as sources | C drafts, J approves | C 4, J 1 | ISW assessments; Economist `areas_of_control_daily_summary.csv`; `scout_corpus_assets.md` §8 | `planning/ukraine_phase_table.md` | each phase has start/end ISO week, regime code, ≥2 source URLs; committed before 2.1 |
| 1.7 | **Draft `PREREG.md`** from `scout_methods.md` §A10 plus §1 of this plan: hypotheses, SESOI, inference rules, fixed definitions (type=0; confidence ∈ {n,h}; ISO week; last snapshot per week; polygon style filter; CRS EPSG:3035 for area; front band ±15 km; 50 km corridors; cloud source), robustness list, blinding protocol (1.9), abandonment criteria, exploratory label rule | C drafts, J edits | C 4, J 3 | this plan; POWER.md; phase table | `planning/PREREG.md` | Jackson has read every line and can defend each number |
| 1.8 | **File OSF registration** using the secondary-data template (osf.io/x4gzt **[confirm live]**); answer the "have you looked at the data" questions honestly (E analysed; C1/C2/T1/T2 not downloaded); link the GitHub commit; tag `v0.1-prereg` | J | 2 | PREREG.md | OSF URL; git tag | OSF timestamp and tag hash both appear in README before any C1 download |
| 1.9 | **Blinding protocol** implemented: `panel.py --blind` permutes the week index of the outcome within sector (seeded) so pipeline development and tests run on scrambled outcomes; unblinding is a single flag flipped once, logged with timestamp | C | 2 | panel.py | `src/ffs/blind.py`, README section | tests run blind; `UNBLIND_LOG.md` exists and is empty |
| 1.10 | `LIMITS.md` (ten named items from scout_risks §3.2 plus S-NPP cutoff, NRT/SP mixing, ISW Nov-2025 edit incident), `PUBLICATION_RULES.md` (sector-week or coarser; ≥7-day lag; no point-level front data; no per-detection FRP/time; no event annotation), `LICENSES.md` (per source), attribution block | C drafts, J approves | C 3, J 1 | scout_risks §1.2, §2.8 | three files | committed and linked from README |
| 1.11 | **Licensing emails**: DeepState (via https://api.deepstatemap.live/request; non-commercial research use of history API; derived aggregates only; attribution with logo/link); ISW/CTP (reuse terms of ArcGIS timelapse layers, cross-check-only use, agreement statistics published); GeoConfirmed (terms); log in Rolodex | J | 1.5 | templates in `planning/outreach/` (C writes) | sent emails saved in `LICENSES/correspondence/` | three sent; dates logged |
| 1.12 | **Reviewer line-up**: ask econ-stats instructor (methods read in W5; also arXiv endorsement question) and one Ukraine SME (candidates: Solstad, Zhukov, Van Den Hoek per scout_audience §C) — send the *pre-registration*, not results | J | 1.5 | PREREG.md, 200-word template (C drafts) | replies logged | at least one methods and one SME reviewer tentatively agreed |
| 1.13 | ERA5 `tcc` request submitted to CDS for bbox 22–42E/44–53N, 2022-01-01→2026-09-30, hours 00/01/02/12/13/14 UTC (covers 01:30/13:30 local overpasses ±1 h); ERA5-Land `snow_depth` and `swvl1` daily | C | 2 | CDS account | request IDs; download lands in W2 | request accepted (CDS queue can take hours–days) |
| 1.14 | **Checkpoint W1 (Oct 20):** OSF registered; tag exists; E reproduces; sectors redesigned; blind mode on; emails sent | J | 0.5 | — | `planning/CHECKPOINTS.md` entry | all green or §8 triggers fired |

W1 totals: **J ≈ 14 h, C ≈ 40 h.**

### Phase 2 — Confirmatory data and products, blind (W2, Oct 21–27)

| ID | Task | Owner | Hrs | Inputs | Outputs | Done when |
|---|---|---|---|---|---|---|
| 2.1 | **DeepState history backfill**: 1,785 snapshots from `https://deepstatemap.live/api/history/public` and `/api/history/<id>/geojson`; 1 req / 2–3 s, descriptive User-Agent with project email, overnight, cached once; style-based filter to occupied-area polygons (names "Окуповано"/CADR/CALR/Crimea); validity repair; weekly last-snapshot selection | C | 6 (mostly wall-clock) | API; sample 1648989208 | `data/raw/deepstate/api/*.geojson` (gitignored, ~0.5–1 GB), `data/processed/deepstate_weekly.parquet` | 1,785 files; weekly national area series plotted against Economist ISW series 2022–23 (sanity: shapes agree; levels differ by known DeepState/ISW offset) |
| 2.2 | **ISW/CTP timelapse pull**: `UkrainianCoTTimelapse_FEB_2022_to_DEC_2024_view/FeatureServer/0` (7,540 polygons, `datetime`), paginate 2,000/query, `f=geojson`; 2025–26 monthly services as listed in scout_data_sources §2.3 | C | 4 | ArcGIS REST | `data/raw/isw/*.geojson`, `data/processed/isw_weekly.parquet` | daily area series 2022-02-24→2024-12-31 matches `areas_of_control_daily_summary.csv` to within 1% for overlapping dates |
| 2.3 | **FIRMS API pulls** for C1/C2: `VIIRS_NOAA20_SP` 2022-04-01→2026-04-30 and `VIIRS_NOAA20_NRT`/`VIIRS_NOAA21_NRT`/`VIIRS_SNPP_NRT` for the trailing months; bbox 22–42E/44–53N (covers Kursk/Belgorod); 5-day chunks, ≤ 1 request/s; record product (SP/NRT) per row | C | 3 | MAP_KEY | `data/raw/firms/api/*.csv` (~150 MB), manifest rows | row counts per sensor-year logged; S-NPP API rows for 2023–2025 match the yearly CSVs ±0.5% (cross-check of the pull) |
| 2.4 | FIRMS yearly CSVs: Ukraine S-NPP 2022; Russian_Federation 2022–2025 (76 MB/yr); Ukraine MODIS 2022–2025 (for the overpass-count proxy only) | C | 1 | URL pattern | raw CSVs | hashed in manifest |
| 2.5 | **Covariates**: ERA5 `tcc` at overpass hours (from 1.13), ERA5-Land snow/soil moisture; ESA WorldCover 2021 tiles for Ukraine (https://worldcover2021.esa.int/download); Copernicus DEM GLO-30 tiles (s3://copernicus-dem-30m/, no account); GHSL built-up; H3 res-6 zonal stats via DuckDB spatial + `exactextract` | C | 8 | CDS download; tile lists | `data/processed/covariates_h3r6.parquet` | every H3 cell in the AOI has cropland/tree/built-up share, mean slope, daily tcc at 01/13 UTC, daily snow flag |
| 2.6 | **Detection-opportunity product** (§5.3): per H3 res-6 cell × day × satellite: looks (empirical swath proxy: distinct (satellite, acq_time) with ≥1 detection within 200 km that day; MODIS as a fourth check), clear fraction (1 − tcc at the pass hour), snow flag, fuel share, day length (`astral`); aggregate to sector-week and sector-month; **validation regression deferred to W3 (needs unblinded fires? No: fires are not the blinded variable; run it now)** | C | 10 | 2.3–2.5 | `data/processed/opportunity_h3r6_day.parquet`, `opportunity_sector_week.parquet`, validation table | validation gate (H4) passes: log front fires ~ opportunity, sector + week-of-year FE, coef > 0, p < 0.01; if it fails, fix the product *before* unblinding (allowed: it does not involve the outcome) |
| 2.7 | **Pre-war per-cell baseline** (Economist-style, empirical): H3 res-6 × ISO week, median and 95th percentile across 2012–2021; excess = max(0, observed − p95) | C | 4 | 1.3 | `data/processed/baseline_h3r6_week.parquet` | spot-check: Donbas cells 2019 vs 2021 within expected agricultural variance; figure saved |
| 2.8 | **Build the C1 panel, blind**: sectors from 1.4 re-cut per phase (D1); front band ±15 km of that week's DeepState line; ISW line as alternate; fires by sensor; excess fires; opportunity; outcome scrambled | C | 8 | 2.1–2.7 | `data/processed/panel_c1_blind.parquet`; `panel_c2_blind.parquet` | tests pass: no duplicate sector-weeks, areas sum to national change ±1%, every sector-week has an opportunity value, zero-fire share reported |
| 2.9 | **Raster twin** (H3 res-7 cell × week, blind) | C | 4 | 2.8 inputs | `panel_h3r7_blind.parquet` | row count and coverage logged; may be cut at W4 if behind |
| 2.10 | **Model code**, run on the blind panel only: pyfixest `feols` CRV1 + `wildboottest`; linearmodels `PanelOLS(cov_type="kernel", bandwidth=4)` for DK; R `fixest` script (`feols(..., vcov = DK(4) ~ week)` and `vcov = ~sector`) reading the same parquet; TOST implemented by hand on the 90% CI; LightGBM/ridge rolling-origin CV; Sims leads-lags; jackknife; phase interaction. Python and R must agree on β and CRV1 SE to 1e-4 **on the blind panel** | C | 10 | PREREG.md §4–5 | `src/ffs/models.py`, `R/models.R`, `tests/test_py_r_agree.py` | the full robustness table renders from scrambled data; agreement test passes |
| 2.11 | **Transfer prep, blind**: Karabakh AOI polygon (pre-2020 NKAO + seven districts, from OSM/Natural Earth); 2012–2019 same-week baseline; geocode the 30 settlement capture dates from the Wikipedia timeline using GeoNames `AZ.txt`; Sudan settlement list (OCHA/GeoNames `SD.txt`), 2012–2022 per-settlement baseline, **blind-season forecast by month filed to `planning/T2_FORECAST.md` and committed** | C | 6 | baseline files from 1.3 | AOI files, capture table, `T2_FORECAST.md` | forecast committed with hash *before* any 2020 AZ/AM or 2023–25 Sudan file exists on disk |
| 2.12 | Living-layer scaffold (`refresh.yml`): daily NOAA-20/21 NRT pull + today's cyterat file → last-30-days layer and coverage strip; **S-NPP excluded from the living layer from day one** (cutoff 1 Nov) | C | 4 | MAP_KEY secret | workflow runs green | first automated commit lands |
| 2.13 | Jackson: read 2.6 validation output and 2.8 test logs; approve unblinding plan for W3; answer any reviewer replies; check DeepState/ISW replies | J | 4 | — | notes in CHECKPOINTS.md | signed off |
| 2.14 | **Checkpoint W2 (Oct 27):** C1/C2 panels built blind; opportunity validated; transfer forecast committed | J | 0.5 | — | — | all green or §8 triggers |

W2 totals: **J ≈ 5 h, C ≈ 70 h** (heavy agent week; Jackson's week is light by design because W1 was heavy).

### Phase 3 — Unblind and run once (W3, Oct 28–Nov 3)

| ID | Task | Owner | Hrs | Inputs | Outputs | Done when |
|---|---|---|---|---|---|---|
| 3.1 | **Unblind C1** (one flag; timestamp to `UNBLIND_LOG.md`; commit) and run the pre-registered primary spec + the seven robustness specs **once**, Python and R; TOST; wild bootstrap; DK | C | 3 | 2.10 | `out/c1_primary.csv`, `out/c1_robustness.csv`, `out/c1_tost.txt`, `out/c1_r_crosscheck.csv` | one run; outputs committed with the unblind timestamp; Py/R agree |
| 3.2 | Classify the H2 outcome by the pre-written rule (supported / equivalence / inconclusive); write the three-sentence result exactly as pre-drafted | J | 1 | 3.1 | `RESULTS.md` §H2 | sentence matches one of the three pre-written templates |
| 3.3 | H3 forecast-skill table (LightGBM vs ridge vs momentum-only; rolling-origin; LOSO) on C1 and E | C | 3 | 2.10 | `out/skill_table.csv`, figure | skill score per block; pre-registered threshold applied |
| 3.4 | H4 blind-spot share with bootstrap CI; sector-month opportunity map; "share of advances in bottom-quartile opportunity" by phase | C | 4 | 2.6, 2.8 | `out/h4_share.csv`, `figs/opportunity_sector_month.png` | CI reported; validation gate recorded as passed in W2 |
| 3.5 | H1 monthly ratio vs pre-war baseline with block-bootstrap CIs | C | 2 | 2.7, 2.8 | `out/h1_monthly.csv`, figure | criterion applied |
| 3.6 | **Pre-registered secondary analyses**: phase interaction (manoeuvre vs saturated-linear; H1 of the corpus scout), Sims leads-and-lags with joint test of lead coefficients = 0, reverse direction (area → fires), drop-one-sector jackknife, sector/band width 2×2 grid, excess-fire and night-only treatments, DeepState vs ISW outcome swap | C | 6 | 2.10 | `out/c1_secondary/*.csv`, figures | every item in PREREG §5 has an output file; nothing not in PREREG is run (exploratory runs go to `out/exploratory/` and are labelled) |
| 3.7 | **Map-latency measurement**: for each sector-week, week-of-change under DeepState vs ISW; distribution of lag; share of disagreements; re-run primary spec with the ISW outcome | C | 4 | 2.1, 2.2 | `out/latency.csv`, figure | median and IQR of lag by phase reported |
| 3.8 | **Detection rate by strike class** (cheap, interviewer-proof): share of Bellingcat civilian-harm incidents (2,517; https://bellingcat-embeds.ams3.cdn.digitaloceanspaces.com/production/ukr/timemap/api.json) and GeoConfirmed placemarks (60,783; https://geoconfirmed.org/api/placemark/Ukraine) with a VIIRS detection within 1 km / ±1 day, by month and weapon class; published as aggregate rates only | C | 4 | event JSONs; FIRMS | `out/detection_rate_by_class.csv`, figure | rates with Wilson CIs by class and season |
| 3.9 | **C2 replication** (2026 NRT) unblinded and run once, same spec | C | 2 | 2.8 | `out/c2_replication.csv` | reported as replication with NRT flag |
| 3.10 | **S-NPP cutoff (Nov 1)**: confirm living layer runs on NOAA-20/21 only; add a "sensor status" strip to the dashboard spec; one paragraph for LIMITS.md and the brief | C | 1 | 2.12 | workflow and text | refresh succeeds on Nov 2 without S-NPP |
| 3.11 | Jackson: read every output table; write `RESULTS.md` first draft (findings per hypothesis, exploratory clearly labelled); decide W4 scope (D7, D4 confirmation) | J | 8 | 3.1–3.9 | `RESULTS.md` | each hypothesis has a verdict sentence with the stamp (`mechanical`) and the file it came from |
| 3.12 | **Checkpoint W3 (Nov 3):** all five hypotheses have verdicts; latency and detection-rate tables exist | J | 0.5 | — | — | — |

W3 totals: **J ≈ 10 h, C ≈ 30 h.**

### Phase 4 — Transfer, brief draft, external review (W4, Nov 4–10)

| ID | Task | Owner | Hrs | Inputs | Outputs | Done when |
|---|---|---|---|---|---|---|
| 4.1 | **T1 Nagorno-Karabakh**: download `viirs-snpp_2020_Azerbaijan.csv` (406 KB) and `_Armenia.csv` (55 KB) **now** (manifest timestamp after prereg); reproduce CEOBS 447 detections 26 Oct–4 Nov 2020; weekly excess vs 2012–2019; event study around 30 capture dates (±7 days, 5 km); H5a verdict | C | 6 | 2.11 | `out/t1_*.csv`, two figures, `RESULTS.md` §H5a | CEOBS number reproduced within ±10% (or discrepancy explained); pre-registered before/after comparison reported with CI |
| 4.2 | **T2 Sudan blind-season**: download `viirs-snpp_2023/2024/2025_Sudan.csv` (~15 MB/yr) now; realised monthly zero-share around UCDP GED (26.1, https://ucdp.uu.se/downloads/, CC BY 4.0; Candidate 26.0.x for 2026) event settlements in Darfur/Kordofan; Spearman against `T2_FORECAST.md`; comparison with Ukraine 44% | C | 6 | 2.11; UCDP | `out/t2_*.csv`, figure, `RESULTS.md` §H5b | both pre-registered criteria evaluated |
| 4.3 | **Global blind-season map**: FIRMS 2019–2021 all-country zips (https://firms.modaps.eosdis.nasa.gov/data/country/zips/viirs-snpp_<yr>_all_countries.zip, ~385 MB each) → monthly P(zero detections) per 1° cell; classify by Köppen zone; one figure | C | 5 | zips | `figs/global_blind_season.png`, `out/global_blind_h3r3.parquet` | figure renders; Ukraine and Sudan positions marked |
| 4.4 | **Brief draft** (`report/brief.qmd`): BLUF; question and pre-registration (OSF link, tag); data and geometry; results in hypothesis order; latency and detection-rate tables; transfer; limits table; "what this means for an analyst" (5 bullets); reproducibility box; appendix tables. Structure by the D015 detect→identify→custody→effect chain (§11) | C drafts, J rewrites | C 8, J 6 | RESULTS.md, figures | HTML + PDF render | 2,500–3,500 words main text; 6–8 code-generated figures with saved CSVs |
| 4.5 | **External review packet**: PREREG.md + RESULTS.md + draft brief + repo to the methods reviewer and the SME reviewer with one specific question each ("Where would you break this in an interview?" / "Is anything misleading to someone who knows the front?") | J | 1.5 | 4.4 | emails logged | both sent by Nov 7 |
| 4.6 | **Optional, D10:** CNAS × Breaking Defense Pathfinder essay (800–1,000 words, unpublished, no gen-AI text, deadline **8 Nov** 11:59 pm ET, https://www.cnas.org/next-generation-programs/pathfinder/pathfinder-2026): "Open thermal satellite data is a sensor the US does not treat as one: a coverage standard." Must be written by Jackson in his own words (contest rule); Claude may only check facts | J | 5 | RESULTS.md | essay submitted | only if W3 checkpoint was green and D10 = yes |
| 4.7 | Decide air-defence note (D7): keep (capped 6 h in W5) or drop | J | 0.5 | time remaining | DECISIONS.md | — |
| 4.8 | **Checkpoint W4 (Nov 10):** transfer done; brief draft rendered; reviewers have the packet | J | 0.5 | — | — | — |

W4 totals: **J ≈ 14 h (9 without Pathfinder), C ≈ 30 h.**

### Phase 5 — Dashboard, hardening, side piece (W5, Nov 11–17)

| ID | Task | Owner | Hrs | Inputs | Outputs | Done when |
|---|---|---|---|---|---|---|
| 5.1 | **Dashboard** (D5; default: hand-rolled MapLibre + Observable Plot static page; data Tier A + B): sector-month opportunity map with slider; weekly front TopoJSON; panel charts; latency chart; "sensor status" strip; 7-day lag enforced; footer attribution block; deployed to GitHub Pages | C | 12 | processed outputs | live URL | loads < 3 MB on first paint; works on phone; no point-level front data served |
| 5.2 | Repo hardening: `data/sample/` so CI runs `make all` < 5 min; README as the 30-second interview (headline figure, what was found / not found, three-command reproduce, badges); `CITATION.cff`; `FAQ.md` (interviewer attacks, §5.6); `CHANGELOG.md`; correction policy; Rolodex log of contacts | C drafts, J edits | C 5, J 2 | everything | files | a stranger can `git clone && make all` on the sample in < 5 min |
| 5.3 | **Air-defence note** (if D7 = keep): pre-register the two break dates (2024 Q3→Q4 EW-lost appears; 2025 Q3→Q4 disappears) in `PREREG_airdefense.md`; re-run on Mirror A; cross-check against Mirror B and KAS monthly figures; 2–3 pages, one figure (destroyed-only vs destroyed+EW-lost by quarter); framed as D010 mode 9 (filmable-weapon claim inflation) and as an extension of CSIS's denominator | C 4, J 2 | 6 | airdefense/out; Mirror B; KAS | `report/intercept_note.qmd` | renders; numbers reproduce the airdefense VERDICT table |
| 5.4 | Incorporate reviewer comments; log changes in CHANGELOG with "reviewer (methods)" / "reviewer (SME)" attribution (no names without permission) | J 3, C 3 | 6 | replies | revised brief | every comment has a response (accepted / rejected with reason) |
| 5.5 | Optional: AFK early-career conference abstract (deadline **11 Nov**, jungeafk@gmail.com) | J | 1 | RESULTS.md | sent | only if J wants the credential |
| 5.6 | Zenodo–GitHub integration enabled; dry-run release `v0.9-rc` | C | 1 | repo | release | Zenodo picks up `CITATION.cff` |
| 5.7 | **Checkpoint W5 (Nov 17):** dashboard live; reviewer comments in; repo reproducible | J | 0.5 | — | — | — |

W5 totals: **J ≈ 9 h, C ≈ 30 h.**

### Phase 6 — Ship (W6, Nov 18–24)

| ID | Task | Owner | Hrs | Inputs | Outputs | Done when |
|---|---|---|---|---|---|---|
| 6.1 | Final brief: HTML + Typst PDF; "how to cite / what this does and does not claim" paragraph; stamps on every number; LIMITS as long as findings | C 4, J 4 | 8 | 5.4 | `report/brief.html`, `report/brief.pdf` | J has read the PDF end to end on paper |
| 6.2 | Tag `v1.0`; Zenodo DOI; freeze the analysis layer (living layer continues) | C | 1 | — | DOI | DOI in README and brief |
| 6.3 | SSRN posting (free, no endorsement) of the brief as a working paper; arXiv only if the instructor endorses (stat.AP or physics.soc-ph) | J | 2 | PDF | SSRN URL | posted |
| 6.4 | Landing page (GitHub Pages index): one figure, three sentences, five buttons (Dashboard / Brief HTML / PDF / Repo / DOI) | C | 2 | — | URL | live |
| 6.5 | Outreach day (§10): LinkedIn post (honest-null hook), X/Bluesky thread with three figures tagging only prior-art authors, HN "Show HN", r/CredibleDefense (read rules first), Bellingcat pitch email (no attachments), CSIS Futures Lab memo (if 5.3 done), Solstad/Zhukov/Van Den Hoek/DeepState thank-you with results | J | 4 | everything | posts sent; Rolodex updated | one neutral post per channel; no reply-debates |
| 6.6 | Resume bullet and pitch finalised (§13) with the real numbers | J 1, C 0.5 | 1.5 | RESULTS.md | `planning/RESUME_PITCH.md` | numbers match v1.0 |
| 6.7 | Post-mortem: what the pre-registration got wrong; `DEVIATIONS.md` finalised | J | 1 | — | file | — |

W6 totals: **J ≈ 13 h, C ≈ 15 h.** Grand total **J ≈ 65–70 h** (leaves ~15 h slack against the 84 h budget), **C ≈ 215 h.**

---

## 4. Data plan

### 4.1 Every source

| # | Source | Role | How obtained | Format / size | Licence | Attribution / redistribution rule | Verified |
|---|---|---|---|---|---|---|---|
| 1 | **NASA FIRMS VIIRS S-NPP yearly country CSVs** 2012–2025, Ukraine; 2022–2025 Russian_Federation; 2012–2020 Azerbaijan, Armenia; 2012–2025 Sudan | fire detections, baseline years | `https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/<yr>/viirs-snpp_<yr>_<Country>.csv`, no key | CSV; Ukraine ~4–8 MB/yr; Russia 76 MB/yr; AZ 0.4 MB/yr; Sudan ~10–16 MB/yr | NASA open data; acknowledgment text required (scout_risks §2.1) | redistribute OK; ship fetch script instead | yes (scouts, HEAD 200) |
| 2 | **FIRMS area API** `VIIRS_NOAA20_SP`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT`, `VIIRS_SNPP_NRT`, `VIIRS_SNPP_SP` | NOAA-20/21 detections; 2026; living layer | `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{KEY}/{SOURCE}/22,44,42,53/5/{date}`; free MAP_KEY; 5,000 tx/10 min | CSV ~150 MB total | same | same; record SP vs NRT per row | yes (today) |
| 3 | **FIRMS data_availability** | authoritative sensor start dates | `/api/data_availability/csv/{KEY}/ALL` | CSV | — | — | needs key |
| 4 | **FIRMS all-country zips 2019–2021** | global blind-season map | `/data/country/zips/viirs-snpp_<yr>_all_countries.zip` | ~385 MB each | same | aggregate only | yes (pattern verified for 2024) |
| 5 | **MODIS yearly Ukraine 2022–2025** | overpass-proxy cross-check only | same pattern, `modis` | ~3 MB/yr | same | — | yes |
| 6 | **DeepState history API** (1,785 snapshots 2022-04-03→) | primary control coding C1/C2 | `https://deepstatemap.live/api/history/public`; `/api/history/<id>/geojson`; polite 1 req/2–3 s | KML-style GeoJSON 200 KB–1 MB each; 0.5–1 GB | DeepState licence; research use unnamed; identical copies prohibited | **never redistribute polygons**; derived sector-week scalars only; attribution with logo/link; email sent W1 | licence yes (today); endpoints yes (feasibility) |
| 7 | **cyterat/deepstate-map-data** daily 2024-07-08→ | E and living layer | GitHub raw files | GeoJSON 75 KB/day | mirror code GPL-3.0; data = DeepState's | fetch, don't vendor | yes |
| 8 | **ISW/CTP ArcGIS feature services** (`UkrainianCoTTimelapse_FEB_2022_to_DEC_2024_view/FeatureServer/0`, monthly 2025–26 services) | second control coding; latency test | ArcGIS REST, `f=geojson`, `resultOffset` paging | ~200 MB | copyright ISW/AEI CTP; no licence text **[UNVERIFIED terms]** | agreement statistics only; no geometry redistribution; email W1 | service verified by scout |
| 9 | **The Economist war-fire repo** `output-data/` | cloud series cross-check; ISW daily area 2022–23; `war_fire` label (stretch) | `git clone https://github.com/TheEconomist/the-economist-war-fire-model` | CSV; ~250 MB | code MIT, data CC BY 4.0 | cite Solstad 2023 | yes |
| 10 | **Natural Earth 1:50m admin-0** | border/coast cut | on disk | GeoJSON 3 MB | public domain | note Crimea coding | yes |
| 11 | **ERA5 single-levels `tcc`** (0.25°, hourly) and **ERA5-Land `snow_depth`, `swvl1`** | cloud at overpass; snow; fuel moisture | CDS API (`cdsapi`), free account | NetCDF ~150 MB (sampled hours) | CC BY 4.0 (C3S/ECMWF) | "Contains modified Copernicus Climate Change Service information [2026]" | dataset exists; queue times variable |
| 12 | **ESA WorldCover 2021 v200** (10 m) | fuel/land-cover shares | https://worldcover2021.esa.int/download tiles for 22–42E/44–53N and Sudan | COG ~2 GB (Ukraine) | CC BY 4.0 | cite ESA WorldCover | yes |
| 13 | **Copernicus DEM GLO-30** | slope/ruggedness | `s3://copernicus-dem-30m/` (eu-central-1, no account) | COG ~1 GB | Copernicus licence | attribution | yes |
| 14 | **GHSL GHS-BUILT-S R2023A** | urban mask / industrial false-positive screen | https://ghsl.jrc.ec.europa.eu/download.php | GeoTIFF ~200 MB | CC BY 4.0 | — | yes |
| 15 | **UCDP GED 26.1** + **Candidate 26.0.x** | Sudan events (T2) | https://ucdp.uu.se/downloads/ | CSV zip 39 MB + 1.4 MB | CC BY 4.0 | cite Davies/Pettersson/Öberg 2026 JPR + Sundberg & Melander 2013; Hegre et al. 2020 for Candidate | yes |
| 16 | **Bellingcat civilian-harm TimeMap** | detection-rate validation | JSON URL (above) | 1.1 MB, 2,517 incidents | LICENSE.md type **[UNVERIFIED]** | link, don't vendor | endpoint yes |
| 17 | **GeoConfirmed** `/api/placemark/Ukraine` | detection-rate validation | REST | 7 MB, 60,783 placemarks | terms **[UNVERIFIED]**; ask | aggregates only | endpoint yes |
| 18 | **Wikipedia Timeline of the 2020 Nagorno-Karabakh war** + GeoNames `AZ.txt` | T1 capture dates | manual compile + `https://download.geonames.org/export/dump/AZ.zip` | CSV 30 rows | CC BY-SA / CC BY | cite | yes (scout) |
| 19 | **OCHA/GeoNames Sudan settlements** `SD.txt` | T2 settlement list | GeoNames dump | ~5 MB | CC BY 4.0 | — | GeoNames yes; HDX COD **[UNVERIFIED URL]** |
| 20 | **Yale HRL / HRW / CIR Sudan arson reports** | T2 hand-labelled set (stretch) | PDFs, manual table | ~100 rows | reports © authors; facts | cite each report | index yes; 2026 PDF 410 |
| 21 | **Ivaniuk missile-attacks dataset** (Mirror A to 2026-06-14; Kaggle for refresh), **KAS Air War Monitor** | side piece | on disk; Kaggle account | CSV | Kaggle dataset licence **[check]** | cite | yes (airdefense pass) |
| 22 | **ISW daily assessments** | phase table sources | web | URLs | © ISW; quoting with link | — | yes |

**Excluded on purpose:** ACLED (EULA), Liveuamap (paid, scraping breaches terms), Maxar/Planet/Umbra open data (no conflict collections), VIIRS Nightfire (EOG account; stretch only), Sentinel-1/2 processing.

### 4.2 Storage layout

```
frontline-from-space/
  data/
    MANIFEST.json              # one row per file: url, sha256, bytes, retrieved_at (UTC), product (SP/NRT), licence, notes
    raw/                       # gitignored; rebuilt by `make data`
      firms/baseline/          # S-NPP 2012–2021 UA, 2012–2019 AZ/AM, 2012–2022 SD
      firms/yearly/            # UA 2022–2025, RU 2022–2025, AZ/AM 2020, SD 2023–2025, MODIS
      firms/api/               # NOAA-20 SP, NOAA-20/21/SNPP NRT by 5-day chunk, filename carries source + dates
      firms/global/            # all-country zips 2019–2021
      deepstate/mirror/        # cyterat daily
      deepstate/api/           # 1,785 history snapshots (never leaves this machine or the repo's gitignore)
      isw/                     # ArcGIS pulls
      economist/               # clone of output-data
      era5/  worldcover/  dem/  ghsl/  ucdp/  events/  geonames/
    interim/                   # gitignored; cleaned parquet per source
    processed/                 # committed if < 10 MB: panels, opportunity aggregates, weekly fronts (derived), baselines
    sample/                    # committed: 3 sectors × 20 weeks for CI
  planning/                    # PREREG.md, POWER.md, ukraine_phase_table.md, T2_FORECAST.md, DECISIONS.md, DEVIATIONS.md, UNBLIND_LOG.md, CHECKPOINTS.md
  out/                         # committed result tables (small CSV) with the unblind timestamp in the header comment
  figs/                        # SVG + PNG, data behind each figure in figs/data/
  report/                      # brief.qmd, intercept_note.qmd, references.bib
  site/                        # static dashboard
  R/                           # fixest cross-check
  src/ffs/  tests/  .github/workflows/
  LICENSE (MIT)  LICENSE-DATA (CC BY 4.0)  LICENSES.md  LICENSES/correspondence/  LIMITS.md  PUBLICATION_RULES.md  FAQ.md  CITATION.cff  CHANGELOG.md
```

Totals: ~8–10 GB raw on the laptop; < 50 MB in git; frozen raw snapshot (FIRMS CSVs + derived parquet, **no DeepState/ISW geometry**) as a GitHub Release asset and Zenodo record. Cost: $0.

### 4.3 Fixed data definitions (copied into PREREG.md)
- FIRMS rows kept: `type == 0`; `confidence ∈ {n, h}` (VIIRS) — the Dhage preprint's "no low-confidence at night" artefact is noted; a sensitivity run keeps `l`.
- Satellites pooled; detections counted per satellite (no cross-satellite dedupe; distinct overpasses are distinct looks). Within-satellite duplicates (same `acq_date`, `acq_time`, lat/lon to 4 dp) dropped.
- SP preferred; NRT rows flagged `product = NRT`; any week mixing SP and NRT is flagged in the panel.
- Week = ISO Monday–Sunday. Control snapshot = last snapshot whose `createdAt` falls in the week (DeepState) / last `datetime` in the week (ISW).
- Line of contact = boundary of occupied area, kept only where > 3 km inside the Natural Earth Ukraine border (as in `first_pass.py`); Kursk salient handled from the Russian-side file with the salient boundary as its own "line."
- Area CRS: EPSG:3035 (LAEA Europe) for Ukraine; EPSG:32638 for Karabakh; EPSG:32635/36 (UTM 35/36N) for Sudan, or an Africa Albers equal-area; stated per theatre.
- Front band ±15 km of that week's line; rear strip 50–90 km on the Ukrainian-held side within the sector corridor (descriptive table only); control for inference = pre-war per-cell baseline.
- Sectors: 50 km segments of the phase reference line; perpendicular corridors clipped by bisectors (D1).

---

## 5. Analysis plan

### 5.1 Primary specification (confirmatory, C1)

```
net4_{i,t+1..t+4} = β · log(1 + front_fires_{i,t})
                  + Σ_{k=0..3} ρ_k · net_{i,t−k}
                  + θ · opportunity_{i,t}
                  + α_i + γ_t + ε_{i,t}
```
- *i* = sector (phase-specific corridors), *t* = ISO week. Outcome = net km² gained by Russia (DeepState) over the next four weeks (DeepState batches edits, so a 1-week horizon is below the outcome's timing resolution).
- Inference: (a) CRV1 by sector + wild cluster bootstrap p (Webb, 9,999, `wildboottest` WCR11); (b) Driscoll–Kraay lag 4 (`linearmodels.PanelOLS(cov_type="kernel", bandwidth=4)`; R `fixest` `vcov = DK(4) ~ week` as the cross-implementation). Significant only if both p < 0.05. CRV3-jackknife reported alongside.
- Nickell bias ≈ 1/T ≈ 0.8% with T ≈ 118: noted, not corrected (no Arellano–Bond).
- Equivalence: TOST on the 90% CI against ±β_SESOI = 2.9.
- Sample: C1 only. E and C2 reported separately; pooled estimate reported as exploratory.

### 5.2 Robustness (fixed list; one table; no cherry-picking)
1. Treatment = excess fires over the pre-war p95 baseline; 1b night-only fires; 1c FRP-weighted.
2. Outcome = 1[advance > 1 km² in next 4 weeks] (LPM and FE-logit); IHS(net km²); winsorised at p99.
3. Sector width 25/100 km × band 10/25 km (2×2 grid).
4. Sims leads-and-lags t−4…t+4; joint Wald test that lead coefficients = 0.
5. Drop-one-sector jackknife (plot 22 estimates); drop Donetsk oblast entirely.
6. Phase interaction (manoeuvre vs saturated-linear per `ukraine_phase_table.md`); reverse direction (area → fires) Granger-style joint Wald both ways.
7. Raster twin: H3 res-7 cell × week Poisson/negative-binomial with cell and week FE.
Plus: outcome from ISW instead of DeepState (latency sensitivity); NRT rows excluded; S-NPP only vs pooled sensors.

### 5.3 Detection-opportunity (blind-spot) product
`opportunity_{c,d} = Σ_p looks_{c,d,p} · clear_{c,d,p} · fuel_c · (1 − snow_{c,d})`, per H3 res-6 cell *c*, day *d*, overpass *p*.
- Looks: empirical swath proxy (distinct satellite × `acq_time` with any detection within 200 km that day); MODIS as cross-check; **stretch**: `skyfield` + CelesTrak TLEs for true pass geometry.
- Clear: 1 − ERA5 `tcc` at the nearest pass hour (primary; reproducible from CDS). Cross-check against the Economist national daily cloud series (expected r > 0.8). **Stretch (D2):** MOD09GA/MYD09GA `state_1km` cloud bits in GEE as the actual-look mask; VNP14IMG fire-mask class 4 is the gold standard but the swath download is too heavy for this window.
- Fuel: WorldCover cropland + grassland + tree share; built-up and water cells get fuel = 0 for vegetation fire (urban fires enter only through the `type ≠ 0` sensitivity).
- Snow: ERA5-Land `snow_depth` > 1 cm.
- Two-way decomposition published per sector-month: P(no detection | not observed) vs P(no detection | observed, no fire). This is the G1 claim from the prior-art scout and the only product with no precedent.
- Validation gate (H4) and the "share of km² gained in bottom-quartile opportunity" statistic.

### 5.4 Forecast-skill test (H3)
LightGBM (num_leaves 15, lr 0.05, ≤ 500 rounds, early stopping) and ridge; features B0–B4 as in scout_methods §A7; `TimeSeriesSplit(gap=4)`, expanding window, 8-week blocks; MAE/RMSE; Brier and PR-AUC for the binary target; skill = 1 − MAE(Bk)/MAE(B1); LOSO as spatial check. SHAP for the dashboard only.

### 5.5 Transfer test as a real out-of-sample test
- **T1 (NK 2020):** predictions filed (H5a) → files downloaded → the same `baseline.py` and an `event_study.py` run once. The reproduction of CEOBS's 447 is a calibration step, not the test.
- **T2 (Sudan):** `T2_FORECAST.md` (monthly blind-season forecast from 2012–2022 only) committed in W2 → wartime files downloaded in W4 → Spearman and zero-share comparison run once. Darfur village-burning is pre-declared as *signal* for H5b (it is what the sensor is supposed to see in a raiding war) and as a *confound* for any front-band reading; the brief says so.
- What transfers is the *metric set* (density ratio, blind-season dates, lead/trail sign), not β. The brief states this before the transfer section.

### 5.6 Hostile-reviewer attack list and pre-written answers (goes into `FAQ.md`)
| Attack | Answer in the design |
|---|---|
| "You ran ten specs and picked one." | E is labelled exploratory; C1 is untouched; PREREG tag + OSF timestamp precede the C1 download (manifest `retrieved_at`); pipeline built blind. |
| "p = 0.048 with 22 clusters is nothing." | Wild cluster bootstrap + CRV3 + DK; significance requires both; equivalence bound makes the null a claim. |
| "A null is a power problem." | Power simulation in POWER.md; MDE reported; outcome (iii) "inconclusive" is pre-written and used if the CI covers both 0 and SESOI. |
| "DeepState is slow/biased." | Two independent control codings; latency measured; outcome swapped to ISW as robustness; 4-week horizon. |
| "Fires are just crop burning." | Pre-war per-cell baseline for the same ISO week; WorldCover stratification; night-only variant; detection-rate-by-strike-class table. |
| "Winter zeros are missing data, not zeros." | The opportunity product separates not-observed from observed-no-fire; H4 is about exactly this. |
| "It's Ukraine-specific." | Within-war phase split; NK manoeuvre test; Sudan inverted-season test; global blind-season map; the sensor physics argument. |
| "The sensor is going dark." | S-NPP cutoff 1 Nov 2026 discussed; NOAA-20 SP enters C1; living layer on NOAA-20/21. |
| "Your code is wrong." | Byte-for-byte reproduction test of the feasibility panel; Python and R agree; CI on a sample; DOI. |
| "This helps targeting." | PUBLICATION_RULES.md: sector-week or coarser, ≥7-day lag, no point/FRP/time tables, no event annotation; marginal-contribution-of-publication argument in the brief. |
| "Nickell bias." | ≈1/T; stated; direction noted; no GMM theatre. |

---

## 6. Deliverables (exact formats)

| # | Deliverable | Format | Location | Size target |
|---|---|---|---|---|
| 1 | Pre-registration | `planning/PREREG.md` (Markdown) + OSF registration (secondary-data template) + git tag `v0.1-prereg` | repo + osf.io | — |
| 2 | Brief | Quarto `report/brief.qmd` → self-contained `brief.html` + `brief.pdf` (Typst; Quarto ≥ 1.9 for `pdf-standard` **[upgrade from 1.8.26]**) | GitHub Pages + Zenodo | 5–8 pages; 2,500–3,500 words; 6–8 figures (SVG + 300-dpi PNG; CSV behind each) |
| 3 | Results tables | `out/*.csv` with header comments (unblind timestamp, git hash) | repo | < 1 MB total |
| 4 | Panels and products | `data/processed/panel_c1.parquet`, `panel_c2.parquet`, `panel_e.parquet`, `opportunity_sector_week.parquet`, `opportunity_h3r6_month.parquet`, `baseline_h3r6_week.parquet`, `fronts_weekly_derived.topojson` (derived line segments only), `latency.csv` | repo (< 10 MB each) + Zenodo | CC BY 4.0 |
| 5 | Dashboard | static HTML/JS (MapLibre GL JS + Observable Plot), data as JSON/TopoJSON/Parquet (Tier A + B), `refresh.yml` daily cron (NOAA-20/21 NRT + cyterat), 7-day lag, sensor-status strip, attribution footer | GitHub Pages `/dashboard/` | < 3 MB first load |
| 6 | Repository | MIT code, CC BY 4.0 derived data; `uv.lock`; Makefile; pytest; CI; `data/sample/`; `MANIFEST.json`; `LIMITS.md`; `PUBLICATION_RULES.md`; `LICENSES.md`; `FAQ.md`; `CITATION.cff`; `CHANGELOG.md`; `DEVIATIONS.md`; `UNBLIND_LOG.md` | github.com/<user>/frontline-from-space | < 50 MB |
| 7 | Frozen release | `v1.0` tag; Zenodo DOI (concept + version); release asset zip of FIRMS raw + processed (no DeepState/ISW geometry) | Zenodo | < 2 GB |
| 8 | Working paper | the brief PDF posted to SSRN (and arXiv stat.AP if endorsed) | SSRN | — |
| 9 | Side note (if D7 = keep) | `report/intercept_note.qmd` → HTML + PDF, 2–3 pages, one figure; `PREREG_airdefense.md` | same site | — |
| 10 | Landing page | `index.html`: one figure, three sentences, five buttons | GitHub Pages root | — |
| 11 | Global blind-season figure | `figs/global_blind_season.svg/png` + `out/global_blind_h3r3.parquet` | repo | — |
| 12 | Planning artefacts | `POWER.md`, `ukraine_phase_table.md`, `T2_FORECAST.md`, `DECISIONS.md`, `CHECKPOINTS.md`, `RESUME_PITCH.md`, `corpus_frames.md` | `planning/` | — |

---

## 7. Tooling and stack decisions

| Layer | Choice | Why (rigor angle) | Rejected | Why rejected |
|---|---|---|---|---|
| Env | **uv** + `pyproject.toml` + `uv.lock`, Python 3.12 | one lockfile = reproducibility claim; already installed | conda/pixi; Docker | pixi only if GDAL CLI needed; Docker adds nothing a lockfile doesn't for an interviewer |
| Vector geo | **geopandas 1.1 / shapely 2.1 / pyproj 3.7** | already used; vectorised distance ops | PostGIS | server to defend; no gain at this scale |
| Tabular / H3 | **DuckDB** + `spatial` + `h3` community extension; Parquet | SQL layer is a stated employer keyword; fast H3 binning; no pandas memory games | polars + h3 | fine, but DuckDB gives SQL visibility |
| Raster | **rasterio + rioxarray + exactextract** | zonal stats to H3 locally; reproducible via `make` | GEE as primary | client-server learning curve (8–16 h) and a non-reproducible dependency on a Google account; GEE kept as D2 stretch for the actual-look cloud mask |
| Cloud covariate | **ERA5 `tcc` via CDS** (primary) + Economist series (cross-check) | downloadable, CC BY, reproducible | MOD09GA/VNP09GA in GEE; VNP14IMG swaths | GEE dependency; swath volume |
| Econometrics | **pyfixest** (`feols`, CRV1, CRV3) + **wildboottest** + **linearmodels PanelOLS kernel** (DK) + **R fixest** cross-check | two implementations agreeing is the cheapest strong check; R hits CSIS/Govini keywords | statsmodels only | no clustered wild bootstrap; DK awkward |
| DK in Python | linearmodels `cov_type="kernel"` | verified name | pyfixest DK | **[UNVERIFIED]** docs 404 today |
| Equivalence | hand-rolled TOST on the 90% CI (10 lines) | transparent | `pingouin.tost` | designed for means, not regression coefficients |
| ML | **LightGBM** + sklearn `TimeSeriesSplit(gap=4)`; ridge | standard; the discipline (gap, no shuffle) is what matters | random K-fold | leakage |
| Change-points | **ruptures** (PELT) — descriptive only | small API | — | — |
| Orbits/sun | **astral** (day length); `skyfield` stretch | cheap | — | — |
| Data versioning | **MANIFEST.json** with sha256 + `retrieved_at` + product; pooch registry generated from it | the retrieval timestamps are the audit trail for the prereg ordering | DVC; git LFS | extra CLI/remote; LFS quota |
| Orchestration | **Makefile** | explicit DAG, zero deps | snakemake | overkill |
| Tests/CI | **pytest** (geometry invariants; byte-for-byte E reproduction; Py/R agreement) + GitHub Actions on `data/sample/` | "defensible" in code form | — | — |
| Blinding | `blind.py` seeded week-permutation of the outcome | cheap, auditable | none | — |
| Report | **Quarto → HTML + Typst PDF** | one source, two outputs, citations | LaTeX; Word | heavier / not reproducible |
| Dashboard | **hand-rolled MapLibre GL JS + Observable Plot static page** (D5) | smallest dependency surface; interviewer can read it; no sleeping app | Observable Framework (slowing repo, node toolchain); Streamlit Community Cloud (sleeps 12 h); Felt (no free embed); kepler.gl (reads as "I uploaded a CSV"; use for GIFs only) | as stated |
| Tiles | TopoJSON + JSON aggregates (Tier A), Parquet via hyparquet (Tier B) | < 3 MB | PMTiles/tippecanoe (stretch); R2 | not needed for aggregates |
| Hosting | **GitHub Pages** + Actions cron | $0; 1 GB; Actions free on public repos; range requests OK | Cloudflare Pages/Workers | fine alternative; no need |
| Archive | **Zenodo** via GitHub integration; SSRN for the paper | DOI; free | HF Datasets | optional second copy |
| Preregistration | **OSF Registries**, secondary-data template + git tag | external timestamp + internal hash | git tag alone | no third-party timestamp |

Learning-curve budget (from scout_methods §B3, trimmed by skipping GEE): DuckDB 4–8 h, pyfixest/linearmodels 3–6 h, LightGBM CV 3–5 h, rasterio 4–8 h, Quarto 3–4 h, MapLibre 10–20 h capped, R fixest 2–4 h. Most of this is Claude's to absorb; Jackson needs to be able to *explain* each choice, which is what `FAQ.md` is for.

---

## 8. Contingencies

| Risk | Trigger (observable, dated) | Fallback | Cost of fallback |
|---|---|---|---|
| **DeepState backfill unavailable** (API blocked, rate-limited, or explicit refusal) | 2.1 fails by Oct 23, or a refusal email arrives | Use **ISW/CTP timelapse** (7,540 polygons 2022-02-24→2024-12-31) as the C1 outcome; DeepState only from the mirror (E) and only if permission silence persists; PREREG already names ISW as the alternate outcome, so this is a logged deviation, not a redesign | Coarser, more conservative outcome; latency section becomes one-sided; ~4 h rework |
| **ISW layers also unavailable** (service withdrawn or terms refuse) | 2.2 fails and 2.1 fails | Economist `areas_of_control_daily_summary.csv` gives national ISW area 2022-02→2023-11 (no sectors); run a national-only descriptive and the E panel; declare C1 panel infeasible; **pause trigger** per scout_risks §9 | Project loses its primary test; ship blind-spot product + transfer + E-labelled-exploratory |
| **NOAA-20 SP pull fails** (API 504s, key issues) | 2.3 incomplete by Oct 24 | FIRMS Archive Download tool (Earthdata login, email delivery, CSV; NOAA-20 from 2018-04-01); or run C1 on S-NPP only (pre-registered as acceptable: "pooled sensors where available") | 1–2 days' delay |
| **S-NPP cutoff** (1 Nov 2026; date may move) | Nov 1 refresh fails or returns empty S-NPP | Living layer already NOAA-20/21 only (2.12); frozen analysis unaffected; LIMITS paragraph pre-written | none |
| **CDS queue / ERA5 delay** | 1.13 not delivered by Oct 24 | Economist daily cloud series (national + east) as the interim `clear` term; ERA5 swapped in when it lands; or MOD09GA via GEE if D2 account exists | opportunity product coarser in space for a week |
| **Null everywhere** (H1 ratio < 3? unlikely; H2 equivalence; H3 no skill; H4 < 30%; H5 flat) | W3 results | This is the pre-registered expectation for H2/H3. For H4/H5, a null is still a measured number with a CI. Brief title is about the sensor, not the forecast; lead with H1 + opportunity product + latency + detection-rate table. **The project does not depend on any positive β.** | none; it is the design |
| **Inconclusive H2** (CI covers 0 and SESOI) | TOST fails and significance fails | Report outcome (iii) verbatim; add C2 replication and pooled E+C1 as *exploratory* with the MDE; state the sample needed | none analytically; honesty cost only |
| **Transfer case fails** (T1 reproduction of 447 off by > 10%; T2 Spearman < 0.7) | W4 | Reproduction failure → investigate type/confidence filters, report both numbers; a failed forecast is a finding ("blind season is not predictable from the baseline alone") and is pre-written; Sahel/Yemen one-figure appendix from the global map remains | none; report |
| **Transfer case infeasible** (geocoding of NK captures too noisy; GeoNames gaps) | 2.11 < 20 of 30 settlements geocoded | Reduce to the 10 largest towns (Jabrayil, Hadrut, Fuzuli, Zangilan, Qubadli, Shusha, …); say so | smaller event study |
| **Time runs short** (any checkpoint red) | W3 checkpoint red | Cut in this order: raster twin (2.9) → air-defence note (5.3) → Pathfinder essay (4.6) → T2 precision/recall (stretch) → T2 entirely → PMTiles/DuckDB-WASM → dashboard reduced to static figures + a map image. **Never cut:** PREREG, C1 primary + robustness, opportunity product, LIMITS, repo, brief | — |
| **Licensing problem** (DeepState refuses research use; ISW objects; Bellingcat/GeoConfirmed restrict) | any refusal email | DeepState: publish derived scalars only (already the rule) and remove DeepState-derived processed files from Zenodo if asked, keeping the fetch script; ISW: drop the agreement statistics figure; Bellingcat/GeoConfirmed: drop the detection-rate table to a footnote with aggregates only | one figure each |
| **OPSEC concern** (a reviewer or a Ukrainian contact says a product is too fine) | any such message | PUBLICATION_RULES already at sector-week/≥7-day lag; escalate to sector-month and 14-day lag; remove the living layer's last-30-days points layer, keep the coverage strip; the blind-spot product stays monthly × sector | hours |
| **pyfixest lacks DK; linearmodels misbehaves** | 2.10 | R `fixest` becomes the DK source of truth; Python reports CRV1/CRV3/wild bootstrap | none (R installed) |
| **Economist cloud series undocumented** | can't find its derivation | use it only as a correlation cross-check, not as an input | none |
| **Reviewer silence** | no reply by Nov 14 | ship anyway; README states "reviewed by: none external as of v1.0; comments invited"; update at v1.1 | credibility slightly lower |
| **Partisan pile-on after publication** | replies/quote-posts | one factual response at most; mute; `LIMITS.md` pinned; correction policy | — |

---

## 9. Decision points for Jackson

| ID | Decision | Options | Recommendation | Decide by |
|---|---|---|---|---|
| **D1** | Unit of analysis for a front that moves 100+ km in 2022 | (a) fixed 2024-12-30 sectors (breaks in 2022); (b) phase-specific 50 km corridors re-cut at each phase boundary from `ukraine_phase_table.md`; (c) H3 cells as primary | **(b)** as primary (comparable to E; corridors fix the Voronoi flaw), **(c)** as robustness spec 7 (immune to the choice) | Oct 14 |
| **D2** | Cloud source for the opportunity product | (a) ERA5 `tcc` via CDS; (b) MOD09GA/VNP09GA actual-look mask via GEE; (c) Economist national series only | **(a)** primary with (c) as cross-check; register a GEE non-commercial project anyway and do (b) only if approved by Oct 21 and time allows | Oct 14 |
| **D3** | DeepState permission path | (a) email and proceed with derived-only publication regardless of reply; (b) wait for reply before backfill; (c) skip DeepState, use ISW for C1 | **(a)**: the licence encourages reuse of content with attribution, the backfill is polite and one-time, and nothing of DeepState's geometry is redistributed; log the request | Oct 14 |
| **D4** | Transfer cases | (a) NK only; (b) NK + Sudan blind-season; (c) NK + Sudan + Syria (if ACLED/Carter control downloadable); (d) Sudan only | **(b)**: NK is the manoeuvre test, Sudan is the season test; Syria needs a 30-min check of Carter Center access and ACLED is excluded anyway | Oct 14 |
| **D5** | Dashboard stack | (a) hand-rolled MapLibre + Plot; (b) Observable Framework; (c) Streamlit | **(a)** | Nov 4 |
| **D6** | Working-paper venue | (a) SSRN only; (b) SSRN + arXiv (needs endorser); (c) SocArXiv | **(b)** if the econ-stats instructor endorses, else (a) | Nov 18 |
| **D7** | Air-defence side note | keep (capped 6 h in W5) / drop | **keep if W3 checkpoint is green**; it is cheap (numbers already reproduce), corrects a cited CSIS figure, and gives the portfolio a theatre-agnostic "measurement forensics" piece; drop first if behind | Nov 10 |
| **D8** | ACLED | use privately for a robustness footnote / exclude entirely | **exclude** (EULA; reproducibility; UCDP suffices) | Oct 14 |
| **D9** | S-NPP cutoff handling in C2 and living layer | (a) C2 ends Sep 30 2026, living layer NOAA-20/21 only; (b) include Oct 2026 S-NPP | **(a)** | Oct 14 |
| **D10** | CNAS Pathfinder essay (Nov 8) | yes / no | **yes only if W3 is green and Jackson wants to write 1,000 words himself in W4** (contest requires no gen-AI text; exclusive and unpublished, so it cannot reuse brief text); otherwise skip without regret | Nov 3 |
| **D11** | Reviewer targets | instructor + (Solstad / Zhukov / Van Den Hoek) | send the *pre-registration* to all three in W1 with one question each; whoever replies becomes the SME reviewer | Oct 17 |
| **D12** | Name and framing | "Front line from space" vs sensor-first title | sensor-first title for the brief and paper ("What a free thermal satellite feed can and cannot tell an analyst about a war: a pre-registered Ukraine test with Karabakh and Sudan checks"); keep "Front line from space" as the repo/dashboard name | Nov 4 |

---

## 10. Publishing and outreach plan

**Order (from scout_audience §B and the risk scout):** repo + DOI → landing page + LinkedIn → SSRN → Bellingcat pitch and CSIS Futures Lab memo in parallel → MWI as fallback → X/Bluesky/HN/r/CredibleDefense thread the same day the brief goes up → USGIF poster application in Jan 2027.

| When | Action | Channel / contact | Notes |
|---|---|---|---|
| W1 (Oct 14–20) | Pre-registration shared with Solstad (sondresolstad@economist.com, GitHub issue), Zhukov (ymz2 at georgetown), Van Den Hoek (vandenhj@oregonstate.edu), DeepState (API request form) | email | < 200 words, one figure (E front/rear monthly table), one specific question each; log in Rolodex |
| W4 (by Nov 7) | Review packet to the two reviewers | email | PREREG + RESULTS + draft brief |
| W4 (Nov 8) | Pathfinder essay (optional, D10) | https://www.cnas.org/next-generation-programs/pathfinder/pathfinder-2026 | Jackson's own words |
| W5 (Nov 11) | AFK early-career abstract (optional) | jungeafk@gmail.com | — |
| W6 (Nov 24) | `v1.0`, Zenodo DOI, SSRN | — | — |
| W6 (Nov 24) | LinkedIn post (second post after the Ukraine reflection; honest-null hook: "I pre-registered a hypothesis and it did not survive. Here is what the sensor *can* do.") | LinkedIn; `~/Jackson Mackney/LinkedIn/posts/` | tag nobody unknown |
| W6 (Nov 24) | X + Bluesky thread: three figures (opportunity map, latency, NK event study), repo, DOI; tag only @Sondreus, @Black_BirdGroup, @bradyafr (prior art / data producers) | X, Bluesky | one post; no reply-debates |
| W6 (Nov 24) | Show HN: dashboard + honest-null framing | news.ycombinator.com | — |
| W6 (Nov 24–25) | r/CredibleDefense (read sidebar rules first), r/OSINT, r/geospatial | Reddit | — |
| W6 (Nov 25) | Bellingcat pitch: 300–500 words, working headline, one-sentence topline, **no attachments** | submissions@bellingcat.com | Resources piece: "A pre-registered test of FIRMS against two control maps, and a month-by-month blind map" |
| W6 (Nov 25) | CSIS Futures Lab memo (if D7 = keep): 2 pages + code, framed as extending their salvo model past Oct 2024 with the EW-lost denominator fix | Atalan/Jensen via CSIS staff pages or LinkedIn | not a takedown |
| Dec 2026 | MWI pitch if Bellingcat declines (600–2,500 words, Word, Chicago; MWIsubmissions@westpoint.edu) | email | "sensor literacy for staff officers" |
| Dec 2026–Jan 2027 | Bellingcat Tech Fellowship call (historically ~15 Jan deadline) — pitch the opportunity product as the tool | bellingcat.com | — |
| 20 Jan–3 Mar 2027 | USGIF GEOINT 2027 Student Poster (symposium 17–19 May 2027, Kissimmee) | education@usgif.org | the room is GEOINT recruiters |
| ongoing | Kaggle dataset of the panel + opportunity product (CC BY) | Kaggle | cheap discovery |
| never | War on the Rocks as first stop (students rejected without non-academic experience); Lawfare (wrong genre); ISW Russia internship (Russian required) | — | — |

Promotion rules (from scout_risks): one neutral post per channel; Ukrainian transliterations; "open-source assessments," never "truth"; no travel to RU/BY/occupied territory while public; log foreign professional contacts.

---

## 11. How the Future_of_War corpus is used

The corpus has never touched satellite fire data (grep returns zero hits), so it contributes **frames, hypotheses, comparisons and an honesty apparatus**, never numbers. Rules, from `scout_corpus_assets.md`:

1. **Spine of the brief = D015's detect → identify → custody → effect chain** (`council/debates/D015_transparency_reconciliation.md:81`). Each link gets a measured number: detect = H1 ratio and the opportunity product; identify = baseline/WorldCover/night-only/detection-rate-by-class; custody = overpass gaps and the latency table; effect = H2/H3. The feasibility null is an *effect-link* null, not a detect-link null. Stamp: Med-High · elicited for the reconciliation; the identify-stage recurrence High · documentary.
2. **D008 force-to-space regimes** (`D008:79–90`, High · documentary — one of four Highs surviving D022) supply the phase coding for `ukraine_phase_table.md` and the sentence "the method was tested first in the regime least likely to show a lead." The mechanical test is applied *before* any C1 fire data is seen (task 1.6).
3. **D011 reconnaissance-strike symmetry** (`D011:58`, Med/Low-Med) supplies the within-war hypothesis (fires lead only in asymmetric/manoeuvre phases). Cited as a hypothesis the fire data tests, with D019's SCOPE riders; never as a confirmed mechanism.
4. **D010 mode 9** (filmable-weapon kill-claim inflation, `D010:309–316`, Med-High) frames the air-defence side note.
5. **D022 two-axis stamp** (`mechanical / documentary / definitional / elicited`; elicited never High) is adopted verbatim in the brief, README and every results table (`basis` column). Every FIRMS/DeepState number is `mechanical`; every "fires = combat" interpretation `documentary`; every corpus prevalence claim `elicited`.
6. **Historical comparisons** for the attrition-vs-manoeuvre paragraph: WWI Western vs Eastern Front (`ww1_1914.md:78`), Iran–Iraq's ~1,100 km Basra line (`iran_iraq_1980.md:33`), Korea's manoeuvre→saturated-linear transition (`korean_war_1950.md:69`), Yemen's custody problem (`yemen_civil_war.md:86`). Stamp Med · documentary; resolve any S-TMP figure against `01_source_log.md` before quoting.
7. **Transfer justification**: `04_rest_of_world.md:152` ("corridor- and node-based density regimes … should not be analyzed with a European linear-front denominator") and the Sudan deep-dive's node list (~line 73) justify changing the outcome to events and the geometry to settlement buffers; D023 justifies spending real time on Sudan.
8. **Watchboard**: the sector-week panel is a live TRNS-2 / MANV-3 feed the corpus specified but never ran (`09_watchboard_population.md:17–31`); one sentence in the brief.
9. **Prediction-failure modes** (`failure_modes.json`; D010; D019's "theory-primed measurement") are named in LIMITS with the design choice each one *changed* (pre-registration, per-cell baseline, Sudan test) — to avoid the corpus's own "disclosure has replaced correction" failure (`00_SKELETON.md:62`).
10. **Do not cite:** any census count, share or cross-tab (236/239 High stamps carry < 2 sources; density × symmetry coding quarantined; triangulation two-legged with shared URLs; S-ID namespace collided); the three landscape chapters' D011 applications; wave-9 chapters 3.4 and 3.6.
11. **Concrete artefact:** `planning/corpus_frames.md` with the verbatim blocks (D015:81, D008:79–86, D019:194, D022:325–336, D010:309–316) and file:line, created in W1 by Claude (1 h).

---

## 12. Air-defence side piece: slotted in, capped, cut first

**Decision: keep, conditional (D7).** Slot: W5 task 5.3, hard cap 6 hours (C 4, J 2). Pre-conditions: W3 checkpoint green. Cut order: first.

Design (rigor version of airdefense VERDICT part (a)):
- `PREREG_airdefense.md` filed before re-running: the claim is that the drone "destroyed" rate falls when the "locationally lost / EW" category appears (2024 Q3→Q4: EW share 0.09→0.40; destroyed 0.55→0.48) and recovers when it disappears (2025 Q4: 0.00; destroyed 0.81–0.91), and that destroyed + EW-lost is flat 2024–2026 (0.93/0.86/0.89). Prediction: Mirror B and KAS monthly figures show the same category entry/exit; if Mirror B shows the dip without the category change, the dip is real and the note says so.
- Inference clustered by night (the airdefense VERDICT's main methodological point); no saturation claim; no cross-theatre overlay on one axis.
- Framed as D010 mode 9 and as an extension of CSIS Futures Lab's denominator (their 0.64 for 2025 is destroyed-only); sent to Atalan/Jensen as a memo, not a takedown.
- Output: `report/intercept_note.qmd` → 2–3 pages, one figure; same site; `PREREG_airdefense.md`.
- Part (b) of the airdefense VERDICT (Patriot-shortage difference-in-differences across weapon classes) is **dropped** from this project: it needs delivery-date data and night-clustered inference on a handful of nights; it is a separate 1–2 week piece.

---

## 13. Resume bullet and 60-second pitch the plan is designed to produce

**Resume bullet (one line; numbers to be replaced with v1.0 values):**
> Pre-registered and tested whether a free satellite thermal feed (NASA FIRMS) leads territorial change in Ukraine: built a reproducible Python/DuckDB/R pipeline fusing ~600k VIIRS detections with two independent control maps into a 22-sector × 190-week panel; fixed-effects inference with wild-cluster-bootstrap and Driscoll–Kraay SEs and an equivalence bound; shipped the first quantified "blind-spot" coverage product for a conflict sensor, an out-of-sample transfer test (Nagorno-Karabakh, Sudan), a 7-page brief, a public repo (DOI) and a daily-refreshing dashboard.

**60-second interview pitch:**
> "Everyone who has looked at NASA's free fire-detection feed over Ukraine says the same thing: the hotspots trace the front. I wanted to know whether that is *useful* to an analyst — can it tell you where the line will move, and when is it lying to you by showing nothing? So I pre-registered one specification on OSF, built the pipeline blind, and ran it once on two years of data I had not touched, with two independent control maps. Result: fires are an excellent locator — front-band density is five to seventeen times the rear every month against a pre-war baseline — but as a leading indicator they add about half a percent over last week's momentum, and I can bound the effect: a doubling of fires buys you less than two square kilometres of four-week advance per sector. The more useful product came out of asking *why*: I built a detection-opportunity layer from overpass geometry, cloud, snow and fuel, and about a third of all Russian gains happened in sector-weeks the sensor could barely see. Then I checked it wasn't a Ukraine story: in Karabakh 2020, a manoeuvre war, fires trailed the advance; in Sudan the blind season I forecast from pre-war data alone matched what happened. Everything is open — code, data, DOI, a dashboard that refreshes only the descriptive layer so the pre-registered result never drifts. And the sensor it all runs on, Suomi-NPP, goes dark on November 1st, which is its own lesson about depending on a single free feed."

The pitch is written so that every sentence maps to a pre-registered hypothesis or a measured product; if H2 turns out "inconclusive" rather than "equivalence established," the fourth sentence changes to "and the data cannot yet rule in or out an effect of practical size — here is the sample that would," and nothing else moves.

---

## Appendix A — What this plan could not verify (do in W1)
- OSF template osf.io/x4gzt is live and usable in OSF Registries.
- pyfixest Driscoll–Kraay syntax (reference page 404); plan assumes linearmodels + R.
- ISW/CTP reuse terms (Cloudflare-blocked); DeepState stance on research use (email).
- Bellingcat TimeMap LICENSE type; GeoConfirmed terms.
- VNP09GA cloud bit layout (irrelevant if D2 = ERA5).
- NOAA-21 orbital offset relative to NOAA-20/S-NPP (only affects the stretch orbit model).
- Economist `cloud_cover_in_ukraine_by_day.csv` derivation (treated as cross-check only).
- Scientific Reports 2026 Nightfire paper DOI (prior-art scout read the PDF; cite from that).
- S-NPP cutoff date may move ("subject to change").
- Sizes of PMTiles/Parquet outputs (stretch only).

## Appendix B — Sources added by this plan (beyond the scouts)
- NASA Earthdata alert, Suomi NPP data product delivery to cease 1 Nov 2026: https://www.earthdata.nasa.gov/data/alerts-outages/suomi-npp-data-product-delivery-cease-november-1-2026
- NASA Earthdata wiki, S-NPP anticipated end of life late 2026 / NOAA-21 replacement: https://wiki.earthdata.nasa.gov/x/oQV5F
- FIRMS area API source list and limits: https://firms.modaps.eosdis.nasa.gov/api/area/
- DeepStateMap licence (re-read): https://deepstatemap.live/license-en.html ; API request: https://api.deepstatemap.live/request
- Secondary-data preregistration template (LDbase pointer to osf.io/x4gzt): https://ldbase.org/resources/templates/preregistrations-using-secondary-data-analysis ; tutorial: https://open.lnu.se/index.php/metapsychology/article/view/2625
- R fixest DK/NW: https://search.r-project.org/CRAN/refmans/fixest/html/vcov_hac.html
- wildboottest (PyPI): https://pypi.org/project/wildboottest/ ; background: https://www.r-bloggers.com/2022/11/fast-wild-cluster-bootstrapping-in-python-via-wildboottest-%f0%9f%90%8d/
