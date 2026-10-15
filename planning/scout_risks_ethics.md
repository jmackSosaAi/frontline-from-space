# Scout: risks, ethics, legal — "Front line from space"

Written 2026-10-13. Scope: OPSEC/dual-use, data licensing and attribution, being-wrong-in-public, information-environment sensitivities, employer perception, personal risk, and a go/no-go checklist. Ground truth for what the project is: `/Users/jacksonmackney/D3/Conflict_Data_Feasibility/frontline/VERDICT.md` and `FIRST_PASS.md`.

Everything marked **[verified]** was read from the primary page today. **[unverified]** means I could not reach the primary text and the claim is from memory or a secondary source; confirm before relying on it. I am not a lawyer; the licensing section is a careful reading, not legal advice.

---

## 0. Bottom line up front

- **OPSEC: low real risk, but not zero, and the mitigation is cheap.** Every input is already public at finer resolution and lower latency than anything this project would publish. FIRMS itself publishes point detections within ~3 hours; The Economist publishes a daily, war-classified, point-level fire map and the code on GitHub under MIT/CC-BY. The project's unit of analysis is the sector-week (about 50 km × 7 days). Publish at that aggregation, lag the dashboard, and never ship a "today's front-fire points" layer, and the dual-use question is answered in one paragraph of the brief.
- **Licensing: two real constraints.** (1) **DeepState**: the website content is freely reusable with attribution, but the **API is free only for volunteer/charitable or Ukrainian-defense activity; commercial use needs approval, and there is no explicit research/media tier.** The GitHub mirror is GPL-3.0 code, but the mirror author cannot relicense DeepState's geometries. Do not redistribute the raw polygons; publish derived sector-week aggregates and a fetch script. (2) **ACLED**: do not use it. Its 2025 EULA bars direct access to data, requires derived outputs to be non-reverse-engineerable, and bars reproducing its maps. UCDP GED is CC BY 4.0 and covers the Sudan transfer test cleanly.
- **Being wrong in public: the biggest reputational risk and the easiest to pre-empt.** Pre-register one specification on OSF before re-running with the expanded data, keep a Limits section as long as the Findings section, and get two external reads (one methods, one Ukraine-subject-matter) before publishing.
- **Information environment:** Ukraine's Criminal Code Art. 114-2 criminalizes disseminating locations of Ukrainian forces and real-time strike consequences; aggregated, lagged, satellite-derived combat-intensity maps are not what it is aimed at and are already published by major outlets, but that is a reason to keep latency and aggregation as a hard rule, not a reason to ignore it. Russia's Art. 207.3 ("fakes") and the "undesirable organization" list (Bellingcat, CIT) are the main reason to **treat travel to Russia/Belarus as off the table while this is public.**
- **Employer perception:** a null result framed as "what a free sensor can and cannot tell you, with a coverage product" reads as analytic maturity; framed as "I failed to predict advances" it reads as failure. A Ukraine-only piece reads as narrow **unless** the deliverable includes a transfer test or at least a blind-spot map for a second theatre. The framing choices below handle both.
- **Personal risk for a student:** low. The realistic threats are (a) pile-on from partisan accounts on either side if a chart is read as "Ukraine is losing/winning," (b) a methods takedown by a credentialed analyst, (c) a future employer or clearance adjudicator asking about contacts. All three are managed by tone, by not engaging with trolls, and by a one-paragraph disclosure note.

**Recommendation: GO**, conditional on the checklist in §9.

---

## 1. OPSEC and dual-use

### 1.1 Is anything here not already public?

| Input | Publicly available at what resolution/latency | Source |
|---|---|---|
| FIRMS VIIRS/MODIS detections | Point level (375 m), ~3 h NRT, global, no key for yearly country CSVs; API with free MAP_KEY (5,000 transactions / 10 min) | [FIRMS FAQ](https://www.earthdata.nasa.gov/data/tools/firms/faq) **[verified]**; [MAP_KEY page](https://firms.modaps.eosdis.nasa.gov/api/map_key/) **[verified]** |
| War-classified fire points, Ukraine, daily | Point level, daily, with ML classification "war-related", **published on GitHub by The Economist** (MIT code, CC-BY-4.0 data), with "events in the past week" map | [TheEconomist/the-economist-war-fire-model](https://github.com/TheEconomist/the-economist-war-fire-model) **[verified]** |
| Territorial control | DeepState daily polygons on the public map and via public history API; cyterat mirror daily GeoJSON; ISW daily maps and ArcGIS timelapse layers | SOURCES.md; [cyterat/deepstate-map-data](https://github.com/cyterat/deepstate-map-data) **[verified]** |
| VIIRS Nightfire frontline delineation | Published academic paper (Dingemanse, Zhizhin, Cerra, *Scientific Reports* 2026) and [Payne Institute post, 2 Mar 2026](https://payneinstitute.mines.edu/conflict-monitoring-with-viirs-nightfire-the-war-in-ukraine/) **[verified existence; paper body not read, Nature paywall redirect]** |
| Bellingcat's FIRMS how-to | Public 2022 guide; no ethics/OPSEC section; no code or data release | [Bellingcat 2022](https://www.bellingcat.com/resources/2022/10/04/scorched-earth-using-nasa-fire-data-to-monitor-war-zones/) **[verified]** |

**Conclusion:** nothing in this project is a new disclosure. The one genuinely new product is the **blind-spot/coverage map** (when and where FIRMS cannot see). Could that help an adversary? In principle "the satellite is blind here in December" tells someone when burning a depot is unobservable from space. In practice: cloud/snow seasonality of thermal sensors is textbook remote sensing, both sides have their own ISR, and the coverage map is derived from public data a hostile actor could compute in an afternoon. This is the classic "the marginal contribution of publication is zero" test and it passes. Note it explicitly in the brief rather than leaving a reviewer to raise it.

### 1.2 What latency and aggregation make it safe?

Adopt these as hard rules and write them in the README:

1. **Unit of publication is the sector-week** (22 sectors of ~50 km, 7-day bins) or coarser (monthly, oblast). No point-level front-band detections in the repo or dashboard. Point data is reproducible from FIRMS by anyone; the repo ships the fetch script, not the points.
2. **Dashboard lag of at least 7 days** behind the most recent FIRMS acquisition, and aggregated to complete weeks only. The Economist publishes daily; being more conservative than a major outlet costs nothing analytically and removes any "real-time targeting aid" reading.
3. **No per-detection FRP or timing tables for the front band.** Fire radiative power and acquisition times of individual detections are the only fields that look like "something big burned here at 01:30." Use them in analysis; publish only aggregates.
4. **Blind-spot product at monthly × sector or coarser.** Express as "probability a 1,000 km² cell has zero detections given fire activity in the rear," not as a day-by-day gap calendar.
5. **No annotation of specific detections as specific events** ("this cluster is the X depot strike"). That is a verification claim the project cannot support and it is exactly the thing Ukrainian law targets (see §4).

### 1.3 How Bellingcat and The Economist handled it

- **Bellingcat (2022):** wrote a tutorial, cross-referenced FIRMS with ISW and Sentinel imagery, listed sensor limitations at length, and **did not discuss OPSEC or civilian-harm concerns at all**. They did not release data or code. **[verified]**
- **The Economist (2023–present):** publishes daily, point-level, war-classified detections plus full code and model on GitHub, CC-BY-4.0, with a Limitations section and a named corresponding author (Sondre Solstad) inviting corrections. **[verified]** I found no published OPSEC criticism of this. **[searched; none found]**
- **Berkeley Protocol / public-interest OSINT guidelines (2023):** principles of proportionality, harm minimization, "publicly available does not imply no restrictions." Neither document addresses publication delay for aggregate conflict indicators specifically. [Guidelines PDF](https://checkfirst.network/wp-content/uploads/2023/04/Guidelines-for-Open-Source-Intelligence-Organisations.pdf) **[verified summary only]**

Takeaway: the field norm is already more permissive than the rules in §1.2. Following §1.2 puts the project on the conservative side of established practice, which is the right place for a student.

---

## 2. Data licensing, source by source

### 2.1 NASA FIRMS (VIIRS SNPP/NOAA-20/NOAA-21, MODIS)

- **Terms:** NASA open data policy, "full and open sharing." No registration for yearly country CSVs; free MAP_KEY for API (5,000 transactions / 10-min window; large date ranges count as multiple transactions). **[verified]**
- **Attribution required:** "We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Earth Science Data and Information System (ESDIS)." Caption form: "NASA FIRMS." If redistributing data to third parties, reproduce or link the LANCE disclaimer. **[verified: FAQ text]** The disclaimer URL `/data/tools/firms/disclaimer` returned 404 today; the FAQ links it under a different path — **[flag: find the live disclaimer URL before publishing]**.
- **Quality caveat you must repeat:** NRT products are not science quality; the standard (SP) reprocessed product differs (location accuracy after maneuvers, day/night flag computed differently). **For the analysis, use the SP archive where available and state which product each year came from.** The 2023–25 yearly CSVs are likely SP; the 2026 API pulls will be NRT. Mixing them is a documented confound and should be in the Limits section. **[verified: FAQ]**
- **Suggested dataset citations:** MODIS MCD14DL doi:10.5067/FIRMS/MODIS/MCD14DL.NRT.006; VIIRS VNP14IMGTDL_NRT doi:10.5067/FIRMS/VIIRS/VNP14IMGT_NRT.002 **[DOI for VIIRS from memory; verify on the FIRMS page]**.
- **Redistribution:** permitted. Shipping the aggregated panel and even the raw yearly CSVs is fine with attribution; prefer a fetch script to keep the repo small.
- **Risk:** low. **Cost:** $0.

### 2.2 DeepStateMap (the key licensing issue)

- **Primary text:** [License Agreement, last updated 3 Sep 2025](https://deepstatemap.live/license-en.html) **[verified]**. Copyright holder DEEPSTATEUATECH LLC. Ukrainian law governs.
- **Visual and textual materials:** "may be freely used for both commercial and non-commercial purposes" with "a text reference, the DeepStateMap.live logo, or a direct link." **This covers screenshots, map images, and quoting figures.**
- **API:** free only for (a) volunteer/charitable activity (proof on request) and (b) "activities for the defense of Ukraine, its sovereignty, and territorial integrity." Commercial entities need prior approval via the API request page. **Research, student, media, and portfolio use are not named anywhere.** Prohibited: "unauthorized distribution, publication, proxying, or other methods of transferring the API to third parties" and "creation of identical objects that completely match the Objects."
- **The history endpoints** `https://deepstatemap.live/api/history/public` and `/api/history/<id>/geojson` are "the API" under this agreement, even though they are unauthenticated. The feasibility pass hit them (one sample); the 2022–24 backfill plan means ~1,800 requests.
- **The cyterat mirror** is GPL-3.0 **[verified via GitHub API]**, but GPL applies to the author's code and repo; it cannot grant rights in DeepState's geometries that DeepState did not grant. Treat the mirror's GeoJSON as DeepState-licensed content that someone else redistributed. Using it for analysis is low risk; **re-redistributing the daily polygons from Jackson's repo is the thing to avoid.**

**Mitigations, in order of preference:**
1. **Email DeepState for written permission** for non-commercial research use of the history API and for publishing derived sector-week aggregates with attribution. Use the API request form linked from the license page. Expected cost: one email; expected latency: unknown, possibly no reply. Send it in week 1 so the answer (or silence) is known before publication. Keep the email in the repo's `LICENSES/` folder if they say yes.
2. **Whether or not they reply:** publish only **derived** data — sector-week net area change, front-line length, sector geometry (which is Jackson's construction) — not DeepState's polygons. Derived weekly scalars are not "identical objects" and are the kind of thing journalists already publish from the map daily.
3. **Rate-limit the backfill** (one request every 2–3 s, ~1.5 h total, overnight), set a descriptive User-Agent with a contact email, cache everything locally once, never re-pull. This is courtesy, not license compliance, but it is what a reasonable rights-holder cares about.
4. **Attribution block** (every chart, README, brief): "Territorial control: DeepStateMap.live (DEEPSTATEUATECH LLC), used under its public license; derived aggregates only." Include the logo or link.
5. **Fallback if DeepState says no:** ISW/CTP ArcGIS timelapse layers as the control-of-territory source (see 2.3), with the same derived-only rule. Analytically weaker (coarser, more conservative updates) but the project still runs.

**Risk:** moderate on paper, low in practice (DeepState's content is reused daily by global media and the license is clearly written to encourage that). **Cost:** $0.

### 2.3 ISW / Critical Threats Project

- **Terms page** (`understandingwar.org/terms-use`) is behind a Cloudflare challenge; could not be read today. **[unverified]** From memory, ISW permits reproduction of its maps and text with attribution and a link, and does not offer a data download. Confirm in a browser before relying on their layers.
- **ArcGIS Online layers** owned by ISW staff accounts (SOURCES.md): their item-level terms govern. Esri's own terms require checking each item's terms and attributing Esri and licensors for base maps. **[verified: Esri docs]** Public feature services with no stated license are a grey area; use them only as a **cross-check** of DeepState timing, publish only agreement statistics (e.g., "DeepState and ISW disagree on week-of-change for 18% of sector-weeks"), never their geometry.
- **Data-integrity caveat to cite:** on 15 Nov 2025 an ISW employee made an unauthorized edit to the Ukraine map (Myrnohrad) that coincided with a Polymarket payout; ISW removed it and said it was unauthorized. [dev.ua report](https://dev.ua/en/news/spivrobitnyk-isw-vnis-neuzhodzhenu-pravku-na-mapi-voiennykh-dii-v-ukraini-shcho-zbihlasia-z-vyplatoiu-po-stavkam-polymarket-1765881875) **[verified]**. This is a one-line reason in the Limits section why no single control map is ground truth and why the project should test sensitivity to the control source.

### 2.4 ACLED — do not use

- [2025 EULA](https://acleddata.com/eula) **[verified]**: commercial and public-sector users need licences; licensees "shall not provide, permit, or allow direct access to any of the Licensed Content"; external materials "must be transformative, such that they cannot be reverse engineered to recreate the Licensed Content"; ACLED's "Analysis" (which includes maps) may not be reproduced or redistributed; scraping prohibited; ML training restricted; non-compete clause. No student tier is named; academic access details were truncated in search results.
- For a public repo with a reproducible pipeline, ACLED is a liability: the pipeline would have to download data the user cannot see, and a weekly event-count panel per 50 km cell arguably lets someone reverse-engineer the event layer at that resolution.
- **Replacement:** UCDP GED for Sudan (and any second theatre). If ACLED is ever needed, use it only privately for a robustness footnote, never in the repo.

### 2.5 UCDP GED and Candidate Events

- [UCDP downloads](https://ucdp.uu.se/downloads/) **[verified]**: **CC BY 4.0**, free, redistributable with citation. GED Global 26.1 is current; UCDP Candidate Events 26.0.8 (Aug 2026) is monthly with ≤1-month lag and covers 2026 for the Sudan test.
- **Required citations:** (1) Davies, Pettersson, Öberg, "Organized violence 1989–2025, and violent political protests," *Journal of Peace Research*, 2026, https://doi.org/10.1093/jopres/xjag046; (2) Sundberg & Melander (2013), "Introducing the UCDP Georeferenced Event Dataset," *JPR* 50(4). Candidate: Hegre, Croicu, Eck, Högbladh (2020), *Research & Politics*. Acknowledge DEMSCORE (Swedish Research Council grant 2021-00162).
- **Caveat for the transfer test:** GED geo-precision codes (where_prec) vary; filter to precision ≤ 2 (settlement/sub-district) for a 50 km cell match. GED is event-based, not territorial, so the Sudan hypothesis is "fires lead events/fatalities," not "fires lead area change" (as VERDICT.md already says).
- **Risk:** none. **Cost:** $0. ~30–40 MB.

### 2.6 Natural Earth, OpenStreetMap, basemaps

- **Natural Earth:** public domain; "crediting the authors is unnecessary." Optional: "Made with Natural Earth." **[verified]** Caveat already in SOURCES.md: Natural Earth places Crimea in Russia; say so in the README and show it as occupied Ukrainian territory consistent with DeepState's polygons.
- **OpenStreetMap:** ODbL 1.0 — attribution "© OpenStreetMap contributors" required; if you build a derived database from OSM (e.g., settlement points for sector labels), it must be ODbL too; "produced works" (maps, charts) need only attribution. **[from memory; standard, low risk]** Tile servers: do not hit tile.openstreetmap.org from a public dashboard (usage policy); use a free-tier tile provider or vector tiles via MapLibre with a provider that allows it, or render static maps.
- **Sentinel-2/3 (Copernicus)**, if used for cloud-cover masks: free and open, attribution "Contains modified Copernicus Sentinel data [year]." **[from memory]**

### 2.7 The Economist war-fire model (if used as a comparison)

- Code MIT; data CC BY 4.0; "freely available for public use, as long as The Economist is cited." Suggested citation: "The Economist and Solstad, Sondre (corresponding author), 2023. The Economist's war-fire model. First published in 'A hail of destruction', The Economist, February 25th issue, 2023." **[verified]**
- Using their war-classified points as a benchmark for the pre-war-baseline approach is cheap, legal, and makes the project look collegial rather than reinventing the wheel. Their author explicitly invites feedback.

### 2.8 Attribution block to paste into README, brief, and dashboard footer

```
Data: NASA FIRMS (VIIRS SNPP/NOAA-20/NOAA-21 active fire, LANCE/ESDIS; NRT and SP products as noted) ·
DeepStateMap.live (DEEPSTATEUATECH LLC) territorial-control polygons, derived aggregates only ·
UCDP GED 26.1 and UCDP Candidate Events 26.0.x (CC BY 4.0) ·
Natural Earth (public domain) · © OpenStreetMap contributors (ODbL) ·
Comparison: The Economist war-fire model (CC BY 4.0, Solstad 2023).
NRT FIRMS data are not science quality; see LIMITS.md.
```

---

## 3. The risk of being wrong in public, and how to pre-empt it

The headline result is near-null and fragile (p = 0.048; drops to 0.079 without Pokrovsk; ~0.5% ΔR²; ~10 specifications tried). The danger is not the null; it is publishing a borderline positive that a critic shows is specification-dependent, or publishing a null that a critic shows is a power problem. Both are pre-emptable.

### 3.1 Pre-registration (do this before pulling NOAA-20/21 or the 2022–24 backfill)

- **Platform:** OSF Registries, free. Use the **secondary-data preregistration template** (van den Akker et al. 2021, *Meta-Psychology*, OSF project doi 10.17605/OSF.IO/U68Y7) or the standard OSF Prereg form with the "existing data" question answered honestly as "registration following analysis of some data." [FORRT summary](https://forrt.org/curated_resources/secondary-data-preregistration/) **[verified existence; check whether the template is live in OSF Registries]**
- **What to lock:** one primary specification (Spec C: sector + week FE, momentum, clustered by sector, 15 km front band), the outcome (net km² next week), the sample (all sectors, all weeks, both products), the single pre-specified subgroup (season), the two placebos (lead-2 fires; rear band), the equivalence bound for "null" (e.g., |β| < 0.3 km² per log-unit, or ΔR² < 1%), and the transfer test for Sudan (fires at t → GED events at t+1, 50 km hex, month).
- **State what is exploratory:** the 2022 manoeuvre-phase split, pre-war-baseline control, FRP/night-only variants.
- **Why it matters for employers:** "I pre-registered, then the expanded data did/did not confirm" is a sentence very few portfolio projects can say. It also converts the "many specifications tried" problem into a disclosed exploratory phase rather than a hidden one.
- **Time:** 2–3 hours. **Cost:** $0.

### 3.2 Limits section, written first

Draft `LIMITS.md` in week 1 and keep it at least as long as the findings. Must include: NRT vs SP product mixing; VIIRS blind season (44% of sector-weeks zero); DeepState batch latency as outcome measurement error; sector-construction sensitivity (Voronoi fan-out, sector 21 artefact); the Pokrovsk-dependence of the coefficient; the permutation test's serial-correlation problem; the Russian-side-of-border gap; one-war, one-type-of-war; control-map integrity (ISW Nov 2025 incident); and the fact that the descriptive claim (front lights up) was already published by Bellingcat/Economist/Dingemanse et al.

### 3.3 External review before publishing

Two reads, asked for explicitly in week 4:
- **Methods read:** anyone with panel-econometrics experience (an econ-stats instructor, a grad student). Question to ask: "Where would you break this in an interview?"
- **Subject-matter read:** someone who follows the Ukraine front professionally (ISW/CTP alumni, a Ukraine-focused journalist, the Economist model's author who invites exactly this). Question: "Is anything here misleading to a reader who knows the front?"
- Record who reviewed and what changed in `CHANGELOG.md`. Do not list names without permission.

### 3.4 Robustness that costs little

- Leave-one-sector-out table for the main coefficient (already partly done; publish it).
- Block bootstrap or moving-block permutation by sector (fixes the permutation test's serial-correlation problem).
- Alternative sector widths (25/50/100 km) and band widths (10/15/20 km).
- Control source sensitivity: DeepState vs ISW week-of-change.
- Equivalence test for the null, so the result is "we can rule out effects larger than X," not "p > 0.05."

### 3.5 Correction policy

One paragraph in README: how to report errors, that the repo is versioned, that a corrected version supersedes. Having a correction policy before you need one is what distinguishes a project from a hot take.

---

## 4. Ukrainian and Russian information-environment sensitivities

### 4.1 Ukraine

- **Criminal Code Art. 114-2** (Law 2160-IX, in force 27 Mar 2022): unauthorized dissemination of information on movement/deployment of the Armed Forces, weapons, and (per SBU guidance) real-time locations/consequences of strikes and air-defence operations; up to 8–12 years. SBU reports 200+ suspects charged. [SBU](https://ssu.gov.ua/en/novyny/sbu-povidomyla-pro-pidozru-ponad-200m-osobam-yaki-poshyriuvaly-informatsiiu-pro-robotu-ppo-ta-inshykh-syl-oborony) **[verified]**; enforcement cases centre on people posting footage of air-defence work and strike sites in near-real time. [Kyiv Independent](https://kyivindependent.com/why-theres-loads-of-video-of-israeli-air-defenses-and-none-of-ukraines/), [mind.ua](https://mind.ua/en/news/20257449-searches-conducted-on-individuals-who-shared-video-footage-of-air-defence-operations-on-social-media) **[verified summaries]**
- **Applicability to this project:** the law targets dissemination that aids Russian targeting; the enforcement pattern is individuals in Ukraine posting near-real-time footage. A US student publishing week-lagged, 50 km-aggregated satellite statistics is far from that pattern, and DeepState itself (a Ukrainian entity working with the MoD) publishes the control-of-territory layer daily. **Jurisdictionally it does not reach Jackson. Normatively, §1.2's lag-and-aggregate rules are the way to show the project respects the concern.**
- **Air-defence side piece:** the intercept-rate note uses Ukrainian Air Force daily communiqués (already public, aggregated by Ukraine itself). No locations. Fine.
- **Reputational sensitivity:** Ukrainian OSINT is a strong, opinionated community. Things that draw fire: implying DeepState is wrong; implying Ukraine is losing; "both-sides" language; using Russian toponyms (use Ukrainian transliterations: Pokrovsk, Kurakhove, Myrnohrad, Kupiansk). The DeepState–Khortytsia Makarivka dispute and the ISW Polymarket incident show how fast map-accuracy arguments turn personal. Describe control sources neutrally ("open-source assessments," "coded by") and avoid the word "truth."

### 4.2 Russia

- **Art. 207.3** ("fakes" about the armed forces, up to 15 years) and **Art. 280.3** (discrediting). In-absentia convictions of foreign-based journalists exist (Gessen, 8 years, 2024). [JURIST](https://www.jurist.org/news/2024/07/russia-court-sentences-russian-american-journalist-in-absentia-to-eight-years-over-spreading-false-information-on-armed-forces) **[verified]** Bellingcat and The Insider (2022) and Conflict Intelligence Team (2023) are "undesirable organizations." [Bellingcat statement](https://www.bellingcat.com/statement-on-the-designation-of-bellingcat-as-an-undesirable-organisation-in-russia/), [Mediazona on CIT](https://zona.media/news/2023/08/10/cit) **[verified]**
- **Realistic exposure for a US student publishing panel regressions:** essentially nil absent travel. **Do not travel to Russia, Belarus, or occupied territory while this is public; be cautious about transit through states with extradition cooperation with Russia.** This is already US State Department Level 4 advice regardless of the project.
- **Russian-language audiences:** the project will be read as pro-Ukrainian by default because it uses DeepState. That is fine; just do not editorialize.

### 4.3 US side

- No ITAR/EAR issue: all inputs are public, unclassified, non-US-government-controlled, and the method is published open science. **[standard; not a legal opinion]**
- Security-clearance adjudication (relevant for defense-tech roles): publishing open-source analysis of a foreign war is not a reportable issue. **Foreign contacts** created by the project (e.g., emailing DeepState, a Ukrainian reviewer) are ordinary professional contacts; keep a simple log of who, when, why, so an SF-86 can be filled honestly later. Do not accept data, money, or credentials from foreign entities.

---

## 5. Employer-perception risks

### 5.1 Does a null result read as failure?

Only if the headline is the null. Reframe hierarchy for the brief and the repo title:

1. **Lead with the positive, already-robust finding plus the new product:** "Front-band fire density is 5–17× the rear in every month; here is a quantified map of when and where that signal disappears."
2. **Second: the pre-registered lead-lag test and its honest answer** with equivalence bounds. "Fires co-move with fighting; they do not forecast next week's territorial change beyond momentum. We can rule out effects larger than X."
3. **Third: transfer.** "In Sudan (arid, event-based), the signal-to-noise is Y."

Interviewer-proofing: the one question that breaks "I predict Russian advances" is "what's your out-of-sample skill vs. a momentum baseline?" Under the reframe, the answer is in the brief.

What reads as maturity to Anduril/Palantir-type reviewers (from the feasibility verdicts and general experience of technical hiring): pre-registration, fixed effects with clustered SEs, placebo and reverse-direction tests, a Limits section, a reproducible pipeline, a correction policy, and sensor-coverage thinking. What reads badly: a flashy coefficient, a dashboard with no caveats, "AI" in the title.

### 5.2 Does a Ukraine-only piece read as narrow?

Yes, somewhat, for employers thinking about the Indo-Pacific or the Gulf. Mitigations ranked by cost:

- **Cheapest (half a day):** a **global blind-season map** — monthly probability of zero VIIRS detections by latitude band/climate zone from FIRMS 2019–21, showing where a thermal front monitor would work (Sahel, Sudan, Yemen, much of the Middle East) and where it would not (temperate winters, monsoon tropics). This is the generalization the user worries about, costs no new sources, and is a striking figure.
- **Medium (1 week):** the Sudan transfer test against UCDP GED.
- **Framing (free):** title and abstract about *the sensor and the method*, with Ukraine as the test case: "What a free thermal satellite feed tells an analyst about a war: a Ukraine test with a Sudan check."
- **Side piece** (intercept-rate reporting artefact) broadens the portfolio to "measurement forensics," which is theatre-agnostic.

### 5.3 Things that could hurt with specific employers

- **Anduril / neo-primes:** care about sensor fusion and failure modes; a coverage product is directly relevant. Risk: none.
- **Palantir:** cares about data provenance and multi-source fusion; the DeepState-vs-ISW disagreement analysis and licensing hygiene are features. Risk: none.
- **Government/IC-adjacent shops:** will notice if the project looks like it is trying to do targeting. §1.2 rules are the answer; say explicitly "this is an analyst-triage tool, not a targeting product."
- **Any employer:** a public pile-on thread with Jackson in it. See §6.

---

## 6. Personal risk profile for a student publishing on an active war

| Threat | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Partisan pile-on (pro-UA or pro-RU accounts reading a chart as a verdict on the war) | Moderate if promoted on X/Telegram; low on GitHub/LinkedIn | Low–moderate (stress, screenshot risk) | Publish on GitHub + LinkedIn + personal site; one neutral post; do not debate in replies; pin the Limits section; mute and move on |
| Methods takedown by a credentialed analyst | Moderate (this community reads carefully) | Moderate (reputational), but **positive if handled well** | Pre-registration, Limits, external review, correction policy; respond once, factually, and update the repo |
| Doxing / harassment | Low | High if it happens | Use real name but no address/phone/class schedule anywhere; separate project email; two-factor everywhere; audit people-search sites once; ICCT is studying pro-Russian doxing of pro-Ukraine foreigners ([ICCT Anti-Dox review, Dec 2024](https://icct.nl/sites/default/files/2024-12/Literature%20Review_Anti%20DOX.pdf)) **[existence verified; body not readable]** |
| Legal exposure in Russia (in absentia) | Very low for aggregate statistics | High only if travelling there | No travel to RU/BY/occupied territory; be cautious about extradition-cooperating states |
| Legal exposure in Ukraine | Negligible (jurisdiction, aggregation, lag) | — | §1.2 rules |
| Being quoted out of context by media | Low | Moderate | Brief has a one-paragraph "how to cite this" with the exact claims that are and are not supported |
| Clearance/background check friction | Very low | Low | Log foreign professional contacts; accept nothing of value from foreign entities |
| Time/scope blowout (the real risk) | High | High (nothing ships) | Fixed 6-week calendar with a ship-regardless date; Sudan test is cut first if behind |

---

## 7. Concrete mitigations checklist (do in week 1)

- [ ] Write `LIMITS.md` skeleton before any new analysis.
- [ ] Write `PUBLICATION_RULES.md` with §1.2 (sector-week only, 7-day lag, no point front-band data, no FRP/time tables, no event annotation).
- [ ] Register pre-analysis plan on OSF (secondary-data template); link in README. Lock Spec C and the equivalence bound.
- [ ] Email DeepState via the API request page: non-commercial research use of history API + publication of derived aggregates with attribution. Save the email.
- [ ] Register FIRMS MAP_KEY; note 5,000/10-min limit; record product (NRT vs SP) per year in a data manifest.
- [ ] Download UCDP GED 26.1 + Candidate 26.0.x; record the two required citations.
- [ ] Decide: no ACLED. Note why in `LICENSES.md`.
- [ ] `LICENSES.md` with per-source terms, URLs, and access dates; `ATTRIBUTION` block in README and dashboard footer.
- [ ] Project email address; 2FA on GitHub; audit personal info exposure once.
- [ ] Line up one methods reviewer and one subject-matter reviewer for week 4.
- [ ] Choose Ukrainian transliteration standard for place names; keep a gazetteer file.
- [ ] Draft the "how to cite / what this does and does not claim" paragraph.

---

## 8. Open items I could not verify

1. **ISW terms of use** (Cloudflare-blocked). Read in a browser; expected: attribution-with-link reuse of maps, no data download. Also check the item-level terms of the ArcGIS timelapse layers before any use beyond cross-checking.
2. **DeepState's position on research use.** License is silent; only an email settles it.
3. **FIRMS LANCE disclaimer URL** (404 today) and the exact VIIRS NRT dataset DOI.
4. **Whether the OSF secondary-data preregistration template is live in OSF Registries** or still only on the authors' OSF project.
5. **ACLED academic/student tier details** (truncated); irrelevant if ACLED is dropped.
6. **Dingemanse, Zhizhin, Cerra, *Sci Rep* 2026** body text (paywall redirect); read via the Payne Institute post or request from the authors — it is the closest prior work and must be cited and differentiated from (they use Nightfire; this project uses the active-fire product and a panel design).
7. **Nothing found** on OPSEC criticism of The Economist's daily point-level publication, which is itself evidence the norm tolerates far more than §1.2.

---

## 9. Go / no-go checklist

**GO if all of the following are true at end of week 1:**

- [ ] `PUBLICATION_RULES.md` adopted (aggregation ≥ sector-week, lag ≥ 7 days, no point-level front data, no event annotation).
- [ ] Pre-registration posted on OSF with one locked primary spec and an equivalence bound.
- [ ] DeepState permission email sent (reply not required to proceed with derived-only publication).
- [ ] UCDP, FIRMS, Natural Earth, OSM, Economist citations recorded; ACLED excluded.
- [ ] `LIMITS.md` skeleton exists with the ten items in §3.2.
- [ ] At least one reviewer tentatively lined up.
- [ ] Jackson is comfortable with: no travel to RU/BY while public; one neutral promotion post; no reply-debates.

**NO-GO / pause triggers:**

- DeepState explicitly refuses research use **and** ISW layers' terms also forbid derived use → pause and look for a third control source (e.g., Liveuamap, which is likely more restrictive; or hand-coded weekly front from ISW PDFs, which is laborious). Probability: low.
- Any plan to publish point-level or sub-weekly front-band detections → stop; that is the only version of this project with a real dual-use question.
- Scope creep past 6 weeks with no shipped artefact → ship the coverage product and the pre-registered test alone; cut Sudan.

**Verdict: GO.** The project is on the conservative side of established practice (Bellingcat, The Economist, Dingemanse et al.), the licensing has one soft spot (DeepState API) with a cheap fix (ask, and publish derived data only), and the reputational risk is best managed by the same things that make it a strong portfolio piece: pre-registration, limits, and review.

---

## Sources consulted

- DeepStateMap license: https://deepstatemap.live/license-en.html
- cyterat mirror (GPL-3.0): https://github.com/cyterat/deepstate-map-data
- Economist war-fire model (MIT/CC-BY-4.0): https://github.com/TheEconomist/the-economist-war-fire-model
- Economist methodology: https://econ.st/42IFlUE
- NASA FIRMS FAQ (citation, NRT vs SP): https://www.earthdata.nasa.gov/data/tools/firms/faq
- FIRMS MAP_KEY limits: https://firms.modaps.eosdis.nasa.gov/api/map_key/
- ACLED EULA (2025): https://acleddata.com/eula ; Content usage terms: https://acleddata.com/contentusage
- UCDP downloads (CC BY 4.0, citations): https://ucdp.uu.se/downloads/
- Natural Earth terms: https://www.naturalearthdata.com/about/terms-of-use/
- Bellingcat 2022 FIRMS guide: https://www.bellingcat.com/resources/2022/10/04/scorched-earth-using-nasa-fire-data-to-monitor-war-zones/
- Payne Institute, VIIRS Nightfire Ukraine (links Sci Rep 2026): https://payneinstitute.mines.edu/conflict-monitoring-with-viirs-nightfire-the-war-in-ukraine/
- ISW Polymarket edit incident: https://dev.ua/en/news/spivrobitnyk-isw-vnis-neuzhodzhenu-pravku-na-mapi-voiennykh-dii-v-ukraini-shcho-zbihlasia-z-vyplatoiu-po-stavkam-polymarket-1765881875
- Frontline mapping methods comparison: https://ukraine-war-analytics.com/analysis/frontline-mapping-methods.html
- SBU on Art. 114-2 enforcement: https://ssu.gov.ua/en/novyny/sbu-povidomyla-pro-pidozru-ponad-200m-osobam-yaki-poshyriuvaly-informatsiiu-pro-robotu-ppo-ta-inshykh-syl-oborony
- Kyiv Independent on air-defence filming ban: https://kyivindependent.com/why-theres-loads-of-video-of-israeli-air-defenses-and-none-of-ukraines/
- Russia Art. 207.3 in-absentia case: https://www.jurist.org/news/2024/07/russia-court-sentences-russian-american-journalist-in-absentia-to-eight-years-over-spreading-false-information-on-armed-forces
- Bellingcat "undesirable" statement: https://www.bellingcat.com/statement-on-the-designation-of-bellingcat-as-an-undesirable-organisation-in-russia/
- CIT "undesirable": https://zona.media/news/2023/08/10/cit
- Public-interest OSINT guidelines (2023): https://checkfirst.network/wp-content/uploads/2023/04/Guidelines-for-Open-Source-Intelligence-Organisations.pdf
- Secondary-data preregistration (van den Akker et al.): https://forrt.org/curated_resources/secondary-data-preregistration/
- ICCT anti-dox literature review: https://icct.nl/sites/default/files/2024-12/Literature%20Review_Anti%20DOX.pdf
