"""12_national_kyiv_week.py — ISO week × national RU-held km² (VIINA Voronoi), Kyiv-city fires and observability,
joined to the Telegram Kyiv strike series (tg_*) and Air Force national launched totals (af_*). H12 inputs.
Contract: planning/PANEL.md (Builder D §3). Output: data/derived/panel/national_week.csv (+ meta).

Definitions: Kyiv city = geoBoundaries ADM1 feature shapeName == "Kyiv" (UA-30). kyiv_fires = FIRMS detections
(confidence n/h, any satellite) inside that polygon, by the UTC date's ISO week; kyiv_opportunity = sum of
detection opportunity over res-6 cells whose centroid is inside the polygon (and their 7 days). af_* = sums over
night_date of the numeric columns of data/derived/telegram/national_night.csv (ISO week of night_date);
af_n_nights = nights with a parsed post. tg_* = kyiv_strikes_week.csv columns as published.

Run:  ~/D3/Frontline_From_Space/.venv/bin/python -I scripts/analysis/12_national_kyiv_week.py
"""
from __future__ import annotations
import sys, time, json
from pathlib import Path
import numpy as np, pandas as pd, geopandas as gpd, shapely, duckdb, h3

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, INTERIM, DERIVED, write_meta, log
from _control import CTRL, PANEL_START, PANEL_END, iso_week_start, phase_of_week

t0 = time.time()
OUT = DERIVED / "panel" / "national_week.csv"
ODBL = "Contains VIINA data (Zhukov, Yuri. 'VIINA: Violent Incident Information from News Articles on the 2022 Russian Invasion of Ukraine'), ODbL 1.0; derived national aggregates. Fires: NASA FIRMS VIIRS 375 m."

clw = pd.read_parquet(CTRL / "control_line_week.parquet")
nat = clw[["week_start", "iso_year", "iso_week", "ru_km2", "ua_km2", "contested_km2", "ru_km2_dsm", "ru_km2_isw", "ru_km2_wiki", "line_km", "n_front15_r5"]].copy()
nat["net_ru_gain_km2"] = nat.ru_km2.diff()
for s in ("dsm", "isw", "wiki"):
    nat[f"net_ru_gain_km2_{s}"] = nat[f"ru_km2_{s}"].diff()
nat = nat[(nat.week_start >= PANEL_START) & (nat.week_start <= PANEL_END)].reset_index(drop=True)
nat["phase"] = phase_of_week(nat.week_start).values
nat["season"] = np.where(pd.DatetimeIndex(nat.week_start).month.isin(range(5, 11)), "summer", "winter")

# Kyiv city polygon
adm1 = gpd.read_file(RAW / "boundaries/geoboundaries/geoBoundaries-UKR-ADM1.geojson")
kyiv = adm1[adm1.shapeName == "Kyiv"].geometry.union_all(); shapely.prepare(kyiv)
assert adm1[adm1.shapeName == "Kyiv"].shapeISO.iloc[0] == "UA-30"
minx, miny, maxx, maxy = kyiv.bounds
fires = pd.read_parquet(INTERIM / "fires.parquet", columns=["acq_ts_utc", "lat", "lon", "daynight", "frp"],
                        filters=[("lon", ">=", minx), ("lon", "<=", maxx), ("lat", ">=", miny), ("lat", "<=", maxy)])
fires = fires[shapely.contains(kyiv, shapely.points(fires.lon.values, fires.lat.values))].copy()
fires["date"] = fires.acq_ts_utc.dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()
fires["week_start"] = iso_week_start(fires.date)
kf = fires.groupby("week_start").agg(kyiv_fires=("lat", "size"), kyiv_fires_night=("daynight", lambda s: int((s.astype(str) == "N").sum())),
                                     kyiv_frp_sum=("frp", "sum")).reset_index()
log(f"Kyiv fires {len(fires):,} ({fires.date.min().date()}..{fires.date.max().date()})")

# Kyiv observability: res-6 cells whose centroid is inside the polygon
r6 = duckdb.sql(f"select distinct h3_r6 from read_parquet('{INTERIM / 'opportunity_r6_day.parquet'}') where h3_r5 in (select distinct h3_r5 from read_parquet('{INTERIM / 'opportunity_r6_day.parquet'}'))").df().h3_r6.tolist()
ll = np.array([h3.cell_to_latlng(c) for c in r6])
kcells = [c for c, (la, lo) in zip(r6, ll) if shapely.contains(kyiv, shapely.Point(lo, la))]
ko = duckdb.sql(f"""select date_trunc('week', date)::date as week_start, sum(opportunity) as kyiv_opportunity, sum(n_overpasses) as kyiv_n_overpasses,
                   sum(n_clear_overpasses) as kyiv_n_clear, avg(case when n_tcc_known > 0 then min_tcc end) as kyiv_min_tcc_mean
                   from read_parquet('{INTERIM / 'opportunity_r6_day.parquet'}') where h3_r6 in {tuple(kcells)} group by all""").df()
ko["week_start"] = pd.to_datetime(ko.week_start)
log(f"Kyiv res-6 cells {len(kcells)}")

# Telegram Kyiv series and Air Force national totals
tg = pd.read_csv(DERIVED / "telegram/kyiv_strikes_week.csv"); tg["week_start"] = pd.to_datetime(tg.week_start)
tg = tg.drop(columns=["iso_year", "iso_week"]).rename(columns={c: f"tg_{c}" for c in tg.columns if c != "week_start"})
af = pd.read_csv(DERIVED / "telegram/national_night.csv"); af["night_date"] = pd.to_datetime(af.night_date)
af["week_start"] = iso_week_start(af.night_date)
num = ["total_launched", "n_uav_launched", "n_missile_launched", "destroyed_total", "shot_down", "ew_lost", "hit_locations_n", "debris_locations_n",
       "ivaniuk_launched", "ivaniuk_destroyed", "n_waves_night", "n_tracks_in_waves", "n_tracks_kyiv_city_in_waves"]
afw = af.groupby("week_start").agg(**{f"af_{c}": (c, lambda s: s.sum(min_count=1)) for c in num},
                                   af_n_nights=("night_date", "size"), af_n_nights_with_launched=("total_launched", lambda s: int(s.notna().sum()))).reset_index()

out = nat.merge(kf, on="week_start", how="left").merge(ko, on="week_start", how="left").merge(tg, on="week_start", how="left").merge(afw, on="week_start", how="left")
for c in ("kyiv_fires", "kyiv_fires_night"):
    out[c] = out[c].fillna(0).astype(int)
out["kyiv_frp_sum"] = out.kyiv_frp_sum.fillna(0)
out["week_start"] = out.week_start.dt.date
out.to_csv(OUT, index=False, float_format="%.3f")
counts = {"weeks": len(out), "kyiv_fires_total": int(out.kyiv_fires.sum()), "kyiv_fires_by_year": {int(y): int(v) for y, v in out.groupby("iso_year").kyiv_fires.sum().items()},
          "weeks_with_tg": int(out.tg_n_impact_incidents_kyiv_city.notna().sum()), "weeks_with_af_launched": int(out.af_total_launched.notna().sum()),
          "kyiv_res6_cells": len(kcells), "runtime_s": round(time.time() - t0, 1)}
write_meta(OUT, inputs={"control_line_week": CTRL / "control_line_week.parquet", "fires": INTERIM / "fires.parquet", "opportunity_r6_day": INTERIM / "opportunity_r6_day.parquet",
                        "kyiv_strikes_week": DERIVED / "telegram/kyiv_strikes_week.csv", "national_night": DERIVED / "telegram/national_night.csv", "adm1": RAW / "boundaries/geoboundaries/geoBoundaries-UKR-ADM1.geojson"},
           counts=counts, extra={"definitions": __doc__.split("Definitions:")[1].split("Run:")[0].strip(), "licence": ODBL, "h12_note": "tg_* and af_* are exploratory cross-checks (DEVIATIONS 2026-10-22)"})
log(f"wrote {OUT} {counts}")
