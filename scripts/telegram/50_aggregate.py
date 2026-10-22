"""L6: publishable aggregates.
  national_night.csv      one row per night from extract/summaries.parquet, cross-checked against the Ivaniuk Kaggle
                          dataset (data/raw/ivaniuk_missile_attacks), joined to launch_waves (n_waves_night, ...).
  launch_waves_week.csv   ISO week x wave counts by start kind / platform / weapon class, durations, lags.
  kyiv_tracks_week.csv    ISO week x tracks over Kyiv city (UA-30) or heading toward Kyiv city; oblast (UA-32) kept
                          as a separate column, never merged (TELEGRAM_PIPELINE.md §5 "Oblast != city").
  impacts_cellweek.csv    H3 res-5 cell x ISO week x weapon_class x tier -> n_events, n_sources, killed, wounded, from
                          strike_events with coordinates. impacts_oblastweek.csv is the same for events without
                          coordinates (oblast x week), so nothing is silently dropped.
  kyiv_strikes_week.csv   ISO week x n_waves_reaching_kyiv (tracks over UA-30), n_impacts_tier_A (strike events in Kyiv
                          city, UA-30), n_impacts_kyiv_oblast (UA-32, separate column), n_tracks_toward_kyiv,
                          n_alert_hours (VA_Kyiv alert -> next all_clear, state machine, capped at ALERT_CAP_H, week of
                          the alert start), killed/wounded in the city. H12 input.
  firms_match_cellweek.csv  (published) h3_r5 x ISO week x weapon_class: events, FIRMS matches, placebo matches.
  link/firms_match_events.csv (INTERIM ONLY, event-level, finer than PREREG §7) one row per tier-A strike event with coordinates: nearest FIRMS VIIRS detection (SNPP, NOAA-20,
                          NOAA-21; SP + NRT from data/raw/firms_api/ukraine) within FIRMS_RADIUS_M in
                          [event_ts - 1 h, event_ts + 12 h] (date-only events: the whole Kyiv date - 1 h .. + 12 h,
                          window_kind='date'), plus a placebo column for the same place and window 7 days earlier.
                          Observability covariates (ERA5 cloud / snow) are not attached yet (meta says so).
All derived tables carry msg_ids / counts only and respect the >= LAG_DAYS lag.

No raw text leaves data/interim: the derived CSV carries msg_ids and numbers only. The disagreement list
with both texts is written to data/interim/telegram/extract/qa_ivaniuk_disagreements.csv.
"""
from __future__ import annotations
import json, sys, datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, INTERIM, DERIVED, write_meta, log, kyiv_flags

SUMM = INTERIM / "extract" / "summaries.parquet"
TYPED = INTERIM / "posts_typed.parquet"
IVA = ROOT / "data" / "raw" / "ivaniuk_missile_attacks" / "extracted" / "missile_attacks_daily.csv"
OUT = DERIVED / "national_night.csv"
WAVES = DERIVED / "launch_waves.parquet"
LINKS = INTERIM / "link" / "wave_links.parquet"
TRACKS = INTERIM / "extract" / "tracks.parquet"
OUT_WAVES_WEEK = DERIVED / "launch_waves_week.csv"
OUT_KYIV_WEEK = DERIVED / "kyiv_tracks_week.csv"
LAG_CLASSES = ["cruise", "ballistic", "kinzhal", "shahed"]
QA_DIR = DERIVED / "qa"
LAG_DAYS = 7
STRIKES = DERIVED / "strike_events.parquet"
TYPED_FINAL = INTERIM / "posts_typed_final.parquet"
FIRMS_DIR = ROOT / "data" / "raw" / "firms_api" / "ukraine"
OUT_CELLWEEK = DERIVED / "impacts_cellweek.csv"
OUT_OBLWEEK = DERIVED / "impacts_oblastweek.csv"
OUT_KYIV_STRIKES = DERIVED / "kyiv_strikes_week.csv"
OUT_FIRMS = INTERIM / "link" / "firms_match_events.csv"      # event-level: interim only (finer than PREREG §7)
OUT_FIRMS_CW = DERIVED / "firms_match_cellweek.csv"           # published: h3_r5 x ISO week x weapon_class
FIRMS_RADIUS_M = 1000.0
FIRMS_RADIUS_WIDE_M = 3000.0   # diagnostic only: settlement centroids sit km from the actual hit in towns
FIRMS_BEFORE_H, FIRMS_AFTER_H = 1.0, 12.0
PLACEBO_DAYS = 7
ALERT_CAP_H = 12.0
CATEGORY_BREAK = dt.date(2026, 8, 10)  # Air Force stopped reporting some per-type counts


def ivaniuk_nights() -> pd.DataFrame:
    d = pd.read_csv(IVA)
    d["t_start"] = pd.to_datetime(d["time_start"], errors="coerce")
    d["t_end"] = pd.to_datetime(d["time_end"], errors="coerce")
    d["night_date"] = d["t_end"].dt.date
    # Ivaniuk convention: an overnight row ends in the morning (time_end has a clock time <= 12:00) and starts the
    # evening before (date-only start, earlier date, or a start before 06:00). Same-day rows starting >= 06:00 are
    # daytime attacks; rows with no clock time at all are daily singles (Orlan etc.). Both are excluded here.
    same_day = d["t_start"].dt.date == d["t_end"].dt.date
    start_has_time = d["time_start"].str.len() > 10
    end_has_time = d["time_end"].str.len() > 10
    is_night = end_has_time & (d["t_end"].dt.hour <= 12) & (~start_has_time | ~same_day | (d["t_start"].dt.hour < 6))
    d["is_day_event"] = ~is_night
    d["hidden"] = d["status_data"].eq("hidden")
    n = d[~d.is_day_event]
    g = n.groupby("night_date").agg(
        ivaniuk_launched=("launched", lambda s: s[~n.loc[s.index, "hidden"]].sum(min_count=1)),
        ivaniuk_destroyed=("destroyed", lambda s: s[~n.loc[s.index, "hidden"]].sum(min_count=1)),
        ivaniuk_not_reach_goal=("not_reach_goal", lambda s: s[~n.loc[s.index, "hidden"]].sum(min_count=1)),
        ivaniuk_hit_locations=("num_hit_location", lambda s: s.sum(min_count=1)),
        ivaniuk_n_rows=("model", "size"),
        ivaniuk_has_hidden=("hidden", "any"),
        ivaniuk_models=("model", lambda s: "|".join(sorted(set(s)))),
        ivaniuk_source=("source", "first"),
    ).reset_index()
    return g, d


def main() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True); QA_DIR.mkdir(exist_ok=True)
    s = pd.read_parquet(SUMM)
    nights = s[(s.period_kind == "night") & s.night_date.notna()].copy()
    # one row per night: the post with the largest launched total (later update supersedes the first wave)
    nights["_key"] = nights["total_launched"].fillna(-1) * 10 + nights["destroyed_total"].notna()
    nights = nights.sort_values(["night_date", "_key", "ts_utc"])
    n_posts = nights.groupby("night_date").size().rename("n_posts_night")
    one = nights.groupby("night_date").tail(1).drop(columns="_key").merge(n_posts, on="night_date")
    one["launch_directions"] = one["launch_directions"].map(lambda a: "|".join(a))
    one["main_target_oblasts"] = one["main_target_oblasts"].map(lambda a: "|".join(a))
    one["after_category_break"] = one["night_date"] >= CATEGORY_BREAK

    iva, iva_rows = ivaniuk_nights()
    # Ivaniuk "destroyed" = shot down by fire; EW-lost/not-reached sits in not_reach_goal (2024-25). The Air Force
    # headline switched from "збито" (fire only) to "знешкоджено"/"збито/подавлено" (fire + EW) during 2025.
    iva["ivaniuk_neutralized"] = iva.ivaniuk_destroyed + iva.ivaniuk_not_reach_goal.fillna(0)
    m = one.merge(iva, on="night_date", how="outer", indicator=True)
    m["in_telegram"] = m["_merge"].isin(["both", "left_only"])
    m["in_ivaniuk"] = m["_merge"].isin(["both", "right_only"])
    both = m[m._merge == "both"]
    cmp_l = both[both.total_launched.notna() & both.ivaniuk_launched.notna()]
    cmp_d = both[both.destroyed_total.notna() & both.ivaniuk_destroyed.notna()]
    m["launched_match"] = (m.total_launched == m.ivaniuk_launched).where(m.total_launched.notna() & m.ivaniuk_launched.notna())
    m["destroyed_match"] = (m.destroyed_total == m.ivaniuk_destroyed).where(m.destroyed_total.notna() & m.ivaniuk_destroyed.notna())
    m["destroyed_match_neutralized"] = (m.destroyed_total == m.ivaniuk_neutralized).where(m.destroyed_total.notna() & m.ivaniuk_neutralized.notna())
    m["destroyed_match_any"] = m.destroyed_match | m.destroyed_match_neutralized
    m["launched_diff"] = m.total_launched - m.ivaniuk_launched
    m["destroyed_diff"] = m.destroyed_total - m.ivaniuk_destroyed

    def rate(a, b):
        ok = (a == b); tol = ((a - b).abs() <= (0.05 * b).clip(lower=2))
        return {"n": int(len(a)), "exact": round(float(ok.mean()), 4) if len(a) else None,
                "within_5pct_or_2": round(float(tol.mean()), 4) if len(a) else None}
    stats = {
        "telegram_nights": int(one.night_date.nunique()), "ivaniuk_nights": int(iva.night_date.nunique()),
        "nights_in_both": int((m._merge == "both").sum()),
        "telegram_only": int((m._merge == "left_only").sum()), "ivaniuk_only": int((m._merge == "right_only").sum()),
        "launched": rate(cmp_l.total_launched, cmp_l.ivaniuk_launched),
        "destroyed_vs_fire_only": rate(cmp_d.destroyed_total, cmp_d.ivaniuk_destroyed),
        "destroyed_vs_fire_plus_ew": rate(cmp_d.destroyed_total, cmp_d.ivaniuk_neutralized),
        "destroyed_exact_either": round(float(((cmp_d.destroyed_total == cmp_d.ivaniuk_destroyed) | (cmp_d.destroyed_total == cmp_d.ivaniuk_neutralized)).mean()), 4),
        "destroyed_exact_either_by_year": {int(y): round(float(((g.destroyed_total == g.ivaniuk_destroyed) | (g.destroyed_total == g.ivaniuk_neutralized)).mean()), 4) for y, g in cmp_d.groupby(pd.to_datetime(cmp_d.night_date).dt.year)},
        "hit_locations": rate(both[both.hit_locations_n.notna() & both.ivaniuk_hit_locations.notna()].hit_locations_n, both[both.hit_locations_n.notna() & both.ivaniuk_hit_locations.notna()].ivaniuk_hit_locations),
        "launched_by_year": {int(y): rate(g.total_launched, g.ivaniuk_launched) for y, g in cmp_l.groupby(pd.to_datetime(cmp_l.night_date).dt.year)},
        "destroyed_by_year": {int(y): rate(g.destroyed_total, g.ivaniuk_destroyed) for y, g in cmp_d.groupby(pd.to_datetime(cmp_d.night_date).dt.year)},
    }

    # derived CSV: numbers + ids only, >= LAG_DAYS lag
    cutoff = dt.date.today() - dt.timedelta(days=LAG_DAYS)
    cols = ["night_date", "in_telegram", "in_ivaniuk", "msg_id", "n_posts_night", "parse_status", "night_date_method",
            "total_launched", "total_launched_method", "n_uav_launched", "n_missile_launched",
            "destroyed_total", "destroyed_method", "shot_down", "ew_lost", "hit_locations_n", "debris_locations_n",
            "launch_directions", "main_target_oblasts", "after_category_break",
            "ivaniuk_launched", "ivaniuk_destroyed", "ivaniuk_not_reach_goal", "ivaniuk_neutralized", "ivaniuk_hit_locations", "ivaniuk_n_rows", "ivaniuk_has_hidden",
            "launched_match", "destroyed_match", "destroyed_match_neutralized", "destroyed_match_any", "launched_diff", "destroyed_diff"]
    out = m[m.night_date <= cutoff].sort_values("night_date")[cols]
    out["msg_id"] = out["msg_id"].astype("Int64")
    wn = waves_per_night()
    out = out.merge(wn, on="night_date", how="left")
    for c in wn.columns:
        if c.startswith("n_"):
            out[c] = out[c].fillna(0).astype("int64")
    out.to_csv(OUT, index=False)

    # worst disagreements (interim: includes both texts)
    typed = pd.read_parquet(TYPED, columns=["channel", "msg_id", "text"])
    typed = typed[typed.channel == "kpszsu"][["msg_id", "text"]]
    bad = both.assign(ld=(both.total_launched - both.ivaniuk_launched).abs(),
                      dd=pd.concat([(both.destroyed_total - both.ivaniuk_destroyed).abs(), (both.destroyed_total - both.ivaniuk_neutralized).abs()], axis=1).min(axis=1))
    bad["worst"] = bad[["ld", "dd"]].max(axis=1)
    bad = bad[bad.worst > 0].sort_values("worst", ascending=False)
    rows = []
    for r in bad.itertuples(index=False):
        iv = iva_rows[(iva_rows.night_date == r.night_date) & ~iva_rows.is_day_event]
        rows.append({"night_date": r.night_date, "msg_id": int(r.msg_id), "tg_launched": r.total_launched, "iv_launched": r.ivaniuk_launched, "iv_neutralized": r.ivaniuk_neutralized,
                     "tg_destroyed": r.destroyed_total, "iv_destroyed": r.ivaniuk_destroyed, "tg_method": r.total_launched_method,
                     "ivaniuk_rows": "; ".join(f"{a.model}: {a.launched}/{a.destroyed}" + (f"+{int(a.not_reach_goal)}ew" if pd.notna(a.not_reach_goal) and a.not_reach_goal > 0 else "") + (" (hidden)" if a.hidden else "") for a in iv.itertuples()),
                     "telegram_text": typed.loc[typed.msg_id == r.msg_id, "text"].iloc[0]})
    qa = pd.DataFrame(rows)
    qa.to_csv(INTERIM / "extract" / "qa_ivaniuk_disagreements.csv", index=False)
    qa.drop(columns=["telegram_text"]).head(50).to_csv(QA_DIR / "ivaniuk_disagreements_top50.csv", index=False)
    (QA_DIR / "ivaniuk_agreement.json").write_text(json.dumps(stats, indent=2, default=str))
    stats["nights_with_wave"] = int((out.n_waves_night > 0).sum())
    stats["telegram_nights_with_wave"] = int(((out.n_waves_night > 0) & out.in_telegram).sum())
    write_meta(OUT, inputs={"summaries": SUMM, "ivaniuk": IVA, "waves": WAVES}, counts={"rows": int(len(out)), **stats},
               extra={"lag_days": LAG_DAYS, "cutoff_night_date": str(cutoff), "category_break": str(CATEGORY_BREAK)})
    log(json.dumps(stats, default=str))
    waves_week(cutoff)
    kyiv_week(cutoff)
    if STRIKES.exists() and len(pd.read_parquet(STRIKES, columns=["event_id"])):
        impacts_cellweek(cutoff)
        kyiv_strikes_week(cutoff)
        firms_match(cutoff)
    else:
        log("strike_events.parquet empty or missing: impacts_cellweek / kyiv_strikes_week / firms_match skipped")


def iso_week(ts: pd.Series) -> pd.DataFrame:
    iso = ts.dt.tz_convert("Europe/Kyiv").dt.isocalendar()
    return pd.DataFrame({"iso_year": iso.year.astype(int).values, "iso_week": iso.week.astype(int).values,
                         "week_start": (ts.dt.tz_convert("Europe/Kyiv").dt.normalize() - pd.to_timedelta(iso.day.astype(int).values - 1, unit="D")).dt.date.values},
                        index=ts.index)


def waves_per_night() -> pd.DataFrame:
    w = pd.read_parquet(WAVES, columns=["wave_id", "night_date", "start_ts", "n_tracks", "n_tracks_kyiv_city", "weapon_classes",
                                        "platforms", "n_nights_spanned", "duration_h"])
    g = w.groupby("night_date")
    return pd.DataFrame({
        "n_waves_night": g.size(),
        "n_waves_multi_night": g.n_nights_spanned.apply(lambda s: int((s > 1).sum())),
        "first_wave_start_utc": g.start_ts.min().dt.strftime("%Y-%m-%dT%H:%MZ"),
        "n_tracks_in_waves": g.n_tracks.sum(),
        "n_tracks_kyiv_city_in_waves": g.n_tracks_kyiv_city.sum(),
        "wave_weapon_classes": g.weapon_classes.apply(lambda s: "|".join(sorted({x for l in s for x in l}))),
        "wave_platforms": g.platforms.apply(lambda s: "|".join(sorted({x for l in s for x in l}))),
        "wave_ids": g.wave_id.apply(lambda s: "|".join(sorted(s))),
    }).reset_index()


def waves_week(cutoff: dt.date) -> None:
    w = pd.read_parquet(WAVES)
    w = w[w.start_ts.dt.tz_convert("Europe/Kyiv").dt.date <= cutoff]
    w = pd.concat([w, iso_week(w.start_ts)], axis=1)
    g = w.groupby(["iso_year", "iso_week", "week_start"])
    agg = pd.DataFrame({
        "n_waves": g.size(),
        "n_waves_start_launch_intel": g.start_kind.apply(lambda s: int((s == "launch_intel").sum())),
        "n_waves_start_launch": g.start_kind.apply(lambda s: int((s == "launch").sum())),
        "n_waves_night_start": g.starts_night.sum().astype(int),
        "n_waves_with_summary": g.summary_msg_id.apply(lambda s: int(s.notna().sum())),
        "n_waves_reaching_kyiv_city": g.n_tracks_kyiv_city.apply(lambda s: int((s > 0).sum())),
        "n_waves_toward_kyiv_city": g.n_tracks_toward_kyiv.apply(lambda s: int((s > 0).sum())),
        "n_waves_kyiv_oblast": g.n_tracks_kyiv_oblast.apply(lambda s: int((s > 0).sum())),
        "median_duration_h": g.duration_h.median().round(2),
        "max_duration_h": g.duration_h.max().round(1),
        "n_tracks": g.n_tracks.sum(), "n_tracks_shahed": g.n_tracks_shahed.sum(), "n_tracks_jet_uav": g.n_tracks_jet_uav.sum(),
        "n_tracks_cruise": g.n_tracks_cruise.sum(), "n_tracks_ballistic": g.n_tracks_ballistic.sum(), "n_tracks_kinzhal": g.n_tracks_kinzhal.sum(),
        "n_launch_posts": g.n_launch_posts.sum(), "n_launch_intel_posts": g.n_launch_intel.sum(), "n_kab_launches_in_windows": g.n_kab_launches_in_window.sum(),
        "n_alerts": g.n_alerts.sum(),
        "summary_launched_sum": g.summary_total_launched.sum(min_count=1), "summary_destroyed_sum": g.summary_destroyed_total.sum(min_count=1),
    })
    for cls in ["shahed", "jet_uav", "cruise", "ballistic", "kinzhal"]:
        agg[f"n_waves_with_{cls}"] = g.weapon_classes.apply(lambda s, c=cls: int(sum(c in l for l in s)))
    for pf in ["Tu-95", "Tu-160", "Tu-22M3", "MiG-31K", "ship", "submarine", "ground"]:
        agg[f"n_waves_platform_{pf.replace('-', '').lower()}"] = g.platforms.apply(lambda s, p=pf: int(sum(p in l for l in s)))
    for cls in LAG_CLASSES:
        agg[f"n_lag_{cls}"] = g[f"lag_min_{cls}"].apply(lambda s: int(s.notna().sum()))
        agg[f"median_lag_min_{cls}"] = g[f"lag_min_{cls}"].median().round(1)
    agg["median_takeoff_to_first_cruise_track_min"] = g.takeoff_to_first_cruise_track_min.median().round(1)
    agg = agg.reset_index().sort_values(["iso_year", "iso_week"])
    agg.to_csv(OUT_WAVES_WEEK, index=False)
    write_meta(OUT_WAVES_WEEK, inputs={"waves": WAVES}, counts={"rows": int(len(agg)), "waves": int(len(w)),
               "waves_by_year": w.groupby("iso_year").size().to_dict()}, extra={"lag_days": LAG_DAYS, "cutoff": str(cutoff)})
    log(f"launch_waves_week: {len(agg)} weeks, {len(w)} waves")


def kyiv_week(cutoff: dt.date) -> None:
    """Tracks over / toward Kyiv city per ISO week (flags from _common.kyiv_flags). Kyiv oblast (UA-32) is a separate
    column and never folded into the city counts."""
    t = pd.read_parquet(TRACKS, columns=["ts_utc", "channel", "msg_id", "seg_idx", "weapon_class", "oblast_iso", "settlement_raw", "settlement_role", "heading_raw", "count"])
    t["city"], t["toward"], t["oblast"] = kyiv_flags(t)
    t = t[t.city | t.toward | t.oblast]
    t = t[t.ts_utc.dt.tz_convert("Europe/Kyiv").dt.date <= cutoff]
    links = pd.read_parquet(LINKS, columns=["wave_id", "kind", "channel", "msg_id", "seg_idx"])
    links = links[links.kind == "track"].drop(columns="kind")
    t = t.merge(links, on=["channel", "msg_id", "seg_idx"], how="left")
    t = pd.concat([t, iso_week(t.ts_utc)], axis=1)
    g = t.groupby(["iso_year", "iso_week", "week_start"])
    def n(mask): return g.apply(lambda d, m=mask: int(m.loc[d.index].sum()), include_groups=False)
    agg = pd.DataFrame({
        "n_tracks_kyiv_city": n(t.city), "n_tracks_toward_kyiv_city": n(t.toward & ~t.city), "n_tracks_kyiv_oblast_only": n(t.oblast & ~t.city & ~t.toward),
        "n_track_posts_kyiv_city": g.apply(lambda d: int(d[d.city].msg_id.nunique()), include_groups=False),
        "n_tracks_kyiv_city_kpszsu": n(t.city & (t.channel == "kpszsu")),
        "n_waves_reaching_kyiv_city": g.apply(lambda d: int(d[d.city].wave_id.nunique()), include_groups=False),
        "n_waves_toward_kyiv_city": g.apply(lambda d: int(d[d.toward | d.city].wave_id.nunique()), include_groups=False),
        "n_days_with_kyiv_city_track": g.apply(lambda d: int(d[d.city].ts_utc.dt.tz_convert("Europe/Kyiv").dt.date.nunique()), include_groups=False),
        "share_city_tracks_in_wave": g.apply(lambda d: round(float(d[d.city].wave_id.notna().mean()), 3) if d.city.any() else None, include_groups=False),
    })
    for cls in ["shahed", "jet_uav", "cruise", "ballistic", "kinzhal", "unknown"]:
        agg[f"n_tracks_kyiv_city_{cls}"] = n(t.city & (t.weapon_class == cls))
    agg = agg.reset_index().sort_values(["iso_year", "iso_week"])
    agg.to_csv(OUT_KYIV_WEEK, index=False)
    write_meta(OUT_KYIV_WEEK, inputs={"tracks": TRACKS, "links": LINKS}, counts={"rows": int(len(agg)), "city_tracks": int(t.city.sum()),
               "toward_only_tracks": int((t.toward & ~t.city).sum()), "oblast_only_tracks": int((t.oblast & ~t.city & ~t.toward).sum())},
               extra={"lag_days": LAG_DAYS, "cutoff": str(cutoff)})
    log(f"kyiv_tracks_week: {len(agg)} weeks, city tracks {int(t.city.sum())}")


# ----------------------------------------------------------------------------------------------- impacts (L6)
def load_strikes(cutoff: dt.date) -> pd.DataFrame:
    e = pd.read_parquet(STRIKES)
    e = e[e.event_ts.dt.tz_convert("Europe/Kyiv").dt.date <= cutoff].copy()
    e["weapon_class"] = e.weapon_class.fillna("unknown")
    e["killed"] = e.killed.fillna(0).astype(int); e["wounded"] = e.wounded.fillna(0).astype(int)
    return pd.concat([e, iso_week(e.event_ts)], axis=1)


def impacts_cellweek(cutoff: dt.date) -> None:
    e = load_strikes(cutoff)
    def agg(d, keys):
        g = d.groupby(keys, dropna=False)
        out = pd.DataFrame({"n_events": g.size(), "n_sources": g.n_sources.sum(), "n_incidents": g.n_incidents.sum(),
                            "n_multi_source": g.n_sources.apply(lambda s: int((s > 1).sum())),
                            "killed": g.killed.sum(), "wounded": g.wounded.sum(),
                            "n_debris_only": g.is_debris_only.sum().astype(int),
                            "n_time_known": g.ts_precision.apply(lambda s: int((s != "date").sum()))}).reset_index()
        return out.sort_values(keys)
    wc = e[e.lat.notna()]
    cw = agg(wc.assign(oblast_iso=wc.oblast_iso), ["h3_r5", "iso_year", "iso_week", "week_start", "weapon_class", "tier"])
    # oblast of the cell = modal oblast of its events (a res-5 cell can straddle a border)
    cell_ob = wc.groupby("h3_r5").oblast_iso.agg(lambda s: s.value_counts().index[0] if s.notna().any() else None)
    cw.insert(1, "oblast_iso", cw.h3_r5.map(cell_ob))
    cw.to_csv(OUT_CELLWEEK, index=False)
    write_meta(OUT_CELLWEEK, inputs={"strike_events": STRIKES}, counts={"rows": int(len(cw)), "events": int(len(wc)), "cells": int(wc.h3_r5.nunique()),
               "events_by_year": wc.groupby("iso_year").size().to_dict(), "killed": int(wc.killed.sum()), "wounded": int(wc.wounded.sum())},
               extra={"lag_days": LAG_DAYS, "cutoff": str(cutoff), "h3_resolution": 5, "casualties": "sum over events of the per-event max across sources"})
    nc = e[e.lat.isna()]
    ow = agg(nc, ["oblast_iso", "iso_year", "iso_week", "week_start", "weapon_class", "tier"])
    ow["n_location_withheld"] = nc.groupby(["oblast_iso", "iso_year", "iso_week", "week_start", "weapon_class", "tier"], dropna=False).location_withheld.sum().astype(int).values
    ow.to_csv(OUT_OBLWEEK, index=False)
    write_meta(OUT_OBLWEEK, inputs={"strike_events": STRIKES}, counts={"rows": int(len(ow)), "events_without_coords": int(len(nc)),
               "by_loc_key_level": nc.loc_key_level.value_counts().to_dict()}, extra={"lag_days": LAG_DAYS, "cutoff": str(cutoff)})
    log(f"impacts_cellweek: {len(cw)} cell-weeks from {len(wc)} events; oblast-week: {len(ow)} rows from {len(nc)} events without coords")


def kyiv_alert_hours(cutoff: dt.date) -> tuple[pd.DataFrame, dict]:
    """VA_Kyiv alert -> next all_clear. State machine: an alert opens an episode if none is open (repeat alert posts
    inside an episode are ignored); the next all_clear closes it. Episodes longer than ALERT_CAP_H are capped
    (missed all_clear). Hours are attributed to the ISO week of the alert start."""
    t = pd.read_parquet(TYPED_FINAL, columns=["channel", "msg_id", "ts_utc", "post_type"])
    t = t[(t.channel == "VA_Kyiv") & t.post_type.isin(["alert", "all_clear"])].sort_values(["ts_utc", "msg_id"])
    open_ts, eps, dup_alert, unpaired_clear = None, [], 0, 0
    for r in t.itertuples():
        if r.post_type == "alert":
            if open_ts is None:
                open_ts = r.ts_utc
            else:
                dup_alert += 1
        else:
            if open_ts is None:
                unpaired_clear += 1
                continue
            h = (r.ts_utc - open_ts).total_seconds() / 3600
            eps.append((open_ts, min(h, ALERT_CAP_H), h > ALERT_CAP_H)); open_ts = None
    ep = pd.DataFrame(eps, columns=["start_ts", "hours", "capped"])
    ep = ep[ep.start_ts.dt.tz_convert("Europe/Kyiv").dt.date <= cutoff]
    ep = pd.concat([ep, iso_week(ep.start_ts)], axis=1)
    g = ep.groupby(["iso_year", "iso_week", "week_start"])
    out = pd.DataFrame({"n_alert_episodes": g.size(), "n_alert_hours": g.hours.sum().round(2), "n_alert_episodes_capped": g.capped.sum().astype(int)}).reset_index()
    info = {"episodes": int(len(ep)), "repeat_alert_posts_ignored": int(dup_alert), "all_clear_without_alert": int(unpaired_clear),
            "episodes_capped": int(ep.capped.sum()), "median_hours": round(float(ep.hours.median()), 2) if len(ep) else None,
            "first_alert": str(ep.start_ts.min()) if len(ep) else None}
    return out, info


def kyiv_strikes_week(cutoff: dt.date) -> None:
    e = load_strikes(cutoff)
    keys = ["iso_year", "iso_week", "week_start"]
    city = e[e.oblast_iso == "UA-30"]; obl = e[e.oblast_iso == "UA-32"]
    gc = city.groupby(keys); go = obl.groupby(keys)
    imp = pd.DataFrame({"n_impacts_tier_A": gc.size(), "n_impacts_tier_A_with_coords": gc.lat.apply(lambda s: int(s.notna().sum())),
                        "n_impacts_tier_A_debris_only": gc.is_debris_only.sum().astype(int),
                        "n_impact_incidents_kyiv_city": gc.n_incidents.sum(), "n_impact_sources_kyiv_city": gc.n_sources.sum(),
                        "killed_kyiv_city": gc.killed.sum(), "wounded_kyiv_city": gc.wounded.sum(),
                        "n_days_with_impact_kyiv_city": gc.event_date_kyiv.nunique(),
                        "n_impacts_in_wave_kyiv_city": gc.wave_id.apply(lambda s: int(s.notna().sum()))})
    for cls in ["shahed", "cruise", "ballistic", "kinzhal", "unknown"]:
        imp[f"n_impacts_kyiv_city_{cls}"] = gc.weapon_class.apply(lambda s, c=cls: int((s == c).sum()))
    impo = pd.DataFrame({"n_impacts_kyiv_oblast": go.size(), "killed_kyiv_oblast": go.killed.sum(), "wounded_kyiv_oblast": go.wounded.sum()})
    # waves + tracks from the already-written weekly tables (same flags, same lag)
    kw = pd.read_csv(OUT_KYIV_WEEK)[keys + ["n_waves_reaching_kyiv_city", "n_waves_toward_kyiv_city", "n_tracks_kyiv_city", "n_tracks_toward_kyiv_city", "n_tracks_kyiv_oblast_only"]]
    kw = kw.rename(columns={"n_waves_reaching_kyiv_city": "n_waves_reaching_kyiv", "n_tracks_toward_kyiv_city": "n_tracks_toward_kyiv"})
    kw["week_start"] = pd.to_datetime(kw.week_start).dt.date
    al, al_info = kyiv_alert_hours(cutoff)
    out = kw.merge(imp.reset_index(), on=keys, how="outer").merge(impo.reset_index(), on=keys, how="outer").merge(al, on=keys, how="outer")
    for c in out.columns:
        if c.startswith(("n_", "killed", "wounded")) and c != "n_alert_hours":
            out[c] = out[c].fillna(0).astype("int64")
    out["n_alert_hours"] = out.n_alert_hours.fillna(0.0)
    out = out.sort_values(keys).reset_index(drop=True)
    out.to_csv(OUT_KYIV_STRIKES, index=False)
    write_meta(OUT_KYIV_STRIKES, inputs={"strike_events": STRIKES, "kyiv_tracks_week": OUT_KYIV_WEEK, "posts_typed_final": TYPED_FINAL},
               counts={"rows": int(len(out)), "kyiv_city_events": int(len(city)), "kyiv_oblast_events": int(len(obl)),
                       "kyiv_city_events_by_year": city.groupby("iso_year").size().to_dict(), "alerts": al_info},
               extra={"lag_days": LAG_DAYS, "cutoff": str(cutoff), "alert_cap_hours": ALERT_CAP_H,
                      "notes": ["UA-30 = Kyiv city (H12 unit); UA-32 = Kyiv oblast, separate columns, never merged",
                                "n_alert_hours from VA_Kyiv alert/all_clear posts only (not the official siren API)"]})
    log(f"kyiv_strikes_week: {len(out)} weeks; {len(city)} city events; alert episodes {al_info['episodes']}")


def load_firms() -> pd.DataFrame:
    files = sorted(FIRMS_DIR.glob("VIIRS_*/*/*.csv"))
    parts = []
    for f in files:
        d = pd.read_csv(f, usecols=["latitude", "longitude", "acq_date", "acq_time", "satellite", "confidence", "frp", "daynight"],
                        dtype={"acq_date": str, "satellite": str, "confidence": str, "daynight": str})
        d["source"] = f.parent.parent.name
        parts.append(d)
    fi = pd.concat([x for x in parts if len(x)], ignore_index=True)
    n0 = len(fi)
    fi = fi.drop_duplicates(["latitude", "longitude", "acq_date", "acq_time", "satellite"])
    t = fi.acq_time.astype(int)
    fi["ts"] = pd.to_datetime(fi.acq_date, utc=True) + pd.to_timedelta(t // 100, unit="h") + pd.to_timedelta(t % 100, unit="m")
    fi = fi.sort_values("ts").reset_index(drop=True)
    log(f"FIRMS: {len(fi):,} detections from {len(files)} files ({n0 - len(fi):,} SP/NRT duplicates dropped); "
        f"{fi.ts.min().date()}..{fi.ts.max().date()}; satellites {fi.satellite.value_counts().to_dict()}")
    return fi


def _nearest(fi_ts, fi_lat, fi_lon, lo, hi, lat, lon):
    """nearest detection in [lo, hi] (int64 ns) within FIRMS_RADIUS_M -> (idx|None, dist_m, n_within, n_within_wide)"""
    i0, i1 = np.searchsorted(fi_ts, lo), np.searchsorted(fi_ts, hi, side="right")
    if i1 <= i0:
        return None, None, 0, 0
    la = fi_lat[i0:i1]; lo_ = fi_lon[i0:i1]
    dlat = np.abs(la - lat); box = dlat < (FIRMS_RADIUS_WIDE_M / 111_195.0) * 1.1
    if not box.any():
        return None, None, 0, 0
    j = np.nonzero(box)[0]
    dlon = (lo_[j] - lon) * np.cos(np.radians(lat))
    d = np.hypot(dlat[j] * 111_195.0, dlon * 111_195.0)
    nw = int((d <= FIRMS_RADIUS_WIDE_M).sum())
    k = np.nonzero(d <= FIRMS_RADIUS_M)[0]
    if len(k) == 0:
        return None, None, 0, nw
    b = k[np.argmin(d[k])]
    return int(i0 + j[b]), float(d[b]), int(len(k)), nw


def firms_match(cutoff: dt.date) -> None:
    e = load_strikes(cutoff)
    e = e[(e.tier == "A") & e.lat.notna()].copy()
    fi = load_firms()
    fi_ts = fi.ts.values.astype("datetime64[ns]").astype(np.int64)
    fi_lat = fi.latitude.values.astype(float); fi_lon = fi.longitude.values.astype(float)
    H = np.int64(3600e9)
    ev_ts = e.event_ts.values.astype("datetime64[ns]").astype(np.int64)
    kyiv_day0 = e.event_ts.dt.tz_convert("Europe/Kyiv").dt.normalize()
    day_lo = kyiv_day0.dt.tz_convert("UTC").values.astype("datetime64[ns]").astype(np.int64)
    day_hi = (kyiv_day0 + pd.Timedelta(days=1)).dt.tz_convert("UTC").values.astype("datetime64[ns]").astype(np.int64)
    date_only = (e.ts_precision == "date").values
    lo = np.where(date_only, day_lo - np.int64(FIRMS_BEFORE_H * 3600e9), ev_ts - np.int64(FIRMS_BEFORE_H * 3600e9))
    hi = np.where(date_only, day_hi + np.int64(FIRMS_AFTER_H * 3600e9), ev_ts + np.int64(FIRMS_AFTER_H * 3600e9))
    shift = np.int64(PLACEBO_DAYS * 24) * H
    rows = []
    for n, (lat, lon, a, b) in enumerate(zip(e.lat.values, e.lon.values, lo, hi)):
        i, d, k, kw = _nearest(fi_ts, fi_lat, fi_lon, a, b, lat, lon)
        ip, dp, kp, kwp = _nearest(fi_ts, fi_lat, fi_lon, a - shift, b - shift, lat, lon)
        rows.append((i, d, k, kw, ip is not None, kp, kwp))
    m = pd.DataFrame(rows, columns=["_i", "dist_m", "n_firms_within_1km_12h", "n_firms_within_3km_12h", "matched_placebo_m7d",
                                    "n_firms_placebo_m7d", "n_firms_placebo_m7d_3km"], index=e.index)
    hit = m._i.notna()
    f = fi.loc[m._i[hit].astype(int).values]
    out = pd.DataFrame({"event_id": e.event_id, "event_ts": e.event_ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "ts_precision": e.ts_precision,
                        "window_kind": np.where(date_only, "date", "ts"), "h3_r5": e.h3_r5, "oblast_iso": e.oblast_iso,
                        "weapon_class": e.weapon_class, "target_type": e.target_type, "geo_level": e.geo_level, "geo_conf": e.geo_conf,
                        "n_sources": e.n_sources, "killed": e.killed, "wounded": e.wounded, "is_debris_only": e.is_debris_only,
                        "matched": hit, "firms_ts": pd.Series(index=e.index, dtype="object"), "dist_m": m.dist_m.round(0),
                        "frp": pd.Series(index=e.index, dtype="float"), "satellite": pd.Series(index=e.index, dtype="object"),
                        "daynight": pd.Series(index=e.index, dtype="object"), "confidence": pd.Series(index=e.index, dtype="object"),
                        "n_firms_within_1km_12h": m.n_firms_within_1km_12h, "matched_placebo_m7d": m.matched_placebo_m7d,
                        "n_firms_placebo_m7d": m.n_firms_placebo_m7d,
                        "matched_3km": m.n_firms_within_3km_12h > 0, "n_firms_within_3km_12h": m.n_firms_within_3km_12h,
                        "matched_placebo_m7d_3km": m.n_firms_placebo_m7d_3km > 0})
    out.loc[hit, "firms_ts"] = f.ts.dt.strftime("%Y-%m-%dT%H:%MZ").values
    out.loc[hit, "frp"] = f.frp.values; out.loc[hit, "satellite"] = f.satellite.values
    out.loc[hit, "daynight"] = f.daynight.values; out.loc[hit, "confidence"] = f.confidence.values
    out["lag_h"] = ((pd.to_datetime(out.firms_ts, utc=True) - e.event_ts).dt.total_seconds() / 3600).round(2)
    out = out.sort_values("event_ts").reset_index(drop=True)
    OUT_FIRMS.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_FIRMS, index=False)
    # published aggregate: cell-week x weapon_class (PREREG §7: nothing finer than cell-week leaves data/interim)
    cw = pd.concat([out, iso_week(pd.to_datetime(out.event_ts, utc=True))], axis=1)
    cw = (cw.groupby(["h3_r5", "iso_year", "iso_week", "week_start", "weapon_class"])
            .agg(n_events=("event_id", "size"), n_matched_1km=("matched", "sum"), n_matched_placebo_1km=("matched_placebo_m7d", "sum"),
                 n_matched_3km=("matched_3km", "sum"), n_matched_placebo_3km=("matched_placebo_m7d_3km", "sum"),
                 n_settlement_geocode=("geo_level", lambda x: int((x == "settlement").sum())))
            .reset_index().sort_values(["iso_year", "iso_week", "h3_r5"]))
    cw.to_csv(OUT_FIRMS_CW, index=False)
    def rate(d):
        return {"n": int(len(d)), "match": round(float(d.matched.mean()), 4) if len(d) else None,
                "placebo": round(float(d.matched_placebo_m7d.mean()), 4) if len(d) else None,
                "match_3km": round(float(d.matched_3km.mean()), 4) if len(d) else None,
                "placebo_3km": round(float(d.matched_placebo_m7d_3km.mean()), 4) if len(d) else None}
    firms_end = fi.ts.max()
    cov = out[pd.to_datetime(out.event_ts, utc=True) <= firms_end]
    yr = pd.to_datetime(out.event_ts).dt.year
    stats = {"rows": int(len(out)), "events_within_firms_coverage": int(len(cov)), "firms_last_detection": str(firms_end),
             "overall": rate(out), "overall_within_coverage": rate(cov),
             "by_weapon_class": {k: rate(d) for k, d in out.groupby("weapon_class")},
             "by_year": {int(k): rate(d) for k, d in out.groupby(yr)},
             "by_window_kind": {k: rate(d) for k, d in out.groupby("window_kind")},
             "by_geo_level": {k: rate(d) for k, d in out.groupby("geo_level")},
             "by_target_type": {k: rate(d) for k, d in out.groupby("target_type")},
             "kyiv_city": rate(out[out.oblast_iso == "UA-30"]),
             "median_lag_h_matched": round(float(out.lag_h[out.matched].median()), 2) if out.matched.any() else None,
             "median_dist_m_matched": round(float(out.dist_m[out.matched].median()), 0) if out.matched.any() else None,
             "firms_detections": int(len(fi))}
    stats["cellweek_rows"] = int(len(cw))
    for _p in (OUT_FIRMS, OUT_FIRMS_CW):
      write_meta(_p, inputs={"strike_events": STRIKES}, counts=stats,
                 extra={"lag_days": LAG_DAYS, "cutoff": str(cutoff), "radius_m": FIRMS_RADIUS_M, "window_h": [-FIRMS_BEFORE_H, FIRMS_AFTER_H],
                        "placebo_shift_days": PLACEBO_DAYS, "wide_radius_m_diagnostic": FIRMS_RADIUS_WIDE_M, "firms_dir": str(FIRMS_DIR.relative_to(ROOT)),
                        "firms_sources": sorted(fi.source.unique().tolist()),
                        "observability_covariates": "not attached yet (ERA5 cloud cover / snow to be joined later)",
                        "notes": ["date-only events use the whole Kyiv date -1 h .. +12 h (window_kind='date')",
                                  "placebo = same place, same window shifted 7 days earlier; match - placebo is the excess detection rate",
                                  "a non-match is not evidence of no fire: cloud, overpass timing, small or short fires"]})
    log(f"firms_match: {len(out)} events, match {stats['overall']['match']}, placebo {stats['overall']['placebo']}; "
        f"by class {json.dumps({k: v['match'] for k, v in stats['by_weapon_class'].items()})}")


if __name__ == "__main__":
    main()
