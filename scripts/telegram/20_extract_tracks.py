#!/usr/bin/env python
"""L3 (tracks): posts_typed.parquet -> extract/tracks.parquet

One row per track statement (a post may hold several: one per line / "; " clause).
Source: post_type == 'track' posts of kpszsu, war_monitor, monitoringwar.
Pure regex; all patterns live in taxonomy.yaml (`track_extraction`, `weapon_classes`, `oblasts`).
Fields: ts, channel, msg_id, seg_idx, weapon_class, weapon_raw, count, count_unit, count_raw,
oblast_raw, oblast_role, oblast_iso, oblast_iso_src, raion_raw, settlement_raw, settlement_role,
settlements_all, heading_raw, text_span (+ span_start/span_end into text_norm).
Roles: location (where it is) > target (heading to) > origin (coming from); 'bare' = line-leading
place; 'context' = oblast taken from a preceding header line. Raw strings are NOT declension-normalised.
"""
from __future__ import annotations
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import regex as re
import yaml

try:
    from _common import INTERIM, TAXONOMY, write_meta, log
except Exception:  # pragma: no cover
    raise

F = re.IGNORECASE | re.UNICODE
TRACK_CHANNELS = ["kpszsu", "war_monitor", "monitoringwar"]
WEAPON_ORDER = ["kinzhal", "kab", "ballistic", "cruise", "jet_uav", "recon_uav", "shahed", "unknown"]
PLACE_CASE = re.UNICODE  # place tokens are case-sensitive (capitalised)


class Cfg:
    def __init__(self, tax: dict):
        te = tax["track_extraction"]
        self.version = te["version"]
        place = te["place"]
        self.place_s = place
        self.place = re.compile(place)
        self.emoji_weapon = te["emoji_weapon"]
        self.oblast_form = re.compile(te["oblast_form"], PLACE_CASE)
        self.raion = re.compile(te["raion"], PLACE_CASE)
        self.count_x = re.compile(te["count_x"])
        self.count_word = re.compile(te["count_word"], F)
        self.count_vague = re.compile(te["count_vague"], F)
        self.heading = re.compile(te["heading"], F)
        self.stop = re.compile(te["stop_place"], F)
        mk = lambda alt: re.compile(r"(?<![\p{L}])(?:%s)\s*(?:м\.\s?|н\.\s?п\.\s?|с\.\s?|смт\.?\s?)?(?P<p>%s)(?![\p{L}])" % (alt, place), PLACE_CASE)
        # markers are lower-case words; compile case-insensitive for the marker only via inline flag
        mk = lambda alt: re.compile(r"(?<![\p{L}])(?i:%s)\s*(?:ТОТ\s+)?(?i:м\.\s?|н\.\s?п\.\s?|с\.\s?|смт\.?\s?)?(?P<p>%s)(?![\p{L}])" % (alt, place))
        self.loc = mk(te["loc_markers"])
        self.tgt = mk(te["tgt_markers"])
        self.org = mk(te["origin_markers"])
        self.bare_lead = re.compile(r"^[^\p{L}\d]*(?P<p>%s(?:\s*[/,]\s*%s)*)\s*(?:[:—–\-.]|$|(?=\d{1,3}\s*[хxX×])|(?=\s+(?i:під\s+атакою|КАР\b|КР\b)))" % (place, place))
        self.bare_tail = re.compile(r"(?:\d{1,3}\s*[хxX×]|(?i:БпЛА|КР|ракет\w*|цілі?|ціль|дрон\w*|реактив\w*|груп\w*|вектор\w*))\s+(?P<p>%s(?:\s*[/,]\s*%s)*)(?![\p{L}])" % (place, place))
        self.weapons = []
        for cls in WEAPON_ORDER:
            pats = tax["weapon_classes"][cls]
            self.weapons.append((cls, re.compile("|".join(pats), F)))
        self.oblast_iso = [(k, re.compile("|".join(v["patterns"]), F)) for k, v in tax["oblasts"].items()
                           if k not in ("UA-30",)]
        self.kyiv_city = re.compile("|".join(tax["oblasts"]["UA-30"]["patterns"]), F)
        self.kyiv_obl = re.compile("|".join(tax["oblasts"]["UA-32"]["patterns"]), F)
        self.city_iso = [(k, re.compile(v)) for k, v in te["city_iso"].items()]
        self.numbered = re.compile(r"^\s*\d{1,2}[.)]\s*")
        self.cont_line = re.compile(r"^[\s\W]*(?i:курс|→|висота|напрям|висотою)")
        self.lead_junk = re.compile(r"^[\s\u200d\ufe0f❗‼⚠🛵🏍🛸🚀🅿🔄🔻🔺📡•▪\-–—→\d.)]+")
        self.channel_tag = re.compile(r"@\w+")


def weapon_of(cfg: Cfg, s: str, lead: str):
    """Earliest-position weapon match; ties by taxonomy order. Falls back to the lead emoji."""
    best = None
    for rank, (cls, rx) in enumerate(cfg.weapons):
        m = rx.search(s)
        if m and (best is None or (m.start(), rank) < (best[1], best[3])):
            best = (cls, m.start(), m.group(0), rank)
    if best:
        return best[0], best[2]
    for em, cls in cfg.emoji_weapon.items():
        if em in lead:
            return cls, em
    return None, None


def count_of(cfg: Cfg, s: str):
    m = cfg.count_x.search(s)
    if m:
        return int(m.group(1)), "drones", m.group(0)
    m = cfg.count_word.search(s)
    if m:
        unit = "groups" if m.group(2).lower().startswith("груп") else "objects"
        return int(m.group(1)), unit, m.group(0)
    m = cfg.count_vague.search(s)
    if m:
        return None, "vague", m.group(0)
    return None, None, None


def oblast_of(cfg: Cfg, s: str):
    """Return (raw, role) from oblast-form mentions in s: location > target > origin."""
    cands = []
    for m in cfg.oblast_form.finditer(s):
        raw = m.group(0).strip()
        pre = s[max(0, m.start() - 30):m.start()]
        pre_clause = re.split(r"[.;\n]", pre)[-1]
        if re.search(r"(?i:(?<![\p{L}])(?:з|із|від|зі))\s*$", pre_clause):
            role = "origin"
        elif re.search(r"(?i:через|повз|над|біля)\s*$", pre_clause):
            role = "location"
        elif re.search(r"(?i:напрям\w*|бік|курсом\s+на|до|територію)\s*$", pre_clause) or re.search(r"(щину|ччину)\b", raw):
            role = "target"
        elif re.search(r"(?i:\bна)\s*$", pre_clause) and not re.search(r"(щині|ччині|ласті)\b", raw):
            role = "target"
        else:
            role = "location"
        cands.append((raw, role, m.start()))
    if not cands:
        hm = re.match(r"^[^\p{L}]*([А-ЯІЇЄҐ][\p{L}]+(?:ськ|зьк|цьк)а)\s*[:—–\-]", s)   # "Черкаська: ..." header
        if hm:
            return hm.group(1), "location"
    for want in ("location", "target", "origin"):
        for raw, role, _ in cands:
            if role == want:
                return raw, role
    return None, None


def clean_place(cfg: Cfg, p: str):
    p = p.strip(" -'’ʼ")
    if re.search(r"(ськ|цьк|зьк)(ої|ій|ою|а)$", p):
        return None   # feminine adjective = oblast adjective ("Полтавської"), not a settlement
    if not p or cfg.stop.search(p) or cfg.oblast_form.fullmatch(p) or re.fullmatch(r"[А-ЯІЇЄҐа-яіїєґ'’ʼ\-]+(щин|ччин)[аиіуоюе]", p):
        return None
    # strip trailing stop word of a two-word candidate ("Київ Уважно")
    parts = p.split(" ")
    if len(parts) == 2 and parts[0] in ("На", "До", "В", "У", "Від", "З", "Із", "Повз", "Біля", "Через", "Над"):
        p = parts[1]; parts = [p]   # sentence-initial preposition glued to the place
    if len(parts) == 2 and cfg.stop.search(parts[1]):
        return parts[0]
    if len(parts) == 2 and cfg.stop.search(parts[0]):
        return None
    return p


RAION_FOLLOW = re.compile(r"(?:\s*(?:[,/]|(?i:та|і|й))\s*[А-ЯІЇЄҐ][\p{L}'’\-]*(?:ськ|цьк|зьк)[\p{L}]*)*\s*(?i:район\w*|р-н\w*|р\.|област|обл\b|ради|громад|округ|водосхов\\w*|мор\\w+|лиман\\w*|озер\\w*|річк\\w*|кос\\w*)")


def is_raion_adj(s: str, end: int, tok: str = "") -> bool:
    """True when the token ending at `end` is an adjective of a raion/oblast/hromada ("Лубенський район")."""
    if tok and not re.search(r"(ськ|цьк|зьк)\w*$", tok.split(" ")[-1]):
        return False
    return bool(RAION_FOLLOW.match(s[end:end + 90]))


def settlement_of(cfg: Cfg, s: str):
    """-> (primary, role, all_list). location markers > bare lead/tail > target > origin."""
    found = []   # (pos, place, role)
    for role, rx in (("location", cfg.loc), ("target", cfg.tgt), ("origin", cfg.org)):
        for m in rx.finditer(s):
            pl = clean_place(cfg, m.group("p"))
            if pl and is_raion_adj(s, m.end("p"), pl):
                continue   # "Вишгородський район": raion adjective, not a settlement
            if pl:
                found.append((m.start("p"), pl, role))
                tail = s[m.end("p"):]
                while True:
                    mm = re.match(r"\s*(?:[,/]|(?i:та|і|й))\s*(?P<p>%s)(?![\p{L}])" % cfg.place_s, tail)
                    if not mm:
                        break
                    pl2 = clean_place(cfg, mm.group("p"))
                    if pl2:
                        found.append((m.end("p") + 0.5, pl2, role))
                    tail = tail[mm.end():]
    for m in cfg.bare_lead.finditer(s):
        for part in re.split(r"\s*[/,]\s*", m.group("p")):
            pl = clean_place(cfg, part)
            if pl and not is_raion_adj(s, m.start("p") + len(part), pl):
                found.append((m.start("p"), pl, "bare"))
    for m in cfg.bare_tail.finditer(s):
        for part in re.split(r"\s*[/,]\s*", m.group("p")):
            pl = clean_place(cfg, part)
            if pl and not is_raion_adj(s, m.start("p") + len(part), pl):
                found.append((m.start("p"), pl, "bare"))
    # drop places that are really raion adjectives or oblast forms (already filtered) and dups
    seen, allp = set(), []
    for pos, pl, role in [f for _, f in sorted(enumerate(found), key=lambda x: (x[1][0], x[0]))]:
        if pl not in seen:
            seen.add(pl); allp.append((pl, role))
    for want in (("location", "bare"), ("target",), ("origin",)):
        for pl, role in allp:
            if role in want:
                return pl, role, [p for p, _ in allp]
    return None, None, []


def iso_of(cfg: Cfg, oblast_raw, settlement_raw):
    if oblast_raw:
        if cfg.kyiv_obl.search(oblast_raw):
            return "UA-32", "oblast"
        for k, rx in cfg.oblast_iso:
            if rx.search(oblast_raw):
                return k, "oblast"
    if settlement_raw:
        for k, rx in cfg.city_iso:
            if rx.search(settlement_raw):
                return k, "city"
    return None, None


def split_segments(cfg: Cfg, text: str):
    """Yield dicts {text, start, end, ctx_oblast}. Header lines (end with ':' / no weapon+count) set context;
    'Курс ...' / '→' lines are appended to the previous segment."""
    segs, ctx_oblast, pos = [], None, 0
    for line in text.split("\n"):
        start = pos
        pos += len(line) + 1
        raw = line
        if not raw.strip():
            continue
        s = cfg.channel_tag.sub("", raw).replace("\ufe0f", "").replace("\u200d", "")  # VS16 breaks \b after emoji
        s = cfg.numbered.sub("", s)
        if re.fullmatch(r"[\s\W]*(?i:увага|уважно|перебувайте в укриттях|не ігноруйте[^.]*|будьте обережні)[\s\W]*", s):
            continue
        if cfg.cont_line.match(s) and segs and segs[-1]["text"] is not None:
            segs[-1]["text"] += " | " + s.strip(); segs[-1]["end"] = start + len(raw)
            continue
        stripped = s.strip()
        # header: ends with ':' -> context only
        if stripped.endswith(":"):
            ob, _ = oblast_of(cfg, stripped)
            if ob:
                ctx_oblast = ob
            else:
                pl = cfg.bare_lead.match(stripped)
                if pl:
                    ctx_oblast = ctx_oblast  # city header: handled as place of following lines
            hdr_place = cfg.bare_lead.match(stripped)
            segs.append({"text": None, "hdr": stripped, "start": start, "end": start + len(raw), "ctx": ctx_oblast})
            continue
        for part in re.split(r";\s*(?=[^;]*\d{1,3}\s*[хxX×])", stripped):
            segs.append({"text": part, "start": start, "end": start + len(raw), "ctx": ctx_oblast})
    return segs


def extract_post(cfg: Cfg, text: str, lead: str = ""):
    rows, hdr_place = [], None
    segs = split_segments(cfg, text)
    for sg in segs:
        if sg["text"] is None:
            hp = cfg.bare_lead.match(sg["hdr"])
            hdr_place = clean_place(cfg, hp.group("p").split("/")[0].strip()) if hp and not cfg.oblast_form.search(sg["hdr"]) else None
            continue
        s = sg["text"]
        cls, wraw = weapon_of(cfg, s, s[:6] + (lead if not rows else ""))
        cnt, unit, craw = count_of(cfg, s)
        ob, orole = oblast_of(cfg, s)
        if cls is None and cnt is None and not ob and craw is None and not cfg.loc.search(s) and not cfg.tgt.search(s):
            continue   # no weapon, count, oblast or place cue: not a track statement
        ob, orole = oblast_of(cfg, s)
        if ob is None and sg.get("ctx"):
            ob, orole = sg["ctx"], "context"
        st, srole, allp = settlement_of(cfg, s)
        if st is None and hdr_place:
            st, srole, allp = hdr_place, "context", [hdr_place]
        hm = cfg.heading.search(s)
        rz = cfg.raion.search(s)
        iso, isrc = iso_of(cfg, ob, st)
        if iso is None and hdr_place:
            iso, isrc = iso_of(cfg, None, hdr_place)
        rows.append(dict(seg_idx=len(rows), weapon_class=cls or "unknown", weapon_raw=wraw,
                         count=cnt, count_unit=unit, count_raw=craw,
                         oblast_raw=ob, oblast_role=orole, oblast_iso=iso, oblast_iso_src=isrc,
                         raion_raw=rz.group(0) if rz else None,
                         settlement_raw=st, settlement_role=srole, settlements_all="|".join(allp) or None,
                         heading_raw=hm.group(0).strip(" ,") if hm else None,
                         text_span=s[:300], span_start=sg["start"], span_end=sg["end"]))
    return rows


def main() -> None:
    import pandas as pd
    tax = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    cfg = Cfg(tax)
    src = INTERIM / "posts_typed.parquet"
    df = pd.read_parquet(src, columns=["channel", "msg_id", "ts_utc", "ts_kyiv", "text_norm", "lead_emoji", "post_type"])
    df = df[(df.post_type == "track") & df.channel.isin(TRACK_CHANNELS)]
    log(f"extracting tracks from {len(df)} track posts (rules {cfg.version})")
    out, n_empty = [], 0
    for ch, mid, ts, tk, txt, lead in zip(df.channel, df.msg_id, df.ts_utc, df.ts_kyiv, df.text_norm, df.lead_emoji):
        rows = extract_post(cfg, txt, lead or "")
        if not rows:  # keep one row so every track post is represented
            n_empty += 1
            cls, wraw = weapon_of(cfg, txt, lead or "")
            c, u, cr = count_of(cfg, txt)
            rows = [dict(seg_idx=0, weapon_class=cls or "unknown", weapon_raw=wraw, count=c, count_unit=u, count_raw=cr,
                         oblast_raw=None, oblast_role=None, oblast_iso=None, oblast_iso_src=None, raion_raw=None,
                         settlement_raw=None, settlement_role=None, settlements_all=None, heading_raw=None,
                         text_span=txt[:300], span_start=0, span_end=len(txt))]
        for r in rows:
            r.update(channel=ch, msg_id=mid, ts_utc=ts, ts_kyiv=tk)
            out.append(r)
    t = pd.DataFrame(out)
    cols = ["ts_utc", "ts_kyiv", "channel", "msg_id", "seg_idx"] + [c for c in t.columns if c not in
            ("ts_utc", "ts_kyiv", "channel", "msg_id", "seg_idx")]
    t = t[cols]
    t["count"] = t["count"].astype("Int64")
    dst = INTERIM / "extract" / "tracks.parquet"
    dst.parent.mkdir(parents=True, exist_ok=True)
    t.to_parquet(dst, index=False)
    counts = {"track_posts": int(len(df)), "rows": int(len(t)), "posts_without_segment_fallback": n_empty,
              "share_settlement": round(float(t.settlement_raw.notna().mean()), 4),
              "share_oblast_raw": round(float(t.oblast_raw.notna().mean()), 4),
              "share_oblast_iso": round(float(t.oblast_iso.notna().mean()), 4),
              "share_count": round(float(t["count"].notna().mean()), 4),
              "share_heading": round(float(t.heading_raw.notna().mean()), 4),
              "by_channel": t.channel.value_counts().to_dict(),
              "by_weapon": t.weapon_class.value_counts().to_dict()}
    write_meta(dst, inputs={"posts_typed": src, "taxonomy": TAXONOMY}, counts=counts,
               extra={"rules_version": cfg.version, "taxonomy_version": tax["version"]})
    log(str(counts))


if __name__ == "__main__":
    main()
