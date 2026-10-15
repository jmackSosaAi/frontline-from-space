# Scout: infrastructure and deliverables for "Front line from space"

Written 2026-10-13. Scope: how to ship the project (dashboard, repo, living updates, brief, portfolio packaging), not what to analyse. Ground truth for the data is `/Users/jacksonmackney/D3/Conflict_Data_Feasibility/frontline/{VERDICT,FIRST_PASS,SOURCES}.md`. Every cost, limit and URL below was checked on 2026-10-13 unless marked **[unverified]**.

Short version: **host everything static on GitHub (repo + Pages), render the brief with Quarto → HTML + Typst PDF, serve the map from pre-aggregated files (not raw points), and refresh data with a GitHub Actions cron. Total cash cost: $0. Infra time budget: about 5 working days out of the 4–6 weeks.** Details and the stretch stack follow.

---

## 0. What has to be served (sizes that drive every decision)

| Asset | Raw size on disk now | What the dashboard needs | Served size (est.) |
|---|---|---|---|
| FIRMS VIIRS S-NPP Ukraine, 2024+2025, 153,017 rows (type 0: ~139k) | 12.0 MB CSV (`data/raw/firms/`) | lat, lon, acq_date, frp, daynight, satellite | ~2.5 MB Parquet (zstd) or ~3 MB gzipped CSV **[estimate]** |
| + 2022, 2023, 2019–21 baseline, NOAA-20/21 (stretch) | 2019: 7.8 MB, 2021: 3.7 MB, 2023: 3.4 MB (HEAD-checked). NOAA-20/21 only via API or Archive tool, see §3 | same | ~8–12 MB Parquet for ~600k points **[estimate]** |
| DeepState daily occupied-area polygons, 536 files | 41 MB GeoJSON (~75 KB each, ~2,900 vertices) | one polygon per **week** (78), or the weekly *change* polygons (diff), plus the line of contact | 78 × 75 KB ≈ 6 MB raw; ~1.5 MB as TopoJSON/gzip **[estimate]** |
| Sector × week panel | 179 KB CSV (`out/sector_week_panel.csv`) | as-is | 180 KB |
| Coverage / blind-spot product (new) | n/a | monthly or weekly grid of detection density and "zero-detection" flags, 0.1° or H3 r6 cells | 0.5–2 MB JSON **[estimate]** |

Takeaway: nothing here needs a tile server, a database, or a paid tier. Even the raw point set fits GitHub Pages' 1 GB site cap and Cloudflare's 25 MiB per-file cap many times over. The only real question is browser performance for 200k–600k points, which is solved by **aggregation first, tiles second, raw points last**.

---

## 1. Interactive map / dashboard

### 1.1 Options compared

| Option | What it is | Fit for this project | Effort | Cost | Verdict |
|---|---|---|---|---|---|
| **Static D3 + MapLibre GL JS (hand-rolled HTML)** | One `index.html` with MapLibre for the map, D3/Plot for the charts, data as Parquet/JSON files next to it | Full control; smallest dependency surface; works on any static host; interviewer can read the source | 3–5 days for a competent first version | $0 | **Minimum stack.** |
| **Observable Framework** | Open-source static-site generator for data apps (ISC licence; GitHub API shows last push 2026-05-15, not archived, 3.6k stars). Python/R/JS "data loaders" run at build time; output is a static `dist/`; Observable Plot and MapLibre work inside it | Best ergonomics for a "dashboard with narrative": Markdown + reactive JS cells, built-in Parquet/DuckDB loaders, charts and map on one page. Hosting on Observable Cloud was deprecated 2025-04-15; you deploy `dist/` to GitHub Pages or Cloudflare yourself | 2–4 days; node toolchain | $0 | **Recommended if Jackson is comfortable with a node build step. Flag: repo activity slowed in 2026; it still builds fine but do not expect new features.** |
| **MapLibre + PMTiles** | Vector tiles in a single `.pmtiles` file read by HTTP range requests; no tile server | The right way to show *all* raw points with pan/zoom at every scale. Build with tippecanoe (v2.79.0, 2025-07-24) → `-o fires.pmtiles`. Works on GitHub Pages / Cloudflare Pages (range requests are supported by both) | +1 day on top of a MapLibre page | $0 | **Stretch.** Only needed if raw-point browsing is a feature. |
| **deck.gl** (ScatterplotLayer / H3HexagonLayer / standalone or in kepler.gl) | WebGL layers; renders 200k–1M points client-side without tiling | Fast raw-point rendering; H3HexagonLayer is ideal for the coverage product (`{hex, count}` JSON). Heavier JS bundle (~1 MB) | 2–3 days | $0 | Good alternative to PMTiles for the stretch; pairs with Observable Framework or plain HTML. |
| **kepler.gl** (demo app or embed) | Uber's no-code deck.gl explorer (MIT; actively pushed 2026-10-14). Loads CSV/GeoJSON from a URL; time filter/playback built in | Fastest way to get a time-slider over 200k points today (load CSV by URL, add a time filter on `acq_date`). But: it is a generic explorer, hard to brand, bundle is large, and it reads as "I uploaded a CSV" to a technical interviewer | 2 hours for a demo link; 2 days to embed properly | $0 | Use for **exploration and as a screenshot/GIF generator**, not as the shipped dashboard. |
| **Streamlit / Panel on Community Cloud** | Python server app | Needs a running Python process; Community Cloud apps sleep after 12 h without traffic (so a recruiter's first click hits a 30-second cold start); memory 690 MB–2.7 GB; limits "may change without notice" | 1–2 days | $0 | **Avoid for the public deliverable.** Fine for a private exploration tool. |
| **Felt** | Hosted collaborative GIS | Free plan: public sharing yes, **embedding no**, data upload/processing "not included" on Free, 25 viewers, 10k map views/month; Team is $199–249/mo | Beautiful, zero code, but the free tier cannot embed or process uploads | 1 hour | $0 for a share link; $199+/mo to embed | Skip, or use only as a one-off share link for a reviewer. |
| **Datawrapper** | Hosted charts and locator/choropleth maps | Free plan: unlimited charts/maps/tables and embeds; PNG export free, PDF/SVG on Pro (free to students on request). No point-density or time-slider maps. API billing started 2026-09-01 (UI use stays free) | Excellent for the **static figures in the brief** (seasonality bars, front-vs-rear table). Not a dashboard | hours | $0 | Use for 2–3 publication charts if you want hosted interactive versions; otherwise Plot/matplotlib. |

### 1.2 How to serve ~200k points and daily polygons cheaply

Do all three tiers; each is cheap and they compose.

**Tier A, aggregates first (minimum).** Pre-compute in Python and ship small files:
- `coverage_monthly.json`: per 0.1° cell (or H3 r6, ~36 km²) per month: detections, nights-with-detection, FRP sum, and a `blind` flag (0 detections across the whole month in a cell that burned in the pre-war baseline). Roughly 2,000 cells × 24 months × 5 fields ≈ 0.5–1 MB. Render with deck.gl `H3HexagonLayer` or a MapLibre `fill` layer; wire a month slider.
- `front_weekly.topojson`: 78 weekly lines of contact + weekly change polygons. Build with `topojson-server`/`geo2topo` (node) or `mapshaper -simplify 10%` → under 2 MB.
- `sector_week_panel.csv` and `sector_summary.csv` as-is for the charts.
- Result: a dashboard that loads in under 3 MB total, works on a phone, and has no tile pipeline at all.

**Tier B, Parquet for the points (minimum+).** Write the cleaned detections to a single GeoParquet/Parquet file (`pyarrow`, zstd, sorted by date, row group ~50k) and read it in the browser with `hyparquet` (pure JS, small) or DuckDB-WASM (bigger: ~30 MB WASM download, but gives SQL and `ST_X/ST_Y`). Observable Framework has a built-in Parquet loader (Apache Arrow) so this is one line there. 150k rows of 6 columns is ~2.5 MB; deck.gl `ScatterplotLayer` renders it instantly. This gives "show me the raw points for week N" without tiles. **Caveat:** DuckDB-WASM did not support GeoArrow geometry as of Oct 2025 (Development Seed), so store plain `lon`/`lat` float columns, not WKB.

**Tier C, PMTiles for everything-at-every-zoom (stretch).**
```
tippecanoe -o fires.pmtiles -zg --drop-densest-as-needed \
  --cluster-distance=20 --accumulate-attribute=frp:sum \
  -l fires fires_2022_2025.geojson
```
Expect 10–30 MB for ~600k points **[estimate; verify on real data]**. Host next to the HTML on GitHub Pages or Cloudflare Pages (both honour `Range`), or on Cloudflare R2 (10 GB free, no egress fees, 10M Class B ops/month free; CORS must be set with the aws CLI). Protomaps recommends R2 for exactly this reason. MapLibre reads it via the `pmtiles` JS protocol. Extra cost: $0. Extra effort: half a day plus `brew install tippecanoe`. Daily polygons can go into the same tileset with a `date` attribute and a MapLibre filter expression, but at 78 weekly snapshots TopoJSON is simpler.

Tooling status on this Mac (checked): `quarto 1.8.26` is installed; `tippecanoe`, `pmtiles`, `typst`, `duckdb`, GDAL, `geopandas` are **not** installed in the default Python (the feasibility `.venv` has geopandas). `brew install tippecanoe pmtiles duckdb gdal typst` is about 10 minutes.

### 1.3 Hosting

| Host | Free limits (checked) | Notes |
|---|---|---|
| **GitHub Pages** | Site ≤ 1 GB; 100 GB/month bandwidth (soft); 10 builds/hour (soft; does not apply when deploying via Actions) | Simplest: `actions/deploy-pages` from the same repo that holds the code. Custom domain free. Supports range requests, so PMTiles works. **Recommended.** |
| **Cloudflare Pages** | 500 builds/month, 1 concurrent, 20 min build timeout, 20,000 files, **25 MiB per file**, unlimited static requests | Faster global CDN than GH Pages; Cloudflare now steers new projects to "Workers with static assets" (same 20k files / 25 MiB limits on Free; static requests free and uncounted). Pages is still supported. Use if you want a nicer domain or later add a Worker. |
| **Observable Cloud** | Hosting deprecated 2025-04-15 | Not an option. |
| **Cloudflare R2** | 10 GB storage, 1M Class A + 10M Class B ops/month, zero egress | Only needed if a PMTiles file exceeds 25 MiB or you want to keep big data out of the git repo. Needs a Cloudflare account and a payment method on file **[unverified whether a card is required for R2 free tier]**. |
| **Hugging Face Datasets** | Free public storage, Parquet preferred, dataset card required; HF asks that large uploads be useful to the community | Good home for the processed Parquet + yearly archive if the repo should stay small; gives a second discovery channel. |
| **Zenodo** | Free, DOI per release, GitHub integration archives each release automatically (public repos only), concept DOI + version DOIs; metadata from `CITATION.cff` or `.zenodo.json` | Use for the frozen v1.0 data+code snapshot cited in the brief. |

Recommendation: GitHub Pages for the site, git for files under ~10 MB, GitHub Release assets (2 GB per file) or Zenodo for the frozen raw-data snapshot, and no LFS (LFS free quota is 1 GB storage / 1 GB bandwidth per month and gets exhausted by cloners).

---

## 2. Repo structure for a reproducible research project

### 2.1 Layout (cookiecutter-data-science v2 flavoured, trimmed)

Cookiecutter Data Science v2 (`pip install cookiecutter-data-science`, `ccds`) gives the canonical `data/{raw,interim,processed,external}`, `Makefile`, `src/`, `reports/figures`, mkdocs layout. Use it as the starting shape but do not keep the parts you will not fill (mkdocs, `models/`).

```
frontline-from-space/
├── README.md                 # 1-screen pitch, headline figure, links to brief + dashboard + DOI
├── LICENSE                   # MIT (code)
├── LICENSE-DATA              # CC BY 4.0 (derived data), with upstream attributions
├── CITATION.cff              # Zenodo picks this up
├── PREREGISTRATION.md        # frozen before re-running; hash committed; OSF link
├── pyproject.toml            # uv/pip; pinned via uv.lock
├── Makefile                  # make data | panel | coverage | figures | site | brief | test | all
├── data/
│   ├── manifest.yaml         # every raw file: url, sha256, bytes, retrieved_at, licence
│   ├── raw/        (gitignored, fetched by `make data`)
│   ├── interim/    (gitignored)
│   ├── processed/  (committed if < 10 MB: panel, coverage grid, weekly fronts)
│   └── sample/     (committed: 2 weeks of FIRMS + 3 DeepState days for CI)
├── src/frontline/
│   ├── fetch.py              # pooch registry → data/raw
│   ├── geometry.py           # line of contact, sectors, bands (from first_pass.py)
│   ├── panel.py              # sector × week build
│   ├── coverage.py           # blind-spot grid
│   ├── models.py             # pre-registered spec + robustness
│   └── export.py             # parquet / topojson / json for the site
├── notebooks/                # exploration only; numbered; outputs stripped (nbstripout)
├── tests/                    # pytest on data/sample: shapes, row counts, invariants
├── site/                     # Observable Framework project or plain HTML + MapLibre
├── brief/                    # brief.qmd → HTML + PDF (Typst)
├── reports/figures/          # png/svg generated by `make figures`
└── .github/workflows/
    ├── ci.yml                # on push/PR: lint, pytest, `make all` on data/sample
    ├── site.yml              # on push to main: build site → GitHub Pages
    └── refresh.yml           # cron: pull FIRMS NRT + DeepState, rebuild processed + site
```

### 2.2 Data manifest and fetching

- Use **pooch** (`pip install pooch`) as the registry: a text or YAML file with `filename sha256` lines plus a base URL; `pooch.retrieve` only downloads when missing or hash-mismatched; `pooch.make_registry()` builds the file. This is lighter than DVC and needs no remote. Add columns for `url`, `bytes`, `retrieved_at`, `licence`, `notes` in `data/manifest.yaml` and generate the pooch registry from it.
- Record the exact FIRMS yearly URLs (`https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/<year>/viirs-snpp_<year>_Ukraine.csv`; 2019 and 2021 HEAD-checked 200 today; 2026 still 404; `viirs-noaa20`/`viirs-noaa21` country files **do not exist** at that pattern, 404) and the cyterat mirror commit SHA for the DeepState files.
- FIRMS NRT rows are replaced by standard-processing (SP) rows after ~5 months, so hash drift is expected for recent months. Treat the yearly archive CSVs as immutable once the year is closed, and the API pulls as a separate, dated layer.
- When to graduate to DVC: only if raw data exceeds a few hundred MB (e.g. adding Russia 2022–25 at 76 MB/year plus NOAA-20/21). Not needed for v1.

### 2.3 Makefile and CI

- `make all` runs `fetch → geometry → panel → coverage → models → export → figures`. Each target depends on its inputs, so CI can run the whole chain on `data/sample/` in under 5 minutes.
- GitHub Actions is **free for public repositories on standard runners** (GitHub billing docs). Keep CI to `ubuntu-latest`, cache the `uv` environment, and pin `geopandas`/`shapely`/`pyproj` versions.
- CI checks worth having: row counts match `manifest.yaml`; panel has 22 × N rows; no NaN in outcome; pre-registered spec reproduces the committed coefficient to 1e-6 on the frozen data; `quarto render` succeeds.
- Add `pre-commit` with ruff + nbstripout; add `CITATION.cff`; add a `CHANGELOG.md`.

### 2.4 Licence choice

| Component | Licence | Why |
|---|---|---|
| Code | **MIT** | Standard, employer-friendly, same as The Economist's war-fire model repo. Avoid GPL for code so a company can read/reuse it without hesitation. |
| Derived data (panel, coverage grid, weekly fronts) | **CC BY 4.0** | Matches UCDP (CC BY 4.0) and The Economist (CC BY 4.0). |
| Brief text and figures | CC BY 4.0 | Same. |
| **Upstream attributions required** | NASA FIRMS: no formal licence, "full and open" with a requested acknowledgment ("We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Earth Science Data and Information System (ESDIS)") and a copy of/link to their disclaimer when redistributing. **DeepStateMap**: content may be used with "a text reference, the DeepStateMap.live logo, or a direct link"; API free for volunteer/charity/defence-of-Ukraine users, commercial API use needs prior permission; "creation of identical objects that completely match the Objects is prohibited" (so do **not** republish their raw daily polygons as a mirror; publish only your derived weekly fronts/changes and point to the source). The **cyterat mirror is GPL-3.0** (applies to its scripts; whether GPL can attach to the data files is legally doubtful, but do not vendor its files into your repo; fetch them in `make data`). UCDP GED: CC BY 4.0 with two required citations (Davies, Pettersson & Öberg 2026 JPR; Sundberg & Melander 2013). ISW ArcGIS layers: copyright ISW/AEI CTP, no licence stated, publicly queryable (2000-record pages, GeoJSON) — use for a cross-check figure only, not redistribution **[licence unverified; ask ISW before redistributing]**. |

---

## 3. Living updates: is a daily refresh worth it, and what does it cost?

### 3.1 What a refresh needs

- **FIRMS NRT via the area API.** `https://firms.modaps.eosdis.nasa.gov/api/area/csv/[MAP_KEY]/[SOURCE]/[W,S,E,N]/[DAY_RANGE]/[DATE]`. Sources: `VIIRS_SNPP_NRT`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT` (plus `_SP` variants and `MODIS_*`). `DAY_RANGE` 1–5. Limit **5,000 transactions per 10-minute interval per MAP_KEY**; multi-day requests may count as several transactions. MAP_KEY is free (email registration). A daily pull of 3 sources × 1 day over the Ukraine bbox is 3 transactions. A full 2024–25 backfill of NOAA-20 SP in 5-day chunks is ~146 requests per source: trivial.
- **NOAA-20/21 history** (the "3× overpasses" fix from the verdict): the yearly country CSVs do not exist for them (404), so use either the API `VIIRS_NOAA20_SP` in 5-day chunks or the **FIRMS Archive Download tool** (`https://firms.modaps.eosdis.nasa.gov/download/`, Earthdata login, email delivery, CSV/SHP/JSON; NOAA-20 from 2018-04-01, NOAA-21 from 2024-01-17, S-NPP from 2012-01-20). One archive request per sensor covers everything.
- **DeepState.** The cyterat mirror updates ~03:00 UTC daily via its own GitHub Action; one `curl` of today's file (~75 KB). Backfill 2022-04 to 2024-07 from `https://deepstatemap.live/api/history/public` (1,785 snapshot IDs) and `/api/history/<id>/geojson` (~200 KB–1 MB each → ~0.5–1 GB total, ~1,800 requests, run once, slowly, with a polite delay; filter to occupied-area polygons by style). This is history, not a daily job.

### 3.2 Where to run it

| Runner | Fit | Cost | Gotchas |
|---|---|---|---|
| **GitHub Actions `schedule`** | Python already there; can commit processed outputs and redeploy Pages in the same run | $0 on a public repo | Minimum interval 5 min; runs can be delayed at the top of the hour (schedule at e.g. 04:17 UTC, after cyterat's 03:00); **scheduled workflows are disabled automatically after 60 days with no repository activity on a public repo** (the bot's own commits count as activity, so a daily commit keeps it alive; still add a `workflow_dispatch` and a monthly reminder). Store MAP_KEY as a repo secret. |
| **Cloudflare Workers cron** | 5 cron triggers per account on Free, 10 ms CPU per run on Free | $0 | 10 ms CPU is enough to fetch and store a CSV into R2/KV, not to run shapely. You would still need somewhere to compute. Only sensible as a "fetch-and-stash" step. |
| Local launchd on the Mac | Works | $0 | Dies when the laptop sleeps; defeats the point of a public living artifact. |

### 3.3 Verdict

**Worth it, in a limited form, because it changes how the project reads.** A dashboard with a "data through yesterday" stamp reads as a shipped system; a static one reads as a homework assignment. But the analysis (pre-registered panel regression) must **not** auto-update, or the pre-registration is meaningless and the results will drift with NRT→SP revisions.

So split it:
- **Living layer (daily, automated):** latest FIRMS detections (last 30 days) over the current line of contact, the current week's coverage/blind-spot grid, and a "sensor status" strip (which satellites reported, which days had `missing_data`). ~150 lines of Python, one Action, runtime under 2 minutes, $0.
- **Frozen layer (versioned releases):** the panel, the models, the brief. Re-run manually at quarter ends with a new tag + Zenodo DOI.

Effort: 1 day to build, half a day to harden (retries, idempotent commits, failure badge). Risk: FIRMS 504s (reported on the Earthdata forum 2025) — make the job retry and tolerate a missed day. If it ever becomes a maintenance burden, freeze it and leave the "last updated" stamp; a dated freeze is honest and still fine for a portfolio.

---

## 4. The brief

### 4.1 Format

- **Source:** one `brief.qmd` rendered by **Quarto** to **HTML** (embed-resources, self-contained, published on the Pages site) **and PDF via Typst** (`format: typst`; Quarto bundles the Typst CLI, so no LaTeX install). Quarto 1.9 (2026-03-24) adds `pdf-standard` for PDF/A and PDF/UA and passes `fig-alt` through; the Mac currently has 1.8.26, so upgrade (`brew upgrade quarto` or the installer).
- Why both: HTML is what a hiring manager clicks from LinkedIn; PDF is what gets attached to an application or printed by an interviewer. Same source, zero duplication.
- Alternative: Quarto `manuscript` project type gives a website with linked notebooks and downloadable PDF/DOCX — heavier than needed. Plain Typst (no Quarto) is fine but loses the executed-code path.
- Datawrapper/Observable Plot can supply interactive versions of 2–3 charts in the HTML; the PDF gets static SVG/PNG from the same data.

### 4.2 Length and structure (target 5–8 pages, ~2,500–3,500 words + 6–8 figures)

1. **One-paragraph answer** (what FIRMS can and cannot tell an analyst) and a headline figure (front vs rear density by month, with the blind season shaded).
2. Question, pre-registered hypotheses (link to PREREGISTRATION.md and the commit hash), data (FIRMS, DeepState, baseline years), geometry (line of contact, 22 sectors, bands) — half a page with the sector map.
3. Results in the order of the hypotheses: (a) localisation (front/rear contrast, pre-war-baseline contrast), (b) lead-lag (the honest near-null, with the leave-one-sector-out and placebo tables), (c) blind spots (coverage map, season × cloud × fuel), (d) transfer (Sudan/within-war 2022 manoeuvre phase, whatever got done).
4. **Limitations and threats** as a table: map latency, NRT vs SP, cloud = unobserved not absent, agricultural confound, multiple specifications tried.
5. **What this means for an analyst** (sensor-fusion triage framing from the verdict): 5 bullets.
6. Reproducibility box: repo, DOI, `make all`, data licences.
7. Appendix (not counted): full regression tables, robustness, data manifest.

### 4.3 Figure standards

- Every figure generated by code in `make figures`, saved as SVG + 300-dpi PNG, filenames = figure numbers, data behind each figure saved as CSV in `reports/figures/data/`.
- Consistent projection (UTM 37N for area; Web Mercator for the web map), consistent sector numbering and colours across map, dashboard and brief.
- Colour: one sequential palette for density (viridis or cividis), one diverging for change (gain/loss), grey hatching for "unobserved/blind". Colour-blind safe; never red/green alone.
- Each figure: title stating the finding, subtitle with units and N, source line with FIRMS/DeepState attribution and date pulled, caption that says what to look at. Uncertainty shown (CIs or leave-one-out spread), not just point estimates.
- Maps: scale bar, north not needed, basemap muted (Protomaps/OpenFreeMap or a plain Natural Earth outline), front line always on top.

### 4.4 Side piece (air-defence reporting artifact)

Same template, 2–3 pages, one figure (destroyed-only vs destroyed+EW-lost drone rates by quarter), separate `qmd`, same site. Framed as "a reporting-regime break, documented," per the airdefense VERDICT.md.

---

## 5. Resume / portfolio packaging

- **One link.** `https://<user>.github.io/frontline-from-space/` landing page: headline figure, three sentences, buttons for Dashboard / Brief (HTML) / Brief (PDF) / Repo / DOI. Everything else hangs off it.
- **Resume line (one):** "Front line from space — built a reproducible pipeline (Python, GeoPandas, GitHub Actions) fusing 150k+ NASA FIRMS thermal detections with daily territorial-control maps into a 22-sector × 77-week panel; pre-registered and falsified a lead-lag hypothesis with fixed-effects/clustered inference; shipped a blind-spot coverage map and daily-refreshing dashboard (MapLibre/Observable). Open data, open code (DOI)." Adjust numbers to the final run.
- **GitHub README** = the 30-second interview: pitch, headline figure, "what I found / what I didn't", stack badges, CI badge, "last data refresh" badge (shields.io endpoint badge reading a JSON the Action writes), how to reproduce in three commands.
- **LinkedIn post + Rolodex follow-ups:** the Ukraine reflection draft already exists in `~/Jackson Mackney/LinkedIn`; this project is the natural second post. Lead with the honest-null framing, which is what differentiates it.
- **Interview-proofing:** a `docs/FAQ.md` answering the questions an interviewer will ask (why 15 km bands, why Voronoi then why not, why not Shahed strikes, how NRT revisions were handled, what would change the result). The verdict's fragility checks belong here.
- **Zenodo DOI** on the v1.0 release so the brief is citable and the archive is independent of GitHub.
- Optional: a 60–90 second screen recording (kepler.gl time playback is good for this) as a GIF in the README.
- What **not** to do: do not claim prediction; do not host on a service that sleeps; do not put ROTC anywhere (per memory); do not list GPA.

---

## 6. Minimum stack vs stretch stack

### Minimum (ship this; ~5 infra days inside the 4–6 weeks, $0)
- Repo: ccds-v2 shape, `uv` + `pyproject`, Makefile, pooch manifest, pytest on `data/sample/`, GitHub Actions CI, MIT + CC BY 4.0, `CITATION.cff`.
- Data served: Tier A aggregates (coverage grid JSON, weekly fronts TopoJSON, panel CSV) + Tier B Parquet of cleaned points.
- Dashboard: Observable Framework (or a single hand-written HTML with MapLibre + Observable Plot if node is unwelcome), deployed to GitHub Pages by Action.
- Living layer: one daily `refresh.yml` that pulls FIRMS NRT (3 sources, Ukraine bbox) + today's DeepState file, rebuilds the last-30-days layer and the coverage strip, commits, redeploys. Analysis frozen.
- Brief: Quarto → HTML + Typst PDF, 5–8 pages, 6–8 code-generated figures.
- Portfolio: landing page, README, Zenodo DOI, resume line, FAQ.

### Stretch (only after the minimum is live)
- PMTiles of all detections 2019–2025 incl. NOAA-20/21 via tippecanoe; R2 if > 25 MiB.
- DuckDB-WASM in-browser querying ("fires within 15 km of the front in week N, night-only, FRP > x").
- Cross-check layer from ISW ArcGIS timelapse services (after a licence email).
- Sudan transfer panel (FIRMS Sudan 2024 15.7 MB HEAD-checked; UCDP GED 26.1 CC BY 4.0) on the same site as a second tab.
- Cloudflare Pages/Workers mirror with a custom domain; Hugging Face Datasets copy of the Parquet.
- Quarto `manuscript` with linked notebooks; PDF/A via `pdf-standard`.
- Reuse The Economist's open war-fire classifier (MIT code, CC BY 4.0 data, updated daily, `output-data/ukraine_war_fires.csv`) as an alternative "war fire" definition for a robustness column — it is a published pre-war-baseline method, which is exactly the control the verdict asked for.

---

## 7. Suggested order of work (infra only)

| Day | Do | Output |
|---|---|---|
| 1 | Create repo from ccds v2; port `first_pass.py` into `src/frontline/`; write `manifest.yaml` + pooch fetch; `make data` works | green `make data` |
| 2 | `data/sample/`, pytest, `ci.yml`; `make panel` reproduces `sector_week_panel.csv` byte-for-byte | CI badge |
| 3 | `export.py` → Parquet, TopoJSON, coverage JSON; Observable Framework skeleton with map + 2 charts; deploy to Pages | live URL |
| 4 | `refresh.yml` with MAP_KEY secret; last-updated badge; failure notification | daily commits |
| 5 | `brief.qmd` skeleton rendering to HTML + Typst PDF with placeholder figures; landing page; `CITATION.cff` | both formats render |
| later | PMTiles, DuckDB-WASM, Sudan tab, Zenodo on v1.0 | |

---

## 8. Unverified or to-confirm

- PMTiles/Parquet sizes above are estimates; measure on the real data.
- Whether Cloudflare R2's free tier requires a card on file.
- ISW ArcGIS reuse terms (copyright notice present, no licence found).
- Whether GPL-3.0 on the cyterat mirror is intended to cover the data files; avoid vendoring regardless.
- FIRMS API: whether `VIIRS_NOAA21_SP` exists (the area page lists `VIIRS_NOAA21_NRT` only).
- Observable Framework's maintenance trajectory (last push 2026-05-15; builds fine today).
- GitHub Pages and Cloudflare Pages range-request support for PMTiles is widely reported (Protomaps docs list GitHub Pages and Netlify as static hosts that work) but not tested here.

## Sources
- Cloudflare Pages limits: https://developers.cloudflare.com/pages/platform/limits ; Workers static-asset limits: https://developers.cloudflare.com/workers/platform/limits ; changelog 2025-09-02: https://developers.cloudflare.com/changelog/2025-09-02-increased-static-asset-limits/ ; Pages→Workers migration: https://developers.cloudflare.com/workers/static-assets/migrate-from-pages/
- GitHub Pages limits: https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits ; Actions billing: https://docs.github.com/en/billing/managing-billing-for-your-products/about-billing-for-github-actions ; schedule event: https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows
- PMTiles: https://docs.protomaps.com/pmtiles/ and https://docs.protomaps.com/pmtiles/cloud-storage ; tippecanoe releases: https://github.com/felt/tippecanoe/releases
- Observable Framework: https://github.com/observablehq/framework ; Observable Cloud deprecation: https://old.observablehq.com/documentation/data-apps/ ; forum on GH Pages deploy: https://talk.observablehq.com/t/deploying-observable-framework-on-github-pages-with-r-and-python-as-data-loaders/9043
- kepler.gl FAQ/URL loading: https://docs.kepler.gl/docs/user-guides/b-kepler-gl-workflow/a-add-data-to-the-map ; repo: https://github.com/keplergl/kepler.gl
- deck.gl H3HexagonLayer: https://deck.gl/docs/api-reference/geo-layers/h3-hexagon-layer ; DuckDB-WASM GeoParquet in browser: https://dev.to/camptocamp-geo/querying-overture-maps-geoparquet-directly-in-the-browser-with-duckdb-wasm-4jn4 ; https://developmentseed.org/blog/2025-10-08-spatial-access-lab
- Streamlit Community Cloud limits: https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app
- Felt pricing: https://felt.com/pricing ; Datawrapper free plan: https://www.datawrapper.de/blog/create-data-visualization-for-free/ and https://www.datawrapper.de/pricing
- FIRMS API: https://firms.modaps.eosdis.nasa.gov/api/ and https://firms.modaps.eosdis.nasa.gov/api/area/ ; Archive Download: https://firms.modaps.eosdis.nasa.gov/download/ ; FIRMS attribution: https://www.earthdata.nasa.gov/data/tools/firms ; forum on 5000/10 min and 504s: https://forum.earthdata.nasa.gov/viewtopic.php?p=23833
- DeepStateMap licence: https://deepstatemap.live/license-en.html ; mirror: https://github.com/cyterat/deepstate-map-data
- The Economist war-fire model: https://github.com/TheEconomist/the-economist-war-fire-model
- ISW ArcGIS services: https://services5.arcgis.com/SaBe5HMtmnbqSWlu/ArcGIS/rest/services/May_2025_Timelapse/FeatureServer/layers
- UCDP downloads/licence: https://ucdp.uu.se/downloads/
- Cookiecutter Data Science v2: https://cookiecutter-data-science.drivendata.org/ ; pooch: https://pypi.org/project/pooch/
- Zenodo–GitHub: https://docs.github.com/en/repositories/archiving-a-github-repository/referencing-and-citing-content
- Quarto Typst: https://quarto.org/docs/output-formats/typst/ ; Quarto 1.9: https://quarto.org/docs/blog/posts/2026-03-24-1.9-release ; manuscripts: https://prerelease.quarto.org/docs/manuscripts
- OSF preregistration template: https://www.overleaf.com/latex/templates/osf-preregistration-template/ycwdkjhjpgfy
- Hugging Face storage limits: https://huggingface.co/docs/hub/en/storage-limits
- MODIS/VIIRS cloud mask (for the "unobserved vs no fire" product): https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/science-domain/cloud-mask/
