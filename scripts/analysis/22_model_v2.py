"""Model v2 for P(detect) of V events — EXPLORATORY ONLY (planning/DETECTION_MODEL.md "Model v2" note, 2026-10-22).

Not in PREREG. The confirmatory H2 result (06_model_h2.py, logit AUC 0.737) and verdicts.json are untouched.
Same events, same drop rule (min_tcc not null) and same month-level train/test split as v1 (events_detect.parquet,
seed 20261014). All tuning/selection uses grouped CV (groups = calendar month) on TRAIN months only; the test set is
scored once per final model. No ACLED, no test labels used for any choice.

New features (per event, over the same 48-h window and the event's h3_r6 cell as v1):
  1. Sensor-cloud calibration (from 04_firemask_sample.py). For each window overpass, P(sensor fire-mask = cloud | ERA5
     tcc) is taken from that granule's own tcc-bin cloud shares when the granule was sampled, the event lies in the
     firemask corridor and the bin has ≥20 blocks; otherwise from a pooled season × day/night × tcc-bin curve built from
     all sampled granules (no detection labels involved). Window aggregates: expected sensor-clear looks, P(any
     sensor-clear look), share of overpasses with a granule-specific value, min granule-specific P(cloud) (LightGBM only).
  2. Cross-track (swath-edge) position. For each overpass, the event's position across the granule's 4-corner CMR
     footprint: frac = |2u−1| where u = d1/(d1+d2), d = great-circle distance to the two along-track edges. Validated
     against FIRMS pixel size (track) on matched fires; relative pixel area(frac) is calibrated from those fires and
     used to weight clear looks ("effective clear looks" = Σ P(clear)·area(0)/area(frac)).
  3. Burnable fraction within 500 m (ESA WorldCover 2021, classes tree/shrub/grass/crop/wetland) and built-up fraction.
  4. Interactions: winter × share_night, min_tcc × any_snow, expected-clear × any_snow.
Outputs: data/interim/analysis/models/v2/, data/derived/results/model_v2.{json,csv} (+ _meta.json),
figures/model_v2_vs_v1.png. Event-level features are cached in data/interim/analysis/models/v2/features_v2.parquet
(interim only, not published).
"""
from __future__ import annotations
import sys, json, time, pickle
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd, duckdb, shapely
import statsmodels.api as sm
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, roc_curve, log_loss, brier_score_loss
from sklearn.model_selection import GroupKFold
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from _common import INTERIM, DERIVED, ROOT, RAW, MODELS, SEED, write_meta, log, sha256_file, season
from _detect import OVERPASSES, NIGHT_HOURS_UTC

t0 = time.time()
RES = DERIVED / "results"; FIG = ROOT / "figures"; OUT = MODELS / "v2"; OUT.mkdir(parents=True, exist_ok=True)
IN = INTERIM / "events_detect.parquet"
FP = RAW / "cmr_footprints/viirs_granule_footprints_2022_2025.parquet"
FM = INTERIM / "firemask_granule_cloud.parquet"
FIRES = INTERIM / "fires.parquet"
CORRIDOR = dict(lon_min=32.5, lon_max=40.0, lat_min=46.3, lat_max=50.5)   # 04_firemask_sample.py
SATMAP = {"S-NPP": "N", "NOAA-20": "N20", "NOAA-21": "N21"}
BURNABLE = [10, 20, 30, 40, 90]
FEAT_CACHE = OUT / "features_v2.parquet"
FORCE = "--rebuild" in sys.argv

# ---------------------------------------------------------------- v1 data, identical handling to 06_model_h2.py
NUM1 = ["min_tcc", "any_snow", "hours_since_prev", "share_night"]
CAT = ["landcover_class", "event_type", "month"]
df = pd.read_parquet(IN)
n0 = len(df)
df = df[df["min_tcc"].notna()].copy()
df["month"] = df["month"].astype(int)
df["any_snow"] = df["any_snow"].astype(float)
df["hours_since_prev"] = df["hours_since_prev"].fillna(df["hours_since_prev"].median())
df["y"] = df["detected"].astype(int)
df["ym"] = df["date"].dt.strftime("%Y-%m")
log(f"{n0:,} events, {len(df):,} modelled; train {int((df.split=='train').sum()):,} test {int((df.split=='test').sum()):,}")


def unitvec(lon, lat):
    lo, la = np.radians(lon), np.radians(lat)
    return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1)


def load_footprint_corners():
    fp = pd.read_parquet(FP, columns=["granule_ur", "product", "satellite", "start_utc", "is_latest", "footprint_wkt"])
    fp = fp[(fp.is_latest == 1) & fp["product"].isin(["VNP14IMG", "VJ114IMG", "VJ214IMG"])].drop_duplicates("granule_ur")
    g = shapely.from_wkt(fp.footprint_wkt.values)
    coords = [shapely.get_coordinates(x) for x in g]
    ok = np.array([len(c) == 5 for c in coords])
    fp = fp[ok].reset_index(drop=True)
    C = np.stack([c[:4] for c, o in zip(coords, ok) if o])
    V = unitvec(C[..., 0], C[..., 1])                    # n,4,3
    # which opposite-edge pair is along-track: the pair whose local direction is closer to north–south
    def nsdot(a, b):
        m = a + b; m /= np.linalg.norm(m, axis=-1, keepdims=True)
        t = b - a; t -= (t * m).sum(-1, keepdims=True) * m; t /= np.linalg.norm(t, axis=-1, keepdims=True)
        nl = np.array([0, 0, 1.0]) - m[..., 2:3] * m; nl /= np.linalg.norm(nl, axis=-1, keepdims=True)
        return np.abs((t * nl).sum(-1))
    along12 = (nsdot(V[:, 1], V[:, 2]) + nsdot(V[:, 3], V[:, 0])) > (nsdot(V[:, 0], V[:, 1]) + nsdot(V[:, 2], V[:, 3]))
    idx = np.where(along12[:, None], [1, 2, 3, 0], [0, 1, 2, 3])
    E = np.take_along_axis(V, idx[:, :, None], axis=1)  # edges (E0,E1) and (E2,E3) are along-track
    fp["sat"] = fp.satellite.map(SATMAP)
    fp["start"] = pd.to_datetime(fp.start_utc, utc=True).astype("datetime64[ns, UTC]")
    info = {"footprints_used": int(len(fp)), "dropped_not_4_corners": int((~ok).sum()), "share_edges_12_30_along": float(along12.mean())}
    return fp[["granule_ur", "sat", "start"]], E, info


def cross_track_frac(P, E):
    def d(a, b):
        n = np.cross(a, b); n /= np.linalg.norm(n, axis=-1, keepdims=True)
        return np.abs(np.arcsin(np.clip((P * n).sum(-1), -1, 1)))
    d1 = d(E[:, 0], E[:, 1]); d2 = d(E[:, 2], E[:, 3])
    return np.abs(2 * d1 / (d1 + d2) - 1).astype(np.float32)


def pixel_area_curve(fp, E, gidx):
    """Calibrate relative FIRMS pixel area (scan×track) vs cross-track frac on a seeded fire sample."""
    con = duckdb.connect(); con.execute("SET TimeZone='UTC'"); con.execute("SET threads=4")
    f = con.sql(f"""SELECT satellite, acq_ts_utc, lat, lon, scan, track FROM '{FIRES}'
                    WHERE lat BETWEEN 44 AND 53 AND lon BETWEEN 22 AND 41
                    USING SAMPLE 200000 ROWS (reservoir, {SEED})""").df()
    f["acq_ts_utc"] = pd.to_datetime(f.acq_ts_utc, utc=True).astype("datetime64[ns, UTC]")
    fp = fp.assign(gi=np.arange(len(fp)))
    parts = []
    for s, ff in f.groupby("satellite"):
        gg = fp[fp.sat == s].sort_values("start")
        m = pd.merge_asof(ff.sort_values("acq_ts_utc"), gg[["start", "gi"]], left_on="acq_ts_utc", right_on="start", direction="backward")
        parts.append(m[(m.acq_ts_utc - m.start) < pd.Timedelta(minutes=6)])
    m = pd.concat(parts)
    m["frac"] = cross_track_frac(unitvec(m.lon.values, m.lat.values), E[m.gi.values.astype(int)])
    m["area"] = m.scan * m.track
    edges = np.linspace(0, 1, 21)
    m["b"] = np.clip(np.digitize(m.frac, edges) - 1, 0, 19)
    curve = m.groupby("b").agg(n=("area", "size"), frac=("frac", "median"), area=("area", "median")).reset_index()
    curve["rel_area"] = curve.area / curve.area.iloc[0]
    rho = float(m[["frac", "track"]].corr(method="spearman").iloc[0, 1])
    return curve, {"fires_sampled": int(len(f)), "fires_matched_to_granule": int(len(m)), "spearman_frac_vs_track": rho,
                   "spearman_frac_vs_scan": float(m[["frac", "scan"]].corr(method="spearman").iloc[0, 1]),
                   "rel_area_at_edge_bin": float(curve.rel_area.iloc[-1])}


def burnable_500m(lat, lon):
    import rasterio
    from rasterio.windows import Window
    lat = np.asarray(lat, float); lon = np.asarray(lon, float)
    burn = np.full(len(lat), np.nan, np.float32); built = np.full(len(lat), np.nan, np.float32)
    t_lat = (np.floor(lat / 3) * 3).astype(int); t_lon = (np.floor(lon / 3) * 3).astype(int)
    for la, lo in set(zip(t_lat.tolist(), t_lon.tolist())):
        p = RAW / "worldcover" / f"ESA_WorldCover_10m_2021_v200_N{la:02d}E{lo:03d}_Map.tif"
        ii = np.where((t_lat == la) & (t_lon == lo))[0]
        if not p.exists():
            continue
        with rasterio.open(p) as r:
            res_y = abs(r.res[1]); res_x = r.res[0]
            for i in ii:
                ry = 500 / 111320 / res_y; rx = 500 / (111320 * np.cos(np.radians(lat[i]))) / res_x
                row, col = r.index(lon[i], lat[i])
                h, w = int(np.ceil(ry)), int(np.ceil(rx))
                a = r.read(1, window=Window(col - w, row - h, 2 * w + 1, 2 * h + 1), boundless=True, fill_value=0)
                yy, xx = np.mgrid[-h:h + 1, -w:w + 1]
                disk = ((yy / ry) ** 2 + (xx / rx) ** 2 <= 1) & (a > 0)
                if disk.sum() == 0:
                    continue
                v = a[disk]
                burn[i] = np.isin(v, BURNABLE).mean(); built[i] = (v == 50).mean()
    return burn, built


def build_features(ev: pd.DataFrame):
    info = {}
    fp, E, info["footprints"] = load_footprint_corners()
    # window overpass rows (same join as _detect.window_covariates)
    con = duckdb.connect(); con.execute("SET TimeZone='UTC'"); con.execute("SET threads=4")
    con.register("ev", ev[["uid", "h3_r6", "w0", "w1"]])
    night = f"(CASE WHEN o.day_night='Night' THEN 1 WHEN o.day_night='Day' THEN 0 ELSE (CASE WHEN hour(o.start_utc) IN ({','.join(map(str, sorted(NIGHT_HOURS_UTC)))}) THEN 1 ELSE 0 END) END)"
    ov = con.sql(f"""SELECT e.uid, o.granule_ur, o.tcc, o.sde_cm, {night} AS is_night
        FROM ev e JOIN read_parquet('{OVERPASSES}/*/*.parquet', hive_partitioning=1) o
        ON o.h3_r6 = e.h3_r6 AND o.start_utc >= e.w0 AND o.start_utc <= e.w1""").df()
    log(f"window overpass rows: {len(ov):,}")
    ov = ov.merge(ev[["uid", "lat", "lon", "month"]], on="uid", how="left")
    gmap = pd.Series(np.arange(len(fp)), index=fp.granule_ur.values)
    gi = ov.granule_ur.map(gmap)
    info["overpass_rows"] = int(len(ov)); info["overpass_rows_no_footprint"] = int(gi.isna().sum())
    ok = gi.notna().values
    ov["frac"] = np.nan
    ov.loc[ok, "frac"] = cross_track_frac(unitvec(ov.lon.values[ok], ov.lat.values[ok]), E[gi[ok].astype(int).values])
    curve, info["pixel_area_validation"] = pixel_area_curve(fp, E, gi)
    log(f"cross-track validation: {info['pixel_area_validation']}")
    ov["rel_area"] = np.interp(ov.frac.fillna(0.5), curve.frac.values, curve.rel_area.values).astype(np.float32)
    # sensor cloud calibration
    fm = pd.read_parquet(FM)
    fm["granule_ur"] = fm.granule.str.replace(r"\.nc$", "", regex=True)
    fm["season"] = season(pd.to_datetime(fm.start_utc).dt.month)
    fm["dn"] = np.where(fm.day_night == "Both", np.where(pd.to_datetime(fm.start_utc).dt.hour.isin(list(NIGHT_HOURS_UTC)), "Night", "Day"), fm.day_night)
    rows = []
    for b in range(10):
        rows.append(fm[["season", "dn"]].assign(bin=b, n=fm[f"bin{b}_n"], cloud=fm[f"bin{b}_cloud"]))
    pooled = pd.concat(rows).groupby(["season", "dn", "bin"])[["n", "cloud"]].sum().reset_index()
    pooled["p_cloud_pooled"] = pooled.cloud / pooled.n.where(pooled.n > 0)
    ov["bin"] = np.clip((ov.tcc.values * 10).astype(int), 0, 9)
    ov["season"] = season(ov.month.astype(int))
    ov["dn"] = np.where(ov.is_night == 1, "Night", "Day")
    ov = ov.merge(pooled[["season", "dn", "bin", "p_cloud_pooled"]], on=["season", "dn", "bin"], how="left")
    gb = fm.set_index("granule_ur")
    in_corr = ov.lon.between(CORRIDOR["lon_min"], CORRIDOR["lon_max"]) & ov.lat.between(CORRIDOR["lat_min"], CORRIDOR["lat_max"])
    sampled = ov.granule_ur.isin(gb.index) & in_corr
    ov["p_cloud_direct"] = np.nan
    if sampled.any():
        s = ov[sampled]
        n_ = np.array([gb.at[g, f"bin{b}_n"] for g, b in zip(s.granule_ur, s.bin)], float)
        c_ = np.array([gb.at[g, f"bin{b}_cloud"] for g, b in zip(s.granule_ur, s.bin)], float)
        ov.loc[sampled, "p_cloud_direct"] = np.where(n_ >= 20, c_ / np.maximum(n_, 1), np.nan)
    ov["p_cloud"] = ov.p_cloud_direct.fillna(ov.p_cloud_pooled).fillna(ov.tcc).clip(0, 1)
    ov["p_clear"] = 1 - ov.p_cloud
    ov["eff_clear"] = ov.p_clear / ov.rel_area
    ov["has_direct"] = ov.p_cloud_direct.notna().astype(float)
    info["firemask"] = {"overpass_rows_in_corridor": int(in_corr.sum()), "rows_granule_sampled_in_corridor": int(sampled.sum()),
                        "rows_with_granule_specific_p_cloud": int(ov.p_cloud_direct.notna().sum()),
                        "pooled_curve_cells": int(len(pooled))}
    ov["log_pc"] = np.log(np.clip(ov.p_cloud, 1e-4, 1))
    agg = ov.groupby("uid").agg(
        exp_clear_sensor=("p_clear", "sum"), log_p_all_cloudy=("log_pc", "sum"), eff_clear_looks=("eff_clear", "sum"),
        best_eff_look=("eff_clear", "max"), frac_min=("frac", "min"), frac_mean=("frac", "mean"),
        share_firemask_direct=("has_direct", "mean"), min_p_cloud_direct=("p_cloud_direct", "min"))
    agg["p_any_clear_sensor"] = 1 - np.exp(agg.pop("log_p_all_cloudy"))
    # frac of the clearest look (lowest calibrated p_cloud)
    best = ov.sort_values(["uid", "p_cloud", "frac"]).drop_duplicates("uid").set_index("uid")
    agg["frac_best_look"] = best.frac
    out = ev[["uid"]].merge(agg.reset_index(), on="uid", how="left")
    burn, built = burnable_500m(ev.lat.values, ev.lon.values)
    out["burnable_500m"] = burn; out["built_500m"] = built
    info["burnable_nan"] = int(np.isnan(burn).sum())
    curve.to_csv(OUT / "pixel_area_curve.csv", index=False)
    pooled.to_csv(OUT / "sensor_cloud_curve.csv", index=False)
    return out, info


if FEAT_CACHE.exists() and not FORCE:
    feats = pd.read_parquet(FEAT_CACHE); finfo = json.loads((OUT / "features_v2_info.json").read_text())
    log("features loaded from cache")
else:
    feats, finfo = build_features(df)
    feats.to_parquet(FEAT_CACHE, index=False)
    (OUT / "features_v2_info.json").write_text(json.dumps(finfo, indent=1, default=str))
    log(f"features built {time.time()-t0:.0f}s")

df = df.merge(feats, on="uid", how="left")
for c in ["frac_min", "frac_mean", "frac_best_look"]:
    df[c] = df[c].fillna(df.loc[df.split == "train", c].median())
for c in ["burnable_500m", "built_500m"]:
    df[c] = df[c].fillna(df.loc[df.split == "train", c].median())
df["winter"] = (season(df["month"]) == "winter").astype(float)
df["x_winter_night"] = df.winter * df.share_night
df["x_tcc_snow"] = df.min_tcc * df.any_snow
df["x_clear_snow"] = df.exp_clear_sensor * df.any_snow

G_CLOUD = ["exp_clear_sensor", "p_any_clear_sensor", "share_firemask_direct"]
G_SCAN = ["frac_min", "frac_mean", "frac_best_look", "eff_clear_looks", "best_eff_look"]
G_BURN = ["burnable_500m", "built_500m"]
G_INT = ["x_winter_night", "x_tcc_snow", "x_clear_snow"]
NUM2 = NUM1 + G_CLOUD + G_SCAN + G_BURN + G_INT
LGB_EXTRA = ["min_p_cloud_direct"]   # NaN where no sampled granule; tree model only


def design(d, num, spec=None):
    if spec is None:
        spec = {"mean": d[num].mean().to_dict(), "sd": d[num].std(ddof=0).replace(0, 1).to_dict(),
                "levels": {c: sorted(d[c].astype(str).unique().tolist()) for c in CAT},
                "ref": {c: d[c].astype(str).value_counts().idxmax() for c in CAT}}
    X = pd.DataFrame(index=d.index)
    for c in num:
        X[c] = (d[c].astype(float) - spec["mean"][c]) / spec["sd"][c]
    for c in CAT:
        s = d[c].astype(str)
        for lv in spec["levels"][c]:
            if lv != spec["ref"][c]:
                X[f"{c}={lv}"] = (s == lv).astype(float)
    X.insert(0, "const", 1.0)
    return X, spec


def fit_logit(tr, te, num):
    Xtr, spec = design(tr, num); Xte, _ = design(te, num, spec)
    Xte = Xte.reindex(columns=Xtr.columns, fill_value=0.0)
    m = sm.Logit(tr.y.values, Xtr).fit(disp=0, maxiter=300, method="newton")
    return m, spec, np.asarray(m.predict(Xte)), np.asarray(m.predict(Xtr))


def lgb_frame(d, feats):
    X = d[feats].copy()
    for c in CAT:
        if c in X:
            X[c] = X[c].astype(str).astype(pd.CategoricalDtype(sorted(df[c].astype(str).unique())))
    return X


V1_LGB = dict(n_estimators=600, learning_rate=0.03, num_leaves=15, min_child_samples=100, subsample=0.8, subsample_freq=1,
              colsample_bytree=0.8, reg_lambda=1.0)


def fit_lgb(tr, te, feats, params):
    g = lgb.LGBMClassifier(**params, random_state=SEED, verbose=-1, n_jobs=4)
    g.fit(lgb_frame(tr, feats), tr.y.values, categorical_feature=[c for c in CAT if c in feats])
    return g, g.predict_proba(lgb_frame(te, feats))[:, 1]


tr, te = df[df.split == "train"].copy(), df[df.split == "test"].copy()
gkf = GroupKFold(n_splits=5)
folds = list(gkf.split(tr, tr.y, groups=tr.ym))


def cv_auc(kind, num=None, feats=None, params=None):
    a = []
    for i_tr, i_va in folds:
        a_tr, a_va = tr.iloc[i_tr], tr.iloc[i_va]
        if kind == "logit":
            _, _, p, _ = fit_logit(a_tr, a_va, num)
        else:
            _, p = fit_lgb(a_tr, a_va, feats, params)
        a.append(roc_auc_score(a_va.y, p))
    return float(np.mean(a)), float(np.std(a))


# ---------------------------------------------------------------- CV on train months: ablation + LightGBM tuning
log("grouped CV (5 folds by month, train only) …")
ablation = []
sets = {"v1": NUM1, "v1+cloud": NUM1 + G_CLOUD, "v1+scan": NUM1 + G_SCAN, "v1+burn": NUM1 + G_BURN,
        "v1+interactions": NUM1 + G_INT, "v2_all": NUM2}
for name, num in sets.items():
    m_, s_ = cv_auc("logit", num=num)
    ablation.append({"model": "logit", "feature_set": name, "cv_auc_mean": m_, "cv_auc_sd": s_})
    m_, s_ = cv_auc("lgbm", feats=num + CAT + (LGB_EXTRA if name == "v2_all" else []), params=V1_LGB)
    ablation.append({"model": "lgbm_v1params", "feature_set": name, "cv_auc_mean": m_, "cv_auc_sd": s_})
ablation = pd.DataFrame(ablation)
log("ablation (CV AUC):\n" + ablation.pivot(index="feature_set", columns="model", values="cv_auc_mean").round(4).to_string())

FEATS2 = NUM2 + LGB_EXTRA + CAT
grid = []
for nl in [7, 15, 31]:
    for mcs in [50, 150, 400]:
        for ne, lr in [(400, 0.03), (900, 0.015)]:
            for cs in [0.6, 0.9]:
                grid.append(dict(n_estimators=ne, learning_rate=lr, num_leaves=nl, min_child_samples=mcs, subsample=0.8,
                                 subsample_freq=1, colsample_bytree=cs, reg_lambda=1.0))
tune = []
for p in grid:
    m_, s_ = cv_auc("lgbm", feats=FEATS2, params=p)
    tune.append({**p, "cv_auc_mean": m_, "cv_auc_sd": s_})
tune = pd.DataFrame(tune).sort_values("cv_auc_mean", ascending=False)
best_p = {k: (int(v) if k in ("n_estimators", "num_leaves", "min_child_samples", "subsample_freq") else float(v))
          for k, v in tune.iloc[0].drop(["cv_auc_mean", "cv_auc_sd"]).items()}
log(f"tuned LightGBM: {best_p} CV AUC {tune.iloc[0].cv_auc_mean:.4f}")
tune.to_csv(OUT / "lgbm_tuning_cv.csv", index=False)

# ---------------------------------------------------------------- final fits, scored once on test
l1, s1, p_l1, _ = fit_logit(tr, te, NUM1)
g1, p_g1 = fit_lgb(tr, te, NUM1 + CAT, V1_LGB)
l2, s2, p_l2, p_l2_tr = fit_logit(tr, te, NUM2)
g2, p_g2 = fit_lgb(tr, te, FEATS2, best_p)
y = te.y.values
preds = {"v1_logit": p_l1, "v1_lgbm": p_g1, "v2_logit": p_l2, "v2_lgbm": p_g2}
rng = np.random.default_rng(SEED)
B = 1000
idx = rng.integers(0, len(y), (B, len(y)))
boot = {k: [] for k in preds}
for i in idx:
    if y[i].min() == y[i].max():
        continue
    for k, p in preds.items():
        boot[k].append(roc_auc_score(y[i], p[i]))
boot = {k: np.array(v) for k, v in boot.items()}
metrics = {}
for k, p in preds.items():
    metrics[k] = {"auc_test": float(roc_auc_score(y, p)), "auc_ci": [float(np.percentile(boot[k], 2.5)), float(np.percentile(boot[k], 97.5))],
                  "logloss_test": float(log_loss(y, p)), "brier_test": float(brier_score_loss(y, p))}
diffs = {}
for a, b in [("v2_logit", "v1_logit"), ("v2_lgbm", "v1_lgbm"), ("v2_lgbm", "v1_logit"), ("v2_logit", "v1_lgbm")]:
    d = boot[a] - boot[b]
    diffs[f"{a}_minus_{b}"] = {"delta_auc": metrics[a]["auc_test"] - metrics[b]["auc_test"],
                               "ci": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))], "share_draws_gt0": float((d > 0).mean())}
log("test AUCs: " + ", ".join(f"{k} {v['auc_test']:.3f} [{v['auc_ci'][0]:.3f},{v['auc_ci'][1]:.3f}]" for k, v in metrics.items()))
assert abs(metrics["v1_logit"]["auc_test"] - 0.737) < 0.002, "v1 logit reproduction does not match 06_model_h2.py"


def calib(y, p, k=10):
    q = pd.qcut(pd.Series(p).rank(method="first"), k, labels=False)
    return pd.DataFrame({"y": y, "p": p, "dec": q}).groupby("dec").agg(n=("y", "size"), mean_pred=("p", "mean"), obs_rate=("y", "mean")).reset_index()


cal = pd.concat([calib(y, p).assign(model=k) for k, p in preds.items()])
for k in preds:
    c = cal[cal.model == k]
    metrics[k]["calib_max_abs_gap"] = float((c.mean_pred - c.obs_rate).abs().max())
    metrics[k]["calib_ece"] = float(((c.mean_pred - c.obs_rate).abs() * c.n).sum() / c.n.sum())
# feature importance / coefficients
imp = pd.DataFrame({"term": FEATS2, "gain": g2.booster_.feature_importance("gain")})
imp["gain_share"] = imp.gain / imp.gain.sum(); imp = imp.sort_values("gain_share", ascending=False)
coef = pd.DataFrame({"term": l2.params.index, "coef": l2.params.values, "se": l2.bse.values, "p": l2.pvalues.values})
coef = coef[coef.term.isin(NUM2)].assign(abs_coef=lambda d: d.coef.abs()).sort_values("abs_coef", ascending=False)
# by-stratum test AUC (season × day/night of best look) for where the gain comes from
strat = []
te["season_"] = season(te.month)
for (s_, b_), dd in te.assign(i=np.arange(len(te))).groupby(["season_", "best_is_night"]):
    if dd.y.nunique() < 2 or len(dd) < 200:
        continue
    ii = dd.i.values
    strat.append({"season": s_, "best_look_night": int(b_), "n": int(len(dd)), "recall": float(dd.y.mean()),
                  **{f"auc_{k}": float(roc_auc_score(y[ii], p[ii])) for k, p in preds.items()}})
strat = pd.DataFrame(strat)

# ---------------------------------------------------------------- save
l1.save(OUT / "v1_logit_refit.pickle"); l2.save(OUT / "v2_logit.pickle")
g2.booster_.save_model(str(OUT / "v2_lgbm.txt")); g1.booster_.save_model(str(OUT / "v1_lgbm_refit.txt"))
json.dump({"logit_spec": s2, "logit_columns": list(l2.params.index), "lgbm_params": best_p, "lgbm_features": FEATS2,
           "num_features": NUM2, "categorical": CAT}, open(OUT / "v2_spec.json", "w"), indent=1, default=str)

rows = []
for k, v in metrics.items():
    for mk in ["auc_test", "logloss_test", "brier_test", "calib_ece", "calib_max_abs_gap"]:
        rows.append({"table": "test_metrics", "model": k, "key": mk, "value": v[mk]})
    rows += [{"table": "test_metrics", "model": k, "key": "auc_ci_lo", "value": v["auc_ci"][0]},
             {"table": "test_metrics", "model": k, "key": "auc_ci_hi", "value": v["auc_ci"][1]}]
for k, v in diffs.items():
    rows += [{"table": "paired_delta_auc", "model": k, "key": "delta", "value": v["delta_auc"]},
             {"table": "paired_delta_auc", "model": k, "key": "ci_lo", "value": v["ci"][0]},
             {"table": "paired_delta_auc", "model": k, "key": "ci_hi", "value": v["ci"][1]}]
for _, r in ablation.iterrows():
    rows.append({"table": "cv_ablation_train", "model": r.model, "key": r.feature_set, "value": r.cv_auc_mean})
for _, r in cal.iterrows():
    rows += [{"table": "calibration_decile", "model": r.model, "key": f"dec{int(r.dec)}_mean_pred", "value": r.mean_pred},
             {"table": "calibration_decile", "model": r.model, "key": f"dec{int(r.dec)}_obs_rate", "value": r.obs_rate},
             {"table": "calibration_decile", "model": r.model, "key": f"dec{int(r.dec)}_n", "value": r.n}]
for _, r in imp.iterrows():
    rows.append({"table": "lgbm_gain_share", "model": "v2_lgbm", "key": r.term, "value": r.gain_share})
for _, r in coef.iterrows():
    rows.append({"table": "logit_std_coef", "model": "v2_logit", "key": r.term, "value": r.coef})
for _, r in strat.iterrows():
    for k in preds:
        rows.append({"table": "test_auc_by_stratum", "model": k, "key": f"{r.season}_bestnight{r.best_look_night}_n{r.n}", "value": r[f"auc_{k}"]})
res_csv = pd.DataFrame(rows); res_csv.insert(0, "label", "exploratory")
res_csv.to_csv(RES / "model_v2.csv", index=False)

out = {"label": "EXPLORATORY — not in PREREG; confirmatory H2 (0.737) and verdicts.json unchanged",
       "spec": "planning/DETECTION_MODEL.md 'Model v2' note (2026-10-22)",
       "n_train": int(len(tr)), "n_test": int(len(te)), "base_rate_test": float(y.mean()),
       "test_metrics": metrics, "paired_bootstrap_delta_auc": diffs, "bootstrap_draws": int(len(boot["v1_logit"])),
       "cv": {"scheme": "GroupKFold(5), groups = calendar month, train months only", "ablation": ablation.to_dict("records"),
              "lgbm_grid_size": len(grid), "lgbm_best_params": best_p, "lgbm_best_cv_auc": float(tune.iloc[0].cv_auc_mean),
              "lgbm_v1params_v2feats_cv_auc": float(ablation.query("model=='lgbm_v1params' and feature_set=='v2_all'").cv_auc_mean.iloc[0])},
       "top_features_lgbm_gain": imp.head(12)[["term", "gain_share"]].to_dict("records"),
       "top_std_coefs_logit": coef.head(12)[["term", "coef", "se", "p"]].to_dict("records"),
       "test_auc_by_stratum": strat.to_dict("records"),
       "features": {"v1_numeric": NUM1, "cloud": G_CLOUD, "scan": G_SCAN, "burn": G_BURN, "interactions": G_INT,
                    "lgbm_only": LGB_EXTRA, "categorical": CAT},
       "feature_build": finfo,
       "feasibility": {"firemask_cloud": "granule-specific only for sampled granules (2 days/ISO week/satellite) in the 32.5–40E/46.3–50.5N corridor; "
                                         "elsewhere pooled season × day/night × tcc-bin calibration from the same sample",
                       "scan_angle": "cross-track ground-distance fraction from 4-corner CMR footprints (no per-pixel geolocation); validated vs FIRMS track",
                       "burnable": "WorldCover 2021 within 500 m of the event point (task said 'of the cell'; the DETECTION_MODEL note says 500 m)",
                       "interactions": "season × night and cloud × snow"},
       "model_files": {p.name: sha256_file(p) for p in [OUT / "v2_logit.pickle", OUT / "v2_lgbm.txt", OUT / "v2_spec.json"]}}
json.dump(out, open(RES / "model_v2.json", "w"), indent=2, default=str)
write_meta(RES / "model_v2.json", inputs={"events_detect": IN, "firemask_granule_cloud": FM, "footprints": FP},
           counts={"events": len(df), "train": len(tr), "test": len(te)},
           extra={"label": "exploratory", "runtime_s": round(time.time() - t0, 1), "outputs": ["data/derived/results/model_v2.csv", "figures/model_v2_vs_v1.png"]})

# ---------------------------------------------------------------- figure
fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))
cols = {"v1_logit": "#1d3557", "v1_lgbm": "#457b9d", "v2_logit": "#e63946", "v2_lgbm": "#f4a261"}
for k, p in preds.items():
    fpr, tpr, _ = roc_curve(y, p)
    ax[0].plot(fpr, tpr, color=cols[k], ls="-" if "v2" in k else "--",
               label=f"{k} {metrics[k]['auc_test']:.3f} [{metrics[k]['auc_ci'][0]:.3f}–{metrics[k]['auc_ci'][1]:.3f}]")
ax[0].plot([0, 1], [0, 1], "k:", lw=0.8); ax[0].set_xlabel("false positive rate"); ax[0].set_ylabel("true positive rate")
ax[0].set_title("ROC on V-test (same events, v1 vs v2)"); ax[0].legend(fontsize=8, loc="lower right")
mx = 0
for k in preds:
    c = cal[cal.model == k]; ax[1].plot(c.mean_pred, c.obs_rate, "o-" if "v2" in k else "s--", color=cols[k], label=k, ms=4)
    mx = max(mx, c.mean_pred.max(), c.obs_rate.max())
ax[1].plot([0, mx], [0, mx], "k:", lw=0.8); ax[1].set_xlabel("mean predicted P(detect)"); ax[1].set_ylabel("observed recall")
ax[1].set_title("Calibration by decile (V-test)"); ax[1].legend(fontsize=8)
ti = imp.head(12).iloc[::-1]
grp = {**{f: "#1d3557" for f in NUM1 + CAT}, **{f: "#e63946" for f in G_CLOUD + LGB_EXTRA}, **{f: "#2a9d8f" for f in G_SCAN},
       **{f: "#f4a261" for f in G_BURN}, **{f: "#8d99ae" for f in G_INT}}
ax[2].barh(ti.term, ti.gain_share, color=[grp[t] for t in ti.term])
ax[2].set_xlabel("share of LightGBM gain (v2)"); ax[2].set_title("v2 top features (navy v1, red cloud, teal scan, orange land)")
fig.suptitle("Model v2 vs v1 — EXPLORATORY (not preregistered)", fontsize=11)
fig.tight_layout(); fig.savefig(FIG / "model_v2_vs_v1.png", dpi=150); plt.close(fig)
log(f"done {time.time()-t0:.0f}s; diffs: {json.dumps({k: round(v['delta_auc'], 4) for k, v in diffs.items()})}")
