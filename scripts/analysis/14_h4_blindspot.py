"""H4 Blind spot (PREREG §4, confirmatory). planning/PANEL.md Builder E.

Gate first: log1p(fires) ~ opportunity | cell FE + week-of-year FE on C1 front_15 cell-weeks; passes if the coefficient
is > 0 with p < 0.01 (CRV1 by cell with the Webb wild-cluster bootstrap, 9,999 draws; Driscoll–Kraay(4) reported too;
the gate uses the wild-bootstrap p as the cluster-robust p). If it fails, H4 is "not testable with this product".
Test: share of C1 Russian km² gained (Σ of positive weekly net_ru_gain_km2 over C1 front_15 cell-weeks) that falls in
cell-weeks in the bottom quartile of `opportunity` (quartile cut fixed on the full sample, ties at the cut included
in the bottom quartile, i.e. opportunity <= Q1). Cell block bootstrap 2,000 draws; supported if the 95% CI excludes
30% from below (lower bound > 0.30).
"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from _panel import *  # noqa

t0 = time.time(); DRAWS = 2000
p = load_panel(5, ["h3_r5", "week_start", "iso_week", "front_15", "front_10", "front_25", "fires", "net_ru_gain_km2", "opportunity",
                   "net_ru_gain_km2_dsm", "net_ru_gain_km2_isw", "net_ru_gain_km2_wiki"])
d = prep(c1_front(p, 15)); d["woy"] = d.iso_week.astype(int)

# ---- gate ----
gate = fe_fit(d, "lf", ["opportunity"], ["opportunity"], fe="cell + woy", label="H4 gate")
g = gate["opportunity"]
gate_pass = bool(g["beta"] > 0 and g["p_wild"] < 0.01)
log(f"H4 gate: beta {g['beta']:.5f} p_wild {g['p_wild']:.4f} p_dk {g['p_dk']:.4f} -> {'PASS' if gate_pass else 'FAIL'}")


# ---- share ----
q1 = float(d.opportunity.quantile(0.25))
d["bottom_q"] = d.opportunity <= q1
d["gain"] = d.net_ru_gain_km2.clip(lower=0)


def share(df, col="gain"):
    tot = df[col].sum()
    return df.loc[df.bottom_q, col].sum() / tot if tot > 0 else np.nan


pt = share(d)
boot = block_boot_cells(d, share, DRAWS)
lo, hi = np.nanpercentile(boot, [2.5, 97.5])
supported = bool(lo > 0.30)
log(f"H4 share {pt:.3f} [{lo:.3f}, {hi:.3f}]  bottom-quartile cut opportunity<= {q1:.0f}; share of cell-weeks {d.bottom_q.mean():.3f}")

# descriptive by opportunity quartile
d["opp_q"] = pd.qcut(d.opportunity.rank(method="first"), 4, labels=["Q1 (lowest)", "Q2", "Q3", "Q4"])
byq = d.groupby("opp_q", observed=True).agg(cell_weeks=("gain", "size"), ru_gain_km2=("gain", "sum"), ru_loss_km2=("net_ru_gain_km2", lambda x: -x.clip(upper=0).sum()),
                                           fires=("fires", "sum"), opp_min=("opportunity", "min"), opp_max=("opportunity", "max")).reset_index()
byq["share_gain"] = byq.ru_gain_km2 / byq.ru_gain_km2.sum()
byq.to_csv(RES / "h4_by_opportunity_quartile.csv", index=False)

# alt sources (robustness 5, descriptive here; same cut)
alt = {}
for src in ["dsm", "isw", "wiki"]:
    d[f"gain_{src}"] = d[f"net_ru_gain_km2_{src}"].clip(lower=0)
    alt[src] = float(share(d, f"gain_{src}"))

h4 = {"gate": {"beta_opportunity": g["beta"], "se_crv1": g["se_crv1"], "p_crv1": g["p_crv1"], "p_wild": g["p_wild"], "p_dk": g["p_dk"], "n": gate["_n"], "n_cells": gate["_n_cells"],
               "criterion": "beta > 0 and p < 0.01", "pass": gate_pass, "formula": gate["_formula"]},
      "share_bottom_quartile": float(pt), "ci95": [float(lo), float(hi)], "draws": DRAWS, "q1_opportunity_cut": q1,
      "share_cell_weeks_bottom_q": float(d.bottom_q.mean()), "total_ru_gain_km2_c1_front15": float(d.gain.sum()),
      "ru_gain_km2_bottom_q": float(d.loc[d.bottom_q, "gain"].sum()), "criterion": "95% CI lower bound > 0.30",
      "supported": supported if gate_pass else None, "alt_source_shares_same_cut": alt, "runtime_s": round(time.time() - t0, 1)}
json.dump(h4, open(RES / "h4_blindspot.json", "w"), indent=2)
pd.DataFrame(flat_rows(gate, "H4", "gate: lf ~ opportunity | cell + week-of-year")).to_csv(RES / "h4_gate.csv", index=False)
write_meta(RES / "h4_blindspot.json", inputs={"panel": PANEL5}, counts={"cell_weeks": len(d), "cells": int(d.cell.nunique())},
           extra={"definitions": __doc__, "licence": "Contains VIINA-derived control aggregates (ODbL); fires NASA FIRMS VIIRS 375 m"})
verdict = ("supported" if supported else "not supported") if gate_pass else "not testable"
save_verdict("H4", {"criterion": "gate: log1p(fires) on opportunity (cell FE + week-of-year FE) beta > 0, p < 0.01; then share of C1 RU km² gained in bottom-quartile-opportunity cell-weeks with 95% cell block-bootstrap CI excluding 30% from below",
                    "result": f"gate beta {g['beta']:.4f} per opportunity unit (p_wild {g['p_wild']:.4f}, p_dk {g['p_dk']:.4f}) -> {'pass' if gate_pass else 'fail'}; share {pt:.3f} (95% CI {lo:.3f}–{hi:.3f}), bottom quartile = opportunity <= {q1:.0f}",
                    "verdict": verdict, "jackson_prediction": "supported", "claude_prediction": "supported", **who_was_right(verdict, "supported", "supported"),
                    "label": "confirmatory", "source": "h4_blindspot.json"})

fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
ax[0].bar(byq.opp_q.astype(str), byq.share_gain, color=["C3", "C1", "C0", "C2"]); ax[0].axhline(0.30, color="k", ls="--", lw=1, label="30% criterion")
ax[0].errorbar([0], [pt], yerr=[[pt - lo], [hi - pt]], fmt="none", ecolor="k", capsize=4)
ax[0].set_ylabel("share of C1 RU km² gained"); ax[0].set_title("H4: gain by detection-opportunity quartile"); ax[0].legend()
ax[1].hist(boot, bins=40, color="grey"); ax[1].axvline(0.30, color="k", ls="--"); ax[1].axvline(pt, color="C3"); ax[1].set_xlabel("bootstrap share (bottom quartile)"); ax[1].set_title("cell block bootstrap, 2,000 draws")
fig.tight_layout(); fig.savefig(FIG / "h4_blindspot.png", dpi=150); plt.close(fig)
caption("h4_blindspot.png", "confirmatory", f"H4 (PREREG §4): share of Russian km² gained in C1 (Σ positive weekly net gain over front_15 cell-weeks) by quartile of "
        f"weekly detection opportunity; the bottom quartile (opportunity ≤ {q1:.0f}) carries the 95% cell block-bootstrap CI (2,000 draws). Dashed = the 30% criterion. "
        f"Gate regression (log1p fires on opportunity, cell + week-of-year FE): β = {g['beta']:.4f}, wild-bootstrap p = {g['p_wild']:.3f}. Source: data/derived/results/h4_blindspot.json.")
log(f"14 done {time.time()-t0:.0f}s"); print(json.dumps(h4, indent=1))
