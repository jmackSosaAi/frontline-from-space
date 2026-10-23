# ACLED: use permitted for aggregated analysis (email, 2026-10-23)

Reply from ACLED Access (access@acleddata.com) to Jackson Mackney's description of this project (sent 2026-10-22 from his UChicago address), received 2026-10-23 11:07 CT:

> Your proposed use case is permitted, provided that the data is aggregated.
>
> As a reminder, any ACLED data published must be transformed and cannot be displayed as raw event-level data points on a platform or map. Also it must be properly cited according to ACLED's Attribution Policy. Additionally, your access remains subject to the Terms and Conditions (T&Cs) and End User License Agreement (EULA) you have accepted.

Rules this project follows as a result:
- ACLED rows stay in `data/raw/acled/` (gitignored). Nothing event-level leaves `data/interim/`.
- Published outputs that use ACLED are cell-week / oblast-week counts or model statistics only; no event points on the dashboard or any map.
- Every figure, table and README that uses ACLED carries the attribution line from https://acleddata.com/attribution-policy/ (form: "Armed Conflict Location & Event Data (ACLED); acleddata.com", with access date).
- Access tier at the time: Research (12-month lag), so the export covers 2022-02-24 → ~2025-10.
