"""11_panel_r5_week.py — H3 res-5 cell × ISO-week panel, 2022-02-21 -> 2025-12-31 (C1 + E), joining VIINA control
(km² by Voronoi), front geometry, FIRMS fires (all satellites), the 2012–21 S-NPP baseline and the observability
product. Contract: planning/PANEL.md (Builder D §2); PREREG §3. Also panel_r6_week.parquet (robustness 7).

Outputs:
  data/interim/analysis/panel_r5_week.parquet      full panel
  data/derived/panel/panel_r5_week.csv.gz          same columns, no geometry (cell-week, ≥7-day lag; PREREG §7)
  data/interim/analysis/panel_r6_week.parquet      control + fire + front columns at res 6
  data/derived/panel/panel_report.json             counts and sanity checks only (no fires-vs-control statistic)

Column rules (stated here, repeated in the meta):
  net_ru_gain_km2 = ru_km2(t) − ru_km2(t−1); net_fwd_k = Σ net(t+1..t+k); net_lag_k = net(t−k).
  side = RU/UA if that status holds > 50% of the cell's Ukrainian area, else mixed; NaN outside Ukraine.
  Fire side = majority `status` of the Voronoi polygon (nearest generator) containing the fire, in the fire's week.
  Big/small = FRP ≥/< the season × day/night p75 in data/derived/prereg_constants.json. Deep RU fire (H13) =
  FRP ≥ 16.33 MW and > 30 km from the RU|UA line, and either in RU-held Ukrainian territory or inside Russia.
  Phase by the ISO week's Monday: A 2022-04-04..2022-11-28 weeks, B 2022-12-05..2024-07-01, E 2024-07-08..2025-12-29.
  Baseline = mean/sd over 2012–2021 of same-ISO-week S-NPP counts in the cell (years lacking week 53 excluded).
  Cell universe: res-5 cells touching Ukraine ∪ cells of the observability product (≤50 km into Russia) ∪ Russian
  cells holding at least one deep RU fire.

Run:  ~/D3/Frontline_From_Space/.venv/bin/python -I scripts/analysis/11_panel_r5_week.py
"""
from __future__ import annotations
import sys, time, json
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, shapely, duckdb, h3
from scipy import sparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, INTERIM, DERIVED, write_meta, log, worldcover_at, WORLDCOVER_CLASSES
from _control import (CRS, CTRL, BANDS, STATUS_COLS, PANEL_START, PANEL_END, C1_START, C1_END, E_START, E_END,
                      ukraine_polygon, h3_hexes, phase_of_week, iso_week_start)

t0 = time.time()
OUTD = DERIVED / "panel"; OUTD.mkdir(parents=True, exist_ok=True)
ODBL = "Contains VIINA data (Zhukov, Yuri. 'VIINA: Violent Incident Information from News Articles on the 2022 Russian Invasion of Ukraine'), ODbL 1.0; derived settlement-control aggregates. Fires: NASA FIRMS VIIRS 375 m."
CONST = json.load(open(DERIVED / "prereg_constants.json"))
P75 = {k: v["value_MW"] for k, v in CONST["frp_p75_big_small"]["primary_full_E_hybrid_line"].items() if k.count("_") == 1}
H13_MW = CONST["h13_p90"]["primary_front_cell_p90_full_E"]["value_MW"]
log(f"big/small p75 {P75}; H13 cutoff {H13_MW} MW")
REPORT = {"constants": {"p75": P75, "h13_MW": H13_MW}}

# ---------------------------------------------------------------- control inputs
UA = ukraine_polygon(); shapely.prepare(UA)
ne0 = gpd.read_file(f"zip://{RAW / 'boundaries/naturalearth/ne_10m_admin_0_countries.zip'}!ne_10m_admin_0_countries.shp")
RUS = shapely.make_valid(ne0[ne0.ADM0_A3 == "RUS"].to_crs(CRS).geometry.union_all()); shapely.prepare(RUS)
sm = np.load(CTRL / "status_matrix.npz", allow_pickle=False)
WEEKS = pd.DatetimeIndex(sm["weeks"]); n_weeks = len(WEEKS); DAY0 = WEEKS[0]
ST = {c: sm[c] for c in STATUS_COLS}
GEN = gpd.read_parquet(CTRL / "voronoi_polys.parquet")
assert (GEN.gen_id.values == sm["gen_id"]).all()
vpoly = GEN.geometry.values
tess = gpd.read_file(RAW / "viina/gn_UA_tess.geojson", columns=["geonameid", "latitude", "longitude"], ignore_geometry=True)
tess["geonameid"] = tess.geonameid.astype("int64"); tess = tess.set_index("geonameid").loc[GEN.gen_id]
gen_pts = gpd.GeoSeries(gpd.points_from_xy(tess.longitude, tess.latitude), crs=4326).to_crs(CRS).values
GTREE = shapely.STRtree(gen_pts)
EDGES = gpd.read_parquet(CTRL / "voronoi_edges.parquet"); EI, EJ, EG = EDGES.i.values, EDGES.j.values, EDGES.geometry.values
CLW = pd.read_parquet(CTRL / "control_line_week.parquet")
S = ST["status"]; RU, UAs = (S == 2), (S == 1)
week_edges = {}
for t in range(n_weeks):
    sel = (RU[EI, t] & UAs[EJ, t]) | (UAs[EI, t] & RU[EJ, t])
    week_edges[t] = EG[sel]
panel_weeks = WEEKS[(WEEKS >= PANEL_START) & (WEEKS <= PANEL_END)]
T_PANEL = np.arange(len(panel_weeks))
log(f"weeks: control {n_weeks} ({WEEKS[0].date()}..{WEEKS[-1].date()}); panel {len(panel_weeks)} ({panel_weeks[0].date()}..{panel_weeks[-1].date()})")

# ---------------------------------------------------------------- fires
fires = pd.read_parquet(INTERIM / "fires.parquet", columns=["acq_ts_utc", "lat", "lon", "h3_r5", "h3_r6", "frp", "daynight", "satellite"])
fires["date"] = fires.acq_ts_utc.dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()
fires["week_start"] = iso_week_start(fires.date)
fires = fires[(fires.week_start >= PANEL_START) & (fires.week_start <= PANEL_END)].reset_index(drop=True)
fires["t"] = ((fires.week_start - DAY0).dt.days // 7).astype(int)
fxy = gpd.GeoSeries(gpd.points_from_xy(fires.lon, fires.lat), crs=4326).to_crs(CRS).values
fires["in_ua"] = shapely.contains(UA, fxy)
fires["in_rus"] = ~fires.in_ua & shapely.contains(RUS, fxy)
fires["season"] = np.where(fires.date.dt.month.between(5, 10), "summer", "winter")
fires["dn"] = fires.daynight.astype(str).map({"D": "day", "N": "night"})
cut = (fires.season + "_" + fires.dn).map(P75).astype(float)
fires["big"] = fires.frp >= cut
# side: Voronoi membership = nearest generator; status in the fire's week
side = np.zeros(len(fires), np.int8)
ua_idx = np.flatnonzero(fires.in_ua.values)
nn = GTREE.nearest(fxy[ua_idx])
side[ua_idx] = S[nn, fires.t.values[ua_idx]]
fires["side"] = side  # 0 none/outside UA, 1 UA, 2 RU, 3 CONTESTED
# distance to the line > 30 km, needed only for H13 candidates
cand = np.flatnonzero((fires.frp.values >= H13_MW) & (fires.in_ua.values | fires.in_rus.values))
near30 = np.zeros(len(fires), bool)
for t, idx in pd.Series(cand).groupby(fires.t.values[cand]):
    eg = week_edges[int(t)]
    if len(eg) == 0:
        continue
    pos = idx.values
    hit = shapely.STRtree(eg).query(fxy[pos], predicate="dwithin", distance=30_000)[0]
    near30[pos[np.unique(hit)]] = True
fires["deep_ru"] = (fires.frp >= H13_MW) & ~near30 & ((fires.in_ua & (fires.side == 2)) | fires.in_rus)
REPORT["fires"] = {"rows_in_panel_weeks": int(len(fires)), "in_ukraine": int(fires.in_ua.sum()), "in_russia": int(fires.in_rus.sum()),
                   "elsewhere_dropped_from_side_and_deep": int((~fires.in_ua & ~fires.in_rus).sum()),
                   "side_share_of_ukraine_fires": {k: round(float(v), 4) for k, v in (fires.loc[fires.in_ua, "side"].map({1: "UA", 2: "RU", 3: "CONTESTED", 0: "missing"}).value_counts(normalize=True)).items()},
                   "deep_ru_by_year": {int(y): int(n) for y, n in fires[fires.deep_ru].groupby(fires.date.dt.year).size().items()},
                   "deep_ru_by_year_in_ukraine": {int(y): int(n) for y, n in fires[fires.deep_ru & fires.in_ua].groupby(fires.date.dt.year).size().items()},
                   "deep_ru_by_year_in_russia": {int(y): int(n) for y, n in fires[fires.deep_ru & fires.in_rus].groupby(fires.date.dt.year).size().items()}}
log(f"fires {REPORT['fires']}")

def fire_agg(key: str) -> pd.DataFrame:
    f = fires
    d = pd.DataFrame({key: f[key].values, "week_start": f.week_start.values,
                      "fires": 1, "fires_night": (f.dn == "night").astype(int), "fires_day": (f.dn == "day").astype(int),
                      "fires_snpp": (f.satellite.astype(str) == "N").astype(int), "frp_sum": f.frp.astype(float),
                      "fires_big": f.big.astype(int), "fires_small": (~f.big).astype(int),
                      "fires_big_ua_side": (f.big & (f.side == 1)).astype(int), "fires_small_ua_side": (~f.big & (f.side == 1)).astype(int),
                      "fires_big_ru_side": (f.big & (f.side == 2)).astype(int), "fires_small_ru_side": (~f.big & (f.side == 2)).astype(int),
                      "fires_contested": (f.side == 3).astype(int), "fires_deep_ru": f.deep_ru.astype(int)})
    return d.groupby([key, "week_start"], sort=False).sum().reset_index()
FA = {5: fire_agg("h3_r5"), 6: fire_agg("h3_r6")}
FIRE_COLS = [c for c in FA[5].columns if c not in ("h3_r5", "week_start")]

# ---------------------------------------------------------------- cell universes
cells5 = gpd.read_parquet(CTRL / "cells_r5.parquet")
opp_cells = duckdb.sql(f"select distinct h3_r5 from read_parquet('{INTERIM / 'opportunity_r6_day.parquet'}')").df().h3_r5.tolist()
deep_cells = FA[5].loc[FA[5].fires_deep_ru > 0, "h3_r5"].unique().tolist()
extra = sorted((set(opp_cells) | set(deep_cells)) - set(cells5.cell))
hx = h3_hexes(extra)
hx["area_in_ua_km2"] = 0.0; hx["area_km2"] = hx.geometry.area / 1e6
c = hx.geometry.centroid; hx["cent_x"], hx["cent_y"] = c.x, c.y; hx["in_ukraine"] = False
cells5 = pd.concat([cells5, hx], ignore_index=True)
REPORT["cells_r5"] = {"touching_ukraine": int(cells5.in_ukraine.sum() + ((cells5.area_in_ua_km2 > 0) & ~cells5.in_ukraine).sum()), "total": len(cells5),
                      "added_from_observability_product": len(set(opp_cells) - set(cells5.cell[cells5.area_in_ua_km2 > 0])), "added_russia_deep_fire_cells": len(set(deep_cells) - set(opp_cells) - set(cells5.cell[cells5.area_in_ua_km2 > 0]))}
cells6 = gpd.read_parquet(CTRL / "cells_r6.parquet")
log(f"cells res5 {len(cells5)} (extra {len(extra)}); res6 {len(cells6)}")

# oblast by majority area, Kyiv city polygon
adm1 = gpd.read_file(RAW / "boundaries/geoboundaries/geoBoundaries-UKR-ADM1.geojson").to_crs(CRS)
def majority_oblast(hexes: gpd.GeoDataFrame) -> np.ndarray:
    tr = shapely.STRtree(adm1.geometry.values)
    ci, ai = tr.query(hexes.geometry.values, predicate="intersects")
    a = shapely.area(shapely.intersection(hexes.geometry.values[ci], adm1.geometry.values[ai]))
    df = pd.DataFrame({"ci": ci, "iso": adm1.shapeISO.values[ai], "a": a}).sort_values("a", ascending=False).drop_duplicates("ci")
    out = np.full(len(hexes), None, dtype=object); out[df.ci.values] = df.iso.values
    return out
cells5["oblast_iso"] = majority_oblast(cells5)

# landcover mode: WorldCover class at res-7 child centroids (49 per cell)
def landcover_mode(cell_ids) -> list:
    kids = [(c, k) for c in cell_ids for k in h3.cell_to_children(c, 7)]
    ll = np.array([h3.cell_to_latlng(k) for _, k in kids])
    cls = np.array(worldcover_at(ll[:, 0], ll[:, 1]))
    df = pd.DataFrame({"cell": [c for c, _ in kids], "cls": cls})
    df = df[df.cls != 0]
    mode = df.groupby("cell").cls.agg(lambda s: s.value_counts().idxmax())
    return pd.Series(cell_ids).map(mode).map(WORLDCOVER_CLASSES).fillna("nodata").tolist()
cells5["landcover_mode"] = landcover_mode(cells5.cell.tolist())
log(f"landcover modes: {cells5.landcover_mode.value_counts().to_dict()}")

# ---------------------------------------------------------------- control per cell × week
def control_block(hexes: gpd.GeoDataFrame) -> dict:
    tree = shapely.STRtree(hexes.geometry.values)
    si, ci = tree.query(vpoly, predicate="intersects")
    a = shapely.area(shapely.intersection(vpoly[si], hexes.geometry.values[ci])) / 1e6
    A = sparse.csr_matrix((a, (ci, si)), shape=(len(hexes), len(vpoly)))
    out = {}
    for c in STATUS_COLS:
        suf = "" if c == "status" else c.replace("status", "")
        ru = np.asarray(A @ (ST[c] == 2).astype(float)); out[f"ru_km2{suf}"] = ru
        net = np.full_like(ru, np.nan); net[:, 1:] = ru[:, 1:] - ru[:, :-1]; out[f"net_ru_gain_km2{suf}"] = net
        if c == "status":
            out["ua_km2"] = np.asarray(A @ (ST[c] == 1).astype(float)); out["contested_km2"] = np.asarray(A @ (ST[c] == 3).astype(float))
            out["missing_km2"] = np.asarray(A @ (ST[c] == 0).astype(float))
            for k in range(1, 5):
                fwd = np.full_like(ru, np.nan); fwd[:, :-k] = ru[:, k:] - ru[:, :-k]; out[f"net_fwd_{k}"] = fwd
                lag = np.full_like(ru, np.nan); lag[:, k:] = net[:, :-k]; out[f"net_lag_{k}"] = lag
    return out

def assemble(hexes: gpd.GeoDataFrame, res: int, full: bool) -> pd.DataFrame:
    key = f"h3_r{res}"
    cb = control_block(hexes)
    tsel = np.array([int((w - DAY0).days // 7) for w in panel_weeks])
    n = len(hexes); r = np.repeat(np.arange(n), len(tsel)); t = np.tile(tsel, n)
    df = pd.DataFrame({key: hexes.cell.values[r], "week_start": WEEKS.values[t]})
    for k, M in cb.items():
        df[k] = M[r, t].astype("float32")
    fr = pd.read_parquet(CTRL / f"front_r{res}_week.parquet")
    df = df.merge(fr, on=[key, "week_start"], how="left")
    for b in BANDS:
        df[f"front_{b}"] = df[f"front_{b}"].fillna(False).astype(bool)
    df["rear_strip"] = df.rear_strip.fillna(False).astype(bool)
    # distance for extra (non-Ukraine) cells not in the front table: same rule, computed here
    known = set(fr[key].unique())
    extra_cells = [c for c in hexes.cell if c not in known]
    if extra_cells:
        hx = hexes.set_index("cell").loc[extra_cells]
        pts = shapely.points(np.c_[hx.cent_x.values, hx.cent_y.values])
        D = np.full((len(extra_cells), len(tsel)), np.nan, dtype="float32")
        for j, ti in enumerate(tsel):
            eg = week_edges[int(ti)]
            if len(eg) == 0: continue
            nn = shapely.STRtree(eg).nearest(pts); D[:, j] = shapely.distance(pts, eg[nn]) / 1000
        ex = pd.DataFrame({key: np.repeat(extra_cells, len(tsel)), "week_start": np.tile(WEEKS.values[tsel], len(extra_cells)), "d": D.ravel()})
        df = df.merge(ex, on=[key, "week_start"], how="left")
        m = df.d.notna().values
        df.loc[m, "dist_to_line_km"] = df.loc[m, "d"].values
        df.loc[m, "rear_strip"] = (df.loc[m, "d"] >= 50) & (df.loc[m, "d"] <= 90)
        for b in BANDS:
            df.loc[m, f"front_{b}"] = df.loc[m, "d"] <= b
        df = df.drop(columns="d")
    area_ua = hexes.set_index("cell").area_in_ua_km2.reindex(df[key]).values
    side = np.where(df.ru_km2 > 0.5 * area_ua, "RU", np.where(df.ua_km2 > 0.5 * area_ua, "UA", "mixed"))
    df["side"] = pd.Categorical(np.where(area_ua > 0, side, None), categories=["UA", "RU", "mixed"])
    df["in_ukraine"] = hexes.set_index("cell").in_ukraine.reindex(df[key]).values
    df["area_in_ua_km2"] = area_ua.astype("float32")
    df = df.merge(FA[res], on=[key, "week_start"], how="left")
    df[FIRE_COLS] = df[FIRE_COLS].fillna(0)
    for c in FIRE_COLS:
        df[c] = df[c].astype("float32" if c == "frp_sum" else "int32")
    iso = pd.DatetimeIndex(df.week_start).isocalendar()
    df["iso_year"] = iso.year.values.astype("int16"); df["iso_week"] = iso.week.values.astype("int8")
    df["season"] = np.where(pd.DatetimeIndex(df.week_start).month.isin(range(5, 11)), "summer", "winter")
    df["phase"] = phase_of_week(df.week_start).values
    df["c1"] = df.phase.isin(["A", "B"]); df["e"] = df.phase.eq("E")
    return df

panel5 = assemble(cells5, 5, True)
panel5["oblast_iso"] = cells5.set_index("cell").oblast_iso.reindex(panel5.h3_r5).values
panel5["landcover_mode"] = cells5.set_index("cell").landcover_mode.reindex(panel5.h3_r5).values
log(f"panel5 control+fires {panel5.shape}")

# ---------------------------------------------------------------- baseline 2012–2021 (S-NPP)
bl = duckdb.sql(f"""
    with f as (select h3_r5, (acq_ts_utc at time zone 'UTC')::date as d from read_parquet('{INTERIM / 'fires_baseline.parquet'}') where satellite = 'N'),
    c as (select h3_r5, isoyear(d) as iy, week(d) as iw, count(*) as n from f group by all),
    yrs as (select distinct isoyear(d) as iy, week(d) as iw from f),
    cells as (select distinct h3_r5 from c),
    grid as (select h3_r5, iy, iw from cells cross join yrs)
    select g.h3_r5, g.iw as iso_week, avg(coalesce(n, 0)) as base_fires_mean, stddev_samp(coalesce(n, 0)) as base_fires_sd, count(*) as base_years
    from grid g left join c using (h3_r5, iy, iw) group by all
""").df()
REPORT["baseline"] = {"cells_with_any_baseline_fire": int(bl.h3_r5.nunique()), "iso_weeks": int(bl.iso_week.nunique()), "years_per_week": {int(k): int(v) for k, v in bl.groupby("iso_week").base_years.first().items() if v != 10}}
panel5 = panel5.merge(bl[["h3_r5", "iso_week", "base_fires_mean", "base_fires_sd"]], on=["h3_r5", "iso_week"], how="left")
panel5["base_fires_mean"] = panel5.base_fires_mean.fillna(0).astype("float32"); panel5["base_fires_sd"] = panel5.base_fires_sd.fillna(0).astype("float32")

# ---------------------------------------------------------------- observability (res-6 cell-days -> res-5 week)
ob = duckdb.sql(f"""
    select h3_r5, date_trunc('week', date)::date as week_start,
           sum(opportunity) as opportunity, sum(n_overpasses) as n_overpasses, sum(n_clear_overpasses) as n_clear,
           avg(case when opportunity = 0 then 1.0 else 0.0 end) as share_zero_days,
           avg(case when n_tcc_known > 0 then min_tcc end) as min_tcc_mean,
           avg(snow_day) as snow_share,
           avg(hours_since_prev_overpass_mean) as hours_since_prev_mean,
           sum(n_night)::double / nullif(sum(n_night) + sum(n_day), 0) as share_night,
           count(*) as n_cell_days_r6
    from read_parquet('{INTERIM / 'opportunity_r6_day.parquet'}') group by all
""").df()
ob["week_start"] = pd.to_datetime(ob.week_start)
panel5 = panel5.merge(ob, on=["h3_r5", "week_start"], how="left")
for c in ("opportunity", "n_overpasses", "n_clear", "n_cell_days_r6"):
    panel5[c] = panel5[c].astype("Int32")
REPORT["observability"] = {"cell_weeks_with_observability": int(panel5.opportunity.notna().sum()), "cell_weeks_without": int(panel5.opportunity.isna().sum())}

# ---------------------------------------------------------------- write res 5
ORDER = ["h3_r5", "week_start", "iso_year", "iso_week", "season", "phase", "c1", "e", "in_ukraine", "oblast_iso", "area_in_ua_km2",
         "ru_km2", "ua_km2", "contested_km2", "missing_km2", "net_ru_gain_km2", "net_fwd_1", "net_fwd_2", "net_fwd_3", "net_fwd_4",
         "net_lag_1", "net_lag_2", "net_lag_3", "net_lag_4",
         "ru_km2_dsm", "net_ru_gain_km2_dsm", "ru_km2_isw", "net_ru_gain_km2_isw", "ru_km2_wiki", "net_ru_gain_km2_wiki",
         "front_10", "front_15", "front_25", "dist_to_line_km", "side", "rear_strip"] + FIRE_COLS + \
        ["base_fires_mean", "base_fires_sd", "opportunity", "n_overpasses", "n_clear", "share_zero_days", "n_cell_days_r6",
         "min_tcc_mean", "snow_share", "hours_since_prev_mean", "share_night", "landcover_mode"]
panel5 = panel5[ORDER].sort_values(["h3_r5", "week_start"]).reset_index(drop=True)
assert not panel5.duplicated(["h3_r5", "week_start"]).any()
out5 = INTERIM / "panel_r5_week.parquet"
panel5.to_parquet(out5, index=False)
panel5.to_csv(OUTD / "panel_r5_week.csv.gz", index=False, compression="gzip", float_format="%.4f")

# ---------------------------------------------------------------- res 6 (control + fires + front)
panel6 = assemble(cells6, 6, False)
keep6 = ["h3_r6", "week_start", "iso_year", "iso_week", "season", "phase", "c1", "e", "in_ukraine", "area_in_ua_km2",
         "ru_km2", "ua_km2", "contested_km2", "net_ru_gain_km2", "net_fwd_1", "net_fwd_2", "net_fwd_3", "net_fwd_4", "net_lag_1", "net_lag_2", "net_lag_3", "net_lag_4",
         "ru_km2_dsm", "net_ru_gain_km2_dsm", "ru_km2_isw", "net_ru_gain_km2_isw", "ru_km2_wiki", "net_ru_gain_km2_wiki",
         "front_10", "front_15", "front_25", "dist_to_line_km", "side", "rear_strip"] + FIRE_COLS
panel6 = panel6[keep6].sort_values(["h3_r6", "week_start"]).reset_index(drop=True)
panel6.to_parquet(INTERIM / "panel_r6_week.parquet", index=False)
log(f"panel6 {panel6.shape}")

# ---------------------------------------------------------------- report (counts and sanity only)
p = panel5
REPORT["panel_r5"] = {"rows": len(p), "cells": int(p.h3_r5.nunique()), "weeks": int(p.week_start.nunique()), "columns": len(p.columns),
                      "c1_cell_weeks": int(p.c1.sum()), "e_cell_weeks": int(p.e.sum())}
REPORT["panel_r6"] = {"rows": len(panel6), "cells": int(panel6.h3_r6.nunique())}
f15 = p[p.front_15].groupby("week_start").size()
REPORT["front15_cells_per_week_median_by_year"] = {int(y): float(v) for y, v in f15.groupby(f15.index.year).median().items()}
REPORT["front_cells_per_week_median_by_band"] = {b: float(p[p[f"front_{b}"]].groupby("week_start").size().median()) for b in BANDS}
nat = CLW.set_index("week_start")
def at(d):
    w = iso_week_start(pd.Series([pd.Timestamp(d)])).iloc[0]
    return {"week_start": str(w.date()), "ru_km2": round(float(nat.loc[w, "ru_km2"]), 0), "ru_km2_dsm": round(float(nat.loc[w, "ru_km2_dsm"]), 0), "ru_km2_isw": round(float(nat.loc[w, "ru_km2_isw"]), 0), "ru_km2_wiki": round(float(nat.loc[w, "ru_km2_wiki"]), 0),
            "contested_km2": round(float(nat.loc[w, "contested_km2"]), 0), "missing_km2_isw": round(float(nat.loc[w, "missing_km2_isw"]), 0)}
REPORT["national_ru_km2"] = {d: at(d) for d in ("2022-02-21", "2022-03-21", "2022-04-03", "2022-11-30", "2024-07-07", "2025-12-31")}
REPORT["national_ru_km2"]["peak"] = {"week_start": str(nat.ru_km2.idxmax().date()), "ru_km2": round(float(nat.ru_km2.max()), 0)}
# Economist national series (ISW-derived), 2022–23 sanity check (PREREG robustness 5)
ec = pd.read_csv(RAW / "economist/keep/output-data/areas_of_control_daily_summary.csv")
ec = ec[ec.type == "Territory assessed as Russia-controlled"].copy(); ec["date"] = pd.to_datetime(ec.date)
ec["week_start"] = iso_week_start(ec.date)
ecw = ec.groupby("week_start").area_in_square_km.mean()
cmp = pd.DataFrame({"viina_ru_km2": nat.ru_km2, "economist_isw_ru_km2": ecw}).dropna()
cmp["diff_km2"] = cmp.viina_ru_km2 - cmp.economist_isw_ru_km2
REPORT["economist_check_2022_23"] = {"weeks_compared": len(cmp), "range": [str(cmp.index.min().date()), str(cmp.index.max().date())],
                                     "corr_levels": round(float(cmp.viina_ru_km2.corr(cmp.economist_isw_ru_km2)), 4),
                                     "corr_weekly_changes": round(float(cmp.viina_ru_km2.diff().corr(cmp.economist_isw_ru_km2.diff())), 4),
                                     "median_diff_km2_viina_minus_economist": round(float(cmp.diff_km2.median()), 0),
                                     "mean_abs_diff_km2": round(float(cmp.diff_km2.abs().mean()), 0),
                                     "at": {str(d.date()): {"viina": round(float(r.viina_ru_km2)), "economist": round(float(r.economist_isw_ru_km2))} for d, r in cmp.iloc[[0, 4, 8, 20, 40, 60, 80, -1]].iterrows()}}
cmp.reset_index().to_csv(OUTD / "national_viina_vs_economist_week.csv", index=False, float_format="%.0f")
c1f = p[p.c1 & p.front_15]
REPORT["fires_per_front15_cell_week_by_phase"] = {ph: {"cell_weeks": int(len(g)), "fires_mean": round(float(g.fires.mean()), 2), "fires_median": float(g.fires.median()), "fires_total": int(g.fires.sum()),
                                                        "share_cell_weeks_zero_fires": round(float((g.fires == 0).mean()), 4)} for ph, g in p[p.front_15].groupby("phase")}
REPORT["c1_front15_net"] = {"cell_weeks": int(len(c1f)), "share_net_nonzero": round(float((c1f.net_ru_gain_km2 != 0).mean()), 4),
                            "share_net_fwd4_nonzero": round(float((c1f.net_fwd_4 != 0).mean()), 4),
                            "mean_abs_net_fwd_4_km2": round(float(c1f.net_fwd_4.abs().mean()), 3), "share_side": {k: round(float(v), 4) for k, v in c1f.side.value_counts(normalize=True).items()}}
REPORT["c1_front15_fire_side_shares"] = {k: round(float(c1f[k].sum() / max(1, c1f.fires.sum())), 4) for k in ("fires_big_ua_side", "fires_small_ua_side", "fires_big_ru_side", "fires_small_ru_side", "fires_contested")}
REPORT["all_c1_fires_in_ukraine_by_side"] = {k: int(v) for k, v in fires[fires.in_ua & (fires.week_start >= "2022-04-04") & (fires.week_start <= "2024-07-01")].side.map({1: "UA", 2: "RU", 3: "CONTESTED", 0: "missing"}).value_counts().items()}
REPORT["missing_status_km2_max_by_source"] = {c: round(float(nat[f"missing_km2{'' if c=='status' else c.replace('status','')}"].max())) for c in STATUS_COLS}
rt = time.time() - t0
REPORT["runtime_s"] = round(rt, 1)
json.dump(REPORT, open(OUTD / "panel_report.json", "w"), indent=2, default=str)
inputs = {"control_weekly": INTERIM / "control_weekly.parquet", "fires": INTERIM / "fires.parquet", "fires_baseline": INTERIM / "fires_baseline.parquet",
          "opportunity_r6_day": INTERIM / "opportunity_r6_day.parquet", "prereg_constants": DERIVED / "prereg_constants.json", "adm1": RAW / "boundaries/geoboundaries/geoBoundaries-UKR-ADM1.geojson"}
extra = {"columns": __doc__.split("Column rules")[1].split("Run:")[0].strip(), "licence": ODBL, "publication_unit": "res-5 cell × ISO week (PREREG §7, DESIGN D16)", "report": OUTD.name + "/panel_report.json"}
write_meta(out5, inputs=inputs, counts=REPORT["panel_r5"], extra=extra)
write_meta(OUTD / "panel_r5_week.csv.gz", inputs=inputs, counts=REPORT["panel_r5"], extra=extra, hash_inputs=False)
write_meta(INTERIM / "panel_r6_week.parquet", inputs=inputs, counts=REPORT["panel_r6"], extra={"licence": ODBL, "note": "robustness 7: control + fire + front columns only"}, hash_inputs=False)
log(f"done in {rt:.0f}s")
print(json.dumps(REPORT, indent=1, default=str))
