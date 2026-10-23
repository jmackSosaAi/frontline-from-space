"""H6 Lead (pre-registered null) and H6b corrected index (PREREG §4, DESIGN D12–D13; confirmatory).

Primary: net_fwd_4 ~ β·log1p(fires) + Σ_k γ_k net_lag_k + δ·opportunity | cell FE + week FE, C1 front_15 cell-weeks.
Inference per _panel.fe_fit (CRV1 + Webb wild-cluster bootstrap 9,999 draws; Driscoll–Kraay(4)). SESOI 1.70 km²/log-unit.
(i) supported if significant under both and β ≥ SESOI; (ii) equivalence if both 90% CIs lie within ±SESOI; (iii) inconclusive.
H6b: regressor log1p(fires / P̂(detect)), P̂ = H2 primary logit scored on the cell-week covariates (mapping in
_panel.h2_pdetect; event_type fixed at the reference 'strike'), clipped at 0.02. Model uncertainty: 1,000 N(β̂, Cov)
coefficient draws → 1,000 corrected indices → 1,000 re-fits (point β and CRV1 90% CI each). Reported interval =
union (outer hull) of the main-fit 90% CIs and the 5th/95th percentiles of the per-draw 90% CI bounds. The H6b category
is judged on that hull (conservative), with the main-fit category also given.
"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import pyfixest as pf
from _panel import *  # noqa

t0 = time.time(); N_DRAWS = 1000
p = load_panel(5, ["h3_r5", "week_start", "front_15", "fires", "net_fwd_4", *MOMENTUM, "opportunity",
                   "min_tcc_mean", "snow_share", "hours_since_prev_mean", "share_night", "landcover_mode"])
d = prep(c1_front(p, 15))
S = SESOI[15]


def category(r):
    if r["significant_both"] and r["beta"] >= r["sesoi"]:
        return "supported"
    if r["equivalence"]:
        return "equivalence"
    return "inconclusive"


# ---- H6 ----
h6 = fe_fit(d, "net_fwd_4", ["lf"] + H6_CONTROLS, ["lf"] + H6_CONTROLS, sesoi=S, label="H6 primary")
h6["lf"]["category"] = category(h6["lf"])
log(f"H6 beta {h6['lf']['beta']:.3f} p_wild {h6['lf']['p_wild']:.4f} p_dk {h6['lf']['p_dk']:.4f} CI90 crv1 {h6['lf']['ci90_crv1']} dk {h6['lf']['ci90_dk']} -> {h6['lf']['category']}")

# ---- H6b ----
p_hat, P = h2_pdetect(d, n_draws=N_DRAWS)
d["p_detect"] = p_hat; d["fires_corr"] = d.fires / d.p_detect; d["lfc"] = np.log1p(d.fires_corr)
h6b = fe_fit(d, "net_fwd_4", ["lfc"] + H6_CONTROLS, ["lfc"], sesoi=S, label="H6b corrected index")
share_clipped = float((p_hat <= P_CLIP + 1e-12).mean())
log(f"H6b main beta {h6b['lfc']['beta']:.3f} p_wild {h6b['lfc']['p_wild']:.4f} p_dk {h6b['lfc']['p_dk']:.4f}; P(detect) mean {p_hat.mean():.3f}, share clipped {share_clipped:.3f}")
betas, los, his = [], [], []
rhs = " + ".join(["lfc_d"] + H6_CONTROLS)
dd = d.copy()
for j in range(N_DRAWS):
    dd["lfc_d"] = np.log1p(dd.fires.values / P[:, j])
    f = pf.feols(f"net_fwd_4 ~ {rhs} | cell + wk", data=dd, vcov={"CRV1": "cell"})
    ci = f.confint(alpha=0.10).loc["lfc_d"]
    betas.append(float(f.coef()["lfc_d"])); los.append(float(ci.iloc[0])); his.append(float(ci.iloc[1]))
    if j % 200 == 0:
        log(f"  draw {j}: beta {betas[-1]:.3f}")
betas, los, his = map(np.asarray, (betas, los, his))
b5, b95 = np.percentile(betas, [5, 95]); lo5 = float(np.percentile(los, 5)); hi95 = float(np.percentile(his, 95))
r = h6b["lfc"]
hull = [min(r["ci90_crv1"][0], r["ci90_dk"][0], lo5), max(r["ci90_crv1"][1], r["ci90_dk"][1], hi95)]
r["propagated"] = {"beta_p5": float(b5), "beta_p95": float(b95), "ci90_lo_p5_across_draws": lo5, "ci90_hi_p95_across_draws": hi95, "hull_90": hull, "n_draws": N_DRAWS}
r["equivalence_main_fit"] = r["equivalence"]; r["category_main_fit"] = category(r)
r["equivalence"] = bool(max(abs(hull[0]), abs(hull[1])) < S)
r["category"] = category(r)
h6b["lfc"] = r
log(f"H6b propagated: beta draws p5/p95 {b5:.3f}/{b95:.3f}; hull {hull} -> {r['category']} (main fit {r['category_main_fit']})")

rows = flat_rows(h6, "H6", "primary: net_fwd_4 ~ log1p(fires) + momentum + opportunity | cell + week") + \
       flat_rows(h6b, "H6b", "corrected: net_fwd_4 ~ log1p(fires/P(detect)) + momentum + opportunity | cell + week",
                 extra={"hull90_lo": hull[0], "hull90_hi": hull[1], "beta_draws_p5": float(b5), "beta_draws_p95": float(b95)})
pd.DataFrame(rows).to_csv(RES / "h6_lead.csv", index=False)
out = {"H6": h6, "H6b": h6b, "sesoi": S, "p_detect": {"mean": float(p_hat.mean()), "median": float(np.median(p_hat)), "min": float(p_hat.min()), "max": float(p_hat.max()),
                                                     "share_clipped_at_0.02": share_clipped, "clip": P_CLIP},
       "headline_change_in_category": h6["lf"]["category"] != h6b["lfc"]["category"], "runtime_s": round(time.time() - t0, 1)}
json.dump(out, open(RES / "h6_lead.json", "w"), indent=2, default=str)
write_meta(RES / "h6_lead.csv", inputs={"panel": PANEL5, "h2_logit_spec": INTERIM / "models" / "h2_logit_primary_all_types_spec.json"},
           counts={"cell_weeks": h6["_n"], "cells": h6["_n_cells"]}, extra={"definitions": __doc__, "p_detect": out["p_detect"],
           "equivalence_rule": "both the CRV1 analytic and the DK 90% CI inside ±SESOI (H6b: also the propagated hull)",
           "licence": "Contains VIINA-derived control aggregates (ODbL); fires NASA FIRMS VIIRS 375 m"})
for hyp, res, prm in [("H6", h6, "lf"), ("H6b", h6b, "lfc")]:
    rr = res[prm]; v = rr["category"]
    extra = f"; propagated hull {hull[0]:.2f}–{hull[1]:.2f}, main-fit category {rr['category_main_fit']}" if hyp == "H6b" else ""
    save_verdict(hyp, {"criterion": "(i) supported: p<0.05 under wild-cluster bootstrap AND Driscoll–Kraay and β ≥ 1.70; (ii) equivalence: 90% CI within ±1.70; (iii) inconclusive",
                       "result": f"β {rr['beta']:.3f} km²/log-unit (p_wild {rr['p_wild']:.3f}, p_dk {rr['p_dk']:.3f}); 90% CI CRV1 {rr['ci90_crv1'][0]:.2f}–{rr['ci90_crv1'][1]:.2f}, DK {rr['ci90_dk'][0]:.2f}–{rr['ci90_dk'][1]:.2f}{extra}",
                       "verdict": v, "jackson_prediction": "equivalence|inconclusive (signed PREREG: '(ii) or (iii) for both')", "claude_prediction": "equivalence|inconclusive",
                       **who_was_right(v, "equivalence|inconclusive", "equivalence|inconclusive"), "label": "confirmatory", "source": "h6_lead.json"})

fig, ax = plt.subplots(figsize=(6.5, 3.6))
ys = [1, 0]
for y, (lab, rr) in zip(ys, [("H6 raw fires", h6["lf"]), ("H6b corrected (fires / P̂ detect)", h6b["lfc"])]):
    ax.plot(rr["ci90_crv1"], [y + 0.12] * 2, color="C0", lw=3, solid_capstyle="butt", label="90% CI, CRV1 by cell" if y == 1 else None)
    ax.plot(rr["ci90_dk"], [y - 0.12] * 2, color="C1", lw=3, label="90% CI, Driscoll–Kraay(4)" if y == 1 else None)
    ax.plot(rr["beta"], y, "ko")
ax.plot(hull, [0 - 0.3] * 2, color="grey", lw=2, ls="--", label="H6b propagated hull (1,000 coefficient draws)")
ax.axvspan(-S, S, color="green", alpha=0.08, label="±SESOI 1.70"); ax.axvline(0, color="k", lw=0.6)
ax.set_yticks(ys); ax.set_yticklabels(["H6 raw fires", "H6b corrected"]); ax.set_xlabel("β: km² RU gain over t+1..t+4 per log-unit of fires at t")
ax.set_title("H6 / H6b: fires and 4-week territorial change, C1 front cells"); ax.legend(fontsize=7, loc="upper right")
fig.tight_layout(); fig.savefig(FIG / "h6_lead.png", dpi=150); plt.close(fig)
caption("h6_lead.png", "confirmatory", "H6 and H6b (PREREG §4, pre-registered null): β on log1p(fires at t) in a two-way FE regression of net Russian km² gain over "
        "t+1..t+4 on fires, 4 outcome lags and detection opportunity, C1 front_15 cell-weeks. Bars = 90% CIs under CRV1 by cell (blue) and Driscoll–Kraay lag 4 "
        "(orange); grey dashed = outer hull of the H6b interval propagated through 1,000 draws of the H2 logit coefficients (P(detect) clipped at 0.02). Green band = ±SESOI. "
        "Source: data/derived/results/h6_lead.json.")
log(f"15 done {time.time()-t0:.0f}s"); print(json.dumps({"H6": h6["lf"], "H6b": h6b["lfc"], "p_detect": out["p_detect"]}, indent=1, default=str))
