"""H3 Paired looks (PREREG §4 H3, confirmatory; DESIGN D11). Builder C.

Unit: an S-NPP detection (fires.parquet satellite N, conf n/h) in an h3_r6 cell of overpasses_r6 (Ukraine + 50 km
Russia buffer) for which overpasses_r6 has a NOAA-20 granule covering the same cell with start_utc 30–70 min after
or before the detection and ERA5 tcc < 0.3 on that NOAA-20 pass (nearest such pass per direction; a detection with
both an earlier and a later qualifying pass contributes one pair per direction). Concordance = ≥1 NOAA-20 detection
within 1,000 m (EPSG:3035) with acq_ts in [pass start − 10 min, pass start + 6 min + 10 min].
Strata: season (summer May–Oct / winter Nov–Apr) × day/night (the S-NPP detection's daynight flag). Wilson 95% CI.
Reverse direction (NOAA-20 detection → S-NPP pass) run the same way.
S-NPP detections are sampled to ≤200,000 with seed 20261014 for speed (stated in meta).
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from _common import INTERIM, DERIVED, ROOT, SEED, write_meta, log
from _detect import con_utc, to_3035, wilson, FIRES, OVERPASSES

RES = DERIVED / "results"; FIG = ROOT / "figures"
t0 = time.time(); rng = np.random.default_rng(SEED)
MAX_N = 200_000
BOX = "lat BETWEEN 43.5 AND 53.5 AND lon BETWEEN 21.5 AND 42.5"
GRANULE_MIN = 6

con = con_utc()
cells = con.sql(f"SELECT DISTINCT h3_r6 FROM read_parquet('{OVERPASSES}/*/*.parquet', hive_partitioning=1)").df()
con.register("cells", cells)
log(f"{len(cells):,} overpass cells")


def load_sat(sat):
    f = con.sql(f"""SELECT f.fire_id, f.acq_ts_utc, f.lat, f.lon, f.h3_r6, f.daynight, f.frp
                    FROM '{FIRES}' f JOIN cells c ON c.h3_r6 = f.h3_r6
                    WHERE f.satellite = '{sat}' AND {BOX}""").df()
    f["acq_ts_utc"] = pd.to_datetime(f["acq_ts_utc"], utc=True)
    return f


def pair_and_score(src: pd.DataFrame, src_sat: str, tgt: pd.DataFrame, tgt_sat: str):
    """src detections → qualifying tgt passes (30–70 min, tcc<0.3) → concordance with tgt detections."""
    n_all = len(src)
    if len(src) > MAX_N:
        src = src.iloc[rng.choice(len(src), MAX_N, replace=False)].sort_values("acq_ts_utc")
    con.register("src", src[["fire_id", "acq_ts_utc", "h3_r6"]])
    q = f"""
    WITH j AS (
      SELECT s.fire_id, o.start_utc, o.tcc, o.day_night, o.granule_ur,
             date_diff('minute', s.acq_ts_utc, o.start_utc) AS dmin
      FROM src s JOIN read_parquet('{OVERPASSES}/*/*.parquet', hive_partitioning=1) o
        ON o.h3_r6 = s.h3_r6 AND o.satellite = '{tgt_sat}'
       AND o.start_utc BETWEEN s.acq_ts_utc - INTERVAL 70 MINUTE AND s.acq_ts_utc + INTERVAL 70 MINUTE
    ), q AS (
      SELECT *, CASE WHEN dmin > 0 THEN 'after' ELSE 'before' END AS direction,
             row_number() OVER (PARTITION BY fire_id, (dmin > 0) ORDER BY abs(dmin)) AS rn
      FROM j WHERE abs(dmin) BETWEEN 30 AND 70
    )
    SELECT fire_id, start_utc, tcc, day_night AS pass_day_night, granule_ur, dmin, direction FROM q WHERE rn = 1"""
    pairs = con.sql(q).df()
    pairs["start_utc"] = pd.to_datetime(pairs["start_utc"], utc=True)
    n_pairs_any_tcc = len(pairs)
    pairs = pairs[pairs["tcc"] < 0.3].copy()
    pairs = pairs.merge(src[["fire_id", "acq_ts_utc", "lat", "lon", "daynight", "frp"]], on="fire_id")
    log(f"{src_sat}->{tgt_sat}: {n_all:,} detections, {len(src):,} used, {n_pairs_any_tcc:,} pairs 30–70 min, {len(pairs):,} with tcc<0.3")
    # concordance
    tx = to_3035(tgt["lat"].values, tgt["lon"].values); tree = cKDTree(tx)
    t_ts = tgt["acq_ts_utc"].values.astype("datetime64[ns]")
    px = to_3035(pairs["lat"].values, pairs["lon"].values)
    hits = tree.query_ball_point(px, r=1000.0)
    w0 = (pairs["start_utc"] - pd.Timedelta(minutes=10)).values.astype("datetime64[ns]")
    w1 = (pairs["start_utc"] + pd.Timedelta(minutes=GRANULE_MIN + 10)).values.astype("datetime64[ns]")
    conc = np.zeros(len(pairs), bool); nmatch = np.zeros(len(pairs), np.int16)
    for i, idx in enumerate(hits):
        if idx:
            ts = t_ts[np.asarray(idx)]
            m = (ts >= w0[i]) & (ts <= w1[i])
            conc[i] = m.any(); nmatch[i] = m.sum()
    pairs["concordant"] = conc; pairs["n_match"] = nmatch
    pairs["season"] = np.where(pairs["acq_ts_utc"].dt.month.between(5, 10), "summer", "winter")
    pairs["daynight"] = pairs["daynight"].map({"D": "day", "N": "night"})
    pairs["year"] = pairs["acq_ts_utc"].dt.year
    pairs["tcc_bin"] = pd.cut(pairs["tcc"], [-0.01, 0.1, 0.2, 0.3], labels=["0-0.1", "0.1-0.2", "0.2-0.3"]).astype(str)
    pairs["frp_bin"] = pd.cut(pairs["frp"], [0, 2, 5, 10, 20, 1e6], labels=["<2", "2-5", "5-10", "10-20", ">=20"]).astype(str)
    return pairs, dict(n_detections=n_all, n_used=len(src), n_pairs_30_70=n_pairs_any_tcc, n_pairs_tcc_lt_0_3=len(pairs))


def table(pairs, by, run):
    g = pairs.groupby(by, dropna=False)["concordant"].agg(n="size", concordant="sum").reset_index()
    p, lo, hi = wilson(g["concordant"], g["n"]); g["share"] = p; g["ci_lo"] = lo; g["ci_hi"] = hi
    g["group_by"] = "x".join(by); g["level"] = g[by].astype(str).agg(" | ".join, axis=1); g = g.drop(columns=by); g["run"] = run
    return g


fN = load_sat("N"); fN20 = load_sat("N20")
log(f"S-NPP {len(fN):,}, NOAA-20 {len(fN20):,} detections in overpass cells")
rows, counts, prim = [], {}, {}
for run, (src, ss, tgt, ts) in {"snpp_to_noaa20": (fN, "N", fN20, "N20"), "noaa20_to_snpp": (fN20, "N20", fN, "N")}.items():
    pairs, cnt = pair_and_score(src, ss, tgt, ts); counts[run] = cnt
    for by in [["season", "daynight"], ["season"], ["daynight"], ["direction"], ["year"], ["tcc_bin"], ["frp_bin"], ["season", "daynight", "direction"]]:
        rows.append(table(pairs, by, run))
    n = len(pairs); k = int(pairs.concordant.sum()); p, lo, hi = wilson(k, n)
    rows.append(pd.DataFrame([{"n": n, "concordant": k, "share": p, "ci_lo": lo, "ci_hi": hi, "group_by": "overall", "level": "all", "run": run}]))
    prim[run] = dict(n=n, concordant=k, share=float(p), ci=[float(lo), float(hi)], **cnt)
tab = pd.concat(rows, ignore_index=True)[["run", "group_by", "level", "n", "concordant", "share", "ci_lo", "ci_hi"]]
tab.to_csv(RES / "h3_concordance.csv", index=False)

s = tab[(tab.run == "snpp_to_noaa20") & (tab.group_by == "seasonxdaynight")]
in_band_strata = {r.level: bool(0.40 <= r.share <= 0.70) for r in s.itertuples()}
verdict = {"overall_share": prim["snpp_to_noaa20"]["share"], "overall_in_40_70": bool(0.40 <= prim["snpp_to_noaa20"]["share"] <= 0.70),
           "overall_ci_within_40_70": bool(prim["snpp_to_noaa20"]["ci"][0] >= 0.40 and prim["snpp_to_noaa20"]["ci"][1] <= 0.70),
           "strata_in_band": in_band_strata, "H3_supported": bool(0.40 <= prim["snpp_to_noaa20"]["share"] <= 0.70),
           "prereg_prediction": "inside 40–70% band", "note": "primary = S-NPP→NOAA-20 pooled; strata reported"}
json.dump({"primary": prim, "verdict": verdict, "definitions": {
    "pair": "S-NPP detection with a NOAA-20 granule covering its h3_r6 cell starting 30–70 min after (or before), nearest per direction, ERA5 tcc<0.3 on that pass",
    "concordant": "≥1 NOAA-20 detection (conf n/h) within 1,000 m with acq_ts in [pass start −10 min, pass start +16 min]",
    "strata": "season of the detection (summer May–Oct) × its own daynight flag", "sampling": f"source detections sampled to ≤{MAX_N:,} with default_rng({SEED}) when more"}},
    open(RES / "h3_summary.json", "w"), indent=2)

fig, ax = plt.subplots(figsize=(7, 4))
for run, c, off in [("snpp_to_noaa20", "#1d3557", -0.15), ("noaa20_to_snpp", "#e63946", 0.15)]:
    t = tab[(tab.run == run) & (tab.group_by == "seasonxdaynight")].sort_values("level")
    x = np.arange(len(t)) + off
    ax.bar(x, t["share"], width=0.3, yerr=[t["share"] - t["ci_lo"], t["ci_hi"] - t["share"]], capsize=3, color=c, label=run.replace("_", " "))
    ax.set_xticks(np.arange(len(t))); ax.set_xticklabels(t["level"])
ax.axhspan(0.4, 0.7, color="grey", alpha=0.15, label="PREREG band 40–70%"); ax.set_ylim(0, 1); ax.set_ylabel("share concordant"); ax.legend(fontsize=8)
ax.set_title("H3 paired-look concordance (tcc<0.3, 30–70 min)")
fig.tight_layout(); fig.savefig(FIG / "h3_concordance.png", dpi=150); plt.close(fig)
write_meta(RES / "h3_concordance.csv", inputs={"fires": FIRES, "overpasses_meta": INTERIM / "overpasses_r6_meta.json"}, counts=counts,
           extra={"primary": prim, "verdict": verdict, "runtime_s": round(time.time() - t0, 1)})
log(f"H3 done {time.time()-t0:.0f}s {json.dumps(prim)} {verdict}")
