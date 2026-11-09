#!/usr/bin/env python
"""L7 QA round 2: packet of the "agree" impact rows no person has checked yet.

The 30-row audit of the agree bucket found errors in four of five fields (planning/QA_HANDCHECK.md, 2026-11-09), so the
decision rule requires a human check of every remaining agree row. This writes those rows, in the same
compare-and-click format as round 1 (English translation, y/n columns, .xlsx copy), to
data/interim/telegram/qa/ra_packet_round2/ra_impacts_r2.{csv,xlsx} and appends their bucket to ra_packet/_key.csv.
Put the returned file (e.g. ra_impacts_r2_PD.csv) in ra_packet/ and re-run 92_qa_score.py.

  .venv/bin/python -I scripts/telegram/94_qa_round2.py --dry-run   # counts only, no network
  .venv/bin/python -I scripts/telegram/94_qa_round2.py
"""
from __future__ import annotations
import argparse, importlib.util, sys, pathlib
from concurrent.futures import ThreadPoolExecutor
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pandas as pd
import llm
from _common import INTERIM, write_meta, log

spec = importlib.util.spec_from_file_location("qa_translate", HERE / "93_qa_translate.py")
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)

QA = INTERIM / "qa"
PACKET, OUT = QA / "ra_packet", QA / "ra_packet_round2"
SEED = 20261014
SHOW = ["url", "text", "event_date", "event_time", "oblast_raw", "raion_raw", "settlement_raw", "location_withheld",
        "weapon_raw", "target_type", "killed", "wounded", "is_debris_only", "n_incidents_in_post"]
BLANK = ["chk_place_ok", "chk_weapon_ok", "chk_target_type_ok", "chk_casualties_ok", "chk_time_ok", "chk_all_found",
         "chk_missed_incidents_in_post", "chk_note"]
ID = ["channel", "msg_id", "incident_idx"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    tri = pd.read_csv(QA / "triage_impacts.csv", dtype=str)
    key = pd.read_csv(PACKET / "_key.csv", dtype=str)
    norm = lambda df: [(c, str(int(float(m))), str(int(float(i)))) for c, m, i in df[ID].values]   # "2.0" == "2"
    seen = set(norm(key[key.sheet == "imp"]))
    agree = tri[tri.bucket == "agree"]
    todo = agree[[v not in seen for v in norm(agree)]]
    if len(agree) - len(todo) != (key[key.sheet == "imp"].bucket == "agree").sum():
        sys.exit("agree rows already in the packet do not match _key.csv; nothing written")
    todo = todo.sample(frac=1, random_state=SEED).reset_index(drop=True)
    start = key[key.sheet == "imp"].row_id.str[-3:].astype(int).max() + 1
    log(f"agree rows {len(agree)}, already in a packet {len(agree) - len(todo)}, round 2 rows {len(todo)}; "
        f"unique posts {todo.text.nunique()}")
    if a.dry_run or todo.empty:
        return
    todo.insert(0, "row_id", [f"imp-{start + i:03d}" for i in range(len(todo))])

    jobs: dict[str, list[str]] = {}
    for r in todo.itertuples():
        t = jobs.setdefault(T.s(r.text), [])
        for x in T.place_terms(r) + [T.s(r.weapon_raw)]:
            if x and x not in t:
                t.append(x)

    def one(item):
        text, terms = item
        out = llm.call(T.PV, T.SYSTEM, f"POST:\n{text}\n\nterms: {terms}", T.SCHEMA, T.MODEL, max_tokens=4096, effort="low")
        return text, out["text_en"].strip(), dict(zip(terms, out.get("terms_en") or []))
    with ThreadPoolExecutor(6) as ex:
        res = {t: (en, tr) for t, en, tr in ex.map(one, jobs.items())}

    def term(text, x):
        x = T.s(x)
        e = res[T.s(text)][1].get(x, "") if x else ""
        return (f"{e} ({x})" if e and e.casefold() != x.casefold() else x)

    imp = todo[["row_id"] + SHOW].copy()
    imp["text_en"] = ["[Machine translation, check the Ukrainian original if a detail decides your answer]\n\n"
                      + res[T.s(t)][0] for t in imp.text]
    imp["place_en"] = [", ".join(p for p in (term(r.text, r.settlement_raw), term(r.text, r.raion_raw),
                                              term(r.text, r.oblast_raw)) if p)
                       or ("withheld by the post" if T.s(r.location_withheld).lower() == "true" else "(none)")
                       for r in imp.itertuples()]
    imp["weapon_en"] = [term(r.text, r.weapon_raw) or "(none named)" for r in imp.itertuples()]
    for c in ("killed", "wounded"):
        imp[c] = imp[c].fillna("").map(lambda v: "none reported" if T.s(v) in ("", "0", "0.0") else str(int(float(v))))
    for c in BLANK:
        imp[c] = ""
    imp = imp[[c for c in T.IMP_ORDER if c in imp.columns]]

    OUT.mkdir(parents=True, exist_ok=True)
    imp.to_csv(OUT / "ra_impacts_r2.csv", index=False)
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook(); ws = wb.active; ws.title = "ra_impacts_r2"
    ws.append(list(imp.columns))
    for row in imp.itertuples(index=False):
        ws.append([T.s(v) for v in row])
    wide = {"text_en": 70, "text": 50, "place_en": 32, "weapon_en": 22, "chk_note": 30, "url": 28}
    dv = DataValidation(type="list", formula1='"y,n"', allow_blank=True); ws.add_data_validation(dv)
    for j, c in enumerate(imp.columns, 1):
        col = ws.cell(row=1, column=j).column_letter
        ws.column_dimensions[col].width = wide.get(c, 14)
        ws.cell(row=1, column=j).font = Font(bold=True)
        if c.startswith("chk_"):
            ws.cell(row=1, column=j).fill = PatternFill("solid", fgColor="FFF2CC")
            if c not in ("chk_missed_incidents_in_post", "chk_note"):
                dv.add(f"{col}2:{col}{len(imp) + 1}")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "B2"
    wb.save(OUT / "ra_impacts_r2.xlsx")

    add = todo[["row_id"] + ID].assign(bucket="agree", sheet="imp", n_bucket_total=str(len(agree)))
    pd.concat([key, add[key.columns]]).to_csv(PACKET / "_key.csv", index=False)
    write_meta(OUT / "ra_impacts_r2.csv", inputs={"triage_impacts": QA / "triage_impacts.csv"},
               counts={"rows": len(imp), "posts": len(jobs)}, prompt_version=T.PV)
    log(f"round 2 packet: {len(imp)} rows in {OUT}; key rows appended to {PACKET / '_key.csv'}")


if __name__ == "__main__":
    main()
