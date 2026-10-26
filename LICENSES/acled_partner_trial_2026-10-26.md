# ACLED: one-month Partner Tier trial (email, 2026-10-26)

ACLED Access granted Jackson Mackney a one-month trial of the Partner Tier for this academic project. It **expires 2026-11-23**, after which the account reverts to Research level (12-month lag). Partner level gives real-time weekly disaggregated event data (no 12-month lag), all tags/qualifiers/context fields, and methodology docs.

Conditions stated in the email (in addition to the 2026-10-23 permission, `acled_permission_2026-10-23.md`):
- Published ACLED data must be transformed and cited per the Attribution Policy; access stays subject to the T&Cs and EULA.
- Platforms, dashboards or tools built with ACLED data during the trial may **not** be made publicly available.
- Academic use only; no external or commercial projects.
- Use of ACLED content with AI/ML/LLM systems is subject to strict limitations.
- Violations can suspend access for the whole university.

Rules this project follows as a result:
- Exported 2026-10-26: Ukraine + Russia, 2022-02-24 → 2025-12-31, 277,536 events, `data/raw/acled/` (gitignored). Sudan, Armenia and Azerbaijan return no results on this account, so the trial appears scoped to Ukraine + Russia.
- ACLED feeds only descriptive statistics and regressions as an external grading source. It is not used to train or tune any ML model (H2 logit/LightGBM, model v2), and no ACLED rows or notes are sent to an LLM (no Claude/Batch API processing, no pasting rows into a chat). Scripts read the CSV; only aggregate numbers are shown.
- No ACLED layer on the public site/dashboard, and no ACLED-derived tables in the public repo. ACLED results appear in the paper as transformed aggregate statistics/figures with the attribution line.
