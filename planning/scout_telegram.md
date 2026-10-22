# Scout: Russian missile/drone strike data from Ukrainian Telegram (2022 → now)

**Written:** 2026-10-21 · **Mode:** scout only. Nothing was logged into and nothing large was downloaded. The only network calls were Kaggle metadata, a 4-byte range check on the Kaggle ZIP, GitHub API listings, and public `t.me/s/<channel>` preview pages (one page per channel; the `?before=` paging test was run on `kpszsu` only).

**Bottom line.** Don't scrape first. The Ivaniuk dataset (Kaggle `piterfm`) is already a hand-built, weekly-updated table of the Air Force's overnight summaries. It has `launch_place`, `target`, `launched`, `destroyed`, EW-lost and hit counts by weapon model, it runs from 2022-09 to 2026-10-17, and it **downloads without a Kaggle login** (verified today). Scraping Telegram adds two things on top of it: (a) the Air Force's real-time **track posts** ("Реактивний БпЛА на Козелець … із північного сходу"), which give town-level trajectories and timing, and (b) regional-administration **impact posts**, which give the city and district hit, the time, and the damage. Jackson can get (b), and most of (a), from public web previews without an account. A Telethon login is needed only for a clean, complete pull with message IDs, edits and views.

---

## 1. Existing structured datasets

| Dataset | URL | Coverage | Key fields | Update cadence | Licence | Download without login? |
|---|---|---|---|---|---|---|
| **Massive Missile Attacks on Ukraine** (Petro Ivaniuk) | https://www.kaggle.com/datasets/piterfm/massive-missile-attacks-on-ukraine | Oct 2022 (first rows 2022-09-28) → 2026-10-17 (v215) | `missile_attacks_daily.csv`: `time_start`, `time_end`, `model`, `launch_place`, `launch_place_details`, `target`, `target_main`, `carrier`, `launched`, `launched_details`, `destroyed`, `destroyed_details`, `not_reach_goal` (EW-lost/decoys, since Jul 2024), `border_crossing`, `still_attacking`, `num_hit_location`, `num_fall_fragment_location`, `affected_region`, `status_data`, `source` (post ID). `missiles_and_uavs.csv`: model reference (category, origin, NATO name, guidance, unit cost) | **Weekly** (versions every ~7 days; the last 8 run 2026-08-30 → 2026-10-17) | **CC BY-NC-SA 4.0** (non-commercial, share-alike) | **Yes.** `https://www.kaggle.com/api/v1/datasets/download/piterfm/massive-missile-attacks-on-ukraine` returns a 302 to a signed GCS ZIP (186 KB, `PK\x03\x04` verified). 916 KB unzipped |
| Mirror A / Mirror B of the above | github.com/hakerdimoha98-source/Missile-attacks-on-Ukraine; github.com/vetalist7/ukraine-attacks-analysis | to 2026-06-14 / 2026-04-19 | same | frozen | inherits CC BY-NC-SA | yes (already on disk in `~/D3/Conflict_Data_Feasibility/airdefense/data/raw/`) |
| Ukrainian air-raid sirens (Vadym Klymenko) | https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset | official alerts 2022-03-15 → now (raion level since Dec 2025); volunteer alerts 2022-02-25 → now (oblast) | region, started_at, finished_at (UTC), `naive` flag | **Daily** (last commit 2026-10-22 UTC) | MIT | yes. `official_data_en.csv` 31 MB, `volunteer_data_en.csv` 9 MB |
| Russian & Ukrainian war-related Telegram channels (Kyrychenko, Univ. Helsinki) | https://zenodo.org/records/16949193 (doi:10.5281/zenodo.16949193) | posts 2015-09 → 2024-03-26 | raw post texts, forwards, channel metadata (66k channels, 79.6M posts from 4,687 channels) | one-off | CC BY 4.0 | yes, but **49 GB** (8 text parts of 4.6–7.3 GB). It's unverified whether `kpszsu` and the regional channels are included; check `channels.csv` (16 MB) first. Raw text only, no strike fields |
| DiXi Group strikes on energy infrastructure | https://map.ua-energy.org/en/resources/12f3148d-841a-478d-b9ed-72bf0764b286 | to Aug 2024 | date, weapon type, subtype, launched, shot down | stopped | not checked | CSV/XLSX advertised (not fetched) |
| Airwars Shahed map | https://airwars.org/shahed-map/ | 2022-09 → 2023-08 (1,956 Shaheds) | strike area (oblast/city/town), date, source statements | stopped | none stated | **no CSV**; map only |
| CSIS Futures Lab Russian Firepower Strike Tracker | https://www.csis.org/programs/futures-lab/projects/russian-firepower-strike-tracker-analyzing-missile-attacks-ukraine | 2022-09 → | daily aggregates by weapon; **built on the Ivaniuk data** | dashboard | n/a | no download found; use Ivaniuk directly |
| ISIS (Institute for Science) monthly Shahed analyses | https://isis-online.org/isis-reports/monthly-analysis-of-russian-shahed-136-deployment-against-ukraine-updated | monthly | launched/intercepted per month, PDF tables | monthly (Aug 2026 report exists) | n/a | PDFs only |
| KAS / Kyiv Dialogue "Ukraine Air War Monitor" (Marcus Welsch) | https://www.kyiv-dialogue.org/en/news/newsreader/ukraine-air-war-monitor-vol-xvi.html | autumn 2022 → | monthly counts; underlying database of strikes on civilian targets | monthly | n/a | newsletter/PDF; database not public, so ask the authors |
| Ivaniuk's own GitHub | https://github.com/PetroIvaniuk/2022-Ukraine-Russia-War-Dataset | 2022 → | **losses only** (equipment and personnel), not strikes | daily | — | yes, but not relevant |

**Important caveat, from Ivaniuk's own description:** *"The Ukrainian Air Force has stopped reporting the number of some kind of missiles launched and intercepted since August 10, 2026."* No scraper can recover per-type launch and intercept counts after that date. The source is gone.

Known quality issues (from `~/D3/Conflict_Data_Feasibility/airdefense/SOURCES.md`): figures are UAF claims only; "destroyed" vs "EW-lost" definitions change in 2024–26; regional-command rows (PvK Pivden etc.) are mostly recon drones and partly double-count; weapon labels are combined ("Iskander-M/KN-23"); when only `destroyed` is published, `launched` is filled with a minimum value (`status_data` flags this).

## 2. Channels worth scraping

All handles were checked today against the public preview `https://t.me/s/<handle>` (title shown). The subscriber figures come from the preview and are approximate.

| Channel | Handle | What it gives | Credibility |
|---|---|---|---|
| Air Force of the AFU (Повітряні Сили) | `@kpszsu` (~916K; ~89.4k posts) | (1) morning summary: types, counts, **launch directions** (e.g. Kursk, Oryol, Millerovo, Primorsko-Akhtarsk, Chauda), shot down / locationally lost, hit locations; (2) real-time **track posts** all night: weapon class + town + heading ("Реактивний БпЛА на Козелець на Чернігівщині із північного сходу") | Primary official source and the basis of every dataset above. Defender-side claims; intercept counts are not independently verifiable; the category set changes over time; per-type counts are partly withheld since 2026-08-10 |
| General Staff | `@GeneralStaffZSU` | daily losses, sometimes strike totals | official; aggregate only |
| Air Command South / West | `@PvKPivden`, `@PvkZahid` | regional shoot-downs, mostly recon/tactical drones | official, but double-counts against `kpszsu`; keep it separate |
| Air Alert (official alert bot channel) | `@air_alert_ua` (~231K) | alert start/end per region | official system; better taken from the Klymenko CSV than scraped |
| Kyiv City MA | `@VA_Kyiv` | impacts, debris falls, districts, casualties in Kyiv | official, local, fast; early numbers get revised |
| Kharkiv ODA (Syniehubov) | `@synegubov` | impacts by city/district, weapon type often named (KAB, Iskander, Shahed) | official; good on weapon type |
| Odesa ODA (Kiper) | `@odeskaODA` | port/energy strikes | official; sometimes withholds locations (OPSEC) |
| Dnipropetrovsk ODA (Hanzha) | `@dnipropetrovskaODA` | strikes by hromada | official |
| Zaporizhzhia OVA (Semikin) | `@zoda_gov_ua` | strikes, KAB/artillery | official; front-adjacent, mixes artillery with missiles |
| Lviv OVA (Kozytskyi) | `@kozytskyy_maksym_official` | western strikes, energy | official |
| Suspilne News | `@suspilnenews` | regional reporting that aggregates oblasts | public broadcaster; secondary |
| monitor / monitorwar | `@war_monitor` (~964K), `@monitoringwar` | real-time tracking, **launch detections** (airfields, Tu-95 take-offs, Black Sea carriers) | volunteer monitoring; fast and usually right on direction, but unofficial, with no corrections log. Ivaniuk uses them for corrections only |

**Handles that did NOT verify** (wrong channel or squatter, so don't use them): `@pvkshid` (squatter), `@etryvoga` (102 subscribers, not the eTryvoga app), `@mykolaivskaODA` (357 subscribers). The real Mykolaiv OVA (Kim) and Air Command East channels still need to be found by hand. Avoid pro-Russian "launch" channels (e.g. Rybar) as a source of fact. If they are used at all, use them only as an attacker-side cross-check, labelled as such.

**Excluded from this project:** `@DeepStateUA` is wartime territorial-control data (C1 source family). Do not scrape it. Only its public landing page title was loaded during the handle check, and no posts were stored.

## 3. What Jackson has to do to scrape Telegram himself

Two routes:

**Route A: public web preview, no account (lightest).** `https://t.me/s/<handle>?before=<msg_id>` returns about 20 posts per page as HTML, with UTC timestamps and post IDs. Paging back works: `kpszsu?before=2000` returned posts dated 2022-09-28 → 2022-10-03. `t.me/robots.txt` returns 404 (no disallow). `kpszsu` would take about 4,500 pages, roughly 2.5 h at a polite 2 s/page. Limits: no edit history, media captions only, and some channels hide previews. Claude can write and run this with no sign-in from Jackson.

**Route B: Telethon with his account (complete, structured).**
1. Jackson logs in at https://my.telegram.org with his phone number. Telegram sends the code **inside the Telegram app**, not by SMS.
2. He opens "API development tools", creates an app (title e.g. "frontline-research", short name, no URL needed) and copies `api_id` and `api_hash`. The hash cannot be revoked, so treat it like a password.
3. He adds `TG_API_ID=` and `TG_API_HASH=` to `~/D3/Frontline_From_Space/.env`.
4. He runs the script once himself. Telethon asks for his phone, the login code (and his 2FA password if set), then writes a `.session` file. **That file is a full login to his account.** Add `*.session` to `.gitignore`, keep it out of OSF/Zenodo, and delete it when done.
5. After that, `client.iter_messages('kpszsu', reverse=True)` pulls about 100 messages per request. 89k posts is about 900 requests; with FloodWait handling and sleeps, that's under an hour per big channel and well under 1 GB of text for all channels above.

Practical risks: use his long-standing personal account, not a fresh or VoIP number (those get flagged). Don't join channels or send messages from the script. Respect `FloodWaitError` sleeps. Per the standing rules, the sign-in and code stay with Jackson; Claude writes the script, Jackson runs the first login.

**Effort to extract structured fields (Ukrainian text):**
- *Morning summaries* (`kpszsu`, ~1,500 nights): templated but the template changes several times (2022, mid-2024 EW category, 2025 "Gerbera/imitator" wording, 2026-08 per-type withholding). A regex per template era plus LLM-assisted extraction with validation **against the Ivaniuk table** (same source) takes about **2–3 days**. The gain over Ivaniuk is small: mostly precise post timestamps and the period after 2026-10-17.
- *Track posts* (`kpszsu` real-time, tens of thousands): short, formulaic `<weapon class> на <town> [<oblast>] [з/із <direction>]`. They need a Ukrainian gazetteer (GeoNames UA + KATOTTH codes) with inflected-case matching (на Козелець / Козельця) and disambiguation of duplicate town names by oblast. About **4–6 days** to a usable track table with about 85–90% geocoded. This is the genuinely new data: hourly town-level drone and missile paths.
- *Regional impact posts* (10+ channels): free text with many styles, casualty updates and revisions. An LLM extraction pass (date, place, weapon if named, hit/debris, infrastructure type) plus a manual check of a 200-post sample takes about **1 week**. This is the only source of **impact points** that could feed a FIRMS recall test.

## 4. ToS and ethics

- **Telegram API Terms** (https://core.telegram.org/api/terms): each developer must use their own `api_id`. §1.5 **prohibits using data obtained from Telegram to train or fine-tune AI/ML models**. Using an LLM for inference-time extraction is not training, but don't fine-tune on the corpus, and say so in the methods. Non-compliance leads to notice, then API access is cut after 10 days. No numeric rate limit is published, so obey FloodWait.
- **Public official channels only.** No private groups, no comments/discussion threads, no user-level data. Strip `from_id`/author fields. Official posts are government communications. Regional admin posts sometimes name casualties, so don't publish names.
- **OPSEC.** Real-time track and impact data at point/hour resolution is exactly what Russian targeting cells use for battle-damage assessment. Follow D16: publish at oblast-day or cell-week resolution, with a lag of 7 days or more. Never release a geocoded point table of impacts or a "which air-defense sector missed" map. Ukraine has prosecuted people for filming impacts and air-defense positions; the same logic applies to republishing derived points.
- **Licences.** The Ivaniuk data is NC-SA, so derived tables must be shared under CC BY-NC-SA, which conflicts with the README's "derived data CC BY 4.0". Either keep Ivaniuk-derived outputs in a separately licensed folder or publish aggregates only with attribution. Sirens are MIT; Kyrychenko is CC BY 4.0.
- **Attribution and bias.** Every number is a defender claim. Frame intercept rates as "reported by the UAF", not as measured.

## 5. Fit with the prereg gate (set V)

- **Allowed to download pre-tag:** yes. None of this is C1 (FIRMS fires or control maps), T1 or T2. It is wartime **event** data, the same family as V, and contains no territorial-control geometry.
- **But it is not V as currently frozen.** PREREG §2 lists V's sources as GeoConfirmed and Bellingcat TimeMap, and §3 defines an Event as "a GeoConfirmed or Bellingcat record with date and coordinates", with detection meaning a fire **within 1 km**. Ivaniuk rows and morning summaries have **no coordinates** (oblast/city strings), so they cannot enter H1/H2 as V events. Only geocoded regional impact posts could, and only at town-centroid precision (much coarser than 1 km).
- **Recommendation:**
  - (a) Use the Ivaniuk table for the **air-defense side note** (exploratory, D19 already cuts it from the core).
  - (b) If impact posts are to feed recall, **amend PREREG before tagging**. Add a "V-tg" source with its own looser match rule (e.g. same town polygon ±12 h) and report it as a secondary recall estimate, not pooled with GeoConfirmed.
  - (c) Otherwise label all Telegram-derived data **exploratory** (§6) so nothing confirmatory depends on it.

## 6. Suggested next steps (no login needed)

1. Pull the Ivaniuk ZIP anonymously into `data/raw/airdefense_ivaniuk/` (186 KB) with a fetch script modelled on `fetch_baseline.py`.
2. Pull the Klymenko sirens CSVs (about 40 MB English pair) into `data/raw/sirens/` to get alert timing per oblast/raion.
3. Fetch the Kyrychenko `channels.csv` (16 MB) only to check whether `kpszsu` and the regional channels are in the 2024 corpus. Skip the 49 GB of texts.
4. Write a Route A preview scraper for `kpszsu` track posts if the town-level trajectory layer is wanted, then decide on Route B only if previews prove incomplete.
