"""L5: link events into launch waves (planning/TELEGRAM_PIPELINE.md §L5).

launch_waves.parquet  one row per wave. A wave opens at the first launch / launch_intel post of an activity
                      session and closes at the last all_clear before a >= QUIET_H gap in launch/track activity
                      (fallback: last activity + QUIET_H when no all_clear was posted). Every track, launch,
                      launch_intel, alert and all_clear inside [start, end] is linked (msg_ids only, no text).
strike_events.parquet one row per strike event, clustered from extract/impacts.parquet (after 30_resolve.py). Rule
                      (§L5): incidents with the same place key and event time within ±CLUSTER_H form one event. Place
                      key = geo_id (resolved settlement/raion feature), else oblast + raion_raw, else oblast +
                      settlement_raw string, else oblast alone (location withheld). Single-link chaining in time.
                      Incidents with a date but no clock time (22%) sit at 12:00 Kyiv and also chain to any same-key
                      incident on the same Kyiv date (ts_precision = 'date'). is_update rows (casualty revisions of
                      an earlier incident) merge into the nearest non-update event of the same key within
                      ±UPDATE_H; with none they stand alone (n_updates_standalone). Per event: event_ts = earliest
                      timed incident, killed/wounded = max across sources (never summed), weapon_class = most
                      specific class present, target_type = mode ('unknown' last), confidence = best, wave_id =
                      the wave whose [start_ts, end_ts] contains event_ts. msg_ids and numbers only; no post text.
                      When impacts.parquet is missing an empty table with the same schema is written.

Design decisions (see planning/TELEGRAM_PIPELINE.md §5 and the report of 2026-10-22):
  * KAB (glide bomb) launches/tracks are frontline fire, not strike waves. They never open, extend or bridge a
    wave; they are counted (`n_kab_launches_in_window`) when they fall inside one.
  * Monitor channels' `launch`-typed posts are not in extract/launches.parquet (kpszsu only). They are read from
    posts_typed here with a small weapon-class regex so that Shahed / ballistic launch calls from monitors can
    open waves and give launch timestamps. Tier C: never evidence of impact.
  * launch_intel opens a wave only in an active status (takeoff, airborne, active, launch_likely,
    launch_confirmed). inactive / landed / false_alarm / unknown status rows are linked but never open one.
  * Lags: `launch_ts_<class>` = first confirmed launch of that weapon class in the wave (kpszsu launch post with
    event_kind launch/repeat_launch, monitor 'пуск/запуск/вихід' post, or launch_intel status launch_confirmed);
    `first_track_ts_<class>` = first track of that class at or after it. Threat warnings do not count as launches.
    `takeoff_ts` = first launch_intel takeoff/airborne in the wave (strategic aviation only).
  * Kyiv city != Kyiv oblast. A track "reaches Kyiv" when oblast_iso == UA-30 (city) or the settlement is Київ in a
    location role with no other oblast; it "heads toward Kyiv" when heading_raw names Київ/Києва (not Київщина) or
    Київ is the settlement in a target role.
  * Noon cut. From mid-2026 the Air Force posts drone tracks around the clock, so a QUIET_H gap never occurs and the
    spec rule alone merges weeks into one wave (first run: a 1,012 h wave spanning 43 nights). Activity sessions are
    therefore also cut at 12:00 Europe/Kyiv, the boundary the Air Force's own "У ніч на" summaries imply. The
    uncut session id is kept in `session_id` / `split_at_noon` so waves can be re-merged.
"""
from __future__ import annotations
import json, re, sys, datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import INTERIM, DERIVED, write_meta, log, kyiv_flags

EXTRACT = INTERIM / "extract"
TRACKS, LAUNCHES, INTEL, SUMM = (EXTRACT / f"{n}.parquet" for n in ("tracks", "launches", "launch_intel", "summaries"))
IMPACTS = EXTRACT / "impacts.parquet"
TYPED = INTERIM / "posts_typed.parquet"
OUT_WAVES = DERIVED / "launch_waves.parquet"
OUT_LINKS = INTERIM / "link" / "wave_links.parquet"          # event -> wave_id (interim: has text_span-free ids only)
OUT_STRIKES = DERIVED / "strike_events.parquet"
LINK_VERSION = "waves-1+strikes-1"
QUIET_H = 2.0
LAG_DAYS = 7
ACTIVE_STATUS = {"takeoff", "airborne", "active", "launch_likely", "launch_confirmed"}
PLATFORM_CLASS = {"Tu-95": "cruise", "Tu-160": "cruise", "Tu-22M3": "cruise", "strategic_aviation": "cruise",
                  "ship": "cruise", "submarine": "cruise", "MiG-31K": "kinzhal", "ground": "ballistic",
                  "tactical": "kab", "other_aircraft": "unknown"}
LAG_CLASSES = ["cruise", "ballistic", "kinzhal", "shahed"]
CLUSTER_H = 3.0      # incidents of one place within ±3 h -> one event
UPDATE_H = 48.0      # an is_update row joins the nearest event of its place within ±48 h
# specificity order for weapon_class across an event's sources (most specific first)
WEAPON_SPECIFICITY = ["kinzhal", "ballistic", "cruise", "kab", "jet_uav", "shahed", "fpv", "recon_uav", "artillery", "missile", "unknown"]
CONF_RANK = {"high": 0, "medium": 1, "low": 2}
STRIKE_SCHEMA = pa.schema([("event_id", pa.string()), ("event_ts", pa.timestamp("ns", tz="UTC")), ("time_is_post_time", pa.bool_()),
                           ("ts_precision", pa.string()), ("event_date_kyiv", pa.date32()),
                           ("oblast_iso", pa.string()), ("raion_raw", pa.string()), ("settlement_raw", pa.string()),
                           ("loc_key_level", pa.string()), ("geo_id", pa.int64()), ("geo_level", pa.string()), ("geo_conf", pa.float64()),
                           ("lat", pa.float64()), ("lon", pa.float64()), ("h3_r5", pa.string()), ("weapon_class", pa.string()),
                           ("target_type", pa.string()), ("killed", pa.int64()), ("wounded", pa.int64()), ("is_debris_only", pa.bool_()),
                           ("location_withheld", pa.bool_()), ("tier", pa.string()), ("n_sources", pa.int64()), ("n_incidents", pa.int64()),
                           ("n_updates", pa.int64()), ("update_only", pa.bool_()), ("channels", pa.list_(pa.string())),
                           ("source_msg_ids", pa.list_(pa.string())), ("wave_id", pa.string()), ("confidence", pa.string()),
                           ("link_version", pa.string())])
MON_CLASS = [("kinzhal", re.compile(r"Кинджал|МіГ-31", re.I)),
             ("kab", re.compile(r"\bКАБ|авіаційн\w*\s+бомб|плануюч", re.I)),
             ("ballistic", re.compile(r"баліст|ОТРК|Іскандер|С-300|С-400|KN-23", re.I)),
             ("cruise", re.compile(r"Х-?\s?(101|555|22|32|59|69)|крилат|Калібр|стратегічн|дальн\w* авіац|Ту-95|Ту-160|Ту-22", re.I)),
             ("shahed", re.compile(r"шахед|shahed|БпЛА|дрон|герань|мопед", re.I))]
MON_LAUNCH_RE = re.compile(r"пуск|запуск|вихід|виход|старт", re.I)


def monitor_class(text: str) -> str:
    for cls, rx in MON_CLASS:
        if rx.search(text):
            return cls
    return "unknown"


def load_events() -> pd.DataFrame:
    """One long table of events: ts_utc, kind, channel, msg_id, weapon_class, is_launch_confirmed, platform,
    oblast_iso, kyiv_city, kyiv_heading, kab."""
    tr = pd.read_parquet(TRACKS, columns=["ts_utc", "channel", "msg_id", "seg_idx", "weapon_class", "oblast_iso",
                                           "settlement_raw", "settlement_role", "heading_raw", "count"])
    tr["kind"] = "track"
    tr["kyiv_city"], tr["kyiv_heading"], tr["kyiv_oblast"] = kyiv_flags(tr)
    tr["launch_confirmed"] = False
    tr["platform"] = None

    la = pd.read_parquet(LAUNCHES, columns=["ts_utc", "channel", "msg_id", "event_kind", "weapon_class", "target_oblast_raw"])
    la["kind"] = "launch"
    la["launch_confirmed"] = la.event_kind.isin(["launch", "repeat_launch"])
    la["seg_idx"] = 0
    la["platform"] = None

    li = pd.read_parquet(INTEL, columns=["ts_utc", "channel", "msg_id", "platform", "status", "weapon_hint", "location_key"])
    li["kind"] = "launch_intel"
    li["weapon_class"] = li.weapon_hint.where(li.weapon_hint.notna() & ~li.weapon_hint.isin(["unknown"]),
                                              li.platform.map(PLATFORM_CLASS)).fillna("unknown")
    li["active"] = li.status.isin(ACTIVE_STATUS)
    li["launch_confirmed"] = li.status.eq("launch_confirmed")
    li["seg_idx"] = 0

    typed = pd.read_parquet(TYPED, columns=["channel", "msg_id", "ts_utc", "post_type", "text_norm"])
    mon = typed[(typed.post_type == "launch") & (typed.channel != "kpszsu")].copy()
    mon["kind"] = "launch"
    mon["weapon_class"] = mon.text_norm.map(monitor_class)
    mon["launch_confirmed"] = mon.text_norm.str.contains(MON_LAUNCH_RE) & ~mon.text_norm.str.contains(r"загроз|небезпек", case=False, regex=True)
    mon["seg_idx"] = 0
    mon["platform"] = None
    mon = mon.drop(columns=["post_type", "text_norm"])
    al = typed[typed.post_type.isin(["alert", "all_clear"])][["channel", "msg_id", "ts_utc", "post_type"]].rename(columns={"post_type": "kind"})
    al["weapon_class"] = None; al["launch_confirmed"] = False; al["seg_idx"] = 0; al["platform"] = None
    del typed

    cols = ["ts_utc", "kind", "channel", "msg_id", "seg_idx", "weapon_class", "launch_confirmed", "platform", "oblast_iso",
            "kyiv_city", "kyiv_heading", "kyiv_oblast", "active", "location_key", "count", "status"]
    ev = pd.concat([tr, la, li, mon, al], ignore_index=True, sort=False).reindex(columns=cols)
    for c in ("active", "kyiv_city", "kyiv_heading", "kyiv_oblast", "launch_confirmed"):
        ev[c] = ev[c].map(lambda v: bool(v) if v is not None and v == v else False).astype(bool)
    ev["is_kab"] = ev.weapon_class.eq("kab")
    ev = ev.sort_values(["ts_utc", "kind", "msg_id", "seg_idx"], kind="mergesort").reset_index(drop=True)
    return ev


def build_waves(ev: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    # activity = non-KAB tracks + non-KAB launches + active launch_intel
    act_mask = (~ev.is_kab) & ((ev.kind == "track") | (ev.kind == "launch") | ((ev.kind == "launch_intel") & ev.active))
    act = ev[act_mask]
    gap_h = act.ts_utc.diff().dt.total_seconds().div(3600)
    session_raw = (gap_h > QUIET_H).cumsum().values
    noon_day = (act.ts_utc.dt.tz_convert("Europe/Kyiv") - pd.Timedelta(hours=12)).dt.strftime("%Y%m%d").values
    act = act.assign(session_raw=session_raw, noon_day=noon_day)
    act["session"] = pd.factorize(act.session_raw.astype(str) + "_" + act.noon_day)[0]
    pieces_per_raw = act.groupby("session_raw").session.nunique()
    opener = act[act.kind.isin(["launch", "launch_intel"])]
    first_open = opener.groupby("session").ts_utc.min()
    sess = act.groupby("session").agg(first_activity_ts=("ts_utc", "min"), last_activity_ts=("ts_utc", "max"), session_raw=("session_raw", "first"))
    sess["split_at_noon"] = sess.session_raw.map(pieces_per_raw) > 1
    sess["session_id"] = "S" + sess.session_raw.astype(str)
    sess = sess.drop(columns="session_raw")
    sess["start_ts"] = first_open
    sess = sess[sess.start_ts.notna()]                      # sessions with no launch post are not waves
    sess["next_start_ts"] = sess.first_activity_ts.shift(-1)
    # end = last all_clear in (last_activity, min(last_activity+QUIET_H, next session first activity)]
    ac = ev[ev.kind == "all_clear"].ts_utc.dt.tz_convert(None).values.astype("datetime64[ns]")
    ends, end_method = [], []
    for r in sess.itertuples():
        hi = r.last_activity_ts + pd.Timedelta(hours=QUIET_H)
        if pd.notna(r.next_start_ts):
            hi = min(hi, r.next_start_ts)
        noon = (r.last_activity_ts.tz_convert("Europe/Kyiv") - pd.Timedelta(hours=12)).normalize() + pd.Timedelta(hours=36)  # next 12:00 Kyiv
        hi = min(hi, (noon - pd.Timedelta(seconds=1)).tz_convert("UTC"))
        i0 = np.searchsorted(ac, np.datetime64(r.start_ts.tz_convert(None))); i1 = np.searchsorted(ac, np.datetime64(hi.tz_convert(None)), side="right")
        if i1 > i0:
            ends.append(pd.Timestamp(ac[i1 - 1]).tz_localize("UTC")); end_method.append("all_clear")
        else:
            ends.append(hi); end_method.append("quiet_timeout")
    sess["end_ts"] = pd.to_datetime(pd.Series(ends, index=sess.index), utc=True); sess["end_method"] = end_method
    sess = sess.reset_index()
    sess["wave_id"] = ["W" + pd.Timestamp(t).strftime("%Y%m%d-%H%M") for t in sess.start_ts]
    sess = sess.set_index("session")

    # link every event inside [start, end]
    starts = sess.start_ts.dt.tz_convert(None).values.astype("datetime64[ns]"); ends_ = sess.end_ts.dt.tz_convert(None).values.astype("datetime64[ns]")
    ts = ev.ts_utc.dt.tz_convert(None).values.astype("datetime64[ns]")
    idx = np.searchsorted(starts, ts, side="right") - 1
    ok = (idx >= 0) & (ts <= ends_[np.clip(idx, 0, len(ends_) - 1)])
    ev = ev.assign(wave_id=np.where(ok, sess.wave_id.values[np.clip(idx, 0, len(ends_) - 1)], None))
    ev["wave_id"] = ev.wave_id.astype("string")
    linked = ev[ev.wave_id.notna()]

    g = linked.groupby("wave_id")
    uniq = lambda s: sorted({x for x in s.dropna() if x not in ("unknown", "")})
    w = sess.reset_index(drop=True).set_index("wave_id")
    w["duration_h"] = (w.end_ts - w.start_ts).dt.total_seconds() / 3600
    w["start_kind"] = linked[linked.ts_utc.values == w.loc[linked.wave_id, "start_ts"].values].groupby("wave_id").kind.agg(
        lambda s: "launch" if "launch" in set(s) else "launch_intel")
    w["start_channel"] = linked[linked.ts_utc.values == w.loc[linked.wave_id, "start_ts"].values].groupby("wave_id").channel.first()
    w["platforms"] = g.platform.agg(uniq)
    w["weapon_classes"] = linked[linked.kind.isin(["track", "launch"])].groupby("wave_id").weapon_class.agg(uniq)
    w["launch_sites"] = g.location_key.agg(uniq)
    trk = linked[(linked.kind == "track") & ~linked.is_kab]
    w["n_tracks"] = trk.groupby("wave_id").size()
    w["n_track_posts"] = trk.groupby("wave_id").msg_id.nunique()
    w["n_tracks_kpszsu"] = trk[trk.channel == "kpszsu"].groupby("wave_id").size()
    w["oblasts_tracked"] = trk.groupby("wave_id").oblast_iso.agg(uniq)
    for c in ("platforms", "weapon_classes", "launch_sites", "oblasts_tracked"):
        w[c] = w[c].map(lambda v: v if isinstance(v, list) else [])
    w["n_oblasts_tracked"] = w.oblasts_tracked.map(len)
    w["n_tracks_kyiv_city"] = trk[trk.kyiv_city].groupby("wave_id").size()
    w["n_tracks_toward_kyiv"] = trk[trk.kyiv_heading].groupby("wave_id").size()
    w["n_tracks_kyiv_oblast"] = trk[trk.kyiv_oblast].groupby("wave_id").size()
    for cls in ["shahed", "jet_uav", "cruise", "ballistic", "kinzhal", "recon_uav", "unknown"]:
        w[f"n_tracks_{cls}"] = trk[trk.weapon_class == cls].groupby("wave_id").size()
    w["n_launch_posts"] = linked[(linked.kind == "launch") & ~linked.is_kab].groupby("wave_id").size()
    w["n_launch_confirmed"] = linked[(linked.kind == "launch") & linked.launch_confirmed & ~linked.is_kab].groupby("wave_id").size()
    w["n_launch_intel"] = linked[linked.kind == "launch_intel"].groupby("wave_id").size()
    w["n_kab_launches_in_window"] = linked[(linked.kind == "launch") & linked.is_kab].groupby("wave_id").size()
    w["n_alerts"] = linked[linked.kind == "alert"].groupby("wave_id").size()
    w["n_all_clear"] = linked[linked.kind == "all_clear"].groupby("wave_id").size()
    w["takeoff_ts"] = linked[(linked.kind == "launch_intel") & linked.status.isin(["takeoff", "airborne"])
                             & linked.platform.isin(["Tu-95", "Tu-160", "Tu-22M3", "strategic_aviation"])].groupby("wave_id").ts_utc.min()
    w["first_track_ts"] = trk.groupby("wave_id").ts_utc.min()
    conf = linked[linked.launch_confirmed & ~linked.is_kab]
    for cls in LAG_CLASSES:
        lts = conf[conf.weapon_class == cls].groupby("wave_id").ts_utc.min().rename("l")
        t = trk[trk.weapon_class == cls][["wave_id", "ts_utc"]].merge(lts, left_on="wave_id", right_index=True)
        ftt = t[t.ts_utc >= t.l].groupby("wave_id").ts_utc.min()
        w[f"launch_ts_{cls}"] = lts
        w[f"first_track_ts_{cls}"] = ftt
        w[f"lag_min_{cls}"] = (ftt - lts).dt.total_seconds().div(60)
    tc = trk[trk.weapon_class == "cruise"][["wave_id", "ts_utc"]].merge(w.takeoff_ts.dropna().rename("t"), left_on="wave_id", right_index=True)
    w["first_cruise_track_after_takeoff_ts"] = tc[tc.ts_utc >= tc.t].groupby("wave_id").ts_utc.min()
    w["takeoff_to_first_cruise_track_min"] = (w.first_cruise_track_after_takeoff_ts - w.takeoff_ts).dt.total_seconds().div(60)
    w["channels"] = g.channel.agg(uniq).map(lambda v: v if isinstance(v, list) else [])
    w["source_msg_ids"] = g.apply(lambda d: sorted({f"{c}:{m}" for c, m in zip(d.channel, d.msg_id)}), include_groups=False)
    w["n_source_posts"] = w.source_msg_ids.map(len)
    for c in w.columns:
        if c.startswith("n_"):
            w[c] = w[c].fillna(0).astype("int64")
    # Kyiv-time context
    sk = w.start_ts.dt.tz_convert("Europe/Kyiv")
    w["start_ts_kyiv"] = sk
    w["end_ts_kyiv"] = w.end_ts.dt.tz_convert("Europe/Kyiv")
    w["start_hour_kyiv"] = sk.dt.hour
    w["starts_night"] = (sk.dt.hour >= 18) | (sk.dt.hour < 6)
    # night_date: the morning the night ends on (Air Force "У ніч на <night_date>")
    w["night_date"] = (sk + pd.Timedelta(hours=12)).dt.date
    w["n_nights_spanned"] = ((w.end_ts_kyiv + pd.Timedelta(hours=12)).dt.normalize() - (sk + pd.Timedelta(hours=12)).dt.normalize()).dt.days + 1
    w["link_version"] = LINK_VERSION
    w = w.reset_index()
    links = linked[["wave_id", "kind", "channel", "msg_id", "seg_idx", "ts_utc", "weapon_class", "is_kab"]].reset_index(drop=True)
    return w, links


def attach_summaries(w: pd.DataFrame) -> pd.DataFrame:
    s = pd.read_parquet(SUMM, columns=["msg_id", "night_date", "period_kind", "total_launched", "destroyed_total", "parse_status"])
    s = s[(s.period_kind == "night") & s.night_date.notna()].sort_values(["night_date", "total_launched"], na_position="first")
    one = s.groupby("night_date").tail(1).rename(columns={"msg_id": "summary_msg_id", "total_launched": "summary_total_launched",
                                                          "destroyed_total": "summary_destroyed_total", "parse_status": "summary_parse_status"})
    one = one.drop(columns="period_kind")
    out = w.merge(one, on="night_date", how="left")
    out["summary_msg_id"] = out.summary_msg_id.astype("Int64")
    return out


def _place_key(r) -> tuple:
    """(level, key) for clustering. geo_id when the place resolved, else raw raion / settlement string within the oblast."""
    if r.geo_id == r.geo_id and r.geo_id is not None:
        return "geo", f"g:{int(r.geo_id)}"
    ob = r.oblast_iso_canon if isinstance(r.oblast_iso_canon, str) else "?"
    if isinstance(r.raion_raw, str) and r.raion_raw.strip():
        return "raion_str", f"r:{ob}:{r.raion_raw.strip().lower()}"
    if isinstance(r.settlement_raw, str) and r.settlement_raw.strip():
        return "settlement_str", f"s:{ob}:{r.settlement_raw.strip().lower()}"
    return "oblast", f"o:{ob}"


def _chain(ts: np.ndarray, date_only: np.ndarray, day: np.ndarray) -> np.ndarray:
    """Single-link cluster ids for one place key. ts sorted ascending (ns int64). Consecutive rows link when the gap is
    <= CLUSTER_H, or when either is date-only and both fall on the same Kyiv date."""
    if len(ts) == 0:
        return np.zeros(0, dtype=np.int64)
    gap_ok = np.diff(ts) <= np.int64(CLUSTER_H * 3600e9)
    same_day = (day[1:] == day[:-1]) & (date_only[1:] | date_only[:-1])
    brk = ~(gap_ok | same_day)
    return np.concatenate([[0], np.cumsum(brk)])


def cluster_impacts(imp: pd.DataFrame) -> pd.DataFrame:
    """-> impacts with cluster_ts, ts_precision, loc_level, loc_key, cluster (int event index)."""
    imp = imp.copy()
    kyiv_noon = pd.to_datetime(imp.event_date, errors="coerce").dt.tz_localize("Europe/Kyiv", ambiguous="NaT", nonexistent="shift_forward") + pd.Timedelta(hours=12)
    imp["cluster_ts"] = imp.event_ts_utc.where(imp.event_ts_utc.notna(), kyiv_noon.dt.tz_convert("UTC"))
    imp["cluster_ts"] = imp.cluster_ts.where(imp.cluster_ts.notna(), imp.post_ts_utc)   # 26 rows with no date at all
    imp["ts_precision"] = np.where(imp.event_ts_utc.isna(), "date", np.where(imp.time_is_post_time.astype(bool), "post_time", "time"))
    imp["date_kyiv"] = imp.cluster_ts.dt.tz_convert("Europe/Kyiv").dt.date.astype(str)
    lk = [_place_key(r) for r in imp.itertuples()]
    imp["loc_level"] = [a for a, _ in lk]; imp["loc_key"] = [b for _, b in lk]
    imp = imp.sort_values(["loc_key", "cluster_ts"], kind="mergesort").reset_index(drop=True)
    imp["cluster"] = -1
    nxt = 0
    base = imp[~imp.is_update]
    for key, g in base.groupby("loc_key", sort=False):
        ids = _chain(g.cluster_ts.values.astype("datetime64[ns]").astype(np.int64), (g.ts_precision == "date").values, g.date_kyiv.values)
        imp.loc[g.index, "cluster"] = ids + nxt
        nxt += int(ids.max()) + 1
    # updates: nearest non-update event of the same key within UPDATE_H, else cluster among themselves
    ev_ts = imp[imp.cluster >= 0].groupby("cluster").cluster_ts.min()
    ev_key = imp[imp.cluster >= 0].groupby("cluster").loc_key.first()
    by_key = {k: (v.cluster_ts.values.astype("datetime64[ns]").astype(np.int64), v.index.values)
              for k, v in pd.DataFrame({"cluster_ts": ev_ts, "loc_key": ev_key}).sort_values("cluster_ts").groupby("loc_key")}
    upd = imp[imp.is_update]
    assigned = {}
    lim = np.int64(UPDATE_H * 3600e9)
    for key, g in upd.groupby("loc_key", sort=False):
        if key in by_key:
            ets, eid = by_key[key]
            for i, t in zip(g.index, g.cluster_ts.values.astype("datetime64[ns]").astype(np.int64)):
                j = np.searchsorted(ets, t)
                cands = [c for c in (j - 1, j) if 0 <= c < len(ets) and abs(ets[c] - t) <= lim]
                if cands:
                    c = min(cands, key=lambda c: abs(ets[c] - t)); assigned[i] = int(eid[c])
    imp.loc[list(assigned), "cluster"] = pd.Series(assigned)
    rest = imp[imp.is_update & (imp.cluster < 0)]
    for key, g in rest.groupby("loc_key", sort=False):
        ids = _chain(g.cluster_ts.values.astype("datetime64[ns]").astype(np.int64), (g.ts_precision == "date").values, g.date_kyiv.values)
        imp.loc[g.index, "cluster"] = ids + nxt
        nxt += int(ids.max()) + 1
    return imp


def _mode(s: pd.Series, last=("unknown",)):
    vc = s.dropna().value_counts()
    vc = vc[~vc.index.isin(last)] if (~vc.index.isin(last)).any() else vc
    return vc.index[0] if len(vc) else None


def build_strike_events(waves: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    imp = pd.read_parquet(IMPACTS)
    need = {"geo_id", "oblast_iso_canon", "weapon_class_canon", "lat"}
    if not need <= set(imp.columns):
        raise SystemExit("impacts.parquet lacks resolve columns: run 30_resolve.py first")
    imp = cluster_impacts(imp)
    imp["post_key"] = imp.channel + "/" + imp.msg_id.astype(str)
    g = imp.groupby("cluster", sort=True)
    prec_rank = imp.ts_precision.map({"time": 0, "post_time": 1, "date": 2})
    # event_ts: earliest incident of the best precision present
    best = imp.assign(_pr=prec_rank).sort_values(["cluster", "_pr", "cluster_ts"]).groupby("cluster").head(1).set_index("cluster")
    ev = pd.DataFrame(index=g.size().index)
    ev["event_ts"] = best.cluster_ts
    ev["ts_precision"] = best.ts_precision
    ev["time_is_post_time"] = best.ts_precision.eq("post_time")
    ev["event_date_kyiv"] = ev.event_ts.dt.tz_convert("Europe/Kyiv").dt.date
    ev["oblast_iso"] = g.oblast_iso_canon.agg(_mode)
    ev["raion_raw"] = g.raion_raw.agg(_mode)
    ev["settlement_raw"] = g.settlement_raw.agg(_mode)
    ev["loc_key_level"] = g.loc_level.first()
    geo = imp[imp.geo_id.notna()].sort_values("geo_conf", ascending=False).groupby("cluster").head(1).set_index("cluster")
    for c in ("geo_id", "geo_level", "geo_conf", "lat", "lon", "h3_r5"):
        ev[c] = geo[c]
    spec = {c: i for i, c in enumerate(WEAPON_SPECIFICITY)}
    ev["weapon_class"] = g.weapon_class_canon.agg(lambda s: min((x for x in s.dropna()), key=lambda x: spec.get(x, 99), default=None))
    ev["target_type"] = g.target_type.agg(_mode)
    ev["killed"] = g.killed.max(); ev["wounded"] = g.wounded.max()
    ev["is_debris_only"] = g.is_debris_only.all()
    ev["location_withheld"] = g.location_withheld.all()
    ev["tier"] = "A"
    ev["n_sources"] = g.post_key.nunique()
    ev["n_incidents"] = g.size()
    ev["n_updates"] = g.is_update.sum().astype(int)
    ev["update_only"] = g.is_update.all()
    ev["channels"] = g.channel.agg(lambda s: sorted(set(s)))
    ev["source_msg_ids"] = g.post_key.agg(lambda s: sorted(set(s)))
    ev["confidence"] = g.confidence.agg(lambda s: min(s.dropna(), key=lambda x: CONF_RANK.get(x, 9), default=None))
    # wave: [start_ts, end_ts] containing event_ts (waves are disjoint in time)
    wv = waves.sort_values("start_ts")
    st = wv.start_ts.dt.tz_convert(None).values.astype("datetime64[ns]"); en = wv.end_ts.dt.tz_convert(None).values.astype("datetime64[ns]")
    ts = ev.event_ts.dt.tz_convert(None).values.astype("datetime64[ns]")
    idx = np.searchsorted(st, ts, side="right") - 1
    ok = (idx >= 0) & (ts <= en[np.clip(idx, 0, len(en) - 1)])
    ev["wave_id"] = np.where(ok, wv.wave_id.values[np.clip(idx, 0, len(en) - 1)], None)
    ev = ev.sort_values(["event_ts", "oblast_iso"], kind="mergesort").reset_index(drop=True)
    ev["event_id"] = ["E" + t.strftime("%Y%m%d-%H%M") + f"-{i:04d}" for i, t in enumerate(ev.event_ts.dt.tz_convert("UTC"))]
    ev["link_version"] = LINK_VERSION
    ev["killed"] = ev.killed.astype("Int64"); ev["wounded"] = ev.wounded.astype("Int64"); ev["geo_id"] = ev.geo_id.astype("Int64")
    ev["wave_id"] = ev.wave_id.astype("string")
    ev = ev[[f.name for f in STRIKE_SCHEMA]]
    stats = {"impacts_rows": int(len(imp)), "impacts_updates": int(imp.is_update.sum()),
             "events": int(len(ev)), "events_update_only": int(ev.update_only.sum()),
             "updates_merged_rows": int(ev.n_updates[~ev.update_only].sum()),
             "updates_standalone_rows": int(ev.n_updates[ev.update_only].sum()),
             "events_multi_source": int((ev.n_sources > 1).sum()), "events_multi_incident": int((ev.n_incidents > 1).sum()),
             "events_with_coords": int(ev.lat.notna().sum()), "events_with_wave": int(ev.wave_id.notna().sum()),
             "loc_key_level": ev.loc_key_level.value_counts().to_dict(), "ts_precision": ev.ts_precision.value_counts().to_dict(),
             "by_oblast": ev.oblast_iso.value_counts().to_dict(), "by_weapon_class": ev.weapon_class.fillna("<none>").value_counts().to_dict(),
             "by_year": ev.event_ts.dt.year.value_counts().sort_index().to_dict(),
             "killed_sum_of_event_max": int(ev.killed.sum()), "wounded_sum_of_event_max": int(ev.wounded.sum()),
             "kyiv_city_events": int((ev.oblast_iso == "UA-30").sum()), "kyiv_oblast_events": int((ev.oblast_iso == "UA-32").sum())}
    return ev, stats


def write_strike_events(waves: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    if not IMPACTS.exists():
        log("impacts.parquet absent: writing empty strike_events with schema")
        pq.write_table(STRIKE_SCHEMA.empty_table(), OUT_STRIKES)
        meta = {"output": str(OUT_STRIKES.relative_to(DERIVED.parents[2])), "status": "stub",
                "reason": "extract/impacts.parquet absent (23_extract_impacts.py not run); schema only, 0 rows",
                "written_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "link_version": LINK_VERSION, "counts": {"rows": 0}}
        OUT_STRIKES.with_name("strike_events_meta.json").write_text(json.dumps(meta, indent=2))
        return pd.DataFrame(columns=[f.name for f in STRIKE_SCHEMA])
    ev, stats = build_strike_events(waves)
    n_all = len(ev)
    ev = ev[ev.event_ts < cutoff].reset_index(drop=True)
    pq.write_table(pa.Table.from_pandas(ev, schema=STRIKE_SCHEMA, preserve_index=False), OUT_STRIKES)
    stats.update(rows=int(len(ev)), rows_before_lag_cut=int(n_all))
    write_meta(OUT_STRIKES, inputs={"impacts": IMPACTS, "waves": OUT_WAVES}, counts=stats,
               extra={"link_version": LINK_VERSION, "cluster_hours": CLUSTER_H, "update_hours": UPDATE_H, "lag_days": LAG_DAYS,
                      "cutoff_event_ts_utc": str(cutoff), "weapon_specificity": WEAPON_SPECIFICITY,
                      "notes": ["killed/wounded = max over an event's sources incl. updates (as last reported), never summed",
                                "date-only incidents placed at 12:00 Europe/Kyiv (ts_precision='date')",
                                "raion_raw/settlement_raw are place names as the extractor returned them, no post text"]})
    log(f"strike_events: {len(ev):,} events from {stats['impacts_rows']:,} incidents; {stats['events_with_coords']:,} with coords; "
        f"{stats['events_with_wave']:,} inside a wave")
    return ev


def main() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True); OUT_LINKS.parent.mkdir(parents=True, exist_ok=True)
    ev = load_events()
    log(f"events: {len(ev):,} " + json.dumps(ev.kind.value_counts().to_dict()))
    w, links = build_waves(ev)
    w = attach_summaries(w)
    cutoff = pd.Timestamp(dt.date.today() - dt.timedelta(days=LAG_DAYS), tz="UTC")
    n_all = len(w)
    w = w[w.start_ts < cutoff].sort_values("start_ts").reset_index(drop=True)
    links = links[links.wave_id.isin(w.wave_id)]
    links.to_parquet(OUT_LINKS, index=False)
    w.to_parquet(OUT_WAVES, index=False)            # written first so write_meta can hash it as a strike_events input
    se = write_strike_events(w, cutoff)
    n_imp = se.groupby("wave_id").size() if len(se) else pd.Series(dtype="int64")
    w["n_impacts_linked"] = w.wave_id.map(n_imp).fillna(0).astype("int64")
    w["n_impacts_linked_kyiv_city"] = w.wave_id.map(se[se.oblast_iso == "UA-30"].groupby("wave_id").size() if len(se) else pd.Series(dtype="int64")).fillna(0).astype("int64")
    w.to_parquet(OUT_WAVES, index=False)
    yrs = w.start_ts.dt.year
    counts = {
        "rows": int(len(w)), "rows_before_lag_cut": int(n_all), "linked_events": int(len(links)),
        "waves_by_year": yrs.value_counts().sort_index().to_dict(),
        "start_kind": w.start_kind.value_counts().to_dict(), "end_method": w.end_method.value_counts().to_dict(),
        "waves_split_at_noon": int(w.split_at_noon.sum()), "raw_sessions": int(w.session_id.nunique()),
        "waves_multi_night": int((w.n_nights_spanned > 1).sum()), "zero_track_waves": int((w.n_tracks == 0).sum()),
        "median_duration_h": round(float(w.duration_h.median()), 2),
        "median_duration_h_by_year": w.groupby(yrs).duration_h.median().round(2).to_dict(),
        "p90_duration_h_by_year": w.groupby(yrs).duration_h.quantile(0.9).round(1).to_dict(),
        "waves_with_summary": int(w.summary_msg_id.notna().sum()),
        "waves_reaching_kyiv_city": int((w.n_tracks_kyiv_city > 0).sum()),
        "lag_n": {c: int(w[f"lag_min_{c}"].notna().sum()) for c in LAG_CLASSES},
        "lag_median_min": {c: (round(float(w[f"lag_min_{c}"].median()), 1) if w[f"lag_min_{c}"].notna().any() else None) for c in LAG_CLASSES},
        "takeoff_to_first_cruise_track_median_min": round(float(w.takeoff_to_first_cruise_track_min.median()), 1),
        "share_tracks_linked": round(float(links[links.kind == "track"].shape[0] / (ev.kind == "track").sum()), 4),
        "strike_events_linked": int(w.n_impacts_linked.sum()), "waves_with_impacts": int((w.n_impacts_linked > 0).sum()),
    }
    write_meta(OUT_WAVES, inputs={"tracks": TRACKS, "launches": LAUNCHES, "launch_intel": INTEL, "summaries": SUMM, "posts_typed": TYPED},
               counts=counts, extra={"link_version": LINK_VERSION, "quiet_hours": QUIET_H, "lag_days": LAG_DAYS, "cutoff_start_utc": str(cutoff),
                                     "links_table": str(OUT_LINKS.relative_to(DERIVED.parents[2])), "kab_excluded_from_activity": True,
                                     "noon_cut_kyiv_hour": 12})
    log(json.dumps(counts, default=str))


if __name__ == "__main__":
    main()
