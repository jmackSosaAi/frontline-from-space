"""Shared helpers for the detection tests (05–09): event detection, event-window covariates,
H1 strata, Wilson CI. Spec: PREREG.md §3–§4, planning/DETECTION_MODEL.md (Builder C decisions).

Detection (PREREG §3, operationalised): an event is detected if ≥1 fire (any satellite unless
restricted, confidence n/h, any type) lies within 1,000 m (EPSG:3035) and has acq_ts_utc in
[event date 00:00 UTC − 12 h, event date 24:00 UTC + 12 h]  (a 48-h window).
Covariates come from overpasses_r6 for the event's h3_r6 cell in the same window.
"""
from __future__ import annotations
import datetime as dt
import numpy as np, pandas as pd, duckdb
from pathlib import Path
from scipy.spatial import cKDTree
from pyproj import Transformer

from _common import INTERIM, SEED, log  # noqa

EVENTS = INTERIM / "events_v.parquet"
FIRES = INTERIM / "fires.parquet"
OVERPASSES = INTERIM / "overpasses_r6.parquet"
OPP_DAY = INTERIM / "opportunity_r6_day.parquet"

WINDOW_BEFORE_H = 12   # hours before event date 00:00 UTC
WINDOW_AFTER_H = 12    # hours after event date 24:00 UTC
RADIUS_M = 1000.0
UKR_BOX = dict(lat0=44.0, lat1=53.0, lon0=22.0, lon1=41.0)
RESTRICTED_TYPES = ["strike", "shelling", "infrastructure", "vehicle_loss"]
NIGHT_HOURS_UTC = set([20, 21, 22, 23, 0, 1, 2, 3, 4])   # for 'Both' granules

_T3035 = Transformer.from_crs("EPSG:4326", "EPSG:3035", always_xy=True)


def to_3035(lat, lon):
    x, y = _T3035.transform(np.asarray(lon, float), np.asarray(lat, float))
    return np.column_stack([x, y])


def con_utc():
    con = duckdb.connect()
    con.execute("SET TimeZone='UTC'")
    con.execute("SET threads=8")
    return con


def load_events() -> pd.DataFrame:
    e = pd.read_parquet(EVENTS)
    e["date"] = pd.to_datetime(e["date"])
    e["w0"] = (e["date"] - pd.Timedelta(hours=WINDOW_BEFORE_H)).dt.tz_localize("UTC")
    e["w1"] = (e["date"] + pd.Timedelta(hours=24 + WINDOW_AFTER_H)).dt.tz_localize("UTC")
    e["uid"] = np.arange(len(e), dtype=np.int64)  # event_id is not unique (2 Bellingcat ids repeat)
    e["month"] = e["date"].dt.month
    e["year"] = e["date"].dt.year
    return e


def load_fires_ukr(satellites=None) -> pd.DataFrame:
    """Fires inside the Ukraine lat/lon box (all events are inside Ukraine ADM0, so any fire within
    1 km of an event is in the box). Optionally restrict satellites."""
    con = con_utc()
    sat = "" if satellites is None else " AND satellite IN (" + ",".join(f"'{s}'" for s in satellites) + ")"
    q = f"""SELECT fire_id, satellite, acq_ts_utc, lat, lon, h3_r6, frp, daynight, type
            FROM '{FIRES}' WHERE lat BETWEEN {UKR_BOX['lat0']} AND {UKR_BOX['lat1']}
            AND lon BETWEEN {UKR_BOX['lon0']} AND {UKR_BOX['lon1']}{sat}"""
    f = con.sql(q).df()
    f["acq_ts_utc"] = pd.to_datetime(f["acq_ts_utc"], utc=True)
    return f


def detect(events: pd.DataFrame, fires: pd.DataFrame, radius_m: float = RADIUS_M) -> pd.DataFrame:
    """Per event: detected (bool), n_fires_1km_window, min_dist_m, max_frp, first_sat, any_night_fire.
    fires must have lat, lon, acq_ts_utc (UTC), satellite, frp, daynight."""
    fx = to_3035(fires["lat"].values, fires["lon"].values)
    tree = cKDTree(fx)
    ex = to_3035(events["lat"].values, events["lon"].values)
    hits = tree.query_ball_point(ex, r=radius_m)
    f_ts = fires["acq_ts_utc"].values.astype("datetime64[ns]")
    f_sat = fires["satellite"].values; f_frp = fires["frp"].values; f_dn = fires["daynight"].values
    w0 = events["w0"].values.astype("datetime64[ns]"); w1 = events["w1"].values.astype("datetime64[ns]")
    n = len(events)
    det = np.zeros(n, bool); nf = np.zeros(n, np.int32); mind = np.full(n, np.nan); mfrp = np.full(n, np.nan)
    sats = np.array([""] * n, dtype=object); nightf = np.zeros(n, bool)
    for i, idx in enumerate(hits):
        if not idx:
            continue
        idx = np.asarray(idx)
        ts = f_ts[idx]
        m = (ts >= w0[i]) & (ts <= w1[i])
        if not m.any():
            continue
        idx = idx[m]
        det[i] = True; nf[i] = len(idx)
        d = np.sqrt(((fx[idx] - ex[i]) ** 2).sum(1)); mind[i] = d.min()
        mfrp[i] = np.nanmax(f_frp[idx])
        sats[i] = "|".join(sorted(set(f_sat[idx].tolist())))
        nightf[i] = bool((f_dn[idx] == "N").any())
    return pd.DataFrame({"uid": events["uid"].values, "detected": det, "n_fires": nf,
                         "min_dist_m": mind, "max_frp": mfrp, "det_sats": sats, "any_night_fire": nightf})


def window_covariates(events: pd.DataFrame, satellites=None) -> pd.DataFrame:
    """Overpass covariates for each event's h3_r6 cell in [w0, w1] from overpasses_r6.
    'Both' day/night granules are assigned by UTC hour (20–04 night). hours_since_prev sentinel
    values (≤0 or >1000 h) are ignored. Returns one row per event (events with no overpass rows get NaN)."""
    con = con_utc()
    ev = events[["uid", "h3_r6", "w0", "w1"]].copy()
    con.register("ev", ev)
    sat = "" if satellites is None else " AND o.satellite IN (" + ",".join(f"'{s}'" for s in satellites) + ")"
    night = f"(CASE WHEN o.day_night='Night' THEN 1 WHEN o.day_night='Day' THEN 0 ELSE (CASE WHEN hour(o.start_utc) IN ({','.join(map(str, sorted(NIGHT_HOURS_UTC)))}) THEN 1 ELSE 0 END) END)"
    q = f"""
    WITH j AS (
      SELECT e.uid, o.tcc, o.sde_cm, o.start_utc, o.satellite, {night} AS is_night,
             CASE WHEN o.hours_since_prev > 0 AND o.hours_since_prev < 1000 THEN o.hours_since_prev END AS hsp,
             (o.tcc < 0.5 AND o.sde_cm < 1.0) AS clear
      FROM ev e JOIN read_parquet('{OVERPASSES}/*/*.parquet', hive_partitioning=1) o
        ON o.h3_r6 = e.h3_r6 AND o.start_utc >= e.w0 AND o.start_utc <= e.w1{sat}
    )
    SELECT uid,
           count(*) AS n_overpasses,
           min(tcc) AS min_tcc, avg(tcc) AS mean_tcc,
           max(CASE WHEN sde_cm >= 1.0 THEN 1 ELSE 0 END) AS any_snow,
           sum(CASE WHEN clear THEN 1 ELSE 0 END) AS n_clear,
           avg(is_night) AS share_night,
           avg(hsp) AS hours_since_prev,
           max(CASE WHEN clear AND is_night=1 THEN 1 ELSE 0 END) AS clear_night,
           max(CASE WHEN clear AND is_night=0 THEN 1 ELSE 0 END) AS clear_day,
           arg_min(is_night, tcc) AS best_is_night,
           sum(CASE WHEN satellite='N' THEN 1 ELSE 0 END) AS n_over_N,
           sum(CASE WHEN satellite='N20' THEN 1 ELSE 0 END) AS n_over_N20,
           sum(CASE WHEN satellite='N21' THEN 1 ELSE 0 END) AS n_over_N21
    FROM j GROUP BY uid"""
    log(f"window_covariates: joining {len(ev):,} events to overpasses (satellites={satellites or 'all'}) …")
    cov = con.sql(q).df()
    out = events[["uid"]].merge(cov, on="uid", how="left")
    for c in ["n_overpasses", "n_clear", "any_snow", "clear_night", "clear_day", "n_over_N", "n_over_N20", "n_over_N21"]:
        out[c] = out[c].fillna(0).astype(int)
        out["no_overpass_rows"] = ~out["uid"].isin(cov["uid"])
    return out


def h1_strata(df: pd.DataFrame, daynight_def: str = "clear_night") -> pd.Series:
    """PREREG H1 strata. best = clear (min_tcc<0.5 & no snow) & night & Jun–Sep;
    worst = (min_tcc≥0.5 or snow) & day & Nov–Feb.
    daynight_def='clear_night' (primary): night = event had ≥1 clear NIGHT overpass in the window; day = otherwise.
      Under this definition the worst stratum's 'day' is automatically satisfied (no clear look at all).
    daynight_def='best_overpass' (sensitivity): night/day = the flag of the lowest-tcc overpass in the window."""
    clear = (df["min_tcc"] < 0.5) & (df["any_snow"] == 0)
    if daynight_def == "clear_night":
        night = df["clear_night"] == 1
    else:
        night = df["best_is_night"] == 1
    m = df["month"]
    best = clear & night & m.between(6, 9)
    worst = (~clear) & (~night) & m.isin([11, 12, 1, 2])
    s = pd.Series("other", index=df.index)
    s[best] = "best"; s[worst] = "worst"
    s[df["min_tcc"].isna()] = "no_overpass"
    return s


def wilson(k, n, z: float = 1.959964):
    k = np.asarray(k, float); n = np.asarray(n, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = k / n
        den = 1 + z * z / n
        c = (p + z * z / (2 * n)) / den
        h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, c - h, c + h


def recall_table(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    g = df.groupby(by, dropna=False)["detected"].agg(n="size", detected="sum").reset_index()
    p, lo, hi = wilson(g["detected"], g["n"])
    g["recall"] = p; g["ci_lo"] = lo; g["ci_hi"] = hi
    return g


def sha256_file(p: Path) -> str:
    from _common import sha256_file as s
    return s(p)
