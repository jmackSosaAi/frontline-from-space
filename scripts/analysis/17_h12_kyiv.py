"""H12 Kyiv strikes (PREREG §4, open question, no directional prediction; confirmatory on C1 weeks).

net_ru_gain_km2(national, week t) ~ Σ_{j=-4..+4} β_j·log1p(kyiv_fires_{t−j}) + Σ_{m=1..4} γ_m·net_{t−m} + week-of-year FE,
OLS with Newey–West (Bartlett, 4 lags) standard errors; sample = C1 outcome weeks (ISO Mondays 2022-04-04 .. 2024-07-01,
PREREG §2 assigns H12 to C1); regressors at t±j are taken from the full national series so the edges are not lost.
j > 0: Kyiv fires j weeks BEFORE the gain (fires lead); j = 0 same week; j < 0: fires j weeks AFTER the gain (fires lag).
log1p keeps β in km² per log-unit so the SESOI applies: national SESOI = 1.70 km² × median number of front_15 res-5
cells per C1 week (the number is computed from national_week.csv and stated in the meta/verdict).
Answer: "no relationship" if every 90% CI (NW) lies within ±national SESOI; otherwise "coordinated" if the significant
(p < 0.05) coefficients are all positive, "opposite" if all negative, "mixed" if both signs, "inconclusive" if none is
significant and the CIs are not all inside the band. Verdict field maps: no relationship → equivalence; coordinated /
opposite / mixed → supported (a relationship); inconclusive → inconclusive.
Season interaction: every Kyiv term × 1[summer] added (reported; the C1 sample is thin for 18 fire terms + 52 WOY FE).
Exploratory (labelled): the same on the full span 2022-04-04 .. 2025-12-29 (C1 ∪ E; most Kyiv fires are in 2025),
and cross-checks with Telegram-derived Kyiv-city impacts (tg_n_impact_incidents_kyiv_city) and Air Force national launched
totals (af_total_launched) in place of kyiv_fires (DEVIATIONS 2026-10-22: tg_*/af_* are exploratory).
"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import statsmodels.api as sm
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from _panel import *  # noqa

t0 = time.time()
J = list(range(-4, 5)); NW_LAGS = 4
n = pd.read_csv(NATIONAL, parse_dates=["week_start"]).sort_values("week_start").reset_index(drop=True)
assert (n.week_start.diff().dropna() == pd.Timedelta(days=7)).all()
c1_weeks = n.week_start.between(C1_START, C1_END)
MED_FRONT = float(n.loc[c1_weeks, "n_front15_r5"].median())
S_NAT = SESOI[15] * MED_FRONT
n["summer"] = (n.season.astype(str) == "summer").astype(float)
for m in range(1, 5):
    n[f"net_lag{m}"] = n.net_ru_gain_km2.shift(m)
log(f"national SESOI = 1.70 × median C1 front_15 cells/week {MED_FRONT:.0f} = {S_NAT:.1f} km²/week per log-unit")


def build(series_col, label):
    x = np.log1p(n[series_col].astype(float))
    cols = {}
    for j in J:
        cols[f"{label}_j{j:+d}"] = x.shift(j)          # shift(j) = value at t−j
    return pd.DataFrame(cols)


def fit(mask, series_col, label, season=False, outcome="net_ru_gain_km2"):
    X = build(series_col, label)
    terms = list(X.columns)
    if season:
        for c in terms:
            X[f"{c}:summer"] = X[c] * n.summer
    X = pd.concat([X, n[[f"net_lag{m}" for m in range(1, 5)]], pd.get_dummies(n.iso_week.astype(int), prefix="woy", drop_first=True, dtype=float)], axis=1)
    X = sm.add_constant(X)
    dd = pd.concat([n[[outcome]], X], axis=1)[mask].dropna()
    res = sm.OLS(dd[outcome], dd.drop(columns=[outcome])).fit(cov_type="HAC", cov_kwds={"maxlags": NW_LAGS, "use_correction": True})
    ci = res.conf_int(alpha=0.10)
    rows = []
    for c in [t for t in dd.columns if t.startswith(label)]:
        j = int(c.split("_j")[1].split(":")[0])
        rows.append({"term": c, "lead_j": j, "summer_interaction": c.endswith(":summer"), "beta": float(res.params[c]), "se_nw": float(res.bse[c]), "p_nw": float(res.pvalues[c]),
                     "ci90_lo": float(ci.loc[c, 0]), "ci90_hi": float(ci.loc[c, 1]), "within_sesoi": bool(max(abs(ci.loc[c, 0]), abs(ci.loc[c, 1])) < S_NAT)})
    out = pd.DataFrame(rows)
    return out, {"n_weeks": int(res.nobs), "df_resid": int(res.df_resid), "r2": float(res.rsquared), "outcome": outcome, "regressor": series_col}


def answer(tab):
    main = tab[~tab.summer_interaction]
    sig = main[main.p_nw < 0.05]
    if main.within_sesoi.all():
        return "no relationship"
    if len(sig) == 0:
        return "inconclusive"
    if (sig.beta > 0).all():
        return "coordinated"
    if (sig.beta < 0).all():
        return "opposite"
    return "mixed"


VERDICT_MAP = {"no relationship": "equivalence", "inconclusive": "inconclusive", "coordinated": "supported", "opposite": "supported", "mixed": "supported"}
full = n.week_start.between(C1_START, E_END)
runs = {}
tabs = []
for key, mask, col, lab, season, kind in [
    ("C1_primary", c1_weeks, "kyiv_fires", "kyiv", False, "confirmatory"),
    ("C1_season", c1_weeks, "kyiv_fires", "kyiv", True, "confirmatory"),
    ("full_span", full, "kyiv_fires", "kyiv", False, "exploratory"),
    ("full_span_season", full, "kyiv_fires", "kyiv", True, "exploratory"),
    ("full_span_night", full, "kyiv_fires_night", "kyivnight", False, "exploratory"),
    ("tg_impacts_kyiv_city", full & n.tg_n_impact_incidents_kyiv_city.notna(), "tg_n_impact_incidents_kyiv_city", "tgimp", False, "exploratory"),
    ("af_total_launched", full & n.af_total_launched.notna(), "af_total_launched", "aflaunch", False, "exploratory"),
]:
    try:
        tab, info = fit(mask, col, lab, season=season)
    except Exception as e:  # thin samples (af_* has fewer weeks) — report, never tune
        log(f"{key}: fit failed: {e}"); runs[key] = {"error": str(e), "kind": kind}; continue
    tab["run"] = key; tab["kind"] = kind; tabs.append(tab)
    info.update({"kind": kind, "answer": answer(tab), "season": season}); runs[key] = info
    log(f"{key} ({kind}, n {info['n_weeks']}, df {info['df_resid']}): {info['answer']}; " + ", ".join(f"j{r.lead_j:+d}: {r.beta:.0f} (p {r.p_nw:.2f})" for r in tab[~tab.summer_interaction].itertuples()))
res = pd.concat(tabs, ignore_index=True)
res["sesoi_national"] = S_NAT
res.to_csv(RES / "h12_kyiv.csv", index=False)
prim = runs["C1_primary"]; ans = prim["answer"]
kyiv_c1 = int(n.loc[c1_weeks, "kyiv_fires"].sum()); kyiv_full = int(n.loc[full, "kyiv_fires"].sum())
summary = {"national_sesoi_km2_per_log_unit": S_NAT, "median_front15_cells_per_c1_week": MED_FRONT, "sesoi_cell": SESOI[15], "newey_west_lags": NW_LAGS,
           "kyiv_fires_in_c1_weeks": kyiv_c1, "kyiv_fires_full_span": kyiv_full, "c1_weeks_with_kyiv_fire": int((n.loc[c1_weeks, "kyiv_fires"] > 0).sum()),
           "runs": runs, "answer_primary": ans, "verdict": VERDICT_MAP[ans], "runtime_s": round(time.time() - t0, 1)}
json.dump(summary, open(RES / "h12_summary.json", "w"), indent=2, default=str)
write_meta(RES / "h12_kyiv.csv", inputs={"national_week": NATIONAL}, counts={"c1_weeks": int(c1_weeks.sum()), "full_span_weeks": int(full.sum()), "kyiv_fires_c1": kyiv_c1, "kyiv_fires_full": kyiv_full},
           extra={"definitions": __doc__, "summary": {k: v for k, v in summary.items() if k != "runs"},
                  "licence": "Contains VIINA-derived national control aggregates (ODbL); fires NASA FIRMS VIIRS 375 m; tg_*/af_* from public Telegram posts (exploratory)"})
pm = res[(res.run == "C1_primary")]
save_verdict("H12", {"criterion": f"national weekly net RU gain on log1p(Kyiv fires) at leads/lags −4..+4, week-of-year FE, 4 outcome lags, Newey–West(4), C1 weeks; 'no relationship' = every 90% CI within ±{S_NAT:.0f} km² (1.70 × {MED_FRONT:.0f} median front cells/week); otherwise coordinated/opposite/mixed by the sign of p<0.05 coefficients",
                     "result": f"answer: {ans}; β by lead j (fires j weeks before the gain): " + ", ".join(f"{r.lead_j:+d}: {r.beta:.0f} (p {r.p_nw:.2f}, 90% CI {r.ci90_lo:.0f}–{r.ci90_hi:.0f})" for r in pm.itertuples()) +
                               f"; n {prim['n_weeks']} weeks, {kyiv_c1} Kyiv fires in C1 ({summary['c1_weeks_with_kyiv_fire']} weeks with any); season-interaction run answer: {runs['C1_season']['answer']}; "
                               f"exploratory full-span (2022-04..2025-12, {kyiv_full} fires) answer: {runs['full_span']['answer']}",
                     "verdict": VERDICT_MAP[ans], "answer": ans, "jackson_prediction": None, "claude_prediction": None,
                     **who_was_right(VERDICT_MAP[ans], None, None), "note": f"open question; PREREG loose guess 'depends on season'. Caveat: only {kyiv_c1} Kyiv fires in {summary['c1_weeks_with_kyiv_fire']} of {prim['n_weeks']} C1 weeks; if the coefficients are flat across all leads AND lags (fires after the gain), read it as a period-level association (Kyiv-fire weeks fell in the 2022 Ukrainian counter-offensive months), not timing", "label": "confirmatory", "source": "h12_kyiv.csv"})

# ---- figure ----
fig, ax = plt.subplots(1, 2, figsize=(10, 3.8), sharey=False)
for a_, key, title in [(ax[0], "C1_primary", f"C1 weeks (confirmatory), n={prim['n_weeks']}"), (ax[1], "full_span", f"2022-04..2025-12 (exploratory), n={runs['full_span']['n_weeks']}")]:
    t = res[(res.run == key) & (~res.summer_interaction)]
    a_.errorbar(t.lead_j, t.beta, yerr=[t.beta - t.ci90_lo, t.ci90_hi - t.beta], fmt="o", color="k", capsize=3, label="β, 90% CI (Newey–West 4)")
    a_.axhspan(-S_NAT, S_NAT, color="green", alpha=0.08, label=f"±national SESOI {S_NAT:.0f} km²"); a_.axhline(0, color="k", lw=0.6)
    a_.set_xticks(J); a_.set_xlabel("j: Kyiv fires j weeks before the national gain (j<0: after)"); a_.set_title(title)
ax[0].set_ylabel("β: national km² RU gain per log-unit of Kyiv fires"); ax[0].legend(fontsize=7)
fig.suptitle(f"H12 Kyiv fires vs national Russian gains: {ans}", fontsize=10); fig.tight_layout(); fig.savefig(FIG / "h12_kyiv.png", dpi=150); plt.close(fig)
caption("h12_kyiv.png", "confirmatory (left) / exploratory (right)", f"H12 (PREREG §4): coefficients on log1p(weekly FIRMS detections inside Kyiv city) at leads/lags −4..+4 "
        f"in a regression of national weekly net Russian km² gain (VIINA) with week-of-year FE and 4 outcome lags, Newey–West(4) 90% CIs. Left: C1 weeks (confirmatory). "
        f"Right: full span through 2025 (exploratory; most Kyiv fires are in 2025). Green band = ±national SESOI = 1.70 km² × {MED_FRONT:.0f} median front cells per week = {S_NAT:.0f} km². "
        f"Source: data/derived/results/h12_kyiv.csv.")
log(f"17 done {time.time()-t0:.0f}s")
print(json.dumps({k: {kk: vv for kk, vv in v.items()} for k, v in runs.items()}, indent=1, default=str))
