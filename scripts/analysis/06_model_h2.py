"""H2 Detection model (PREREG §4 H2, confirmatory). Builder C.

Features exactly as PREREG: tcc at overpass (= min tcc over the event window), snow flag (any sde≥1 cm in the
window), hours since last overpass (window mean of hours_since_prev), day/night (= share of night overpasses),
land-cover class, event type, month. Primary: statsmodels Logit, numerics standardised on train, one-hot
categoricals (reference = modal level). Secondary: LightGBM, same features. Fit on split==train, AUC on
split==test with a 1,000-draw bootstrap CI over test events (seed 20261014). Calibration by decile; coefficient table.
Secondary run restricted to strike+shelling+infrastructure+vehicle_loss.
Inputs: data/interim/analysis/events_detect.parquet (from 05). Models → data/interim/analysis/models/.
"""
from __future__ import annotations
import sys, json, time, pickle
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import statsmodels.api as sm
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, roc_curve, log_loss, brier_score_loss
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from _common import INTERIM, DERIVED, ROOT, MODELS, SEED, write_meta, log, sha256_file
from _detect import RESTRICTED_TYPES

RES = DERIVED / "results"; FIG = ROOT / "figures"; MODELS.mkdir(parents=True, exist_ok=True)
t0 = time.time()
rng = np.random.default_rng(SEED)

NUM = ["min_tcc", "any_snow", "hours_since_prev", "share_night"]
CAT = ["landcover_class", "event_type", "month"]
IN = INTERIM / "events_detect.parquet"
df = pd.read_parquet(IN)
n0 = len(df)
df = df[df["min_tcc"].notna()].copy()           # 24 events with no overpass rows in their cell → dropped
df["month"] = df["month"].astype(int)
df["any_snow"] = df["any_snow"].astype(float)
df["hours_since_prev"] = df["hours_since_prev"].fillna(df["hours_since_prev"].median())
df["y"] = df["detected"].astype(int)
log(f"{n0:,} events, {len(df):,} with covariates; train {int((df.split=='train').sum()):,} test {int((df.split=='test').sum()):,}")


def design(d: pd.DataFrame, spec: dict | None = None):
    """Standardised numerics + one-hot categoricals (drop reference). spec fixes means/sds/levels from train."""
    if spec is None:
        spec = {"mean": d[NUM].mean().to_dict(), "sd": d[NUM].std(ddof=0).replace(0, 1).to_dict(),
                "levels": {c: sorted(d[c].astype(str).unique().tolist()) for c in CAT},
                "ref": {c: d[c].astype(str).value_counts().idxmax() for c in CAT}}
    X = pd.DataFrame(index=d.index)
    for c in NUM:
        X[c] = (d[c].astype(float) - spec["mean"][c]) / spec["sd"][c]
    for c in CAT:
        s = d[c].astype(str)
        for lv in spec["levels"][c]:
            if lv == spec["ref"][c]:
                continue
            X[f"{c}={lv}"] = (s == lv).astype(float)
    X.insert(0, "const", 1.0)
    return X, spec


def auc_boot(y, p, draws=1000):
    y = np.asarray(y); p = np.asarray(p)
    a = roc_auc_score(y, p)
    bs = []
    for _ in range(draws):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            continue
        bs.append(roc_auc_score(y[i], p[i]))
    return float(a), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def calib(y, p, k=10):
    q = pd.qcut(pd.Series(p).rank(method="first"), k, labels=False)
    g = pd.DataFrame({"y": y, "p": p, "dec": q}).groupby("dec").agg(n=("y", "size"), mean_pred=("p", "mean"), obs_rate=("y", "mean"))
    return g.reset_index()


def fit_all(d: pd.DataFrame, tag: str):
    tr, te = d[d.split == "train"], d[d.split == "test"]
    Xtr, spec = design(tr); Xte, _ = design(te, spec)
    Xte = Xte.reindex(columns=Xtr.columns, fill_value=0.0)
    logit = sm.Logit(tr["y"].values, Xtr).fit(disp=0, maxiter=200, method="newton")
    p_te = logit.predict(Xte); p_tr = logit.predict(Xtr)
    auc_l, lo_l, hi_l = auc_boot(te["y"].values, p_te.values)
    coef = pd.DataFrame({"term": Xtr.columns, "coef": logit.params.values, "se": logit.bse.values,
                         "z": logit.tvalues.values, "p": logit.pvalues.values,
                         "odds_ratio": np.exp(logit.params.values)})
    coef["ci_lo"] = np.exp(logit.params.values - 1.96 * logit.bse.values); coef["ci_hi"] = np.exp(logit.params.values + 1.96 * logit.bse.values)
    coef["model"] = "logit"; coef["run"] = tag
    coef["note"] = ["standardised (per 1 train-SD)" if t in NUM else ("intercept" if t == "const" else f"vs ref") for t in Xtr.columns]
    # LightGBM on raw features, categoricals native
    feats = NUM + CAT
    Ltr = tr[feats].copy(); Lte = te[feats].copy()
    for c in CAT:
        cats = pd.CategoricalDtype(sorted(d[c].astype(str).unique()))
        Ltr[c] = Ltr[c].astype(str).astype(cats); Lte[c] = Lte[c].astype(str).astype(cats)
    gbm = lgb.LGBMClassifier(n_estimators=600, learning_rate=0.03, num_leaves=15, min_child_samples=100,
                             subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                             random_state=SEED, verbose=-1)
    gbm.fit(Ltr, tr["y"].values, categorical_feature=CAT)
    g_te = gbm.predict_proba(Lte)[:, 1]
    auc_g, lo_g, hi_g = auc_boot(te["y"].values, g_te)
    imp = pd.DataFrame({"term": feats, "gain": gbm.booster_.feature_importance("gain")})
    imp["gain_share"] = imp["gain"] / imp["gain"].sum(); imp["model"] = "lgbm"; imp["run"] = tag
    out = dict(run=tag, n_train=int(len(tr)), n_test=int(len(te)), base_rate_train=float(tr.y.mean()), base_rate_test=float(te.y.mean()),
               logit=dict(auc_test=auc_l, auc_ci=[lo_l, hi_l], auc_train=float(roc_auc_score(tr.y, p_tr)),
                          logloss_test=float(log_loss(te.y, p_te)), brier_test=float(brier_score_loss(te.y, p_te)),
                          pseudo_r2=float(logit.prsquared), converged=bool(logit.mle_retvals.get("converged", True)), n_params=int(len(logit.params))),
               lgbm=dict(auc_test=auc_g, auc_ci=[lo_g, hi_g], auc_train=float(roc_auc_score(tr.y, gbm.predict_proba(Ltr)[:, 1])),
                         logloss_test=float(log_loss(te.y, g_te)), brier_test=float(brier_score_loss(te.y, g_te))))
    cal_l = calib(te.y.values, p_te.values); cal_l["model"] = "logit"; cal_l["run"] = tag
    cal_g = calib(te.y.values, g_te); cal_g["model"] = "lgbm"; cal_g["run"] = tag
    return out, coef, imp, pd.concat([cal_l, cal_g]), logit, spec, gbm, (te.y.values, p_te.values, g_te)


results, coefs, imps, cals = {}, [], [], []
for tag, d in [("primary_all_types", df), ("secondary_restricted", df[df.event_type.isin(RESTRICTED_TYPES)])]:
    out, coef, imp, cal, logit, spec, gbm, (y, pl, pg) = fit_all(d, tag)
    results[tag] = out; coefs.append(coef); imps.append(imp); cals.append(cal)
    logit.save(MODELS / f"h2_logit_{tag}.pickle")
    with open(MODELS / f"h2_logit_{tag}_spec.json", "w") as f:
        json.dump({"spec": spec, "columns": list(logit.params.index), "params": logit.params.to_dict(),
                   "cov_params": logit.cov_params().values.tolist(), "num": NUM, "cat": CAT}, f, indent=1, default=str)
    gbm.booster_.save_model(str(MODELS / f"h2_lgbm_{tag}.txt"))
    if tag == "primary_all_types":
        fig, ax = plt.subplots(1, 2, figsize=(10, 4))
        for p, lab, c in [(pl, f"logit AUC {out['logit']['auc_test']:.3f}", "#1d3557"), (pg, f"LightGBM AUC {out['lgbm']['auc_test']:.3f}", "#e63946")]:
            fpr, tpr, _ = roc_curve(y, p); ax[0].plot(fpr, tpr, label=lab, color=c)
        ax[0].plot([0, 1], [0, 1], "k:", lw=0.8); ax[0].set_xlabel("false positive rate"); ax[0].set_ylabel("true positive rate"); ax[0].legend(); ax[0].set_title("H2 ROC on V-test")
        for m, c in [("logit", "#1d3557"), ("lgbm", "#e63946")]:
            cc = cal[cal.model == m]; ax[1].plot(cc.mean_pred, cc.obs_rate, "o-", color=c, label=m)
        ax[1].plot([0, cal.mean_pred.max()], [0, cal.mean_pred.max()], "k:", lw=0.8); ax[1].set_xlabel("mean predicted P(detect)"); ax[1].set_ylabel("observed recall"); ax[1].set_title("Calibration by decile (V-test)"); ax[1].legend()
        fig.tight_layout(); fig.savefig(FIG / "h2_roc_calibration.png", dpi=150); plt.close(fig)
        cs = coef[coef.term != "const"].copy(); cs = cs.reindex(cs.coef.abs().sort_values(ascending=False).index).head(20)
        fig, ax = plt.subplots(figsize=(7, 6))
        ax.errorbar(cs.coef, cs.term, xerr=1.96 * cs.se, fmt="o", color="#1d3557", capsize=2); ax.axvline(0, color="k", lw=0.8)
        ax.set_xlabel("logit coefficient (numerics per train SD; categoricals vs reference)"); ax.set_title("H2 logistic: 20 largest coefficients"); ax.invert_yaxis()
        fig.tight_layout(); fig.savefig(FIG / "h2_coefficients.png", dpi=150); plt.close(fig)

pd.concat(coefs).to_csv(RES / "h2_coefficients.csv", index=False)
pd.concat(imps).to_csv(RES / "h2_lgbm_importance.csv", index=False)
pd.concat(cals).to_csv(RES / "h2_calibration.csv", index=False)
prim = results["primary_all_types"]
verdict = {"auc_logit_ge_0.75": prim["logit"]["auc_test"] >= 0.75, "auc_logit_ci_lo_ge_0.75": prim["logit"]["auc_ci"][0] >= 0.75,
           "auc_logit_lt_0.65_bounds_only_for_H6b": prim["logit"]["auc_test"] < 0.65,
           "H2_supported": prim["logit"]["auc_test"] >= 0.75, "prereg_prediction": "supported, AUC 0.75–0.85",
           "note": "primary = logistic, all event types, V-test; LightGBM secondary"}
json.dump({"results": results, "verdict": verdict, "features": {"numeric": NUM, "categorical": CAT},
           "definitions": {"min_tcc": "tcc at overpass = minimum ERA5 tcc over the event window's overpasses",
                           "any_snow": "any overpass in window with ERA5-Land sde ≥ 1 cm", "hours_since_prev": "window mean of hours since the cell's previous overpass (any satellite)",
                           "share_night": "day/night = share of the window's overpasses flagged Night", "dropped_no_overpass_rows": int(n0 - len(df))},
           "model_files": {k: {"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p)} for k, p in
                           {"logit_primary": MODELS / "h2_logit_primary_all_types.pickle", "logit_primary_spec": MODELS / "h2_logit_primary_all_types_spec.json",
                            "lgbm_primary": MODELS / "h2_lgbm_primary_all_types.txt"}.items()}},
          open(RES / "h2_auc.json", "w"), indent=2, default=str)
write_meta(RES / "h2_auc.json", inputs={"events_detect": IN}, counts={"events": len(df), "train": int((df.split == "train").sum()), "test": int((df.split == "test").sum())},
           extra={"primary": prim, "verdict": verdict, "runtime_s": round(time.time() - t0, 1)})
log(f"H2 done {time.time()-t0:.0f}s: {json.dumps(prim)}\n{verdict}")
