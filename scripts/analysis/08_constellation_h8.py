"""H8 Constellation loss (PREREG §4 H8, descriptive with CIs; DESIGN D15). Builder C.

Drop S-NPP (satellite N) from fires and from overpasses, then
(a) recompute H1 recall (overall + strata, V-test and all-V) and report deltas vs the full constellation;
(b) blind-season length: per in-Ukraine h3_r6 cell, the number of ISO weeks (per calendar year of the week's Thursday)
    whose median daily opportunity is below the 25th percentile of all C1-period (2022-04-03→2024-07-07) in-Ukraine
    cell-days of full-constellation opportunity. If that percentile is 0 (most winter cell-days have opportunity 0),
    "below" is impossible, so blind = median daily opportunity ≤ percentile (i.e. = 0); stated in the JSON.
    Overall (all in-Ukraine cells) and for the north-east (Kharkiv UA-63, Luhansk UA-09, Donetsk UA-14, Sumy UA-59).
Deltas carry cell block-bootstrap 95% CIs (resample h3_r6 cells with replacement, 1,000 draws, seed 20261014),
for both recall (events grouped by cell) and blind-season length.
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd, h3, geopandas as gpd
from shapely.geometry import Point
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from _common import INTERIM, DERIVED, ROOT, RAW, SEED, write_meta, log
from _detect import (load_events, load_fires_ukr, detect, window_covariates, h1_strata, wilson, con_utc,
                     RESTRICTED_TYPES, EVENTS, FIRES, OVERPASSES, OPP_DAY)

RES = DERIVED / "results"; FIG = ROOT / "figures"
t0 = time.time(); rng = np.random.default_rng(SEED)
NE = ["UA-63", "UA-09", "UA-14", "UA-59"]
C1 = ("2022-04-03", "2024-07-07")
DRAWS = 1000

# ---------------- (a) recall without S-NPP ----------------
full = pd.read_parquet(INTERIM / "events_detect.parquet")
ev = load_events()
fires2 = load_fires_ukr(["N20", "N21"])
det2 = detect(ev, fires2)
cov2 = window_covariates(ev, ["N20", "N21"])
red = ev[["uid", "event_id", "h3_r6", "split", "event_type", "month", "year", "oblast_iso"]].merge(det2, on="uid").merge(cov2, on="uid")
red["stratum"] = h1_strata(red, "clear_night")
red["season"] = np.where(red["month"].between(5, 10), "summer", "winter")
red.to_parquet(INTERIM / "events_detect_noSNPP.parquet", index=False)
both = full[["uid", "h3_r6", "split", "event_type", "month", "season", "stratum", "detected"]].rename(columns={"detected": "det_full", "stratum": "stratum_full"}) \
    .merge(red[["uid", "detected", "stratum"]].rename(columns={"detected": "det_red", "stratum": "stratum_red"}), on="uid")
both["is_ne"] = both["uid"].map(ev.set_index("uid")["oblast_iso"]).isin(NE)
both["winter_months"] = both["month"].isin([11, 12, 1, 2])


def cell_boot_delta(d, maskf, draws=DRAWS):
    """Block bootstrap over h3_r6 cells of recall_full, recall_red, delta (pp)."""
    cells = d["h3_r6"].unique(); idx_by_cell = d.groupby("h3_r6").indices
    df_ = d["det_full"].values.astype(float); dr_ = d["det_red"].values.astype(float)
    mf = maskf(d).values if callable(maskf) else np.ones(len(d), bool)
    out = []
    for _ in range(draws):
        pick = rng.choice(cells, len(cells), replace=True)
        ii = np.concatenate([idx_by_cell[c] for c in pick])
        ii = ii[mf[ii]]
        if len(ii) == 0:
            continue
        out.append((df_[ii].mean(), dr_[ii].mean()))
    out = np.array(out)
    return out


recall_rows, deltas = [], {}
for split_label, sub in [("test", both[both.split == "test"]), ("all", both)]:
    for grp, mk in [("overall", lambda d: pd.Series(True, index=d.index)), ("winter_Nov_Feb", lambda d: d["winter_months"]),
                    ("summer_May_Oct", lambda d: d["season"] == "summer"), ("winter_Nov_Apr", lambda d: d["season"] == "winter"),
                    ("north_east", lambda d: d["is_ne"]), ("stratum_best_full", lambda d: d["stratum_full"] == "best"),
                    ("stratum_worst_full", lambda d: d["stratum_full"] == "worst"), ("stratum_other_full", lambda d: d["stratum_full"] == "other")]:
        m = mk(sub); s = sub[m]
        n = len(s); kf = int(s.det_full.sum()); kr = int(s.det_red.sum())
        pf, lof, hif = wilson(kf, n); pr, lor, hir = wilson(kr, n)
        bs = cell_boot_delta(sub, mk)
        dpp = (bs[:, 1] - bs[:, 0]) * 100
        row = dict(split=split_label, group=grp, n=n, detected_full=kf, recall_full=float(pf), recall_full_ci=[float(lof), float(hif)],
                   detected_noSNPP=kr, recall_noSNPP=float(pr), recall_noSNPP_ci=[float(lor), float(hir)],
                   delta_pp=float((pr - pf) * 100), delta_pp_ci=[float(np.percentile(dpp, 2.5)), float(np.percentile(dpp, 97.5))],
                   relative_change=float((pr - pf) / pf) if pf > 0 else None)
        recall_rows.append(row)
    # strata recomputed under the reduced constellation (the strata themselves move, since clear_night uses N20/N21 only)
    for st in ["best", "other", "worst", "no_overpass"]:
        s = sub[sub.stratum_red == st]; n = len(s)
        if n == 0:
            continue
        k = int(s.det_red.sum()); p, lo, hi = wilson(k, n)
        recall_rows.append(dict(split=split_label, group=f"stratum_{st}_recomputed_noSNPP", n=n, detected_noSNPP=k, recall_noSNPP=float(p), recall_noSNPP_ci=[float(lo), float(hi)]))
rec = pd.DataFrame(recall_rows)
rec.to_csv(RES / "h8_recall_noSNPP.csv", index=False)
# best/worst ratio under reduced constellation (test)
t = both[both.split == "test"]
b = t[t.stratum_red == "best"].det_red.mean(); w = t[t.stratum_red == "worst"].det_red.mean()
ratio_red = float(b / w) if w > 0 else None
log("recall part done")

# ---------------- (b) blind season ----------------
con = con_utc()
opp = con.sql(f"""SELECT h3_r6, date::DATE AS date, opportunity, (opp_N20 + opp_N21) AS opp_noSNPP, n_overpasses, (n_N20 + n_N21) AS n_over_noSNPP
                  FROM '{OPP_DAY}' WHERE in_ukraine""").df()
opp["date"] = pd.to_datetime(opp["date"])
c1 = opp[(opp.date >= C1[0]) & (opp.date <= C1[1])]
q25 = float(np.percentile(c1["opportunity"].values, 25))
q25_strict_possible = bool((c1["opportunity"] < q25).any())
blind_rule = "median_daily_opportunity < q25" if q25_strict_possible else "median_daily_opportunity <= q25 (q25 == 0, so strict 'below' is empty)"
log(f"C1 cell-days {len(c1):,}; q25 of daily opportunity = {q25}; rule: {blind_rule}")
iso = opp["date"].dt.isocalendar()
opp["iso_year"] = iso["year"].astype(int); opp["iso_week"] = iso["week"].astype(int)
wk = opp.groupby(["h3_r6", "iso_year", "iso_week"]).agg(med_full=("opportunity", "median"), med_red=("opp_noSNPP", "median"), n_days=("date", "size")).reset_index()
wk = wk[wk.n_days >= 4]   # drop the two partial boundary weeks
if q25_strict_possible:
    wk["blind_full"] = wk.med_full < q25; wk["blind_red"] = wk.med_red < q25
else:
    wk["blind_full"] = wk.med_full <= q25; wk["blind_red"] = wk.med_red <= q25
# cell → oblast
cells = pd.DataFrame({"h3_r6": wk["h3_r6"].unique()})
ll = np.array([h3.cell_to_latlng(c) for c in cells["h3_r6"]])
g = gpd.GeoDataFrame(cells, geometry=[Point(lo, la) for la, lo in ll], crs="EPSG:4326")
adm1 = gpd.read_file(RAW / "boundaries/geoboundaries/geoBoundaries-UKR-ADM1.geojson")[["shapeISO", "geometry"]]
g = gpd.sjoin(g, adm1, how="left", predicate="within").drop_duplicates("h3_r6")
miss = g["shapeISO"].isna()
if miss.any():   # centroid on a seam: nearest oblast
    near = gpd.sjoin_nearest(g[miss].drop(columns=["shapeISO", "index_right"]), adm1, how="left")
    g.loc[miss, "shapeISO"] = near["shapeISO"].values
cell_obl = g.set_index("h3_r6")["shapeISO"]
wk["oblast_iso"] = wk["h3_r6"].map(cell_obl); wk["is_ne"] = wk["oblast_iso"].isin(NE)
# per cell-year counts
cy = wk.groupby(["h3_r6", "iso_year", "is_ne"]).agg(blind_weeks_full=("blind_full", "sum"), blind_weeks_red=("blind_red", "sum"), n_weeks=("iso_week", "size")).reset_index()
# published cell-week table is too fine (cell-week in Ukraine is allowed by PREREG §7 but we keep results at oblast-year)
ob = wk.groupby(["oblast_iso", "iso_year"]).agg(n_cells=("h3_r6", "nunique"), n_cell_weeks=("iso_week", "size"),
                                                 blind_cell_weeks_full=("blind_full", "sum"), blind_cell_weeks_noSNPP=("blind_red", "sum")).reset_index()
ob["blind_weeks_per_cell_full"] = ob.blind_cell_weeks_full / ob.n_cells; ob["blind_weeks_per_cell_noSNPP"] = ob.blind_cell_weeks_noSNPP / ob.n_cells
ob["delta_weeks"] = ob.blind_weeks_per_cell_noSNPP - ob.blind_weeks_per_cell_full
ob.to_csv(RES / "h8_blind_season_oblast_year.csv", index=False)


def boot_blind(d, draws=DRAWS):
    cells = d["h3_r6"].unique(); idx = d.groupby("h3_r6").indices
    f = d["blind_weeks_full"].values.astype(float); r = d["blind_weeks_red"].values.astype(float)
    out = []
    for _ in range(draws):
        pick = rng.choice(cells, len(cells), replace=True)
        ii = np.concatenate([idx[c] for c in pick])
        out.append((f[ii].mean(), r[ii].mean()))
    return np.array(out)


blind_rows = []
for region, dd in [("ukraine", cy), ("north_east", cy[cy["is_ne"]])]:
    for yr, d in [("all_years_mean", dd)] + [(str(y), dd[dd.iso_year == y]) for y in sorted(dd.iso_year.unique())]:
        bs = boot_blind(d); dl = bs[:, 1] - bs[:, 0]
        blind_rows.append(dict(region=region, year=yr, n_cells=int(d.h3_r6.nunique()), n_cell_years=len(d),
                               blind_weeks_full=float(d.blind_weeks_full.mean()), blind_weeks_full_ci=[float(np.percentile(bs[:, 0], 2.5)), float(np.percentile(bs[:, 0], 97.5))],
                               blind_weeks_noSNPP=float(d.blind_weeks_red.mean()), blind_weeks_noSNPP_ci=[float(np.percentile(bs[:, 1], 2.5)), float(np.percentile(bs[:, 1], 97.5))],
                               delta_weeks=float(d.blind_weeks_red.mean() - d.blind_weeks_full.mean()), delta_weeks_ci=[float(np.percentile(dl, 2.5)), float(np.percentile(dl, 97.5))]))
blind = pd.DataFrame(blind_rows); blind.to_csv(RES / "h8_blind_season.csv", index=False)

# weekly share of blind cells (national + NE), full vs reduced, for the figure and a published series
ws = wk.groupby(["iso_year", "iso_week"]).agg(share_blind_full=("blind_full", "mean"), share_blind_noSNPP=("blind_red", "mean")).reset_index()
wsne = wk[wk["is_ne"]].groupby(["iso_year", "iso_week"]).agg(share_blind_full_ne=("blind_full", "mean"), share_blind_noSNPP_ne=("blind_red", "mean")).reset_index()
ws = ws.merge(wsne, on=["iso_year", "iso_week"]); ws.to_csv(RES / "h8_blind_share_week.csv", index=False)

summary = {
    "recall_test_overall": next(r for r in recall_rows if r["split"] == "test" and r["group"] == "overall"),
    "recall_test_winter_Nov_Feb": next(r for r in recall_rows if r["split"] == "test" and r["group"] == "winter_Nov_Feb"),
    "recall_test_winter_Nov_Apr": next(r for r in recall_rows if r["split"] == "test" and r["group"] == "winter_Nov_Apr"),
    "recall_test_north_east": next(r for r in recall_rows if r["split"] == "test" and r["group"] == "north_east"),
    "ratio_best_worst_noSNPP_test": ratio_red,
    "blind_season": {f"{r['region']}|{r['year']}": r for r in blind_rows},
    "q25_C1_daily_opportunity": q25, "blind_rule": blind_rule, "C1_window": C1,
    "prereg_prediction": {"recall_falls_10_25pp_in_winter": None, "blind_season_lengthens_ge_2_weeks_in_NE": None},
    "n_cells_ukraine": int(cy.h3_r6.nunique()), "n_cells_ne": int(cy[cy["is_ne"]].h3_r6.nunique()),
    "definitions": {"fires": "satellites N20, N21 only", "overpasses": "satellites N20, N21 only (strata, clear_night recomputed)",
                    "bootstrap": f"cell block bootstrap over h3_r6, {DRAWS} draws, seed {SEED}", "blind_week": blind_rule,
                    "weeks": "ISO weeks with ≥4 days in the data (two boundary weeks dropped), assigned to ISO year"}}
w = summary["recall_test_winter_Nov_Feb"]["delta_pp"]; ne = summary["blind_season"]["north_east|all_years_mean"]["delta_weeks"]
summary["prereg_prediction"]["recall_falls_10_25pp_in_winter"] = bool(-25 <= w <= -10)
summary["prereg_prediction"]["blind_season_lengthens_ge_2_weeks_in_NE"] = bool(ne >= 2)
summary["verdict"] = "descriptive; no success criterion. See prereg_prediction flags."
json.dump(summary, open(RES / "h8_summary.json", "w"), indent=2, default=str)

fig, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
x = pd.to_datetime(ws.iso_year.astype(str) + "-W" + ws.iso_week.astype(str).str.zfill(2) + "-4", format="%G-W%V-%u")
ax[0].plot(x, ws.share_blind_full, color="#1d3557", label="full constellation"); ax[0].plot(x, ws.share_blind_noSNPP, color="#e63946", label="without S-NPP")
ax[0].set_ylabel("share of Ukraine cells blind"); ax[0].legend(fontsize=8); ax[0].set_title("H8 blind weeks (median daily opportunity ≤ C1 25th pct)")
ax[1].plot(x, ws.share_blind_full_ne, color="#1d3557"); ax[1].plot(x, ws.share_blind_noSNPP_ne, color="#e63946"); ax[1].set_ylabel("share of NE cells blind")
fig.tight_layout(); fig.savefig(FIG / "h8_blind_season.png", dpi=150); plt.close(fig)

r = rec[(rec.split == "test") & (rec.group.isin(["overall", "summer_May_Oct", "winter_Nov_Apr", "winter_Nov_Feb", "north_east"]))]
fig, ax = plt.subplots(figsize=(7, 3.8)); xx = np.arange(len(r))
ax.bar(xx - 0.18, r.recall_full, 0.36, color="#1d3557", label="full"); ax.bar(xx + 0.18, r.recall_noSNPP, 0.36, color="#e63946", label="without S-NPP")
ax.set_xticks(xx); ax.set_xticklabels(r.group, rotation=15); ax.set_ylabel("recall (V-test)"); ax.legend(); ax.set_title("H8 recall with and without S-NPP")
fig.tight_layout(); fig.savefig(FIG / "h8_recall_noSNPP.png", dpi=150); plt.close(fig)

write_meta(RES / "h8_summary.json", inputs={"events_detect": INTERIM / "events_detect.parquet", "fires": FIRES, "opportunity_day": OPP_DAY,
                                              "overpasses_meta": INTERIM / "overpasses_r6_meta.json"},
           counts={"events": len(both), "cells_ukraine": summary["n_cells_ukraine"], "cells_ne": summary["n_cells_ne"], "c1_cell_days": len(c1)},
           extra={"runtime_s": round(time.time() - t0, 1), "q25": q25, "blind_rule": blind_rule})
log(f"H8 done {time.time()-t0:.0f}s")
print(json.dumps({k: summary[k] for k in ["recall_test_overall", "recall_test_winter_Nov_Feb", "recall_test_north_east", "q25_C1_daily_opportunity", "blind_rule", "prereg_prediction"]}, indent=1, default=str))
print(blind.to_string())
