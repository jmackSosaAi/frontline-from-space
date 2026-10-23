"""Shared geometry for the C1 control panel (scripts 10–12). Ported from scripts/prereg_constants.py so the
Voronoi, control line and front-cell definitions are identical to the ones that fixed the SESOI (PREREG §3).

Ukraine polygon = Natural Earth 10m admin-0 Ukraine ∪ NE admin-1 Crimea + Sevastopol (as in prereg_constants.py).
CRS for area and distance: EPSG:3035. ISO weeks Monday-start.
"""
from __future__ import annotations
import numpy as np, pandas as pd, geopandas as gpd, shapely
from shapely.geometry import Polygon
from pathlib import Path
from _common import RAW, INTERIM

CRS = 3035
CTRL = INTERIM / "control"            # interim control geometry (not published)
TESS = RAW / "viina" / "gn_UA_tess.geojson"
VIINA_ZIPS = {y: RAW / "viina" / f"control_latest_{y}.zip" for y in range(2022, 2027)}
BANDS = (10, 15, 25)
STATUS_COLS = ["status", "status_dsm", "status_isw", "status_wiki"]
STATUS_CODE = {"": 0, "UA": 1, "RU": 2, "CONTESTED": 3}
CODE_STATUS = {v: k for k, v in STATUS_CODE.items()}

PANEL_START = pd.Timestamp("2022-02-21")           # first ISO week of VIINA (data begin 2022-02-23)
PANEL_END = pd.Timestamp("2025-12-31")
C1_START, C1_END = pd.Timestamp("2022-04-03"), pd.Timestamp("2024-07-07")
PHASE_A_END = pd.Timestamp("2022-11-30")           # A: 2022-04-03..2022-11-30; B: 2022-12-01..2024-07-07
E_START, E_END = pd.Timestamp("2024-07-08"), pd.Timestamp("2025-12-31")


def iso_week_start(d: pd.Series) -> pd.Series:
    """Monday of the ISO week containing each date (same rule as prereg_constants.iso_week)."""
    return d.dt.to_period("W-SUN").dt.start_time


def ukraine_polygon():
    ne0 = gpd.read_file(f"zip://{RAW / 'boundaries/naturalearth/ne_10m_admin_0_countries.zip'}!ne_10m_admin_0_countries.shp")
    ne1 = gpd.read_file(f"zip://{RAW / 'boundaries/naturalearth/ne_10m_admin_1_states_provinces.zip'}")
    ua0 = ne0[ne0.ADMIN == "Ukraine"].to_crs(CRS).geometry.union_all()
    crimea = ne1[ne1.name.isin(["Crimea", "Sevastopol"])].to_crs(CRS).geometry.union_all()
    ua = shapely.make_valid(ua0.union(crimea))
    return ua


def h3_hexes(ids: list[str]) -> gpd.GeoDataFrame:
    import h3
    polys = [Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(c)]) for c in ids]
    return gpd.GeoDataFrame({"cell": list(ids)}, geometry=polys, crs=4326).to_crs(CRS)


def cells_touching(ua, res: int, buffer_deg: float = 0.2) -> gpd.GeoDataFrame:
    """All H3 cells at `res` whose polygon intersects the Ukraine polygon (prereg_constants grid rule)."""
    import h3
    ua_ll = gpd.GeoSeries([ua], crs=CRS).to_crs(4326).iloc[0]
    ids = sorted(h3.geo_to_cells(ua_ll.buffer(buffer_deg), res))
    hexes = h3_hexes(ids)
    hexes = hexes[hexes.intersects(ua)].reset_index(drop=True)
    return hexes


def phase_of_week(week_start: pd.Series) -> pd.Series:
    """Phase by the Monday of the ISO week: A, B (C1), E, or none. Stated in the Builder D log."""
    ws = pd.to_datetime(week_start)
    out = pd.Series("none", index=ws.index, dtype=object)
    out[(ws >= C1_START) & (ws <= PHASE_A_END)] = "A"
    out[(ws > PHASE_A_END) & (ws <= C1_END)] = "B"
    out[(ws >= E_START) & (ws <= E_END)] = "E"
    return out
