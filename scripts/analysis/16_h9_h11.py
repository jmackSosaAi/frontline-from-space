"""H9 lead time, H10 fire size × side, H11 phase flip, H11s season within phase (PREREG §4 "Jackson's directional
predictions"; confirmatory). Sample, FE and inference as H6 (C1 front_15 cell-weeks; cell + week FE; CRV1 + Webb
wild-cluster bootstrap 9,999 draws; Driscoll–Kraay(4)). Each hypothesis is run once, exactly as written below.

H9. Primary = JOINT distributed-lead regression (PREREG: "separate β for the same week and for leads of 1, 2, 3, 4, 6
and 8 weeks"): net_t ~ Σ_k β_k·log1p(fires_{t−k}) for k ∈ {0,1,2,3,4,6,8} + Σ_{j=1..4} γ_j net_{t−j} + δ·opportunity_t
| cell + week. β_k = effect of fires k weeks earlier on this week's net gain (fires lead by k). Check = SEPARATE
regressions net_{t+k} ~ β·log1p(fires_t) + same controls, one per k. SESOI for a 1-week outcome = 0.65 km²/log-unit
(PREREG §3). Supported if the largest positive β_k is at k ∈ {0,1} and significant under both methods, and every
β_k for k ≥ 2 passes equivalence (both 90% CIs within ±0.65). The k = 0 term is descriptive co-movement.
H10. net_{t+1..t+3} (PREREG wording "over t+1…t+3"; net_fwd_4 given as a labelled check because PANEL.md names
net_fwd_4 for H9–H11) ~ log1p of the four fire terms big/small × UA/RU side entered together + H6 controls | FE.
Supported if β(big, UA side) > 0 and β(small, RU side) < 0, each significant under both methods.
H11. net_fwd_4 ~ β_A·log1p(fires)·1[phase A] + β_B·log1p(fires)·1[phase B] + controls | FE (phase main effect is
absorbed by week FE); β_A − β_B from the re-parameterisation lf + lf·1[B]. Supported if β_A > 0, β_B < 0 and
β_A − β_B > 0, each p < 0.05 under both methods.
H11s. Within each phase, lf·1[summer] and lf·1[winter] (summer May–Oct); interaction = lf·1[phase]·1[summer] on top of
lf·1[phase]. Supported if in BOTH phases |β_summer| > |β_winter| and the interaction has p < 0.05 under both
methods (PREREG: "within each phase"). A phase-pooled season interaction is given as a labelled check.
"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from _panel import *  # noqa

t0 = time.time()
LEADS = [0, 1, 2, 3, 4, 6, 8]
FOUR = ["fires_big_ua_side", "fires_small_ua_side", "fires_big_ru_side", "fires_small_ru_side"]
p = load_panel(5, ["h3_r5", "week_start", "season", "front_15", "fires", "net_ru_gain_km2", "net_fwd_3", "net_fwd_4",
                   *MOMENTUM, "opportunity", *FOUR])
# shifts on the full cell × week grid (before the C1 / front filter), so t+k and t−k exist at the sample edges
p["lf_all"] = np.log1p(p["fires"])
for k in LEADS:
    p = add_shift(p, "net_ru_gain_km2", k, f"net_t{k}")                  # outcome at t+k (separate form)
    p[f"lf_lag{k}"] = p.groupby("cell")["lf_all"].shift(k)                # fires at t−k (joint form)
d = prep(c1_front(p, 15))
S4, S1 = SESOI[15], SESOI["1wk"]
d["A"] = (d.week_start <= PHASE_A_END).astype(float); d["B"] = 1.0 - d["A"]
d["summer"] = (d.season.astype(str) == "summer").astype(float); d["winter"] = 1.0 - d["summer"]
log(f"sample {len(d)} cell-weeks, {d.cell.nunique()} cells; phase A {int(d.A.sum())}, B {int(d.B.sum())}")
verdicts, all_rows = {}, []

# ======================= H9 =======================
joint_terms = [f"lf_lag{k}" for k in LEADS]
h9j = fe_fit(d, "net_ru_gain_km2", joint_terms + H6_CONTROLS, joint_terms, sesoi=S1, label="H9 joint (primary)")
h9s = {}
for k in LEADS:
    h9s[k] = fe_fit(d, f"net_t{k}", ["lf"] + H6_CONTROLS, ["lf"], sesoi=S1, label=f"H9 separate lead {k}")
betas = {k: h9j[f"lf_lag{k}"]["beta"] for k in LEADS}
peak = max(betas, key=betas.get)
peak_r = h9j[f"lf_lag{peak}"]
equiv_ge2 = {k: h9j[f"lf_lag{k}"]["equivalence"] for k in LEADS if k >= 2}
h9_ok = bool(peak in (0, 1) and peak_r["significant_both"] and peak_r["beta"] > 0 and all(equiv_ge2.values()))
h9_sep_peak = max(LEADS, key=lambda k: h9s[k]["lf"]["beta"])
log(f"H9 joint: betas {{{', '.join(f'{k}:{v:.3f}' for k, v in betas.items())}}}; peak lead {peak} (p_wild {peak_r['p_wild']:.3f}, p_dk {peak_r['p_dk']:.3f}); "
    f"equivalence k>=2 {equiv_ge2} -> {'supported' if h9_ok else 'not supported'}; separate-form peak {h9_sep_peak}")
all_rows += flat_rows(h9j, "H9", "joint (primary): net_t ~ Σ_k log1p(fires_{t-k}) + momentum + opportunity | cell + week", extra={"outcome": "net_ru_gain_km2", "lead": None})
for k in LEADS:
    all_rows += flat_rows(h9s[k], "H9", f"separate (check): net_{{t+{k}}} ~ log1p(fires_t) + momentum + opportunity | cell + week", extra={"outcome": f"net_t{k}", "lead": k})
for r in all_rows:
    if r["hypothesis"] == "H9" and r["lead"] is None:
        r["lead"] = int(r["param"].replace("lf_lag", "")) if r["param"].startswith("lf_lag") else None
h9_v = "supported" if h9_ok else "not supported"
verdicts["H9"] = {"criterion": "joint distributed-lead regression: largest positive β at lead 0 or 1 and significant under wild-cluster bootstrap AND Driscoll–Kraay; every β at leads ≥ 2 within ±0.65 (1-week SESOI) under both 90% CIs",
                  "result": f"peak lead {peak} (β {peak_r['beta']:.3f}, p_wild {peak_r['p_wild']:.3f}, p_dk {peak_r['p_dk']:.3f}); β by lead " +
                            ", ".join(f"{k}: {betas[k]:.3f}" for k in LEADS) + f"; equivalence at leads ≥2: {sum(equiv_ge2.values())}/{len(equiv_ge2)}; separate-form peak lead {h9_sep_peak}",
                  "verdict": h9_v, "jackson_prediction": "supported", "claude_prediction": "equivalence|inconclusive (PREREG H6 prediction: no lead at a meaningful size)",
                  **who_was_right(h9_v, "supported", "not supported|equivalence|inconclusive"), "label": "confirmatory", "source": "h9_leads.csv"}
save_verdict("H9", verdicts["H9"])

# ======================= H10 =======================
for c in FOUR:
    d[f"l_{c}"] = np.log1p(d[c])
four_l = [f"l_{c}" for c in FOUR]
h10 = fe_fit(d, "net_fwd_3", four_l + H6_CONTROLS, four_l, sesoi=S4, label="H10 primary (net t+1..t+3)")
h10_4 = fe_fit(d, "net_fwd_4", four_l + H6_CONTROLS, four_l, sesoi=S4, label="H10 check (net t+1..t+4)")
a, b = h10["l_fires_big_ua_side"], h10["l_fires_small_ru_side"]
h10_ok = bool(a["beta"] > 0 and a["significant_both"] and b["beta"] < 0 and b["significant_both"])
log("H10: " + "; ".join(f"{c} β {h10[f'l_{c}']['beta']:.3f} (p_wild {h10[f'l_{c}']['p_wild']:.3f}, p_dk {h10[f'l_{c}']['p_dk']:.3f})" for c in FOUR) + f" -> {'supported' if h10_ok else 'not supported'}")
all_rows += flat_rows(h10, "H10", "primary: net_fwd_3 ~ log1p(big_ua) + log1p(small_ua) + log1p(big_ru) + log1p(small_ru) + momentum + opportunity | cell + week", extra={"outcome": "net_fwd_3"})
all_rows += flat_rows(h10_4, "H10", "check: same with net_fwd_4", extra={"outcome": "net_fwd_4"})
h10_v = "supported" if h10_ok else "not supported"
verdicts["H10"] = {"criterion": "four fire terms (big/small × UA/RU side) together, outcome net over t+1..t+3: (a) β(big, UA side) > 0 and (b) β(small, RU side) < 0, each p < 0.05 under both methods",
                   "result": "; ".join(f"{c.replace('fires_', '')} β {h10[f'l_{c}']['beta']:.3f} (p_wild {h10[f'l_{c}']['p_wild']:.3f}, p_dk {h10[f'l_{c}']['p_dk']:.3f})" for c in FOUR) +
                             f"; (a) {'holds' if a['beta'] > 0 and a['significant_both'] else 'fails'}, (b) {'holds' if b['beta'] < 0 and b['significant_both'] else 'fails'}",
                   "verdict": h10_v, "jackson_prediction": "supported", "claude_prediction": "equivalence|inconclusive (PREREG H6 prediction extended: no meaningful fire→movement effect)",
                   **who_was_right(h10_v, "supported", "not supported|equivalence|inconclusive"), "label": "confirmatory", "source": "h10_size_side.csv"}
save_verdict("H10", verdicts["H10"])

# ======================= H11 =======================
d["lf_A"] = d.lf * d.A; d["lf_B"] = d.lf * d.B
h11 = fe_fit(d, "net_fwd_4", ["lf_A", "lf_B"] + H6_CONTROLS, ["lf_A", "lf_B"], sesoi=S4, label="H11 phase")
h11d = fe_fit(d, "net_fwd_4", ["lf", "lf_B"] + H6_CONTROLS, ["lf_B"], sesoi=S4, label="H11 difference (lf_B here = β_B − β_A)")
bA, bB, dif = h11["lf_A"], h11["lf_B"], h11d["lf_B"]
h11_ok = bool(bA["beta"] > 0 and bA["significant_both"] and bB["beta"] < 0 and bB["significant_both"] and dif["beta"] < 0 and dif["significant_both"])
log(f"H11: β_A {bA['beta']:.3f} (p_wild {bA['p_wild']:.3f}, p_dk {bA['p_dk']:.3f}); β_B {bB['beta']:.3f} (p_wild {bB['p_wild']:.3f}, p_dk {bB['p_dk']:.3f}); "
    f"β_A−β_B {-dif['beta']:.3f} (p_wild {dif['p_wild']:.3f}, p_dk {dif['p_dk']:.3f}) -> {'supported' if h11_ok else 'not supported'}")
all_rows += flat_rows(h11, "H11", "net_fwd_4 ~ lf·1[A] + lf·1[B] + momentum + opportunity | cell + week", extra={"outcome": "net_fwd_4"})
all_rows += flat_rows(h11d, "H11", "difference: net_fwd_4 ~ lf + lf·1[B] + controls | FE (coefficient on lf·1[B] = β_B − β_A)", extra={"outcome": "net_fwd_4"})
h11_v = "supported" if h11_ok else "not supported"
verdicts["H11"] = {"criterion": "β_A > 0, β_B < 0 and β_A − β_B > 0, each p < 0.05 under wild-cluster bootstrap AND Driscoll–Kraay (phase A 2022-04-03..2022-11-30, B 2022-12-01..2024-07-07)",
                   "result": f"β_A {bA['beta']:.3f} (p_wild {bA['p_wild']:.3f}, p_dk {bA['p_dk']:.3f}); β_B {bB['beta']:.3f} (p_wild {bB['p_wild']:.3f}, p_dk {bB['p_dk']:.3f}); "
                             f"β_A − β_B {-dif['beta']:.3f} (p_wild {dif['p_wild']:.3f}, p_dk {dif['p_dk']:.3f})",
                   "verdict": h11_v, "jackson_prediction": "supported", "claude_prediction": "equivalence|inconclusive (PREREG H6 prediction: no meaningful effect in either phase)",
                   **who_was_right(h11_v, "supported", "not supported|equivalence|inconclusive"), "label": "confirmatory", "source": "h11_phase.csv"}
save_verdict("H11", verdicts["H11"])

# ======================= H11s =======================
for ph in ["A", "B"]:
    d[f"lf_{ph}_summer"] = d[f"lf_{ph}"] * d.summer; d[f"lf_{ph}_winter"] = d[f"lf_{ph}"] * d.winter
seas_terms = ["lf_A_summer", "lf_A_winter", "lf_B_summer", "lf_B_winter"]
h11s = fe_fit(d, "net_fwd_4", seas_terms + H6_CONTROLS, seas_terms, sesoi=S4, label="H11s season within phase")
h11si = fe_fit(d, "net_fwd_4", ["lf_A", "lf_A_summer", "lf_B", "lf_B_summer"] + H6_CONTROLS, ["lf_A_summer", "lf_B_summer"], sesoi=S4,
               label="H11s interaction (lf_X_summer here = β_X,summer − β_X,winter)")
d["lf_summer"] = d.lf * d.summer
h11sp = fe_fit(d, "net_fwd_4", ["lf", "lf_summer"] + H6_CONTROLS, ["lf", "lf_summer"], sesoi=S4, label="H11s check: phase-pooled season interaction")
per_phase = {}
for ph in ["A", "B"]:
    s, w, i = h11s[f"lf_{ph}_summer"], h11s[f"lf_{ph}_winter"], h11si[f"lf_{ph}_summer"]
    per_phase[ph] = {"beta_summer": s["beta"], "beta_winter": w["beta"], "abs_summer_gt_winter": bool(abs(s["beta"]) > abs(w["beta"])),
                     "interaction_beta": i["beta"], "interaction_p_wild": i["p_wild"], "interaction_p_dk": i["p_dk"], "interaction_significant_both": i["significant_both"],
                     "holds": bool(abs(s["beta"]) > abs(w["beta"]) and i["significant_both"])}
h11s_ok = bool(all(v["holds"] for v in per_phase.values()))
log(f"H11s: A summer {per_phase['A']['beta_summer']:.3f} winter {per_phase['A']['beta_winter']:.3f} (int p_wild {per_phase['A']['interaction_p_wild']:.3f}, p_dk {per_phase['A']['interaction_p_dk']:.3f}); "
    f"B summer {per_phase['B']['beta_summer']:.3f} winter {per_phase['B']['beta_winter']:.3f} (int p_wild {per_phase['B']['interaction_p_wild']:.3f}, p_dk {per_phase['B']['interaction_p_dk']:.3f}) -> {'supported' if h11s_ok else 'not supported'}")
all_rows += flat_rows(h11s, "H11s", "net_fwd_4 ~ lf·1[A]·1[summer] + lf·1[A]·1[winter] + lf·1[B]·1[summer] + lf·1[B]·1[winter] + controls | FE", extra={"outcome": "net_fwd_4"})
all_rows += flat_rows(h11si, "H11s", "interaction: lf·1[X] + lf·1[X]·1[summer] (coefficient = β_X,summer − β_X,winter)", extra={"outcome": "net_fwd_4"})
all_rows += flat_rows(h11sp, "H11s", "check: phase-pooled lf + lf·1[summer]", extra={"outcome": "net_fwd_4"})
h11s_v = "supported" if h11s_ok else "not supported"
verdicts["H11s"] = {"criterion": "within each phase |β_summer| > |β_winter| and the season interaction p < 0.05 under both methods (summer May–Oct)",
                    "result": "; ".join(f"phase {ph}: β_summer {v['beta_summer']:.3f}, β_winter {v['beta_winter']:.3f}, interaction p_wild {v['interaction_p_wild']:.3f}, p_dk {v['interaction_p_dk']:.3f} -> {'holds' if v['holds'] else 'fails'}" for ph, v in per_phase.items()) +
                              f"; pooled check: β_summer−β_winter {h11sp['lf_summer']['beta']:.3f} (p_wild {h11sp['lf_summer']['p_wild']:.3f}, p_dk {h11sp['lf_summer']['p_dk']:.3f})",
                    "verdict": h11s_v, "jackson_prediction": "supported", "claude_prediction": "equivalence|inconclusive (no directional PREREG prediction beyond H6's null)",
                    **who_was_right(h11s_v, "supported", "not supported|equivalence|inconclusive"), "label": "confirmatory", "source": "h11_phase.csv"}
save_verdict("H11s", verdicts["H11s"])

# ======================= outputs =======================
rows = pd.DataFrame(all_rows)
rows[rows.hypothesis == "H9"].to_csv(RES / "h9_leads.csv", index=False)
rows[rows.hypothesis == "H10"].to_csv(RES / "h10_size_side.csv", index=False)
rows[rows.hypothesis.isin(["H11", "H11s"])].to_csv(RES / "h11_phase.csv", index=False)
summary = {"H9": {"joint": h9j, "separate": {str(k): v for k, v in h9s.items()}, "peak_lead_joint": peak, "peak_lead_separate": h9_sep_peak, "equivalence_ge2": {str(k): v for k, v in equiv_ge2.items()}, "supported": h9_ok, "sesoi_1wk": S1},
           "H10": {"primary_net_fwd_3": h10, "check_net_fwd_4": h10_4, "supported": h10_ok},
           "H11": {"phase": h11, "difference": h11d, "beta_A_minus_beta_B": -dif["beta"], "supported": h11_ok},
           "H11s": {"season_within_phase": h11s, "interaction": h11si, "pooled_check": h11sp, "per_phase": per_phase, "supported": h11s_ok},
           "sesoi_4wk": S4, "n": int(len(d)), "n_cells": int(d.cell.nunique()), "runtime_s": round(time.time() - t0, 1)}
json.dump(summary, open(RES / "h9_h11_summary.json", "w"), indent=2, default=str)
for f in ["h9_leads.csv", "h10_size_side.csv", "h11_phase.csv"]:
    write_meta(RES / f, inputs={"panel": PANEL5}, counts={"cell_weeks": int(len(d)), "cells": int(d.cell.nunique()), "phase_A_cell_weeks": int(d.A.sum()), "phase_B_cell_weeks": int(d.B.sum())},
               extra={"definitions": __doc__, "sesoi": {"4wk": S4, "1wk": S1}, "equivalence_rule": "both the CRV1 analytic and the DK 90% CI inside ±SESOI",
                      "licence": "Contains VIINA-derived control aggregates (ODbL); fires NASA FIRMS VIIRS 375 m"})

# ---- figures ----
fig, ax = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
for a_, res, title in [(ax[0], {k: h9j[f"lf_lag{k}"] for k in LEADS}, "joint (primary)"), (ax[1], {k: h9s[k]["lf"] for k in LEADS}, "separate (check)")]:
    for k in LEADS:
        r = res[k]
        a_.plot([k - 0.12] * 2, r["ci90_crv1"], color="C0", lw=3, label="90% CI CRV1" if k == 0 else None)
        a_.plot([k + 0.12] * 2, r["ci90_dk"], color="C1", lw=3, label="90% CI Driscoll–Kraay(4)" if k == 0 else None)
        a_.plot(k, r["beta"], "ko")
    a_.axhspan(-S1, S1, color="green", alpha=0.08, label="±SESOI 0.65 (1-week)"); a_.axhline(0, color="k", lw=0.6)
    a_.set_xticks(LEADS); a_.set_xlabel("lead k (weeks from fires to net gain)"); a_.set_title(f"H9 {title}")
ax[0].set_ylabel("β: km² RU gain per log-unit of fires"); ax[0].legend(fontsize=7)
fig.suptitle(f"H9 lead time, C1 front cells: joint peak at lead {peak}", fontsize=10); fig.tight_layout(); fig.savefig(FIG / "h9_leads.png", dpi=150); plt.close(fig)
caption("h9_leads.png", "confirmatory", f"H9 (PREREG §4): β on log1p(fires) at leads 0, 1, 2, 3, 4, 6 and 8 weeks, C1 front_15 cell-weeks, two-way FE with 4 outcome lags and "
        f"opportunity. Left: joint distributed-lead regression (primary; fires at t−k on net gain at t). Right: one regression per lead (check; fires at t on net at t+k). "
        f"Bars = 90% CIs under CRV1 by cell (blue) and Driscoll–Kraay lag 4 (orange); green band = ±0.65 km², the 1-week SESOI. Joint peak at lead {peak}. Source: data/derived/results/h9_leads.csv.")

fig, ax = plt.subplots(figsize=(7, 3.6))
labs = ["big, UA side", "small, UA side", "big, RU side", "small, RU side"]
for i, c in enumerate(FOUR):
    r = h10[f"l_{c}"]
    ax.plot(r["ci90_crv1"], [i + 0.12] * 2, color="C0", lw=3, label="90% CI CRV1" if i == 0 else None)
    ax.plot(r["ci90_dk"], [i - 0.12] * 2, color="C1", lw=3, label="90% CI Driscoll–Kraay(4)" if i == 0 else None)
    ax.plot(r["beta"], i, "ko")
ax.axvline(0, color="k", lw=0.6); ax.set_yticks(range(4)); ax.set_yticklabels(labs); ax.set_xlabel("β: km² RU gain over t+1..t+3 per log-unit of fires")
ax.set_title("H10: fire size × side of the line, C1 front cells"); ax.legend(fontsize=7)
fig.tight_layout(); fig.savefig(FIG / "h10_size_side.png", dpi=150); plt.close(fig)
caption("h10_size_side.png", "confirmatory", "H10 (PREREG §4): coefficients on log1p of the four front-cell fire counts (FRP ≥/< the season × day/night p75; fire's Voronoi "
        "polygon UA- or RU-held that week) entered together in the H6 specification with outcome net Russian km² gain over t+1..t+3. Prediction: big-UA-side > 0, "
        "small-RU-side < 0. Bars = 90% CIs (CRV1 by cell, Driscoll–Kraay lag 4). Source: data/derived/results/h10_size_side.csv.")

fig, ax = plt.subplots(figsize=(7.5, 3.8))
items = [("A (manoeuvre)", bA), ("B (attrition)", bB), ("A summer", h11s["lf_A_summer"]), ("A winter", h11s["lf_A_winter"]), ("B summer", h11s["lf_B_summer"]), ("B winter", h11s["lf_B_winter"])]
for i, (lab, r) in enumerate(items):
    y = len(items) - 1 - i
    ax.plot(r["ci90_crv1"], [y + 0.12] * 2, color="C0", lw=3, label="90% CI CRV1" if i == 0 else None)
    ax.plot(r["ci90_dk"], [y - 0.12] * 2, color="C1", lw=3, label="90% CI Driscoll–Kraay(4)" if i == 0 else None)
    ax.plot(r["beta"], y, "ko")
ax.axvspan(-S4, S4, color="green", alpha=0.08, label="±SESOI 1.70"); ax.axvline(0, color="k", lw=0.6)
ax.set_yticks(range(len(items))); ax.set_yticklabels([l for l, _ in items][::-1]); ax.set_xlabel("β: km² RU gain over t+1..t+4 per log-unit of fires")
ax.set_title("H11 / H11s: phase and season, C1 front cells"); ax.legend(fontsize=7)
fig.tight_layout(); fig.savefig(FIG / "h11_phase.png", dpi=150); plt.close(fig)
caption("h11_phase.png", "confirmatory", "H11 and H11s (PREREG §4): β on log1p(fires) by phase (A manoeuvre 2022-04-03..2022-11-30; B attrition 2022-12-01..2024-07-07) and by "
        "season within phase (summer May–Oct), H6 specification on C1 front_15 cell-weeks. Prediction: β_A > 0, β_B < 0; |β_summer| > |β_winter| within phase. Bars = 90% CIs "
        "(CRV1 by cell, Driscoll–Kraay lag 4); green band = ±SESOI. Source: data/derived/results/h11_phase.csv.")
log(f"16 done {time.time()-t0:.0f}s")
print(json.dumps({h: {k: v for k, v in verdicts[h].items() if k in ("result", "verdict")} for h in verdicts}, indent=1, ensure_ascii=False))
