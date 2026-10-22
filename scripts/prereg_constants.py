"""Pre-tag constants required by PREREG.md §3 (SESOI on VIINA 2025; FRP big/small cutoffs; H13 cutoff).

Allowed inputs only (PREREG §2): E-period S-NPP FIRMS (2024-07-08 -> 2025-12-31), VIINA 2025,
DeepState mirror (E only, used for the 2024 half of E because VIINA 2024 is not on disk and
mostly falls in C1). Nothing is downloaded. FIRMS rows dated before 2024-07-08 are dropped while
the 2024 CSV is being read, before any column other than acq_date is used. H14 (baseline FRP
floors) is a hypothesis and is deliberately NOT computed here.

Run (needs geopandas/shapely>=2.1/scipy; the project .venv lacks them):
  ~/D3/Conflict_Data_Feasibility/frontline/.venv/bin/python -I scripts/prereg_constants.py

Grid: uses h3-py (res 5) if importable; otherwise a regular hexagon grid in EPSG:3035 whose cell
area equals the H3 res-5 average (252.903 km2). The output JSON records which grid was used.
"""
import json, os, sys, glob, zipfile, datetime as dt
import numpy as np, pandas as pd, geopandas as gpd, shapely
from shapely.geometry import Polygon
from scipy import sparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FEAS = os.path.expanduser("~/D3/Conflict_Data_Feasibility/frontline/data/raw")
P = dict(
    viina=os.path.join(ROOT, "data/raw/viina/control_latest_2025.zip"),
    tess=os.path.join(ROOT, "data/raw/viina/gn_UA_tess.geojson"),
    ne0=os.path.join(ROOT, "data/raw/boundaries/naturalearth/ne_10m_admin_0_countries.zip"),
    ne1=os.path.join(ROOT, "data/raw/boundaries/naturalearth/ne_10m_admin_1_states_provinces.zip"),
    firms=[os.path.join(FEAS, "firms/viirs-snpp_2024_Ukraine.csv"), os.path.join(FEAS, "firms/viirs-snpp_2025_Ukraine.csv")],
    deepstate=os.path.join(FEAS, "deepstate/daily"),
    out=os.path.join(ROOT, "data/derived/prereg_constants.json"),
)
CRS = 3035
E_START, E_END = pd.Timestamp("2024-07-08"), pd.Timestamp("2025-12-31")
C1_START, C1_END = pd.Timestamp("2022-04-03"), pd.Timestamp("2024-07-07")
VIINA_FROM_WEEK = pd.Timestamp("2024-12-30")  # ISO week containing 2025-01-01
FRONT_KM, BANDS = 15, (10, 15, 25)
H3_RES5_AVG_KM2 = 252.903
log = []
def say(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); log.append(s)
def iso_week(d):
    return d.dt.to_period("W-SUN").dt.start_time

# ---------------------------------------------------------------- Ukraine polygon (NE 10m + Crimea)
ne0 = gpd.read_file(f"zip://{P['ne0']}!ne_10m_admin_0_countries.shp")
ne1 = gpd.read_file(f"zip://{P['ne1']}")
ua0 = ne0[ne0.ADMIN == "Ukraine"].to_crs(CRS).geometry.union_all()
crimea = ne1[ne1.name.isin(["Crimea", "Sevastopol"])].to_crs(CRS).geometry.union_all()
UA = shapely.make_valid(ua0.union(crimea))
shapely.prepare(UA)
say(f"Ukraine polygon (NE 10m admin-0 Ukraine + NE admin-1 Crimea/Sevastopol): {UA.area/1e6:,.0f} km2")

# ---------------------------------------------------------------- grid
try:
    import h3  # noqa
    GRID = "h3_res5"
except ImportError:
    GRID = "hex_equal_area_3035"

if GRID == "h3_res5":
    ua_ll = gpd.GeoSeries([UA], crs=CRS).to_crs(4326).iloc[0]
    ids = sorted(h3.geo_to_cells(ua_ll.buffer(0.2), 5))
    polys = [Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(c)]) for c in ids]
    hexes = gpd.GeoDataFrame({"cell": ids}, geometry=polys, crs=4326).to_crs(CRS)
    def cell_of_points(x, y, lon, lat):
        return np.array([h3.latlng_to_cell(a, b, 5) for a, b in zip(lat, lon)])
else:
    S = np.sqrt(2 * H3_RES5_AVG_KM2 * 1e6 / (3 * np.sqrt(3)))  # edge = circumradius (m)
    def axial_round(x, y):
        q = (np.sqrt(3) / 3 * x - y / 3) / S
        r = (2 / 3 * y) / S
        cx, cz = q, r; cy = -cx - cz
        rx, ry, rz = np.round(cx), np.round(cy), np.round(cz)
        dx, dy, dz = abs(rx - cx), abs(ry - cy), abs(rz - cz)
        fx = (dx > dy) & (dx > dz); fy = ~fx & (dy > dz)
        rx = np.where(fx, -ry - rz, rx); ry = np.where(fy, -rx - rz, ry)
        rz = np.where(~fx & ~fy, -rx - ry, rz)
        return rx.astype(int), rz.astype(int)
    def cell_of_points(x, y, lon=None, lat=None):
        q, r = axial_round(np.asarray(x), np.asarray(y))
        return np.char.add(np.char.add(q.astype(str), "_"), r.astype(str))
    minx, miny, maxx, maxy = UA.bounds
    gx, gy = np.meshgrid(np.arange(minx - 3 * S, maxx + 3 * S, S), np.arange(miny - 3 * S, maxy + 3 * S, S))
    ids = np.unique(cell_of_points(gx.ravel(), gy.ravel()))
    polys = []
    for c in ids:
        q, r = map(int, c.split("_"))
        cx, cy = S * np.sqrt(3) * (q + r / 2), S * 1.5 * r
        polys.append(Polygon([(cx + S * np.cos(np.radians(30 + 60 * k)), cy + S * np.sin(np.radians(30 + 60 * k))) for k in range(6)]))
    hexes = gpd.GeoDataFrame({"cell": ids}, geometry=polys, crs=CRS)
hexes = hexes[hexes.intersects(UA)].reset_index(drop=True)
hexes["area_in_ua_km2"] = hexes.geometry.intersection(UA).area / 1e6
CELL_IDX = {c: i for i, c in enumerate(hexes.cell)}
cent = hexes.geometry.centroid.values
say(f"Grid {GRID}: {len(hexes)} cells touching Ukraine; full-cell area {hexes.area.mean()/1e6:.1f} km2")

# ---------------------------------------------------------------- settlement Voronoi
tess = gpd.read_file(P["tess"], columns=["geonameid", "latitude", "longitude"], ignore_geometry=True)
tess["geonameid"] = tess.geonameid.astype("int64")
pts = gpd.GeoSeries(gpd.points_from_xy(tess.longitude, tess.latitude), crs=4326).to_crs(CRS)
tess["x"], tess["y"] = pts.x.round(0), pts.y.round(0)
tess = tess.sort_values("geonameid")
dup = tess.duplicated(["x", "y"])
gen = tess[~dup].reset_index(drop=True)
alias = tess.merge(gen[["x", "y", "geonameid"]].rename(columns={"geonameid": "gen_id"}), on=["x", "y"])
say(f"Settlements {len(tess)}; unique generator points {len(gen)} ({dup.sum()} share coordinates with another settlement -> merged)")
mp = shapely.MultiPoint(np.c_[gen.x, gen.y])
vor = shapely.voronoi_polygons(mp, extend_to=UA.envelope.buffer(200_000), ordered=True)
vpoly = np.array(shapely.get_parts(vor))
assert len(vpoly) == len(gen)
assert shapely.contains(vpoly, shapely.points(np.c_[gen.x, gen.y])).all()
vpoly = shapely.intersection(vpoly, UA)
gen["area_km2"] = shapely.area(vpoly) / 1e6
say(f"Voronoi clipped to Ukraine: total {gen.area_km2.sum():,.0f} km2; {int((gen.area_km2 == 0).sum())} empty after clip")

# settlement x cell area matrix
tree = shapely.STRtree(hexes.geometry.values)
si, ci = tree.query(vpoly, predicate="intersects")
a = shapely.area(shapely.intersection(vpoly[si], hexes.geometry.values[ci])) / 1e6
A = sparse.csr_matrix((a, (ci, si)), shape=(len(hexes), len(gen)))  # cells x settlements, km2

# Voronoi adjacency and shared edges
vtree = shapely.STRtree(vpoly)
i, j = vtree.query(vpoly, predicate="intersects")
k = i < j; i, j = i[k], j[k]
edge = shapely.intersection(shapely.boundary(vpoly[i]), shapely.boundary(vpoly[j]))
k = shapely.length(edge) > 1.0  # shared edge, not a corner touch
EI, EJ, EG = i[k], j[k], edge[k]
say(f"Voronoi neighbour pairs sharing an edge: {len(EI):,}")

# ---------------------------------------------------------------- VIINA weekly modal status
with zipfile.ZipFile(P["viina"]) as z:
    v = pd.read_csv(z.open("control_latest_2025.csv"), usecols=["geonameid", "date", "status"],
                    dtype={"geonameid": "int64", "status": "category"})
codes = sorted(v.status.dropna().unique().tolist())
v["date"] = pd.to_datetime(v.date.astype(str), format="%Y%m%d")
assert v.date.min() >= pd.Timestamp("2025-01-01") and v.date.max() <= pd.Timestamp("2025-12-31")
say(f"VIINA 2025 rows {len(v):,}; settlements {v.geonameid.nunique():,}; dates {v.date.min().date()}..{v.date.max().date()}; "
    f"status codes {dict(v.status.value_counts())}")
v = v.merge(alias[["geonameid", "gen_id"]], on="geonameid", how="inner")
v["week"] = iso_week(v.date)
days_per_week = v.groupby("week").date.nunique()
g = v.groupby(["gen_id", "week", "status"], observed=True).agg(n=("date", "size"), last=("date", "max")).reset_index()
g = g.sort_values(["gen_id", "week", "n", "last"], ascending=[True, True, False, False])
first = g.drop_duplicates(["gen_id", "week"])
second = g[g.duplicated(["gen_id", "week"])].drop_duplicates(["gen_id", "week"])
ties = first.merge(second, on=["gen_id", "week"], suffixes=("", "_2"))
n_ties = int((ties.n == ties.n_2).sum())
WEEKS = sorted(first.week.unique())
widx = {w: t for t, w in enumerate(WEEKS)}
gidx = pd.Series(range(len(gen)), index=gen.geonameid)
row = gidx.loc[first.gen_id].values; col = first.week.map(widx).values
ST = np.full((len(gen), len(WEEKS)), "", dtype=object)
ST[row, col] = first.status.astype(str).values
missing = int((ST == "").sum())
say(f"Weekly modal status: {len(WEEKS)} ISO weeks ({WEEKS[0].date()}..{WEEKS[-1].date()}, days/week first {days_per_week.iloc[0]} last {days_per_week.iloc[-1]}); "
    f"settlement-weeks {first.shape[0]:,}; ties {n_ties} (broken by status on the latest day); missing {missing}; "
    f"merged generators with conflicting status in some week: {int((v.groupby(['gen_id','date']).status.nunique() > 1).groupby(level=0).any().sum())}")
RU = (ST == "RU"); UAs = (ST == "UA"); CT = (ST == "CONTESTED")
say(f"Settlement-weeks RU {RU.sum():,}, UA {UAs.sum():,}, CONTESTED {CT.sum():,}")

def front_cells_from_lines(geoms, km):
    if len(geoms) == 0:
        return np.zeros(len(hexes), bool)
    t = shapely.STRtree(geoms)
    hit = np.unique(t.query(cent, predicate="dwithin", distance=km * 1000)[0])
    m = np.zeros(len(hexes), bool); m[hit] = True
    return m

# control line per week = RU|UA shared Voronoi edges
FRONT = {b: np.zeros((len(hexes), len(WEEKS)), bool) for b in BANDS}
line_km, line_edges = [], []
for t in range(len(WEEKS)):
    sel = (RU[EI, t] & UAs[EJ, t]) | (UAs[EI, t] & RU[EJ, t])
    eg = EG[sel]
    line_km.append(float(shapely.length(eg).sum() / 1000)); line_edges.append(int(sel.sum()))
    for b in BANDS:
        FRONT[b][:, t] = front_cells_from_lines(eg, b)
say(f"Control line length km: median {np.median(line_km):.0f} (min {min(line_km):.0f}, max {max(line_km):.0f}); "
    f"front cells/week at 15 km: median {np.median(FRONT[15].sum(0)):.0f}")

# ---------------------------------------------------------------- SESOI
RUarea = np.asarray(A @ RU.astype(float))                 # cells x weeks, km2 RU-held
RUarea_c = np.asarray(A @ (RU + 0.5 * CT).astype(float))  # contested counted as half
def sesoi(area, band, horizon=4, cell_mask=None, full_weeks_only=False):
    d = area[:, horizon:] - area[:, :-horizon]            # change from t to t+h (= sum of net_{t+1..t+h})
    f = FRONT[band][:, :-horizon].copy()
    if cell_mask is not None:
        f &= cell_mask[:, None]
    if full_weeks_only:  # drop windows touching the partial first/last ISO weeks
        ok = np.array([days_per_week.loc[WEEKS[t]] == 7 and days_per_week.loc[WEEKS[t + horizon]] == 7 for t in range(f.shape[1])])
        f &= ok[None, :]
    x = d[f]
    return dict(sesoi_km2=float(np.mean(np.abs(x)) / 2), mean_abs_change_km2=float(np.mean(np.abs(x))),
                mean_signed_change_km2=float(np.mean(x)), median_abs_change_km2=float(np.median(np.abs(x))),
                share_zero=float(np.mean(x == 0)), n_cell_weeks=int(x.size),
                n_cells=int(f.any(1).sum()), n_origin_weeks=int(f.shape[1]))
S_main = sesoi(RUarea, 15)
S_alt = {f"band_{b}km": sesoi(RUarea, b) for b in BANDS if b != 15}
S_alt["contested_as_half_15km"] = sesoi(RUarea_c, 15)
S_alt["horizon_1wk_15km"] = sesoi(RUarea, 15, 1)
S_alt["cells_ge50pct_in_ukraine_15km"] = sesoi(RUarea, 15, cell_mask=(hexes.area_in_ua_km2.values >= 0.5 * hexes.area.values / 1e6))
S_alt["full_iso_weeks_only_15km"] = sesoi(RUarea, 15, full_weeks_only=True)
say(f"SESOI (VIINA 2025, 15 km): {S_main['sesoi_km2']:.3f} km2 (mean |4-wk change| {S_main['mean_abs_change_km2']:.3f}; "
    f"n = {S_main['n_cell_weeks']} cell-weeks, {S_main['n_cells']} cells)")
for kk, vv in S_alt.items():
    say(f"  {kk}: {vv['sesoi_km2']:.3f} (n {vv['n_cell_weeks']})")
nat = RUarea.sum(0)
say(f"National RU-held area (Voronoi, km2): {nat[0]:,.0f} -> {nat[-1]:,.0f} (net {nat[-1]-nat[0]:+,.0f})")

# ---------------------------------------------------------------- DeepState line for the 2024 half of E
ds_files = sorted(glob.glob(os.path.join(P["deepstate"], "deepstatemap_data_*.geojson")))
ds_dates = pd.to_datetime([os.path.basename(f)[18:26] for f in ds_files])
keep = (ds_dates >= E_START) & (ds_dates <= E_END)
ds = pd.DataFrame({"f": np.array(ds_files)[keep], "date": ds_dates[keep]})
ds["week"] = iso_week(ds.date)
ds_last = ds.sort_values("date").groupby("week").tail(1).set_index("week").sort_index()
UA_inner = UA.buffer(-3000)
DS_FRONT, DS_OCC = {}, {}
for w, r in ds_last.iterrows():
    occ = shapely.make_valid(gpd.read_file(r.f).to_crs(CRS).geometry.union_all())
    b = occ.boundary.intersection(UA_inner)
    parts = [p for p in shapely.get_parts(b) if p.length > 5000]
    DS_FRONT[w] = front_cells_from_lines(np.array(parts), FRONT_KM)
    DS_OCC[w] = occ
say(f"DeepState weekly snapshots in E: {len(ds_last)} ({ds_last.index[0].date()}..{ds_last.index[-1].date()})")

# ---------------------------------------------------------------- FIRMS E
cols = ["latitude", "longitude", "acq_date", "satellite", "confidence", "frp", "daynight", "type"]
parts = []
for f in P["firms"]:
    for ch in pd.read_csv(f, usecols=cols, chunksize=200_000):
        ch["acq_date"] = pd.to_datetime(ch.acq_date)
        ch = ch[(ch.acq_date >= E_START) & (ch.acq_date <= E_END)]  # drop C1 rows first, before anything else
        parts.append(ch)
fr = pd.concat(parts, ignore_index=True)
assert fr.acq_date.min() >= E_START and not ((fr.acq_date >= C1_START) & (fr.acq_date <= C1_END)).any()
n_raw = len(fr)
fr = fr[fr.confidence.isin(["n", "h"])].copy()
say(f"FIRMS E rows {n_raw:,}; confidence n/h {len(fr):,}; satellites {fr.satellite.unique().tolist()}; "
    f"dates {fr.acq_date.min().date()}..{fr.acq_date.max().date()}")
xy = gpd.GeoSeries(gpd.points_from_xy(fr.longitude, fr.latitude), crs=4326).to_crs(CRS)
fr["cell"] = cell_of_points(xy.x.values, xy.y.values, fr.longitude.values, fr.latitude.values)
fr["ci"] = fr.cell.map(CELL_IDX)
fr["week"] = iso_week(fr.acq_date)
fr["season"] = np.where(fr.acq_date.dt.month.between(5, 10), "summer", "winter")
fr["dn"] = fr.daynight.map({"D": "day", "N": "night"})
fr = fr[fr.ci.notna()].copy(); fr["ci"] = fr.ci.astype(int)

def flag(frontfun):
    out = np.zeros(len(fr), bool)
    for w, idx in fr.groupby("week").groups.items():
        m = frontfun(w)
        if m is not None:
            out[fr.index.get_indexer(idx)] = m[fr.loc[idx, "ci"].values]
    return out
viina_front = lambda w: FRONT[15][:, widx[w]] if w in widx else None
ds_front = lambda w: DS_FRONT.get(w)
fr["front_viina"] = flag(viina_front)
fr["front_ds"] = flag(ds_front)
fr["front_hybrid"] = np.where(fr.week >= VIINA_FROM_WEEK, fr.front_viina, fr.front_ds)

def pct(sel, q):
    x = fr.loc[sel, "frp"].values
    return dict(value_MW=round(float(np.percentile(x, q)), 3), n=int(x.size))
def frp_table(colname, period_mask):
    base = fr[colname] & period_mask
    out = {}
    for s in ("summer", "winter"):
        for d in ("day", "night"):
            out[f"{s}_{d}"] = pct(base & (fr.season == s) & (fr.dn == d), 75)
    out["pooled_p75"] = pct(base, 75)
    out["pooled_p90"] = pct(base, 90)
    return out
allE = pd.Series(True, index=fr.index)
in2025 = fr.week >= VIINA_FROM_WEEK
FRP = {
    "primary_full_E_hybrid_line": frp_table("front_hybrid", allE),
    "viina_2025_only": frp_table("front_viina", in2025),
    "deepstate_line_full_E": frp_table("front_ds", allE),
}
# reference distributions for the H13 cutoff
rear_ru = np.zeros(len(fr), bool)
PT = xy.values
gtree = shapely.STRtree(shapely.points(np.c_[gen.x, gen.y]))
for w, idx in fr.groupby("week").groups.items():
    pos = fr.index.get_indexer(idx)
    p = PT[pos]
    if w >= VIINA_FROM_WEEK:
        t = widx[w]
        eg = EG[(RU[EI, t] & UAs[EJ, t]) | (UAs[EI, t] & RU[EJ, t])]
        near = np.zeros(len(pos), bool)
        near[np.unique(shapely.STRtree(eg).query(p, predicate="dwithin", distance=30_000)[0])] = True
        nn = gtree.nearest(p)  # Voronoi membership = nearest generator
        rear_ru[pos] = (~near) & RU[nn, t]
    elif w in DS_OCC:
        occ = DS_OCC[w]
        rear_ru[pos] = shapely.within(p, occ) & ~shapely.dwithin(p, occ.boundary.intersection(UA_inner), 30_000)
fr["rear_ru30"] = rear_ru
H13 = {
    "primary_front_cell_p90_full_E": FRP["primary_full_E_hybrid_line"]["pooled_p90"],
    "ref_all_E_fires_p90": pct(allE, 90),
    "ref_russian_held_rear_gt30km_p90": pct(fr.rear_ru30, 90),
}
say("FRP p75 (MW) front-cell fires, primary (full E; DeepState line 2024 weeks, VIINA line 2025 weeks):")
for kk, vv in FRP["primary_full_E_hybrid_line"].items():
    say(f"  {kk}: {vv['value_MW']} (n {vv['n']})")
for name in ("viina_2025_only", "deepstate_line_full_E"):
    say(f"  [{name}] " + "; ".join(f"{k}={v['value_MW']} (n {v['n']})" for k, v in FRP[name].items()))
say("H13 p90: " + "; ".join(f"{k}={v['value_MW']} (n {v['n']})" for k, v in H13.items()))

# ---------------------------------------------------------------- write
res = dict(
    generated=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    script="scripts/prereg_constants.py",
    grid=GRID,
    grid_note=("h3-py not installed and no downloads allowed: regular hexagons in EPSG:3035 with the H3 res-5 "
               "average area (252.903 km2). Re-run with h3 installed before tagging." if GRID != "h3_res5" else "H3 res 5"),
    crs_for_area_and_distance="EPSG:3035",
    viina_status_codes=codes,
    sesoi=dict(definition="half the mean |RU-held km2(t+4) - RU-held km2(t)| over front cell-weeks (centroid <=15 km of the RU|UA Voronoi boundary at week t), VIINA 2025 majority `status`, weekly modal status",
               primary=S_main, alternatives=S_alt, old_deepstate_value_km2=2.9,
               per_doubling_km2=round(S_main["sesoi_km2"] * np.log(2), 3),
               weeks=[str(w.date()) for w in WEEKS], ties_broken_by_latest_day=n_ties,
               control_line_km_median=float(np.median(line_km))),
    frp_p75_big_small=FRP,
    h13_p90=H13,
    h14="not computed (hypothesis; computing baseline FRP floors would be looking at the test)",
    filters=dict(firms="S-NPP yearly country files, 2024-07-08..2025-12-31, confidence in {n,h}, any type; C1 rows dropped on read",
                 season="summer May-Oct, winter Nov-Apr (by acq_date month)", week="ISO week (Mon-Sun)"),
    log=log,
)
os.makedirs(os.path.dirname(P["out"]), exist_ok=True)
with open(P["out"], "w") as fh:
    json.dump(res, fh, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))
say(f"wrote {P['out']}")
