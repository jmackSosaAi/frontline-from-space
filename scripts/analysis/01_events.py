"""01_events.py — build data/interim/analysis/events_v.parquet (set V: GeoConfirmed + Bellingcat TimeMap).

Contract: planning/DETECTION_MODEL.md (Builder A); definitions PREREG.md §2–§3.
  - one row per V event, 2022-02-24 -> 2025-12-31, inside Ukraine ADM0 (geoBoundaries)
  - columns: event_id, source, event_type_raw, event_type, date, lat, lon, h3_r5, h3_r6, oblast_iso,
             landcover_code, landcover_class, split, dup_ids
  - split: calendar months 2022-02..2025-12 drawn 70/30 by numpy.random.default_rng(20261014)
  - dedup: GeoConfirmed placemarks with identical (date, lat, lon) are one event; a Bellingcat and a
    GeoConfirmed record within 100 m on the same date are one event (both ids kept in dup_ids).

GeoConfirmed icon codes (icon `name` is null in the API; the template PNG basename is the type). Legend
read off the public icon templates on 2026-10-22: category = leading digit(s), last digit = status
(1 intact / present, 2 damaged, 3 destroyed). Mapping table ICON_TYPES below; printed to meta.

Run:  ~/D3/Frontline_From_Space/.venv/bin/python -I scripts/analysis/01_events.py
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, shapely

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (ROOT, RAW, INTERIM, SEED, V_START, V_END, WORLDCOVER_CLASSES, write_meta, log,
                     h3_cells, h3_parent, worldcover_at)

GC = RAW / "events/geoconfirmed_Ukraine.json"
BC = RAW / "events/bellingcat_timemap.json"
ADM0 = RAW / "boundaries/geoboundaries/geoBoundaries-UKR-ADM0.geojson"
ADM1 = RAW / "boundaries/geoboundaries/geoBoundaries-UKR-ADM1.geojson"
OUT = INTERIM / "events_v.parquet"
DUP_M = 100.0  # metres, Bellingcat vs GeoConfirmed

# --- GeoConfirmed icon code -> (raw label, coarse type) -----------------------------------------------
# coarse set fixed by the contract: strike, shelling, vehicle_loss, aircraft_loss, infrastructure, other
ICON_TYPES = {
    "01": ("artillery_position", "shelling"), "02": ("artillery_damaged", "vehicle_loss"), "03": ("artillery_destroyed", "vehicle_loss"),
    "10": ("munition_impact", "strike"),
    "11": ("bridge", "infrastructure"), "12": ("bridge_damaged", "infrastructure"), "13": ("bridge_destroyed", "infrastructure"),
    "20": ("photo", "other"), "30": ("video", "other"),
    "21": ("helicopter", "other"), "22": ("helicopter_damaged", "aircraft_loss"), "23": ("helicopter_destroyed", "aircraft_loss"),
    "31": ("jet", "other"), "32": ("jet_damaged", "aircraft_loss"), "33": ("jet_destroyed", "aircraft_loss"),
    "41": ("tank", "other"), "42": ("tank_damaged", "vehicle_loss"), "43": ("tank_destroyed", "vehicle_loss"),
    "50": ("casualty", "other"),
    "51": ("ship", "other"), "52": ("ship_damaged", "vehicle_loss"), "53": ("ship_destroyed", "vehicle_loss"),
    "60": ("chemical", "other"),
    "61": ("truck", "other"), "62": ("truck_damaged", "vehicle_loss"), "63": ("truck_destroyed", "vehicle_loss"),
    "70": ("explosion", "strike"),
    "71": ("mlrs_position", "shelling"), "72": ("mlrs_damaged", "vehicle_loss"), "73": ("mlrs_destroyed", "vehicle_loss"),
    "81": ("uav_fixedwing", "other"), "82": ("uav_fixedwing_damaged", "aircraft_loss"), "83": ("uav_fixedwing_destroyed", "aircraft_loss"),
    "90": ("clash", "other"), "91": ("unknown", "other"),
    "92": ("soldier_damaged", "other"), "93": ("soldier_destroyed", "other"),
    "100": ("person_moving", "other"), "101": ("person_surrender", "other"), "102": ("person_surrender_damaged", "other"), "103": ("person_surrender_destroyed", "other"),
    "110": ("uav_quadcopter", "other"),
    "111": ("missile", "strike"), "112": ("missile_damaged", "strike"), "113": ("missile_destroyed", "strike"),
    "120": ("fortification", "infrastructure"),
    "121": ("industrial", "infrastructure"), "122": ("industrial_damaged", "infrastructure"),
    "131": ("camp", "other"), "132": ("camp_damaged", "other"), "133": ("camp_destroyed", "other"),
    "141": ("boat", "other"), "142": ("boat_damaged", "vehicle_loss"), "143": ("boat_destroyed", "vehicle_loss"),
    "151": ("submarine", "other"), "152": ("submarine_damaged", "vehicle_loss"),
    "161": ("train", "other"), "162": ("train_damaged", "vehicle_loss"), "163": ("train_destroyed", "vehicle_loss"),
    "171": ("apc", "other"), "172": ("apc_damaged", "vehicle_loss"), "173": ("apc_destroyed", "vehicle_loss"),
    "181": ("loitering_munition", "strike"), "182": ("loitering_munition_damaged", "aircraft_loss"), "183": ("loitering_munition_destroyed", "aircraft_loss"),
    "191": ("building", "infrastructure"), "192": ("building_damaged", "infrastructure"), "193": ("building_destroyed", "infrastructure"),
    "201": ("sam_system", "other"), "202": ("sam_damaged", "vehicle_loss"), "203": ("sam_destroyed", "vehicle_loss"),
    "moto": ("motorcycle", "other"), "nomoto": ("motorcycle_damaged", "vehicle_loss"), "nonomoto": ("motorcycle_destroyed", "vehicle_loss"),
    "_CIRCLES_RU_56_FLAG": ("flag_ru", "other"), "_CIRCLES_UA_56_FLAG": ("flag_ua", "other"),
    # custom (UUID-named) icons, read off the served PNGs 2026-10-22
    "82c8f84f-3212-4d5f-8a7f-9fafdcb97265": ("uav_fixedwing_damaged", "aircraft_loss"),
    "eb113eda": ("uav_fixedwing_destroyed", "aircraft_loss"),
    "637f806c-46e7-48cf-a15b-0a0ead05c01a": ("uav_quadcopter_damaged", "aircraft_loss"),
    "e4610521-8e49-4a1c-937b-bb9bdaaf1824": ("uav_quadcopter_destroyed", "aircraft_loss"),
    "efded2b8-0c8c-465f-9596-00ea404049a1": ("radar", "other"),
    "15380368-63be-4bf9-8373-a30ef0d31bed": ("radar_damaged", "vehicle_loss"),
    "89b368d2-b2c3-475a-bd5a-e16d10abfea9": ("ew_vehicle", "other"),
    "25508da3-5341-4843-b7e6-b955eaad7ce8": ("ew_vehicle_damaged", "vehicle_loss"),
    "72ae8f9c-dc54-4dcd-bfb5-c77d0fb85944": ("ew_vehicle_destroyed", "vehicle_loss"),
    "4b82ea08-a3ee-4002-a75b-6084c7967169": ("vehicle_burning", "vehicle_loss"),
    "f0b7a02c-510c-40ef-94db-aa70eb4c3b90": ("vehicle_burning_damaged", "vehicle_loss"),
    "09407941": ("vehicle_burning_destroyed", "vehicle_loss"),
    "7d3b5b68": ("truck_destroyed", "vehicle_loss"),
    "a8c55b37": ("pickup", "other"), "b602eea6": ("pickup", "other"),
    "e8796387": ("missile", "strike"), "ed1395e2": ("hangar", "infrastructure"),
}


def icon_lookup(code: str):
    """Exact code, else UUID prefix (first 8 chars) for custom icons."""
    if code in ICON_TYPES:
        return ICON_TYPES[code]
    return ICON_TYPES.get(code[:8])
# Bellingcat: every TimeMap record is a documented incident of civilian harm/damage. impact[] names the object hit.
BC_CIVIL_OBJECTS = {"Residential", "Commercial", "School or childcare", "Roads/Highways/Transport", "Industrial",
                    "Healthcare", "Administrative", "Cultural", "Religious", "Food/Food Infrastructure", "Humanitarian"}


def load_geoconfirmed() -> pd.DataFrame:
    g = json.loads(GC.read_text())
    rows = []
    for fac in g:
        for ic in fac["icons"]:
            code = os.path.splitext(os.path.basename(ic.get("icon") or ""))[0]
            for p in ic["placemarks"]:
                rows.append((p["id"], fac.get("name"), code, p.get("date"), p.get("la"), p.get("lo")))
    df = pd.DataFrame(rows, columns=["event_id", "faction", "icon_code", "date_raw", "lat", "lon"])
    n0 = len(df)
    df["date"] = pd.to_datetime(df.date_raw, errors="coerce").dt.normalize()
    df["lat"] = pd.to_numeric(df.lat, errors="coerce"); df["lon"] = pd.to_numeric(df.lon, errors="coerce")
    df = df.dropna(subset=["date", "lat", "lon"])
    log(f"geoconfirmed: {n0} placemarks, {len(df)} with date+coords")
    looked = df.icon_code.map(icon_lookup)
    known = looked.notna()
    df["event_type_raw"] = np.where(known, looked.map(lambda v: v[0] if v else ""), "icon_" + df.icon_code)
    df["event_type"] = np.where(known, looked.map(lambda v: v[1] if v else ""), "other")
    df["source"] = "geoconfirmed"
    return df


def load_bellingcat() -> pd.DataFrame:
    b = json.loads(BC.read_text())
    df = pd.DataFrame(b)
    n0 = len(df)
    df["date"] = pd.to_datetime(df.date, errors="coerce").dt.normalize()
    df["lat"] = pd.to_numeric(df.latitude, errors="coerce"); df["lon"] = pd.to_numeric(df.longitude, errors="coerce")
    df = df.dropna(subset=["date", "lat", "lon"])
    log(f"bellingcat: {n0} records, {len(df)} with date+coords")
    imp = df.impact.map(lambda x: [str(i) for i in (x or [])])
    df["event_type_raw"] = imp.map(lambda x: "|".join(x) if x else "unspecified")
    df["event_type"] = imp.map(lambda x: "infrastructure" if any(i in BC_CIVIL_OBJECTS for i in x) else "strike")
    df["event_id"] = df["id"].astype(str)
    df["source"] = "bellingcat"
    return df[["event_id", "source", "event_type_raw", "event_type", "date", "lat", "lon"]]


def main() -> None:
    t0 = time.time()
    INTERIM.mkdir(parents=True, exist_ok=True)
    gc = load_geoconfirmed(); bc = load_bellingcat()
    counts: dict = {"geoconfirmed_placemarks_parsed": int(len(gc)), "bellingcat_parsed": int(len(bc))}

    # --- window -------------------------------------------------------------------------------------
    lo, hi = pd.Timestamp(V_START), pd.Timestamp(V_END)
    gc = gc[gc.date.between(lo, hi)].copy(); bc = bc[bc.date.between(lo, hi)].copy()
    counts.update(geoconfirmed_in_window=int(len(gc)), bellingcat_in_window=int(len(bc)))
    log(f"in window {V_START}..{V_END}: gc {len(gc)}, bc {len(bc)}")

    # --- GeoConfirmed exact-duplicate collapse (date, lat, lon) ---------------------------------------
    gc = gc.sort_values(["date", "lat", "lon", "event_id"])
    key = ["date", "lat", "lon"]
    grp = gc.groupby(key, sort=False)
    first = grp.head(1).copy()
    all_ids = grp.event_id.agg(list)
    first["dup_ids"] = [list(x[1:]) for x in all_ids.loc[list(zip(first.date, first.lat, first.lon))]]
    # raw types of the collapsed placemarks are joined so nothing is lost
    all_types = grp.event_type_raw.agg(lambda s: "|".join(sorted(set(s))))
    first["event_type_raw"] = all_types.loc[list(zip(first.date, first.lat, first.lon))].values
    counts["geoconfirmed_exact_dup_collapsed"] = int(len(gc) - len(first))
    gc = first[["event_id", "source", "event_type_raw", "event_type", "date", "lat", "lon", "dup_ids"]]
    bc = bc.assign(dup_ids=[[] for _ in range(len(bc))])
    log(f"gc exact dups collapsed: {counts['geoconfirmed_exact_dup_collapsed']} -> {len(gc)} events")

    # --- Bellingcat vs GeoConfirmed within 100 m, same date -> one event (Bellingcat row kept) ---------
    gc_g = gpd.GeoDataFrame(gc, geometry=gpd.points_from_xy(gc.lon, gc.lat), crs=4326).to_crs(3035)
    bc_g = gpd.GeoDataFrame(bc, geometry=gpd.points_from_xy(bc.lon, bc.lat), crs=4326).to_crs(3035)
    j = gpd.sjoin_nearest(bc_g[["event_id", "date", "geometry"]], gc_g[["event_id", "date", "geometry"]],
                          how="inner", max_distance=DUP_M, distance_col="d_m", lsuffix="bc", rsuffix="gc")
    j = j[j.date_bc == j.date_gc]
    gc_matched = set(j.event_id_gc)
    add = j.groupby("event_id_bc").event_id_gc.agg(list)
    gc_dups = dict(zip(gc.event_id, gc.dup_ids))
    merged = {}
    for bid, gids in add.items():
        extra = []
        for gid in gids:
            extra.append(gid); extra += list(gc_dups[gid])
        merged[bid] = list(dict.fromkeys(extra))
    bc["dup_ids"] = [merged.get(b, []) for b in bc.event_id]
    gc = gc[~gc.event_id.isin(gc_matched)]
    counts.update(cross_source_pairs=int(len(j)), geoconfirmed_merged_into_bellingcat=int(len(gc_matched)),
                  bellingcat_with_gc_match=int(len(add)))
    log(f"cross-source dups: {len(j)} pairs, {len(gc_matched)} gc records merged into {len(add)} bc events")

    ev = pd.concat([bc, gc], ignore_index=True)
    ev = ev[["event_id", "source", "event_type_raw", "event_type", "date", "lat", "lon", "dup_ids"]]

    # --- inside Ukraine ADM0; oblast via ADM1 ---------------------------------------------------------
    a0 = gpd.read_file(ADM0); a1 = gpd.read_file(ADM1)[["shapeISO", "shapeName", "geometry"]]
    ua = shapely.make_valid(a0.geometry.union_all()); shapely.prepare(ua)
    pts = shapely.points(ev.lon.values, ev.lat.values)
    inside = shapely.contains(ua, pts)
    counts["dropped_outside_adm0"] = int((~inside).sum())
    ev = ev[inside].reset_index(drop=True)
    log(f"inside Ukraine ADM0: {len(ev)} (dropped {counts['dropped_outside_adm0']})")
    evg = gpd.GeoDataFrame(ev, geometry=gpd.points_from_xy(ev.lon, ev.lat), crs=4326)
    sj = gpd.sjoin(evg, a1, how="left", predicate="within")
    sj = sj[~sj.index.duplicated(keep="first")]
    ev["oblast_iso"] = sj.shapeISO.values
    miss = ev.oblast_iso.isna()
    if miss.any():  # points on ADM1 seams: nearest oblast
        near = gpd.sjoin_nearest(evg[miss].to_crs(3035), a1.to_crs(3035), how="left")
        near = near[~near.index.duplicated(keep="first")]
        ev.loc[miss, "oblast_iso"] = near.shapeISO.values
    counts["oblast_filled_by_nearest"] = int(miss.sum())

    # --- h3, land cover ------------------------------------------------------------------------------
    ev["h3_r6"] = h3_cells(ev.lat, ev.lon, 6); ev["h3_r5"] = h3_parent(ev.h3_r6, 5)
    ev["landcover_code"] = np.array(worldcover_at(ev.lat, ev.lon), dtype=np.int16)
    ev["landcover_class"] = ev.landcover_code.map(WORLDCOVER_CLASSES).fillna("unknown")

    # --- split: months 2022-02..2025-12, 70/30 by seeded RNG -------------------------------------------
    months = pd.period_range("2022-02", "2025-12", freq="M")
    rng = np.random.default_rng(SEED)
    n_test = int(round(0.3 * len(months)))
    test_months = sorted(str(m) for m in rng.choice(np.array([str(m) for m in months]), size=n_test, replace=False))
    ev["split"] = np.where(ev.date.dt.to_period("M").astype(str).isin(test_months), "test", "train")

    ev = ev.sort_values(["date", "source", "event_id"]).reset_index(drop=True)
    ev["dup_ids"] = ev.dup_ids.map(lambda x: list(x) if isinstance(x, (list, tuple, np.ndarray)) else [])
    ev["date"] = ev.date.dt.date
    cols = ["event_id", "source", "event_type_raw", "event_type", "date", "lat", "lon", "h3_r5", "h3_r6",
            "oblast_iso", "landcover_code", "landcover_class", "split", "dup_ids"]
    ev = ev[cols]
    ev.to_parquet(OUT, index=False)

    # --- summary + meta --------------------------------------------------------------------------------
    yr = pd.to_datetime(ev.date).dt.year
    by_src_type_year = ev.groupby([ev.source, ev.event_type, yr]).size().rename("n").reset_index()
    by_src_type_year.columns = ["source", "event_type", "year", "n"]
    by_src_type_year.to_csv(INTERIM / "events_v_summary.csv", index=False)
    counts.update(
        events=int(len(ev)),
        by_source=ev.source.value_counts().to_dict(),
        by_type=ev.event_type.value_counts().to_dict(),
        by_year=yr.value_counts().sort_index().to_dict(),
        by_split=ev.split.value_counts().to_dict(),
        landcover_mix=ev.landcover_class.value_counts().to_dict(),
        raw_types_unmapped=sorted(set(t for t in ev.event_type_raw[ev.source == "geoconfirmed"] if t.startswith("icon_"))),
    )
    write_meta(OUT, inputs={"geoconfirmed": GC, "bellingcat": BC, "adm0": ADM0, "adm1": ADM1}, counts=counts, extra={
        "window": [V_START, V_END],
        "split": {"rule": "calendar months 2022-02..2025-12; round(0.3*n_months) drawn without replacement by "
                          "numpy.random.default_rng(20261014).choice over the sorted month list",
                  "n_months": len(months), "n_test_months": n_test, "test_months": test_months},
        "dedup": {"geoconfirmed_exact": "identical (date, lat, lon) -> one event; first id by sort kept, rest in dup_ids; raw types joined by '|'",
                  "cross_source": f"Bellingcat and GeoConfirmed within {DUP_M:.0f} m (EPSG:3035) on the same date -> one event; "
                                  "the Bellingcat row is kept, GeoConfirmed ids (and their exact dups) go to dup_ids"},
        "event_type_mapping": {"geoconfirmed_icon_codes": {k: {"raw": v[0], "coarse": v[1]} for k, v in ICON_TYPES.items()},
                               "geoconfirmed_unknown_icon": "raw = 'icon_<basename>', coarse = other (custom UUID-named icons)",
                               "bellingcat": "coarse = infrastructure if any impact[] item names a civilian object class; "
                                             "else strike (impact empty, 'Undefined' or 'Military'); raw = impact list joined by '|'"},
        "landcover": "ESA WorldCover 2021 v200 10 m class at the point (3° tiles by floor(lat/3), floor(lon/3))",
        "runtime_s": round(time.time() - t0, 1),
    })
    print(by_src_type_year.pivot_table(index=["source", "event_type"], columns="year", values="n", fill_value=0).to_string())
    print("\ntest months:", test_months)
    print("\nlandcover mix:", ev.landcover_class.value_counts().to_dict())
    print(f"\n{len(ev)} events -> {OUT.relative_to(ROOT)}  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
