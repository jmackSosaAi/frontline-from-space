# Post-tag pull: what to fetch the moment `prereg-v1` exists

Drafted 2026-10-21. Nothing on this list has been downloaded. Every URL and size below was checked with a HEAD request or an API file listing on 2026-10-21; no data bodies were fetched.
Script: `scripts/fetch_post_tag.py` (drafted, **not run**). Manifest part: `data/manifest_parts/post_tag.json`.

## 0. Preconditions (the script checks 0.1–0.3 and stops if any fails)

1. `PREREG.md` is committed and tagged `prereg-v1`, and the working-tree `PREREG.md` matches the tag. Any later change goes in `DEVIATIONS.md`.
2. Registered on OSF (https://osf.io/3whtz/): the script asks the OSF API for at least one registration, using `OSF_TOKEN` from `.env`. `--osf-ok` overrides this if the API call fails.
3. `FIRMS_MAP_KEY` works (`mapkey_status` returns a transaction limit).
4. **Disclose before tagging:** The Economist repo snapshot in `data/raw/economist/keep/` (commit `8b431f9`, fetched 2026-10-14, already in `MANIFEST.json`) contains `ukraine_war_fires.csv`, `control_status_of_fires_II.csv`, `areas_of_control_daily_summary.csv` and `war_fires_by_ADM3.csv`, which cover C1 dates. Before the tag, add a sentence to PREREG §2 saying these were on disk and whether they were opened. The post-tag step below fetches fresh copies pinned to a commit.

## 1. Order of pulls

H7 forces this order. `predictions/transfer_v1.json` (predicted recall for Karabakh and Sudan from the H2 model fit on Ukraine) has to be committed **before** any T1/T2 data arrives. Ukraine comes first, then the model fit, then T1/T2.

| # | Dataset | URL / endpoint | Method | Expected size | Serves |
|---|---|---|---|---|---|
| 1 | **VIINA control 2022, 2023, 2024** (C1 outcome) + **2026** | `https://media.githubusercontent.com/media/zhukovyuri/VIINA/main/Data/control_latest_{2022,2023,2024,2026}.zip` (the GitHub raw URLs are LFS pointers) | script, HTTP GET | 28.2 + 32.1 + 32.2 + 27.3 = **~120 MB** | Outcome and control line for H4, H5, H6/H6b, H9–H12; robustness 5 (`status_dsm/isw/wiki`). 2026 extends E for H13 |
| 2 | **FIRMS API, Ukraine bbox** `22,44,41,53`: `VIIRS_SNPP_SP`, `VIIRS_NOAA20_SP` 2022-02-24 → SP end (2026-06-30 today); `VIIRS_NOAA21_SP` 2023-03-01 → SP end; `VIIRS_{SNPP,NOAA20,NOAA21}_NRT` from SP end+1 → today | `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{bbox}/5/{start}` | script; 5-day chunks; SP/NRT boundaries read at run time from `/api/data_availability/csv/{KEY}/ALL`; throttled under 5,000 transactions per 10 min using `mapkey_status` | ~950 calls; **~150–300 MB** | H1, H2 (fires matched to V events), H3 (S-NPP vs NOAA-20 paired looks), H4, H5, H6/H6b, H8 (constellation without S-NPP), H9–H12, H14 re-check; Kyiv fires for H12 |
| 3 | **FIRMS yearly country CSVs, Ukraine** S-NPP + NOAA-20, 2022–2025 (NOAA-21 has no yearly files; 404) | `https://firms.modaps.eosdis.nasa.gov/data/country/{viirs-snpp,viirs-jpss1}/{Y}/{sensor}_{Y}_Ukraine.csv` | script, no key | 8 files, **~35 MB** (2022: 4.05 / 4.78 MB) | Completeness check on #2: row counts per sensor-year after clipping to the border. No new hypothesis |
| 4 | **Economist war-fire files**, pinned to the commit current at pull time | `https://raw.githubusercontent.com/TheEconomist/the-economist-war-fire-model/{sha}/output-data/` + `ukraine_war_fires.csv` (71.3 MB), `control_status_of_fires_II.csv` (28.0), `cloud_cover_in_ukraine_by_day.csv` (0.09), `areas_of_control_daily_summary.csv` (0.66), `firms_update_RU.csv` (22.2). Branch is `master` (`main` gives 404) | script; single files, never a clone; commit SHA resolved through the GitHub API | **~122 MB** | Robustness 5 (national ISW area series as a 2022–23 check); `war_fire` label as a benchmark classifier (exploratory); cloud series compared against ERA5 opportunity (H4 gate); `in_ukraine_held_area` as a check on side of line (H10); RU fires as a check on #6 |
| 5a | **Ukraine Fire Perimeters 2022** (Zibtsev et al.) | `https://zenodo.org/records/8298835`, 6 shapefile parts via `/api/records/8298835/files/.../content` | script | **~32 MB** | H2 (size truth from Sentinel-2 burned area compared with FRP, plus land cover), H10 (FRP vs. area, `occupied` flag), H5. Cannot measure recall |
| 5b | **Ukraine Fire Perimeters 2023** | `https://zenodo.org/records/10514571` (6 parts) | script | **~12.6 MB** | Same as 5a; `buff30_new` front-buffer flag for H10/H5 |
| 5c | **Project Owl UAControlMap backups** | `https://github.com/owlmaps/UAControlMapBackups` (branch `master`, `{YYYY}/{YYMMDD_HHMM}.kmz`, 2022-12-08 → today) | script; folders listed through the GitHub contents API; **default: the last file of each ISO week** (~200 files); `--owl-daily` gets all ~1,400 | weekly **~350 MB** (daily ~2.5 GB) | Robustness 5: a fourth independent control source. No licence, so do not redistribute and ask Project Owl before publishing derivatives |
| 5d | **Matsala et al. war fire-risk ZIP** | `https://zenodo.org/records/8132956` → `ZENODO.zip` | script | **162 MB** | H2 covariate benchmark (forest fuel, distance to front); exploratory |
| 5e | **Texty Mykolaiv shelling** | `https://raw.githubusercontent.com/texty/project_Mykolaiv_shelling_web/main/` + `data/shelling_points.geojson`, `data/shelling_triangles.geojson`, `data/shelling_triangles_2.geojson`, `artilerry position.geojson`, `front_line.geojson` (the last two sit at repo root, not in `data/`) | script | **~0.18 MB** | Small 2022 V-set check (H1). Low priority. No licence |
| 6a | **FIRMS API, western-Russia bbox** `27,41,60,64` (Ust-Luga/Kirishi in the west, Ufa/Orsk in the east, Ukhta in the north), same sources and dates as #2 | as #2 | script | ~950 calls; **~200–400 MB** | H13 (deep strikes on depots/refineries, E period), H10 (Russian-held side incl. Kursk/Belgorod), H5 |
| 6b | **FIRMS yearly country CSVs, Russian_Federation** S-NPP + NOAA-20, 2022–2025 | `.../data/country/{sensor}/{Y}/{sensor}_{Y}_Russian_Federation.csv` | script, no key | 8 files, **~400 MB** (S-NPP 2022 51.4 MB, 2025 47.3 MB) | Russia country coverage outside the bbox; check on 6a |
| — | **STOP.** Fit H2 on V-train, write `predictions/transfer_v1.json`, commit it. | | by hand | | H7 |
| 7 | **T1: FIRMS Azerbaijan + Armenia 2020**, S-NPP | `.../viirs-snpp/2020/viirs-snpp_2020_{Azerbaijan,Armenia}.csv` | script; refuses until transfer_v1.json is committed | 0.41 + 0.06 = **~0.46 MB** | H7 (Karabakh) |
| 8 | **T2: FIRMS Sudan 2023 → today**, S-NPP | yearly `viirs-snpp_{2023,2024,2025}_Sudan.csv`; 2026 through the API area endpoint, Sudan bbox `21.8,8.6,38.7,22.3` (SP then NRT) | script; same transfer gate | **~58 MB** yearly + ~60 calls / ~15 MB | H7 (Darfur/Kordofan, T2 window ends 2025-12-31; 2026 is exploratory) |
| 9 | **UCDP GED 26.1** | `https://ucdp.uu.se/downloads/ged/ged261-csv.zip` | script; same transfer gate | **39.1 MB** | H7 (Sudan events, the recall denominator) |
| 10 | **ACLED Ukraine + Russia** | acleddata.com Data Export Tool | **browser, Jackson's logged-in session.** Countries Ukraine + Russia, 2022-02-24 → latest available (his tier ends Oct 2025), all event types, CSV. Save to `data/raw/acled/`, then `python3 -I scripts/fetch_post_tag.py --register-acled data/raw/acled/<file>.csv` to hash it and add it to the manifest | ~100–200 MB | V extension for H1/H2 (dated strikes and shelling), timing checks for H12/H13. **Do not redistribute the raw data** (ACLED terms) |
|    | *Done 2026-10-26:* Partner Tier trial (no lag) → 2022-02-24 → 2025-12-31, 277,536 events (Ukraine 235,270; Russia 42,266; 20,361 after 2025-10-17). Pulled in 8 half-year in-page chunks merged into one CSV (one 160 MB request timed out). Sudan / Armenia / Azerbaijan return no results on this account (trial appears scoped to Ukraine + Russia); H7 stays on UCDP. | | | | |

**Total:** about 1.8–2.3 GB with weekly Owl files. Calls to the FIRMS API: about 1,950. At 5,000 transactions per 10 minutes this takes 1–3 h of wall time, and the script resumes where it stopped.

## 2. Rules the script follows

- Idempotent. A file that is on disk and listed in `post_tag.json` is skipped. NRT chunks that end within 3 days of today are fetched again on each run, because they are still filling.
- Download order follows the table, and each step writes its own manifest records, so the times show the T1/T2 data arrived after `transfer_v1.json`.
- `MAP_KEY` never appears in the manifest (written as `{MAP_KEY}`), and no key is printed.
- Each file is checked for HTTP 200, file signature (`latitude` header / `PK` / JSON / shapefile magic), and FIRMS chunk dates inside the window. There is a 5 GB cap.
- Each step can be run alone (`--only viina,firms_ua`). `--dry-run` prints the plan without any network calls.

## 3. Not in this pull

- World Bank/UMD/JRC village-council cropland damage package. Gated for the same reasons as in `fetch_sweep.py`. Decide after the tag whether it belongs in robustness. The robustness list is fixed, so adding it would make it exploratory.
- Perimeters for 2024/25 (not on Zenodo). Ask Zibtsev's group.
- Texty "Under attack" national map (no export).
