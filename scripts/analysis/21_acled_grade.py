"""ACLED as an independent grader of the FIRMS fire record (EXPLORATORY; PREREG did not name ACLED).

Question: does a third, independent event record (ACLED) show the same recall-by-observability gradient
("blindness map") as the confirmatory V set (GeoConfirmed + Bellingcat, H1)?

Rule (identical to H1, PREREG §3 as operationalised in _detect.py): an event is detected if >=1 fire
(N/N20/N21, conf n/h, any type) lies within 1,000 m (EPSG:3035) with acq_ts_utc in
[event date 00:00Z - 12 h, event date 24:00Z + 12 h]. Chance rate: the same place and window shifted
-7 d and +7 d (as the Telegram match). A 3 km radius is reported as a sensitivity because ACLED
geo_precision 1 is a named-town coordinate, not the impact point.

ACLED licence rules (enforced here): only event_date, event_type, sub_event_type, latitude, longitude,
geo_precision, time_precision, population_best, country are read; no notes/source/actor columns; only
aggregates are printed or written; all outputs go to data/interim/acled/ (gitignored) and
figures/private_acled/ (gitignored). ACLED is not used to train, tune or score any model.

Outputs: data/interim/acled/acled_recall.csv (+_meta.json), acled_vs_v_opportunity.csv,
acled_cellweek.json, acled_summary.json, figures/private_acled/acled_grade.png.
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd, duckdb
from scipy.spatial import cKDTree
from scipy.stats import spearmanr, pearsonr
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from _common import INTERIM, ROOT, RAW, SEED, write_meta, log, h3_cells
from _detect import (load_events, load_fires_ukr, to_3035, window_covariates, h1_strata, wilson,
                     WINDOW_BEFORE_H, WINDOW_AFTER_H, RADIUS_M, OPP_DAY, FIRES)

t0 = time.time()
ACLED = RAW / "acled" / "acled_ukraine_russia_popexp_2022-02-24_2026-10-26.csv"
OUT = ROOT / "data" / "interim" / "acled"; FIG = ROOT / "figures" / "private_acled"
OUT.mkdir(parents=True, exist_ok=True); FIG.mkdir(parents=True, exist_ok=True)
PANEL = INTERIM / "panel_r5_week.parquet"
H1 = ROOT / "data" / "derived" / "results" / "h1_recall.csv"
H5 = ROOT / "data" / "derived" / "results" / "h5_monthly_ratio.csv"
SUBTYPES = {"Explosions/Remote violence": ["Shelling/artillery/missile attack", "Air/drone strike"],
            "Battles": ["Armed clash", "Government regains territory", "Non-state actor overtakes territory"]}
STUDY_END = pd.Timestamp("2025-12-31")
PLACEBO_D = 7
CHUNK = 40_000

# ---------------------------------------------------------------- ACLED (allowed columns only)
sub_list = ",".join(f"'{s}'" for v in SUBTYPES.values() for s in v)
con = duckdb.connect()
a = con.sql(f"""SELECT event_date, event_type, sub_event_type, latitude AS lat, longitude AS lon,
                       geo_precision, time_precision, population_best
                FROM read_csv_auto('{ACLED}', sample_size=-1)
                WHERE country='Ukraine' AND time_precision=1 AND geo_precision IN (1,2)
                  AND sub_event_type IN ({sub_list})""").df()
a["date"] = pd.to_datetime(a["event_date"]); a = a.drop(columns=["event_date"])
n_read = len(a)

# ---------------------------------------------------------------- fires: 2022–2025 parquet + 2026 API (SP>NRT)
fires = load_fires_ukr()[["acq_ts_utc", "lat", "lon"]]
import importlib.util
spec = importlib.util.spec_from_file_location("f02", Path(__file__).with_name("02_fires.py"))
f02 = importlib.util.module_from_spec(spec); spec.loader.exec_module(f02)
p26 = [(1, p) for p in sorted((RAW / "firms_api" / "ukraine").glob("VIIRS_*_SP/2026/*.csv"))] + \
      [(2, p) for p in sorted((RAW / "firms_api" / "ukraine").glob("VIIRS_*_NRT/2026/*.csv"))]
f26 = pd.concat([f02.read_one(p, pr) for pr, p in p26], ignore_index=True)
f26 = f26[f26.acq_ts_utc >= pd.Timestamp("2026-01-01", tz="UTC")]
f26 = f26.assign(_la=f26.latitude.round(5), _lo=f26.longitude.round(5)).sort_values(["_prio", "source_file"], kind="stable")
f26 = f26.drop_duplicates(["satellite", "acq_ts_utc", "_la", "_lo"])
f26 = f26[f26.latitude.between(44, 53) & f26.longitude.between(22, 41)]
f26 = f26.rename(columns={"latitude": "lat", "longitude": "lon"})[["acq_ts_utc", "lat", "lon"]]
fire_max = f26.acq_ts_utc.max()
fires = pd.concat([fires, f26], ignore_index=True)
log(f"fires {len(fires):,} (2026: {len(f26):,}, last {fire_max})")
FX = to_3035(fires.lat.values, fires.lon.values).astype(np.float64)
TREE = cKDTree(FX)
FTS = fires.acq_ts_utc.values.astype("datetime64[ns]").astype(np.int64)
del fires, f26

H = np.int64(3600 * 10**9)


def detect_rule(lat, lon, date, radius=RADIUS_M, shift_days=0) -> np.ndarray:
    """Same rule as _detect.detect (1 km, [date-12h, date+36h]) with a prebuilt tree; chunked.
    Verified below to reproduce events_detect.detected for the V set exactly."""
    d = pd.to_datetime(date).values.astype("datetime64[ns]").astype(np.int64) + np.int64(shift_days) * 24 * H
    w0 = d - WINDOW_BEFORE_H * H; w1 = d + (24 + WINDOW_AFTER_H) * H
    out = np.zeros(len(d), bool)
    for s in range(0, len(d), CHUNK):
        ex = to_3035(lat[s:s + CHUNK], lon[s:s + CHUNK])
        for j, idx in enumerate(TREE.query_ball_point(ex, r=radius)):
            if idx:
                ts = FTS[idx]; i = s + j
                out[i] = bool(((ts >= w0[i]) & (ts <= w1[i])).any())
    return out


# ---------------------------------------------------------------- V set (H1 events) for the comparison
v = pd.read_parquet(INTERIM / "events_detect.parquet", columns=["uid", "date", "lat", "lon", "h3_r6", "month", "detected",
                                                                 "stratum", "split", "season"])
v_chk = detect_rule(v.lat.values, v.lon.values, v.date)
n_mismatch = int((v_chk != v.detected.values).sum())
log(f"rule check vs H1 events_detect: mismatches {n_mismatch} of {len(v):,}")
v["placebo_m7"] = detect_rule(v.lat.values, v.lon.values, v.date, shift_days=-PLACEBO_D)
v["placebo_p7"] = detect_rule(v.lat.values, v.lon.values, v.date, shift_days=PLACEBO_D)

# ---------------------------------------------------------------- ACLED detection
a["period"] = np.where(a.date <= STUDY_END, "2022-02-24..2025-12-31", "2026")
last_ok = (fire_max.tz_convert(None).normalize() - pd.Timedelta(days=PLACEBO_D + 2))
n_dropped_2026_tail = int((a.date > last_ok).sum())
a = a[a.date <= last_ok].reset_index(drop=True)
a["detected"] = detect_rule(a.lat.values, a.lon.values, a.date)
a["placebo_m7"] = detect_rule(a.lat.values, a.lon.values, a.date, shift_days=-PLACEBO_D)
a["placebo_p7"] = detect_rule(a.lat.values, a.lon.values, a.date, shift_days=PLACEBO_D)
a["detected_3km"] = detect_rule(a.lat.values, a.lon.values, a.date, radius=3000.0)
a["placebo_m7_3km"] = detect_rule(a.lat.values, a.lon.values, a.date, radius=3000.0, shift_days=-PLACEBO_D)
a["month"] = a.date.dt.month; a["year"] = a.date.dt.year
a["season"] = np.where(a.month.between(5, 10), "summer", "winter")
a["h3_r6"] = h3_cells(a.lat, a.lon, 6)
log(f"ACLED events {len(a):,}; detection done ({time.time()-t0:.0f}s)")

# ---------------------------------------------------------------- opportunity on event day (r6 cell) — 2022–2025 only
def join_opp(df):
    k = df[["h3_r6", "date"]].drop_duplicates()
    con.register("k", k)
    o = con.sql(f"""SELECT k.h3_r6, k.date, coalesce(o.opportunity, 0) AS opp_day
                    FROM k LEFT JOIN read_parquet('{OPP_DAY}') o ON o.h3_r6=k.h3_r6 AND o.date=k.date""").df()
    con.unregister("k")
    r = df.merge(o, on=["h3_r6", "date"], how="left")
    r["opp_stratum"] = pd.cut(r.opp_day, [-1, 0, 1, 2, 99], labels=["0", "1", "2", "3+"]).astype(str)
    return r

study = a[a.period != "2026"].copy()
study["uid"] = np.arange(len(study), dtype=np.int64)
study = join_opp(study)
v = join_opp(v)

# H1 condition strata for ACLED (same covariate code as H1), geo_precision 1 only, chunked
g1 = study[study.geo_precision == 1].copy()
g1["w0"] = (g1.date - pd.Timedelta(hours=WINDOW_BEFORE_H)).dt.tz_localize("UTC")
g1["w1"] = (g1.date + pd.Timedelta(hours=24 + WINDOW_AFTER_H)).dt.tz_localize("UTC")
cov = pd.concat([window_covariates(g1.iloc[s:s + CHUNK]) for s in range(0, len(g1), CHUNK)], ignore_index=True)
g1 = g1.merge(cov, on="uid")
g1["stratum"] = h1_strata(g1, "clear_night")
study = study.merge(g1[["uid", "stratum"]], on="uid", how="left")
study["stratum"] = study["stratum"].fillna("geo2_not_computed")
log(f"covariates done ({time.time()-t0:.0f}s)")

# population tercile (geo1, study window)
q = study.loc[study.geo_precision == 1, "population_best"].quantile([1 / 3, 2 / 3]).values
study["pop_tercile"] = pd.cut(study.population_best, [-np.inf, q[0], q[1], np.inf], labels=["T1 rural", "T2", "T3 urban"]).astype(str)
study.loc[study.population_best.isna(), "pop_tercile"] = "missing"

# ---------------------------------------------------------------- recall tables
def rt(df, by, set_name, geo):
    rows = []
    groups = [("all", df)] if by is None else list(df.groupby(by, dropna=False))
    for lev, s in groups:
        n = len(s)
        if n == 0:
            continue
        k = int(s.detected.sum()); p, lo, hi = wilson(k, n)
        pm = s.placebo_m7.mean(); pp = s.placebo_p7.mean(); ch = (pm + pp) / 2
        r = dict(event_set=set_name, geo_precision=geo, group_by=by or "overall", level=str(lev[0] if isinstance(lev, tuple) else lev),
                 n=n, detected=k, recall=p, ci_lo=lo, ci_hi=hi, placebo_m7=pm, placebo_p7=pp, chance=ch,
                 excess=p - ch, ratio_to_chance=(p / ch if ch > 0 else np.nan))
        if "detected_3km" in s:
            r.update(recall_3km=s.detected_3km.mean(), placebo_m7_3km=s.placebo_m7_3km.mean())
        rows.append(r)
    return rows

rows = []
for per in ["2022-02-24..2025-12-31", "2026"]:
    base = a[a.period == per]
    for geo, s in [("1", base[base.geo_precision == 1]), ("1|2", base)]:
        tag = f"ACLED {per}"
        for by in [None, "sub_event_type", "event_type", "season", "year"]:
            rows += rt(s, by, tag, geo)
for geo, s in [("1", study[study.geo_precision == 1]), ("1|2", study)]:
    for by in ["opp_stratum", "stratum", "pop_tercile", "month"]:
        rows += rt(s, by, "ACLED 2022-02-24..2025-12-31", geo)
    for st in ["Shelling/artillery/missile attack", "Air/drone strike", "Armed clash"]:
        for by in ["opp_stratum", "pop_tercile"]:
            for r in rt(s[s.sub_event_type == st], by, "ACLED 2022-02-24..2025-12-31", geo):
                r["group_by"] = f"{by}|{st}"; rows.append(r)
for lab, s in [("V all", v), ("V test", v[v.split == "test"])]:
    for by in [None, "opp_stratum", "stratum", "season"]:
        rows += rt(s, by, lab, "V")
tab = pd.DataFrame(rows)
tab.to_csv(OUT / "acled_recall.csv", index=False)


def get(es, geo, gb, lev, col="recall"):
    m = tab[(tab.event_set == es) & (tab.geo_precision == geo) & (tab.group_by == gb) & (tab.level == lev)]
    return float(m[col].iloc[0]) if len(m) else None

S = "ACLED 2022-02-24..2025-12-31"
cmp = []
for gb, levs in [("opp_stratum", ["0", "1", "2", "3+"]), ("stratum", ["worst", "other", "best", "no_overpass"]), ("season", ["winter", "summer"])]:
    for lev in levs:
        cmp.append(dict(group_by=gb, level=lev,
                        acled_g1_n=get(S, "1", gb, lev, "n"), acled_g1_recall=get(S, "1", gb, lev), acled_g1_chance=get(S, "1", gb, lev, "chance"),
                        v_all_n=get("V all", "V", gb, lev, "n"), v_all_recall=get("V all", "V", gb, lev), v_all_chance=get("V all", "V", gb, lev, "chance"),
                        v_test_recall=get("V test", "V", gb, lev)))
cmp = pd.DataFrame(cmp); cmp.to_csv(OUT / "acled_vs_v_opportunity.csv", index=False)


def ratio(es, geo, gb, hi, lo):
    x, y = get(es, geo, gb, hi), get(es, geo, gb, lo)
    return (x / y) if (x is not None and y) else None

grad = {
    "opp_3plus_over_0": {"acled_g1": ratio(S, "1", "opp_stratum", "3+", "0"), "acled_g12": ratio(S, "1|2", "opp_stratum", "3+", "0"),
                         "v_all": ratio("V all", "V", "opp_stratum", "3+", "0"), "v_test": ratio("V test", "V", "opp_stratum", "3+", "0")},
    "h1_best_over_worst": {"acled_g1": ratio(S, "1", "stratum", "best", "worst"),
                           "v_all": ratio("V all", "V", "stratum", "best", "worst"), "v_test": ratio("V test", "V", "stratum", "best", "worst")},
    "summer_over_winter": {"acled_g1": ratio(S, "1", "season", "summer", "winter"),
                           "v_all": ratio("V all", "V", "season", "summer", "winter")},
}
# Spearman over the 4 opportunity strata is not informative; report the monotonicity flag instead.
def mono(es, geo):
    r = [get(es, geo, "opp_stratum", l) for l in ["0", "1", "2", "3+"]]
    return bool(all(np.diff(r) > 0)) if None not in r else None
grad["monotone_increasing_in_opportunity"] = {"acled_g1": mono(S, "1"), "v_all": mono("V all", "V")}

# ---------------------------------------------------------------- cell-week check
ac = con.sql(f"""SELECT event_date, latitude AS lat, longitude AS lon FROM read_csv_auto('{ACLED}', sample_size=-1)
                 WHERE country='Ukraine' AND time_precision=1 AND geo_precision IN (1,2) AND sub_event_type IN ({sub_list})
                   AND event_date <= DATE '2025-12-31'""").df()
ac["h3_r5"] = h3_cells(ac.lat, ac.lon, 5)
ac["week_start"] = pd.to_datetime(ac.event_date) - pd.to_timedelta(pd.to_datetime(ac.event_date).dt.weekday, unit="D")
acw = ac.groupby(["h3_r5", "week_start"]).size().rename("acled").reset_index()
del ac
pan = pd.read_parquet(PANEL, columns=["h3_r5", "week_start", "c1", "front_15", "fires", "opportunity", "in_ukraine"])
pan = pan[pan.front_15 & pan.in_ukraine].merge(acw, on=["h3_r5", "week_start"], how="left")
pan["acled"] = pan.acled.fillna(0).astype(np.float32)
n_acled_total = int(acw.acled.sum()); n_acled_on_front = int(pan.acled.sum())

def cw(df):
    x = np.log1p(df.fires.values.astype(float)); y = np.log1p(df.acled.values.astype(float))
    d = pd.DataFrame({"x": x, "y": y, "c": df.h3_r5.values, "w": df.week_start.values})
    for col in ["x", "y"]:  # two-way demean (one pass + correction; balanced-enough panel)
        d[col] = d[col] - d.groupby("c")[col].transform("mean") - d.groupby("w")[col].transform("mean") + d[col].mean()
    return dict(cell_weeks=len(df), cells=int(df.h3_r5.nunique()), share_weeks_with_acled=float((df.acled > 0).mean()),
                pearson_log1p=float(pearsonr(x, y)[0]), spearman=float(spearmanr(df.fires, df.acled)[0]),
                pearson_log1p_two_way_demeaned=float(pearsonr(d.x, d.y)[0]))

cellweek = {"acled_events_2022_2025_time1_geo12": n_acled_total, "acled_events_on_front15_cellweeks": n_acled_on_front,
            "front15_all_2022_2025": cw(pan), "front15_C1": cw(pan[pan.c1])}
# H5 context: ACLED intensity per front cell-week by calendar month in C1 vs H5 ratio; ACLED coverage over time.
c1 = pan[pan.c1].copy(); c1["m"] = c1.week_start.dt.month
mon = c1.groupby("m").agg(acled_per_cw=("acled", "mean"), fires_per_cw=("fires", "mean")).reset_index()
h5 = pd.read_csv(H5).rename(columns={"month": "m"})
mon = mon.merge(h5[["m", "ratio"]], on="m")
cellweek["H5_context_C1"] = {"spearman_month_acled_per_cw_vs_h5_ratio": float(spearmanr(mon.acled_per_cw, mon.ratio)[0]),
                             "spearman_month_acled_per_cw_vs_fires_per_cw": float(spearmanr(mon.acled_per_cw, mon.fires_per_cw)[0]),
                             "note": "C1 = 2022-04-03..2024-07-07; H5 and every C1 descriptive end before late 2025, so ACLED's late-2025 coverage cannot change them."}
pan["half"] = pan.week_start.dt.year.astype(str) + np.where(pan.week_start.dt.month <= 6, "H1", "H2")
hy = pan.groupby("half").agg(acled_per_cw=("acled", "mean"), fires_per_cw=("fires", "mean"), cw=("acled", "size"))
cellweek["front15_by_half_year"] = {k: {kk: round(float(vv), 3) for kk, vv in r.items()} for k, r in hy.iterrows()}
json.dump(cellweek, open(OUT / "acled_cellweek.json", "w"), indent=2)

# ---------------------------------------------------------------- figure
fig, ax = plt.subplots(1, 3, figsize=(14, 4))
for i, (gb, levs, title) in enumerate([("opp_stratum", ["0", "1", "2", "3+"], "recall by clear overpasses on event day (r6 cell)"),
                                       ("stratum", ["worst", "other", "best"], "recall by H1 condition stratum")]):
    xs = np.arange(len(levs))
    for off, (es, geo, lab, col) in zip([-0.2, 0.2], [(S, "1", "ACLED geo-prec 1", "#e76f51"), ("V all", "V", "GeoConfirmed+Bellingcat (V all)", "#457b9d")]):
        r = [tab[(tab.event_set == es) & (tab.geo_precision == geo) & (tab.group_by == gb) & (tab.level == l)].iloc[0] for l in levs]
        ax[i].bar(xs + off, [x.recall for x in r], 0.38, yerr=[[x.recall - x.ci_lo for x in r], [x.ci_hi - x.recall for x in r]], color=col, label=lab, capsize=3)
        ax[i].scatter(xs + off, [x.chance for x in r], marker="_", s=300, color="k", zorder=3)
    ax[i].set_xticks(xs); ax[i].set_xticklabels(levs); ax[i].set_title(title, fontsize=9); ax[i].set_ylabel("recall (1 km, 48 h)")
ax[0].legend(fontsize=7)
st = tab[(tab.event_set == S) & (tab.geo_precision == "1") & (tab.group_by == "sub_event_type")].sort_values("recall")
ax[2].barh(st.level, st.recall, xerr=[st.recall - st.ci_lo, st.ci_hi - st.recall], color="#e76f51", capsize=3)
ax[2].scatter(st.chance, st.level, marker="|", s=200, color="k", zorder=3); ax[2].set_title("ACLED by sub-type (| = chance, ±7 d)", fontsize=9)
ax[2].tick_params(axis="y", labelsize=7)
fig.text(0.01, 0.01, "Armed Conflict Location & Event Data (ACLED); acleddata.com, accessed 2026-10-26. PRIVATE — not for publication.", fontsize=7)
fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(FIG / "acled_grade.png", dpi=150); plt.close(fig)

# ---------------------------------------------------------------- summary + meta
def ov(es, geo):
    return {c: get(es, geo, "overall", "all", c) for c in ["n", "recall", "ci_lo", "ci_hi", "chance", "excess", "ratio_to_chance", "recall_3km", "placebo_m7_3km"]}
h1 = pd.read_csv(H1); h1p = h1[(h1.event_set == "all_types") & (h1.split == "test") & (h1.group_by == "overall")].iloc[0]
summary = {
    "label": "exploratory (ACLED not in PREREG)",
    "attribution": "Armed Conflict Location & Event Data (ACLED); acleddata.com, accessed 2026-10-26",
    "rule_check_mismatches_vs_H1": n_mismatch,
    "H1_primary_recall_test": float(h1p.recall),
    "overall": {"acled_study_geo1": ov(S, "1"), "acled_study_geo12": ov(S, "1|2"),
                "acled_2026_geo1": ov("ACLED 2026", "1"), "acled_2026_geo12": ov("ACLED 2026", "1|2"),
                "v_all": ov("V all", "V"), "v_test": ov("V test", "V")},
    "gradients": grad,
    "cellweek": {k: cellweek[k] for k in ["front15_all_2022_2025", "front15_C1", "H5_context_C1"]},
}
json.dump(summary, open(OUT / "acled_summary.json", "w"), indent=2, default=float)
write_meta(OUT / "acled_recall.csv", inputs={"acled": ACLED, "fires": FIRES, "opportunity": OPP_DAY, "panel": PANEL, "h1": H1, "h5": H5},
           counts={"acled_rows_read_filtered": n_read, "acled_events_used": len(a), "study_geo1": int((study.geo_precision == 1).sum()),
                   "study_geo12": len(study), "y2026_used": int((a.period == "2026").sum()), "dropped_2026_tail_beyond_fire_data": n_dropped_2026_tail,
                   "v_events": len(v), "fires_last_ts": str(fire_max)},
           extra={"label": "exploratory", "seed_note": "no randomness used", "columns_read": ["event_date", "event_type", "sub_event_type", "latitude", "longitude", "geo_precision", "time_precision", "population_best", "country"],
                  "filters": "country=Ukraine, time_precision=1, geo_precision in {1,2}, sub_event_type in " + str(SUBTYPES),
                  "rule": "H1 rule: >=1 fire within 1,000 m (EPSG:3035), acq_ts in [date-12h, date+36h]; placebo = same place/window shifted -7 d and +7 d; chance = mean of the two",
                  "opportunity": "opportunity_r6_day.opportunity (clear overpasses) for the event's r6 cell on the event date; missing cell-day = 0",
                  "pop_terciles_geo1": [float(x) for x in q], "runtime_s": round(time.time() - t0, 1)})
log(f"done {time.time()-t0:.0f}s")
print(json.dumps({"overall": {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in d.items()} for k, d in summary["overall"].items()},
                  "gradients": grad, "rule_mismatch": n_mismatch}, indent=1, default=str))
