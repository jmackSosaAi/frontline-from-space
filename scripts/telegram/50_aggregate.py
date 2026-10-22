"""L6: publishable aggregates.
  national_night.csv      one row per night from extract/summaries.parquet, cross-checked against the Ivaniuk Kaggle
                          dataset (data/raw/ivaniuk_missile_attacks), joined to launch_waves (n_waves_night, ...).
  launch_waves_week.csv   ISO week x wave counts by start kind / platform / weapon class, durations, lags.
  kyiv_tracks_week.csv    ISO week x tracks over Kyiv city (UA-30) or heading toward Kyiv city; oblast (UA-32) kept
                          as a separate column, never merged (TELEGRAM_PIPELINE.md §5 "Oblast != city").
Still missing (need impacts.parquet): kyiv_strikes_week.csv impacts columns, impacts_cellweek.csv, firms_match.csv.

No raw text leaves data/interim: the derived CSV carries msg_ids and numbers only. The disagreement list
with both texts is written to data/interim/telegram/extract/qa_ivaniuk_disagreements.csv.
"""
from __future__ import annotations
import json, sys, datetime as dt
from pathlib import Path
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


if __name__ == "__main__":
    main()
