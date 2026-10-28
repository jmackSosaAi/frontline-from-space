# Front line from space

**How reliable a witness is a free thermal satellite feed (NASA FIRMS / VIIRS) to a ground war, and when is it blind?**

Ukraine 2022–2025 is the test case; Nagorno-Karabakh 2020 and Sudan 2023– are out-of-sample checks. The project measures how often FIRMS catches a confirmed strike, models why it misses, corrects the fire series for what the sensor could not see, and only then re-asks whether fires lead territorial change.

Status: pre-registered (`prereg-v1`, 2026-10-22; OSF registration https://osf.io/xd2zj/); confirmatory tests scored; first paper draft in `paper/draft_v1.md`. Ship date: 2026-11-10.

## Results (draft, 2026-10-27)

**Blindness map.** FIRMS caught 5.0% of 14,736 held-out geolocated strike and battle events (H1 supported): 7.4% in clear summer nights, 0.06% in cloudy or snowy winter days. A same-place ±7-day placebo hits 3.8%, so most of the raw match rate is background fire (exploratory). The pre-registered detection model reached AUC 0.737, short of 0.75 (H2 not supported; an exploratory v2 built afterwards reaches 0.765). Two satellites 30–70 min apart under clear sky agree on 53.6% of fires (H3 supported). The sensor's small-fire floor is 3.8× higher on summer days than winter nights (H14 supported). Losing S-NPP cuts recall by 0.7 pp (H8, descriptive). Russian gains did not concentrate in blind weeks: 21.8% vs the 30% predicted (H4 not supported). In Karabakh and Sudan recall was 12.5% and 2.9%, inside the ±15 pp band (H7 supported, weak: the model's calibration did not transfer).

**What fire still shows.** Front fires run 2.1× the pre-war same-week baseline, not 3× (H5 not supported). Fires do not lead Russian gains at a meaningful size: raw inconclusive (H6), observability-corrected inside the pre-registered smallest effect of interest (H6b, equivalence). Jackson's directional hypotheses H9–H11 were not supported; H12 (Kyiv) is labelled "opposite" but reads as a period-level association, not timing; H13 (exploratory) is inconclusive.

Verdicts: `data/derived/results/verdicts.json`. Deviations: `DEVIATIONS.md`. Figures and captions: `figures/`.

- `DESIGN.md` — every design decision, the alternatives, and why
- `PREREG.md` — hypotheses, tests and predictions, frozen before confirmatory data were downloaded (tag `prereg-v1`)
- `data/MANIFEST.json` — every raw file: URL, bytes, SHA-256, retrieval timestamp (raw data are not committed; re-fetch with `scripts/`)
- `planning/` — scouting notes and the three plan drafts that preceded `DESIGN.md`

Code: MIT. Derived data: CC BY 4.0. Raw data remain under their sources' licences; no DeepState or ISW geometry is redistributed. Contact: jmackney@uchicago.edu
