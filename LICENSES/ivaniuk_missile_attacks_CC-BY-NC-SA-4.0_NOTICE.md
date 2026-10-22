# Massive Missile Attacks on Ukraine (Petro Ivaniuk, Kaggle `piterfm/massive-missile-attacks-on-ukraine`)

Source: https://www.kaggle.com/datasets/piterfm/massive-missile-attacks-on-ukraine (version 215, retrieved 2026-10-22 via the public
download endpoint, no login). Files: `missile_attacks_daily.csv`, `missiles_and_uavs.csv`, stored under `data/raw/ivaniuk_missile_attacks/`.

Licence: **CC BY-NC-SA 4.0** (Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International),
https://creativecommons.org/licenses/by-nc-sa/4.0/. Attribution: "Petro Ivaniuk, Massive Missile Attacks on Ukraine (Kaggle)".
The author compiled it by hand from the Air Force Command of the UA Armed Forces and General Staff public posts.

How it is used here: as a cross-source check of our own regex extraction of the Air Force nightly summaries
(`scripts/telegram/22_extract_summaries.py` -> `data/derived/telegram/national_night.csv`). The derived CSV carries the
Ivaniuk per-night totals in columns prefixed `ivaniuk_`. Anything redistributed with those columns is non-commercial and
must stay under CC BY-NC-SA 4.0 (ShareAlike); the rest of the project's data licence does not override this. Note the
author's own caveat: the Air Force stopped reporting some per-type missile counts from 2026-08-10 (`status_data = hidden`).
