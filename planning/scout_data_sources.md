# Scout: data sources for "Front line from space"

Compiled 2026-10-13. Scope: every open dataset that could feed the project (FIRMS-vs-front-line in Ukraine, blind-spot/coverage product, transfer test to Sudan or another war, plus the drone-intercept side note).

**How to read the verification tags**
- **[VERIFIED]** I hit the URL today (HTTP 200, and usually inspected the payload / schema / row counts).
- **[DOC]** Taken from an official documentation page I fetched today, not from a download.
- **[UNVERIFIED]** From memory or a search snippet; confirm before relying on it.
- Sizes are `Content-Length` from a HEAD request unless stated.

Ground truth already in hand (see `/Users/jacksonmackney/D3/Conflict_Data_Feasibility/frontline/SOURCES.md`): VIIRS S-NPP yearly Ukraine CSVs 2023–25 (197k rows), MODIS 2023 Ukraine, 536 daily DeepState polygons 2024-07-08 → 2025-12-31 (cyterat mirror), Natural Earth 50m borders. ~82 MB total.

---

## 0. The short list (what to actually pull, in order)

| Priority | Source | Why | Cost to get |
|---|---|---|---|
| 1 | FIRMS API with free MAP_KEY: `VIIRS_NOAA20_SP`, `VIIRS_NOAA21_NRT`, `VIIRS_SNPP_SP`, night flag, FRP | Triples overpasses; closes the "no detection ≠ no fire" gap; adds 2026 | 10-min signup, bbox loop of ≤5-day chunks |
| 2 | FIRMS yearly country CSVs 2012–2025 for Ukraine (pre-war baseline 2012–21) and Russian_Federation 2022–25 | Economist-style per-cell pre-war baseline replaces the weak Voronoi rear strip; Russia file covers Kursk/Belgorod | No key; ~8 MB/yr Ukraine, 76 MB/yr Russia |
| 3 | ISW ArcGIS feature services (`UkrainianCoTTimelapse_FEB_2022_to_DEC_2024_view`, monthly `*_Timelapse` services 2025–26) | A second, independent coding of control with a `datetime` field from 2022-02-24; lets you backfill 2022–mid-2024 (manoeuvre phase) and cross-check DeepState batch latency | Public REST, no key; paginate 2000 recs/query |
| 4 | DeepState own history API (1,785 snapshots 2022-04-03 → 2026-10-13) | Primary control source back to April 2022 | ~1,800 requests, filter KML-style layers |
| 5 | The Economist war-fire repo (`cloud_cover_in_ukraine_by_day.csv`, `firms_update_RU.csv`, `ukraine_war_fires.csv`, `areas_of_control_daily_summary.csv`) | Ready-made daily cloud-cover series (2022-01-01 → today), a published war-fire classifier to benchmark against, ISW-derived daily area 2022-02-24 → 2023-11-05 | One `git clone`, CC BY 4.0 |
| 6 | ERA5 `tcc` hourly via CDS API, or MOD09GA/MYD09GA `state_1km` cloud bit in GEE | Your own cloud/obscuration covariate for the blind-spot map (the Economist file is a black box) | Free account; a few hundred MB |
| 7 | ESA WorldCover 2021 10 m + MCD64A1 500 m burned area + Hall et al. (2021) crop-burning calendar | Fuel/land-cover stratification; agricultural-fire season | Free, CC BY 4.0 / public domain |
| 8 | UCDP GED 26.1 + Candidate 26.0.8 (CC BY 4.0, no login) and ACLED (free registration) for Sudan, Myanmar, Mali/Burkina, Ethiopia | Transfer test outcome variable where no control polygons exist | Minutes |
| 9 | GeoConfirmed API (`/api/placemark/Ukraine`, 60,783 placemarks 2014→2026-10-13), Bellingcat civilian-harm JSON (2,517 incidents), Oryx scrapes | Point-event validation of what FIRMS does and does not see | No key |

Everything below is the long-form catalogue.

---

## 1. Thermal / active-fire feeds

### 1.1 NASA FIRMS, country yearly CSVs (no key) **[VERIFIED]**
- **URL pattern:** `https://firms.modaps.eosdis.nasa.gov/data/country/<sensor>/<year>/<sensor>_<year>_<Country>.csv`, `<sensor>` ∈ {`viirs-snpp`, `modis`}. All-country zips: `.../data/country/zips/viirs-snpp_<year>_all_countries.zip` (2024: 372 MB).
- **Verified today (HTTP 200):** `viirs-snpp_2019_Ukraine.csv` (7.8 MB); `viirs-snpp_2024_Russian_Federation.csv` (76.0 MB); `viirs-snpp_2024_Sudan.csv` (15.7 MB); `viirs-snpp_2025_Sudan.csv`; `viirs-snpp_2024_Myanmar.csv` (26.5 MB); `viirs-snpp_2024_Ethiopia.csv`; `viirs-snpp_2024_Mali.csv`; `viirs-snpp_2024_Burkina_Faso.csv`; `modis_2024_Ukraine.csv`.
- **Verified 404 today:** `viirs-noaa20_2024_Ukraine.csv`, `viirs-noaa21_2024_Ukraine.csv`, `viirs-snpp_2026_Ukraine.csv`, `viirs-noaa20_2024_all_countries.zip`. **The yearly country files exist only for S-NPP and MODIS.** NOAA-20/21 must come from the API or the Archive Download tool.
- **Coverage:** S-NPP 375 m from 2012-01-20; MODIS 1 km from 2000-11. Yearly files are standard-processing (SP) science quality.
- **Fields (VIIRS):** latitude, longitude, bright_ti4, scan, track, acq_date, acq_time (UTC HHMM), satellite (N), instrument, confidence (l/n/h), version, bright_ti5, frp (MW), daynight (D/N), type (0 veg fire, 1 volcano, 2 other static land, 3 offshore). MODIS confidence is 0–100 instead.
- **License:** NASA data policy, effectively public domain; cite FIRMS/LANCE and replicate the NRT disclaimer if redistributing. No login.
- **Use in this project:** Backbone. Pull Ukraine 2012–2025 (pre-war baseline 2012–2021, ~10 files, ~80 MB) and Russian_Federation 2022–2025 (~300 MB) for Kursk/Belgorod/Bryansk. Pull Sudan 2022–2025, Myanmar 2023–2025, Mali/Burkina 2022–2025 for the transfer test. Known limits from the feasibility pass stand: clipped at the international border, type-2 industrial false positives (Donbas coke/steel), winter blindness.

### 1.2 NASA FIRMS API (free MAP_KEY) **[DOC]**
- **Signup:** https://firms.modaps.eosdis.nasa.gov/api/map_key (email only, instant).
- **Area endpoint:** `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{west,south,east,north}/{DAY_RANGE}[/{YYYY-MM-DD}]`.
- **Sources listed on the docs page:** `MODIS_NRT`, `MODIS_SP`, `VIIRS_SNPP_NRT`, `VIIRS_SNPP_SP`, `VIIRS_NOAA20_NRT`, `VIIRS_NOAA20_SP`, `VIIRS_NOAA21_NRT`, `LANDSAT_NRT` (US/Canada only). **No `VIIRS_NOAA21_SP` yet.**
- **Limits:** 1–5 days per call; 5,000 transactions per 10 minutes per key; a multi-day call may count as several transactions. Lookback: use `/api/data_availability/csv/{MAP_KEY}/ALL` to get exact start dates per source (needs the key; the keyless call returns "Invalid MAP_KEY").
- **Sensor start dates (Archive page):** S-NPP 2012-01-20; NOAA-20 2018-04-01; NOAA-21 2024-01-17; Landsat 2022-06-20 (NA only). NRT is replaced by SP science quality after ~5 months.
- **Size estimate:** A Ukraine bbox (22–41 E, 44–53 N) for 2024 is ~86k rows for S-NPP alone; expect ~250k rows/yr with NOAA-20 and NOAA-21 added, ~30 MB/yr. For 2022–2026 all three sensors: ~1,000 five-day calls per sensor, ~3,000 calls total; well within the limit, under an hour with polite sleeps.
- **Use in this project:** The single cheapest improvement. Three VIIRS satellites give roughly 6 overpasses/day instead of 2, with ~50-minute spacing between the morning/afternoon passes of each pair. This directly attacks the "not observed vs. no fire" problem and is the basis for a per-cell per-day "number of clear looks" coverage layer. Also the only route to 2026 data.

### 1.3 NASA FIRMS Archive Download tool **[DOC]**
- **URL:** https://firms.modaps.eosdis.nasa.gov/download/ (older than 7 days only). Choose country or draw a bbox, sensor, date range; formats .shp/.csv/.json; delivered by email after processing; Earthdata login or emailed code. Includes a "Download yearly summary by country [.csv]" link.
- **Use:** Fallback for bulk NOAA-20/21 if the API loop is slow. No license text on the page.

### 1.4 FIRMS in Google Earth Engine **[DOC]**
- `ee.ImageCollection("FIRMS")`: MODIS-only NRT raster, 1 km, 2000-11-01 → 2026-10-12 (daily), bands `T21`, `confidence`, `line_number`. Not VIIRS.
- `NASA/LANCE/SNPP_VIIRS/C2` and `NASA/LANCE/NOAA20_VIIRS/C2`: VIIRS 375 m daily NRT rasters (VNP14IMGTDL_NRT / VJ114IMGTDL_NRT). NOAA-20 collection listed from 2023-10-08. Rolling NRT, "not science quality".
- Community catalog (Samapriya Roy): `projects/sat-io/open-datasets/VIIRS/VNP14IMGTDL_NRT_YYYY` 2012–2021 and `projects/sat-io/open-datasets/MODIS_MCD14DL/MCD14DL_YYYY` 2000–2020, archival vector points. https://gee-community-catalog.org/projects/firms_vector/ . Frozen at 2022-04-28.
- **Use:** GEE is the right place to compute the cloud/clear-look covariate and land-cover intersections at scale, but for the fire points themselves the CSV/API route is simpler and science-quality. Use GEE if you want to turn the coverage product into a map tile service for the dashboard for free.

### 1.5 VIIRS Nightfire (VNF), Earth Observation Group, Colorado School of Mines **[DOC]**
- **URL:** https://eogdata.mines.edu/products/vnf/ ; product page https://payneinstitute.mines.edu/eog/viirs-nightfire-vnf . Free registration required (EOG account). Nightly CSV and KMZ per UTC date; V3.0 operational, V4.0 available from 2025-07-01 for S-NPP, NOAA-20 and NOAA-21. Coverage 2012 → present. Uses M10–M13 plus M7/M8/DNB confirmation; Planck-curve fit gives sub-pixel temperature, source area and radiant heat (fields: Temp_BB, Area_BB, RH, etc.).
- **License:** Not stated; credit EOG/Payne Institute and cite Elvidge et al. 2013 (*Remote Sensing* 5:4423). Treat as research-use, check the account terms.
- **Prior art:** Dingemanse, Zhizhin, Cerra (Payne Institute post 2026-03-02) "Conflict monitoring with VIIRS Nightfire: the war in Ukraine" — frontline delineation, urban combat detection, heavy-industry status; article ID s41598-026-42172-0 (Scientific Reports; DOI inferred, not fetched). The VERDICT already cites it.
- **Use:** Night-only, temperature-resolved detections. Combustion at >1,500 K (munitions, vehicles, fuel) separates from ~1,000 K vegetation fire. This is the best available tool for the "what kind of fire" question and for a night-only robustness check that removes most agricultural burning. Modest size: a few MB per night globally, filter to the AO.

### 1.6 Sentinel-3 SLSTR FRP (active fire) **[DOC]**
- Collections `SL_2_FRP___` NRT (EUMETSAT) and NTC on the Copernicus Data Space Ecosystem (https://dataspace.copernicus.eu/), 2020-08-08 → present, global, 1 km, day and night, S3A+S3B (~2 more overpasses/day). Also published in the Climate Data Store as an active-fire/FRP dataset from 2020. Free account; S3/STAC/openEO access. License: Copernicus Sentinel legal notice (free, open, attribution).
- **Use:** Optional fourth/fifth look per day for the coverage product. Low priority because 1 km resolution adds little over VIIRS and the format (SAFE/netCDF) is heavier; worth a one-day spike only if you want to show "sensor fusion" in the brief.

### 1.7 Landsat 8/9 and Sentinel-2 (burn scars and SWIR) **[DOC/UNVERIFIED]**
- FIRMS `LANDSAT_NRT` 30 m active fire covers only CONUS/Canada/northern Mexico; not usable for Ukraine.
- Sentinel-2 L2A (10–20 m, 5-day revisit, free via CDSE or GEE `COPERNICUS/S2_SR_HARMONIZED`) and Landsat C2 L2 (30 m, GEE `LANDSAT/LC08/C02/T1_L2`, `LC09`) give burn scars via NBR/dNBR (B8A/B12) for after-the-fact validation of FIRMS clusters.
- Existing Ukraine burn-perimeter products: *Ukraine Fire Perimeters 2022* (Zenodo 8298835) and *2023* (Zenodo 10514571, Zibtsev et al., NUBiP, CC BY 4.0, shapefile 12.6 MB, Sentinel-2 SWIR2–NIR–Red visual delineation seeded from MODIS/VIIRS, with `occupied` and `buff_30km` flags). No 2024 version seen.
- MCD64A1 v6.1 burned area, 500 m monthly, 2000-11 → 2026-07 in GEE (`MODIS/061/MCD64A1`), bands BurnDate/Uncertainty/QA, public domain. FireCCI51 (250 m) and GABAM (30 m Landsat annual) exist [UNVERIFIED current versions]. Hall et al. 2021 show MCD64A1 under-counts Ukrainian cropland burns by 30–63 %.
- **Use:** (a) Validate that FIRMS "front" clusters correspond to real scars; (b) quantify how much front-band burning is in cropland vs. grass/forest vs. built-up; (c) a few before/after Sentinel-2 chips for the brief. Do not build the core analysis on these; they lag and cloud-fail too.

### 1.8 Sentinel-1 SAR and open damage products **[VERIFIED record pages]**
- Sentinel-1 GRD/SLC free via CDSE and AWS (`registry.opendata.aws/sentinel-1`), 10 m, ~6–12-day revisit over Ukraine (S1A + S1C since 2025), all-weather. No open "military activity" product exists; it is a raw sensor.
- **Dietrich et al. (ETH Zurich) 2025**, *Communications Earth & Environment*, "An open-source tool for mapping war destruction at scale in Ukraine using Sentinel-1 time series": Zenodo 15088349 (v2, 2025-03-19), 22.8 GB, country-wide building-damage heatmap 2022-02 → 2024-02, Overture footprints with damage probabilities, UNOSAT labels and AOIs; runs on GEE; per-period heatmaps on request. License on the Zenodo record (check; likely CC BY).
- **PWTT (Pixel-Wise T-Test)**, pip package `pwtt`, Sentinel-1 battle-damage change detection with a UNOSAT-labelled benchmark (Mariupol, Rubizhne, Irpin, Gaza).
- UNOSAT Ukraine rapid damage assessments: older 2022 products on HDX (Sumy, N. Kharkiv), geodatabase/shapefile, public.
- **Use:** A damage layer is a *third* outcome variable independent of both FIRMS and control maps: does FIRMS activity in a cell precede SAR-detected building damage? Treat as a stretch goal (week 5+), using the Dietrich heatmap rather than processing S1 yourself.

### 1.9 Copernicus Emergency Management Service (CEMS) Rapid Mapping **[DOC]**
- https://emergency.copernicus.eu/ ; products free and open, attribution "© European Union, Copernicus EMS". Each activation downloadable as zip and as GeoJSON/vector tiles/COG layers. I did not find a current Ukraine or Sudan *conflict* rapid-mapping activation (search budget ran out before I could list activations; the only Sudan hit was EMSN114, a 2021 risk-and-recovery product). **[UNVERIFIED whether any 2022–26 conflict activations exist.]**
- **Use:** Low. Check the activation list once; if there is a Ukraine or Sudan damage-grading product, it is a free validation chip.

### 1.10 Commercial-imagery open programs
- **Maxar Open Data Program** **[VERIFIED STAC]**: `s3://maxar-opendata/` (us-west-2, no account), CC BY-NC 4.0, 55 event collections. All are disasters (hurricanes, earthquakes, floods, wildfires; "Sudan-flooding-8-22-2022" is a flood). **No Ukraine or conflict collections.** maxar.com/open-data had an expired TLS certificate today.
- **Planet NICFI**: tropical-only basemaps; Norwegian contract ended 2025-01-24, access being extended/relaunched [UNVERIFIED status]. Irrelevant to Ukraine (outside tropics); marginal for Sudan (Darfur is north of the NICFI belt). Planet's Education & Research program gives students limited PlanetScope quota on application [UNVERIFIED current terms].
- **Umbra Open Data** **[DOC]**: SAR 25 cm–1 m, CC license (variant unstated), STAC at `s3://umbra-open-data-catalog/stac/catalog.json`, 20+ time-series sites and 1,000+ assorted scenes; no conflict sites listed on the page.
- **Capella Open Data** [UNVERIFIED]: a small SAR sample set on AWS, CC BY 4.0, occasional conflict-adjacent scenes.
- **Use:** None of these are a data source for the analysis. One or two Sentinel-2 true-colour chips are enough for illustration; do not spend time here.

---

## 2. Territorial-control sources (Ukraine)

### 2.1 DeepStateMap.live, own API **[VERIFIED]**
- **History index:** `https://deepstatemap.live/api/history/public` → JSON list of 1,785 snapshots (2022: 420, 2023: 359, 2024: 364, 2025: 367, 2026: 275 so far), fields `id`, `description` (UA), `descriptionEn`, `createdAt`, `updatedAt`. First 2022-04-03, latest 2026-10-13 18:10 UTC.
- **Snapshot:** `https://deepstatemap.live/api/history/<id>/geojson`. Sample 1648989208 = 69 features: 59 Polygons, 7 Points, 3 GeometryCollections, KML-style `styleUrl`/`icon` properties. Must filter to occupied-area polygons by style/name (`name` like "Окуповано"/"CADR"/"CALR"/"Crimea"), not by a clean attribute. 200 KB–1 MB each; ~1,800 requests, maybe 1 GB total.
- **License (https://deepstatemap.live/license-en.html):** DEEPSTATEUATECH LLC holds rights. API free for volunteer/charitable entities and those "supporting Ukraine's defense, sovereignty, or territorial integrity"; commercial API use needs prior approval via their form; content may be used freely with text reference/logo/link; redistributing or proxying the API itself is prohibited; identical copies banned. Students/researchers are not named. **Practical reading:** a non-commercial student research project with attribution is in the spirit of the free categories, but a public repo should ship *derived* products (sector-week panel, front-line segments) rather than a mirror of raw daily polygons, and should say so. Email them; a one-line permission reply is worth having for the brief.
- **Use:** Primary control variable. Backfill 2022-04 → 2024-07 gives Kharkiv (Sep 2022) and Kherson (Nov 2022) manoeuvre phases, the 2023 counteroffensive, Bakhmut and Avdiivka. This is the within-war transfer test the VERDICT asks for. Keep the known caveat: `createdAt` is the edit time, not the ground-change time.

### 2.2 DeepState GitHub mirror `cyterat/deepstate-map-data` **[VERIFIED]**
- https://github.com/cyterat/deepstate-map-data, GPL-3.0 (applies to the scripts; the data's terms are DeepState's), daily GitHub Action ~03:00 UTC, `data/deepstatemap_data_YYYYMMDD.geojson` from 2024-07-08, plus `deepstate-map-data.geojson.gz` (dates null for most features; don't use). 35 stars, 1,274 commits.
- **Use:** Already on disk. Keep for 2024-07 onward; prefer the API for history.

### 2.3 ISW / CTP ArcGIS Online feature services **[VERIFIED, this is new]**
- **Org root:** `https://services5.arcgis.com/SaBe5HMtmnbqSWlu/ArcGIS/rest/services?f=pjson` lists **326 public feature services** (Ukraine, Kursk, Syria, Gaza, Sahel, Somalia, Iran). Capabilities: Query (some Sync). Copyright text: "Institute for the Study of War and American Enterprise Institute's Critical Threats Project". maxRecordCount 2000, so paginate with `resultOffset`. Output `f=geojson` works on ArcGIS feature services.
- **Key Ukraine services found:**
  - `UkrainianCoTTimelapse_FEB_2022_to_DEC_2024_view/FeatureServer/0` ("UkraineControlMapAO01D_Merge"): **7,540 polygons, time field `datetime`, extent 2022-02-24 → 2024-12-31.** This is a daily assessed-Russian-control timelapse for the whole war to end-2024. Also layers 1 (ClaimedRussianTerritory), 2 (ClaimedUkrainianCounteroffensives), 75 (AssessedRussianAdvance). Attribute `area` present.
  - `UkraineCoTTimelapse_Full_Length_view/FeatureServer/0..3`: same four layers, 7,540 recs, 2022-02-24 → 2024-11-30.
  - Monthly 2023–2026 timelapse services: `Ukraine_COT_Timelapse_<Month>_<Year>` (May 2023 → Apr 2025 seen), `May_2025_Timelapse`, `June_2025_Timelapse`, `July_2025_Timelapse`, `August_2025_Timelapse` (layers: AssessedRussianAdvances_AUG, ClaimedRussianTerritory_AUG, AssessedRussianControl_AUG, ClaimedUkrainianCounteroffensivesAUG), `SEP2025Timelapse1_WFL1`, `Russo_Ukraine_War_October_2025_Timelapse`, `Russo_Ukraine_War_November_2025_Timelapse`, `Ukraine_Time_Lapse_December_2025_WFL1`, `COT_Merge_Jan_2026_view/FeatureServer/37` (342 recs, 2026-01-01 → 01-31, field `Area_KM`), `ADV_merge_JAN_2026_view`, `Ukraine_Timelapse_Feb_2026_WFL1_view`, `Export_March_2026_V4`, `Ukraine_Timelapse_April_2026_WFL1`, `Assessed_Russian_Advances_in_May_2026`. Expect 2026 months to keep appearing.
  - Live layers: `Assessed_Russian_Gains_in_the_Past_24_Hours_view`, `VIEW_RussiaCoTinUkraine_V3/FeatureServer/49`, `View_AssessedRussianInfiltrationAreasinUkraine_V4`, `VIEW_Kursk_Incursion_Events_view/FeatureServer/2`, `Russian_Field_Fortifications` (+ `_Polylines`), `Bryansk__Kursk__Belgorod__and_Voronezh_Settlements_view`, `Ukrainian_Partisan_Warfare_Events_view`, `Major_Ukrainian_Railroads`, `Ukrainian_Trunk_Primary_and_Secondary_Roads`.
  - Older: `OCTControlnew/FeatureServer/0..30` = one layer per day for October 2022 (3 polygons each), `Corrected_Ukraine_COT_Timelapse_November_2023` (9,314 recs across 5 layers, 2023-02-01 → 2023-11-30).
- **License:** No explicit reuse license; copyright notice only. ISW's site terms [UNVERIFIED] generally permit non-commercial use with attribution. Same posture as DeepState: publish derived panels, not a polygon mirror; attribute "ISW/CTP".
- **Use:** (a) Independent second coding of control for a measurement-error check (DeepState vs ISW disagreement by sector-week is itself a finding); (b) `datetime` lets you test whether DeepState's batch latency hides a 1-week lead; (c) `Russian_Field_Fortifications` is a covariate for where attrition is expected; (d) `VIEW_Kursk_Incursion_Events_view` gives the Kursk case directly.

### 2.4 Economist `areas_of_control_daily_summary.csv` **[VERIFIED]**
- In the Economist repo (see 4.1): 3,002 rows, 2022-02-24 → 2023-11-05, source = ISW, five types (assessed control, claimed control, assessed advances, claimed counteroffensives, partisan), daily area km² and % of Ukraine. File names reveal ISW's daily GeoJSON naming (`UkraineControlMapAO24FEB2022.geojson`).
- **Use:** Instant national-level sanity series for 2022–23 without touching ArcGIS; confirms the ISW daily layers exist for every day.

### 2.5 UAControlMap **[UNVERIFIED]**
- https://uacontrolmap.com/ returned HTTP 200 but I could not inspect content (search budget exhausted). It is a volunteer control map (Twitter @UAControlMap). No known bulk download or license. Treat as a tertiary visual cross-check only.

### 2.6 Liveuamap **[UNVERIFIED terms]**
- https://liveuamap.com (terms page returned 403 to curl). Third-party comparison pages quote an API at $150/month Pro (200 req/day) and $1,000+/month Enterprise. No free data export; scraping would breach terms. **Exclude.**

### 2.7 Academic front-line datasets
- I found **no** Zenodo/Dataverse replication dataset of daily Ukraine control polygons (searches returned ISW/DeepState derivatives only). ix5.org has a derived day-by-day control series from Liveuamap/NZZ (personal project). WarMapper changed methodology to "presence of forces" (not comparable). PolGeoNow maps are paywalled. **[Search was partial; treat as "none known", not "none exists".]** The *Vienna* reference in the brief most likely points to wiiw's "War in Ukraine Data Tracker" (https://wiiw.ac.at/war-data-tracker.html), which is humanitarian/economic, not front-line geometry.
- **Use:** None needed; DeepState + ISW is already two independent codings.

---

## 3. Event and incident data

### 3.1 ACLED **[DOC]**
- https://acleddata.com/register ; free registration via the Access Portal, pick a category. Tiers per current docs: Public Sector (6 downloads/yr, 3 yrs history), Civil Society/Academic (unlimited downloads of the full global dataset, API on request), Corporate (3/yr, 1 yr). A 2021 FAQ listed "Academic" explicitly; the current page lists it under Civil Society — **confirm which bucket a student falls in at signup**. API default 5,000 rows/call, OAuth token (new API docs at apidocs.acleddata.com; page did not render for me). Weekly updates. Terms of Use forbid redistribution of raw data; derived aggregates with attribution are fine. ACLED also publishes curated country aggregates on HDX (`data.humdata.org/organization/acled`; Sudan page exists, license "Other").
- **Coverage:** Ukraine 2018 → present (event types battles, explosions/remote violence, etc., settlement-level geocoding); Sudan, Myanmar, Sahel, Ethiopia all covered.
- **Use:** Outcome variable for transfer wars (fires lead events/fatalities at the admin-2 or 0.25° cell level); in Ukraine, a third outcome (shelling events) and a check on whether FIRMS detects "explosions/remote violence" vs "battles". Do not commit the raw export to the public repo.

### 3.2 UCDP GED and Candidate **[VERIFIED]**
- https://ucdp.uu.se/downloads/ : GED **26.1** (`ged261-csv.zip`, 39.1 MB, 1989–2025, CC BY 4.0, no login); GED 25.1 still live (`ged251-csv.zip`); **Candidate 26.0.8** (`GEDEvent_v26_0_8.csv`, 1.4 MB, monthly, ≤1-month lag, Aug 2026 release). API: https://ucdp.uu.se/apidocs/ . Cite Davies, Pettersson & Öberg 2026 (JPR) and Sundberg & Melander 2013.
- **Caveat:** GED is fatality-focused, point-geocoded to settlements, conservative; Ukraine counts are heavily aggregated ("Donetsk oblast" rows). Good for Sudan/Sahel transfer; weak for fine Ukraine work.
- **Use:** Transfer-test outcome where ACLED terms are awkward for a public repo (UCDP is CC BY, redistributable).

### 3.3 GDELT **[DOC]**
- Public BigQuery dataset (`gdelt-bq.gdeltv2.events`, free 1 TB/month query tier) and GEO 2.0 API (7-day window). News-mention based, noisy, geocodes to places named in articles.
- **Use:** Marginal. Possibly as a "media attention" covariate to show that FIRMS sees things the press does not and vice versa. Skip unless time allows.

### 3.4 Bellingcat Civilian Harm in Ukraine (TimeMap) **[VERIFIED]**
- Live JSON: `https://bellingcat-embeds.ams3.cdn.digitaloceanspaces.com/production/ukr/timemap/api.json` (1.1 MB, **2,517 incidents, 2022-02-24 → 2025-07-09**). Fields: id, date, location, latitude, longitude (obscured to ~150 m), description, sources[], impact[], weapon_system[], graphic. Repo https://github.com/bellingcat/ukraine-timemap (LICENSE.md present; type not confirmed — read it). Map at https://ukraine.bellingcat.com .
- **Use:** Rear-area strike validation set: which fraction of verified strikes (date + point) have a FIRMS detection within 1 km/24 h? That is a direct, interviewer-proof measurement of FIRMS sensitivity to missile/drone strikes.

### 3.5 Eyes on Russia (Centre for Information Resilience) **[UNVERIFIED download]**
- Map now at https://www.info-res.org/eyes-on-russia/maps/eyes-on-russia-map/ (eyesonrussia.org redirects). Thousands of geolocated, verified videos/photos since 2022; a Methodology page exists; no download/API visible on the landing page. Sibling projects: **Sudan Witness** (https://www.info-res.org/sudan-witness/, 200), Myanmar Witness, Afghan Witness. CIR has reported 235+ town/village fires in Sudan via FIRMS.
- **Use:** Manual spot checks only unless CIR shares an export on request (worth one email; they have shared with researchers before [UNVERIFIED]).

### 3.6 GeoConfirmed **[VERIFIED API]**
- `GET https://geoconfirmed.org/api/placemark/Ukraine` → 7.1 MB JSON: factions (Ukraine, Ukraine Civilian, Russia, Russia Civilian, North Korea, Belarus, NATO, Neutral, Unknown) → icons → placemarks `{id, date, la, lo, ds}`; **60,783 placemarks, 2014-03-03 → 2026-10-13**. Also `/api/placemark/Israel` (850 KB), `/Syria` (158 KB); `/Sudan` returns an empty list. Per-placemark detail endpoint exists [UNVERIFIED path]. QGIS plugin exists. License/terms not found; community OSINT project; ask before redistributing raw.
- **Use:** The largest open geolocated OSINT event set for Ukraine. Use as a daily point density of "visually confirmed activity" per sector to test whether FIRMS tracks it, and to characterise what FIRMS misses (strikes without sustained fire).

### 3.7 Oryx losses **[VERIFIED repos]**
- Oryx itself is a blog list without coordinates. Scrapers: https://github.com/scarnecchia/oryx_data (daily CSV, auto-updated 22:30 ET) and https://github.com/leedrake5/Russia-Ukraine (Google-sheet pipeline). Fields: date documented, system, status (destroyed/damaged/abandoned/captured), source URL. **No coordinates.** WarSpotting (https://ukr.warspotting.net) geolocates losses by date and place name with an API/exports, but returned 403 to curl [UNVERIFIED terms].
- **Use:** National daily loss counts as a tempo covariate; a dated loss is a lagging indicator (documentation lag). Not geolocated enough for sectors unless WarSpotting cooperates.

### 3.8 Russian strike / incident datasets
- **Petro Ivaniuk "Massive Missile Attacks on Ukraine"** (Kaggle `piterfm`, plus GitHub mirrors used in the airdefense pass; Mirror A ends 2026-06-14). Nightly launched/destroyed by weapon class, UAF claims; region string in `destroyed_details`. Already profiled; the EW-lost reporting break is the side-note finding.
- **Texty.org.ua "Under attack: what and when Russia shelled Ukraine"** (https://texty.org.ua/projects/107577/...): news-derived settlement-level strike points since 2022-02-24, flagged for inaccuracy; no bulk download found; a Kyiv strike database updated to 2026-06-15. [UNVERIFIED export]
- **Airwars Ukraine** (https://airwars.org): civilian-harm incident pages with geolocation and ACLED cross-references; no bulk export [UNVERIFIED].
- **Militarnyi Deep Strike Map** (Ukrainian strikes inside Russia, CSV export advertised); `deepstrikemap.militarnyi.com` did not resolve today. **Novaya Gazeta Europe** interactive map of attacks on Russian territory (Telegram-mined, ~5 % error) [UNVERIFIED export].
- **Economist `firms_update_RU.csv`** (22 MB) and `oblast_activity_by_day.csv` (country, date, oblast, events incl. RUS Kursk/Belgorod) are a ready Russia-side fire series.
- **Use:** Strikes on refineries/depots inside Russia are big, hot, persistent fires — a positive-control class where FIRMS *should* work. A short "FIRMS detection rate by target class" table (refinery vs. depot vs. residential) is a cheap, novel sub-result and feeds the generalisation argument.

---

## 4. Published models and derived products to benchmark against

### 4.1 The Economist war-fire model **[VERIFIED]**
- https://github.com/TheEconomist/the-economist-war-fire-model — code MIT, **data CC BY 4.0**. Method: per 0.1° cell, excess fires vs. a pre-war (2015–21) model; flagged "war fire" if <5 % chance under normal-year model and recurrence within 50 km / 7–180 days; `war_fire_restrictive` drops the 10-day follow-on rule. Updated several times daily by `scripts/000-autoupdater.R`.
- **Files in `output-data/` (sizes bytes):** `ukraine_war_fires.csv` 71,275,035 (per-fire rows with LATITUDE, LONGITUDE, date, ACQ_TIME, pop_density, excess_fire, predicted_fire, war_fire, sustained_excess, war_fire_restrictive, length_of_war_fire_area; rows seen for 2025-08 and 2026-04); `firms_update.csv` 53,146,283; `firms_update_RU.csv` 22,235,408 (VIIRS rows for Russia, NRT); `control_status_of_fires_II.csv` 27,960,840 (lat, lon, date, time, `in_ukraine_held_area`); **`cloud_cover_in_ukraine_by_day.csv`** 85,184 (date, cloud_cover_in_country, cloud_cover_in_east_of_country; 2022-01-01 → 2026-10-12); `strikes_by_location_and_day.csv` (daily fires/war fires split by held area, with 7-day moving averages on non-cloud days); `areas_of_control_daily_summary.csv` (see 2.4); `oblast_activity_by_day.csv`; `dates_of_successfully_acquired_fire_data*.csv`; `nightlights.RDS`; `ave_cloud_cover.csv` (2015–2025, all NA in head/tail — check).
- **Use:** (1) Their `war_fire` label is a published baseline your sector panel can be re-run on: does the result change if you use "war fires" instead of all type-0 fires? (2) Their cloud series is a free covariate (but source unclear — likely derived from the FIRMS/MODIS cloud fraction; document it as theirs). (3) Their `in_ukraine_held_area` gives a side-of-line flag back to 2022. Credit The Economist and Solstad.

### 4.2 Bellingcat 2022 "Scorched Earth" and Small Wars Journal 2026 summary of the Economist tracker
- Narrative prior art already cited in VERDICT. No data beyond FIRMS.

### 4.3 Hall et al. 2021, *Environ. Res. Lett.* 16:064019 (UMD) **[DOC]**
- Ukraine cropland burning: 57 % of VIIRS detections in 2016–17 were pre-planting or post-harvest residue burns; field-level mapping of ~43k fields; MCD64A1 under-counts by 30–63 %. Full text gives the monthly calendar (spring March–April pre-planting; July–September post-harvest). PDF: https://bsosdev1.umd.edu/sites/geog.umd.edu/files/pubs/Hall_2021_Environ._Res._Lett._16_064019.pdf .
- **Use:** The citation that justifies the agricultural-season control and the cropland mask; take their monthly shares as the "normal year" fuel calendar.

---

## 5. Covariates for the blind-spot / coverage product

| Layer | Source and access | Resolution / cadence | License | Use |
|---|---|---|---|---|
| Cloud cover (reanalysis) | ERA5 single levels `tcc` (total cloud cover), hourly, via CDS API (`cdsapi`, free ECMWF account, accept dataset licence) https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels | 0.25°, hourly, 1940→ (5-day lag) | CC BY 4.0 (C3S/ECMWF) | Sample `tcc` at each VIIRS overpass time (≈01:30/13:30 local ± sensor) per cell → "probability a fire was observable" per cell-day. Ukraine+Russia bbox, 2022–26, ~1–2 GB NetCDF. |
| Cloud cover (observed, same satellite) | MODIS `MODIS/061/MOD09GA` + `MYD09GA` `state_1km` bits 0–1 (cloud state) or bit 10 (internal cloud) in GEE; VIIRS `NOAA/VIIRS/001/VNP09GA` `SurfReflect_QF2` cloud bits [UNVERIFIED bit positions] | 1 km / 500 m daily | Public domain | Better than ERA5 because it is the actual look. Daily cloudy-pixel fraction per 0.1° cell; compute in GEE and export CSV. The Economist's `cloud_cover_in_ukraine_by_day.csv` is a national shortcut. |
| Snow cover | MODIS `MOD10A1`/`MYD10A1` NDSI snow cover, GEE | 500 m daily | Public domain | Winter blindness is snow + wet fuel, not just cloud; separate the two in the coverage model. |
| Land cover / fuel | ESA WorldCover 2021 v200 (10 m, CC BY 4.0, 3°×3° COG tiles, ~120 GB global; Ukraine subset ~2 GB) https://worldcover2021.esa.int/download or GEE `ESA/WorldCover/v200`; Copernicus Global Land Cover 100 m v3 (GEE); ESA CCI; Dynamic World (GEE, 10 m near-daily) | 10–100 m | CC BY 4.0 | Cropland / grassland / tree / built-up share per cell; stratify the fire signal and the baseline. |
| Cropland burning calendar | Hall et al. 2021 (above); FAO GIEWS crop calendars [UNVERIFIED URL]; MCD64A1 monthly burned area 2012–21 as empirical calendar | monthly | open | Define "agricultural season" weeks per oblast objectively. |
| Terrain | Copernicus DEM GLO-30 (`s3://copernicus-dem-30m/`, eu-central-1, no account, COG; a few tiles withheld — check Ukraine/Sudan gaps) or SRTM 30 m (GEE `USGS/SRTMGL1_003`, ≤60° N) | 30 m | Copernicus licence / public domain | Slope, ruggedness, tree-line; forest-and-ravine sectors (Serebryanka, Kreminna) are where thermal signal is suppressed by canopy. |
| Population / built-up | GHSL GHS-POP and GHS-BUILT-S (R2023A, 100 m / 1 km, 2020–2025 epochs) https://ghsl.jrc.ec.europa.eu/download.php ; WorldPop constrained 100 m 2020 (CC BY 4.0) https://hub.worldpop.org/ | 100 m | CC BY 4.0 | Urban combat (Bakhmut, Avdiivka, Pokrovsk, Toretsk) burns differently from field combat; also screen out industrial static sources with GHS-BUILT. |
| Roads / rail | OSM via Geofabrik `ukraine-latest.osm.pbf` (880 MB) and `sudan-latest.osm.pbf` (205 MB), ODbL; HOT Export Tool for clipped GeoJSON; ISW `Major_Ukrainian_Railroads`, `Ukrainian_Trunk_Primary_and_Secondary_Roads` feature services | vector | ODbL / ISW | Logistics-node covariate; distance-to-road for Sudan villages. |
| Fortifications | ISW `Russian_Field_Fortifications` (+ `_Polylines`) feature services | vector | ISW copyright | Where defence-in-depth exists, expect attrition and fire without movement. |
| Admin boundaries | HDX COD-AB (Ukraine ADM1–4, Sudan ADM1–3, Myanmar MIMU townships) ; Natural Earth 50m (already on disk; note Crimea coded as Russia) | vector | CC BY / public | Aggregation units for the transfer tests. |
| Night lights | VIIRS DNB monthly `NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG` (GEE), EOG annual V2 | 500 m monthly | public / EOG terms | Economic-activity proxy; Economist uses `nightlights.RDS`. Optional. |

---

## 6. Transfer wars: what exists for the outcome variable

The key structural fact: **no other war has a DeepState.** Outside Ukraine the outcome must be events (ACLED/UCDP), village destruction, or hand-digitised monthly control maps.

### 6.1 Sudan (SAF vs RSF, 2023-04-15 →)
- **FIRMS:** `viirs-snpp_2023/2024/2025_Sudan.csv` [VERIFIED 2024 = 15.7 MB]. Arid, mostly clear sky Oct–May, grass/savanna burning season Nov–Feb in the south; Darfur is sparse fuel, so a village fire stands out — the opposite regime from Ukraine.
- **Control maps:** Sudan War Monitor (https://sudanwarmonitor.com, Substack; periodic hand-drawn control maps built from geolocated combatant video; images, no vectors); Sudans Post monthly "territorial control" articles (images); PolGeoNow (paywalled); Thomas van Linge maps (images, Twitter). **Digitising 12–24 monthly rasters to polygons is 1–2 days of QGIS work and is the only route to an area-change outcome.** [None verified as vector.]
- **Events:** ACLED Sudan (best coverage, weekly, settlement geocoding; HDX curated aggregate exists); UCDP GED 26.1 + Candidate (CC BY).
- **Burned villages:** Yale Humanitarian Research Lab (reports under https://medicine.yale.edu/lab/khoshnood/ — the site moved; the old URL redirects to a 404; find reports via files-profile.medicine.yale.edu links). Yale HRL explicitly uses FIRMS thermal scarring + Planet/Maxar imagery to date village arson (e.g. nine communities west of El Fasher razed 2024-03-31 → 04-15; Tikailat dated 2024-04-14 via VIIRS). HRW used FIRMS for Sirba, West Darfur, 2023-07-27/28. CIR Sudan Witness counted 235+ town/village fires and 50+ repeatedly burned. **No one publishes a CSV of these events; a hand-compiled table of ~100 dated, geolocated village burnings from Yale/HRW/CIR/Dabanga reports is feasible in a day and becomes your Sudan positive-control set.** Historical analogue: Marx (USHMM) Landsat detection of 2,666 destroyed Darfur villages 2002–08.
- **Use in this project:** Test (a) does FIRMS detect documented village burnings (sensitivity) and (b) do FIRMS clusters lead ACLED/UCDP event counts at the locality-week level. Expect FIRMS to work *better* than in Ukraine for detection and *worse* for territory (RSF/SAF control changes are town-centred and sudden).

### 6.2 Myanmar (post-2021 civil war)
- FIRMS Myanmar yearly CSVs [VERIFIED 2024 = 26.5 MB] — but Myanmar has one of the world's highest agricultural/forest burning loads (Feb–Apr dry season), a very hard confounder.
- Control: ISP-Myanmar township-control PDFs (2025–26; "military lost 101 towns, recaptured 22"), Special Advisory Council township assessments [UNVERIFIED download], MIMU township boundaries on HDX (HDX URL I tried 404'd; find via MIMU geonode). Events: ACLED (strong), UCDP.
- **Use:** Only as a hard negative example in the brief ("where the method must fail"), unless time allows.

### 6.3 Sahel (Mali, Burkina Faso, Niger; JNIM/ISSP)
- FIRMS Mali and Burkina_Faso yearly CSVs [VERIFIED 2024]. Massive seasonal savanna burning Nov–Feb; otherwise arid and clear.
- Control: ISW/CTP Sahel AO maps as ArcGIS services (`Salafi_Jihadi_Area_of_Operations_in_the_Sahel__October_2024_WFL1`, `2022_09_16_Sahel_...` found in the ISW org listing) — polygons, dated. ACLED has JNIM/ISSP expansion maps and actor profiles. Events: ACLED, UCDP.
- **Use:** Secondary transfer candidate because ISW/CTP AO polygons exist as vectors (unlike Sudan). Low-intensity insurgency, so expect few fires per event.

### 6.4 Ethiopia (Tigray 2020–22, Amhara 2023 →)
- FIRMS Ethiopia yearly CSV [VERIFIED 2024]. Events: ACLED, UCDP; EPO (Ethiopia Peace Observatory, ACLED-run). Control: none in vector [UNVERIFIED]. Tigray 2020–22 is closed and well-documented; a retrospective test is possible.

### 6.5 Gaza / Israel–Lebanon / Syria
- GeoConfirmed `/api/placemark/Israel` and `/Syria` exist (verified); ISW/CTP has dozens of Gaza/Syria/Lebanon feature services (`AssessedIsraeliControlledTerritory_VIEW`, `Assessed_IDF_Advances_in_Syria_in_the_Past_24_Hours_MDS_view`, Syria faction MDS layers). Dense urban, small AO; FIRMS at 375 m is a poor fit.
- **Use:** Mention as out of scope with a reason (pixel size vs. AO).

---

## 7. Side piece: drone intercept-rate artifact
- Petro Ivaniuk dataset (Kaggle `piterfm/massive-missile-attacks-on-ukraine`; mirrors `hakerdimoha98-source/Missile-attacks-on-Ukraine` to 2026-06-14, `vetalist7/ukraine-attacks-analysis` to 2026-04-19) — already profiled in airdefense/SOURCES.md. Needs a Kaggle account (free) to refresh June–Oct 2026 and to get `missile_models.csv`.
- Cross-checks: KAS Ukraine Air War Monitor monthly figures; CSIS Futures Lab (Atalan & Jensen 2025-02-24); RUSI Iskander commentary; Kiel Ukraine Support Tracker Release 31 (on disk).
- Nothing further to scout; the artifact is in hand.

---

## 8. Licensing summary for a public repo

| Source | Raw redistribution in repo? | Derived aggregates? | Attribution |
|---|---|---|---|
| FIRMS (NASA/LANCE) | Yes | Yes | "NASA FIRMS / LANCE" + NRT disclaimer if NRT |
| UCDP | Yes (CC BY 4.0) | Yes | Davies et al. 2026; Sundberg & Melander 2013 |
| ACLED | **No** | Yes, with attribution | ACLED Terms of Use & Attribution Policy |
| DeepState | **No** (API/content terms; no identical copies) | Yes, with link/logo; email for comfort | "DeepStateMap.live" |
| ISW/CTP ArcGIS | Avoid mirroring; small clipped samples OK with notice | Yes | "ISW and AEI's Critical Threats Project" |
| Economist war-fire | Yes (CC BY 4.0) | Yes | The Economist / Sondre Solstad |
| Bellingcat TimeMap | Check LICENSE.md; link to api.json rather than vendoring | Yes | Bellingcat |
| GeoConfirmed | Not stated; ask | Yes | GeoConfirmed |
| EOG VNF | Account terms; no bulk re-host | Yes | EOG/Payne Institute; Elvidge et al. 2013 |
| ERA5 | Yes (CC BY 4.0) | Yes | C3S/ECMWF, note modifications |
| WorldCover, GHSL, WorldPop, Copernicus DEM | Yes | Yes | CC BY 4.0 / Copernicus licence |
| OSM | Yes (ODbL, share-alike on derived DB) | Yes | "© OpenStreetMap contributors" |
| Maxar/Umbra open | CC BY-NC / CC | n/a (not used) | — |

---

## 9. Size and time budget for the full pull

| Pull | Size | Wall time |
|---|---|---|
| FIRMS yearly CSV: Ukraine 2012–25, Russia 2022–25, Sudan 2022–25, Mali/BF/Myanmar/Ethiopia 2023–25 | ~500 MB | 20 min |
| FIRMS API: 3 VIIRS sources, Ukraine+Russia-border bbox, 2022–2026 | ~150 MB | 1–2 h scripted |
| DeepState API history 1,785 snapshots | ~0.5–1 GB | 1–2 h, polite 1 req/s |
| ISW ArcGIS: full-length timelapse (7,540 recs ×4 layers) + 2025–26 monthly services | ~200 MB GeoJSON | 1 h |
| Economist repo clone (output-data) | ~250 MB | 5 min |
| ERA5 tcc hourly, bbox 22–42 E / 44–53 N, 2022–26 | ~1.5 GB NetCDF (or sample 2 timesteps/day → 150 MB) | CDS queue, hours |
| WorldCover Ukraine tiles | ~2 GB | 30 min |
| Copernicus DEM tiles Ukraine east | ~1 GB | 20 min |
| UCDP GED + Candidate | 41 MB | 1 min |
| ACLED Ukraine + Sudan exports | ~100 MB | after registration |
| GeoConfirmed + Bellingcat JSON | 8 MB | 1 min |
| OSM Ukraine/Sudan PBF | 1.1 GB | 10 min |

Total on disk ≈ 8–10 GB; everything fits a laptop. Zero cost.

---

## 10. Things I could not verify (flag list)
1. ACLED's current academic/student tier label and whether API access is granted to students without a request (docs page did not render; 2021 FAQ vs current table disagree).
2. Whether FIRMS `VIIRS_NOAA20_SP` covers back to 2018 via API (needs MAP_KEY to query `/api/data_availability`).
3. Exact bit positions for cloud in VIIRS VNP09GA `SurfReflect_QF2`; MOD09GA state bits are documented.
4. Bellingcat `LICENSE.md` type and whether it covers the data as well as code.
5. GeoConfirmed terms of use and the per-placemark detail endpoint.
6. ISW's written reuse terms for ArcGIS layers (copyright notice only, no licence text found).
7. Existence of any CEMS Rapid Mapping activation for the Ukraine war or Sudan 2023–26.
8. UAControlMap content, method and any export (site up, not inspected).
9. WarSpotting API/terms (403 to curl); Militarnyi Deep Strike Map (DNS failure today); Texty bulk export.
10. Yale HRL report index location after the site migration (old lab URL → 404).
11. Scientific Reports DOI for the Dingemanse/Zhizhin/Cerra Nightfire paper (inferred 10.1038/s41598-026-42172-0 from the article ID).
12. Current Planet NICFI/Education programme terms; Capella open data contents.
13. Whether the Economist `ave_cloud_cover.csv` is populated (head and tail rows were NA).
14. MIMU Myanmar township boundary HDX URL (the one I tried 404'd) and SAC-M township control downloads.

Web-search budget for this session ran out after ~45 searches; the items above were left to direct URL probes, which is why several remain open.
