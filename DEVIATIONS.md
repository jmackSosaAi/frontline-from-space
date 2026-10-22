# Deviations from prereg-v1

Dated log of every change made after `PREREG.md` was signed and tagged `prereg-v1` (2026-10-22). Newest last.

## 2026-10-22: Telegram public posts added as an additional validation-event source

- **What:** after prereg-v1, public Telegram posts from these official and monitoring channels were added as an additional validation-event source (manifest set `V-telegram`) for H1, H2 and H12: `@kpszsu` (Air Force of the AFU), `@VA_Kyiv` (Kyiv City MA), `@synegubov` (Kharkiv ODA), `@odeskaODA` (Odesa ODA), `@dnipropetrovskaODA` (Dnipropetrovsk ODA), `@zoda_gov_ua` (Zaporizhzhia OVA), `@kozytskyy_maksym_official` (Lviv OVA), `@war_monitor` and `@monitoringwar` (volunteer monitoring, unofficial).
- **How:** no-login public web preview `https://t.me/s/<handle>?before=<msg_id>` (`scripts/fetch_telegram_preview.py`), one request at a time, ~2 s between pages, contact address in the User-Agent. Stored fields: channel, msg_id, date_utc, text, views, has_media, forwarded_from_channel. No user or author data. `@DeepStateUA` (territorial-control data) is excluded and was not scraped.
- **Scope:** not used to define any confirmatory outcome. The confirmatory set V stays as frozen in PREREG §2–§3 (GeoConfirmed and Bellingcat). Any Telegram-derived recall estimate is reported separately as secondary/exploratory and is not pooled with V.
- **AI use:** an LLM is used only for inference-time extraction (date, place, weapon, hit/debris) from post text. No model is trained or fine-tuned on the corpus (Telegram API Terms §1.5).
