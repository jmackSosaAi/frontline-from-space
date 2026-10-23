"""Shared helpers for the C1 panel tests (scripts 13–19). Spec: PREREG.md §3–§5, DESIGN D12–D13, planning/PANEL.md.

Inference (PREREG H6 / DESIGN D13): two-way FE (cell, week) via pyfixest.feols; (a) CRV1 by cell with a wild-cluster
bootstrap (Webb weights, 9,999 draws, seed 20261014, `wildboottest` package through pyfixest); (b) Driscoll–Kraay with
Bartlett kernel, bandwidth 4 (linearmodels.PanelOLS). "Significant" = p < 0.05 under both. "Equivalence" = the 90% CI
lies within ±SESOI under BOTH the CRV1 (analytic) and the DK interval (the stricter reading; stated in every meta).
"""
from __future__ import annotations
import json, warnings, time
import numpy as np, pandas as pd
from pathlib import Path
from _common import ROOT, INTERIM, DERIVED, SEED, write_meta, log  # noqa: F401

warnings.filterwarnings("ignore")
RES = DERIVED / "results"; RES.mkdir(parents=True, exist_ok=True)
FIG = ROOT / "figures"; FIG.mkdir(exist_ok=True)
PANEL5 = INTERIM / "panel_r5_week.parquet"; PANEL6 = INTERIM / "panel_r6_week.parquet"
NATIONAL = DERIVED / "panel" / "national_week.csv"
CONST = json.load(open(DERIVED / "prereg_constants.json"))
SESOI = {15: CONST["sesoi"]["primary"]["sesoi_km2"],
         10: CONST["sesoi"]["alternatives"]["band_10km"]["sesoi_km2"],
         25: CONST["sesoi"]["alternatives"]["band_25km"]["sesoi_km2"],
         "1wk": CONST["sesoi"]["alternatives"]["horizon_1wk_15km"]["sesoi_km2"]}
C1_START, C1_END = pd.Timestamp("2022-04-04"), pd.Timestamp("2024-07-01")   # ISO-week Mondays inside C1
E_START, E_END = pd.Timestamp("2024-07-08"), pd.Timestamp("2025-12-29")
PHASE_A_END = pd.Timestamp("2022-11-28")
MOMENTUM = ["net_lag_1", "net_lag_2", "net_lag_3", "net_lag_4"]
H6_CONTROLS = MOMENTUM + ["opportunity"]
B_PRIMARY = 9999
P_CLIP = 0.02


def load_panel(res: int = 5, columns=None) -> pd.DataFrame:
    p = pd.read_parquet(PANEL5 if res == 5 else PANEL6, columns=columns)
    p["week_start"] = pd.to_datetime(p["week_start"])
    cell = "h3_r5" if res == 5 else "h3_r6"
    p = p.sort_values([cell, "week_start"]).reset_index(drop=True)
    p["cell"] = pd.factorize(p[cell])[0]
    return p


def add_shift(p: pd.DataFrame, col: str, k: int, name: str, cell="cell") -> pd.DataFrame:
    """name = col at t+k within cell (panel is a complete cell × week grid, checked in 11_panel: 202 weeks per cell)."""
    p[name] = p.groupby(cell)[col].shift(-k)
    return p


def c1_front(p: pd.DataFrame, band: int = 15, period="C1") -> pd.DataFrame:
    if period == "C1":
        m = p["week_start"].between(C1_START, C1_END)
    else:
        m = p["week_start"].between(E_START, E_END)
    return p[m & p[f"front_{band}"].astype(bool)].copy()


def prep(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["wk"] = pd.factorize(d["week_start"])[0]
    d["lf"] = np.log1p(d["fires"])
    return d


def fe_fit(d: pd.DataFrame, y: str, rhs: list[str], params: list[str], *, sesoi: float | None = None,
           reps: int = B_PRIMARY, fe="cell + wk", cluster="cell", dk_bandwidth=4, label="") -> dict:
    """Two-way FE regression with the PREREG H6 inference. Returns {param: {...}} plus n/n_cells.
    Rows with any NaN in y/rhs are dropped (count reported)."""
    import pyfixest as pf
    from linearmodels.panel import PanelOLS
    cols = [y] + rhs
    dd = d.dropna(subset=cols).copy()
    n_drop = len(d) - len(dd)
    fml = f"{y} ~ {' + '.join(rhs)} | {fe}"
    t0 = time.time()
    fit = pf.feols(fml, data=dd, vcov={"CRV1": cluster})
    tidy = fit.tidy(); ci90 = fit.confint(alpha=0.10)
    out = {"_n": int(len(dd)), "_n_cells": int(dd[cluster].nunique()), "_n_dropped_nan": int(n_drop), "_formula": fml,
           "_label": label, "_reps": reps}
    # DK
    idx = dd.set_index([cluster, "week_start"])
    fe_terms = " + EntityEffects + TimeEffects" if fe == "cell + wk" else " + EntityEffects"
    dk = PanelOLS.from_formula(f"{y} ~ {' + '.join(rhs)}{fe_terms}", data=idx).fit(
        cov_type="kernel", kernel="bartlett", bandwidth=dk_bandwidth)
    dkci = dk.conf_int(level=0.90)
    for prm in params:
        r = {"beta": float(tidy.loc[prm, "Estimate"]), "se_crv1": float(tidy.loc[prm, "Std. Error"]),
             "p_crv1": float(tidy.loc[prm, "Pr(>|t|)"]),
             "ci90_crv1": [float(ci90.loc[prm].iloc[0]), float(ci90.loc[prm].iloc[1])],
             "se_dk": float(dk.std_errors[prm]), "p_dk": float(dk.pvalues[prm]),
             "ci90_dk": [float(dkci.loc[prm, "lower"]), float(dkci.loc[prm, "upper"])]}
        if reps:
            wb = fit.wildboottest(reps=reps, param=prm, weights_type="webb", seed=SEED)
            r["p_wild"] = float(wb["Pr(>|t|)"]); r["t_wild"] = float(wb["t value"])
        else:
            r["p_wild"] = float("nan")
        r["significant_both"] = bool(r["p_wild"] < 0.05 and r["p_dk"] < 0.05)
        if sesoi is not None:
            r["sesoi"] = float(sesoi)
            r["equivalence"] = bool(max(abs(r["ci90_crv1"][0]), abs(r["ci90_crv1"][1]),
                                        abs(r["ci90_dk"][0]), abs(r["ci90_dk"][1])) < sesoi)
        out[prm] = r
    out["_runtime_s"] = round(time.time() - t0, 1)
    return out


def flat_rows(res: dict, hyp: str, spec: str, extra: dict | None = None) -> list[dict]:
    rows = []
    for k, v in res.items():
        if k.startswith("_"):
            continue
        row = {"hypothesis": hyp, "spec": spec, "param": k, "n": res["_n"], "n_cells": res["_n_cells"], **v}
        row["ci90_crv1_lo"], row["ci90_crv1_hi"] = row.pop("ci90_crv1")
        row["ci90_dk_lo"], row["ci90_dk_hi"] = row.pop("ci90_dk")
        if extra:
            row.update(extra)
        rows.append(row)
    return rows


def save_verdict(hyp: str, entry: dict) -> None:
    """One entry per hypothesis in data/derived/results/verdicts.json (merged, never overwritten wholesale)."""
    vp = RES / "verdicts.json"
    v = json.load(open(vp)) if vp.exists() else {}
    entry = {"hypothesis": hyp, **entry}
    v[hyp] = entry
    v = dict(sorted(v.items(), key=lambda kv: (len(kv[0]), kv[0])))
    vp.write_text(json.dumps(v, indent=2, ensure_ascii=False, default=str))


def who_was_right(verdict: str, jackson: str | None, claude: str | None) -> dict:
    """jackson/claude: the predicted verdict category ('supported', 'not supported', 'equivalence', 'inconclusive',
    'equivalence|inconclusive', None = no directional prediction)."""
    def ok(pred):
        if pred is None:
            return None
        return verdict in pred.split("|")
    return {"jackson_right": ok(jackson), "claude_right": ok(claude)}


def caption(name: str, kind: str, text: str) -> None:
    cp = FIG / "CAPTIONS.md"
    hdr = "\n# Figure captions — C1 panel tests (Builder E, 2026-10-23)\n"
    cur = cp.read_text() if cp.exists() else ""
    if hdr.strip() not in cur:
        cur += hdr
    line = f"\n**{name}** — **{kind}.** {text}\n"
    if f"**{name}**" in cur:   # replace an existing caption for this figure (re-runs)
        import re
        cur = re.sub(rf"\n\*\*{re.escape(name)}\*\*.*?\n(?=\n|\Z)", line.rstrip("\n") + "\n", cur, flags=re.S)
    else:
        cur += line
    cp.write_text(cur)


def block_boot_cells(d: pd.DataFrame, stat, draws: int, cell="cell", seed=SEED):
    """Cell block bootstrap: resample cells with replacement, concatenate their rows, apply stat(df)."""
    rng = np.random.default_rng(seed)
    cells = d[cell].unique(); groups = {c: g for c, g in d.groupby(cell)}
    out = []
    for _ in range(draws):
        pick = rng.choice(cells, size=len(cells), replace=True)
        out.append(stat(pd.concat([groups[c] for c in pick], ignore_index=True)))
    return np.asarray(out)


def h2_pdetect(d: pd.DataFrame, n_draws: int = 0, seed=SEED):
    """Score the H2 primary logit on panel cell-week covariates. Mapping (stated in metas): min_tcc <- min_tcc_mean,
    any_snow <- snow_share (share of snow cell-days, used as the binary flag's expectation), hours_since_prev <-
    hours_since_prev_mean, share_night <- share_night, landcover_class <- landcover_mode, event_type <- 'strike'
    (reference level: a generic front-line strike), month <- month of the ISO week's Monday. Returns p_hat (clipped at
    P_CLIP) and, if n_draws, a (n, n_draws) matrix of clipped P from N(β̂, Cov) coefficient draws."""
    S = json.load(open(INTERIM / "models" / "h2_logit_primary_all_types_spec.json"))
    spec, cols = S["spec"], S["columns"]
    beta = np.array([S["params"][c] for c in cols]); cov = np.array(S["cov_params"])
    X = pd.DataFrame(index=d.index); X["const"] = 1.0
    num = {"min_tcc": "min_tcc_mean", "any_snow": "snow_share", "hours_since_prev": "hours_since_prev_mean",
           "share_night": "share_night"}
    for c, src in num.items():
        X[c] = (d[src].astype(float) - spec["mean"][c]) / spec["sd"][c]
    lc = d["landcover_mode"].astype(str); mo = d["week_start"].dt.month.astype(str)
    for lv in spec["levels"]["landcover_class"]:
        if lv != spec["ref"]["landcover_class"]:
            X[f"landcover_class={lv}"] = (lc == lv).astype(float)
    for lv in spec["levels"]["month"]:
        if lv != spec["ref"]["month"]:
            X[f"month={lv}"] = (mo == lv).astype(float)
    Xm = X.reindex(columns=cols, fill_value=0.0).values
    p = np.clip(1 / (1 + np.exp(-(Xm @ beta))), P_CLIP, 1)
    if not n_draws:
        return p, None
    rng = np.random.default_rng(seed)
    draws = rng.multivariate_normal(beta, cov, size=n_draws)
    P = np.clip(1 / (1 + np.exp(-(Xm @ draws.T))), P_CLIP, 1)
    return p, P
