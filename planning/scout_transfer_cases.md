# Scout: transfer cases for "Front line from space"

Written 2026-10-13/14. Scope: for each candidate second/third war, can the Ukraine method (FIRMS front-band density, sector panel, lead-lag against a control/event series, blind-spot map) be tested there, and what would the test tell us about the Ukraine confounders (season, area of operations, war type)?

Ground truth I started from: `Conflict_Data_Feasibility/frontline/VERDICT.md`, `FIRST_PASS.md`, `SOURCES.md`. Key facts carried over: FIRMS country CSVs need no key; the Ukraine front band is 5–17x denser than the rear band in every month; the sensor is blind Nov–Feb (44% of sector-weeks with zero front detections); the lead-lag result is borderline (p≈0.05) and fragile; DeepState latency is itself a confounder.

Verification status: anything marked **[verified]** I fetched today (HTTP status, file size, page text). **[not verified]** means I could not reach the page or confirm the claim; treat as a lead. The web-search budget ran out part-way through, so several leads (Sudan War Monitor GIS, Carter Center data access, OCHA Gaza zone polygons, ISP-Myanmar township control, Libya/Sahel control maps) rest on one search pass plus direct fetches.

---

## 0. Two things that change the whole question

**1. There are two different "FIRMS signals" in modern wars, and only one of them is what we measured in Ukraine.**
- *Combat-fire signal* (Ukraine): vegetation and structures ignited by artillery, drones, FPV strikes along a continuous line of contact. Dense, linear, seasonal, confounded by crop burning.
- *Arson signal* (Darfur, Sagaing, Rakhine 2017, Tigray western corridor): deliberate burning of villages by a raiding force. Point-like, often outside the agricultural burning season, and already used operationally by Yale HRL, Sudan Witness/CIR, Myanmar Witness and HRW **[verified: Yale HRL Kutum and El Fasher reports credit FIRMS; CIR Murnei/Tawilah report; HRW Thantlang 2021]**.
- A transfer test that ignores this will "fail" for the wrong reason. The honest framing is: *does front-band fire density track the line of contact in a war that has a line of contact?* For raiding wars the question becomes *does FIRMS flag attacks on settlements, and with what false-positive rate against seasonal burning?* Both are worth doing, but they are different hypotheses and must be pre-registered separately.

**2. Almost no war outside Ukraine has a daily territorial-control polygon series.** DeepState is unusual. For most candidates the outcome variable must be an event series (UCDP GED/Candidate, ACLED) or a settlement-level control list, not km² of area change. That makes the transfer test "fires vs. events" or "fires vs. settlement flips", not "fires vs. area". The one partial exception is Yemen (ACAPS admin-2 control snapshots, ~monthly) and the within-war Ukraine 2022 case (VIINA settlement-day control from 24 Feb 2022, DeepState from 3 Apr 2022).

---

## 1. Shared data sources (used by several cases)

| Source | What | Access / license | Cadence | Notes |
|---|---|---|---|---|
| NASA FIRMS country yearly CSVs | VIIRS S-NPP 375 m detections per country per year, 2012– | No key. URL pattern `https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/<year>/viirs-snpp_<year>_<Country>.csv` | Yearly archive; current year only via API with free MAP_KEY | File sizes checked today, see each case. Country naming: `Democratic_Republic_of_the_Congo`, `Palestine`, `Burkina_Faso`, `Russian_Federation` **[verified 200]**; `Congo_DRC`, `State_of_Palestine` **[404]**. |
| FIRMS API (MAP_KEY) | `area`, `data_availability`, `missing_data`, `kml_fire_footprints` endpoints; `country` endpoint currently listed as unavailable **[verified on api page]** | Free key | NRT | Adds NOAA-20/21 VIIRS (3x overpasses). Transaction limits not confirmed from the page; check `data_availability` before planning. |
| UCDP GED 26.1 | Geocoded fatal events 1989–2025, village-level, daily | CSV/XLSX, CC BY 4.0 **[verified]** | Annual | `https://ucdp.uu.se/downloads/` ; ged251/ged261 zips returned 200 in the feasibility pass (29/39 MB). |
| UCDP Candidate 26.0.x | Same coding, monthly release, "not more than a month's lag globally" **[verified]** | CC BY 4.0 | Monthly | Covers 2026 to the current month; the natural outcome series for any case post-2025. |
| ACLED | Event data incl. battles, strikes, territorial-change-flagged events | Free account; Civil Society/Academic tier = unlimited downloads **[verified via API docs summary]**; redistribution and AI/ML use restricted (Content Usage Terms updated 8 Jul 2025) **[verified]** | Weekly | HDX mirrors are only monthly admin aggregates (`*_HRP_political_violence_events_and_fatalities_by_month-year.xlsx`) **[verified]**; event-level needs the key. Do not republish raw ACLED rows in the public repo; publish derived indices only. |
| HDX (data.humdata.org) | Catalog; CKAN API works without login (`/api/3/action/package_search`) **[verified]** | Varies per dataset | — | Web pages returned 403 to WebFetch; use the API. |
| VIINA 2.0 (Zhukov & Ayers, Harvard) | Ukraine events + settlement-level daily control from 24 Feb 2022; `control_latest_YYYY.zip` (GeoNames) and `kontrol_latest_YYYY.zip` (KATOTTH), with `gn_UA_tess.geojson` tessellation | ODbL **[verified]** | Daily | Control = majority vote of Wikipedia, Wikipedia+VIINA boost, DeepState; ties to DeepState. `https://github.com/zhukovyuri/VIINA` |
| DeepState history API | 1,785 snapshots 2022-04-03 → 2026-10-13 (from feasibility index) **[verified index start 03.04.2022]** | Unstated license; public endpoint | Daily-ish | `https://deepstatemap.live/api/history/public`, `/api/history/<id>/geojson`. Mixed KML layers; filter by style. |
| The Economist war-fire model | `output-data/ukraine_fires.csv`, `ukraine_war_fires.csv`; 0.1° cells, excess-fire flag at <5% chance in a normal year; sustained-excess rule | Code MIT, data CC BY 4.0 **[verified]** | Autoupdater | Ukraine only **[verified]**. Reuse the *method* (pre-war per-cell baseline) in other countries; nobody has published that transfer. |
| Cloud climatology | MODIS Aqua/Terra monthly cloud fraction (MOD08_M3/MYD08_M3, 1°) via NASA Earthdata (free login); or ERA5 monthly total cloud cover via Copernicus CDS (free) | Open | Monthly | NASA NEO viewer URL now redirects to science.nasa.gov **[verified redirect]**; use Earthdata/LAADS or Giovanni instead. Cheapest proxy of all: FIRMS `missing_data` plus per-cell "days with any detection within 200 km" as an observed-coverage index. |

Fire-regime and cloud numbers below are from standard climatology (GFED/MODIS burned-area literature, Köppen/monsoon timing). I did **not** re-verify them today; the first task in any chosen case is to compute them from the FIRMS country file itself (monthly detection counts 2012–present, which is also the pre-war baseline).

---

## 2. Case cards

Scoring: each 0–3. **Outcome series** (is there a usable control/event time series), **FIRMS signal** (expected size and cleanliness of a war signal), **Confounder leverage** (does it test season / AO / war-type differently from Ukraine), **Cost** (3 = cheap). Total out of 12.

### 2.1 Sudan 2023–

- **Outcome series.** No GIS territorial-control series exists in public. Control maps are images: Sudan War Monitor (Substack, geolocated combatant video; e.g. 31 May 2024 map) **[verified page, no GIS]**, PolGeoNow (4 editions Oct 2023–Jun 2024, two paywalled, image only) **[verified]**, Sudans Post (monthly 2025–26 maps, image) **[not verified beyond search snippets]**, EUAA country guidance text. Event series: UCDP GED/Candidate (CC BY) and ACLED (key). ACLED on HDX is monthly admin aggregates only **[verified]**.
- **FIRMS file.** `viirs-snpp_2024_Sudan.csv` = 15.7 MB **[verified 200]**, roughly 150–200k rows.
- **Fire regime.** Arid north (Khartoum, River Nile) with almost no vegetation fuel; Sahelian/Sudanian savanna in Darfur, Kordofan, Blue Nile, Gedaref with a very heavy dry-season burning peak Nov–Feb (pastoral and agricultural burning). So the natural fire season is the *opposite* of Ukraine's (Jul–Sep). Khartoum/Omdurman/Wad Madani fighting produced urban structure fires visible to VIIRS but no vegetation signal.
- **Cloud.** Khartoum ~nil cloud Oct–May; Darfur/Kordofan wet season Jun–Sep (ITCZ) brings heavy afternoon cloud; El Fasher siege (Apr 2024–Oct 2025) spans both regimes.
- **War type.** Mixed: siege/attrition (El Fasher, Khartoum 2023–25, Omdurman), maneuver (SAF retakes Gezira Jan–Mar 2025, Khartoum Mar 2025; RSF sweeps Darfur late 2023), and raiding (RSF arson against villages in Darfur, Kordofan). This is the richest menu of war types of any candidate.
- **Expected FIRMS signal.** Two components: (a) *arson* — already proven detectable by Yale HRL and CIR using FIRMS; (b) *front-band* fires around sieges — unknown, probably weak outside the savanna belt because there is no fuel. The clean test: build a village/settlement list (HDX/OCHA Sudan settlements, GeoNames), compute per-settlement anomalous detections against the 2012–2022 same-week baseline, and compare with ACLED/UCDP "attack on village" events. That is a precision/recall test, not a lead-lag test.
- **Confounders tested.** Season (burning season inverted vs Ukraine), AO (arid vs steppe), war type (raiding + siege). It cannot test "fires lead territorial change" because there is no area series; but it can test "fires lead *reported* events", which also measures reporting latency in a low-coverage information environment (communications blackouts in Darfur) — a genuinely useful second finding.
- **Scores.** Outcome 1, Signal 3 (arson component), Confounders 3, Cost 2. **Total 9.**

### 2.2 Sahel (Mali, Burkina Faso, Niger) 2012–

- **Outcome series.** No control maps in GIS. JNIM/ISSP "control" is zonal and contested; the best public statements are percentage estimates (e.g. "at least 40% of Burkina Faso" via Long War Journal/ACLED) **[search snippet only]**. Event series: ACLED (strong Sahel coverage), UCDP GED/Candidate.
- **FIRMS files.** `2024_Mali` 13.7 MB, `2024_Burkina_Faso` 7.7 MB **[verified 200]**. Niger file not checked.
- **Fire regime.** Among the heaviest burning regions on Earth (Sudanian savanna burning Oct–Apr, peaking Nov–Jan). The agricultural/pastoral fire count will swamp any combat signal by two or three orders of magnitude.
- **Cloud.** Dry season essentially clear; wet season Jun–Sep cloudy. Combat is year-round with a wet-season lull.
- **War type.** Pure raiding/insurgency: ambushes, IEDs, sieges of towns (Djibo), massacres and village burnings. No line of contact.
- **Expected FIRMS signal.** Village arson is detectable in principle but sits inside the world's busiest fire season. Detection would require a very good per-village baseline and still have a high false-positive rate. The Ukraine front-band method has no object to measure.
- **Confounders tested.** Season (strongly), war type (raiding). But this is a *negative control* more than a transfer: it tells us where the method should fail. Useful as a one-figure appendix ("here is what a war looks like when the fire season owns the signal"), not as the primary case.
- **Scores.** Outcome 1, Signal 1, Confounders 2, Cost 2. **Total 6.**

### 2.3 Myanmar 2021–

- **Outcome series.** No downloadable township-control time series found. ISP-Myanmar publishes township control analyses and "Data Matters" charts (e.g. 105,799 houses destroyed Feb 2021–Oct 2024, Sagaing 63,655) **[verified page; no download offered]**; `ispmyanmar.com/mapping/` returned 404 **[verified]**. HDX has a single British Red Cross "Areas of Control" GeoTIFF for 8 Mar 2025 (CC0, adapted from Wikipedia) **[verified]**. Data for Myanmar (D4M) publishes cumulative house-burning counts by region (112,485 through Dec 2024; 108,645 attributed to junta/allies) **[search snippets; dataset download not found]**. Myanmar Witness uses FIRMS to corroborate arson claims. Event series: ACLED (strong), UCDP GED (on HDX as "Myanmar – Data on Conflict Events", CC BY-IGO, through 2024) **[verified]**.
- **FIRMS file.** `2024_Myanmar` 26.5 MB **[verified 200]** — bigger than Sudan's; Myanmar burns a lot.
- **Fire regime.** Slash-and-burn (taungya) and field clearing Feb–Apr, nationwide, extremely dense; monsoon May–Oct with few fires. The Rohingya paper (Ren et al. 2020, arXiv:2003.08874) defined the agricultural season as Nov–May and the non-agricultural window as Jun–Oct, and found 167 detections in Jun–Oct 2017 against a 2012–2016 mean of 29.75 (2.7 sd) **[verified from PDF]**. That is the template: anomalous detections in the off-season are the signal.
- **Cloud.** Monsoon May–Oct is among the cloudiest regimes on Earth (Sagaing, Chin, Rakhine): the off-season when arson would be visible is also when the sky is closed. Nov–Feb is clear and relatively fire-free: the best window.
- **War type.** Raiding plus positional siege (Lashio, Myawaddy, Loikaw, Rakhine towns), plus the Oct 2023 "Operation 1027" maneuver phase in northern Shan. No continuous front.
- **Expected FIRMS signal.** Arson signal strong in Nov–Feb (HRW's Thantlang detections, 29–30 Oct 2021, day and night **[verified]**), buried in Feb–Apr, invisible in monsoon. Front-band method does not apply.
- **Confounders tested.** Season (a monsoon regime with a fire season out of phase with Ukraine), AO (tropical/forest/paddy), war type (raiding + sieges). It is the best case for building a *blind-spot calendar* that is genuinely different from Ukraine's.
- **Scores.** Outcome 1 (D4M counts are regional, not geocoded; ACLED carries most weight), Signal 2, Confounders 3, Cost 2. **Total 8.**

### 2.4 Ethiopia / Tigray 2020–22

- **Outcome series.** None in GIS. Event series: ACLED (Ethiopia Peace Observatory) and UCDP GED. Severe under-reporting because of the communications blackout: a known weakness that FIRMS can partly address (this is the one case where "satellite sees what reporters cannot" is testable, because post-war reporting back-filled many events).
- **FIRMS file.** `2021_Ethiopia` 19.3 MB **[verified 200]**.
- **Fire regime.** Western Tigray/Kafta-Sheraro burns seasonally; Bellingcat notes seasonal fires there Jun–Sep **[verified]**; the Substack analysis found Nov detections in a Tigray box of 656/418/815/1,461/690/726/838 for 2014–2020, with 2020 the highest except the 2017 drought year **[verified]**. Highlands have thin fuel. Bellingcat documented a hotspot sequence along the Shiraro–Shire–Aksum road in Nov 2020 matching ENDF advances **[verified]** — the only published "fires track an advancing front" example outside Ukraine.
- **Cloud.** Kiremt rains Jun–Sep heavy cloud; Oct–May largely clear. The war's main phases (Nov 2020 offensive, Jun–Jul 2021 TDF counteroffensive, Aug–Nov 2022 final offensive) straddle both.
- **War type.** Nov 2020 = maneuver (fast ENDF/Eritrean advance along roads); 2021–22 = maneuver swings and then attrition in the north (Shire, Adigrat axes).
- **Expected FIRMS signal.** Moderate: road-following fire sequences in the dry months, arson of towns; little in the rainy season. Good for a *qualitative* front-tracking test against dated ISW-style narratives, but the outcome series is thin.
- **Confounders tested.** War type (maneuver) and AO (highland, arid-savanna mix). Season less cleanly than Myanmar.
- **Scores.** Outcome 1, Signal 2, Confounders 2, Cost 2. **Total 7.**

### 2.5 Nagorno-Karabakh 2020 (and 2023)

- **Outcome series.** No polygon series, but a very good *settlement capture list with dates*: Azerbaijani MoD and presidential announcements day by day, compiled on Wikipedia's Timeline (e.g. 3 Oct Suqovuşan/Talış; 4 Oct Jabrayil city; 9 Oct Hadrut; 18 Oct Fuzuli city; 20 Oct Zangilan city; 25–26 Oct Qubadli; 7–8 Nov Shusha; 9 Nov "48 more villages"; ceasefire 10 Nov 01:00) **[verified]**. Announcement dates lag or lead actual capture; Armenian confirmations exist for some. Geocode via GeoNames. 2023 (19–20 Sep) is one day long and gives nothing.
- **FIRMS files.** `2020_Azerbaijan` 406 KB, `2020_Armenia` 55 KB, `2012_Azerbaijan` 377 KB **[verified 200]** — tiny, trivially processable, with a full 2012–2019 baseline.
- **Fire regime.** Mountain forest and some cropland; autumn is a low-fire season. CEOBS (Darbyshire 2021) counted 447 VIIRS detections 26 Oct–4 Nov 2020 (peak 31 Oct) versus 203 for all of 2012–2019 combined and a previous single-year max of 72; ~102 km² moderate/high-severity burn; fires anti-correlated with fire-weather danger, concluding military causation **[verified]**.
- **Cloud.** Caucasus autumn: variable, with frequent frontal cloud; the fire pulse occurred in a late-October dry spell.
- **War type.** 44-day maneuver war with drones and artillery along a moving front: the closest open-data analogue to "what Ukraine 2022 looked like", and the opposite of Ukraine 2024–25 attrition.
- **Expected FIRMS signal.** Strong anomaly but *concentrated in the last 10 days*, after most of the southern advance (Jabrayil, Fuzuli, Zangilan were taken 4–20 Oct with few fires). That is itself an important result: in a fast maneuver war, fires *followed* the Shusha/Lachin fighting rather than leading the southern sweep. Sample size (one war, ~6 weeks, ~450 war-fires) is too small for a panel regression but ideal for an event-study figure.
- **Confounders tested.** War type (maneuver), season (autumn forest, low ag-burning), AO (mountains). It cannot test seasonality across a year.
- **Scores.** Outcome 2, Signal 3, Confounders 2, Cost 3. **Total 10.**

### 2.6 Gaza 2023–

- **Outcome series.** OCHA publishes "militarized zones and displacement orders" geodata (HRW cites OCHA data as of 23 Jul 2025, 87.8% of the Strip under orders or militarized zones) **[search snippets]**, but I could not find a public download: HDX search returned UNOSAT damage geodatabases (CC BY-SA, e.g. 11 Oct 2025 CDA) **[verified]** and no zone polygons; `ochaopt.org/data` lists tools but no Gaza zone layer **[verified]**. The IDF "orange line" maps were sent to aid groups, not published. Event series: ACLED; UCDP.
- **FIRMS file.** `2024_Palestine` 42 KB and `2024_Israel` 136 KB **[verified 200]** — a few hundred detections in total. The Strip is ~365 km², i.e. about 2,600 VIIRS pixels; dense urban structure fires do register (Sentinel/VIIRS imagery of Gaza fires was widely shared), but there is almost no vegetation and the FIRMS "type" field will be ambiguous.
- **Fire regime.** Mediterranean, negligible wildland fuel; a few crop/stubble fires in the buffer zone May–Jun.
- **Cloud.** Clear May–Oct; winter rain Nov–Mar with moderate cloud.
- **War type.** Urban clearance and siege; territorial "control" is an IDF-defined line, not a contested front in the Ukraine sense.
- **Expected FIRMS signal.** Weak and structurally different (building fires, not vegetation). Damage assessment is far better done with UNOSAT/Sentinel-1 than with FIRMS. Not a good transfer case; worth one paragraph as a *fuel-limited* blind spot.
- **Scores.** Outcome 1, Signal 1, Confounders 1 (fuel), Cost 3. **Total 6.**

### 2.7 Syria (phases: 2017–19 ISIS collapse; 2019–20 Idlib; Dec 2024 HTS offensive)

- **Outcome series.** The best in the Middle East, but access is unconfirmed: ACLED's monthly sub-district (272 units) control/contestation coding from 2017 **[verified method page; download not confirmed]**; Carter Center "Exploring Historical Control" viewer, 8,099 localities since 2014 **[verified viewer; no download found]**; the Wikimedia Commons `Syrian_Civil_War_map.svg` has a long revision history based on Liveuamap **[verified exists; revision count and license not read]**; Liveuamap itself is paywalled for history.
- **FIRMS file.** `2024_Syria` 1.2 MB **[verified 200]**.
- **Fire regime.** Arid steppe; cropland burning May–Jun in Hasakah/Raqqa/Deir ez-Zor (the 2019 wheat-field fires during the ISIS insurgency are the textbook case of deliberate crop burning as a weapon — **[not re-verified today]**). Idlib olive/forest fires in summer.
- **Cloud.** Very clear May–Oct; winter cloud Nov–Mar moderate.
- **War type.** Dec 2024: an 11-day maneuver collapse (Aleppo 29 Nov → Damascus 8 Dec) in the dead of the no-fire season; 2017–19: maneuver against ISIS in open desert; 2019–20 Idlib: attrition with heavy airstrikes.
- **Expected FIRMS signal.** The Dec 2024 offensive likely shows almost nothing (winter, fast, little artillery prep): a clean *null in a maneuver war* that would sharpen the Ukraine interpretation. The Idlib attrition phase likely shows strong summer fires. If ACLED sub-district control is downloadable, Syria 2017–20 gives a monthly panel of 272 units × 48 months with a control outcome — the only candidate besides Yemen with that.
- **Confounders tested.** War type (maneuver vs attrition inside one country), season, AO (arid). Rich, if the control data is reachable.
- **Scores.** Outcome 2 (conditional), Signal 2, Confounders 3, Cost 2. **Total 9 (conditional on ACLED/Carter access; 6 without).**

### 2.8 Yemen 2015–22 (and Red Sea phase 2023–)

- **Outcome series.** ACAPS "Yemen: Areas of control" on HDX: 72 shapefile snapshots from 11 Feb 2021 to 8 Apr 2026, admin-2 PCODED, CC BY **[verified via HDX API]** — about one per month on average (irregular). ACLED also publishes a district-level control methodology (Sulz & Roy, Aug 2021) **[verified]**. So Yemen *does* have a reproducible control series, but it starts in 2021, after the most mobile phases (Hodeidah 2018, Marib 2020–21 partly).
- **FIRMS file.** `2024_Yemen` 239 KB **[verified 200]** — very few detections.
- **Fire regime.** Hyper-arid; only highland terrace agriculture and qat; vegetation fire signal essentially absent.
- **Cloud.** Clear most of the year; highland monsoon cloud Jul–Aug.
- **War type.** Positional attrition with airstrikes (Marib front 2020–21), then frozen since the Apr 2022 truce.
- **Expected FIRMS signal.** Near zero. Yemen is the *fuel-limited null*: a control series exists, a war existed, and FIRMS should see almost nothing. That is a useful one-figure appendix, not a case.
- **Scores.** Outcome 2, Signal 0, Confounders 1, Cost 3. **Total 6.**

### 2.9 DRC / M23 2022–

- **Outcome series.** Kivu Security Tracker events are integrated into ACLED only through Nov 2023; ACLED says it "has been unable to identify a suitable source to fill this gap" **[verified]**. No control polygons found; Critical Threats Africa File gives dated narrative (lines frozen on RN5 Feb–Mar 2025) **[search snippets]**. Event series: ACLED, UCDP.
- **FIRMS file.** `2024_Democratic_Republic_of_the_Congo` = 155 MB **[verified 200]** — the largest of any candidate by far; the DRC is one of the world's top burning countries (Jun–Sep dry-season savanna fires south of the equator, Dec–Feb north).
- **Cloud.** Equatorial; eastern Kivu highlands are cloudy most of the year with two short dry windows.
- **War type.** Maneuver in Jan–Feb 2025 (Goma 27 Jan, Bukavu 16 Feb), otherwise raiding and positional.
- **Expected FIRMS signal.** Combat fires lost in a huge seasonal fire background under persistent cloud; Goma/Bukavu are urban with little fuel. Poor.
- **Scores.** Outcome 1, Signal 1, Confounders 2, Cost 1 (file size). **Total 5.**

### 2.10 Libya 2019–20 (LNA Tripoli offensive)

- **Outcome series.** None in GIS found. ACLED and UCDP events; HDX "Libya – Data on Conflict Events" (UCDP, CC BY-IGO, to Jun 2024) **[verified]**.
- **FIRMS file.** `2019_Libya` 3.8 MB **[verified 200]** — mostly gas flares (type 2 static sources), which is a good reminder to filter `type`.
- **Fire regime.** Desert; coastal strip has little fuel. Cloud: clear.
- **War type.** Positional attrition on Tripoli's southern suburbs (Apr 2019–Jun 2020) with drones/airstrikes, then maneuver collapse in May–Jun 2020.
- **Expected FIRMS signal.** Very weak (urban/desert); strong industrial false-positive problem (oil infrastructure, flares). A footnote.
- **Scores.** Outcome 1, Signal 0, Confounders 1, Cost 3. **Total 5.**

### 2.11 Ukraine 2022 maneuver phase (within-war transfer)

- **Outcome series.** Excellent: VIINA settlement-day control from 24 Feb 2022 (ODbL, with tessellation geojson) **[verified]**; DeepState API snapshots from 3 Apr 2022 (1,785 to date) **[verified start]**; Wikipedia's settlement table with capture/recapture dates (e.g. Balakliia 3 Mar→8 Sep 2022; Izium/Kupiansk by 10 Sep; Kherson 1 Mar→11 Nov 2022) **[verified]**; ISW ArcGIS timelapse layers (schema/license unchecked). The Economist war-fire CSVs (CC BY 4.0) also carry an ISW-based held-area flag per fire **[verified]**.
- **FIRMS file.** `2022_Ukraine` 4.05 MB **[verified 200]**, i.e. about half the row count of 2024, consistent with the invasion starting in the no-fire season.
- **Fire regime/cloud.** Same as the existing study: blind Nov–Feb, peak Jul–Sep. Feb–Mar 2022 (Kyiv/Kharkiv/Kherson advances) is in the blind season; Sep 2022 Kharkiv counteroffensive is in peak season; Nov 2022 Kherson withdrawal is in the blind season again.
- **War type.** Maneuver (Feb–Apr, Sep, Nov 2022) → attrition (Bakhmut winter 2022–23) → failed maneuver (Jun–Aug 2023 counteroffensive, peak fire season) → attrition (2024–25). All inside one country, one sensor, one map team.
- **Expected FIRMS signal.** This directly tests Jackson's war-type worry with everything else held fixed. Prediction to pre-register: in the Sep 2022 Kharkiv phase, fires should *follow* the advance (burning of abandoned positions, strikes on retreating columns) rather than lead it; in the 2023 Zaporizhzhia counteroffensive, fires should lead at the breach points (Robotyne) by days, not weeks. If neither holds, the "attrition explains the null" story is weakened.
- **Confounders tested.** War type (fully), season (partly: maneuver phases happen in both seasons), AO (new sectors: Kyiv, Sumy, Kherson left bank).
- **Scores.** Outcome 3, Signal 2, Confounders 3, Cost 3. **Total 11.**

---

## 3. Ranking

| Rank | Case | Score | One-line verdict |
|---|---|---|---|
| 1 | Ukraine 2022–23 within-war | 11 | Only case with a daily control series; isolates war type and new AOs with sensor and cartographer held fixed. Must do. |
| 2 | Nagorno-Karabakh 2020 | 10 | Tiny files, full 2012–19 baseline, dated settlement list, published anomaly count to replicate (447 fires). A 2-day job that gives a true maneuver-war external test. |
| 3 | Sudan 2023– | 9 | Richest menu of war types and the inverted fire season; outcome is events/arson, not area. Tests the *other* FIRMS signal. |
| 3 | Syria 2017–20 + Dec 2024 | 9* | *Conditional on ACLED sub-district control or Carter Center data; otherwise 6. Dec 2024 is a clean maneuver null. |
| 5 | Myanmar 2021– | 8 | Best monsoon/cloud blind-spot calendar; arson signal in Nov–Feb; outcome series weak. |
| 6 | Ethiopia/Tigray | 7 | One published "fires track advance" example; thin outcome data; blackout makes it a reporting-latency study. |
| 7 | Sahel | 6 | Negative control: fire season owns the signal. One figure. |
| 7 | Gaza | 6 | Fuel-limited; UNOSAT is the right tool. One paragraph. |
| 7 | Yemen | 6 | Has a monthly control series but no fuel: the fuel-limited null with an outcome variable. One figure. |
| 10 | DRC/M23 | 5 | 155 MB of savanna fire under equatorial cloud; outcome gap after Nov 2023. Skip. |
| 10 | Libya | 5 | Desert, flares, urban. Skip. |

## 4. Recommendation

**Primary transfer case: Nagorno-Karabakh 2020**, run *after* the Ukraine 2022 within-war phase (which is part of the main project, not a transfer). Reasons:
1. Everything is small and free: two FIRMS files under 0.5 MB per year for 2012–2020, a dated settlement list, UCDP GED for events. Estimated 1–2 days including the write-up.
2. There is a published number to replicate (CEOBS: 447 VIIRS fires 26 Oct–4 Nov 2020 vs 203 in 2012–19) and then extend: nobody has put those fires against the day-by-day capture list. The extension is the novel part and it is cheap.
3. It is the cleanest open-data example of a *maneuver* war with drones and artillery, which is exactly the war type the Ukraine 2024–25 null cannot speak to.
4. Expected result is informative either way: if fires trail the southern advance and only spike at Shusha/Lachin, the brief can say "in maneuver warfare FIRMS is a trailing indicator of where the fight was, not where it is going", which is consistent with the Ukraine finding and strengthens the sensor-triage framing.

**Backup transfer case: Sudan 2023–**, as the *arson/raiding* test. Reasons:
1. It forces the method to confront the second kind of FIRMS signal and the inverted fire season (Nov–Feb peak), the two biggest "Ukraine-specific" objections.
2. The outcome is ACLED/UCDP events (settlement attacks), so the design is detection precision/recall against a per-village 2012–22 baseline, with Yale HRL and CIR reports as a hand-labelled validation set (they name villages and dates). This is also the most directly employer-relevant framing (triage of a free feed in a low-reporting environment).
3. Cost is moderate: one 15.7 MB file per year, UCDP free, ACLED needs a key and cannot be redistributed raw. Estimated 4–6 days.
4. Risk: ACLED terms (no raw redistribution; AI/ML restrictions) mean the public repo ships only derived per-village indices and UCDP rows. Mitigation: pre-register with UCDP Candidate as the primary outcome and ACLED as a robustness check.

**Why not Syria as backup:** it would be the better scientific case (monthly sub-district control from 2017 is the only other "control" panel), but I could not confirm that ACLED's control coding or the Carter Center's locality history is downloadable. Spend 30 minutes checking (ACLED portal after registration; email Carter Center Conflict Resolution Program) before deciding; if either is available, Syria displaces Sudan as backup and Sudan becomes the appendix arson figure.

**Appendix figures (one each, ≤ half a day total):** Sahel (season owns the signal), Yemen (fuel-limited with a control series), Gaza (fuel-limited urban), to populate the "when FIRMS is blind" product with non-Ukraine evidence.

## 5. Which cases test which Ukraine confounder

| Confounder Jackson worries about | Ukraine 2022 within-war | NK 2020 | Sudan | Syria | Myanmar | Sahel | Yemen | Gaza |
|---|---|---|---|---|---|---|---|---|
| Season / fuel (Nov–Feb blind, Jul–Sep crop burning) | Partial (maneuver in both seasons) | Autumn forest, low ag-burning: yes | Inverted season (Nov–Feb peak): **yes, strongest** | Arid, May–Jun crop fires: yes | Monsoon + Feb–Apr swidden: **yes** | Season swamps everything: yes (negative control) | No fuel at all: yes (null) | No fuel: yes (null) |
| Area of operations (steppe/Donbas specific) | New AOs (Kyiv, Sumy, Kherson left bank): yes | Mountains/forest: yes | Desert + savanna + megacity: yes | Steppe/desert: yes | Tropical forest/paddy: yes | Savanna: yes | Highland desert: yes | Urban: yes |
| War type (attrition → momentum explains all) | **Yes, the cleanest** (same sensor, same map team) | Maneuver: yes | Siege + maneuver + raiding: yes | Maneuver (Dec 2024) vs attrition (Idlib): yes | Raiding + siege: yes | Raiding only: yes | Frozen attrition: weak | Urban clearance: weak |
| Map latency (DeepState batching) | VIINA vs DeepState vs Wikipedia disagreement is measurable: **yes** | Announcement vs confirmation dates: partly | Reporting blackout: measures *event* latency instead | Monthly coding: no | No | No | Monthly snapshots: no | No |
| Industrial false positives (Donbas plants) | Same | None | Khartoum refinery (burned Jan 2025!), Port Sudan tanks | Oil fields NE Syria | Few | Few | Marib gas | None |

## 6. Concrete work plan for the two chosen cases

**NK 2020 (1–2 days)**
1. Download `viirs-snpp_<2012..2020>_Azerbaijan.csv` and `_Armenia.csv` (~4 MB total). Filter `type == 0`, confidence ≠ low.
2. Clip to the pre-war NKAO + surrounding districts polygon (draw from Natural Earth admin-1 or OSM).
3. Build the per-week baseline 2012–2019 for the same calendar weeks; count 2020 excess. Reproduce the 447-fire figure for 26 Oct–4 Nov.
4. Geocode the Timeline settlement list (GeoNames `AZ.txt`, free) into a date-of-capture table; sanity-check 10 against Wikipedia village pages.
5. Event study: for each captured settlement, FIRMS detections within 5 km in the 14 days before and after announcement date. Also UCDP GED events in the same windows.
6. Figure: cumulative captured settlements vs daily war-fires; map of fires coloured by day with the front implied by captures.
7. Write 1 page: did fires lead, coincide or trail? Pre-register the expected answer (trail) before step 5.

**Sudan 2023– (4–6 days)**
1. Download `viirs-snpp_<2012..2025>_Sudan.csv` (~15 MB/yr; 2023–25 ~45 MB; baseline years smaller). Register FIRMS MAP_KEY for 2026 and NOAA-20/21.
2. Settlement list: HDX Sudan populated places (OCHA/GeoNames `SD.txt`). Per-settlement 5 km buffers.
3. Baseline: for each settlement and ISO week, 2012–2022 mean and 95th percentile of detections. Flag 2023–25 weeks above the 95th percentile.
4. Outcomes: UCDP GED 25.1/26.1 + Candidate (CC BY) events with "attack on civilians / village"; ACLED events as robustness (key; do not redistribute). Validation set: Yale HRL Kutum (26 communities, Oct–Nov 2024), El Fasher (11 villages, 20–25 Apr 2024), CIR Murnei (27–28 Jun 2023) and Tawilah (16 Jun 2023) — all name villages and dates.
5. Metrics: precision/recall of FIRMS flags against events by month, split by season (burning Nov–Feb vs wet Jun–Sep vs dry-clear Mar–May) and by region (Darfur savanna vs Khartoum/Gezira).
6. Siege sub-test: El Fasher ring (Apr 2024–Oct 2025) 15 km front band vs 50–90 km rear, same design as Ukraine; expect weak.
7. Figure set for the blind-spot product: monthly flagged-vs-background ratio, Sudan beside Ukraine.

## 7. Flags and unverified items

- Could not verify: ACLED sub-district control for Syria is downloadable; Carter Center data access; OCHA Gaza zone polygons download; ISP-Myanmar township control product; D4M dataset download; Sudan War Monitor or Sudans Post GIS exports; FIRMS API transaction limits; the Economist model's baseline years (site unreachable); Wikimedia Commons map revision counts/licenses.
- Not re-verified today (standard climatology): all fire-season months and cloud regimes stated above. Compute them from the FIRMS files and MODIS cloud fraction in week 1.
- NK settlement dates are *announcement* dates and are disputed in places; treat ±2 days as noise.
- ACLED Content Usage Terms (8 Jul 2025) restrict AI/ML use and redistribution. Keep ACLED out of the public repo's raw data and out of any model-training pipeline; publish derived counts only.
- FIRMS country files are clipped to borders. For NK use both Azerbaijan and Armenia files; for Sudan the Chad side of Darfur is missing (`Chad` file needed for West Darfur refugee-flow fires).
- The DRC and Sahel files are large and dominated by background burning; if anyone insists on them, aggregate to 0.1° cells first and never load raw rows into memory on a laptop.
