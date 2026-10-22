"""H1 Recall (PREREG §4 H1, confirmatory). Builder C.

Detected = ≥1 fire (any satellite, conf n/h) within 1,000 m and acq_ts in
[event date 00:00 UTC − 12 h, event date 24:00 UTC + 12 h]. Covariates from overpasses_r6 for the
event's h3_r6 cell in the same window. Strata per PREREG: best = clear & night & Jun–Sep,
worst = (tcc≥0.5 or snow) & day & Nov–Feb. Primary on split==test (PREREG: "against V-test events");
all-V and train reported alongside. Wilson 95% CIs; ratio best/worst with a 1,000-draw bootstrap over events.

Outputs: data/interim/analysis/events_detect.parquet (event-level, gitignored; reused by 06/08),
data/derived/results/h1_*.csv/json, figures/h1_*.png.
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from _common import INTERIM, DERIVED, ROOT, SEED, write_meta, log, sha256_file
from _detect import (load_events, load_fires_ukr, detect, window_covariates, h1_strata, wilson,
                     recall_table, RESTRICTED_TYPES, EVENTS, FIRES, OVERPASSES)

RES = DERIVED / "results"; FIG = ROOT / "figures"
RES.mkdir(parents=True, exist_ok=True); FIG.mkdir(exist_ok=True)
t0 = time.time()

ev = load_events()
log(f"events {len(ev):,}")
fires = load_fires_ukr()
log(f"fires in Ukraine box {len(fires):,}")
det = detect(ev, fires)
cov = window_covariates(ev)
df = ev.drop(columns=["dup_ids"]).merge(det, on="uid").merge(cov, on="uid")
df["stratum"] = h1_strata(df, "clear_night")
df["stratum_alt"] = h1_strata(df, "best_overpass")
df["season"] = np.where(df["month"].between(5, 10), "summer", "winter")
df["daynight_h1"] = np.where(df["clear_night"] == 1, "night", "day")
df["restricted"] = df["event_type"].isin(RESTRICTED_TYPES)
out_ev = INTERIM / "events_detect.parquet"
df.to_parquet(out_ev, index=False)
log(f"no overpass rows for {int(df['no_overpass_rows'].sum())} events; detected overall {df['detected'].mean():.3f}")

# ---------- recall tables ----------
rows = []
def add(sub, label, event_set):
    for by, name in [(["stratum"], "stratum"), (["stratum_alt"], "stratum_alt"), (["event_type"], "event_type"),
                     (["season"], "season"), (["daynight_h1"], "daynight"), (["month"], "month"),
                     (["landcover_class"], "landcover"), (["year"], "year"), (["source"], "source"),
                     (["season", "daynight_h1"], "season_x_daynight")]:
        t = recall_table(sub, by)
        t["group_by"] = name
        t["level"] = t[by].astype(str).agg(" | ".join, axis=1) if len(by) > 1 else t[by[0]].astype(str)
        t = t.drop(columns=by)
        t["split"] = label; t["event_set"] = event_set
        rows.append(t)
    n = len(sub); k = int(sub["detected"].sum()); p, lo, hi = wilson(k, n)
    rows.append(pd.DataFrame([{"n": n, "detected": k, "recall": p, "ci_lo": lo, "ci_hi": hi,
                               "group_by": "overall", "level": "all", "split": label, "event_set": event_set}]))

for label, sub in [("test", df[df.split == "test"]), ("all", df), ("train", df[df.split == "train"])]:
    add(sub, label, "all_types")
    add(sub[sub.restricted], label, "restricted_strike_shelling_infra_vehicle")
tab = pd.concat(rows, ignore_index=True)[["event_set", "split", "group_by", "level", "n", "detected", "recall", "ci_lo", "ci_hi"]]
tab.to_csv(RES / "h1_recall.csv", index=False)

# ---------- ratio with bootstrap ----------
rng = np.random.default_rng(SEED)
def ratio_boot(sub, col="stratum", draws=1000):
    b = sub[sub[col] == "best"]["detected"].values.astype(float)
    w = sub[sub[col] == "worst"]["detected"].values.astype(float)
    if len(b) == 0 or len(w) == 0:
        return dict(n_best=len(b), n_worst=len(w), ratio=None)
    r = b.mean() / w.mean() if w.mean() > 0 else np.inf
    rs = []
    for _ in range(draws):
        bb = rng.choice(b, len(b)); ww = rng.choice(w, len(w))
        rs.append(bb.mean() / ww.mean() if ww.mean() > 0 else np.inf)
    rs = np.array(rs)
    return dict(n_best=int(len(b)), n_worst=int(len(w)), recall_best=float(b.mean()), recall_worst=float(w.mean()),
                ratio=float(r), ratio_ci_lo=float(np.quantile(rs, 0.025, method="nearest")), ratio_ci_hi=(None if np.isinf(np.quantile(rs, 0.975, method="nearest")) else float(np.quantile(rs, 0.975, method="nearest"))), share_draws_ratio_inf=float(np.mean(np.isinf(rs))),
                share_draws_ratio_ge_3=float(np.mean(rs >= 3)), draws=draws)

res = {}
for label, sub in [("test", df[df.split == "test"]), ("all", df), ("train", df[df.split == "train"])]:
    for es, s2 in [("all_types", sub), ("restricted", sub[sub.restricted])]:
        for col in ["stratum", "stratum_alt"]:
            n = len(s2); k = int(s2["detected"].sum()); p, lo, hi = wilson(k, n)
            res[f"{label}|{es}|{col}"] = dict(overall_n=n, overall_recall=float(p), overall_ci=[float(lo), float(hi)],
                                               **ratio_boot(s2, col))
prim = res["test|all_types|stratum"]
verdict = {
    "overall_recall_below_50pct": bool(prim["overall_ci"][1] < 0.5),
    "ratio_at_least_3": bool(prim["ratio"] is not None and prim["ratio"] >= 3),
    "ratio_ci_excludes_3_from_below": bool(prim.get("ratio_ci_lo", 0) >= 3),
    "H1_supported": bool(prim["overall_ci"][1] < 0.5 and prim["ratio"] is not None and prim["ratio"] >= 3),
    "note": "Primary = V-test, all event types, day/night = clear-night-overpass definition. Supported requires both criteria.",
}
json.dump({"primary": prim, "all_runs": res, "verdict": verdict,
           "definitions": {
               "detected": "≥1 fire (N/N20/N21, conf n/h, any type) within 1,000 m (EPSG:3035) and acq_ts_utc in [date 00:00Z−12h, date 24:00Z+12h]",
               "covariates": "overpasses_r6 rows for the event h3_r6 in the same window; min/mean tcc, any snow (sde≥1 cm), n overpasses, n clear (tcc<0.5 & sde<1), share night ('Both' granules by UTC hour 20–04), mean hours_since_prev (sentinels ≤0/>1000 dropped)",
               "stratum": "best = min_tcc<0.5 & no snow & ≥1 clear night overpass & Jun–Sep; worst = (min_tcc≥0.5 or snow) & no clear night overpass & Nov–Feb",
               "stratum_alt": "same but night/day = flag of the lowest-tcc overpass in the window (sensitivity)",
               "n_events_without_overpass_rows": int(df["no_overpass_rows"].sum()),
           }}, open(RES / "h1_ratio.json", "w"), indent=2)

# ---------- figures ----------
t = tab[(tab.event_set == "all_types") & (tab.split == "test")]
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
s = t[t.group_by == "stratum"].set_index("level").reindex(["best", "other", "worst"]).dropna(subset=["n"])
ax[0].bar(s.index, s["recall"], yerr=[s["recall"] - s["ci_lo"], s["ci_hi"] - s["recall"]], capsize=4, color=["#2a9d8f", "#8d99ae", "#e76f51"])
ax[0].set_ylim(0, 0.2); ax[0].set_ylabel("recall (V-test)"); ax[0].set_title("H1 recall by condition stratum")
for i, (k, r) in enumerate(s.iterrows()):
    ax[0].text(i, r["ci_hi"] + 0.02, f"n={int(r['n'])}", ha="center", fontsize=8)
m = t[t.group_by == "month"].copy(); m["level"] = m["level"].astype(int); m = m.sort_values("level")
ax[1].errorbar(m["level"], m["recall"], yerr=[m["recall"] - m["ci_lo"], m["ci_hi"] - m["recall"]], fmt="o-", capsize=3)
ax[1].set_xticks(range(1, 13)); ax[1].set_ylim(0, 0.25); ax[1].set_xlabel("month"); ax[1].set_title("H1 recall by calendar month (V-test)")
fig.tight_layout(); fig.savefig(FIG / "h1_recall_strata.png", dpi=150); plt.close(fig)

t2 = tab[(tab.event_set == "all_types") & (tab.split == "test") & (tab.group_by == "event_type")].sort_values("recall")
fig, ax = plt.subplots(figsize=(6, 3.5))
ax.barh(t2["level"], t2["recall"], xerr=[t2["recall"] - t2["ci_lo"], t2["ci_hi"] - t2["recall"]], capsize=3, color="#457b9d")
ax.set_xlim(0, 0.12); ax.set_xlabel("recall (V-test)"); ax.set_title("H1 recall by event type")
fig.tight_layout(); fig.savefig(FIG / "h1_recall_event_type.png", dpi=150); plt.close(fig)

write_meta(RES / "h1_recall.csv", inputs={"events_v": EVENTS, "fires": FIRES, "overpasses_meta": INTERIM / "overpasses_r6_meta.json"},
           counts={"events": len(df), "test": int((df.split == "test").sum()), "detected_all": int(df.detected.sum()),
                   "fires_in_box": len(fires), "no_overpass_rows": int(df.no_overpass_rows.sum())},
           extra={"primary": prim, "verdict": verdict, "runtime_s": round(time.time() - t0, 1),
                  "event_level_table": str(out_ev.relative_to(ROOT))})
log(f"H1 done in {time.time()-t0:.0f}s. primary: {json.dumps(prim)}; verdict {verdict}")
