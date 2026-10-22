# Telegram pipeline: 359k posts → strike signal

**Written:** 2026-10-22 · **Status:** design, nothing built yet · **Prereg status:** everything here is **exploratory** (post-tag source addition, see `DEVIATIONS.md`). It feeds H1/H2 validation events and H12 (Kyiv), and gives new descriptive products (launch waves, launch-to-impact timing). It never defines a confirmatory outcome.

## 0. What the data actually looks like

| Channel group | Posts | Median length | Nature |
|---|---|---|---|
| Air Force `kpszsu` | 88.5k | 59 chars | Templated alerts. Emoji = type code: 🛵/🏍/🛸 drone tracks (~36k), 🚀 launches (~10k: `Пуск КАБ на Сумщину`), ⚠ warnings, 📢 all-clear, 🛫/🛬 aviation activity, ☄️ ballistic. Plus **1,147 morning summaries** (>900 chars): counts by weapon type, launch directions, destroyed/EW-lost, number of hit locations. |
| Monitors `war_monitor`, `monitoringwar` | 74.7k | 59 chars | Templated, region-prefixed (`Київ —`, `Одещина —`). Launch intel: Ту-95 (755 posts), МіГ-31 (826), carriers/ships `носії` (1,854), take-offs `зліт` (729), with "time to Ukraine" estimates. Also 💥 explosions, ⚪️ all-clear, 📡 radar, timestamped night logs. |
| Regional admins (Kyiv, Kharkiv, Odesa, Dnipro, Zaporizhzhia, Lviv) | 195k | 180–600 chars | Prose. Mix of alert templates (🟢/📢), **daily impact reports** (`📍Харківщина. 11 жовтня … близько 05:00 ворог обстріляв із РСЗВ … по с. Борова … Пошкоджено 2 житлових будинки`), and noise (politics, aid, TV). Pre-war 2020–21 posts exist. |

Two facts drive the design: (a) rules can type and parse ~90% of Air Force + monitor posts; (b) only the regional prose needs an LLM, and only after a cheap filter.

## 1. Principles

1. **Raw is immutable.** `data/raw/telegram_api/*.jsonl` is never edited. Everything downstream is regenerable from it.
2. **Deterministic before probabilistic.** Regex/emoji rules first; LLM only on what rules can't type or parse. Every LLM call is cached by `(msg_id, prompt_version)` so re-runs are free and reproducible.
3. **Every row carries its provenance.** Each extracted event lists the `msg_id`s it came from. A reviewer can click back to the post.
4. **Event time ≠ post time.** Summaries posted at 11:00 describe the previous night; impact reports say "близько 05:00". Extract `event_time` when stated, else `post_time` with `time_is_post_time=1`. Store UTC and Europe/Kyiv.
5. **Source tiers, fixed up front.** A = official impact report (regional admin, Air Force summary); B = official track/launch post (Air Force); C = volunteer monitor. Monitor posts are never evidence that something *hit*; they are evidence of *launch timing and direction*.
6. **Privacy and terms.** Strip names of casualties; publish aggregates only (cell-week, oblast-day, national-week), never raw text. LLM used for inference only; no fine-tuning on the corpus (Telegram API Terms §1.5). Raw posts stay off GitHub/OSF/Zenodo.
7. **Schemas fixed before extraction starts.** The tables in §3 are the contract; the taxonomy in `scripts/telegram/taxonomy.yaml` is the vocabulary. Changing either after QA is a dated note in this file.

## 2. Layers

```
L0 raw        data/raw/telegram_api/<ch>.jsonl                 immutable
L1 normalize  data/interim/telegram/posts.parquet              one table, all channels, war period only
L2 type       data/interim/telegram/posts_typed.parquet        post_type + rule/llm flag + confidence
L3 extract    data/interim/telegram/extract/{tracks,launches,summaries,impacts}.parquet
L4 resolve    same tables + geo + canonical weapon/oblast codes
L5 link       data/derived/telegram/strike_events.parquet, launch_waves.parquet
L6 aggregate  data/derived/telegram/*_week.csv (publishable)
L7 QA         data/derived/telegram/qa/                        hand-check samples, precision/recall, cross-source agreement
```

### L1 Normalize (`00_normalize.py`)
One row per post. Columns: `channel, msg_id, ts_utc, ts_kyiv, date_kyiv, text, text_norm` (unicode NFC, emoji kept, whitespace collapsed), `n_chars, has_media, edit_ts_utc, fwd_from, lead_emoji` (first grapheme if emoji), `year`. Drop posts before 2022-02-24 and empty-text media posts (keep a count). Output ~340k rows.

### L2 Type (`10_type_rules.py`, `11_type_llm.py`)
`post_type ∈ {track, launch, launch_intel, alert, all_clear, aviation_activity, daily_summary, impact_report, ua_strike_on_ru, other}`.
- Rules: emoji code + a dozen regexes per channel (`^🛵|^🏍|^🛸` → track; `^🚀\s*Пуск|^☄` → launch; `Ту-95|Ту-22|МіГ-31|носі[їй]|зліт` → launch_intel; `^⚠.*Увага|тривог` → alert; `^📢.*Відбій|^⚪|^🟢` → all_clear; `^🛫|тактичної авіації` → aviation_activity; `У ніч на|ЗНЕШКОДЖЕНО` + len>700 → daily_summary; regional + `обстріл|удар|влучан|пошкоджен|загину|поранен` → impact_report candidate).
- Coverage target: rules type ≥90% of Air Force + monitor posts with ≥98% precision on a 300-post check. Residual + all regional candidates go to the LLM typer (Haiku-class, fixed labels, one call per post, cached).
- Columns added: `post_type, type_method ∈ {rule, llm}, type_conf`.
- **Result (2026-10-22):** rules typed 94.95% of AF+monitor posts, precision 287/300. LLM typer (`claude-haiku-5-5`, effort low, `type_v1`) ran on the 36,200 residual: 8,187 AF/monitor untyped + 28,013 regional candidates; 0 failed, 0 refusals, ~$2.20 (output ran ~22 tok/call, not the 120 assumed). Confidence: 27.0k high / 7.7k medium / 1.5k low. Regional candidates → 17,960 `impact_report`, 8,585 `other`, 1,059 `daily_summary`. Hand-check: 25/25 impact_report plausible, 14/15 `other` correct. The 36,781 regional posts with no strike keyword were never sent (decision: keep out). Outputs `posts_typed_llm.parquet`, `posts_typed_final.parquet`.
- Both LLM scripts take `--batch` (Message Batches API, −50%; results land in the same `llm_cache/`, so batch and sync runs are interchangeable). Impact extraction (`impacts_v1`, `claude-sonnet-5-5`) submitted as one batch of 17,956 on 2026-10-22; batch ids in `data/interim/telegram/extract/batch_ids.tsv`.

### L3 Extract (`20_extract_tracks.py`, `21_extract_launches.py`, `22_extract_summaries.py`, `23_extract_impacts.py`)
Separate script and schema per type; each is small and testable.

| Table | Rows (est.) | Method | Key fields |
|---|---|---|---|
| `tracks` | ~40k | regex | `ts, channel, weapon_class {shahed, jet_uav, recon_uav, cruise, ballistic, kab, unknown}, count, oblast_raw, settlement_raw, heading_raw, text_span` |
| `launches` | ~12k | regex + LLM fallback | `ts, channel, weapon_class, launch_site_raw (Kursk, Bryansk, Belgorod, Black Sea…), target_oblast_raw, count` |
| `launch_intel` | ~4k | regex + LLM | `ts, channel, platform {Tu-95, Tu-160, Tu-22M3, MiG-31K, ship, submarine, ground}, n_platforms, location_raw (Caspian, Engels, Olenya, Saratov, Black Sea…), status {takeoff, airborne, launch_likely, launch_confirmed, landed}, eta_minutes` |
| `summaries` | 1,147 | regex-heavy, LLM fallback | `night_date, total_launched, by_type[{type, count}], launch_directions[], destroyed_total, shot_down, ew_lost, hit_locations_n, debris_locations_n, main_target_oblasts[]` |
| `impacts` | ~15–30k | LLM (strict JSON schema) | `event_ts (or null), time_is_post_time, oblast_raw, raion_raw, settlement_raw, weapon_raw, target_type {residential, energy, industrial, military, transport, agri, other, unknown}, killed, wounded, damage_text_short, is_debris_only, confidence` |

LLM rules: one post → one JSON object validated against a schema; temperature 0; prompt versioned; output cached in `data/interim/telegram/llm_cache/<prompt_version>/<channel>.jsonl`. A post with several incidents yields several `impacts` rows.

### L4 Resolve (`30_resolve.py`)
- **Weapon taxonomy** (`taxonomy.yaml`): Шахед/Shahed/Герань/"ударний БпЛА" → `shahed`; Х-101/Х-555/Калібр/Іскандер-К → `cruise`; Іскандер-М/KN-23/С-300 (ground-attack) → `ballistic`; Кинджал → `kinzhal`; КАБ → `kab`; etc. Keep `weapon_raw` alongside.
- **Oblast canon**: Харківщина/Харківська обл./Харків → `UA-63` (ISO 3166-2). 27 regions, hand table.
- **Settlement geocoding**: match `settlement_raw` (+ oblast, + raion) to **VIINA's 33,141-settlement tessellation** (`gn_UA_tess.geojson`, already on disk) first, GeoNames UA second. Ukrainian declensions handled by stemming the last 1–3 chars and matching within the stated oblast. Store `geo_method, geo_conf, lat, lon, h3_r5`. Unmatched → null, flagged, never guessed.
- **Launch sites**: small hand gazetteer (Engels, Olenya, Shaykovka, Soltsy, Millerovo, Shatalovo, Kursk, Oryol, Bryansk, Primorsko-Akhtarsk, Chauda, Cape Chauda, Caspian Sea, Black Sea, Sea of Azov) with coordinates.

### L5 Link (`40_link_events.py`)
- **`strike_events`**: cluster `impacts` reporting the same thing. Rule: same settlement (or same raion if no settlement) and event_ts within ±3 h → one event. Keep `source_msg_ids[]`, `n_sources`, `tier` (best source tier present), `channels[]`. Air Force summary hit counts attach to the night, not to events.
- **`launch_waves`**: a wave starts with a `launch_intel` or `launch` post and ends at the next all-clear with no new launch/track for 2 h. Each wave: `wave_id, start_ts, end_ts, platforms[], weapon_classes[], n_tracks, oblasts_tracked[], n_impacts_linked, summary_row (night_date)`. Links every track/impact/alert inside its window.
- **Launch-to-impact**: for each wave, first launch_intel ts → first impact ts, by weapon class. New descriptive product.

### L6 Aggregate (`50_aggregate.py`), the publishable layer
- `kyiv_strikes_week.csv`: ISO week × {n_waves_reaching_kyiv, n_impacts_tier_A, n_tracks_toward_kyiv, n_alert_hours} — H12 input, replaces/complements FIRMS Kyiv fires.
- `impacts_cellweek.csv`: H3 res-5 × ISO week × tier × weapon_class → counts. Joins the FIRMS panel for an exploratory "fires where strikes were reported" check.
- `national_night.csv`: from `summaries` (one row per night) — benchmark against Ivaniuk.
- `launch_waves_week.csv`: waves per week by platform/weapon; `waves × front movement` for the coordination question in H12.
- `firms_match.csv`: for each tier-A impact with coordinates, nearest FIRMS detection within 1 km on the next overpass window (±12 h), with the observability covariates → feeds H1/H2 as extra validation events (labelled as the Telegram source).
- All published aggregates ≥ cell-week or oblast-day, ≥7-day lag, per PREREG §7.

### L7 QA (`90_qa_sample.py`)
- Stratified hand-check: 50 posts per post_type (seed 20261014) → typing precision/recall.
- 200 `impacts` rows → field-level accuracy (place, weapon, target_type, casualties) checked against the post text.
- Cross-source agreement: `summaries` vs Ivaniuk (counts by night, should agree ≥95% on launched/destroyed where both exist); `alert`/`all_clear` vs sirens CSV (timing within 2 min); `strike_events` vs Bellingcat/GeoConfirmed (same place ±1 day).
- Report `qa/REPORT.md` with the numbers. They go in the methods section as the extraction error rates.

## 3. Build order (by payoff ÷ effort)

| # | Step | Posts | Method | Output | Effort |
|---|---|---|---|---|---|
| 1 | L1 normalize + L2 rules | 359k | code | typed posts; coverage report | ½ day |
| 2 | `summaries` (Air Force nightly) | 1,147 | regex | `national_night.csv` validated against Ivaniuk | ½ day |
| 3 | `launch_intel` + `launches` + waves | ~16k | regex + small LLM | `launch_waves` | 1 day |
| 4 | `tracks` | ~40k | regex | geography of threats; Kyiv series | ½ day |
| 5 | L2 LLM typing of regional posts | ~195k → ~40–60k candidates | Haiku-class | `impact_report` set | ½ day + API cost |
| 6 | `impacts` extraction + geocode | ~40–60k | Haiku/Sonnet-class, cached | `strike_events`, `impacts_cellweek`, `firms_match` | 2 days |
| 7 | L7 QA + report | — | hand + code | error rates | 1 day |

Steps 1–4 need no LLM and produce the launch-wave product on their own. Step 6 is the expensive one and the one worth doing carefully.

**LLM budget (step 5–6):** ~60k posts × ~400 tokens in + ~150 out ≈ 33M tokens. Haiku-class for typing, Sonnet-class for extraction on the ~20k that survive typing. Low tens of dollars. Cache makes every re-run free.

## 4. Layout

```
scripts/telegram/
  taxonomy.yaml           emoji codes, weapon classes, oblast canon, launch-site gazetteer
  00_normalize.py
  10_type_rules.py        11_type_llm.py
  20_extract_tracks.py    21_extract_launches.py   22_extract_summaries.py   23_extract_impacts.py
  30_resolve.py
  40_link_events.py
  50_aggregate.py
  90_qa_sample.py
  llm.py                  one cached, schema-validated call wrapper (prompt_version in path)
data/interim/telegram/    L1–L4 + llm_cache/   (gitignored)
data/derived/telegram/    L5–L6 aggregates + qa/   (committed: CSVs are aggregates only)
```

Everything reads `.env` for keys; nothing prints them. Each script is idempotent and writes a `_meta.json` (inputs' hashes, prompt_version, row counts) next to its output.

## 5. Known traps

- **Album posts**: photo albums take several msg_ids with one caption; the empty-text ones are dropped at L1 (count logged).
- **Edited posts**: Telegram gives the edited text only; casualty numbers in regional posts are routinely revised upward. Record `edit_ts_utc`; treat casualties as "as last edited".
- **Declensions**: `на Козелець`, `у Козельці`, `Козелецького району` are the same place. Stem + oblast-constrained matching; test on 200 hand-labelled strings before trusting it.
- **Oblast ≠ city**: `Київ` (city) vs `Київщина` (oblast). Keep them distinct; H12 uses the city.
- **OPSEC withholding**: officials often omit exact locations of military/energy hits. The `impacts` set under-reports those target types non-randomly. State it; never "fill in".
- **Category drift**: the Air Force changed how it counts (e.g. "decoy drones" added, per-type counts partly withheld since 2026-08-10). `summaries` keeps `by_type` raw; comparisons across the break are flagged.
- **Timezone**: Kyiv switches DST; use `Europe/Kyiv` via zoneinfo, never a fixed offset.
- **Monitor rumours**: tier C only. Never promoted to A by repetition across monitor channels.
