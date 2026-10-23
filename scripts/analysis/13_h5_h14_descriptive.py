"""H5 (location / calibration) and H14 (seasonal detection floor). PREREG §4; planning/PANEL.md Builder E. Confirmatory.

H5: C1 front cells (front_15), monthly ratio of S-NPP fire density to the same cells' 2012–2021 same-ISO-week S-NPP
baseline: ratio_m = Σ fires_snpp / Σ base_fires_mean over front cell-weeks whose ISO-week Monday falls in calendar month
m (like-for-like: both S-NPP). Supported if ratio ≥ 3 in ≥ 9 of 12 months (point estimate; the cell block-bootstrap
95% CI, 2,000 draws, is reported and the count of months whose CI lower bound ≥ 3 is given as the strict reading).
H14: baseline B (fires_baseline.parquet, S-NPP 2012–2021, conf n/h): 5th-percentile FRP by month × day/night with
bootstrap 95% CIs (1,000 draws). Supported if the summer-day (May–Oct, D) floor ≥ 1.5 × the winter-night (Nov–Apr, N)
floor. Re-check on V events: FRP of the matched fire (max FRP within 1 km/window) for detected events vs the FRP of
the nearest fire within 1–5 km in the window for missed events ("missed-nearby"), by season × day/night.
"""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from _panel import *  # noqa
from _detect import to_3035
from scipy.spatial import cKDTree

t0 = time.time(); rng = np.random.default_rng(SEED)
DRAWS_H5, DRAWS_H14 = 2000, 1000

# ---------------- H5 ----------------
p = load_panel(5, ["h3_r5", "week_start", "front_15", "fires_snpp", "fires", "base_fires_mean", "rear_strip", "in_ukraine"])
d = c1_front(p, 15); d["month"] = d.week_start.dt.month
log(f"H5 sample {len(d)} cell-weeks, {d.cell.nunique()} cells")


def ratios(df):
    g = df.groupby("month").agg(f=("fires_snpp", "sum"), b=("base_fires_mean", "sum"))
    return (g.f / g.b).reindex(range(1, 13)).values


pt = ratios(d)
boot = block_boot_cells(d, ratios, DRAWS_H5)
lo, hi = np.nanpercentile(boot, 2.5, axis=0), np.nanpercentile(boot, 97.5, axis=0)
h5 = pd.DataFrame({"month": range(1, 13), "ratio": pt, "ci_lo": lo, "ci_hi": hi,
                   "cell_weeks": d.groupby("month").size().reindex(range(1, 13)).values,
                   "fires_snpp": d.groupby("month").fires_snpp.sum().reindex(range(1, 13)).values,
                   "baseline_expected": d.groupby("month").base_fires_mean.sum().reindex(range(1, 13)).values})
h5["ge3_point"] = h5.ratio >= 3; h5["ge3_ci_lo"] = h5.ci_lo >= 3
n_pt, n_ci = int(h5.ge3_point.sum()), int(h5.ge3_ci_lo.sum())
h5.to_csv(RES / "h5_monthly_ratio.csv", index=False)
h5_summary = {"months_ratio_ge3_point": n_pt, "months_ci_lo_ge3": n_ci, "criterion": "ratio >= 3 in >= 9 of 12 months",
              "supported": n_pt >= 9, "supported_strict_ci": n_ci >= 9, "overall_ratio": float(d.fires_snpp.sum() / d.base_fires_mean.sum()),
              "n_cell_weeks": int(len(d)), "n_cells": int(d.cell.nunique()), "draws": DRAWS_H5}
json.dump(h5_summary, open(RES / "h5_summary.json", "w"), indent=2)
write_meta(RES / "h5_monthly_ratio.csv", inputs={"panel": PANEL5}, counts={"cell_weeks": len(d), "cells": int(d.cell.nunique())},
           extra={"definition": "ratio_m = Σ fires_snpp / Σ base_fires_mean over C1 front_15 cell-weeks with ISO-week Monday in month m; "
                                "cell block bootstrap 2,000 draws (seed 20261014), percentile 95% CI. Verdict on the point estimate (PREREG wording); "
                                "the CI-lower-bound count is the strict reading.", "summary": h5_summary,
                  "licence": "Contains VIINA-derived front flags (ODbL); fires NASA FIRMS VIIRS 375 m"})
save_verdict("H5", {"criterion": "front-cell S-NPP fire density >= 3x same-cell 2012–2021 same-ISO-week baseline in >= 9 of 12 calendar months of C1",
                    "result": f"{n_pt}/12 months with point ratio >= 3 ({n_ci}/12 with 95% CI lower bound >= 3); overall ratio {h5_summary['overall_ratio']:.2f}",
                    "verdict": "supported" if n_pt >= 9 else "not supported",
                    "jackson_prediction": "supported", "claude_prediction": "supported (PREREG: 'supported; already published in descriptive form elsewhere')",
                    **who_was_right("supported" if n_pt >= 9 else "not supported", "supported", "supported"),
                    "label": "confirmatory", "source": "h5_monthly_ratio.csv"})
log(f"H5: {n_pt}/12 months ratio>=3 (CI-lo {n_ci}/12); overall {h5_summary['overall_ratio']:.2f}")

fig, ax = plt.subplots(figsize=(7, 3.6))
ax.errorbar(h5.month, h5.ratio, yerr=[h5.ratio - h5.ci_lo, h5.ci_hi - h5.ratio], fmt="o", color="k", capsize=3)
ax.axhline(3, color="C3", ls="--", lw=1, label="3× criterion"); ax.axhline(1, color="grey", ls=":", lw=0.8)
ax.set_yscale("log"); ax.set_xticks(range(1, 13)); ax.set_xlabel("calendar month (ISO-week Monday)")
ax.set_ylabel("front-cell S-NPP fires / 2012–21 baseline"); ax.set_title("H5: front-cell fire density vs pre-war baseline, C1"); ax.legend()
fig.tight_layout(); fig.savefig(FIG / "h5_monthly_ratio.png", dpi=150); plt.close(fig)
caption("h5_monthly_ratio.png", "confirmatory", "H5 (PREREG §4): ratio of S-NPP fire counts in C1 front cells (centroid ≤ 15 km from the "
        "weekly VIINA RU|UA line) to the same cells' mean same-ISO-week S-NPP count in 2012–2021, by calendar month, with cell "
        "block-bootstrap 95% CIs (2,000 draws). Dashed line = the pre-stated 3× criterion (≥ 9 of 12 months). Source: "
        "data/derived/results/h5_monthly_ratio.csv.")

# ---------------- H14 on baseline B ----------------
fb = pd.read_parquet(INTERIM / "fires_baseline.parquet", columns=["acq_ts_utc", "frp", "daynight"])
fb["month"] = pd.to_datetime(fb.acq_ts_utc).dt.month; fb["dn"] = fb.daynight.astype(str)
fb = fb[fb.frp.notna() & (fb.frp > 0)]


def p5_boot(x, draws):
    x = np.asarray(x, float); n = len(x)
    if n < 20:
        return np.nan, np.nan, np.nan
    pt = np.percentile(x, 5)
    bs = np.percentile(x[rng.integers(0, n, size=(draws, n))], 5, axis=1)
    return float(pt), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


rows = []
for (m, dn), g in fb.groupby(["month", "dn"]):
    pt, lo, hi = p5_boot(g.frp.values, DRAWS_H14)
    rows.append({"set": "B", "month": m, "daynight": dn, "n": len(g), "p5_frp": pt, "ci_lo": lo, "ci_hi": hi, "median_frp": float(g.frp.median())})
h14 = pd.DataFrame(rows)
sd = fb[(fb.month.between(5, 10)) & (fb.dn == "D")].frp.values; wn = fb[(~fb.month.between(5, 10)) & (fb.dn == "N")].frp.values
sd_p, sd_lo, sd_hi = p5_boot(sd, DRAWS_H14); wn_p, wn_lo, wn_hi = p5_boot(wn, DRAWS_H14)
# ratio bootstrap (independent resamples of the two strata)
bs_sd = np.percentile(sd[rng.integers(0, len(sd), size=(DRAWS_H14, len(sd)))], 5, axis=1)
bs_wn = np.percentile(wn[rng.integers(0, len(wn), size=(DRAWS_H14, len(wn)))], 5, axis=1)
ratio = sd_p / wn_p; r_lo, r_hi = np.percentile(bs_sd / bs_wn, [2.5, 97.5])
h14_sum = {"summer_day_p5_MW": sd_p, "summer_day_ci": [sd_lo, sd_hi], "n_summer_day": int(len(sd)),
           "winter_night_p5_MW": wn_p, "winter_night_ci": [wn_lo, wn_hi], "n_winter_night": int(len(wn)),
           "ratio": float(ratio), "ratio_ci95": [float(r_lo), float(r_hi)], "criterion": "summer-day p5 FRP >= 1.5 x winter-night p5 FRP (baseline B)",
           "supported": bool(ratio >= 1.5), "also_summer_night_p5": p5_boot(fb[(fb.month.between(5, 10)) & (fb.dn == "N")].frp.values, DRAWS_H14)[0],
           "also_winter_day_p5": p5_boot(fb[(~fb.month.between(5, 10)) & (fb.dn == "D")].frp.values, DRAWS_H14)[0]}
log(f"H14 B: summer-day p5 {sd_p:.2f} MW, winter-night p5 {wn_p:.2f} MW, ratio {ratio:.2f} [{r_lo:.2f}, {r_hi:.2f}]")

# ---------------- H14 re-check on V events ----------------
ev = pd.read_parquet(INTERIM / "events_detect.parquet", columns=["uid", "lat", "lon", "w0", "w1", "detected", "max_frp", "any_night_fire", "season", "month", "split"])
fires = pd.read_parquet(INTERIM / "fires.parquet", columns=["lat", "lon", "acq_ts_utc", "frp", "daynight"])
fires = fires[fires.lat.between(44, 53) & fires.lon.between(22, 41)].reset_index(drop=True)
fx = to_3035(fires.lat.values, fires.lon.values); tree = cKDTree(fx)
miss = ev[~ev.detected].reset_index(drop=True)
ex = to_3035(miss.lat.values, miss.lon.values)
f_ts = fires.acq_ts_utc.values.astype("datetime64[ns]"); f_frp = fires.frp.values; f_dn = fires.daynight.astype(str).values
w0 = miss.w0.values.astype("datetime64[ns]"); w1 = miss.w1.values.astype("datetime64[ns]")
hits = tree.query_ball_point(ex, r=5000.0)
near_frp = np.full(len(miss), np.nan); near_dn = np.array([""] * len(miss), dtype=object); near_d = np.full(len(miss), np.nan)
for i, idx in enumerate(hits):
    if not idx:
        continue
    idx = np.asarray(idx); ts = f_ts[idx]; m = (ts >= w0[i]) & (ts <= w1[i])
    if not m.any():
        continue
    idx = idx[m]; dist = np.sqrt(((fx[idx] - ex[i]) ** 2).sum(1)); j = int(np.argmin(dist))
    near_frp[i] = f_frp[idx[j]]; near_dn[i] = f_dn[idx[j]]; near_d[i] = dist[j]
miss["near_frp"] = near_frp; miss["near_dn"] = near_dn; miss["near_dist_m"] = near_d
mn = miss[miss.near_frp.notna()]
det = ev[ev.detected].copy(); det["dn"] = np.where(det.any_night_fire, "N", "D")
vrows = []
for (s, dn), g in det.groupby(["season", "dn"]):
    pt, lo, hi = p5_boot(g.max_frp.values, DRAWS_H14)
    vrows.append({"set": "V_detected_matched_fire", "season": s, "daynight": dn, "n": len(g), "p5_frp": pt, "ci_lo": lo, "ci_hi": hi, "median_frp": float(g.max_frp.median())})
for (s, dn), g in mn.groupby(["season", "near_dn"]):
    pt, lo, hi = p5_boot(g.near_frp.values, DRAWS_H14)
    vrows.append({"set": "V_missed_nearest_fire_1-5km", "season": s, "daynight": dn, "n": len(g), "p5_frp": pt, "ci_lo": lo, "ci_hi": hi, "median_frp": float(g.near_frp.median())})
h14v = pd.DataFrame(vrows)
h14_all = pd.concat([h14, h14v], ignore_index=True)
h14_all.to_csv(RES / "h14_frp_floor.csv", index=False)


def vget(setname, s, dn):
    r = h14v[(h14v.set == setname) & (h14v.season == s) & (h14v.daynight == dn)]
    return float(r.p5_frp.iloc[0]) if len(r) else float("nan")


h14_sum["v_recheck"] = {"detected_summer_day_p5": vget("V_detected_matched_fire", "summer", "D"), "detected_winter_night_p5": vget("V_detected_matched_fire", "winter", "N"),
                        "detected_ratio": vget("V_detected_matched_fire", "summer", "D") / vget("V_detected_matched_fire", "winter", "N"),
                        "missed_nearby_summer_day_p5": vget("V_missed_nearest_fire_1-5km", "summer", "D"), "missed_nearby_winter_night_p5": vget("V_missed_nearest_fire_1-5km", "winter", "N"),
                        "n_missed_with_fire_1_5km": int(len(mn)), "n_missed": int(len(miss)), "n_detected": int(len(det)),
                        "note": "V events (train+test pooled; descriptive re-check). Detected: max FRP among fires within 1 km/window. Missed-nearby: FRP of the nearest fire 1–5 km away inside the window; day/night = that fire's flag."}
json.dump(h14_sum, open(RES / "h14_summary.json", "w"), indent=2, default=float)
write_meta(RES / "h14_frp_floor.csv", inputs={"fires_baseline": INTERIM / "fires_baseline.parquet", "events_detect": INTERIM / "events_detect.parquet", "fires": INTERIM / "fires.parquet"},
           counts={"baseline_fires": int(len(fb)), "v_detected": int(len(det)), "v_missed": int(len(miss)), "v_missed_with_nearby_fire": int(len(mn))},
           extra={"definition": "p5 of FRP (MW) by month × day/night on baseline B (S-NPP 2012–2021, conf n/h, FRP > 0); bootstrap 1,000 draws. Summer = May–Oct, winter = Nov–Apr. "
                                "Ratio CI from independent stratum resamples.", "summary": h14_sum})
v = "supported" if ratio >= 1.5 else "not supported"
save_verdict("H14", {"criterion": "baseline B: 5th-percentile FRP, summer daytime >= 1.5 x winter night-time",
                     "result": f"summer-day p5 {sd_p:.2f} MW vs winter-night p5 {wn_p:.2f} MW; ratio {ratio:.2f} (95% CI {r_lo:.2f}–{r_hi:.2f}); V re-check detected-event ratio {h14_sum['v_recheck']['detected_ratio']:.2f}",
                     "verdict": v, "jackson_prediction": "supported", "claude_prediction": "supported", **who_was_right(v, "supported", "supported"),
                     "label": "confirmatory", "source": "h14_frp_floor.csv"})

fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
for dn, c in [("D", "C1"), ("N", "C0")]:
    g = h14[h14.daynight == dn]
    ax[0].errorbar(g.month, g.p5_frp, yerr=[g.p5_frp - g.ci_lo, g.ci_hi - g.p5_frp], fmt="o-", color=c, capsize=2, label={"D": "day", "N": "night"}[dn])
ax[0].set_xticks(range(1, 13)); ax[0].set_xlabel("month"); ax[0].set_ylabel("5th-percentile FRP (MW)"); ax[0].set_title("Baseline B 2012–2021 (S-NPP)"); ax[0].legend()
for setname, mk in [("V_detected_matched_fire", "o"), ("V_missed_nearest_fire_1-5km", "x")]:
    g = h14v[h14v.set == setname]
    labs = [f"{s}-{dn}" for s, dn in zip(g.season, g.daynight)]
    ax[1].errorbar(labs, g.p5_frp, yerr=[g.p5_frp - g.ci_lo, g.ci_hi - g.p5_frp], fmt=mk, capsize=2, label=setname.replace("_", " "), ls="none")
ax[1].set_ylabel("5th-percentile FRP (MW)"); ax[1].set_title("V events re-check"); ax[1].legend(fontsize=7); ax[1].tick_params(axis="x", rotation=30)
fig.suptitle(f"H14 seasonal detection floor: summer-day/winter-night p5 ratio {ratio:.2f} (criterion ≥ 1.5)", fontsize=10)
fig.tight_layout(); fig.savefig(FIG / "h14_frp_floor.png", dpi=150); plt.close(fig)
caption("h14_frp_floor.png", "confirmatory", "H14 (PREREG §4): left, 5th-percentile FRP of VIIRS S-NPP detections in Ukraine 2012–2021 (baseline B, conf n/h) "
        "by month × day/night with bootstrap 95% CIs (1,000 draws); the pre-stated test is summer-day (May–Oct) ≥ 1.5 × winter-night (Nov–Apr). "
        "Right, re-check on V events: p5 FRP of the matched fire for detected events (circles) and of the nearest fire 1–5 km away inside the window "
        "for missed events (crosses), by season × day/night. Source: data/derived/results/h14_frp_floor.csv.")
log(f"13 done in {time.time()-t0:.0f}s")
print(json.dumps({"H5": h5_summary, "H14": {k: v for k, v in h14_sum.items() if k != 'v_recheck'}, "H14_v": h14_sum["v_recheck"]}, indent=1, default=float))
