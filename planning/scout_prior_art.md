# Scout: prior art on satellite fire/thermal data for conflict monitoring and territorial-change prediction

Written 2026-10-13 for the "Front line from space" project. Companion to `/Users/jacksonmackney/D3/Conflict_Data_Feasibility/frontline/{VERDICT,FIRST_PASS,SOURCES}.md`, which are the ground truth for what we already have (22 sectors × 77 weeks panel, fire coefficient 0.85, p 0.048, R² gain 0.006, 44% zero-fire sector-weeks in winter).

Verification key used throughout:
- **[READ]** = I read the primary document (full text or substantial extract) this session.
- **[ABSTRACT]** = abstract / landing page / secondary summary only; details flagged where inferred.
- **[UNVERIFIED]** = could not retrieve; claims come from search snippets or memory and need checking.

Web-search budget for the session ran out part-way through; the last ~6 planned searches (Economist 2026 follow-ups, Sudan Witness methodology, Perun episode lists, RUSI rate-of-advance, Kashmir, Gaza thermal) did not run. Those gaps are flagged in Section 7.

---

## 0. One-paragraph verdict

Everything published so far on FIRMS/VIIRS and war does one of three things: (a) **visual/anecdotal correspondence** of hotspots with the front (Bellingcat 2022, ELINT/PanArmenian 2020, Line of Actual Control 2020–22, most OSINT Twitter use); (b) **classification of fires as war-related against a pre-war baseline** and then *descriptive* mapping (The Economist's model, Tomchenko 2023, Ialongo 2023, Yailymov 2023, Naghizadeh 2024); or (c) **event-level verification of arson / strikes** with FIRMS as a timestamp and VHR imagery as the proof (Yale HRL Sudan, HRW Thantlang, Myanmar Witness, Dingemanse & Cerra Black Sea 2026). The only peer-reviewed work that touches "fires vs. the front line" quantitatively is Dingemanse, Zhizhin & Cerra (Sci. Rep. 2026) and the underlying DLR thesis, and they explicitly report that **no statistically significant linear relationship between distance-to-front and VNF count could be established**, that the front is only visible by spatial autocorrelation in late spring–late summer, and they use *liveuamap paid shapefiles*, *monthly 5 km grids*, and *no lead-lag or forecasting test*. **Nobody has published a sector-week panel with fixed effects, a pre-registered lead-lag test against a territorial-control dataset, a placebo/reverse-causality check, a quantified detection-coverage ("when is the sensor blind") product, or a cross-war transfer test.** Those are the open claims; the gap table in Section 8 ranks them.

---

## 1. Ukraine: journalism and OSINT

### 1.1 Bellingcat, "Scorched Earth: Using NASA Fire Data to Monitor War Zones" (4 Oct 2022) [READ]
- URL: https://www.bellingcat.com/resources/2022/10/04/scorched-earth-using-nasa-fire-data-to-monitor-war-zones/
- **What they did:** A how-to guide. Two workflows: (1) geolocate/chronolocate fire footage with FIRMS; (2) monitor hotspot clusters to generate leads. Worked examples: July 2022 Ukraine (hotspots "followed the forward edge of battle" vs. an ISW sitrep), Tigray Nov 2020 (hotspots moving Shiraro→Shire→Aksum matching ENDF advance; FRP 0–5 MW along road, 20–39 MW in towns), Western Tigray Feb 2021 (five clusters, two in a park with seasonal fire history, discarded).
- **Data:** FIRMS MODIS (1 km, Terra/Aqua) and VIIRS (375 m, S-NPP and NOAA-20); Sentinel-2 false colour, Planet, Worldview; Kepler.gl and Google Earth Pro.
- **Method:** Filter by confidence and FRP; compare to prior-year fire history; cross-check with sitreps; task imagery. Cement kiln example (500 MW, 100% confidence) to show industrial separation by FRP/persistence.
- **Found:** Qualitative. "Not a smoking gun but it can generate important leads"; "rarely sufficient on its own."
- **Did NOT do:** No accuracy/precision/recall, no systematic comparison against a control dataset, no threshold testing, no cause attribution, no seasonality or cloud quantification. 2022 interfaces.

### 1.2 The Economist, Ukraine war-fire model (live since Feb 2023; code public) [READ: GitHub README + Zenodo record + SWJ summary; interactive page itself not fetchable]
- URLs: repo https://github.com/TheEconomist/the-economist-war-fire-model ; Zenodo/Discuss Data record https://zenodo.org/records/17151723 ; Kaggle mirror https://www.kaggle.com/datasets/joebeachcapital/the-economists-ukraine-war-fire-daily-update ; secondary summary https://smallwarsjournal.com/2026/03/25/fire-detection-as-a-proxy-for-combat-the-economist/ ; live page https://www.economist.com/interactive/graphic-detail/ukraine-fires (paywalled; WebFetch blocked).
- **What they did:** Classify each FIRMS detection in Ukraine as "war-related" or not, publish a daily-updating map and CSVs, and use war-fire counts as one input into a casualty model.
- **Data:** NASA FIRMS (sensor not named in README; press summaries say "satellites pass over roughly twice a day"). Zenodo record says the model "combines NASA FIRMS infrared fire data with synthetic-aperture radar (SAR) imagery", but the README does not mention SAR; I could not resolve this. Territorial control = ISW ("areas within Ukraine not assessed as controlled by Russia by the Institute for the Study of War on the given date"). Population per fire point (`pop_exact`).
- **Method (from README, authoritative):** 0.1° × 0.1° grid cells. An ensemble of models trained on *non-war years* predicts expected fire activity per cell-day; a cell-day is "abnormal" if the observed excess has <5% probability of occurring in a normal year (press describes this as "95 of 100 models agree", equivalent). "Sustained excess" requires two such events in one cell <50 km apart, ≥7 and <180 days apart. Fires within 10 days of a qualifying war event are also flagged, on the stated empirical basis that "other activity producing fire events, typically from agriculture, does not resume until 10 days after an area has seen a war event." Extreme heat weeks (above the 95% interval of average temperature) produce *no* war classifications (happened once, 4–11 Apr 2023). A third-party paper (arXiv 2408.17022) says the base learners are gradient-boosted trees on ~10 non-war years; unconfirmed against the code.
- **What it controls for:** Local pre-war baseline per cell and calendar time (that is the whole point of the ensemble), extreme heat. **It does not** model cloud cover, overpass gaps, land cover, or season explicitly beyond what the baseline absorbs; cloud is listed as a limitation only.
- **Found:** 14,068 war events 24 Feb 2022–18 Feb 2023; 93,834 by 19 Jun 2024; ~3,368/month in recent months per SWJ. Fires occur in both front-line and rear areas. Location "to within 500 m" (README) vs "could be off by as much as 1 km" (press). Casualty estimates combine fire trends, territorial change and 200+ external estimates.
- **Did NOT do:** No published validation against ground truth, no precision/recall, no error rates (README is explicit: classification "is probabilistic" and can err both ways; "the number not flagged as war-related but should be is probably even larger"). **No lead-lag or forecasting claim about territorial change.** No coverage/blind-spot product. No sector panel. No transfer to another war. Casualty model is not reproducible from the repo alone.
- **Licence:** code MIT; data CC-BY-4.0 (README) / ODbL (Zenodo record for the Discuss Data deposit). Daily `output-data/ukraine_war_fires.csv` is directly reusable as a *second* fire classification to compare against our front/rear design.

### 1.3 OSINT and GitHub trackers [mixed]
- **Line of Actual Control (Substack), "Wildfire Data Reveals Russian Military Exercises" (18 Jan 2022)** [READ]: FIRMS 2021 Russia-wide, clipped to Wikimapia-traced training-range polygons from an ISW Zapad-2021 map, 552 detections inside ranges; matched to MoD press releases (Pogonovo Apr, Mulino Jul, Shikhany Aug). Notes snow/cloud blind season. No statistics. https://actualcontrol.substack.com/p/wildfire-data-reveals-russian-military
- **Same author, "Fire on the Mountain" (23 Nov 2020, Nagorno-Karabakh)** [READ]: Sentinel-2 SWIR burn-scar mapping (Pierre Markuse script), ~70 km² Tonashen, ~35 km² Sotk Pass; dates scars by image sequence; cause left open. **Does not use FIRMS.** https://actualcontrol.substack.com/p/fire-on-the-mountain
- **leomollmann/russo-ukrainian-war (GitHub, ~2022)** [READ]: FIRMS points + distance-to-road/rail + population; neural net classifier accidental vs attack; labels from PostGIS cross-reference with Centre for Information Resilience tweets, manual annotation; ~126k points 24 Feb–7 Nov 2022. **No accuracy metrics, no licence, dormant.** https://github.com/leomollmann/russo-ukrainian-war
- **playframap.github.io "Ukraine Control Map"** [ABSTRACT]: web map with a FIRMS overlay (needs user MAP_KEY). Visual only. https://playframap.github.io/
- **Hue-Jhan/OSINT-War-Room** [ABSTRACT]: dashboard aggregator; FIRMS inclusion unconfirmed. https://github.com/Hue-Jhan/OSINT-War-Room
- **ELINT News / PanArmenian, 1 Nov 2020** [ABSTRACT]: FIRMS 24-h map of Karabakh "could outline the approximate frontlines". Press report of a tweet. https://panarmenian.net/eng/news/287293
- **Twitter/X daily FIRMS-front accounts:** search did not surface a named account; Bellingcat says "many analysts have noticed" the correspondence. [UNVERIFIED: whether any account posts a systematic daily product.]
- **feedbagel, "Using NASA VIIRS heat data to detect US maritime interdiction strikes in real time"** [ABSTRACT, 2025–26]: blog applying FIRMS to Caribbean boat strikes; shows the "FIRMS as strike timestamp" idea is spreading beyond land war. https://feedbagel.com/post/using-nasa-viirs-satellite-heat-data-to-detect-us-maritime-interdiction-strikes-

### 1.4 DeepState-derived quantitative work [READ unless noted]
- **cyterat/deepstate-map-data** — daily GeoJSON of occupied MultiPolygon from 2024-07-08, GPL-3.0, 03:00 UTC GitHub Action. Already in our pipeline. https://github.com/cyterat/deepstate-map-data
- **ihorbach/ukraine-territory-trend** — monthly last-observation series of occupied km² (geodesic WGS-84) from the cyterat mirror; GitHub Pages chart; explicitly says no data before 2024-07-08 and "label as territory under Russian control according to DeepState". No fires, no statistics. https://github.com/ihorbach/ukraine-territory-trend
- **visua.no "DeepState gross flows"** — month-end diff of occupied polygon into Russian gains vs Ukrainian liberations from Jan 2023 (so they have a pre-July-2024 DeepState source, likely the API history); peak Russian gain 731 km² Nov 2024; Aug 2026 Ukrainian liberation 128 km². States DeepState "delays map updates during Ukrainian offensive operations" and that the grey zone is "hundreds of square kilometres". No fires. https://visua.no/en/charts/deepstate-gross-flows/
- **zsoltlazar "Automated DeepStateMap Occupied Areas" (Kaggle) / lazar-bit/deepstate-map-data-analytics** [UNVERIFIED: page returned title only].
- **Russia Matters "War Report Card"** (weekly) — sums three ISW layers for km²; notes DeepState gaps (e.g., no 15 Sep 2026 data). https://www.russiamatters.org/news/russia-ukraine-war-report-card/russia-ukraine-war-report-card-oct-7-2026
- **Black Bird Group (Finland)** — monthly net-advance figures on X (e.g., Feb 2026 net −37 km²; Jun 2026 −9 km²). Methodology not published in anything I could retrieve. [UNVERIFIED method] https://threadreaderapp.com/user/Black_BirdGroup
- **None of these touch fires.** The DeepState-quant niche is "km²/month" only.

### 1.5 Think-tank front-dynamics measurement [ABSTRACT/secondary]
- **ISW** year-end 2025: Russia took ~4,831 km² in Ukraine in 2025; 13.24 km²/day average (9.87 in 2024); monthly from 8.8 (Oct) to 20.99 (Nov); "78 casualties per km²" using UA General Staff claims. Method: ISW's own geolocation-based control layers, monthly km² ÷ days. A Euromaidan piece quotes 14.4 km²/day for 2025, so figures vary by cut. https://www.criticalthreats.org/analysis/russian-offensive-campaign-assessment-december-31-2025
- **CSIS, "Russia's Battlefield Woes in Ukraine" (2025)** [READ]: straight-line front displacement ÷ days → m/day. Avdiivka→Pokrovsk ~135 m/day; Kupiansk ~50 m/day; Ukraine 2023 summer ~90 m/day; Somme ~80; 2022 Kharkiv ~7,400; Kursk 2024 ~1,250. Data source for the front not named. A Jan 2026 CSIS brief (secondary coverage) gives 15 m/day Chasiv Yar, 23 Kupiansk, 70 Pokrovsk, 297 Huliaipole. https://www.csis.org/analysis/russias-battlefield-woes-ukraine
- **RUSI** (Watling & Reynolds, *Tactical Developments During the Third Year*, Feb 2025) — qualitative on attritional fires; no published km² method retrieved. [UNVERIFIED]
- **Perun** — searched; no episode found that computes km²/casualty or uses FIRMS. [UNVERIFIED]
- **Takeaway:** the measurement vocabulary that exists is km²/day and m/day from hand-drawn control maps. Nobody combines it with a remote-sensing proxy in a panel.

---

## 2. Ukraine: academic remote sensing

### 2.1 Dingemanse, Zhizhin & Cerra, "Conflict monitoring with VIIRS Nightfire: the war in Ukraine", *Scientific Reports* (2026), s41598-026-42172-0 [READ, full text via PDF]
- URL: https://www.nature.com/articles/s41598-026-42172-0 ; underlying thesis: https://elib.dlr.de/214347/1/Merlijn_Dingemanse_thesis.pdf (69 pp, read in part); Payne Institute note: https://payneinstitute.mines.edu/conflict-monitoring-with-viirs-nightfire-the-war-in-ukraine/
- **What they did:** Three use cases with **VIIRS Nightfire (VNF) v3**, not FIRMS: (i) heavy-industry status, (ii) urban combat detection per settlement, (iii) "towards frontline monitoring".
- **Data:** VNF (S-NPP + NOAA-20, M10/M11 SWIR thresholding + M12/M13 MWIR decorrelation; 750 m; temperature and source-area per detection) 2019-01-01 → 2025-09-30; **liveuamap paid-subscription shapefiles** sampled weekly for occupied area, from which a weekly frontline polyline and weekly territorial changes are clipped; OCHA boundaries; UNOSAT VHR damage assessments; VNF permanent-emitter catalogue to drop industry.
- **Method:** Urban: 7-day rolling VNF/km² per settlement >5 km²; flag settlements within 5 km of the front for ≥1 week with VNF density >2.5/km²; pre/post-war VNF ratio; blind majority visual inspection. Front: histogram of VNF distance-to-front (whole war composite); then monthly 5×5 km grid, global and local Moran's I (16 nearest neighbours), high-high swath = front.
- **Found:** VNF density vs UNOSAT damage density r² = 0.78, p<0.001 (thesis: 0.66), median CDA:VNF ratio 3.83:1. 90 of 1,985 settlements flagged; 86% show rising VNF as the front approaches, 6% inverse (unlisted industrial emitters). Most wartime VNF within 20 km of the front; urban detections cluster closer than non-urban. Global Moran's I 0.05–0.25, higher in high-count months; front visible as a hot-spot swath only late spring → late summer; "impossible to spot the frontline from autocorrelation data" in winter and late spring. Heavy-industry emissions down >60% in 2022 vs 2019–21.
- **Explicit limitations they state (quotable):** "no statistically significant linear relationship between the distance from the frontline and the number of VNF detections could be established"; frontline "calculated only on a weekly or monthly basis"; "buffered overlay of occupied areas, which can be imprecise"; cloud cover in Ukraine ">80 percent in December and under 50 percent in August"; Tuapse refinery hit twice with fires and not detected; 47% of Ukraine cultivated, crop-residue burning "likely to have a large effect"; 2024 extreme wildfire year; "near real-time detection of events is not yet possible"; "the data must be averaged over a time window", lowering temporal resolution.
- **What they say prior work lacked:** Ialongo et al. 2023 and Yailymov et al. 2023 showed FIRMS shifting toward the front but "did not go beyond visual analysis"; Naghizadeh 2024 correlated fire density with ACLED but "does not remove permanent emitters and relies on composites over several months."
- **Did NOT do:** No lead-lag test, no regression of territorial change on fires, no fixed-effects panel, no placebo, no rear control, no quantified per-sector blind-season map, no cloud-mask-based "observed vs unobserved" accounting, no daytime FIRMS comparison, no transfer test (thesis Appendix K mentions Gaza urban detection "with different filtering thresholds", not reproduced in the paper). Control data is paid (liveuamap), so the pipeline is not freely reproducible.
- **Relevance:** This is the closest competitor and the paper to cite in the first paragraph. Our design answers exactly the question they left open ("separating frontline VNF detections from background") with a free control dataset (DeepState) and a panel estimator.

### 2.2 Dingemanse & Cerra, "VIIRS nighttime thermal anomalies reveal conflict-related events on Black Sea offshore structures and Snake Island", *RSASE* 43 (2026) 102153 [READ]
- URL: https://doi.org/10.1016/j.rsase.2026.102153 (open access, CC-BY); PDF https://elib.dlr.de/225855/1/Viirs%20offshore%20article.pdf
- **Did:** VNF 2019-01-01 → 2025-11-30, 1 km buffers on 13 platforms + Snake Island, per-night count/temperature/area; validated with Sentinel-2 SWIR and dNBR (0.1/0.16 thresholds) plus news.
- **Found:** 3 platforms with sustained uncontrolled gas fires (~1,700–1,820 K, >20 m²), 1 conventional fire (1,415 K); all four Snake Island detection dates match S2 changes. Chose VNF over FIRMS "due to its algorithm being focused on nighttime acquisitions, and to the availability of area and temperature estimates."
- **Most useful number for us:** Sentinel-2 cloud table for the western Black Sea 2024–25: share of datatakes <10% cloud = 4.3% Jan, 13.6% Feb, 28% Mar, 27.6% Apr, 25% May, 57.1% Jun, 66.7% Jul, 71.9% Aug, 32.1% Sep, 34.5% Oct, 16.7% Nov, 3.0% Dec. This is the only published month-by-month cloud-availability table I found for the theatre, and it is for a coastal AO, not Donbas.
- **Did NOT do:** anything on land, any statistics beyond description.

### 2.3 Tomchenko et al., "Assessment and monitoring of fires caused by the war in Ukraine on landscape scale", *J. Landscape Ecology* 16(2) 2023 [READ]
- URL: https://doi.org/10.2478/jlecol-2023-0011 (CC BY-NC-ND)
- **Did:** FIRMS VIIRS (S-NPP + NOAA-20) daily points Mar 2022–Mar 2023 for 15 oblasts nearest the front, intersected with ESA WorldCover 2021 (tree/grass/crop/built-up); Sentinel-2 EO Browser spot checks.
- **Found:** Fire share by land cover shifts through 2022: forest peaks May–Jun (50%, 40%), cropland Jul–Aug (60%), built-up Sep–Nov; built-up fires ×4 Mar 2023 vs Mar 2022; cites ecoaction.org.ua claim that fires rose "36 times" and burned area "14 times" vs same period 2021 (not their own computation). Map of two weeks in July 2022 shows hotspots "concentrated along the front line".
- **Did NOT do:** No pre-war baseline of their own, no control region, no statistics, no front-line distance metric. Descriptive GIS.

### 2.4 Other Ukraine items [ABSTRACT]
- **Ialongo et al. 2023** (socio-economic disruptions from satellites, incl. fires shifting toward front) and **Yailymov et al. 2023** (FIRMS + optical, manual shelling-damage classes) — cited by 2.1 as visual-only. Not retrieved.
- **Trofymchuk et al. 2022**, "Detection of thermal anomalies as a result of military action in Ukraine by remote sensing methods" (SGEM / EarthDoc 10.3997/2214-4609.2023510041) — FIRMS 24 Feb–8 Jun 2022, Black Sea Biosphere Reserve case. [UNVERIFIED: 403.]
- **Oreshchenko & Osadchyi 2024**, **Mkrtchian & Müller 2024** (agricultural abandonment near the front — relevant to "fields near the front are not harvested so stubble burning falls", which is our confound) — cited in 2.1, not retrieved.
- **"Geospatial analysis of the fire incidents and burned areas induced by Russia-Ukraine war in 2022 using MODIS and VIIRS data"**, *Applied Geomatics* 2025, 10.1007/s12518-025-00634-6 — compares 2022 to prior years, VIIRS detects more than MODIS. [UNVERIFIED: paywall redirect.]
- **Tomchenko et al. 2025**, "Geoinformation wildfire mapping of Ukraine: analyzing FIRMS data" (*Geodesy and Cartography*, 2021–23) — wildfire, not conflict. https://journals.vilniustech.lt/index.php/GAC/article/view/21322
- **Integrating optical and radar for conflict-related change detection in Ukraine**, *Sci. Rep.* 2026 s41598-026-41424-3 — change detection, not control. [UNVERIFIED]
- **Cerra et al., ISPRS Annals X-3-2024** "Increases in night lights intensity reveal extreme events" — DNB. https://isprs-annals.copernicus.org/articles/X-3-2024/53/2024/
- **Tarnas et al. 2026**, *Conflict and Health*, "Nighttime lights as a proxy for conflict intensity and infrastructure recovery in Yemen and Ukraine" [READ via PMC]: Black Marble VNP46A3 monthly; BFAST breakpoints; ground truth = Yemen Data Project air raids and ACLED (shelling/air/drone) for Ukraine; breakpoints aligned with attack onset in 85.7% of Yemeni governorates but only 51.9% of Ukrainian oblasts; simulated BFAST recovery 92% (Yemen) vs 56% (Ukraine). NTL fell 53.3% Yemen, 21.0% Ukraine. Admits oblast-level ecological design, blackout confound, no physical-damage validation. Useful as the NTL analogue of "the proxy works far better in one theatre than another." https://pmc.ncbi.nlm.nih.gov/articles/PMC12889831/
- **"The rural limits of conflict monitoring using nighttime lights"**, *Humanit. Soc. Sci. Commun.* 2025, s41599-025-05074-6 — conflict areas have below-average NTL coverage; "most challenging in the very areas where such detection would be most valuable." [ABSTRACT] Directly analogous framing to our blind-spot product.
- **Artillery crater detection with VHR + deep learning**, *Sci. Remote Sens.* 2023 S2666017223000172 [UNVERIFIED: 403] — potential ground-truth source for "was there shelling here" independent of DeepState.

### 2.5 VIIRS product-level caveats that affect every study above [READ]
- **Schroeder et al. 2014** (RSE 143:85–96): VIIRS 375 m I-band algorithm; commission error <1.2% for nominal-confidence pixels; 3× (day) and 25× (night) more fire pixels than the 750 m product; 50%-detection-probability curves vs fire area and temperature exist in the NOAA ATBD but I did not retrieve the values. https://directreadout.sci.gsfc.nasa.gov/publications_documents/Schroeder_et_al_2014b_RSE.pdf
- **Dhage 2025, arXiv:2510.26816** (preprint, single author, not peer-reviewed) [READ]: of 6,007,831 nighttime VIIRS detections (FIRMS, 17 Jan 2023–17 Jan 2024, S-NPP + NOAA-20), **zero** are low-confidence vs ~695k expected under independence; nighttime fires below ~295 K I4 brightness appear to be dropped rather than flagged. Implication for us: a "night-only, drop low-confidence" filter is not symmetric between day and night, and night counts are already pre-filtered. Cite with the caveat that it is a preprint.
- **No published omission-rate-by-cloud study for conflict fires** turned up. The only cloud numbers are Dingemanse's (>80% Dec, <50% Aug) and the Black Sea S2 table. This is itself a gap (Section 8, row G3).

---

## 3. Sudan and Tigray: atrocity documentation with thermal data

### 3.1 Yale Humanitarian Research Lab (HRL), Sudan 2024–26 [ABSTRACT; report list READ]
- Publications index: https://ysph.yale.edu/hrl/publications/reports/
- Key items: "Confirmation of Nine Arson Attacks West of El-Fasher" (16 Apr 2024); "RSF Burning Agricultural Communities Close to El-Fasher" (29 May 2024); "Fourteen Arson Attacks on Villages, North Darfur" (16 Oct 2024); "Twenty-Six Arson Attacks on Villages in Kutum Locality, 12 Oct–6 Nov 2024" (7 Nov 2024); **"The Impact of Systematic Razing of Agricultural Communities Around El-Fasher: A Remote Sensing Study" (10 Mar 2026)**; "Assessment of Fire Damage in Al Umda IDP Camp, Tawila" (27 Mar 2026).
- **Did:** "Thermal scarring" workflow: FIRMS/VIIRS (and MODIS) detections date a burn to a day (e.g., Tikailat 14 Apr 2024), VHR commercial imagery confirms structure loss, Sentinel-2 vegetation indices quantify cultivated-land loss. The 2026 study (reported by Dabanga/Middle East Eye as produced with NASA Harvest — [UNVERIFIED]) covers 41 villages burned 31 Mar–12 Jun 2024: fire activity +330% in 2024 vs previous five years; cultivated land within 2 km fell 82% (7.16 → 1.25 km²); 68% of villages show no sign of life months later; 10 attacked more than once. PDF link https://files-profile.medicine.yale.edu/documents/0667d53f-af67-415c-99ce-bd9b2f32bc0e returned HTTP 410 for me; methodology section **not read**.
- **Did NOT do:** No front line (none exists in Darfur in the Ukraine sense), no prediction, no detection-probability accounting, no open code. Yale's product is forensic confirmation, village by village.
- **Relevance:** Sudan is our transfer case. HRL's village list is a potential *labelled set* for "does a FIRMS cluster at a village predict HRL confirmation of arson" and for calibrating detection probability in an arid theatre where the sensor should work year-round.

### 3.2 Atwal, Pfoser & Rothbart (GMU / Sudan Conflict Observatory), "Near-real-time conflict-related fire detection in Sudan using unsupervised deep learning", arXiv:2512.07925 (Dec 2025) [READ]
- URL: https://arxiv.org/html/2512.07925v1
- **Did:** RaVAEn VAE change detection on PlanetScope 3 m, five sites (Gandahar market, El Fasher, Muqrin, Jaranga, Sarafaya); AUPRC 0.63–0.94 vs 0.42–0.69 for pixel cosine baseline. Incident ground truth from ACLED, social media, interviews.
- **Says about VIIRS:** "public sources such as VIIRS and MODIS are unreliable for detecting small fires" — asserted from literature (Bromley 2010 Darfur MODIS), **not tested**.
- **Did NOT do:** No VIIRS/MODIS comparison, no latency measurement, five sites, commercial imagery (not free at scale).
- **Relevance:** Gives us a published claim to test cheaply: *how many HRL-confirmed village burnings have a FIRMS detection within 1 km on the stated day ±1?* That is a detection-rate number nobody has published for Sudan.

### 3.3 Tigray
- **Naghizadeh 2024**, *Research & Politics*, "The uses for fire data and satellite images in monitoring, detecting, and documenting collective political violence" [ABSTRACT; SAGE 403]: manually reviewed >2,000 FIRMS detections in the first three months of the Tigray war against open imagery; found multiple unreported arson/aerial-bombing destruction events; also (per Dingemanse) shows a density correlation between VIIRS fires and ACLED in SE Ukraine using multi-month composites without removing permanent emitters. https://doi.org/10.1177/20531680241261769
- **Ecology & Society 29(3):20 (2024)** [READ]: FIRMS VIIRS S-NPP, 460 m buffers, ~13,000 fires Nov 2020–Jun 2022 vs pre-war 1 Jan 2018–2 Nov 2020; monthly counts did **not** rise during the war; spatial pattern similar to pre-war; concludes fires do not explain woody-vegetation loss; notes ">250 m²" detection floor and that the product used (NRT vs standard) is ambiguous in their own text. https://ecologyandsociety.org/vol29/iss3/art20/ — **an honest null on fires in a war**, worth citing as precedent.
- **DX Open Network / Vigil Monitor** (Jan–Feb 2021): Shimelba and Hitsats camp fires, Gijet ~500 structures — VHR-led, FIRMS as lead. [ABSTRACT]
- **HRW / Amnesty Axum**: Amnesty's Axum report (Feb 2021) and HRW's shelling report were testimony-led with Maxar graphics; I found no HRW/Amnesty *thermal-data* methodology for Tigray. [UNVERIFIED that none exists; search budget ended.]
- **Did NOT do (all):** no systematic detection-rate, no control, no prediction.

---

## 4. Other theatres

### 4.1 Myanmar [READ]
- **Ren, Calef, Durieux, Ziemann & Theiler (LANL/Descartes), "On the Detectability of Conflict: a Remote Sensing Study of the Rohingya Conflict", arXiv:2003.08874 (2020)**: MODIS + VIIRS fire time series to find anomalous spatio-temporal patterns in Rakhine, plus Sentinel-1 backscatter/coherence for razing under cloud. Abstract-level only; qualitative. The title phrase "detectability of conflict" is the closest existing framing to our blind-spot question, but they do not quantify it.
- **HRW, "Month of fires in Thantlang" (30 Nov 2021)**: FIRMS thermal anomalies on ≥10 dates 29 Oct–29 Nov 2021 (first at 12:29 local 29 Oct), cross-checked with PlanetScope daily imagery; could not count destroyed buildings. https://www.hrw.org/news/2021/11/30/month-fires-thantlang-myanmar
- **Myanmar Witness (CIR), "One year mapping fires in Myanmar" (1 Sep 2022) and "Villages burn in Sagaing" (2023)**: FIRMS + Sentinel-2 + UGC triangulation; "almost 200 fires" verified Sep 2021–May 2022; in Apr 2023, 6 of 8 reported village burnings verified, 2 unverifiable for lack of FIRMS/imagery/UGC. States FIRMS false positives from industry and cloud interference. https://www.info-res.org/myanmar-witness/reports/one-year-mapping-fires-in-myanmar/
- **Did NOT do:** detection-rate, control regions, statistics. "Data for Myanmar" did not surface.

### 4.2 Nagorno-Karabakh 2020 [ABSTRACT]
- **Darbyshire & Weir, "Environmental dimensions during and after the Nagorno-Karabakh conflict of 2020", *IEAM* 19(2) 2023, doi:10.1002/ieam.4674**; and CEOBS 2021 report: hundreds of landscape fires 26 Oct–4 Nov 2020 judged "climatologically anomalous and so likely arose directly from the fighting"; split between deliberate and accidental "unknown". Which fire product and how the climatological baseline was built: not retrieved. https://www.environmentalpeacebuilding.org/library/show/LibraryItem-5922
- DFRLab Nov 2020 white-phosphorus imagery piece — VHR, not thermal.
- **Did NOT do:** front-line linkage, statistics, detection accounting. A 44-day manoeuvre war with FIRMS archive available is a candidate within-dataset "war of movement" transfer test (see gap G5).

### 4.3 Syria [ABSTRACT]
- **AAAS, "Investigating spatio-temporal dynamics of the Syrian civil war through spaceborne thermal" (c. 2014–15; MODVOLC-style MODIS hotspots)**: explicitly asked whether thermal data could be "a leading indicator of later news-making events" at city scale. Landing page only; numbers not retrieved. https://www.aaas.org/resources/investigating-spatio-temporal-dynamics-syrian-civil-war-through-spaceborne-thermal — the one prior piece that frames fires as a *lead* indicator; result unknown to me. [UNVERIFIED]
- **2019 Hasakah/Raqqa crop fires**: HRW estimated ~40,000 ha burned in NW front-line areas since 10 May 2019 (via The New Humanitarian); STJ reports; iMMAP/RFSAN 2015 FIRMS cropland fire map. Causes disputed (weather vs arson). No peer-reviewed VIIRS analysis found.
- **Mueller, Groger, Hersh, Matranga & Serrat, "Monitoring War Destruction from Space", arXiv:2010.05970 / PNAS 2021**: VHR + CNN building destruction, Syria. Not thermal. 
- **Li & Li 2014 / Li et al. 2017** NTL in Syria; **Yemen NTL 2017** (RS 9:798); **Iraq NTL 2018** (RS 10:858); **Kurdistan fires & conflict**, *Remote Sensing* 13(8):1575 (2021) [UNVERIFIED: 403] — VIIRS active fire in KRI, geopolitics of land and fire.

### 4.4 Gaza [ABSTRACT]
- All retrieved work is **NTL / SAR damage**, not active fire: Rinaldo et al. (Graduate Institute, 2026) 441 1-km cells, 12 Oct 2023–31 Oct 2024, −68.5% luminosity; CARE/Wuhan −84%; SARI Global (Jun 2025) VIIRS DNB −85% in Khan Yunis/Al-Shati aligned with UNOSAT damage; Payne Institute DNB 8–10 Oct 2023 blackout. Dingemanse thesis Appendix K reports VNF urban-combat method "demonstrated to work in the Gaza strip … although different filtering thresholds were required" (not in the published paper).
- **No FIRMS/VNF active-fire Gaza paper found.** [UNVERIFIED after one search; budget ended.] Gaza is a poor transfer case for our design anyway: no linear front, dense urban, tiny AO (VIIRS pixel = 375 m).

### 4.5 Kashmir / Line of Control [UNVERIFIED]
- Two searches found **nothing** applying MODIS/VIIRS active fire to LoC shelling. 2025 Operation Sindoor coverage is VHR damage assessment (Takshashila "From Pixels to Proof"; Damien Symon's Kirana Hills imagery). A 2007 IJRS paper on MODIS LST before the 2005 earthquake is unrelated. The LoC is mountainous, forested, with heavy winter snow and monsoon cloud, so a FIRMS analysis there would mostly measure blindness — which is actually a point in favour of including it in the *coverage* product, not the *lead-lag* product.

### 4.6 Russia-side and exercise detection
- Line of Actual Control 2022 (1.3) is the only item. Kursk 2024–25 is covered by the Russia FIRMS country file we have not yet downloaded (76 MB for 2024).

---

## 5. Territorial-control measurement and prediction (non-thermal)

- **Anders 2020**, *JPR* 57(6):701–714, "Territorial control in civil wars: Theory and measurement using machine learning": control as latent variable, HMM over ratio of terrorist to conventional tactics from event data, 0.25° hex grid, validated on Colombia and Nigeria. No remote sensing. https://doi.org/10.1177/0022343320959687
- **CONTACT (arXiv 2504.13730, 2025)**: LLM extraction of territorial control from news text, ISIS Syria/Iraq, tiny test set (5 examples). No remote sensing.
- **ViEWS / conflict-forecasting literature** (not searched this session): forecasts fatalities at PRIO-grid month, not front movement; uses NTL as a covariate in some models. [UNVERIFIED]
- **Spatiotemporal prediction of conflict fatality risk with CNNs and satellite imagery**, *Remote Sensing* 16(18):3411 (2024) — imagery → fatality risk, not control. [ABSTRACT]
- **Economist** uses ISW control as a *covariate* for its fire classification, not as an outcome.
- **Conclusion:** I found **no published model, in any theatre, that regresses or forecasts territorial-control change on satellite fire detections.** The thesis/paper in 2.1 computes "distance of VNF detection from territorial change" as an indicator but reports only composites and says the relationship with area gains "appears less consistent" than with the front line itself.

---

## 6. Tools, datasets and sources the prior art uses that we have not yet exploited

| Item | Used by | Cost / licence | Why it matters for us |
|---|---|---|---|
| **VIIRS Nightfire (VNF) v3/v4**, EOG Colorado School of Mines, nightly global CSV, temperature + source area per detection | Dingemanse ×2, Zhizhin | Free (EOG registration) https://eogdata.mines.edu/products/vnf/ | Night-only, physics-based temperature lets us separate ~1,100 K vegetation fire from ~1,700 K+ gas/munitions; a second sensor product for a robustness arm. |
| **Economist `ukraine_war_fires.csv`** (daily, 0.1° cells, war_fire flag, ISW-held flag) | — | CC-BY-4.0 | Drop-in alternative fire classification; test whether our front/rear result survives using *their* classification. |
| **VNF permanent-emitter catalogue** (EOG multiyear IR emitter list) | Dingemanse | Free | Clean removal of Donbas steel/coke plants instead of FIRMS `type==2`. |
| **ESA WorldCover 2021 (10 m)** | Tomchenko | Free, CC-BY | Land-cover stratification of front-band fires (crop vs grass vs built-up) — the confound our FIRST_PASS names. |
| **UNOSAT damage assessments (Ukraine)** | Dingemanse | Free | Independent "fighting happened here" ground truth not derived from DeepState. |
| **liveuamap occupied-area shapefiles** | Dingemanse | Paid subscription | Not for us; note as the paid alternative to DeepState. |
| **ISW ArcGIS timelapse feature services** | Economist (control covariate), Russia Matters | Public items; licence unretrieved | Second coding of control for timing cross-check. Item 49a529bb6f1d4f86b06ab7e756e47359 page returned no text; licence [UNVERIFIED]. |
| **DeepState API history** `https://deepstatemap.live/api/history/public` (1,785 snapshots from 2022-04-03) | visua.no (implied) | Free, no stated licence | Backfill to 2022 for the manoeuvre-phase transfer test. |
| **Black Marble VNP46A2/A3 DNB** | Tarnas, Cerra, SARI | Free | Cloud/snow flags in Black Marble QA can double as an *observability* layer for the blind-spot product. |
| **MODIS/VIIRS cloud mask (MOD35 / VNP35) or FIRMS "no data" footprints** | nobody in the conflict literature | Free (LAADS) | The actual ingredient for "observed and no fire" vs "not observed". Nobody has done this for a war. |
| **Sentinel-2 dNBR** via Copernicus Data Space / GEE | Dingemanse Black Sea, Line of Actual Control | Free | Burn-scar confirmation of a sample of front-band FIRMS clusters; cheap validation. |
| **Yale HRL village lists (Sudan)** | HRL | Free PDFs | Labelled arson events for Sudan detection-rate test. |
| **UCDP GED 25.1/26.1** (already identified), **ACLED** (free key) | Tarnas, Naghizadeh, Atwal | Free / free-with-registration | Event ground truth for Sudan transfer. |
| **ERA5 / Fire Weather Index (EFFIS)** | Dingemanse (cites 2024 FWI) | Free | Covariate for fuel dryness; explains 2024 Ukraine wildfire spike. |
| **Kaggle FIRMS country archives; FIRMS MAP_KEY API** | everyone | Free | Already planned (NOAA-20/21 adds). |

---

## 7. What I could not verify (do before citing)

1. Economist: whether SAR is actually an input (Zenodo says yes, README no), exact base learner, baseline years. Read `the-economist-war-fire-model/` R scripts.
2. Yale HRL 2026 methodology section (PDF 410'd); NASA Harvest co-authorship.
3. Naghizadeh 2024 full text (SAGE 403): exact ACLED correlation coefficient and composite window.
4. AAAS Syria thermal study results — the only prior "leading indicator" framing.
5. Darbyshire & Weir 2023 fire product and baseline method.
6. Kurdistan *Remote Sensing* 2021 paper content; Trofymchuk 2022; *Applied Geomatics* 2025 Ukraine paper.
7. Any Gaza or Kashmir active-fire study (two searches each, nothing; budget ended before a third).
8. Perun / RUSI quantitative rate-of-advance methods; Black Bird Group method.
9. ISW ArcGIS item licence and schema.
10. Whether any X/Twitter account publishes a systematic daily FIRMS-front product.
11. Dhage preprint's claim against NASA's VIIRS documentation (single-author, not peer-reviewed).

---

## 8. Gap table: claims nobody has published that this project could own

Scoring: **Defensible** = can we make the claim stick against a technical interviewer with open data in 4–6 weeks (1–5)? **Interesting** = would an Anduril/Palantir/OSINT-shop reader care (1–5)? Ranked by product, ties by defensibility.

| # | Claim nobody has published | Closest prior art and why it falls short | Def. | Int. | Notes / how to make it |
|---|---|---|---|---|---|
| **G1** | **A quantified blind-spot map for FIRMS in a war: for each front sector and calendar month, P(a fighting-week produces ≥1 detection), decomposed into cloud/overpass (not observed) vs fuel/season (observed, no fire).** | Dingemanse 2026 gives two cloud percentages and says the front is "impossible to spot" in winter; Black Sea paper gives an S2 cloud table for one coastal AO; Bellingcat lists causes qualitatively. **Nobody joins a cloud mask to fire detections per sector-month in a conflict.** | 5 | 5 | Use VNP35/MOD35 or Black Marble QA cloud flags over the front band; our 44%-zero-weeks number becomes a two-way table. Transferable product: run the same code on Sudan, Sahel, LoC, Karabakh. This is the project's anchor claim. |
| **G2** | **A pre-registered sector-week panel test of whether front-band fires lead territorial change, with fixed effects, clustered SEs, momentum control, placebo (future fires) and reverse-direction check — reported as a weak/null result.** | Dingemanse: "no statistically significant linear relationship" between distance-to-front and VNF count, monthly composites, no outcome regression. Economist: no lead-lag claim at all. AAAS Syria asked the lead-indicator question (result unretrieved). **No one has regressed control change on fires anywhere.** | 5 | 4 | Already 80% done (FIRST_PASS). Pre-register Spec C + the Pokrovsk-drop fragility before re-running with NOAA-20/21 and 2022 backfill. The honest null is itself the publishable finding. |
| **G3** | **Detection rate of FIRMS against independently confirmed fighting events, by season and land cover**: share of UNOSAT-dated damage windows (Ukraine) and Yale-HRL-dated village arsons (Sudan) that have a FIRMS detection within 1 km / ±1 day. | Dingemanse reports VNF density ∝ UNOSAT damage density (r² 0.78) but not recall per event; Atwal et al. *assert* VIIRS is unreliable for small fires without testing; Myanmar Witness reports 6/8 verified but not as a rate. | 4 | 5 | Cheap: ~90 UNOSAT activations, ~90 HRL villages. Gives the first published "FIRMS recall" number for war fires, split temperate vs arid. Directly answers the generalization worry. |
| **G4** | **Pre-war-baseline (Economist-style) vs rear-strip vs week-fixed-effects: do three different "normal fire" controls give the same front signal?** A methods comparison on the same cells. | Economist uses baseline only; we used rear strip + week FE; Tomchenko uses no control; Ecology & Society (Tigray) uses a pre-war period. Nobody compares controls. | 4 | 3 | Mostly code: 2019–21 FIRMS for the same sector cells; plus run Economist's `war_fire` flag through our panel. Shows analytic maturity. |
| **G5** | **Within-war transfer: does the fire→advance relationship differ between the 2022 manoeuvre phase (Kharkiv Sep 2022 at ~7,400 m/day per CSIS; Kherson Nov 2022) and the 2024–25 attrition phase (15–135 m/day)?** | CSIS/ISW publish m/day by phase; Dingemanse's control data covers 2022 but they do not split; our data starts Jul 2024. Nobody tests whether fires lead more in manoeuvre war. | 3 | 5 | Needs DeepState API backfill (~1,800 snapshots, KML-style layers to filter) — the biggest engineering risk in the plan. If it works, it is the most interesting result for a defence-tech reader: "the proxy's lead time depends on the type of war." |
| **G6** | **Cross-war transfer with a stated protocol: same pipeline, Sudan 2023–25 (arid, no front line → outcome = UCDP/ACLED events) and optionally Karabakh 2020 (44-day manoeuvre war, FIRMS archive exists).** | Yale/Atwal: forensic, event-level; Ecology & Society: null on fire counts in Tigray; no one runs a Ukraine-built method on Sudan with the same code. | 3 | 4 | Risk: Sudan has no control polygons; be explicit that the outcome variable changes. Karabakh is only 44 days (~88 overpasses) but has ~0 confounding agriculture in the mountains and a known end date. |
| **G7** | **The agricultural-abandonment confound measured, not asserted: front-band cropland fire counts vs rear cropland fire counts by month, stratified by WorldCover class, showing that front-band "fires" are disproportionately grass/built-up not stubble.** | Tomchenko shows land-cover shares for 15 whole oblasts; Dingemanse says crop burning "likely" matters; Mkrtchian & Müller 2024 document abandonment (not retrieved). Nobody stratifies the front band itself. | 4 | 3 | One join to WorldCover. Converts our strongest descriptive finding (front 5–17× rear) into a cleaner statement. |
| **G8** | **Day vs night asymmetry in war-fire detection, including the Dhage preprint's "no low-confidence at night" artifact, and whether night-only counts track the front better.** | Dhage (preprint) documents the artifact globally; Dingemanse prefers night for noise-floor reasons; nobody tests it on a front. | 3 | 3 | Needs the MAP_KEY for full day/night NOAA-20/21. A small, sharp methods note. |
| **G9** | **Map-latency correction: estimate DeepState's reporting lag by cross-coding against ISW timelapse layers (and the visua.no note that DeepState delays updates during UA offensives), and show how much lag alone could hide a 1-week lead.** | visua.no and Russia Matters note the lag qualitatively; nobody measures it or propagates it into a lead-lag test. | 3 | 4 | Needs ISW ArcGIS layer access and licence check. Even a partial answer ("median lag X days in sector Y") strengthens the null. |
| **G10** | **A public, versioned, free-data-only reproduction kit** (FIRMS country CSVs + cyterat mirror + Natural Earth + WorldCover) for the above, with the dashboard. | Economist's kit is open but depends on ISW control and R; Dingemanse's pipeline depends on paid liveuamap; leomollmann is dormant with no licence. | 5 | 3 | Reproducibility is the employer-facing differentiator; cheap to claim, hard for others to match without paying. |

**Claims to avoid** (already published or indefensible): "fires track the front" (Bellingcat 2022, Economist, Tomchenko, Dingemanse — all have it); "war fires can be classified against a pre-war baseline" (Economist); "FIRMS timestamps village arson" (Yale, HRW, Myanmar Witness); "I can predict Russian advances from fires" (our own data says no; Dingemanse says no linear relationship); any Gaza/urban claim at 375 m.

**Recommended ordering for the plan:** G1 → G2 → G3 → G7 → G4 (core brief, weeks 1–4); G5 and G9 only if the DeepState backfill and ISW access work by end of week 2; G6 as the final chapter with Sudan first; G8 and G10 as appendix/repo hygiene.

---

## 9. Citation list (URLs as retrieved 2026-10-13)

- Bellingcat 2022 — https://www.bellingcat.com/resources/2022/10/04/scorched-earth-using-nasa-fire-data-to-monitor-war-zones/
- Economist model repo — https://github.com/TheEconomist/the-economist-war-fire-model ; Zenodo — https://zenodo.org/records/17151723 ; Kaggle mirror — https://www.kaggle.com/datasets/joebeachcapital/the-economists-ukraine-war-fire-daily-update ; SWJ summary — https://smallwarsjournal.com/2026/03/25/fire-detection-as-a-proxy-for-combat-the-economist/
- Dingemanse, Zhizhin, Cerra 2026 — https://www.nature.com/articles/s41598-026-42172-0 ; thesis — https://elib.dlr.de/214347/1/Merlijn_Dingemanse_thesis.pdf ; Zhizhin slides May 2025 — https://mmda.ipt.kpi.ua/wp-content/uploads/2025/05/Shifting-Landscapes-Zhizhin-20250521.pdf
- Dingemanse & Cerra 2026 (Black Sea) — https://doi.org/10.1016/j.rsase.2026.102153
- Tomchenko et al. 2023 — https://doi.org/10.2478/jlecol-2023-0011
- Tarnas et al. 2026 — https://pmc.ncbi.nlm.nih.gov/articles/PMC12889831/
- Rural limits of NTL — https://www.nature.com/articles/s41599-025-05074-6
- Schroeder et al. 2014 — https://directreadout.sci.gsfc.nasa.gov/publications_documents/Schroeder_et_al_2014b_RSE.pdf
- Dhage 2025 preprint — https://arxiv.org/abs/2510.26816
- Yale HRL reports index — https://ysph.yale.edu/hrl/publications/reports/ ; 2026 razing study (via Dabanga) — https://www.dabangasudan.org/en/all-news/article/yale-hrl-rsf-razed-north-darfur-farming-communities-to-induce-famine
- Atwal, Pfoser, Rothbart 2025 — https://arxiv.org/html/2512.07925v1
- Naghizadeh 2024 — https://doi.org/10.1177/20531680241261769
- Ecology & Society Tigray 2024 — https://ecologyandsociety.org/vol29/iss3/art20/
- Ren et al. 2020 Rohingya — https://arxiv.org/abs/2003.08874
- HRW Thantlang 2021 — https://www.hrw.org/news/2021/11/30/month-fires-thantlang-myanmar
- Myanmar Witness 2022 — https://www.info-res.org/myanmar-witness/reports/one-year-mapping-fires-in-myanmar/
- Darbyshire & Weir 2023 — doi:10.1002/ieam.4674 ; CEOBS summary — https://www.environmentalpeacebuilding.org/library/show/LibraryItem-5922
- Line of Actual Control — https://actualcontrol.substack.com/p/fire-on-the-mountain ; https://actualcontrol.substack.com/p/wildfire-data-reveals-russian-military
- AAAS Syria thermal — https://www.aaas.org/resources/investigating-spatio-temporal-dynamics-syrian-civil-war-through-spaceborne-thermal
- Mueller et al. 2020 — https://arxiv.org/abs/2010.05970
- Anders 2020 — https://doi.org/10.1177/0022343320959687 ; CONTACT — https://arxiv.org/abs/2504.13730
- CSIS battlefield woes — https://www.csis.org/analysis/russias-battlefield-woes-ukraine ; ISW 31 Dec 2025 — https://www.criticalthreats.org/analysis/russian-offensive-campaign-assessment-december-31-2025
- DeepState mirrors/analyses — https://github.com/cyterat/deepstate-map-data ; https://github.com/ihorbach/ukraine-territory-trend ; https://visua.no/en/charts/deepstate-gross-flows/ ; https://www.russiamatters.org/news/russia-ukraine-war-report-card/russia-ukraine-war-report-card-oct-7-2026
- leomollmann — https://github.com/leomollmann/russo-ukrainian-war ; playframap — https://playframap.github.io/
- Gaza NTL — https://repository.graduateinstitute.ch/record/321956 ; https://reliefweb.int/report/occupied-palestinian-territory/mapping-gazas-infrastructure-collapse-through-satellite-radiance
- VNF product — https://eogdata.mines.edu/products/vnf/
