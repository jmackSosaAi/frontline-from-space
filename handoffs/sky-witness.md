# Handoff: Front line from space · sky-witness
Status: ACTIVE
Written: 2026-11-10, 1:20pm CT by Claude Code · first version of this file

## Read these first, in order
1. ~/Jackson Mackney/CLAUDE.md (standing rules)
2. ~/Jackson Mackney/About_Jackson/README.md, WORKING_WITH_ME.md, HOW_I_USE_CLAUDE.md, WORKFLOW_RULES.md (how he works; workflow tiering rules)
3. ~/D3/Frontline_From_Space/README.md (the fire project: question, results, where files live)
4. ~/D3/Frontline_From_Space/planning/SKY_SCAN_2026-11-10.md (the data-access scan that this lane builds on: sources, licences, what is already downloaded, the December plan)
5. ~/D3/Frontline_From_Space/paper/draft_v1.md (the fire paper; the second witness is scored the same way; section 3 has the grid, panel and matching rule)
6. ~/D3/Frontline_From_Space/PREREG.md and DEVIATIONS.md (how the first witness was pre-registered; the addendum for the second witness should follow the same form)
7. ~/D3/Frontline_From_Space/planning/QA_HANDCHECK.md (hand-check of the Telegram layer; final state, nothing to do)

## The goal
The fire paper is finished and public. Jackson wants a second chapter under the umbrella question "what can you learn about the Ukraine war purely from the sky": take ETH Zurich's open radar building-damage data, drop it onto the fire project's existing grid and weekly control map, and score it as a second witness next to fire. Then a LinkedIn post plus a short visual brief (Vectus style, for skimmers) covering both. His words: "we have a decent backbone here and we would effectively just be pulling in preexisting data... you can do this deeply autonomously if we spend time and produce a solid outline, milestones... it doesn't require my manual intervention."

## Where we stopped
The access scan finished (planning/SKY_SCAN_2026-11-10.md, not yet committed) and was reported to Jackson. The next thing was writing the autonomous plan with milestones for the second witness. One question was put to him and not answered: is a quarterly answer that stops in Nov 2023 good enough for chapter two, or does it need a finer time step (which means building our own radar detector, a much bigger job)? He then switched terminals to get a newer model; nothing was half-edited.

## Done
- Second checker (Paolo, label PD) scored; hand-check written into paper, DEVIATIONS, QA_HANDCHECK · commits 9df4e71, a8171cb · [checked]
- Pre-ship review workflow (2 Sonnet, 1 Opus, 1 Fable); 27 wording fixes applied; output planning/reviews/prereview_2026-11-09.json · commit ae0a0f2 · [checked]
- V-set placebo published as data/derived/results/v_placebo.csv (recall 5.00%, placebo 3.78%) · [checked]
- Paper PDF with figures: paper/draft_v1.pdf (20 pages) and draft_v1.html · commit 0a55fa8, pushed to github.com/jmackSosaAi/frontline-from-space main · [checked]
- Sky access scan: 4 lanes + judge; samples downloaded to data/raw/sky_scan/ (314 MB; eth-zenodo-damage, unosat-hdx, sentinel1-raw, optical-routes) · planning/SKY_SCAN_2026-11-10.md · [checked]
- LinkedIn post framing discussed; six framings offered; Jackson's own simplest motive: "i wanted to try my hand at research and do more personal projects, im into conflict and defense and just got back from ukraine" · not written to a file yet · [checked, from conversation]

## Not done / half done
- planning/SKY_SCAN_2026-11-10.md is untracked; commit it · [checked]
- The autonomous plan for the second witness (milestones, stop points, prereg addendum text) · not started · [checked]
- LinkedIn post + visual brief for the fire result · not started; framings are only in the old session's chat, the six options were: the question / the map you've seen / the honest result / the number / the caution / first project · [checked]
- 35-row follow-up hand-check (data/interim/telegram/qa/ra_packet_round2/) · built but Jackson decided NOT to fund it; leave it · [checked]
- Not deleted on purpose (he said "dont delete anything yet"): tg_frontline.session (full Telegram login at repo root), checkers' copies of RA files · [checked]
- S-NPP: paper says delivery was scheduled to end 2 Nov 2026; not confirmed whether it did · [assumed]

## Sent or submitted (never repeat these)
- Nothing sent to any person this session. Both checkers were paid earlier by Jackson (Zelle, Nov 2 and Nov 5). A reply to Paolo about 35 more rows was drafted in chat and NOT sent; it is now moot.
- Pushed to the public GitHub repo: commits 9df4e71, ae0a0f2, a8171cb, 0a55fa8.

## Decisions and rules from Jackson
- "im not here to do critical thinking stuff fr... anything that would help it just do" → in box-checking mode, make the routine calls and report; no yes/no lists.
- "dont delete anything yet tho" → no deletions without a fresh yes.
- "it was expensive to pay them i gave way too much money and it took them longer than it was actually estimated" → no more paid helper rounds; disclose gaps instead.
- "signing up for accounts doesnt take long... the issue we had previously was emailing and waiting... if all you could theoretically need from me is to sign in one time, thats fine"; signing a prereg is fine too → one-time sign-ins and a prereg signature are the only manual steps allowed; any source needing an email permission loop is dropped.
- "youre looking too hard to tie the narrative to a personal story of mine" and "thats ignorant bro. people live there and follow shit" → for the post, no frontline-witness framing and no "residents don't know" framing; state the plain motive.
- "everyone shares these fire maps as if they show the war, thats a claim... you need to be able to back that up" → every claim in the post must be backable; the backable version is: The Economist, Bellingcat and a few papers built war trackers on this data, none measured the miss rate.
- He corrected me twice for length ("make that more concise", "more simple and concise") → replies under ~100 words, one idea per answer.
- Never put Paolo's email handle (APDA) in the public repo; his files are labelled PD.

## Next steps, in order
1. Commit planning/SKY_SCAN_2026-11-10.md.
2. Get his answer: quarterly-through-2023 is enough (plan A, 2 to 4 days of agent work) or a finer time step is required (plan B, build a monthly radar change detector from Planetary Computer Sentinel-1 RTC; weeks, not days).
3. Write the plan as NORTH_STAR.md + a milestone file in planning/ (reuse list, new code list, prereg addendum draft for him to sign, stop points, what runs overnight, which sign-ins he does up front). Follow WORKFLOW_RULES.md tiering.
4. After he signs the addendum: loader for ETH building scores (Zenodo 15088349, 4.81 GB, CC BY 4.0) onto the H3 res-5 grid; quarter roll-up of the VIINA panel; score like fire; cross-check fire vs radar; spot-check vs UNOSAT snapshots.
5. In parallel, LinkedIn post (6 sentences, plain motive, three numbers, attachment) and the visual brief in the Vectus style (deck-layout rules in memory: charts natural size, matter-of-fact headers, scannable blocks).

## Open questions for Jackson
- Quarterly and ending Nov 2023: good enough for chapter two? (decides plan A vs B)
- OK to download the 4.81 GB building file, or read only needed columns from the server?
- Which post framing he wants (or his own three sentences first).

## Watch out for
- Never put ACLED data or raw Telegram text into any model; agents must not open data/interim/acled or data/interim/telegram raw text. Licences in LICENSES/.
- The Gmail connector only sees the personal account; the checkers' thread lives in the UChicago inbox, read via Chrome.
- Shell alias: `claude` is aliased with flags, so `claude update` starts a session; use `command claude update`.
- UNOSAT data on HDX is CC BY-SA (share-alike): anything derived from it must carry the same licence; prefer ETH (CC BY 4.0).
- Downloaded files are untrusted: inspect with python -I from outside their folder.
- School first until Dec 11 (fall-2026-classes/CATCHUP_PLAN_2026-11-05.md); this lane is a December job unless it needs none of his time.

## Other places touched
- ~/Jackson Mackney/About_Jackson/LEARNING_LOG.md (seven entries dated 2026-11-09 and 2026-11-10)
- ~/.claude/projects/.../memory/: frontline-from-space-project.md updated; research-data-access-rule.md added
- ~/Downloads/ra_impacts_APDA.csv (Paolo's original file; copy lives in data/interim/telegram/qa/ra_packet/ra_impacts_PD.csv)
