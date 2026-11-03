# Telegram extraction QA: triage + hand-check plan

Written 2026-10-27. Goal: an independent, defensible error rate for the Telegram layer (what the paper reports as
extraction accuracy) with as little human reading as possible. Human checkers are research assistants (RAs).

## Why humans at all
The extraction was done by a model. A second model grading it is not independent: both tend to make the same mistakes
(an ambiguous village name, a casualty count from the previous day), so they would agree and both be wrong. The paper's
accuracy number must come from people. Machines only decide *where people look*.

## Method
1. **Sample** (done, `90_qa_sample.py`, seed 20261014): 200 extracted incidents stratified by channel, 50 posts where
   the model found nothing, 500 typed posts.
2. **Triage** (`91_qa_triage.py`). Each incident row gets
   - rule checks (no model): the place word appears in the post; the geocoder found exactly one settlement; nonzero
     casualty counts appear as digits or with a casualty word; the weapon word appears; the event date is within 2 days
     of the post;
   - a second, independent extraction by a different model (`llm.MODEL_ADJUDICATE`, same prompt and schema), compared
     field by field.
   A row is **agree** only if every rule passes and the second model matches on every field; otherwise **iffy**.
   Empty-list posts: agree if the second model also finds nothing. Typing: no triage, a random 100.
   Rules-only dry run on 2026-10-27: 140 agree / 60 iffy (iffy reasons: place not unique in geocoder 34, place word
   not found 26, date 1). The model pass will move more rows to iffy.
3. **RA packet** (written by step 2, `data/interim/telegram/qa/ra_packet/`): all iffy rows + a random **audit** of 30
   agree rows, shuffled together, bucket hidden from the RAs (`_key.csv` stays with us). Expected size ≈ 90–140
   impact rows + 50 empty-list posts + 100 typing rows.
4. **Scoring** (`92_qa_score.py`): per field, accuracy in each bucket, combined into one estimate for the full sample
   weighted by bucket size, 95% intervals. Two RAs on the same row: "n" from either counts (conservative) and the row
   is listed for adjudication.

## Decision rules (fixed before any RA sheet is filled)
- **Agree label trusted** for a field if the 30-row audit finds **no** errors in it (95% upper bound on error ≈ 11%).
  One or more errors → that field's agree label is not trusted: RAs check that field on every agree row, and the
  accuracy is recomputed on the full set.
- **Paper threshold**: we report every field's accuracy whatever it is. If place accuracy < 85% or casualty accuracy
  < 85%, the Telegram match results in the paper are labelled "low-confidence extraction" and the extraction is
  revisited (prompt or geocoder) before any further use. A bad result is a finding, not wasted work.
- **Inter-rater check**: both RAs code the same first 20 impact rows (`imp-001`…`imp-020`). Report raw agreement;
  if below 85%, the guide is clarified and the disagreements adjudicated by Jackson before scoring.

## Running it
```
# after triage, make the packet compare-and-click: English translation of every post (machine, labelled), AI fields in
# English, yes/no for every question, .xlsx copies with dropdowns
# .venv/bin/python -I scripts/telegram/93_qa_translate.py   (run right after 91; refuses to run twice)
.venv/bin/python -I scripts/telegram/91_qa_triage.py --dry-run    # cost + example requests, no network
.venv/bin/python -I scripts/telegram/91_qa_triage.py --run        # second-model pass (~246 posts) + RA packet
# give RAs: ra_impacts.csv / ra_empty.csv / ra_typing.csv + tools/qa_checker.html + docs/RA_GUIDE.md
# put returned files (e.g. ra_impacts_AB.csv) back in data/interim/telegram/qa/ra_packet/
.venv/bin/python -I scripts/telegram/92_qa_score.py               # -> data/derived/telegram/qa/REPORT.md
```

## Data handling
RA sheets contain raw public Telegram post text. Share them privately (direct file transfer or a private university
drive folder), never on a public link, GitHub, OSF or Zenodo; RAs delete their copies when done. `_key.csv` is never
shared. Only the aggregate `REPORT.md` / `qa_scores.csv` are published.

## First returns (2026-11-03): rater AT (Role B), rater PD (Role A) pending
Ingested `ra_{empty,typing,impacts}_AT.csv` (complete: 35/35, 100/100, imp-001..020). Raw `92_qa_score.py` output is
misleading because three questions in the guide did not match the extraction rules (`prompts/impacts_v1.md`):
- **Date/time** (6/20 "yes"): the packet never shows the post's publication date, and the AI's date comes from it, so
  the rater answered "no date in the text". Not scoreable by humans as asked; use the rule check (event date within 2
  days of the post) instead, and tell PD to answer Yes unless the post states a different date or time.
- **Empty posts** (22/35 "has a strike"): ~20 of the 22 are daily or weekly statistics lists ("341 strikes on 21
  settlements..."), aftermath, or commemoration posts, which the prompt tells the AI to skip on purpose. The guide asked
  "a strike at a named place" and did not mention that exclusion. True misses by the prompt's own rule: about 0-2
  (emp-021, emp-026 lead with a casualty line). Finding for the paper either way: the Telegram layer drops front-line
  statistics lists by design, so it undercounts shelling of front-line settlements.
- **Casualties** (15/20): the prompt puts a post-wide casualty total on one incident and leaves the others null, which
  the packet shows as "none reported"; some "no" answers are that convention, not an error. Check per row against
  sibling incidents of the same post before scoring.
Real-looking errors so far: place 2/20, weapon 3/20 (all "several weapons named, none tied to this strike"), missed
incidents in 3/20 posts. Category (typing) 76/100; disagreements mostly launch vs track vs daily_summary edge cases.
Plan: adjudicate the three mismatched fields against the prompt rules (Jackson approves the adjudication list), score
after PD returns, log the guide mismatch in DEVIATIONS.md.
