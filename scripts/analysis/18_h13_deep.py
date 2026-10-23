"""H13 Deep strikes (PREREG §4; EXPLORATORY throughout — the campaign is mostly 2025, after C1; E period 2024-07-08 ..
2025-12-31). Prediction: equivalence (90% CI within ±SESOI 1.70).

Deep RU fire (panel column fires_deep_ru) = FRP ≥ 16.33 MW, > 30 km from the RU|UA line, in RU-held Ukrainian territory
or inside Russia. These fires are by construction NOT in front cells, so the literal cell-level reading of
"net_fwd_4 on log1p(fires_deep_ru) with the H6 controls" is degenerate (deep-fire cells have no line to move).
Ambiguity resolved (stated here and in the meta/log): the deep-fire exposure is the NATIONAL weekly count, and the
outcome is front-cell movement.
Spec 1 (cell panel): E front_15 cell-weeks, net_fwd_4 ~ β·log1p(deep_ru_fires_national_t) + Σ net_lag_1..4 + opportunity
| cell FE + week-of-year FE (a full week FE would absorb the national regressor); CRV1 + Webb wild bootstrap 9,999 and
Driscoll–Kraay(4); equivalence = both 90% CIs within ±1.70.
Spec 2 (national weekly): national Σ net_{t+1..t+4} ~ β·log1p(deep_ru_fires_national_t) + 4 outcome lags + week-of-year
FE, Newey–West(4); equivalence = 90% CI within ±(1.70 × median E front_15 cells per week).
Caveat: Russian agricultural burning dominates the ≥16.33 MW deep count (≈25k fires per year inside Russia); the
regressor is a noisy proxy for strikes. Descriptive cross-check against Militarnyi / Saltan deep-strike counts is NOT
done here (left for the write-up).
"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import statsmodels.api as sm
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from _panel import *  # noqa

t0 = time.time()
p = load_panel(5, ["h3_r5", "week_start", "iso_week", "front_15", "fires", "fires_deep_ru", "net_ru_gain_km2", "net_fwd_4", *MOMENTUM, "opportunity", "in_ukraine"])
deep_nat = p.groupby("week_start").agg(deep_ru=("fires_deep_ru", "sum")).reset_index()
deep_nat["l_deep"] = np.log1p(deep_nat.deep_ru)
d = prep(c1_front(p, 15, period="E")); d["woy"] = d.iso_week.astype(int)
d = d.merge(deep_nat, on="week_start", how="left")
S = SESOI[15]
log(f"E front_15 sample {len(d)} cell-weeks, {d.cell.nunique()} cells; national deep fires/week median {deep_nat.deep_ru.median():.0f}")

# Spec 1
h13 = fe_fit(d, "net_fwd_4", ["l_deep"] + H6_CONTROLS, ["l_deep"], sesoi=S, fe="cell + woy", label="H13 cell panel, national deep-fire exposure")
r = h13["l_deep"]
cat1 = "equivalence" if r["equivalence"] else ("supported" if r["significant_both"] and abs(r["beta"]) >= S else "inconclusive")
log(f"H13 spec1: β {r['beta']:.3f} p_wild {r['p_wild']:.3f} p_dk {r['p_dk']:.3f} CI90 crv1 {r['ci90_crv1']} dk {r['ci90_dk']} -> {cat1}")

# Spec 2
n = pd.read_csv(NATIONAL, parse_dates=["week_start"]).sort_values("week_start").reset_index(drop=True)
n = n.merge(deep_nat, on="week_start", how="left")
n["y_fwd4"] = sum(n.net_ru_gain_km2.shift(-k) for k in range(1, 5))
for m in range(1, 5):
    n[f"net_lag{m}"] = n.net_ru_gain_km2.shift(m)
e_mask = n.week_start.between(E_START, E_END)
MED_FRONT_E = float(n.loc[e_mask, "n_front15_r5"].median()); S_NAT = S * MED_FRONT_E
X = pd.concat([n[["l_deep", "net_lag1", "net_lag2", "net_lag3", "net_lag4"]], pd.get_dummies(n.iso_week.astype(int), prefix="woy", drop_first=True, dtype=float)], axis=1)
X = sm.add_constant(X); dd = pd.concat([n[["y_fwd4"]], X], axis=1)[e_mask].dropna()
ols = sm.OLS(dd.y_fwd4, dd.drop(columns=["y_fwd4"])).fit(cov_type="HAC", cov_kwds={"maxlags": 4, "use_correction": True})
ci = ols.conf_int(alpha=0.10).loc["l_deep"]
spec2 = {"beta": float(ols.params["l_deep"]), "se_nw": float(ols.bse["l_deep"]), "p_nw": float(ols.pvalues["l_deep"]), "ci90": [float(ci[0]), float(ci[1])],
         "n_weeks": int(ols.nobs), "df_resid": int(ols.df_resid), "sesoi_national": S_NAT, "median_front15_cells_per_E_week": MED_FRONT_E,
         "equivalence": bool(max(abs(ci[0]), abs(ci[1])) < S_NAT)}
cat2 = "equivalence" if spec2["equivalence"] else ("supported" if spec2["p_nw"] < 0.05 and abs(spec2["beta"]) >= S_NAT else "inconclusive")
log(f"H13 spec2 national: β {spec2['beta']:.1f} km²/log-unit (p_nw {spec2['p_nw']:.3f}, CI90 {spec2['ci90']}), SESOI_nat {S_NAT:.0f} -> {cat2}")

rows = flat_rows(h13, "H13", "spec1 (exploratory): E front_15, net_fwd_4 ~ log1p(national deep RU fires_t) + momentum + opportunity | cell + week-of-year", extra={"outcome": "net_fwd_4"})
rows.append({"hypothesis": "H13", "spec": "spec2 (exploratory): national Σnet_{t+1..t+4} ~ log1p(deep RU fires_t) + 4 lags + week-of-year FE, Newey–West(4)", "param": "l_deep",
             "n": spec2["n_weeks"], "n_cells": 1, "beta": spec2["beta"], "se_crv1": np.nan, "p_crv1": np.nan, "se_dk": spec2["se_nw"], "p_dk": spec2["p_nw"], "p_wild": np.nan,
             "ci90_crv1_lo": np.nan, "ci90_crv1_hi": np.nan, "ci90_dk_lo": spec2["ci90"][0], "ci90_dk_hi": spec2["ci90"][1], "sesoi": S_NAT, "equivalence": spec2["equivalence"],
             "significant_both": spec2["p_nw"] < 0.05, "outcome": "national net_fwd_4"})
pd.DataFrame(rows).to_csv(RES / "h13_deep.csv", index=False)
out = {"spec1_cell_panel": h13, "spec1_category": cat1, "spec2_national": spec2, "spec2_category": cat2, "sesoi": S, "label": "exploratory",
       "deep_fires_E_total": int(deep_nat.loc[deep_nat.week_start.between(E_START, E_END), "deep_ru"].sum()), "runtime_s": round(time.time() - t0, 1)}
json.dump(out, open(RES / "h13_deep.json", "w"), indent=2, default=str)
write_meta(RES / "h13_deep.csv", inputs={"panel": PANEL5, "national_week": NATIONAL}, counts={"cell_weeks": h13["_n"], "cells": h13["_n_cells"], "national_weeks": spec2["n_weeks"]},
           extra={"definitions": __doc__, "licence": "Contains VIINA-derived control aggregates (ODbL); fires NASA FIRMS VIIRS 375 m"})
verdict = cat1   # primary exploratory reading = spec 1
save_verdict("H13", {"criterion": "EXPLORATORY (E period): equivalence if the 90% CI of β on log1p(national weekly deep RU fires ≥16.33 MW, >30 km from the line) lies within ±1.70 km²/log-unit (cell panel, cell + week-of-year FE, wild-cluster bootstrap and Driscoll–Kraay); national weekly spec with ±SESOI × median E front cells as a second reading",
                     "result": f"spec1 β {r['beta']:.3f} (p_wild {r['p_wild']:.3f}, p_dk {r['p_dk']:.3f}; 90% CI CRV1 {r['ci90_crv1'][0]:.2f}–{r['ci90_crv1'][1]:.2f}, DK {r['ci90_dk'][0]:.2f}–{r['ci90_dk'][1]:.2f}) -> {cat1}; "
                               f"spec2 national β {spec2['beta']:.0f} km²/log-unit (p_nw {spec2['p_nw']:.3f}, 90% CI {spec2['ci90'][0]:.0f}–{spec2['ci90'][1]:.0f}, SESOI_nat {S_NAT:.0f}) -> {cat2}",
                     "verdict": verdict, "jackson_prediction": "equivalence", "claude_prediction": "equivalence (PREREG: 'economic damage doesn't slow Russia's war effort')",
                     **who_was_right(verdict, "equivalence", "equivalence"), "label": "exploratory",
                     "note": "deep-fire exposure taken as the national weekly count (deep fires are not in front cells by construction); Russian agricultural burning dominates the count", "source": "h13_deep.json"})

fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
ax[0].plot(deep_nat.week_start, deep_nat.deep_ru, color="C3", lw=0.9); ax[0].axvspan(E_START, E_END, color="grey", alpha=0.15, label="E period")
ax[0].set_ylabel("deep RU fires ≥16.33 MW per week"); ax[0].set_title("national weekly deep-fire count"); ax[0].legend(fontsize=7)
ax[1].plot(r["ci90_crv1"], [1.12] * 2, color="C0", lw=3, label="90% CI CRV1"); ax[1].plot(r["ci90_dk"], [0.88] * 2, color="C1", lw=3, label="90% CI Driscoll–Kraay(4)"); ax[1].plot(r["beta"], 1, "ko")
ax[1].axvspan(-S, S, color="green", alpha=0.08, label="±SESOI 1.70"); ax[1].axvline(0, color="k", lw=0.6); ax[1].set_yticks([1]); ax[1].set_yticklabels(["spec 1"])
ax[1].set_xlabel("β: front-cell km² RU gain over t+1..t+4 per log-unit of national deep fires"); ax[1].set_title(f"H13 (exploratory): {cat1}"); ax[1].legend(fontsize=7)
fig.tight_layout(); fig.savefig(FIG / "h13_deep.png", dpi=150); plt.close(fig)
caption("h13_deep.png", "exploratory", "H13 (PREREG §4, exploratory; E period 2024-07-08..2025-12-31): left, national weekly count of FIRMS detections ≥ 16.33 MW more than 30 km "
        "from the RU|UA line in RU-held or Russian territory (dominated by agricultural burning in Russia). Right, β on log1p of that count in a regression of front-cell "
        "net Russian km² gain over t+1..t+4 with 4 outcome lags, opportunity, cell and week-of-year FE; 90% CIs under CRV1 by cell and Driscoll–Kraay(4); green = ±SESOI. "
        "Source: data/derived/results/h13_deep.json.")
log(f"18 done {time.time()-t0:.0f}s"); print(json.dumps({"spec1": r, "spec2": spec2}, indent=1, default=str))
