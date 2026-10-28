# Research assistant guide: checking AI-extracted strike reports

Thank you for helping. This takes about 2–3 hours in total. You do not need to know Ukrainian.

## What this is
An AI read about 18,000 posts from official Ukrainian regional Telegram channels (governors, city administrations) and
pulled out each reported strike: where it hit, the weapon, what was hit, casualties, and when. Your job is to check a
sample of its work against the original post. Your answers become the accuracy numbers in a research paper, so the
only thing that matters is being careful and honest. "No" answers are just as useful as "yes."

## What you get
- `qa_checker.html`: a page that runs in your browser, offline. Nothing is uploaded.
- One or more sheets: `ra_impacts.csv`, `ra_empty.csv`, `ra_typing.csv`.

## How to work
1. Open `qa_checker.html` in Chrome, Safari or Firefox (double-click it). Type your initials. Choose a sheet.
2. Left side: the original post. Click **Copy post text** and paste it into [DeepL](https://www.deepl.com/translator)
   or Google Translate (Ukrainian → English). Or click **Open in Telegram** and use its translate button.
3. Right side: what the AI extracted, and the questions. Answer each one with **Yes** or **No** (keys `Y` / `N`).
4. Use **Next** / **Prev** (arrow keys) to move. Progress saves automatically in your browser.
5. When finished, click **Save CSV** and send the downloaded file (e.g. `ra_impacts_AB.csv`) back. If you stop
   halfway, Save CSV anyway and send it; you can reload it later and continue.

## The questions

### `ra_impacts`: one AI-extracted strike per row
Some posts report several strikes; each row is **one** of them (the place shown tells you which).
| Question | Answer Yes if… |
|---|---|
| Place correct? | the settlement (or district if no settlement) is where the post says this strike hit. Spelling/transliteration differences and grammatical endings (Харків / Харкові) are fine. If the post deliberately hides the place and the AI marked `location_withheld`, that is correct. |
| Weapon correct? | the weapon matches the post: Shahed/drone, missile (ballistic, cruise, Kinzhal), artillery/shelling, KAB/guided bomb, FPV drone, MLRS. If the post names no weapon and the AI left it blank, that is correct. |
| Target type correct? | the category fits what was hit: residential (homes, apartment blocks), energy (power, gas, fuel), industrial (factories, enterprises), military, transport (roads, rail, port), agri (farms, grain), other, unknown. |
| Killed / wounded correct? | both numbers match the post **for this strike**. Blank or 0 is correct if the post reports none. |
| Date / time correct? | the date (and time if given) is when the strike happened. "Overnight" posts usually mean the night before the post. |
| Strikes the AI missed | how many **other** strikes this post reports that the AI did not list (`n_incidents_in_post` shows how many it found). Usually 0. |

### `ra_empty`: posts where the AI found **no** strike
Answer **Yes** if the post does describe at least one strike, shelling or attack at a named place. Answer **No** if
it is about something else (air-raid alerts only, repairs, aid, statements, summaries with no place).

### `ra_typing`: the post's category
Answer **Yes** if the category shown is right. If **No**, type the right one from this list:
| Category | Meaning |
|---|---|
| `alert` | air-raid alert announced |
| `all_clear` | alert ended |
| `aviation_activity` | warning about enemy aircraft/bombers in the air (e.g. Tu-95, MiG-31 take-off) |
| `launch` | missiles/drones launched or approaching (real-time warning) |
| `track` | a drone/missile's movement ("Shahed heading toward X") |
| `launch_intel` | numbers launched/shot down overnight (Air Force tallies) |
| `impact_report` | reports a strike, damage or casualties at a place |
| `daily_summary` | roundup of a day or night across many places |
| `ua_strike_on_ru` | Ukrainian strike on Russian territory or forces |
| `other` | anything else (aid, repairs, statements, appeals) |

## Rules
- Judge only from the post itself. Don't look things up elsewhere.
- If you genuinely can't tell, answer **No** and write why in the note. Uncertain cases are exactly what we need to see.
- Don't discuss rows with the other assistant until you have both sent your files (the first 20 impact rows are
  checked by both of you on purpose, to measure agreement).
- These posts are public but the sheets are research data: don't share them, and delete your copies when done.
- Some posts describe deaths and injuries, including of children. Take breaks; you can stop at any time.

Questions: contact Jackson.
