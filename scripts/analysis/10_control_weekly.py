"""10_control_weekly.py — VIINA settlement control, weekly modal status, Voronoi areas, RU|UA control line and
front-cell flags, 2022-02-21 -> latest 2026 ISO week. Contract: planning/PANEL.md (Builder D §1); PREREG §3.

Outputs (data/interim/analysis/):
  control_weekly.parquet          generator settlement × ISO week: modal status, status_dsm, status_isw, status_wiki
  voronoi_area.parquet            geonameid, gen_id, area_km2 (Voronoi clipped to Ukraine, EPSG:3035), h3_r5, h3_r6
  control/voronoi_polys.parquet   generator Voronoi polygons (geo, EPSG:3035)           (interim, not published)
  control/voronoi_edges.parquet   shared edges between neighbouring Voronoi polygons (i, j, geometry)
  control/status_matrix.npz       int8 generator × week matrices per status source + week list (0 missing,1 UA,2 RU,3 CONTESTED)
  control/control_line_week.parquet  per week: line length, edges, national km² by status (each source), settlement counts
  control/front_r5_week.parquet, control/front_r6_week.parquet  cell × week: dist_to_line_km, front_10/15/25, rear_strip
  control/cells_r5.parquet, control/cells_r6.parquet            cell polygons (geo), centroid, area in Ukraine

Modal status: most frequent non-missing daily status in the ISO week (Mon–Sun); ties broken by the status on the
latest day of the week with a non-missing status (prereg_constants.py rule). Settlements sharing coordinates are
merged into one generator (lowest geonameid); its daily status is the primary settlement's, filled from the alias
when the primary is missing. Control line = shared Voronoi edges between an RU and a UA settlement (majority
`status`); CONTESTED is neither side. Front flag = cell centroid within 10/15/25 km of the line; rear strip 50–90 km.

Run:  ~/D3/Frontline_From_Space/.venv/bin/python -I scripts/analysis/10_control_weekly.py
"""
from __future__ import annotations
import sys, time, zipfile
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, shapely
from scipy import sparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import INTERIM, write_meta, log
from _control import (CRS, CTRL, TESS, VIINA_ZIPS, BANDS, STATUS_COLS, STATUS_CODE, PANEL_START,
                      ukraine_polygon, cells_touching, iso_week_start)

t0 = time.time()
CTRL.mkdir(parents=True, exist_ok=True)
ODBL = "Contains VIINA data (Zhukov, Yuri. 'VIINA: Violent Incident Information from News Articles on the 2022 Russian Invasion of Ukraine'), ODbL 1.0; derived settlement-control aggregates."

# ---------------------------------------------------------------- Ukraine, cells
UA = ukraine_polygon()
shapely.prepare(UA)
log(f"Ukraine polygon {UA.area/1e6:,.0f} km2")
CELLS = {}
for res in (5, 6):
    hx = cells_touching(UA, res)
    hx["area_in_ua_km2"] = hx.geometry.intersection(UA).area / 1e6
    hx["area_km2"] = hx.geometry.area / 1e6
    c = hx.geometry.centroid
    hx["cent_x"], hx["cent_y"] = c.x, c.y
    hx["in_ukraine"] = shapely.contains(UA, c.values)
    CELLS[res] = hx
    hx.to_parquet(CTRL / f"cells_r{res}.parquet")
    log(f"res {res}: {len(hx)} cells touching Ukraine ({int(hx.in_ukraine.sum())} centroid inside)")

# ---------------------------------------------------------------- settlements -> Voronoi
tess = gpd.read_file(TESS, columns=["geonameid", "latitude", "longitude"], ignore_geometry=True)
tess["geonameid"] = tess.geonameid.astype("int64")
pts = gpd.GeoSeries(gpd.points_from_xy(tess.longitude, tess.latitude), crs=4326).to_crs(CRS)
tess["x"], tess["y"] = pts.x.round(0), pts.y.round(0)
tess = tess.sort_values("geonameid").reset_index(drop=True)
dup = tess.duplicated(["x", "y"])
gen = tess[~dup].reset_index(drop=True)
alias = tess.merge(gen[["x", "y", "geonameid"]].rename(columns={"geonameid": "gen_id"}), on=["x", "y"])
log(f"settlements {len(tess)}; generators {len(gen)} ({int(dup.sum())} share coordinates -> merged)")
mp = shapely.MultiPoint(np.c_[gen.x, gen.y])
vor = shapely.voronoi_polygons(mp, extend_to=UA.envelope.buffer(200_000), ordered=True)
vpoly = np.array(shapely.get_parts(vor))
assert len(vpoly) == len(gen) and shapely.contains(vpoly, shapely.points(np.c_[gen.x, gen.y])).all()
vpoly = shapely.intersection(vpoly, UA)
gen["area_km2"] = shapely.area(vpoly) / 1e6
log(f"Voronoi clipped: total {gen.area_km2.sum():,.0f} km2; {int((gen.area_km2 == 0).sum())} empty after clip")
gpd.GeoDataFrame(gen[["geonameid", "area_km2"]].rename(columns={"geonameid": "gen_id"}), geometry=vpoly, crs=CRS).to_parquet(CTRL / "voronoi_polys.parquet")

import h3
gen["h3_r5"] = [h3.latlng_to_cell(a, b, 5) for a, b in zip(gen.latitude, gen.longitude)]
gen["h3_r6"] = [h3.latlng_to_cell(a, b, 6) for a, b in zip(gen.latitude, gen.longitude)]
va = alias[["geonameid", "gen_id"]].merge(gen[["geonameid", "area_km2", "h3_r5", "h3_r6"]].rename(columns={"geonameid": "gen_id"}), on="gen_id")
va.loc[va.geonameid != va.gen_id, "area_km2"] = 0.0   # area is carried by the generator; aliases get 0 (no double count)
va = va.sort_values("geonameid").reset_index(drop=True)
va.to_parquet(INTERIM / "voronoi_area.parquet", index=False)
write_meta(INTERIM / "voronoi_area.parquet", inputs={"tess": TESS}, counts={"settlements": len(va), "generators": len(gen), "total_km2": float(gen.area_km2.sum())},
           extra={"crs": "EPSG:3035", "clip": "NE 10m Ukraine + NE admin-1 Crimea/Sevastopol", "alias_rule": "settlements sharing rounded-metre coordinates merged; area on the lowest geonameid (gen_id), aliases 0", "licence": ODBL})

# edges
vtree = shapely.STRtree(vpoly)
i, j = vtree.query(vpoly, predicate="intersects")
k = i < j; i, j = i[k], j[k]
edge = shapely.intersection(shapely.boundary(vpoly[i]), shapely.boundary(vpoly[j]))
k = shapely.length(edge) > 1.0
EI, EJ, EG = i[k], j[k], edge[k]
gpd.GeoDataFrame({"i": EI, "j": EJ, "length_m": shapely.length(EG)}, geometry=EG, crs=CRS).to_parquet(CTRL / "voronoi_edges.parquet")
log(f"Voronoi edge pairs {len(EI):,}")

# ---------------------------------------------------------------- VIINA daily -> dense day matrices
gid_idx = pd.Series(np.arange(len(tess)), index=tess.geonameid)        # geonameid -> row (all settlements)
gen_row = gid_idx.loc[gen.geonameid].values                             # generator rows
alias_only = alias[alias.geonameid != alias.gen_id]
a_row, a_gen = gid_idx.loc[alias_only.geonameid].values, gid_idx.loc[alias_only.gen_id].values
day_min, day_max = None, None
daily = []
counts_raw = {}
for y, zp in VIINA_ZIPS.items():
    with zipfile.ZipFile(zp) as z:
        v = pd.read_csv(z.open(f"control_latest_{y}.csv"), usecols=["geonameid", "date"] + STATUS_COLS,
                        dtype={"geonameid": "int64", "date": "int32", **{c: "category" for c in STATUS_COLS}})
    v["date"] = pd.to_datetime(v.date.astype(str), format="%Y%m%d")
    counts_raw[y] = {"rows": len(v), "settlements": int(v.geonameid.nunique()), "dates": [str(v.date.min().date()), str(v.date.max().date())],
                     "status": {k: int(n) for k, n in v.status.value_counts(dropna=False).items()}}
    v = v[v.geonameid.isin(gid_idx.index)]
    out = pd.DataFrame({"r": gid_idx.loc[v.geonameid].values.astype(np.int32), "d": v.date.values})
    for c in STATUS_COLS:
        lut = np.array([STATUS_CODE.get(str(cat), 0) for cat in v[c].cat.categories] + [0], dtype=np.int8)  # last = NaN
        codes = v[c].cat.codes.values.astype(np.int64)
        out[c] = lut[np.where(codes < 0, len(lut) - 1, codes)]
    daily.append(out)
    log(f"VIINA {y}: {counts_raw[y]}")
    del v
daily = pd.concat(daily, ignore_index=True)
DAY0 = PANEL_START
daily = daily[daily.d >= DAY0]
dday = ((daily.d - DAY0).dt.days).values.astype(np.int32)
n_days = int(dday.max()) + 1
n_weeks = int(np.ceil(n_days / 7))
n_days_pad = n_weeks * 7
WEEKS = pd.DatetimeIndex([DAY0 + pd.Timedelta(days=7 * w) for w in range(n_weeks)])
log(f"daily rows {len(daily):,}; days {n_days} ({DAY0.date()}..{(DAY0 + pd.Timedelta(days=n_days-1)).date()}); weeks {n_weeks}")
dup_days = int(daily.duplicated(["r", "d"]).sum())

def dense(col: str) -> np.ndarray:
    M = np.zeros((len(tess), n_days_pad), dtype=np.int8)
    M[daily.r.values, dday] = daily[col].values
    G = M[gen_row].copy()
    # fill generator-missing days from alias settlements
    for ar, ag in zip(a_row, a_gen):
        gi = np.searchsorted(gen_row, ag)
        m = G[gi] == 0
        G[gi, m] = M[ar, m]
    return G

def weekly_modal(G: np.ndarray) -> tuple[np.ndarray, int]:
    W = G.reshape(G.shape[0], n_weeks, 7)
    cnt = np.stack([(W == c).sum(2) for c in (1, 2, 3)], axis=2)         # gen × week × {UA,RU,CT}
    mx = cnt.max(2)
    modal = cnt.argmax(2).astype(np.int8) + 1
    modal[mx == 0] = 0
    tied = ((cnt == mx[..., None]).sum(2) > 1) & (mx > 0)
    # latest non-missing day in the week
    pos = np.where(W > 0, np.arange(7)[None, None, :], -1).max(2)
    latest = np.take_along_axis(W, np.clip(pos, 0, 6)[..., None], axis=2)[..., 0]
    modal[tied] = latest[tied]
    return modal, int(tied.sum())

ST, ties = {}, {}
for c in STATUS_COLS:
    ST[c], ties[c] = weekly_modal(dense(c))
    log(f"{c}: settlement-weeks UA {(ST[c]==1).sum():,} RU {(ST[c]==2).sum():,} CONTESTED {(ST[c]==3).sum():,} missing {(ST[c]==0).sum():,}; ties {ties[c]:,}")
days_per_week = np.bincount(dday // 7, minlength=n_weeks) / max(1, daily.r.nunique())  # approx observed days/week
days_obs = pd.Series(daily.d.unique()).groupby(((pd.Series(daily.d.unique()) - DAY0).dt.days // 7).values).size().reindex(range(n_weeks), fill_value=0).values
np.savez_compressed(CTRL / "status_matrix.npz", weeks=WEEKS.values.astype("datetime64[D]"), gen_id=gen.geonameid.values,
                    **{c: ST[c] for c in STATUS_COLS})

# long table
rows = np.repeat(np.arange(len(gen)), n_weeks); cols = np.tile(np.arange(n_weeks), len(gen))
cw = pd.DataFrame({"gen_id": gen.geonameid.values[rows], "week_start": WEEKS.values[cols]})
code_cat = pd.CategoricalDtype(["", "UA", "RU", "CONTESTED"])
for c in STATUS_COLS:
    cw[c] = pd.Categorical.from_codes(ST[c].ravel(), dtype=code_cat)
cw["iso_year"] = cw.week_start.dt.isocalendar().year.astype("int16"); cw["iso_week"] = cw.week_start.dt.isocalendar().week.astype("int8")
cw.to_parquet(INTERIM / "control_weekly.parquet", index=False)
write_meta(INTERIM / "control_weekly.parquet", inputs={"viina": list(VIINA_ZIPS.values()), "tess": TESS},
           counts={"generators": len(gen), "weeks": n_weeks, "rows": len(cw), "viina_raw": counts_raw, "duplicate_settlement_days": dup_days, "ties_broken_by_latest_day": ties,
                   "settlement_weeks_by_status": {c: {"UA": int((ST[c]==1).sum()), "RU": int((ST[c]==2).sum()), "CONTESTED": int((ST[c]==3).sum()), "missing": int((ST[c]==0).sum())} for c in STATUS_COLS}},
           extra={"week_rule": "ISO week Mon–Sun; modal non-missing daily status; ties -> status on the latest non-missing day", "weeks": [str(WEEKS[0].date()), str(WEEKS[-1].date())],
                  "days_observed_per_week_first_last": [int(days_obs[0]), int(days_obs[-1])], "licence": ODBL})

# ---------------------------------------------------------------- control line, national km², front flags
S = ST["status"]
RU, UAs = (S == 2), (S == 1)
line_km, n_edges = np.zeros(n_weeks), np.zeros(n_weeks, int)
nat = {c: {s: np.zeros(n_weeks) for s in ("UA", "RU", "CONTESTED", "missing")} for c in STATUS_COLS}
area = gen.area_km2.values
for c in STATUS_COLS:
    for code, s in ((1, "UA"), (2, "RU"), (3, "CONTESTED"), (0, "missing")):
        nat[c][s] = ((ST[c] == code) * area[:, None]).sum(0)
front = {res: {b: np.zeros((len(CELLS[res]), n_weeks), bool) for b in BANDS} for res in (5, 6)}
dist = {res: np.full((len(CELLS[res]), n_weeks), np.nan) for res in (5, 6)}
cent = {res: shapely.points(np.c_[CELLS[res].cent_x.values, CELLS[res].cent_y.values]) for res in (5, 6)}
for t in range(n_weeks):
    sel = (RU[EI, t] & UAs[EJ, t]) | (UAs[EI, t] & RU[EJ, t])
    eg = EG[sel]
    n_edges[t] = int(sel.sum()); line_km[t] = float(shapely.length(eg).sum() / 1000)
    if len(eg) == 0:
        continue
    tree = shapely.STRtree(eg)
    for res in (5, 6):
        nn = tree.nearest(cent[res])
        d = shapely.distance(cent[res], eg[nn]) / 1000
        dist[res][:, t] = d
        for b in BANDS:
            front[res][b][:, t] = d <= b
log(f"control line km: median {np.median(line_km[n_edges>0]):.0f} (min {line_km[n_edges>0].min():.0f}, max {line_km.max():.0f}); weeks with no line {(n_edges==0).sum()}")
log(f"front cells/week res5 @15 km: median {np.median(front[5][15].sum(0)):.0f}")

clw = pd.DataFrame({"week_start": WEEKS, "iso_year": WEEKS.isocalendar().year.values, "iso_week": WEEKS.isocalendar().week.values,
                    "days_observed": days_obs, "line_km": line_km, "n_edges": n_edges,
                    "n_front15_r5": front[5][15].sum(0), "n_front10_r5": front[5][10].sum(0), "n_front25_r5": front[5][25].sum(0)})
for c in STATUS_COLS:
    suf = "" if c == "status" else c.replace("status", "")
    for s in ("UA", "RU", "CONTESTED", "missing"):
        clw[f"{s.lower()}_km2{suf}"] = nat[c][s]
    clw[f"n_ru{suf}"] = (ST[c] == 2).sum(0); clw[f"n_ua{suf}"] = (ST[c] == 1).sum(0); clw[f"n_contested{suf}"] = (ST[c] == 3).sum(0); clw[f"n_missing{suf}"] = (ST[c] == 0).sum(0)
clw.to_parquet(CTRL / "control_line_week.parquet", index=False)

for res in (5, 6):
    hx = CELLS[res]
    r = np.repeat(np.arange(len(hx)), n_weeks); cidx = np.tile(np.arange(n_weeks), len(hx))
    f = pd.DataFrame({f"h3_r{res}": hx.cell.values[r], "week_start": WEEKS.values[cidx], "dist_to_line_km": dist[res].ravel().astype("float32")})
    for b in BANDS:
        f[f"front_{b}"] = front[res][b].ravel()
    f["rear_strip"] = (dist[res].ravel() >= 50) & (dist[res].ravel() <= 90)
    f.to_parquet(CTRL / f"front_r{res}_week.parquet", index=False)
    write_meta(CTRL / f"front_r{res}_week.parquet", inputs={"control_weekly": INTERIM / "control_weekly.parquet"}, hash_inputs=False,
               counts={"cells": len(hx), "weeks": n_weeks, "front15_median_per_week": float(np.median(front[res][15].sum(0)))},
               extra={"rule": "cell centroid distance (EPSG:3035) to nearest RU|UA shared Voronoi edge of the week; front_b = dist <= b km; rear_strip 50–90 km; NaN if no line that week"})

rt = time.time() - t0
log(f"done in {rt:.0f}s")
write_meta(CTRL / "control_line_week.parquet", inputs={"control_weekly": INTERIM / "control_weekly.parquet"}, hash_inputs=False,
           counts={"weeks": n_weeks, "line_km_median": float(np.median(line_km)), "runtime_s": round(rt, 1)},
           extra={"licence": ODBL})
