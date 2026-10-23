"""PREREG §5 robustness, items 1–7, one row per (hypothesis, item, variant) in data/derived/results/robustness.csv
(every coefficient in robustness_detail.csv). Each row re-runs the hypothesis' pre-stated test under the variant and
records whether the verdict flips relative to verdicts.json (written by scripts 14–18). Nothing here changes a primary
result. Inference as in the primary runs (CRV1 + Webb wild bootstrap 9,999 draws; Driscoll–Kraay(4)), except where
stated. Applicability (n/a reasons are written into the table):
 1. Front band 10 / 25 km: H4, H5, H6, H6b, H9, H10, H11, H11s, H13. SESOI 2.31 / 1.06 for 4-week outcomes (PREREG §3);
    the 1-week SESOI 0.65 (fixed on the 15-km band only) is kept for H9's ≥2-week equivalence.
 2. Rear strip (50–90 km) in place of the 2012–21 baseline: H5 only (monthly ratio of front fires_snpp per cell-week to
    rear-strip fires_snpp per cell-week; same ≥3× in ≥9 of 12 months rule).
 3. Night-only fires (fires_night; kyiv_fires_night): H4 gate, H6, H9, H11, H11s, H12. H10 (no night split of the
    size × side columns), H13 (no night split of deep fires), H5 (no S-NPP night column) n/a.
 4. Drop-one-oblast jackknife (oblast_iso of the cell): H4, H5, H6, H6b, H9, H10, H11, H11s; a hypothesis "flips" if any
    single drop changes its verdict.
 5. VIINA single-source status (dsm / isw / wiki) for the OUTCOME and momentum (the control line and front flags stay
    on the majority status; the fire side split stays on the majority status): H4 (share; gate unchanged), H6, H6b,
    H9, H10, H11, H11s, H12, H13. A source's weeks before it starts reporting (national RU km² = 0) are set missing.
    Economist national series 2022–23: sanity row from panel_report.json (Builder D).
 6. Reverse direction (log1p(fires_t) on net_{t−1..t−4} + opportunity | FE) and lead-2 placebo (fires two weeks AFTER
    the outcome window closes, i.e. fires at t+6 on net_{t+1..t+4}): H6, H10, H11. H9 has its own lead structure and
    H12 already contains the lags −4..−1 (reverse direction), so both n/a.
 7. H3 res-6 panel (control and fire columns only, so the opportunity covariate is dropped and stated): H6, H9, H10,
    H11, H11s, H13. SESOI is the res-5 value (no res-6 SESOI was fixed), so equivalence rows are indicative only.
"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import statsmodels.api as sm
from _panel import *  # noqa

t0 = time.time()
LEADS = [0, 1, 2, 3, 4, 6, 8]
FOUR = ["fires_big_ua_side", "fires_small_ua_side", "fires_big_ru_side", "fires_small_ru_side"]
SRC = ["dsm", "isw", "wiki"]
PRIM = json.load(open(RES / "verdicts.json"))
S1 = SESOI["1wk"]
rows, detail = [], []


def pv(h):
    return PRIM.get(h, {}).get("verdict", "n/a")


def add(h, item, variant, stat, verdict, note="", n=None):
    flip = (verdict != pv(h)) if (pv(h) != "n/a" and verdict not in ("n/a",)) else None
    rows.append({"hypothesis": h, "item": item, "variant": variant, "statistic": stat, "verdict": verdict, "primary_verdict": pv(h), "flip": flip, "n": n, "note": note})
    log(f"  [{item}] {h} {variant}: {verdict}{' FLIP' if flip else ''} | {stat}")


def det(res, h, item, variant):
    for r in flat_rows(res, h, variant, extra={"item": item}):
        detail.append(r)


def cat6(r):
    if r["significant_both"] and r["beta"] >= r["sesoi"]:
        return "supported"
    return "equivalence" if r["equivalence"] else "inconclusive"


# ---------------------------------------------------------------- panel prep (full grid, then filters)
p = load_panel(5)
p["lf_all"] = np.log1p(p.fires); p["lfn_all"] = np.log1p(p.fires_night)
for k in LEADS:
    p[f"lf_lag{k}"] = p.groupby("cell").lf_all.shift(k); p[f"lfn_lag{k}"] = p.groupby("cell").lfn_all.shift(k)
p["lf_t6"] = p.groupby("cell").lf_all.shift(-6)
for c in FOUR:
    p[f"l_{c}"] = np.log1p(p[c]); p[f"l_{c}_t6"] = p.groupby("cell")[f"l_{c}"].shift(-6)
nat = p.groupby("week_start").agg(**{f"ru_{s}": (f"ru_km2_{s}", "sum") for s in SRC}, deep_ru=("fires_deep_ru", "sum")).reset_index()
nat["l_deep"] = np.log1p(nat.deep_ru)
src_start = {s: nat.loc[nat[f"ru_{s}"] > 0, "week_start"].min() for s in SRC}
for s in SRC:
    v = p[f"net_ru_gain_km2_{s}"].where(p.week_start > src_start[s])     # the first reporting week's jump from 0 is also dropped
    p[f"net_{s}"] = v
    g = p.groupby("cell")[f"net_{s}"]
    p[f"net_fwd_3_{s}"] = sum(g.shift(-k) for k in range(1, 4)); p[f"net_fwd_4_{s}"] = sum(g.shift(-k) for k in range(1, 5))
    for k in range(1, 5):
        p[f"net_lag_{k}_{s}"] = g.shift(k)
p = p.merge(nat[["week_start", "l_deep"]], on="week_start", how="left")
log(f"prep done {time.time()-t0:.0f}s; single-source start weeks {dict((k, str(v.date())) for k, v in src_start.items())}")


def base_cfg(S4):
    return {"lf": "lf", "lf_lags": [f"lf_lag{k}" for k in LEADS], "y0": "net_ru_gain_km2", "y3": "net_fwd_3", "y4": "net_fwd_4", "mom": MOMENTUM,
            "opp": ["opportunity"], "four": [f"l_{c}" for c in FOUR], "S4": S4, "S1": S1}


def mk(d):
    d = prep(d); d["woy"] = d.iso_week.astype(int)
    d["A"] = (d.week_start <= PHASE_A_END).astype(float); d["B"] = 1 - d.A
    d["summer"] = (d.season.astype(str) == "summer").astype(float); d["winter"] = 1 - d.summer
    return d


# ---------------------------------------------------------------- runners (each = the primary test, parameterised)
def run_h6(d, cfg, h="H6", item="", variant="", fe="cell + wk"):
    lf = cfg["lf"]; r = fe_fit(d, cfg["y4"], [lf] + cfg["mom"] + cfg["opp"], [lf], sesoi=cfg["S4"], fe=fe)
    det(r, h, item, variant); x = r[lf]
    add(h, item, variant, f"β {x['beta']:.3f} p_wild {x['p_wild']:.3f} p_dk {x['p_dk']:.3f} CI90 crv1 [{x['ci90_crv1'][0]:.2f},{x['ci90_crv1'][1]:.2f}] dk [{x['ci90_dk'][0]:.2f},{x['ci90_dk'][1]:.2f}]", cat6(x), n=r["_n"])


def run_h6b(d, cfg, item, variant):
    d = d.copy(); ph, _ = h2_pdetect(d); d["lfc"] = np.log1p(d.fires / ph)
    r = fe_fit(d, cfg["y4"], ["lfc"] + cfg["mom"] + cfg["opp"], ["lfc"], sesoi=cfg["S4"]); det(r, "H6b", item, variant); x = r["lfc"]
    add("H6b", item, variant, f"β {x['beta']:.3f} p_wild {x['p_wild']:.3f} p_dk {x['p_dk']:.3f} CI90 crv1 [{x['ci90_crv1'][0]:.2f},{x['ci90_crv1'][1]:.2f}] dk [{x['ci90_dk'][0]:.2f},{x['ci90_dk'][1]:.2f}]",
        cat6(x), note="main fit only (no coefficient-draw propagation in robustness)", n=r["_n"])


def run_h9(d, cfg, item, variant):
    terms = cfg["lf_lags"]; r = fe_fit(d, cfg["y0"], terms + cfg["mom"] + cfg["opp"], terms, sesoi=cfg["S1"]); det(r, "H9", item, variant)
    betas = {k: r[t]["beta"] for k, t in zip(LEADS, terms)}; peak = max(betas, key=betas.get); pr = r[terms[LEADS.index(peak)]]
    eq = {k: r[t]["equivalence"] for k, t in zip(LEADS, terms) if k >= 2}
    ok = peak in (0, 1) and pr["significant_both"] and pr["beta"] > 0 and all(eq.values())
    add("H9", item, variant, f"peak lead {peak} β {pr['beta']:.3f} (p_wild {pr['p_wild']:.3f}, p_dk {pr['p_dk']:.3f}); equiv ≥2: {sum(eq.values())}/{len(eq)}; β " + " ".join(f"{k}:{v:.2f}" for k, v in betas.items()),
        "supported" if ok else "not supported", n=r["_n"])


def run_h10(d, cfg, item, variant, four=None, y=None):
    four = four or cfg["four"]; y = y or cfg["y3"]
    r = fe_fit(d, y, four + cfg["mom"] + cfg["opp"], four, sesoi=cfg["S4"]); det(r, "H10", item, variant)
    a, b = r[four[0]], r[four[3]]
    ok = a["beta"] > 0 and a["significant_both"] and b["beta"] < 0 and b["significant_both"]
    add("H10", item, variant, "; ".join(f"{c.split('fires_')[-1].replace('_t6', '')} {r[c]['beta']:.2f} (pw {r[c]['p_wild']:.3f}, pdk {r[c]['p_dk']:.3f})" for c in four),
        "supported" if ok else "not supported", n=r["_n"])


def run_h11(d, cfg, item, variant, lf=None):
    d = d.copy(); lf = lf or cfg["lf"]; d["lfA"] = d[lf] * d.A; d["lfB"] = d[lf] * d.B
    r = fe_fit(d, cfg["y4"], ["lfA", "lfB"] + cfg["mom"] + cfg["opp"], ["lfA", "lfB"], sesoi=cfg["S4"]); det(r, "H11", item, variant)
    rd = fe_fit(d, cfg["y4"], [lf, "lfB"] + cfg["mom"] + cfg["opp"], ["lfB"], sesoi=cfg["S4"]); det(rd, "H11", item, variant + " (difference)")
    A, B, D = r["lfA"], r["lfB"], rd["lfB"]
    ok = A["beta"] > 0 and A["significant_both"] and B["beta"] < 0 and B["significant_both"] and D["beta"] < 0 and D["significant_both"]
    add("H11", item, variant, f"β_A {A['beta']:.3f} (pw {A['p_wild']:.3f}, pdk {A['p_dk']:.3f}); β_B {B['beta']:.3f} (pw {B['p_wild']:.3f}, pdk {B['p_dk']:.3f}); A−B {-D['beta']:.3f} (pw {D['p_wild']:.3f}, pdk {D['p_dk']:.3f})",
        "supported" if ok else "not supported", n=r["_n"])


def run_h11s(d, cfg, item, variant, lf=None):
    d = d.copy(); lf = lf or cfg["lf"]
    for ph in "AB":
        d[f"lf{ph}"] = d[lf] * d[ph]; d[f"lf{ph}s"] = d[f"lf{ph}"] * d.summer; d[f"lf{ph}w"] = d[f"lf{ph}"] * d.winter
    r = fe_fit(d, cfg["y4"], ["lfAs", "lfAw", "lfBs", "lfBw"] + cfg["mom"] + cfg["opp"], ["lfAs", "lfAw", "lfBs", "lfBw"], sesoi=cfg["S4"]); det(r, "H11s", item, variant)
    ri = fe_fit(d, cfg["y4"], ["lfA", "lfAs", "lfB", "lfBs"] + cfg["mom"] + cfg["opp"], ["lfAs", "lfBs"], sesoi=cfg["S4"]); det(ri, "H11s", item, variant + " (interaction)")
    holds = {ph: abs(r[f"lf{ph}s"]["beta"]) > abs(r[f"lf{ph}w"]["beta"]) and ri[f"lf{ph}s"]["significant_both"] for ph in "AB"}
    add("H11s", item, variant, "; ".join(f"{ph}: summer {r[f'lf{ph}s']['beta']:.2f} winter {r[f'lf{ph}w']['beta']:.2f} int pw {ri[f'lf{ph}s']['p_wild']:.3f} pdk {ri[f'lf{ph}s']['p_dk']:.3f}" for ph in "AB"),
        "supported" if all(holds.values()) else "not supported", n=r["_n"])


def run_h4(d, item, variant, lf="lf", gain_col="net_ru_gain_km2", draws=2000, gate=True):
    d = d.copy(); q1 = float(d.opportunity.quantile(0.25)); d["bq"] = d.opportunity <= q1; d["gain"] = d[gain_col].clip(lower=0)
    gp, gtxt = True, ""
    if gate:
        g = fe_fit(d, lf, ["opportunity"], ["opportunity"], fe="cell + woy"); det(g, "H4", item, variant + " (gate)"); gx = g["opportunity"]
        gp = gx["beta"] > 0 and gx["p_wild"] < 0.01; gtxt = f"gate β {gx['beta']:.4f} p_wild {gx['p_wild']:.3f} {'pass' if gp else 'FAIL'}; "
    share = lambda df: df.loc[df.bq, "gain"].sum() / df.gain.sum() if df.gain.sum() > 0 else np.nan
    pt = share(d); lo, hi = np.nanpercentile(block_boot_cells(d, share, draws), [2.5, 97.5])
    v = ("supported" if lo > 0.30 else "not supported") if gp else "not testable"
    add("H4", item, variant, f"{gtxt}share {pt:.3f} [{lo:.3f},{hi:.3f}] (Q1 cut {q1:.0f})", v, n=len(d))


def run_h5(d, item, variant):
    d = d.copy(); d["month"] = d.week_start.dt.month
    g = d.groupby("month").agg(f=("fires_snpp", "sum"), b=("base_fires_mean", "sum")); ratio = (g.f / g.b).reindex(range(1, 13))
    n_ge3 = int((ratio >= 3).sum())
    add("H5", item, variant, f"{n_ge3}/12 months ratio ≥3 (point); overall {d.fires_snpp.sum() / d.base_fires_mean.sum():.2f}", "supported" if n_ge3 >= 9 else "not supported", note="point estimates only", n=len(d))


def run_h12(nw, ycol, xcol, item, variant):
    nn = nw.sort_values("week_start").reset_index(drop=True).copy()
    c1 = nn.week_start.between(C1_START, C1_END); S_NAT = SESOI[15] * float(nn.loc[c1, "n_front15_r5"].median())
    x = np.log1p(nn[xcol].astype(float)); X = pd.DataFrame({f"j{j:+d}": x.shift(j) for j in range(-4, 5)})
    for m in range(1, 5):
        X[f"lag{m}"] = nn[ycol].shift(m)
    X = sm.add_constant(pd.concat([X, pd.get_dummies(nn.iso_week.astype(int), prefix="woy", drop_first=True, dtype=float)], axis=1))
    dd = pd.concat([nn[[ycol]], X], axis=1)[c1].dropna()
    res = sm.OLS(dd[ycol], dd.drop(columns=[ycol])).fit(cov_type="HAC", cov_kwds={"maxlags": 4, "use_correction": True}); ci = res.conf_int(alpha=0.10)
    terms = [c for c in dd.columns if c.startswith("j")]
    within = all(max(abs(ci.loc[c, 0]), abs(ci.loc[c, 1])) < S_NAT for c in terms); sig = [c for c in terms if res.pvalues[c] < 0.05]
    ans = "no relationship" if within else ("inconclusive" if not sig else ("coordinated" if all(res.params[c] > 0 for c in sig) else ("opposite" if all(res.params[c] < 0 for c in sig) else "mixed")))
    v = {"no relationship": "equivalence", "inconclusive": "inconclusive"}.get(ans, "supported")
    add("H12", item, variant, f"answer {ans}; β " + " ".join(f"{c}:{res.params[c]:.0f}(p{res.pvalues[c]:.2f})" for c in terms), v, note=f"primary answer {PRIM.get('H12', {}).get('answer')}", n=int(res.nobs))


def run_h13(d, cfg, item, variant, y=None):
    y = y or cfg["y4"]; r = fe_fit(d, y, ["l_deep"] + cfg["mom"] + cfg["opp"], ["l_deep"], sesoi=cfg["S4"], fe="cell + woy"); det(r, "H13", item, variant); x = r["l_deep"]
    add("H13", item, variant, f"β {x['beta']:.3f} p_wild {x['p_wild']:.3f} p_dk {x['p_dk']:.3f} CI90 crv1 [{x['ci90_crv1'][0]:.2f},{x['ci90_crv1'][1]:.2f}] dk [{x['ci90_dk'][0]:.2f},{x['ci90_dk'][1]:.2f}]",
        "equivalence" if x["equivalence"] else ("supported" if x["significant_both"] and abs(x["beta"]) >= cfg["S4"] else "inconclusive"), n=r["_n"])


def run_all_fe(d, cfg, item, variant, with_h6b=True, with_h13=None):
    run_h6(d, cfg, item=item, variant=variant)
    if with_h6b:
        run_h6b(d, cfg, item, variant)
    run_h9(d, cfg, item, variant); run_h10(d, cfg, item, variant); run_h11(d, cfg, item, variant); run_h11s(d, cfg, item, variant)
    if with_h13 is not None:
        run_h13(with_h13, cfg, item, variant)


d15 = mk(c1_front(p, 15)); e15 = mk(c1_front(p, 15, period="E"))

# ---------------------------------------------------------------- 1. front band
for band in (10, 25):
    log(f"== item 1 band {band}")
    d = mk(c1_front(p, band)); e = mk(c1_front(p, band, period="E")); cfg = base_cfg(SESOI[band])
    run_h4(d, "1 band", f"{band} km"); run_h5(d, "1 band", f"{band} km")
    run_all_fe(d, cfg, "1 band", f"{band} km", with_h13=e)

# ---------------------------------------------------------------- 2. rear strip reference (H5)

def checkpoint(tag):
    """Write partial tables after every item so a killed run keeps what it has (added 2026-10-23)."""
    pd.DataFrame(rows).to_csv(RES / "robustness.partial.csv", index=False)
    pd.DataFrame(detail).to_csv(RES / "robustness_detail.partial.csv", index=False)
    log(f"checkpoint after {tag}: {len(rows)} rows")

checkpoint("item 1")
log("== item 2 rear strip")
c1m = p.week_start.between(C1_START, C1_END)
rear = p[c1m & p.rear_strip.astype(bool) & p.in_ukraine.astype(bool)].copy(); rear["month"] = rear.week_start.dt.month
fr = d15.assign(month=d15.week_start.dt.month)
num = fr.groupby("month").fires_snpp.sum() / fr.groupby("month").size(); den = rear.groupby("month").fires_snpp.sum() / rear.groupby("month").size()
ratio_rear = (num / den).reindex(range(1, 13)); n_ge3 = int((ratio_rear >= 3).sum())
add("H5", "2 rear strip", "front fires_snpp per cell-week / rear-strip (50–90 km) fires_snpp per cell-week, C1", f"{n_ge3}/12 months ≥3; monthly " + " ".join(f"{m}:{v:.2f}" for m, v in ratio_rear.items()),
    "supported" if n_ge3 >= 9 else "not supported", note=f"rear-strip cell-weeks {len(rear)}", n=len(fr))

# ---------------------------------------------------------------- 3. night-only fires
checkpoint("item 2")
log("== item 3 night")
cfgn = base_cfg(SESOI[15]); cfgn["lf"] = "lfn"; cfgn["lf_lags"] = [f"lfn_lag{k}" for k in LEADS]
dn = d15.copy(); dn["lfn"] = np.log1p(dn.fires_night)
run_h4(dn, "3 night", "fires_night", lf="lfn")
run_h6(dn, cfgn, item="3 night", variant="log1p(fires_night)"); run_h9(dn, cfgn, "3 night", "log1p(fires_night) lags"); run_h11(dn, cfgn, "3 night", "log1p(fires_night)"); run_h11s(dn, cfgn, "3 night", "log1p(fires_night)")
natw = pd.read_csv(NATIONAL, parse_dates=["week_start"])
run_h12(natw, "net_ru_gain_km2", "kyiv_fires_night", "3 night", "kyiv_fires_night")
for h, why in [("H10", "no night split of the size × side columns"), ("H13", "no night split of deep fires"), ("H5", "no S-NPP night column")]:
    add(h, "3 night", "n/a", "", "n/a", note=why)

# ---------------------------------------------------------------- 4. drop-one-oblast jackknife
checkpoint("item 3")
log("== item 4 jackknife")
cfg15 = base_cfg(SESOI[15]); n_before = len(rows)
for ob in sorted(d15.oblast_iso.dropna().unique()):
    d = d15[d15.oblast_iso != ob]
    run_h4(d, "4 jackknife", f"drop {ob}", draws=500); run_h5(d, "4 jackknife", f"drop {ob}")
    run_all_fe(d, cfg15, "4 jackknife", f"drop {ob}")
jk = pd.DataFrame(rows[n_before:])
for h, g in jk.groupby("hypothesis"):
    add(h, "4 jackknife", "SUMMARY over drops", f"verdicts: {g.verdict.value_counts().to_dict()}", "flips" if g.flip.any() else pv(h), note="any single-oblast drop changing the verdict counts as a flip")
for h in ["H12", "H13"]:
    add(h, "4 jackknife", "n/a", "", "n/a", note="national / E-period spec; no oblast dimension")

# ---------------------------------------------------------------- 5. VIINA single-source outcomes
checkpoint("item 4")
log("== item 5 single source")
natw_src = natw.copy()
for s in SRC:
    natw_src[f"net_{s}"] = natw_src[f"net_ru_gain_km2_{s}"].where(natw_src.week_start > src_start[s])
for s in SRC:
    cfg = base_cfg(SESOI[15]); cfg.update({"y0": f"net_{s}", "y3": f"net_fwd_3_{s}", "y4": f"net_fwd_4_{s}", "mom": [f"net_lag_{k}_{s}" for k in range(1, 5)]})
    run_h4(d15, "5 source", f"status_{s}", gain_col=f"net_{s}", gate=False)
    run_all_fe(d15, cfg, "5 source", f"status_{s} outcome", with_h13=e15)
    run_h12(natw_src, f"net_{s}", "kyiv_fires", "5 source", f"status_{s} national outcome")
rep = json.load(open(DERIVED / "panel" / "panel_report.json")).get("economist_check_2022_23", {})
add("national series", "5 source", "Economist (ISW-based) national RU km² 2022-02..2023-10 vs VIINA majority",
    f"corr levels {rep.get('corr_levels')}, corr weekly changes {rep.get('corr_weekly_changes')}, median diff VIINA−Economist {rep.get('median_diff_km2_viina_minus_economist')} km², weeks {rep.get('weeks_compared')}", "sanity", note="from panel_report.json (Builder D)")

# ---------------------------------------------------------------- 6. reverse direction and lead-2 placebo
checkpoint("item 5")
log("== item 6 reverse / placebo")
r = fe_fit(d15, "lf", MOMENTUM + ["opportunity"], MOMENTUM, sesoi=None); det(r, "H6", "6 reverse", "lf_t ~ net_lag_1..4 + opportunity | FE")
sig = [m for m in MOMENTUM if r[m]["significant_both"]]
add("H6", "6 reverse", "reverse: log1p(fires_t) on net_{t−1..t−4}", "; ".join(f"{m} {r[m]['beta']:.4f} (pw {r[m]['p_wild']:.3f}, pdk {r[m]['p_dk']:.3f})" for m in MOMENTUM),
    "reverse effect present" if sig else "no reverse effect", note="β in log-units of fires per km² of prior-week RU gain", n=r["_n"])
rp = fe_fit(d15, "net_fwd_4", ["lf_t6"] + H6_CONTROLS, ["lf_t6"], sesoi=SESOI[15]); det(rp, "H6", "6 placebo", "net_fwd_4 ~ lf_{t+6}")
x = rp["lf_t6"]; add("H6", "6 placebo", "lead-2 placebo: fires at t+6 on net_{t+1..t+4}", f"β {x['beta']:.3f} pw {x['p_wild']:.3f} pdk {x['p_dk']:.3f} CI90 crv1 [{x['ci90_crv1'][0]:.2f},{x['ci90_crv1'][1]:.2f}]",
                    "placebo significant (warning)" if x["significant_both"] else "placebo null", n=rp["_n"])
cfgp = base_cfg(SESOI[15])
run_h10(d15, cfgp, "6 placebo", "four terms at t+6 on net_fwd_3", four=[f"l_{c}_t6" for c in FOUR])
run_h11(d15, cfgp, "6 placebo", "lf_{t+6} by phase", lf="lf_t6")
for h, why in [("H9", "own lead structure (leads 0–8 are the test)"), ("H12", "lags −4..−1 in the primary spec are the reverse direction"), ("H13", "exploratory; not run")]:
    add(h, "6 reverse/placebo", "n/a", "", "n/a", note=why)

# ---------------------------------------------------------------- 7. res-6 panel
checkpoint("item 6")
log("== item 7 res-6")
p6 = load_panel(6)
p6["lf_all"] = np.log1p(p6.fires)
for k in LEADS:
    p6[f"lf_lag{k}"] = p6.groupby("cell").lf_all.shift(k)
for c in FOUR:
    p6[f"l_{c}"] = np.log1p(p6[c])
p6 = p6.merge(nat[["week_start", "l_deep"]], on="week_start", how="left")
d6 = mk(c1_front(p6, 15)); e6 = mk(c1_front(p6, 15, period="E")); cfg6 = base_cfg(SESOI[15]); cfg6["opp"] = []
log(f"res-6 C1 front_15 sample {len(d6)} cell-weeks, {d6.cell.nunique()} cells")
import functools as _ft
_fe_fit_full = fe_fit
fe_fit = _ft.partial(_fe_fit_full, reps=999)   # res-6 only: 999 Webb draws (stated in the rows' note); primary items keep 9,999
run_all_fe(d6, cfg6, "7 res-6", "res-6 cells, no opportunity covariate; wild bootstrap 999 draws", with_h6b=False, with_h13=e6)
fe_fit = _fe_fit_full
for h, why in [("H4", "no opportunity at res 6"), ("H5", "no baseline columns at res 6"), ("H6b", "no H2 covariates at res 6"), ("H12", "national spec")]:
    add(h, "7 res-6", "n/a", "", "n/a", note=why)

checkpoint("item 7")
# ---------------------------------------------------------------- write
R = pd.DataFrame(rows); D = pd.DataFrame(detail)
R.to_csv(RES / "robustness.csv", index=False); D.to_csv(RES / "robustness_detail.csv", index=False)
flips = R[(R.flip == True) | (R.verdict == "flips")][["hypothesis", "item", "variant", "verdict", "primary_verdict"]]  # noqa: E712
summary = {"rows": int(len(R)), "flips": flips.to_dict(orient="records"), "n_flips": int(len(flips)), "src_start_weeks": {k: str(v.date()) for k, v in src_start.items()},
           "jackknife_oblasts": sorted(d15.oblast_iso.dropna().unique().tolist()), "runtime_s": round(time.time() - t0, 1)}
json.dump(summary, open(RES / "robustness_summary.json", "w"), indent=2, default=str)
write_meta(RES / "robustness.csv", inputs={"panel_r5": PANEL5, "panel_r6": PANEL6, "national_week": NATIONAL, "verdicts": RES / "verdicts.json"},
           counts={"rows": int(len(R)), "detail_rows": int(len(D)), "flips": int(len(flips))},
           extra={"definitions": __doc__, "summary": summary, "licence": "Contains VIINA-derived control aggregates (ODbL); fires NASA FIRMS VIIRS 375 m"})
log(f"19 done {time.time()-t0:.0f}s; {len(R)} rows, {len(flips)} flips")
print(flips.to_string())
