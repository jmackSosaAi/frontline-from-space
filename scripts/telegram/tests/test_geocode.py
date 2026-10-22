"""Geocoder evaluation on the 200 hand-labelled strings (geocode_cases.csv).
Run: .venv/bin/python -I scripts/telegram/tests/test_geocode.py   -> prints metrics, writes
data/derived/telegram/qa/geocode_eval.json (+ geocode_eval_errors.csv: strings only, no post text).
Labels were written by hand (Claude, from place knowledge) BEFORE looking at resolver output.
truth: place | none (not a place / unresolvable by design) | ambiguous (many same-name places, null expected) |
       skip (labeller unsure, excluded) | <site key> | oblast:<ISO> (launch sites).
A settlement result is correct iff the matched gazetteer feature carries truth_name_uk (any alt, normalised)
among its names AND its oblast is in truth_oblast_iso. Precision = correct / resolved(place-or-ambiguous labels
counted as errors when resolved wrongly, 'none' labels resolved = false positive).
Recall = correct / labels with truth == place."""
import importlib.util, json, pathlib, sys, collections
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
TG = HERE.parent
sys.path.insert(0, str(TG))
spec = importlib.util.spec_from_file_location("resolve30", TG / "30_resolve.py")
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
import yaml
G = R.Gaz(yaml.safe_load(R.TAXONOMY.read_text(encoding="utf-8")))
byid = {}
for f in G.feats:
    byid.setdefault(f["id"], f)


def nz(x):
    return None if (x is None or (isinstance(x, float) and x != x) or x == "") else x


def main():
    c = pd.read_csv(HERE / "geocode_cases.csv", keep_default_na=False)
    out = []
    for r in c.itertuples():
        if r.kind == "launch_site":
            s = G.site(r.string, None)
            got = s["site_key"] or (f"oblast:{s['site_oblast_iso']}" if s["site_oblast_iso"] else "none")
            ok = got == r.truth
            out.append(dict(id=r.id, kind=r.kind, string=r.string, truth=r.truth, got=got, ok=ok, method=s["site_geo_method"],
                            resolved=got != "none", scored=True))
            continue
        res = G.geocode(r.string, nz(r.oblast_iso), nz(r.raion_raw))
        resolved = res["lat"] is not None
        scored = r.truth != "skip"
        ok = None
        if r.truth == "place":
            if resolved:
                f = byid[res["geo_id"]] if res["geo_level"] != "raion" else None
                names = f["names"] if f else set()
                alts = {R.norm(x) for x in r.truth_name_uk.split("|")}
                ok = bool(f) and bool(alts & names) and f["iso"] in r.truth_oblast_iso.split("|")
            else:
                ok = False
        elif r.truth in ("none", "ambiguous"):
            ok = not resolved
        out.append(dict(id=r.id, kind=r.kind, string=r.string, truth=r.truth, got=res["geo_name"], ok=ok, method=res["geo_method"],
                        conf=res["geo_conf"], resolved=resolved, scored=scored, truth_name=r.truth_name_uk))
    d = pd.DataFrame(out)
    m = {}
    st = d[(d.kind != "launch_site") & d.scored]
    pl = st[st.truth == "place"]
    res_ = st[st.resolved]
    tp = int(((st.truth == "place") & st.resolved & (st.ok == True)).sum())
    m["settlement"] = dict(n=len(st), n_place=len(pl), resolved=len(res_), correct=tp,
                           precision=round(tp / max(len(res_), 1), 3), recall=round(tp / max(len(pl), 1), 3),
                           false_positive_on_none_or_ambiguous=int(((st.truth != "place") & st.resolved).sum()),
                           wrong_place=int(((st.truth == "place") & st.resolved & (st.ok == False)).sum()),
                           missed_place=int(((st.truth == "place") & ~st.resolved).sum()))
    for k, g in st.groupby("kind"):
        gp = g[g.truth == "place"]; gr = g[g.resolved]; t = int(((g.truth == "place") & g.resolved & (g.ok == True)).sum())
        m["settlement_" + k] = dict(n=len(g), precision=round(t / max(len(gr), 1), 3), recall=round(t / max(len(gp), 1), 3))
    mth = collections.OrderedDict()
    for meth, g in res_.groupby("method"):
        mth[meth] = dict(n=len(g), correct=int(((g.truth == "place") & (g.ok == True)).sum()))
    m["precision_by_method"] = mth
    hi = res_[res_.conf >= 0.8]
    m["settlement_conf_ge_0.8"] = dict(resolved=len(hi), correct=int(((hi.truth == "place") & (hi.ok == True)).sum()))
    si = d[d.kind == "launch_site"]
    sp = si[si.truth != "none"]; sr = si[si.resolved]
    stp = int(((si.truth != "none") & si.resolved & (si.ok == True)).sum())
    m["launch_site"] = dict(n=len(si), n_site=len(sp), resolved=len(sr), correct=stp,
                            precision=round(stp / max(len(sr), 1), 3), recall=round(stp / max(len(sp), 1), 3),
                            false_positive_on_none=int(((si.truth == "none") & si.resolved).sum()))
    m["skipped_unsure_labels"] = int((~d.scored).sum())
    qa = R.ROOT / "data" / "derived" / "telegram" / "qa"; qa.mkdir(parents=True, exist_ok=True)
    (qa / "geocode_eval.json").write_text(json.dumps(m, ensure_ascii=False, indent=2))
    err = d[(d.scored) & (d.ok == False) | ((d.kind != 'launch_site') & (d.truth.isin(['none', 'ambiguous'])) & d.resolved)]
    err.to_csv(qa / "geocode_eval_errors.csv", index=False)
    print(json.dumps(m, ensure_ascii=False, indent=1))
    print(err[["id", "kind", "string", "truth", "truth_name", "got", "method"]].to_string() if "truth_name" in err else err.to_string())
    return m


if __name__ == "__main__":
    main()
