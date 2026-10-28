"""H7 Transfer — scoring (PREREG §4 H7, confirmatory). Predictions filed in predictions/transfer_v1.json (tag transfer-v1)
before any T1/T2 download; this script only reads them.

PREREG test: realised recall against UCDP GED (Sudan) and dated settlement captures (Karabakh, detection within
5 km / ±2 days) is within ±15 pp of predicted. Prediction: within band for Sudan; Karabakh within band but lower.

Rules used (all stated in the meta):
- Sudan primary   = PREREG §3 rule: >=1 fire within 1 km and acq_ts in [date_start 00:00 −12 h, date_end 24:00 +12 h] UTC.
- Karabakh primary = H7 rule: within 5 km and [date_start 00:00 −48 h, date_end 24:00 +48 h] UTC.
- Secondary (DEVIATIONS 2026-10-22 H7 note): each case also under the other rule, so Karabakh is shown at the model's own
  1 km / 48 h definition and Sudan at 5 km / ±2 days.
- Karabakh event set: no dated settlement-capture list is on disk, so UCDP GED 26.1 events in the T1 window and AOI are
  used (deviation logged in DEVIATIONS.md, 2026-10-27).
- Events: primary = UCDP where_prec == 1 (exact location) and date_prec == 1 (single day). Sensitivity = where_prec <= 2
  and date_prec <= 2 (window spans date_start..date_end).
- Fires: VIIRS S-NPP (the T1/T2 files on disk are S-NPP only), confidence n/h, any type.
- Distances in a local azimuthal-equidistant projection centred on each AOI (EPSG:3035 is Europe-only).
- CI: cluster bootstrap over event-days (date_start), 2,000 draws, seed 20261014, percentile 95%.
- Verdict per case: |observed − predicted point| <= 15 pp (point estimate; whether the whole 95% CI sits in the band is
  also reported). H7 supported iff both cases are within band.
Outputs aggregate only (no coordinates, no event ids): data/derived/results/h7_scored.{csv,json}, figures/h7_transfer.png.
"""
from __future__ import annotations
import sys, json, zipfile, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyproj import Transformer
from scipy.spatial import cKDTree
from _common import ROOT, RAW, DERIVED, SEED, write_meta, log
from _panel import save_verdict

RES = DERIVED / "results"; FIG = ROOT / "figures"
PRED = ROOT / "predictions" / "transfer_v1.json"
GED = RAW / "ucdp" / "ged261-csv.zip"
FP = RAW / "firms_country_post_tag"
BAND = 0.15; N_BOOT = 2000
RULES = {"1km_12h": dict(r=1000.0, buf_h=12), "5km_2d": dict(r=5000.0, buf_h=48)}
CASES = {
    "karabakh_2020": dict(countries=["Azerbaijan", "Armenia"], adm1=None, primary="5km_2d",
                          fires=[FP / "viirs-snpp_2020_Azerbaijan.csv", FP / "viirs-snpp_2020_Armenia.csv"]),
    "sudan_2023_2025": dict(countries=["Sudan"], adm1=r"Darfur|Kordofan", primary="1km_12h",
                            fires=[FP / f"viirs-snpp_{y}_Sudan.csv" for y in (2023, 2024, 2025)]),
}
P = json.load(open(PRED))

ged = pd.read_csv(zipfile.ZipFile(GED).open("GEDEvent_v26_1.csv"), low_memory=False,
                  usecols=["country", "adm_1", "date_start", "date_end", "date_prec", "where_prec", "latitude",
                           "longitude", "type_of_violence", "best"])
ged["date_start"] = pd.to_datetime(ged["date_start"]).dt.normalize()
ged["date_end"] = pd.to_datetime(ged["date_end"]).dt.normalize()


def events_for(case, cfg):
    pc = P["cases"][case]; a = pc["aoi"]; w0, w1 = map(pd.Timestamp, pc["window"])
    e = ged[ged.country.isin(cfg["countries"]) & ged.date_start.between(w0, w1)
            & ged.latitude.between(a["lat0"], a["lat1"]) & ged.longitude.between(a["lon0"], a["lon1"])].copy()
    if cfg["adm1"]:
        e = e[e.adm_1.fillna("").str.contains(cfg["adm1"])]
    e["set"] = np.where((e.where_prec == 1) & (e.date_prec == 1), "precise", "loose")
    e = e[(e.where_prec <= 2) & (e.date_prec <= 2)].reset_index(drop=True)
    return e, a, (w0, w1)


def fires_for(cfg, a, win):
    f = pd.concat([pd.read_csv(p, usecols=["latitude", "longitude", "acq_date", "acq_time", "confidence"]) for p in cfg["fires"]])
    f = f[f.confidence.isin(["n", "h"])]
    f = f[f.latitude.between(a["lat0"] - 0.1, a["lat1"] + 0.1) & f.longitude.between(a["lon0"] - 0.1, a["lon1"] + 0.1)]
    f["ts"] = pd.to_datetime(f.acq_date) + pd.to_timedelta(f.acq_time // 100, "h") + pd.to_timedelta(f.acq_time % 100, "min")
    f = f[f.ts.between(win[0] - pd.Timedelta(days=4), win[1] + pd.Timedelta(days=5))]
    return f.drop_duplicates(["latitude", "longitude", "ts"]).reset_index(drop=True)


def detect(e, f, a, r, buf_h):
    tr = Transformer.from_crs("EPSG:4326", f"+proj=aeqd +lat_0={(a['lat0']+a['lat1'])/2} +lon_0={(a['lon0']+a['lon1'])/2} +units=m",
                              always_xy=True)
    fx = np.column_stack(tr.transform(f.longitude.values, f.latitude.values))
    ex = np.column_stack(tr.transform(e.longitude.values, e.latitude.values))
    hits = cKDTree(fx).query_ball_point(ex, r=r)
    ts = f.ts.values
    w0 = (e.date_start - pd.Timedelta(hours=buf_h)).values; w1 = (e.date_end + pd.Timedelta(hours=24 + buf_h)).values
    return np.array([bool(len(h)) and bool(((ts[h] >= w0[i]) & (ts[h] <= w1[i])).any()) for i, h in enumerate(hits)])


def boot(det, day, rng):
    g = pd.DataFrame({"d": det, "day": day}).groupby("day")["d"].agg(["sum", "size"])
    k, n = g["sum"].values.astype(float), g["size"].values.astype(float)
    w = rng.multinomial(len(g), np.full(len(g), 1 / len(g)), size=N_BOOT).astype(np.float32)
    rr = (w @ k) / (w @ n)
    return float(np.percentile(rr, 2.5)), float(np.percentile(rr, 97.5)), len(g)


rng = np.random.default_rng(SEED)
rows = []; counts = {}
for case, cfg in CASES.items():
    e, a, win = events_for(case, cfg)
    f = fires_for(cfg, a, win)
    counts[case] = {"fires_snpp_nh_in_aoi_window": int(len(f)), "events_precise": int((e.set == "precise").sum()),
                    "events_loose_incl_precise": int(len(e))}
    log(f"{case}: {counts[case]}")
    pred = P["cases"][case]
    for rule, rc in RULES.items():
        det = detect(e, f, a, rc["r"], rc["buf_h"])
        for es in ("precise", "loose"):
            m = (e.set == "precise").values if es == "precise" else np.ones(len(e), bool)
            lo, hi, nd = boot(det[m], e.date_start.values[m], rng)
            obs = float(det[m].mean())
            role = "primary" if (rule == cfg["primary"] and es == "precise") else (
                "secondary_rule" if es == "precise" else "sensitivity_event_precision")
            rows.append(dict(case=case, rule=rule, event_set=es, role=role, n_events=int(m.sum()), n_event_days=nd,
                             n_detected=int(det[m].sum()), observed_recall=obs, ci95_lo=lo, ci95_hi=hi,
                             predicted_recall=pred["predicted_recall"], pred_int90_lo=pred["interval_90"][0],
                             pred_int90_hi=pred["interval_90"][1], diff_pp=100 * (obs - pred["predicted_recall"]),
                             within_band=abs(obs - pred["predicted_recall"]) <= BAND,
                             ci_inside_band=(lo >= pred["predicted_recall"] - BAND) and (hi <= pred["predicted_recall"] + BAND),
                             obs_inside_pred_int90=pred["interval_90"][0] <= obs <= pred["interval_90"][1]))

T = pd.DataFrame(rows)
T.to_csv(RES / "h7_scored.csv", index=False, float_format="%.5f")
prim = T[T.role == "primary"].set_index("case")
kb, sd = prim.loc["karabakh_2020"], prim.loc["sudan_2023_2025"]
verdict = "supported" if (kb.within_band and sd.within_band) else "not supported"
# "Karabakh ... lower": compared like-for-like (same rule, precise events) under both rules; the cross-rule primary
# comparison is also reported but mixes 5 km and 1 km definitions.
pe = T[T.event_set == "precise"].set_index(["case", "rule"])["observed_recall"]
lower_by_rule = {r: bool(pe[("karabakh_2020", r)] < pe[("sudan_2023_2025", r)]) for r in RULES}
lower = all(lower_by_rule.values())
lower_primary_cross_rule = bool(kb.observed_recall < sd.observed_recall)
fmt = lambda r: (f"{100*r.observed_recall:.1f}% (95% CI {100*r.ci95_lo:.1f}–{100*r.ci95_hi:.1f}, n={r.n_events}) vs predicted "
                 f"{100*r.predicted_recall:.1f}% ({r.diff_pp:+.1f} pp, {'within' if r.within_band else 'outside'} ±15 pp)")
sec = T[T.role == "secondary_rule"].set_index("case")
out = {
    "hypothesis": "H7", "label": "confirmatory",
    "criterion": "per case |observed recall − filed predicted recall| <= 15 pp; supported iff both cases within band",
    "verdict": verdict, "karabakh_lower_than_sudan_same_rule": lower_by_rule,
    "karabakh_lower_than_sudan_primary_cross_rule": lower_primary_cross_rule,
    "primary": {c: prim.loc[c].drop(["rule", "event_set", "role"]).to_dict() | {"rule": prim.loc[c, "rule"]} for c in prim.index},
    "secondary_rule": {c: sec.loc[c].drop(["event_set", "role"]).to_dict() for c in sec.index},
    "notes": [
        "Karabakh event set = UCDP GED 26.1 (exact-location, single-day events in the T1 window and AOI), not dated settlement captures (none on disk); DEVIATIONS 2026-10-27.",
        "Karabakh scored at the PREREG 5 km / ±2 day rule while the filed prediction is at the model's 1 km / 48 h definition (DEVIATIONS 2026-10-22); the 1 km row is the like-for-like comparison.",
        "Sudan prediction assumed S-NPP + NOAA-20 + NOAA-21 overpass cadence; T2 fires on disk are S-NPP only, which should push observed recall below the prediction for cadence reasons alone.",
        "±15 pp band is wide relative to predictions of 3% and 11%: the band floor is 0 for both cases, so the test can fail only from above.",
        "CI: cluster bootstrap over event-days, 2,000 draws, percentile 95%.",
    ],
}
(RES / "h7_scored.json").write_text(json.dumps(out, indent=2, default=lambda x: x.item() if hasattr(x, "item") else str(x)))

meta_extra = {"rules": RULES, "primary_rule": {c: v["primary"] for c, v in CASES.items()}, "band_pp": 15, "n_boot": N_BOOT,
              "cluster": "event-day (UCDP date_start)", "projection": "local aeqd centred on AOI",
              "fires": "VIIRS S-NPP country CSVs, confidence n/h, any type, dedup on lat/lon/time",
              "events": "UCDP GED 26.1; precise = where_prec 1 & date_prec 1; loose = where_prec<=2 & date_prec<=2; "
                        "Karabakh = country Azerbaijan|Armenia in AOI/window; Sudan = adm_1 ~ Darfur|Kordofan in AOI/window",
              "prediction_file": "predictions/transfer_v1.json (tag transfer-v1)"}
inputs = {"predictions": PRED, "ucdp_ged": GED}
for c, cfg in CASES.items():
    inputs[f"fires_{c}"] = cfg["fires"]
for o in ("h7_scored.csv", "h7_scored.json"):
    write_meta(RES / o, inputs=inputs, counts=counts, extra=meta_extra)

jp = "supported (PREREG: 'within band for Sudan (predicted high recall); Karabakh within band but lower')"
save_verdict("H7", {
    "criterion": out["criterion"] + " (Karabakh 5 km / ±2 d; Sudan 1 km / ±12 h)",
    "result": f"Karabakh {fmt(kb)}; Sudan {fmt(sd)}; Karabakh lower than Sudan under the same rule: {lower} (1 km and 5 km); "
              f"cross-rule primary comparison: {lower_primary_cross_rule}. "
              f"Secondary: Karabakh at 1 km/±12 h {100*sec.loc['karabakh_2020','observed_recall']:.1f}%, "
              f"Sudan at 5 km/±2 d {100*sec.loc['sudan_2023_2025','observed_recall']:.1f}%",
    "verdict": verdict, "jackson_prediction": jp, "claude_prediction": jp,
    "jackson_right": bool(verdict == "supported" and lower), "claude_right": bool(verdict == "supported" and lower),
    "label": "confirmatory", "source": "h7_scored.json",
    "note": "Karabakh events = UCDP GED (no settlement-capture list on disk; DEVIATIONS 2026-10-27). Band floor is 0 for both cases.",
})

# ---- figure ----
fig, ax = plt.subplots(figsize=(7.2, 4.2))
names = {"karabakh_2020": "Karabakh 2020", "sudan_2023_2025": "Sudan (Darfur/Kordofan) 2023–25"}
for i, c in enumerate(CASES):
    pr = prim.loc[c]; p = pr.predicted_recall
    ax.add_patch(plt.Rectangle((i - 0.38, max(0, p - BAND) * 100), 0.76, (min(1, p + BAND) - max(0, p - BAND)) * 100,
                               color="0.9", zorder=0, label="±15 pp band" if i == 0 else None))
    ax.errorbar(i - 0.18, p * 100, yerr=[[100 * (p - pr.pred_int90_lo)], [100 * (pr.pred_int90_hi - p)]], fmt="s", color="#4C72B0",
                capsize=4, label="predicted (90% int.)" if i == 0 else None)
    ax.errorbar(i + 0.02, pr.observed_recall * 100, yerr=[[100 * (pr.observed_recall - pr.ci95_lo)], [100 * (pr.ci95_hi - pr.observed_recall)]],
                fmt="o", color="#C44E52", capsize=4, label="observed, primary rule (95% CI)" if i == 0 else None)
    s = sec.loc[c]
    ax.errorbar(i + 0.20, s.observed_recall * 100, yerr=[[100 * (s.observed_recall - s.ci95_lo)], [100 * (s.ci95_hi - s.observed_recall)]],
                fmt="o", mfc="white", color="#C44E52", capsize=4, label="observed, other rule (95% CI)" if i == 0 else None)
    ax.text(i, -4.5, f"primary {pr.rule.replace('_', ' / ')}; n={pr.n_events}", ha="center", fontsize=7, color="0.35")
ax.set_xticks(range(len(CASES))); ax.set_xticklabels([names[c] for c in CASES])
ax.set_ylabel("recall (%)"); ax.set_xlim(-0.6, len(CASES) - 0.4); ax.set_ylim(-7, None)
ax.set_title(f"H7 transfer: filed prediction vs observed — verdict: {verdict}", fontsize=10)
ax.legend(fontsize=7, loc="upper left", frameon=False)
fig.tight_layout(); fig.savefig(FIG / "h7_transfer.png", dpi=200); plt.close(fig)

cap = (f"\n**h7_transfer.png** — **confirmatory.** H7 (PREREG §4): recall of VIIRS S-NPP (conf n/h) for UCDP GED 26.1 "
       f"exact-location single-day events, Karabakh 2020-09-27..11-10 (primary rule 5 km / ±2 d; UCDP used because no dated "
       f"settlement-capture list was on disk, DEVIATIONS 2026-10-27) and Darfur/Kordofan 2023-04-15..2025-12-31 (primary rule "
       f"1 km / ±12 h, PREREG §3). Blue = prediction filed in predictions/transfer_v1.json before T1/T2 download (90% coefficient "
       f"interval); red filled = observed under the primary rule, open = under the other rule; 95% CIs from a cluster bootstrap "
       f"over event-days (2,000 draws). Grey = ±15 pp pass band. Verdict: {verdict}. Source: data/derived/results/h7_scored.csv.\n")
cp = FIG / "CAPTIONS.md"; cur = cp.read_text()
if "**h7_transfer.png**" in cur:
    cur = re.sub(r"\n\*\*h7_transfer\.png\*\*.*?\n(?=\n|\Z)", cap.rstrip("\n") + "\n", cur, flags=re.S)
else:
    cur += cap
cp.write_text(cur)
log(f"H7 verdict: {verdict}; Karabakh {fmt(kb)}; Sudan {fmt(sd)}")
print(T[["case", "rule", "event_set", "n_events", "observed_recall", "ci95_lo", "ci95_hi", "diff_pp", "within_band"]].round(4).to_string(index=False))
