# Front line from space — project plan, SHIP-FIRST / PORTFOLIO-FIRST draft

**Key:** `ship` · **Written:** 2026-10-13 · **Ship date:** Tuesday 2026-11-10 (4 weeks from today), hard · **Budget:** $0
**Angle:** optimize for a polished public artifact (dashboard + repo + brief) that is in front of employers by 10 Nov, with analysis good enough to defend to a technical interviewer and scope cut ruthlessly. Everything not needed for that is a stretch goal with an explicit cap.

Inputs read in full: `Conflict_Data_Feasibility/frontline/{VERDICT,FIRST_PASS,SOURCES}.md` and `out/*.csv`, `airdefense/{VERDICT,FIRST_PASS}.md`, and all eight scout files in this folder. Verification done today for this plan (beyond the scouts): FIRMS area-API page lists `VIIRS_NOAA20_SP`, `VIIRS_NOAA21_NRT`, `VIIRS_SNPP_SP`, DAY_RANGE 1–5, 5,000 transactions / 10 min; **no `VIIRS_NOAA21_SP`** ([firms.modaps.eosdis.nasa.gov/api/area](https://firms.modaps.eosdis.nasa.gov/api/area/)). Quarto bundles Typst ([quarto.org](https://quarto.org/docs/output-formats/typst.html)). CNAS Pathfinder: 8 Nov 2026, 800–1,000 words, unpublished, no gen-AI text ([cnas.org](https://www.cnas.org/next-generation-programs/pathfinder/pathfinder-2026)). pyfixest's docs claim HAC estimators but do not name Driscoll–Kraay ([pyfixest.org](http://pyfixest.org/pyfixest.html)) → DK goes through `linearmodels` as planned. Local tooling: `uv 0.12.5`, `quarto 1.8.26`, `node v25.9.0`, `R` present; `duckdb`, `tippecanoe` not installed.

---

## 0. The one-page version

**What ships on 10 Nov (MVP):**
1. Public GitHub repo `frontline-from-space` (MIT code / CC BY 4.0 derived data) with `make all` reproducing the panel from a hashed manifest, CI green, `PREREG.md` tag-dated before the confirmatory data was touched.
2. Static dashboard on GitHub Pages (hand-rolled MapLibre + Observable Plot, under 3 MB of pre-aggregated data, 7-day lag, sector-week or coarser).
3. A 5–8 page brief (Quarto → HTML + Typst PDF) with four results in this order: (a) front-band density is 5–17× rear in every month; (b) the sector-month **blind-spot map** (new); (c) the pre-registered lead-lag test with equivalence bounds (expected honest null); (d) the Nagorno-Karabakh 2020 maneuver-war transfer check.
4. One landing page, a Zenodo DOI, a README that is the 30-second interview, `LIMITS.md`, `FAQ.md`.

**What is cut from MVP and why:** Sudan transfer (4–6 days, no control polygons; replaced by NK 2020 at 1–2 days), ERA5/GEE cloud covariates (CDS queues and a 2-evening GEE learning curve; replaced by the Economist's daily cloud series + overpass counting), PMTiles/DuckDB-WASM raw-point browsing (OPSEC rule forbids point-level front data anyway), ACLED (licence), VNF Nightfire (account + new product), living daily cron (stretch, 1-day cap in week 4).

**Cut order if behind schedule** (first to go at the top): Sudan → living layer → global blind-season map → air-defense side note → 2022 DeepState backfill (fall back to ISW layer, then to "confirmatory = NOAA-20/21-added 2024–25 sample") → NK transfer (never cut below a single figure).

**Jackson's time:** ~55 hours over 4 weeks (≈14 h/week). Claude does code, drafts, pulls; Jackson decides, registers accounts, sends emails, reviews every number, writes the Pathfinder essay himself if he chooses to enter.

---

## 1. Thesis and pre-registered hypotheses

### 1.1 Thesis (one paragraph, goes at the top of the brief)

A free 375 m thermal feed (NASA FIRMS, three VIIRS satellites) is a *locator*, not a *forecaster*, of ground war. Along Ukraine's ~1,100 km line of contact, fire detections within 15 km of the line run 5–17× the density of the same land 50–90 km behind it in every month, so the sensor reliably shows where fighting is. But the sensor is blind for roughly four months a year (fuel, snow, cloud, overpass cadence), and when it can see, its signal co-moves with territorial change rather than preceding it: in a pre-registered sector-week panel with momentum control, fires add about half a percentage point of explained variance over last week's advance. The brief quantifies each link in the chain — detect, identify, custody, effect — says exactly where it breaks, ships a sector-month coverage product an analyst can use to decide when the feed is worth looking at, and checks whether the "concurrent, not leading" pattern also holds in a fast maneuver war (Nagorno-Karabakh 2020). The honest null is the finding; the blind-spot map is the product.

### 1.2 Hypotheses (copied verbatim into `PREREG.md`, committed and tagged before any confirmatory pull)

| # | Hypothesis | Pre-specified test | Success criterion | Failure / null criterion | Prediction |
|---|---|---|---|---|---|
| **H1 Location** | Front-band fire density exceeds the same-cell pre-war (2019–21) same-calendar-week baseline. | Monthly ratio of ±15 km band density to 2019–21 baseline on the same cells; also front/rear strip ratio as in the feasibility pass. | Ratio ≥ 3 in ≥ 9 of 12 calendar months (Jul 2024–Dec 2025 pooled by month), with bootstrap CI (resample sectors) excluding 1. | Ratio < 3 in ≥ 4 months, or CI includes 1 in the fire season. | **Supported** (feasibility: 5–17×). |
| **H2 Lead** | Front fires at week *t* predict Russian net gain over weeks *t+1..t+4*, conditional on momentum. | Primary spec §5.1: `net4 ~ log1p(front) + Σ_{k=0..3} net_{t−k} + opportunity | sector FE + week FE`, CRV1-by-sector **and** Driscoll–Kraay(4). | β > 0, p < 0.05 under both SEs, **and** a doubling of fires implies ≥ 2 km² extra 4-week gain. | Otherwise null. Equivalence: report the 90% CI; if it lies within ±2 km² per log-unit we say "effects larger than the mean weekly gain are ruled out." | **Not supported** (null). |
| **H3 Forecast value** | Fires improve out-of-sample forecasts over momentum-only. | Ridge + LightGBM, rolling-origin CV, 8-week test blocks, 4-week gap, B1 (momentum) vs B2 (+fires lags 0–4). | MAE improves ≥ 5% vs B1 on both the 2024-07→2025-12 sample and the backfill sample (if obtained). | < 5% in either sample. | **Not supported.** |
| **H4 Blind spot** | A material share of territorial change happens when the sensor cannot see. | Detection-opportunity index per sector-week (§5.3); share of total km² gained (Jul 2024–Dec 2025) in sector-weeks in the bottom opportunity quartile. | Share ≥ 30%. | Share < 15% (in between: report as "partial"). | **Supported** (Nov 2024 and Jan–Feb 2025 gains in blind months). |
| **H5 Transfer (NK 2020)** | In a fast maneuver war, fires trail rather than lead settlement capture. | Event study on the Wikipedia/MoD day-by-day capture list (geocoded, ±2 days noise): VIIRS detections within 5 km of each captured settlement, days −14..+14. Replicate CEOBS's 447 detections (26 Oct–4 Nov 2020) first. | "Trail" if mean detections/day in +1..+7 exceeds −7..−1 by ≥ 2× with a sign test p < 0.05 across settlements. "Lead" if the reverse. | Neither → "concurrent". | **Trail** (fires concentrated in the last 10 days around Shusha/Lachin). |
| **H6 Within-war phase** (conditional on obtaining 2022–24 control data) | Fires lead only in non-saturated phases (Kharkiv Sep–Oct 2022, Kherson Oct–Nov 2022). | β × phase interaction in the primary spec, phases coded from the project's own phase table using the D008 written test, fixed before the pull. | Interaction > 0, p < 0.05 both SEs. | Otherwise null → "fires never lead, in any regime." | Weak lead in maneuver phases; honest expectation is a null given winter timing of Feb–Apr and Nov 2022. |

**Rules fixed in `PREREG.md`:** the Jul 2024–Dec 2025 S-NPP panel is declared *exploratory* (≈10 specs already tried). Confirmatory sample for H2/H3 is, in order of preference, (a) 2022-04→2024-07 from DeepState API, (b) 2022-02→2024-12 from the ISW `UkrainianCoTTimelapse_FEB_2022_to_DEC_2024_view` layer, (c) if neither is obtained by Day 14, the 2024-07→2025-12 panel with NOAA-20/21 detections added, labelled "partially confirmatory". No new hypotheses after the tag; deviations logged in `DEVIATIONS.md` with dates. Five robustness specs listed in §5.2, no additions. Every figure caption carries `confirmatory` or `exploratory`.

---

## 2. Scope

### In (MVP, must ship 10 Nov)
- Ukraine, Jul 2024–Dec 2025, S-NPP + NOAA-20 + NOAA-21, type 0, confidence n/h; 22 sectors × 77 weeks (re-cut with perpendicular corridors replacing Voronoi cells).
- Pre-war baseline from FIRMS S-NPP Ukraine 2019–2021 on the same cells and calendar weeks.
- Blind-spot product at sector × month (publication) built from sector × week (analysis).
- Primary spec + 5 robustness specs + forecast-skill table.
- NK 2020 transfer figure and one page.
- Repo, CI, manifest, README, LIMITS, FAQ, PREREG, dashboard, brief (HTML+PDF), landing page, Zenodo DOI, one LinkedIn post, pre-registration emails to 4 prior-art authors.

### Out (explicitly not in this project)
- ACLED (2025 EULA: no direct access, non-reverse-engineerable derivatives, ML restrictions). UCDP only.
- Point-level front-band detections, FRP/time tables, event annotation, anything sub-weekly (OPSEC rules, §8).
- Any Gaza/urban claim at 375 m; Sahel/DRC/Libya/Yemen (one sentence each in LIMITS as fuel/season nulls).
- Casualty estimates, "prediction of Russian advances," production-grade anything.
- VIIRS Nightfire, Sentinel-1/2 processing, GEE, ERA5 (all stretch or dropped).
- Peer-reviewed submission.

### Stretch (only after the MVP is live, each with a cap)
| Stretch | Cap | Gate |
|---|---|---|
| S1 2022–24 DeepState API backfill → H6 phase split | 8 h build + overnight pull | Attempt Days 8–10; if KML-style filter is not clean by end of Day 10, switch to ISW layer (S1b, 4 h) |
| S2 Global blind-season map (FIRMS all-country zips 2019–21, 0.5° monthly zero-detection probability by climate zone) | 6 h | Only if H4 product is done by Day 17 |
| S3 Living layer (daily GitHub Actions cron: last-30-days FIRMS NRT + current DeepState front, "data through" badge) | 8 h | Week 4 only if brief draft done by Day 24 |
| S4 Air-defense EW-lost side note (2–3 pp, 1 figure) | 5 h | Week 4; numbers already reproduced in `airdefense/` |
| S5 Sudan arson/raiding test vs UCDP GED + Yale HRL village list | 4–6 days | Not in the 4 weeks; "v1.1, December" if at all |
| S6 Economist `war_fire` label as alternative treatment column | 3 h | Week 3 if ahead |
| S7 DeepState vs ISW map-latency measurement (G9) | 4 h | Requires S1b data anyway; do if S1b runs |
| S8 One R script reproducing the primary spec with `fixest` (CSIS/Govini keyword coverage) | 2 h | Week 4 |
| S9 CNAS Pathfinder essay (8 Nov) | 6 h Jackson-only | Decision point D6 |

---

## 3. Work breakdown by phase and week

Owner key: **J** = Jackson, **C** = Claude. Hours are Jackson's; Claude tasks list Jackson's review time in brackets. Dates: W1 Oct 14–20, W2 Oct 21–27, W3 Oct 28–Nov 3, W4 Nov 4–10.

### Phase 0 — Day 0 (today/tomorrow, 2 h J)
| Task | Owner | h | Inputs | Outputs | Done when |
|---|---|---|---|---|---|
| 0.1 Register FIRMS MAP_KEY | J | 0.2 | email | key in local `.env`, later repo secret | `/api/data_availability/csv/KEY/ALL` returns rows; record start dates for `VIIRS_NOAA20_SP`, `VIIRS_NOAA21_NRT` |
| 0.2 Create GitHub repo (public from day 1), enable Pages + Actions, 2FA, project email alias | J | 0.5 | — | empty repo, Pages URL | URL resolves |
| 0.3 Decide D1–D5 (§9) | J | 1 | this plan | `planning/DECISIONS.md` | each decision has a one-line rationale |
| 0.4 Send DeepState permission email via API request page; log in Rolodex | J | 0.3 | template in risks scout §2.2 | sent email saved to `LICENSES/deepstate_request.md` | sent |

### Phase 1 — Week 1 (Oct 14–20): freeze, scaffold, pre-register. J ≈ 14 h.
| Task | Owner | h | Inputs | Outputs | Done when |
|---|---|---|---|---|---|
| 1.1 Repo scaffold: `pyproject.toml` + `uv.lock` (py 3.12; geopandas 1.1, shapely 2.1, pyproj 3.7, duckdb, pyarrow, linearmodels, pyfixest, lightgbm, scikit-learn, ruptures, pooch, pytest, ruff), `Makefile`, layout §7.4, MIT + CC BY 4.0 + `CITATION.cff` | C [J 1] | 1 | methods/infra scouts | repo skeleton | `uv sync` clean; `make help` lists targets |
| 1.2 Port `first_pass.py` → `src/ffs/{geometry,panel}.py`; reproduce `sector_week_panel.csv` **byte-for-byte** on the existing 2024–25 data | C [J 1] | 1 | `frontline/scripts/first_pass.py`, raw data copied | `data/processed/panel_v0.parquet`, pytest `test_reproduce_feasibility.py` | Spec C coef = 0.8409 ± 1e-4, n = 1606 |
| 1.3 `data/manifest.yaml` + `pooch` registry; `make data` fetches FIRMS S-NPP Ukraine 2019, 2020, 2021, 2023, 2024, 2025 + cyterat daily files + Natural Earth | C [J 0.5] | 0.5 | URLs §4 | manifest with sha256, bytes, retrieved_at, licence per file | CI runs `make data` on `data/sample/` only; full fetch < 20 min locally |
| 1.4 Write `LIMITS.md` skeleton (10 named items from risks scout §3.2) and `PUBLICATION_RULES.md` (§8 OPSEC rules) | C [J 1] | 1 | risks scout | two files | Jackson has edited and approved wording |
| 1.5 Build `planning/ukraine_phase_table.md` (phases 2022-02→2025-12 coded by the D008 written test, with ISW/Wikipedia dates), and `planning/corpus_frames.md` (verbatim quotes with file:line from D015:81, D008:79–86, D019:194, D022:325–336, D010:309–316) | C [J 1.5] | 1.5 | Future_of_War corpus (read-only) | two files | phase table has ≥ 8 dated phases, each with a source URL and a regime code, fixed **before** any 2022 fire data is looked at |
| 1.6 Write `PREREG.md` (§1.2 + §5.1 + §5.2 verbatim), commit, `git tag prereg-v1`, optional OSF registration (D5) | C drafts, **J signs** | 2 | §1, §5 | tagged commit; OSF URL if chosen | tag exists; no NOAA-20/21 or 2022 data in repo before tag timestamp |
| 1.7 Email the pre-registration (≤200 words + one figure + one question) to Solstad, Van Den Hoek, Zhukov; GitHub issue on cyterat mirror | J | 1.5 | audience scout §C.4 template | sent; Rolodex entries | 3 emails sent |
| 1.8 NOAA-20 SP + NOAA-21 NRT + S-NPP SP pull via API, Ukraine bbox 22–41E / 44–53N, 5-day chunks, 2024-07-01→2025-12-31 (+ 2019–21 NOAA-20 for baseline parity), polite 1 req/s, cached raw CSVs | C [J 0.5] | 0.5 | MAP_KEY | `data/raw/firms_api/*.csv`, manifest rows flagged SP/NRT | ~220 calls/sensor; row count per sensor logged; NRT rows flagged |
| 1.9 Replace Voronoi cells with perpendicular corridors (segment buffered 90 km each side, clipped by bisectors); re-cut 22 sectors; pytest geometric invariants (sectors partition the band, areas sum, no duplicate sector-week) | C [J 1] | 1 | 1.2 | `src/ffs/sectors.py`, `tests/test_geometry.py` | rear strip of every Donetsk sector now has > 0 cells; invariants pass |
| 1.10 Week-1 go/no-go checklist (risks scout §9) | J | 0.5 | all above | `planning/GO.md` | all boxes ticked |

### Phase 2 — Week 2 (Oct 21–27): confirmatory data, baseline, blind-spot product. J ≈ 14 h.
| Task | Owner | h | Inputs | Outputs | Done when |
|---|---|---|---|---|---|
| 2.1 Pre-war baseline: H3 res-6 cells (DuckDB `h3` + `spatial` extensions); per cell × ISO-week empirical median and 95th pct from 2019–21 S-NPP (+NOAA-20 2019–21 if 1.8 succeeded); excess = max(0, obs − p95) | C [J 1] | 1 | 1.3, 1.8 | `data/processed/baseline_cellweek.parquet`, `excess_sectorweek.parquet` | H1 ratio table by month exists; Donetsk 30 km buffer-around-2021-line robustness flag computed |
| 2.2 Detection-opportunity index (§5.3): overpass count = distinct (satellite, acq_time rounded to 10 min) with ≥1 detection anywhere in a 200 km box per day; cloud = Economist `cloud_cover_in_ukraine_by_day.csv` (east-of-country column); fuel-season = 2019–21 baseline amplitude; snow proxy = calendar + baseline zero-weeks (ERA5 is stretch) | C [J 1.5] | 1.5 | 1.8, Economist repo clone (CC BY 4.0) | `opportunity_sectorweek.parquet`, `coverage_sectormonth.json` | validation regression log(front) ~ opportunity | sector + week-of-year FE has strongly positive coefficient; else product is wrong and we fix before using |
| 2.3 **S1 attempt (Days 8–10, 8 h cap):** DeepState history API backfill 2022-04-03→2024-07-07, 1 req / 2–3 s overnight with contact UA string; style-based filter to occupied polygons; weekly snapshots; pytest monotone-area sanity | C [J 1] | 1 | API index (1,785 ids) | `data/raw/deepstate_api/` (gitignored), `fronts_weekly_2022_2024.parquet` | ≥ 95% of weeks have a clean occupied polygon, area series continuous with cyterat series at 2024-07-08 within 1%. **If not by end of Day 10 → S1b.** |
| 2.3b **S1b fallback:** ISW `UkrainianCoTTimelapse_FEB_2022_to_DEC_2024_view/FeatureServer/0` paginated GeoJSON (2000/query), `datetime` field → weekly snapshots. Derived-only use; licence email to ISW sent same day | C [J 1] | 1 | ISW service URL | same outputs from ISW | same test; `DEVIATIONS.md` entry |
| 2.4 Extend panel to the confirmatory window; estimate **primary spec once**, robustness specs once, save all coefficient tables as CSV with the git hash | C [J 2] | 2 | 2.1–2.3, PREREG | `out/tables/primary.csv`, `robustness_*.csv`, `DEVIATIONS.md` if any | Tables match PREREG spec text; Jackson has re-run `make models` himself |
| 2.5 Forecast-skill table (Ridge + LightGBM, `TimeSeriesSplit(gap=4)`, leave-one-sector-out) | C [J 1] | 1 | 2.4 panel | `out/tables/forecast_skill.csv` | B1..B3 MAE/Brier/PR-AUC with skill vs B1 |
| 2.6 NK 2020 transfer: FIRMS Azerbaijan+Armenia 2012–2020 (<5 MB), clip to NKAO+districts polygon, reproduce CEOBS 447, geocode capture list (GeoNames `AZ.txt`), ±14-day event study, one figure | C [J 2] | 2 | transfer scout §6 | `src/ffs/transfer_nk.py`, `reports/figures/fig_nk.svg`, 1-page `report/nk.qmd` | 447 ± 10% reproduced; H5 test result recorded |
| 2.7 Mid-project checkpoint: decide S1/S1b/S1c outcome, cut list, D7–D10 | J | 1 | all | `DECISIONS.md` update | written |

### Phase 3 — Week 3 (Oct 28–Nov 3): figures, dashboard, brief draft. J ≈ 14 h.
| Task | Owner | h | Inputs | Outputs | Done when |
|---|---|---|---|---|---|
| 3.1 `make figures`: 8 figures (§6.3), SVG + 300-dpi PNG, data CSV per figure, consistent sector colours, hatching for "unobserved" | C [J 2] | 2 | out/ | `reports/figures/fig01..08.*` + `data/` | every figure has title-as-finding, N, source line, date pulled |
| 3.2 `export.py`: `coverage_sectormonth.json` (<1 MB), `fronts_weekly.topojson` (<2 MB via mapshaper, weekly only, 7-day lag), `panel_sectorweek.csv`, `tables.json` | C [J 0.5] | 0.5 | 2.x | `site/data/` | total < 3 MB |
| 3.3 Dashboard `site/index.html`: MapLibre GL JS (OpenFreeMap or Protomaps basemap, no OSM tile server), month slider over the coverage hexes, weekly front line, three Plot charts (seasonality front vs rear, lead-lag with bootstrap bands, forecast skill), footer attribution block, "data through 2025-12-31" stamp | C [J 2] | 2 | 3.2 | live Pages URL | loads on phone < 3 s; no point-level layer; Jackson has clicked every control |
| 3.4 Brief `report/brief.qmd` draft (§6.1 structure), render HTML + Typst PDF; upgrade Quarto to 1.9 if `pdf-standard` wanted | C drafts, **J rewrites voice** | 4 | tables, figures, corpus_frames | `site/brief.html`, `site/brief.pdf` | 2,500–3,500 words; Limits ≥ as long as Results; every number traceable to a CSV |
| 3.5 README (30-second interview), `FAQ.md` (12 interviewer attacks with answers), landing page `site/index.html` buttons | C [J 1.5] | 1.5 | brief | files | Jackson can answer each FAQ aloud |
| 3.6 Send draft to two reviewers (methods: econ-stats instructor; SME: Solstad or Van Den Hoek if they replied; otherwise Black Bird Group via X DM) with 3 named questions | J | 1 | brief draft | emails logged | sent by Nov 3 |
| 3.7 S2 global blind-season map **if** 2.2 done by Day 17 | C [J 0.5] | 0.5 | all-country zips 2019–21 (~1.1 GB, DuckDB aggregate to 0.5° monthly, never load raw into pandas) | `fig09_global_blind.svg` | one figure |

### Phase 4 — Week 4 (Nov 4–10): review, harden, ship, outreach. J ≈ 13 h.
| Task | Owner | h | Inputs | Outputs | Done when |
|---|---|---|---|---|---|
| 4.1 Incorporate reviewer comments; log in `CHANGELOG.md` (no names without permission) | C [J 2] | 2 | replies | updated brief | changes listed |
| 4.2 Freeze: `v1.0.0` tag, GitHub Release with processed Parquet, Zenodo DOI via integration, DOI into brief + README + `CITATION.cff` | C [J 0.5] | 0.5 | repo | DOI | DOI resolves |
| 4.3 S4 air-defense note (if time): `report/intercept-note.qmd`, 1 figure (destroyed vs destroyed+EW-lost by quarter), framed as a reporting-regime break; 2-page memo PDF for CSIS Futures Lab | C [J 1.5] | 1.5 | `airdefense/out/` | `site/intercept-note.html/.pdf` | Numbers reproduce `airdefense/VERDICT.md` table |
| 4.4 S3 living layer (if ahead): `refresh.yml` daily 04:17 UTC, MAP_KEY secret, last-30-days NRT layer + current front, badge; analysis **frozen** | C [J 1] | 1 | 0.1 | cron commits | two consecutive daily runs green |
| 4.5 S8 R `fixest` cross-check script | C [J 0.5] | 0.5 | panel | `R/primary_spec.R` | coefficient matches Python to 1e-3 |
| 4.6 Publish day (Tue 10 Nov): LinkedIn post (honest-null hook), X/Bluesky thread (3 figures, tag only Solstad/Black Bird/Africk), r/CredibleDefense per sidebar rules, Show HN; Bellingcat pitch email (no attachments); CSIS memo email; AFK abstract (deadline 11 Nov) | J | 3 | everything | posts, emails logged in Rolodex | all sent same day; no reply-debates rule in effect |
| 4.7 Resume bullet + pitch (§13) into `Work_History_and_Resume`; `Personal_Projects` entry | J | 1 | §13 | files | done |
| 4.8 Retrospective: what to do in v1.1 (Sudan, ERA5, VNF) in `ROADMAP.md` | J | 0.5 | — | file | written |

Jackson total ≈ 57 h. Claude compute/wall time: ~4 overnight pulls (API, backfill, zips), otherwise interactive.

---

## 4. Data plan

### 4.1 Sources (MVP in bold; sizes verified by scouts' HEAD requests on 2026-10-13 unless noted)

| Source | How obtained | Size | Licence / attribution | Role |
|---|---|---|---|---|
| **FIRMS VIIRS S-NPP yearly Ukraine CSVs 2019, 2020, 2021, 2023, 2024, 2025** `https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/<year>/viirs-snpp_<year>_Ukraine.csv` | `make data` (pooch, no key) | 2019 7.8 MB, 2021 3.7 MB, 2023 3.4 MB, 2024 ~8 MB, 2025 ~7 MB | NASA open; acknowledgment text in §4.4; SP science quality | baseline + exploratory panel |
| **FIRMS API `VIIRS_NOAA20_SP`, `VIIRS_NOAA21_NRT`, `VIIRS_SNPP_SP`**, area endpoint, bbox 22,44,41,53, DAY_RANGE 5 | scripted loop, MAP_KEY, 1 req/s | ~30 MB/yr all sensors | same; NRT rows flagged in manifest | 3× overpasses; opportunity index |
| **DeepState daily polygons 2024-07-08→2025-12-31 (cyterat mirror)** `https://github.com/cyterat/deepstate-map-data` | `make data` fetch at pinned commit; **never vendored** | 41 MB (536 files) | DeepState licence (derived aggregates only, attribution + link); mirror GPL-3.0 scripts | outcome, exploratory window |
| DeepState history API 2022-04-03→2024-07-07 `https://deepstatemap.live/api/history/public` → `/api/history/<id>/geojson` (S1) | overnight pull, 1 req / 2–3 s, UA with contact, cached once | 0.5–1 GB raw (gitignored) | same; permission email sent Day 0 | confirmatory outcome (preferred) |
| ISW/CTP `UkrainianCoTTimelapse_FEB_2022_to_DEC_2024_view/FeatureServer/0` on `services5.arcgis.com/SaBe5HMtmnbqSWlu` (S1b) | REST `f=geojson`, `resultOffset` pages of 2000 | ~200 MB GeoJSON | copyright ISW/AEI CTP, **no licence text (unverified)**; derived-only; email ISW | confirmatory outcome (fallback); latency cross-check |
| **Economist war-fire repo** `https://github.com/TheEconomist/the-economist-war-fire-model` → `output-data/cloud_cover_in_ukraine_by_day.csv` (85 KB), optionally `ukraine_war_fires.csv` (71 MB) | `git clone --depth 1` or raw URLs | 85 KB used in MVP | MIT code / **CC BY 4.0** data; cite Solstad 2023 | cloud covariate; S6 alternative treatment |
| **Natural Earth 1:50m admin-0** | already on disk; pooch | 3.1 MB | public domain (Crimea caveat in README) | border/coast cut |
| **FIRMS Azerbaijan + Armenia 2012–2020** (same URL pattern) | pooch | < 5 MB total | NASA | NK transfer |
| GeoNames `AZ.txt` + Wikipedia "Timeline of the 2020 Nagorno-Karabakh war" | download / hand table (~40 rows) | 1 MB / tiny | CC BY 4.0 / CC BY-SA | NK capture dates (announcement dates, ±2 d) |
| UCDP GED 26.1 `https://ucdp.uu.se/downloads/` `ged261-csv.zip` | pooch | 39 MB | CC BY 4.0; cite Davies/Pettersson/Öberg 2026 + Sundberg & Melander 2013 | NK events; Sudan (stretch) |
| FIRMS all-country zips 2019–21 `.../data/country/zips/viirs-snpp_<year>_all_countries.zip` (S2) | pooch, DuckDB read-zip | ~372 MB/yr | NASA | global blind-season map |
| Ivaniuk missile dataset mirror (S4) | already in `airdefense/data` | small | Kaggle terms; aggregate only | side note |
| **Not used:** ACLED, VNF, ERA5, GEE, WorldCover, Sentinel, liveuamap, Maxar | — | — | see §2 Out | — |

### 4.2 Storage layout
```
data/
  manifest.yaml            # url, sha256, bytes, retrieved_at, licence, product (SP/NRT), notes
  raw/                     # gitignored; fetched by `make data`
    firms_country/  firms_api/  deepstate_mirror/  deepstate_api/  isw/  economist/  naturalearth/  nk/  ucdp/
  interim/                 # gitignored; DuckDB file ffs.duckdb, H3 cell tables
  processed/               # committed if < 10 MB each
    panel_sectorweek.parquet  baseline_cellweek.parquet  opportunity_sectorweek.parquet
    fronts_weekly.parquet (derived line-of-contact geometry only)  nk_eventstudy.parquet
  sample/                  # committed: 2 weeks FIRMS + 3 DeepState days + 1 NK week → CI
out/tables/                # every coefficient table as CSV with git hash column
reports/figures/           # fig01..09 .svg/.png + data/fig01.csv ...
site/                      # index.html, data/*.json|topojson|csv, brief.html, brief.pdf
```
CRS discipline: analysis in EPSG:3035 (Ukraine) / UTM 38N (NK); web in EPSG:3857. Weeks = ISO Mon–Sun; snapshot = last map in week.

### 4.3 Licensing matrix for what the repo ships
| Component | Ship raw? | Ship derived? | Licence |
|---|---|---|---|
| Code | — | — | MIT |
| Panel, coverage grid, weekly line-of-contact geometry (Jackson's construction) | yes | yes | CC BY 4.0 |
| FIRMS points | **no** (fetch script; OPSEC + size) | aggregates yes | NASA ack |
| DeepState / ISW polygons | **never** | aggregates yes | attribution + link; no identical objects |
| Economist cloud series | link, not vendor | yes | CC BY 4.0 |
| UCDP rows for NK window | yes (CC BY) | yes | two citations |

### 4.4 Attribution block (README, brief, dashboard footer)
> Data: NASA FIRMS (VIIRS S-NPP/NOAA-20/NOAA-21 active fire, LANCE/ESDIS; SP and NRT products as flagged). "We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Earth Science Data and Information System (ESDIS)." · Territorial control: DeepStateMap.live (DEEPSTATEUATECH LLC), derived sector-week aggregates only [and/or ISW & AEI's Critical Threats Project] · Cloud cover: The Economist war-fire model (Solstad 2023, CC BY 4.0) · UCDP GED 26.1 (CC BY 4.0) · Natural Earth (public domain) · Basemap © OpenFreeMap / © OpenStreetMap contributors (ODbL). NRT FIRMS data are not science quality; see LIMITS.md.

Flag: the live FIRMS LANCE disclaimer URL returned 404 to the risks scout; find the current link on https://www.earthdata.nasa.gov/data/tools/firms before publishing.

---

## 5. Analysis plan

### 5.1 Primary (confirmatory) specification
```
net4_{i,t+1..t+4} = β·log(1 + front_{i,t}) + Σ_{k=0..3} ρ_k·net_{i,t−k} + θ·opportunity_{i,t} + α_i + γ_t + ε_{i,t}
```
- Units: 22 sectors from 50 km segments of the 2024-12-30 line (perpendicular corridors), ±15 km front band of *that week's* line; outcome = Russian net km² gained, 4-week sum (DeepState batches edits; 1-week lead is below the outcome's resolution).
- Fires: S-NPP + NOAA-20 + NOAA-21 pooled, type 0, confidence n/h.
- Inference: CRV1 by sector (pyfixest, plus wild cluster bootstrap Webb 9,999 draws as a check) **and** Driscoll–Kraay lag 4 via `linearmodels.PanelOLS(cov_type="kernel", bandwidth=4)`; R `fixest` `vcov = DK(4) ~ week` cross-check (S8). Significant only if both p < 0.05.
- Nickell bias ≈ 1/T ≈ 1.3%: stated, ignored.
- Effect-size floor: doubling fires ⇒ ≥ 2 km² extra 4-week gain; forecast floor ≥ 5% MAE skill. Equivalence statement from the 90% CI.

### 5.2 Robustness (fixed list, five items; the methods scout's seven trimmed for time)
1. Treatment = excess over 2019–21 baseline (and night-only detections).
2. Outcome = P(gain > 1 km² in next 4 weeks) LPM with FE; IHS(net).
3. Geometry 2×2: sector 25/100 km × band 10/25 km, one table.
4. Sims leads-and-lags t−4..t+4 with joint test leads = 0; reverse direction (net → fires).
5. Drop-one-sector jackknife plot (22 estimates) + drop Donetsk entirely.
Dropped from MVP: H3 res-7 Poisson raster twin, PELT change-points (exploratory only if time).

### 5.3 Blind-spot / detection-opportunity product (the anchor deliverable)
`opportunity_{i,w}` = Σ over days in week of [overpass count (empirical: distinct satellite×acq_time with ≥1 detection in a 200 km box around the sector) × (1 − cloud_east_day from Economist series) × fuel-season weight (sector's 2019–21 baseline count for that calendar week, scaled 0–1)]. Published as sector × month: P(≥1 detection in a fighting week), decomposed into "not observed" (cloud/overpass) vs "observed, no fire" (fuel/snow). Validation: `log(front) ~ opportunity | sector + week-of-year FE` must be strongly positive. Headline statistic: share of km² gained in bottom-quartile opportunity sector-weeks (H4). Stretch upgrades (v1.1): ERA5 `tcc` at overpass hour, MOD09GA state bits in GEE, ERA5-Land snow.

### 5.4 Transfer test (NK 2020, MVP) and generalisation argument
- NK: per §1.2 H5; also replicate the CEOBS anomaly (447 vs 203 in 2012–19) as a calibration of the baseline method on a second country.
- Generalisation is argued on three legs in the brief: (1) blind-spot physics is theatre-independent (fuel, cloud, overpass); (2) within-war phase contrast if S1/S1b lands (H6); (3) NK maneuver-war check. Named non-travelling confounders (FPV-set field fires, DeepState editorial cadence) and travelling ones (agricultural season, cloud climatology).
- Sudan explicitly deferred to v1.1 with the design already written (transfer scout §6).

### 5.5 Descriptive products in the brief
Distance-decay histogram (signed distance to line, monthly), front/rear monthly table (already have), lead-lag correlogram with sector-block bootstrap bands, map-latency note (qualitative in MVP; measured if S7).

---

## 6. Deliverables and exact formats

| # | Deliverable | Format | Location | Acceptance |
|---|---|---|---|---|
| 1 | Repository | GitHub public; `pyproject.toml` + `uv.lock`; Makefile targets `data panel baseline coverage models figures export site brief test all`; CI `ci.yml` (ruff, pytest, `make all` on `data/sample/` < 5 min); `site.yml` deploy | `github.com/<user>/frontline-from-space` | CI badge green; fresh clone → `make all` works on sample |
| 2 | `PREREG.md` | Markdown, tagged `prereg-v1` | repo root | tag timestamp precedes confirmatory data commits |
| 3 | `LIMITS.md`, `PUBLICATION_RULES.md`, `FAQ.md`, `DEVIATIONS.md`, `CHANGELOG.md`, `LICENSES.md` | Markdown | repo root / docs | present, linked from README |
| 4 | Processed data | Parquet (zstd) < 10 MB each; CSV tables | `data/processed/`, `out/tables/` | manifest hashes |
| 5 | Dashboard | single `index.html` + `site/data/` (<3 MB), MapLibre GL JS 4.x pinned from cdnjs, Observable Plot pinned; 7-day lag; sector-month coverage hexes; weekly front; 3 charts; footer attribution | GitHub Pages | works on phone; no point layer |
| 6 | Brief | Quarto `.qmd` → self-contained HTML + Typst PDF, 5–8 pp, 2,500–3,500 words, 8 figures (SVG/PNG + data CSVs), two-axis confidence stamps inline (`mechanical / documentary / elicited`) | `site/brief.html`, `site/brief.pdf` | renders both; Limits ≥ Results length |
| 7 | Figures | fig01 front vs rear density by month (blind season shaded); fig02 sector map with corridors; fig03 sector×month coverage heatmap; fig04 share of gains in blind weeks; fig05 lead-lag correlogram with bands; fig06 primary + robustness coefficient plot incl. jackknife; fig07 forecast-skill bars; fig08 NK event study; (fig09 global blind-season map, stretch) | `reports/figures/` | each with title-as-finding, N, source, date |
| 8 | Landing page | Section at top of `index.html`: headline figure, 3 sentences, buttons Dashboard / Brief HTML / Brief PDF / Repo / DOI | Pages | one URL on resume |
| 9 | Zenodo DOI | v1.0.0 release | zenodo.org | DOI resolves |
| 10 | Outreach set | LinkedIn post (`~/Jackson Mackney/LinkedIn/posts/`), X/Bluesky thread text, Bellingcat pitch (300–500 words, no attachments), CSIS 2-page memo (if S4), AFK abstract | files in `outreach/` | sent 10–11 Nov |
| 11 | Side note (S4) | `intercept-note.qmd` → HTML + PDF, 2–3 pp, 1 figure | `site/` | numbers reproduce airdefense table |

---

## 7. Tooling and stack decisions (with alternatives rejected)

| Layer | Decision | Rejected and why |
|---|---|---|
| Env | **uv** (installed) + Python 3.12, `uv.lock` | pixi (1 h adoption, no GDAL CLI need); conda (slow, not needed since wheels bundle GDAL/PROJ) |
| Geo | **geopandas 1.1 / shapely 2.1 / pyproj** (already used in `first_pass.py`) | PostGIS (server), GEE (2-evening learning curve, non-commercial registration lag) |
| Tabular | **DuckDB** with `spatial` + `h3` community extensions for H3 binning and the all-country zips | pandas-only (memory on 372 MB zips); polars (fine, but DuckDB gives the SQL keyword for CSIS/Govini/Anduril postings) |
| Econometrics | **pyfixest** (CRV1, wild bootstrap) + **linearmodels PanelOLS kernel** for DK; **statsmodels** for LPM | pyfixest for DK (not documented, verified today); Arellano–Bond (Nickell bias 1.3%, overkill); R-only (keep one R script as cross-check, S8) |
| ML | **LightGBM + sklearn TimeSeriesSplit(gap=4)**, Ridge counterpart | random k-fold (leakage); deep models (no) |
| Change-points / point patterns | dropped from MVP (`ruptures`, `pointpats` optional) | — |
| Orbits/sun | **empirical overpass count** from detection timestamps | skyfield + TLEs (correct but 2–3 h for marginal gain in MVP) |
| Cloud covariate | **Economist daily series** (CC BY 4.0) | ERA5 via CDS (queue outages reported 2026; 1.5 GB); MOD09GA in GEE (learning curve); VNP14IMG swaths (tens of MB per granule) |
| Data versioning | **manifest.yaml + pooch** | DVC (second CLI, remote); Git LFS (1 GB quota exhausted by cloners) |
| Orchestration | **Makefile** | snakemake/doit (unneeded) |
| Tests/CI | **pytest + ruff + GitHub Actions** (free on public repos) | — |
| Reports | **Quarto → HTML + Typst PDF** (Typst bundled; local Quarto 1.8.26, upgrade to 1.9 optional) | LaTeX (install), Word (not reproducible), Quarto manuscript (heavier) |
| Dashboard | **Hand-rolled single HTML: MapLibre GL JS + Observable Plot**, pre-aggregated JSON/TopoJSON, GitHub Pages | Observable Framework (node build; Observable Cloud hosting deprecated 2025-04-15; repo activity slowed 2026 — acceptable but adds a build step for little gain at 3 MB of data); Streamlit Community Cloud (sleeps after 12 h, recruiter hits cold start); kepler.gl (reads as "uploaded a CSV"; use only for a GIF); Felt (no embed on free tier); PMTiles/tippecanoe (not installed; only needed for raw points, which OPSEC rules exclude) |
| Hosting | **GitHub Pages** (1 GB site, 100 GB/mo soft) + GitHub Release assets + **Zenodo** DOI | Cloudflare Pages/R2 (card-on-file unverified; no need at 3 MB), Hugging Face (v1.1 maybe) |
| Living updates | **Stretch S3**: GitHub Actions cron (5-min min interval; disabled after 60 days inactivity — bot commits prevent) | Cloudflare Workers cron (10 ms CPU, cannot run shapely); launchd (laptop sleeps) |
| Pre-registration | **git tag** (`prereg-v1`) as the mandatory timestamp; **OSF** registration optional (D5) using the standard OSF Prereg form with "existing data: some analysis has occurred" answered honestly; the secondary-data template's live status in OSF Registries is unverified | — |
| Notebooks | exploration only, `nbstripout`; nothing load-bearing | — |

Install list for Jackson (10 min): `brew install duckdb mapshaper` (or `npx mapshaper`), `brew upgrade quarto` (optional).

---

## 8. Contingencies

Hard rules first (from risks scout, adopted verbatim in `PUBLICATION_RULES.md`): publish at sector-week or coarser; dashboard lags ≥ 7 days and shows complete weeks only; no point-level front-band detections, FRP or acquisition-time tables, or event annotation; blind-spot product at sector-month; neutral wording for control sources; Ukrainian transliterations; no travel to RU/BY/occupied territory while public; one promotion post, no reply-debates; log foreign professional contacts.

| Risk | Trigger | Fallback | Cost |
|---|---|---|---|
| **Data unavailable — FIRMS API** (504s, key issues) | Pull < 80% complete after two overnight attempts by Day 5 | Use FIRMS Archive Download tool (Earthdata login, email delivery, NOAA-20 from 2018-04-01, NOAA-21 from 2024-01-17); if that also fails by Day 9, ship S-NPP-only and state it in LIMITS; H4 opportunity uses S-NPP overpasses only | 1 h / 0 h |
| **Data unavailable — DeepState backfill** (S1) | Not clean by end of Day 10, or DeepState says no | S1b ISW layer; if ISW terms forbid, S1c: confirmatory = NOAA-20/21-augmented 2024–25 panel, labelled "partially confirmatory"; H6 dropped, explicitly | 4 h / 0 h |
| **Data unavailable — Economist cloud series** removed or broken | 404 or NA column | ERA5 monthly `tcc` from CDS for the east bbox (small, monthly, minutes) or the Dingemanse published monthly cloud figures as a crude calendar; opportunity index then = overpasses × fuel season | 2 h |
| **Null everywhere** (H1 ratio weak too, opportunity validation fails) | H1 fails or validation regression ≤ 0 | H1 failing would contradict the feasibility pass; first suspect geometry regression (run byte-for-byte test). If genuine, the brief becomes "what a free thermal feed cannot tell you," still shippable: coverage product + NK + LIMITS. The honest-null framing is already the headline, so H2/H3 nulls are the expected outcome and not a contingency | 0 h |
| **Positive but fragile β** (p < 0.05 both SEs but jackknife flips) | Jackknife shows ≥ 3 sectors flipping sign | Report as pre-registered: "significant, not robust"; equivalence CI; do not headline it | 0 h |
| **Transfer case fails** (NK: 447 not reproduced, or capture geocoding too noisy) | Reproduction off by > 25% or < 20 geocoded settlements | Check CEOBS window and type filter; fall back to a single descriptive figure (daily war-fires vs cumulative captures) without the sign test; in the worst case, replace with S2 global blind-season map as the generalisation leg | 2 h |
| **Time runs short** | Any Phase milestone slips > 3 days | Apply cut order §0; brief shrinks to 5 pages; dashboard to coverage map + one chart; ship on 10 Nov regardless with `ROADMAP.md` | — |
| **Licensing problem — DeepState refuses research use** | Email reply "no" | Switch outcome source to ISW for all windows (if ISW terms allow derived use); keep DeepState only as a cited comparison figure (screenshots are explicitly licensed); `DEVIATIONS.md` | 4 h |
| **Licensing problem — ISW also forbids** | Both refuse | Pause only the backfill; the 2024–25 cyterat-derived aggregates remain (derived weekly scalars, attribution) — risks scout rates this low-risk; note in LIMITS | 0 h |
| **OPSEC concern raised** (reviewer, commenter, or Jackson's own doubt) | Any request for point-level or sub-weekly data; any reading of the dashboard as a targeting aid | Rules already exclude it; answer with the one-paragraph "marginal contribution of publication is zero" argument (FIRMS itself is 3-hour point-level; Economist is daily point-level); if still uncomfortable, coarsen dashboard to sector-month and lag 14 days | 1 h |
| **Reviewer finds a real error after publication** | Any confirmed error | Correction policy in README: versioned fix, CHANGELOG, new release; respond once factually | 2 h |
| **Pile-on** | Hostile thread | Mute, no replies, pin LIMITS; one neutral post only | 0 h |

---

## 9. Decision points for Jackson

| # | Decision | Options | Recommendation | By |
|---|---|---|---|---|
| D1 | Control source for 2022–24 backfill | (a) DeepState API (b) ISW layer (c) skip backfill | **(a) with 8-h cap, (b) fallback, (c) if both fail**; send both permission emails Day 0 | Day 0 |
| D2 | Dashboard build | (a) hand-rolled HTML (b) Observable Framework (c) Streamlit | **(a)**: no build step, no sleeping, interviewer reads the source | Day 0 |
| D3 | Transfer leg in MVP | (a) NK 2020 (b) Sudan (c) global blind-season map only | **(a)**, with (c) as first stretch; Sudan to v1.1 | Day 0 |
| D4 | Pre-registration venue | (a) git tag only (b) git tag + OSF | **(b)** if OSF form takes < 1 h; external timestamp is what reviewers trust | Day 6 |
| D5 | Repo/brief title | e.g. "Front line from space: what a free thermal satellite feed can and cannot tell an analyst about a war" vs Ukraine-first title | **Sensor-first title**, Ukraine as the test case (addresses the "too Ukraine-specific" worry in the title itself) | Day 6 |
| D6 | CNAS Pathfinder essay (8 Nov, 800–1,000 words, exclusive, no gen-AI text, Jackson-written) | enter / skip | **Skip unless Jackson wants to write it himself in week 3**; it competes with brief rewriting and must not reuse brief text | Day 17 |
| D7 | Living layer (S3) | build / freeze with date stamp | Build only if brief draft is done by Day 24; otherwise a dated freeze is honest and fine | Day 24 |
| D8 | Air-defense side note (S4) | include as separate note / drop | **Include if ≤ 5 h remain in week 4**: numbers are done, it broadens the portfolio to "measurement forensics," and it is the CSIS Futures Lab door-opener | Day 24 |
| D9 | DuckDB + one R script for keyword coverage | yes / no | **Yes** (DuckDB is in the pipeline anyway; R script 2 h) | Day 14 |
| D10 | Outreach breadth | GitHub+LinkedIn only / + X/Bluesky/HN/Reddit / + Bellingcat & CSIS pitches | **All three tiers on 10–11 Nov**, one post per channel, no debates | Day 28 |
| D11 | Use NRT NOAA-21 rows in the confirmatory spec | include flagged / S-NPP+NOAA-20 SP only | **Include flagged**; robustness run without NRT rows | Day 6 |

---

## 10. Publishing and outreach plan

**Order (audience scout B.1–B.5, dated):**
1. **10 Nov:** repo public with v1.0.0 + Zenodo DOI; Pages live; LinkedIn post (hook: "I pre-registered a hypothesis about satellite fire data and the Ukraine front, and it failed. Here is the map of when the satellite is blind."); X/Bluesky thread with fig01, fig03, fig05, tagging only @Sondreus, @Black_BirdGroup, @bradyafr; Show HN; r/CredibleDefense (read sidebar first).
2. **10–11 Nov:** Bellingcat pitch to submissions@bellingcat.com (300–500 words, working headline, one-sentence topline, link not attachment; frame as a *Resources* follow-up to their 2022 FIRMS primer with an open coverage tool). CSIS Futures Lab memo (Atalan/Jensen via LinkedIn/staff page) if S4 ships: "extending your salvo model past Oct 2024 with a denominator fix." AFK early-career conference abstract to jungeafk@gmail.com by **11 Nov**.
3. **Fallbacks:** Modern War Institute (600–2,500 words, MWIsubmissions@westpoint.edu) as the "sensor literacy for staff officers" piece; Wavell Room; Small Wars Journal. **Not** War on the Rocks (students rejected without non-academic experience), not Lawfare.
4. **Jan 2027:** USGIF GEOINT 2027 Student Poster (apply 20 Jan–3 Mar; the room is GEOINT recruiters). Bellingcat Tech Fellowship call (~Jan) with the coverage tool as the pitch. Palantir Deployment Strategist / FDSE new-grad and Shield AI 2027 intern applications carry the one URL.
5. **Critique loop (before publishing):** pre-registration email Day 7 to Solstad (sondresolstad@economist.com), Van Den Hoek (vandenhj@oregonstate.edu), Zhukov (ymz2@georgetown.edu); draft to two reviewers Day 21. Log every contact in Rolodex and `CHANGELOG.md`.
6. **Resume integration:** `Work_History_and_Resume/WORK_HISTORY.md` + `Personal_Projects/` entry on 10 Nov; one URL on the resume.

---

## 11. How the Future_of_War corpus is used

The corpus has zero FIRMS/VIIRS content (corpus scout grep), so it is a **frame supplier, not a data source**. Used, with the D022 two-axis stamp carried inside each sentence:
- **D015 detect→identify→custody→effect chain** (`D015:81`) structures the brief's results: detect = 5–17× front/rear (mechanical); identify = type/night/baseline filters; custody = overpass and cloud gaps (the opportunity index); effect = the H2/H3 null. "We found almost nothing" becomes "we located where the chain breaks."
- **D008 force-to-space regimes** (`D008:79–90`, High · documentary): Ukraine 2024–25 coded `saturated-linear` ⇒ momentum-dominated small change is the regime behaving as predicted; the method was tested where a lead was least likely. Drives the phase table and H6.
- **D011 symmetry** (`D011:58`, Med · elicited): cited only as the hypothesis behind H6, never as confirmed mechanism; D019 scope riders respected.
- **D010 mode 9** (`D010:309–316`): frame for the air-defense side note.
- **D022 stamp** (`D022:325–336`): adopted in brief, README, and every table (`basis` column).
- **Historical comparison set** (one paragraph): WWI East vs West (`ww1_1914.md:78`), Iran–Iraq ~1,100 km line (`iran_iraq_1980.md:33`), Korea's transition (`korean_war_1950.md:69`) — Med · documentary, each S-TMP resolved against `01_source_log.md` before quoting a figure.
- **Transfer roadmap**: `04_rest_of_world.md:152` is the one-sentence justification for node-based geometry in Sudan (v1.1).
- **Never used:** census counts, cross-tabs, High stamps, "triangulated," any D011 theatre application from the landscapes.
- Files produced: `planning/corpus_frames.md` (verbatim quotes with file:line), `planning/ukraine_phase_table.md` (project-built; the corpus has no Ukraine deep-dive). The brief can note that the sector-week panel operationalises watchboard indicators TRNS-2 and MANV-3 that the parent project specified but never ran.

---

## 12. Air-defense side piece

**Slotted as stretch S4, week 4, 5-hour cap, decision D8 (recommend include).** Content: the Shahed intercept rate widely cited (incl. CSIS's 0.64 for 2025) is a reporting artifact: the "EW-lost/locationally lost" category enters 2024 Q3 (share 0.09→0.40 in Q4), coincides with the destroyed-only rate falling to 0.48–0.58, and exits 2025 Q4 when the rate jumps to 0.81–0.91; destroyed + EW-lost is flat (0.93 / 0.86 / 0.89 for 2024/25/26). Pre-register the break dates, cross-check against Mirror B and KAS monthly figures, one figure, 2–3 pages, same Quarto template, same site, framed as D010 mode 9 ("filmable-weapon kill-claim inflation") and as measurement forensics that transfers to any theatre's denominator problem. Not the Patriot-shortage natural experiment (clustered on a handful of nights; drop). If week 4 is tight, it is cut before the brief and after the living layer.

---

## 13. What the plan is designed to produce

**Resume bullet (one line; adjust numbers to the final run):**
> *Front line from space* — built an open, reproducible pipeline (Python, GeoPandas, DuckDB, GitHub Actions) fusing ~250k NASA FIRMS thermal detections from three satellites with daily territorial-control maps into a 22-sector × 77-week panel; pre-registered and falsified a lead-lag hypothesis with fixed-effects, clustered and Driscoll–Kraay inference, placebo and leave-one-out checks; shipped a sector-month sensor blind-spot map, a maneuver-war transfer test, a public dashboard and a 7-page brief (DOI).

**60-second interview pitch:**
> "I wanted to know what a free satellite thermal feed can actually tell an analyst about a war, so I tested it on Ukraine. I pulled NASA FIRMS detections from three VIIRS satellites and the daily DeepState control maps, recomputed the line of contact every week, cut it into 22 sectors, and built a sector-week panel. Three things came out. First, the sensor locates fighting well: fire density within 15 km of the line is five to seventeen times the density fifty kilometres behind it, every month. Second, it does not forecast anything: I pre-registered a fixed-effects test with momentum control before pulling the confirmatory data, and fires added about half a percent of explained variance over last week's advance, with a flat lead-lag curve. I report that as a null with equivalence bounds rather than hunting for a specification that works. Third — and this is the product — the sensor is blind about four months a year from fuel, snow and cloud, and I built a sector-by-month coverage map that shows when the feed is worth looking at and when 'no detection' means 'not observed.' I checked the maneuver-war case on Nagorno-Karabakh 2020, where fires trailed the advance. Everything is open: a repo with a hashed data manifest and CI, a dashboard aggregated to sector-week with a seven-day lag for OPSEC, and a brief with a limits section as long as the results. The thing I'd do next is run the same coverage code on an arid theatre like Sudan, where the outcome has to be event clusters because there is no front line."

---

## 14. Flags: what this plan relies on that is not verified
- `VIIRS_NOAA21_SP` does not exist on the API page (verified today); NOAA-21 rows will be NRT and flagged (D11).
- pyfixest Driscoll–Kraay: not documented; plan uses `linearmodels` (verified cov_type name) + R `fixest` cross-check.
- ISW ArcGIS reuse terms: copyright notice only; terms page Cloudflare-blocked. Email before any derived publication from ISW layers.
- DeepState stance on student research use: licence silent; email sent Day 0; derived-only regardless.
- OSF secondary-data template live status: unverified; the standard OSF Prereg form with the "existing data" question is the fallback.
- FIRMS LANCE disclaimer live URL: 404 for the scout; find before publishing.
- Economist `cloud_cover_in_ukraine_by_day.csv` provenance (how computed) is undocumented in the repo; cite as theirs and describe as "a published daily national/eastern cloud fraction."
- NK capture dates are announcement dates (±2 days); CEOBS 447 figure's exact filters not retrieved.
- The Scientific Reports 2026 Nightfire paper body was read by the prior-art scout via PDF; the Nature page itself paywalled. Cite from the PDF/thesis.
- Hour estimates assume Claude writes first drafts of all code and prose; Jackson's hours are review, decision, accounts, emails, voice.
