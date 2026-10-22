"""H7 Transfer prediction (PREREG §4 H7, confirmatory; filed before T1/T2 download). Builder C.

Predicted recall for Karabakh (AOI 38.5–41.5N, 44.5–48.5E, 2020-09-27→2020-11-10) and Sudan Darfur/Kordofan
(AOI 8.5–22N, 21.5–33E, 2023-04-15→2025-12-31) from the H2 primary logistic model (fit on Ukraine V-train).
Covariate distribution is built from synthetic events: (ERA5 grid point in AOI, date in window) pairs, each given
the overpass pattern of a randomly drawn Ukraine event window ("template": relative times, day/night, satellite,
restricted to S-NPP for Karabakh 2020 and to all three satellites for Sudan, Ukraine templates of the same calendar
year for Sudan). Template UTC times are shifted by the longitude difference to Ukraine (solar time preserved).
tcc at each synthetic overpass = ERA5 tcc at the nearest grid point and nearest available hour; snow = ERA5-Land
sde that day. Land cover: Ukraine strike-event mix (primary) and a sensitivity (Sudan grassland/bare 50/50,
Karabakh tree_cover/grassland 50/50). event_type = strike; month = calendar month of the synthetic date.
Predicted recall = mean P(detect) over synthetic events; 90% interval = 5th–95th percentile over 1,000 draws of
the coefficient vector from N(β̂, Cov(β̂)). Output: predictions/transfer_v1.json (+ results/h7_*).
"""
from __future__ import annotations
import sys, json, time, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd, xarray as xr
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from _common import INTERIM, DERIVED, ROOT, RAW, MODELS, SEED, write_meta, log, sha256_file
from _detect import load_events, con_utc, OVERPASSES, NIGHT_HOURS_UTC

RES = DERIVED / "results"; FIG = ROOT / "figures"; PRED = ROOT / "predictions"; PRED.mkdir(exist_ok=True)
t0 = time.time(); rng = np.random.default_rng(SEED)
N_SIM = 20000; N_COEF_DRAWS = 1000
UKR_LON = 32.0
CASES = {
    "karabakh_2020": dict(aoi=dict(lat0=38.5, lat1=41.5, lon0=44.5, lon1=48.5), start="2020-09-27", end="2020-11-10",
                          sats=["N"], template_years=[2022, 2023, 2024, 2025], tcc_files=["era5_tcc_karabakh_2020.nc"],
                          sde_files=["era5land_snowdepth_karabakh_2020.nc"], lc_sens={"tree_cover": 0.5, "grassland": 0.5},
                          desc="Nagorno-Karabakh war, mountain, autumn; S-NPP only (NOAA-20 country files not used; T1 defined on S-NPP)"),
    "sudan_2023_2025": dict(aoi=dict(lat0=8.5, lat1=22.0, lon0=21.5, lon1=33.0), start="2023-04-15", end="2025-12-31",
                            sats=["N", "N20", "N21"], template_years=None, tcc_files=[f"era5_tcc_sudan_{y}.nc" for y in (2023, 2024, 2025)],
                            sde_files=[f"era5land_snowdepth_sudan_{y}.nc" for y in (2023, 2024, 2025)], lc_sens={"grassland": 0.5, "bare_sparse": 0.5},
                            desc="Darfur + Kordofan, arid; S-NPP + NOAA-20 + NOAA-21 (same cadence as Ukraine in the same calendar year)"),
}

# ---- model ----
spec_path = MODELS / "h2_logit_primary_all_types_spec.json"; pkl_path = MODELS / "h2_logit_primary_all_types.pickle"
S = json.load(open(spec_path)); spec = S["spec"]; cols = S["columns"]
beta = np.array([S["params"][c] for c in cols]); cov = np.array(S["cov_params"])
NUM, CAT = S["num"], S["cat"]
coef_draws = rng.multivariate_normal(beta, cov, size=N_COEF_DRAWS)


def design(d: pd.DataFrame) -> np.ndarray:
    X = pd.DataFrame(index=d.index); X["const"] = 1.0
    for c in NUM:
        X[c] = (d[c].astype(float) - spec["mean"][c]) / spec["sd"][c]
    for c in CAT:
        s = d[c].astype(str)
        for lv in spec["levels"][c]:
            if lv != spec["ref"][c]:
                X[f"{c}={lv}"] = (s == lv).astype(float)
    return X.reindex(columns=cols, fill_value=0.0).values


# ---- Ukraine templates: per event window, the list of overpasses ----
ev = load_events()
con = con_utc(); con.register("ev", ev[["uid", "h3_r6", "w0", "w1", "year"]])
night = f"(CASE WHEN o.day_night='Night' THEN 1 WHEN o.day_night='Day' THEN 0 ELSE (CASE WHEN hour(o.start_utc) IN ({','.join(map(str, sorted(NIGHT_HOURS_UTC)))}) THEN 1 ELSE 0 END) END)"
tpl = con.sql(f"""SELECT e.uid, e.year, o.satellite, {night} AS is_night,
                         date_diff('minute', e.w0, o.start_utc) / 60.0 AS rel_h
                  FROM ev e JOIN read_parquet('{OVERPASSES}/*/*.parquet', hive_partitioning=1) o
                    ON o.h3_r6 = e.h3_r6 AND o.start_utc >= e.w0 AND o.start_utc <= e.w1""").df()
log(f"templates: {len(tpl):,} overpass rows for {tpl.uid.nunique():,} Ukraine event windows")
strike_lc = ev[ev.event_type == "strike"]["landcover_class"].value_counts(normalize=True)


def templates_for(sats, years):
    t = tpl[tpl.satellite.isin(sats)]
    if years is not None:
        t = t[t.year.isin(years)]
    t = t.sort_values(["uid", "rel_h"])
    t["gap"] = t.groupby("uid")["rel_h"].diff()
    g = {uid: (grp["rel_h"].values, grp["is_night"].values, grp["gap"].values) for uid, grp in t.groupby("uid")}
    return g


def load_grid(files, var):
    parts = [xr.open_dataset(RAW / "era5" / f)[var].load() for f in files]
    return parts[0] if len(parts) == 1 else xr.concat(parts, dim="valid_time").sortby("valid_time")


def simulate(case, cfg, lc_mode):
    aoi = cfg["aoi"]
    tcc = load_grid(cfg["tcc_files"], "tcc"); sde = load_grid(cfg["sde_files"], "sde")
    tcc = tcc.sel(latitude=slice(aoi["lat1"], aoi["lat0"]), longitude=slice(aoi["lon0"], aoi["lon1"]))
    days = pd.date_range(cfg["start"], cfg["end"], freq="D")
    lats = tcc.latitude.values; lons = tcc.longitude.values
    lon_shift_h = (float(lons.mean()) - UKR_LON) / 15.0     # same local solar time → earlier UTC further east
    tcc_hours = pd.to_datetime(tcc.valid_time.values)
    tcc_vals = tcc.values  # (time, lat, lon)
    sde_time = pd.to_datetime(sde.valid_time.values).normalize(); sde_vals = sde.values
    sde_lat = sde.latitude.values; sde_lon = sde.longitude.values
    pt_lat = rng.choice(len(lats), N_SIM); pt_lon = rng.choice(len(lons), N_SIM)
    di = rng.choice(len(days), N_SIM); d = days[di]
    if cfg["template_years"] is None:
        tpl_by_year = {y: templates_for(cfg["sats"], [y]) for y in sorted(set(d.year))}
    else:
        tpl_all = templates_for(cfg["sats"], cfg["template_years"]); tpl_by_year = None
    pools = [tpl_all] if tpl_by_year is None else list(tpl_by_year.values())
    pool_keys = {id(p): np.array(list(p.keys())) for p in pools}
    rows = []
    t_index = pd.Index(tcc_hours)
    for i in range(N_SIM):
        pool = tpl_all if tpl_by_year is None else tpl_by_year[d[i].year]
        keys = pool_keys[id(pool)]
        uid = keys[rng.integers(len(keys))]
        rel_h, isn, gap = pool[uid]
        w0 = d[i] - pd.Timedelta(hours=12)
        times = w0 + pd.to_timedelta(rel_h - lon_shift_h, unit="h")
        ti = t_index.get_indexer(times, method="nearest")
        tc = tcc_vals[ti, pt_lat[i], pt_lon[i]]
        # snow at the nearest ERA5-Land point on the event date
        si = sde_time.get_indexer([d[i].normalize()], method="nearest")[0]
        la = np.abs(sde_lat - lats[pt_lat[i]]).argmin(); lo = np.abs(sde_lon - lons[pt_lon[i]]).argmin()
        s_cm = float(sde_vals[si, la, lo]) * 100.0
        if np.isnan(s_cm):
            s_cm = 0.0
        g = gap[~np.isnan(gap)]
        rows.append(dict(min_tcc=float(np.nanmin(tc)), mean_tcc=float(np.nanmean(tc)), any_snow=float(s_cm >= 1.0),
                         hours_since_prev=float(g.mean()) if len(g) else np.nan, share_night=float(isn.mean()),
                         n_overpasses=len(rel_h), month=int(d[i].month), lat=float(lats[pt_lat[i]]), lon=float(lons[pt_lon[i]])))
    sim = pd.DataFrame(rows)
    sim["hours_since_prev"] = sim["hours_since_prev"].fillna(sim["hours_since_prev"].median())
    sim["event_type"] = "strike"
    if lc_mode == "ukraine_strike_mix":
        sim["landcover_class"] = rng.choice(strike_lc.index.values, N_SIM, p=strike_lc.values)
    else:
        ks = list(cfg["lc_sens"].keys()); sim["landcover_class"] = rng.choice(ks, N_SIM, p=[cfg["lc_sens"][k] for k in ks])
    X = design(sim)
    p_hat = 1 / (1 + np.exp(-(X @ beta)))
    p_draws = 1 / (1 + np.exp(-(X @ coef_draws.T)))      # (N_SIM, draws)
    rec_draws = p_draws.mean(0)
    sim["p_hat"] = p_hat
    by_month = sim.groupby("month").agg(n=("p_hat", "size"), predicted_recall=("p_hat", "mean"), min_tcc=("min_tcc", "mean"), any_snow=("any_snow", "mean")).reset_index()
    return dict(predicted_recall=float(p_hat.mean()), interval_90=[float(np.percentile(rec_draws, 5)), float(np.percentile(rec_draws, 95))],
                covariate_summary=dict(mean_min_tcc=float(sim.min_tcc.mean()), share_min_tcc_lt_0_5=float((sim.min_tcc < 0.5).mean()),
                                       mean_mean_tcc=float(sim.mean_tcc.mean()), share_any_snow=float(sim.any_snow.mean()),
                                       mean_hours_since_prev=float(sim.hours_since_prev.mean()), mean_share_night=float(sim.share_night.mean()),
                                       mean_n_overpasses_48h=float(sim.n_overpasses.mean()), lon_shift_h=lon_shift_h,
                                       landcover_mix={k: float(v) for k, v in sim.landcover_class.value_counts(normalize=True).items()}),
                by_month=by_month.to_dict(orient="records"), n_sim=N_SIM), sim


out_cases, cov_rows = {}, []
for case, cfg in CASES.items():
    res = {}
    for lc_mode in ["ukraine_strike_mix", "local_landcover_sensitivity"]:
        r, sim = simulate(case, cfg, lc_mode); res[lc_mode] = r
        for m in r["by_month"]:
            cov_rows.append(dict(case=case, landcover_mode=lc_mode, **m))
        log(f"{case} [{lc_mode}]: predicted recall {r['predicted_recall']:.4f} 90% {r['interval_90']}  min_tcc {r['covariate_summary']['mean_min_tcc']:.2f} snow {r['covariate_summary']['share_any_snow']:.3f}")
    prim = res["ukraine_strike_mix"]
    out_cases[case] = dict(
        predicted_recall=prim["predicted_recall"], interval_90=prim["interval_90"],
        sensitivity_local_landcover=dict(landcover=cfg["lc_sens"], predicted_recall=res["local_landcover_sensitivity"]["predicted_recall"],
                                         interval_90=res["local_landcover_sensitivity"]["interval_90"]),
        aoi=cfg["aoi"], window=[cfg["start"], cfg["end"]], description=cfg["desc"],
        covariate_summary=prim["covariate_summary"], by_month=prim["by_month"],
        assumptions=[
            f"Overpass cadence = Ukraine event-window templates (satellites {cfg['sats']}" + (f", Ukraine years {cfg['template_years']}" if cfg["template_years"] else ", same calendar year as the synthetic date") + "), UTC times shifted by the AOI–Ukraine longitude difference",
            "Synthetic events uniform over ERA5 0.25° grid points in the AOI and days in the window (not weighted by where fighting occurred)",
            "tcc at overpass = ERA5 tcc at the nearest grid point and nearest available hour (hour set 22–02, 09–13 UTC; ≤1 h off after the longitude shift)",
            "snow = ERA5-Land sde ≥ 1 cm at the nearest 0.1° point on the event date (NaN over water/outside mask → no snow)",
            "event_type = strike; land cover = Ukraine strike-event mix (primary) — see sensitivity for local land cover",
            "Detection definition as in H1: ≥1 fire within 1 km and within [date−12 h, date+36 h]; realised recall for the test must use the same window and radius (PREREG H7 says 5 km / ±2 days for Karabakh settlement captures, which is a looser definition and would be expected to give higher realised recall)",
            "Interval = 90% from 1,000 multivariate-normal draws of the logistic coefficients; does not include template/ERA5 sampling noise or the unmodelled gap between Ukraine and the target theatre",
        ])
    out_cases[case]["prereg_test"] = "realised recall within ±15 pp of predicted_recall (PREREG H7)"

transfer = dict(
    schema="transfer_v1", written_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    model=dict(name="H2 primary logistic (statsmodels), fit on Ukraine V-train, all event types",
               pickle=str(pkl_path.relative_to(ROOT)), pickle_sha256=sha256_file(pkl_path),
               spec=str(spec_path.relative_to(ROOT)), spec_sha256=sha256_file(spec_path),
               auc_test=json.load(open(RES / "h2_auc.json"))["results"]["primary_all_types"]["logit"]["auc_test"]),
    ukraine_reference=dict(observed_recall_test_all_types=json.load(open(RES / "h1_ratio.json"))["primary"]["overall_recall"],
                           note="Ukraine V-test observed recall under the same detection definition, for scale"),
    sudan_2025_era5="present (era5_tcc_sudan_2025.nc, era5land_snowdepth_sudan_2025.nc) — all three years used",
    prereg_predictions="PREREG H7: Sudan within band (predicted high recall); Karabakh within band but lower",
    cases=out_cases, seed=SEED, n_sim_per_case=N_SIM, n_coef_draws=N_COEF_DRAWS,
    inputs={f: sha256_file(RAW / "era5" / f) for c in CASES.values() for f in c["tcc_files"] + c["sde_files"]},
)
json.dump(transfer, open(PRED / "transfer_v1.json", "w"), indent=2)
pd.DataFrame(cov_rows).to_csv(RES / "h7_predicted_by_month.csv", index=False)
json.dump({"cases": {k: {kk: v[kk] for kk in ["predicted_recall", "interval_90", "sensitivity_local_landcover", "covariate_summary"]} for k, v in out_cases.items()},
           "written_utc": transfer["written_utc"]}, open(RES / "h7_predictions.json", "w"), indent=2)

fig, ax = plt.subplots(figsize=(7, 3.8))
names = list(out_cases) + ["ukraine_test_observed"]
vals = [out_cases[c]["predicted_recall"] for c in out_cases] + [transfer["ukraine_reference"]["observed_recall_test_all_types"]]
lo = [out_cases[c]["predicted_recall"] - out_cases[c]["interval_90"][0] for c in out_cases] + [0]
hi = [out_cases[c]["interval_90"][1] - out_cases[c]["predicted_recall"] for c in out_cases] + [0]
ax.bar(names, vals, yerr=[lo, hi], capsize=4, color=["#457b9d", "#e9c46a", "#8d99ae"])
for i, c in enumerate(out_cases):
    s = out_cases[c]["sensitivity_local_landcover"]["predicted_recall"]; ax.plot(i, s, "kx", ms=8, label="local land-cover sensitivity" if i == 0 else None)
ax.set_ylabel("predicted recall (strike events)"); ax.set_title("H7 transfer predictions filed before T1/T2 download"); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(FIG / "h7_transfer_predictions.png", dpi=150); plt.close(fig)
write_meta(PRED / "transfer_v1.json", inputs={"logit_spec": spec_path, "logit_pickle": pkl_path, **{f: RAW / "era5" / f for c in CASES.values() for f in c["tcc_files"] + c["sde_files"]}},
           counts={"n_sim_per_case": N_SIM, "n_coef_draws": N_COEF_DRAWS, "template_rows": len(tpl)}, extra={"runtime_s": round(time.time() - t0, 1)})
log(f"H7 done {time.time()-t0:.0f}s"); print(json.dumps({k: {kk: v[kk] for kk in ['predicted_recall', 'interval_90', 'sensitivity_local_landcover', 'covariate_summary']} for k, v in out_cases.items()}, indent=1))
