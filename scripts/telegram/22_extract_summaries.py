"""L3: parse Air Force (kpszsu) daily summaries -> extract/summaries.parquet.

Regex-first. Where a post resists, the row is written with nulls + parse_status; nothing is guessed.
Input : data/interim/telegram/posts_typed.parquet (channel=kpszsu, post_type=daily_summary)
Output: data/interim/telegram/extract/summaries.parquet (+ summaries_meta.json)
        data/interim/telegram/extract/summaries_qa_unparsed.csv  (msg_id, status, first line; interim only)
"""
from __future__ import annotations
import json, sys, datetime as dt
from pathlib import Path
import regex as re
import pandas as pd, yaml
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import INTERIM, TAXONOMY, write_meta, log

PARSER_VERSION = "summaries-1"
IN_PATH = INTERIM / "posts_typed.parquet"
OUT_DIR = INTERIM / "extract"
OUT_PATH = OUT_DIR / "summaries.parquet"

TAX = yaml.safe_load(open(TAXONOMY, encoding="utf-8"))

MONTHS = {m: i + 1 for i, m in enumerate(
    ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня",
     "вересня", "жовтня", "листопада", "грудня"])}
MONTHS_NOM = {m: i + 1 for i, m in enumerate(
    ["січень", "лютий", "березень", "квітень", "травень", "червень", "липень", "серпень",
     "вересень", "жовтень", "листопад", "грудень"])}
MONTH_RE = "(" + "|".join(MONTHS) + ")"

# Ukrainian number words (nominative/instrumental/genitive forms) -> int
WORDNUM = {
    "одн": 1, "один": 1, "одна": 1, "одну": 1, "одним": 1, "одній": 1, "одного": 1, "одної": 1,
    "дв": 2, "два": 2, "дві": 2, "двох": 2, "двома": 2,
    "три": 3, "трьох": 3, "трьома": 3,
    "чотир": 4, "чотири": 4, "чотирьох": 4, "чотирма": 4,
    "п'ят": 5, "п’ят": 5, "пʼят": 5, "шіст": 6, "шест": 6, "сім": 7, "сьом": 7, "сем": 7,
    "вісім": 8, "восьм": 8, "дев'ят": 9, "дев’ят": 9, "десят": 10,
    "одинадцят": 11, "дванадцят": 12, "тринадцят": 13, "чотирнадцят": 14, "п'ятнадцят": 15,
    "п’ятнадцят": 15, "шістнадцят": 16, "сімнадцят": 17, "вісімнадцят": 18, "дев'ятнадцят": 19,
    "дев’ятнадцят": 19, "двадцят": 20, "тридцят": 30, "сорок": 40, "п'ятдесят": 50, "п’ятдесят": 50,
    "півсотні": 50, "півтора десятк": 15, "десятк": 10,
}
NUM_WORD_STEMS = r"(?:один|одн|дв|три|трьох|трьома|чотир|п[’'ʼ]ят|шіст|шест|сім|сьом|вісім|восьм|дев[’'ʼ]ят|десят|одинадцят|дванадцят|тринадцят|чотирнадцят|шістнадцят|сімнадцят|вісімнадцят|двадцят|тридцят|сорок|півсотні)"
NUM_RE = r"(?:\d+|(?<![А-ЯІЇЄа-яіїє])" + NUM_WORD_STEMS + r"[а-яіїє’'ʼ]*)"


def word_to_int(tok: str) -> int | None:
    tok = tok.strip().lower()
    if tok.isdigit():
        return int(tok)
    # longest matching stem
    for stem in sorted(WORDNUM, key=len, reverse=True):
        if tok.startswith(stem):
            return WORDNUM[stem]
    return None


def num_at(m: str) -> int | None:
    m = re.sub(r"[-–](ма|ми|м|х|ти|та|ть|ох|ом|ьох|ьома|ьма|и|а)$", "", m)
    return word_to_int(m)


# ---------------------------------------------------------------- weapon class per clause
W_MISSILE = re.compile(r"ракет|Кинджал|Кінджал|Х-\s?\d|X-\s?\d|Калібр|Іскандер|С-300|С-400|Онікс|Циркон|Орєшнік|Орешник", re.I)
W_ORDER = ["kinzhal", "kab", "ballistic", "cruise"]
W_PAT = {k: re.compile("|".join(v), re.I) for k, v in TAX["weapon_classes"].items()}
W_RECON = re.compile(r"розвідувальн|Орлан|ZALA|Zala|Supercam|Ланцет|Lancet|Мерлін|Форпост|Молні", re.I)
W_JET = re.compile(r"^\W*реактивн", re.I)
W_UAV = re.compile(r"БпЛА|БПЛА|дрон|безпілотн|Shahed|Шахед|шахед|Герань|Гербер|Пародія|імітатор|повітрян\w+ ціл", re.I)


def weapon_class(desc: str) -> str:
    if W_MISSILE.search(desc):
        for k in W_ORDER:
            if W_PAT[k].search(desc):
                return k
        return "missile_other"
    if W_JET.search(desc):
        return "jet_uav"
    if W_RECON.search(desc):
        return "recon_uav"
    if re.search(r"повітрян\w+ ціл|засоб\w+ повітряного нападу", desc, re.I):
        return "any"
    if W_UAV.search(desc):
        return "shahed"
    return "unknown"


# ---------------------------------------------------------------- period / night date
RE_NICH_NA = re.compile(r"(?:^|(?<=[.!\n➖—-])\s*)У ніч на (\d{1,2}) " + MONTH_RE + r"(?: (\d{4}))?")
RE_NICH_Z = re.compile(r"[Уу] ніч з (\d{1,2})(?: " + MONTH_RE + r")?(?: (\d{4}))? на (\d{1,2}) " + MONTH_RE + r"(?: (\d{4}))?")
RE_VNOCHI = re.compile(r"(?:[Вв]ночі|[Уу]ночі|[Вв] ніч),? (?:з (\d{1,2})(?: " + MONTH_RE + r")? на )?(\d{1,2}) " + MONTH_RE + r"(?: (\d{4}))?")
RE_DATE_NIGHT = re.compile(r"(\d{1,2}) " + MONTH_RE + r"(?: (\d{4}))?(?: року)?,? (?:уночі|вночі)")
RE_START = re.compile(r"\((?:і?з|із)\s*(\d{1,2}[.:]\d{2})\s*(\d{1,2}) " + MONTH_RE + r"\)")
RE_MONTH = re.compile(r"[Пп]ротягом " + MONTH_RE + r" (\d{4})|[Пп]ротягом (?:минулого )?місяця")
RE_WEEK = re.compile(r"[Пп]ротягом (?:минулого )?тижня|за тиждень")
RE_DAY = re.compile(r"[Пп]ротягом (?:дня|доби|поточної доби|денної пори|світлової)|[Бб]лизько \d{1,2}[.:]\d{2}|[Вв]період з|[Вв] період з|[Уу]продовж (?:дня|доби)|[Зз]ранку|[Уу]ранці|[Вв]день|[Уу]день|[Зз] \d{1,2}[.:]\d{2} по \d{1,2}[.:]\d{2}")
RE_ANYDATE = re.compile(r"(\d{1,2})(?:-го|-е)? " + MONTH_RE + r"(?: (\d{4}))?")


def resolve_year(day: int, month: int, year: int | None, post_date: dt.date) -> dt.date | None:
    if year:
        try:
            return dt.date(year, month, day)
        except ValueError:
            return None
    best = None
    for y in (post_date.year, post_date.year - 1, post_date.year + 1):
        try:
            d = dt.date(y, month, day)
        except ValueError:
            continue
        if d <= post_date + dt.timedelta(days=1):
            if best is None or abs((post_date - d).days) < abs((post_date - best).days):
                best = d
    return best


def parse_period(text: str, post_date: dt.date) -> dict:
    out = {"period_kind": None, "night_date": None, "night_date_method": None, "period_start_raw": None}
    m = RE_START.search(text)
    if m:
        out["period_start_raw"] = f"{m.group(1)} {m.group(2)} {m.group(3)}"
    head = text[:600]
    if (m := RE_MONTH.search(head)) and not RE_NICH_NA.search(head):
        out["period_kind"] = "month"
        return out
    if RE_WEEK.search(head) and not RE_NICH_NA.search(head):
        out["period_kind"] = "week"
        return out
    mn, md = RE_NICH_NA.search(text), RE_DAY.search(head)
    if mn and md and md.start() < mn.start() and not RE_START.search(text):
        mn = None
    if m := mn:
        out["period_kind"] = "night"
        out["night_date"] = resolve_year(int(m.group(1)), MONTHS[m.group(2)], int(m.group(3)) if m.group(3) else None, post_date)
        out["night_date_method"] = "nich_na"
        return out
    if m := RE_NICH_Z.search(text):
        out["period_kind"] = "night"
        out["night_date"] = resolve_year(int(m.group(4)), MONTHS[m.group(5)], int(m.group(6)) if m.group(6) else None, post_date)
        out["night_date_method"] = "nich_z_na"
        return out
    if m := RE_VNOCHI.search(text):
        out["period_kind"] = "night"
        out["night_date"] = resolve_year(int(m.group(3)), MONTHS[m.group(4)], int(m.group(5)) if m.group(5) else None, post_date)
        out["night_date_method"] = "vnochi"
        return out
    if m := RE_DATE_NIGHT.search(text):
        out["period_kind"] = "night"
        out["night_date"] = resolve_year(int(m.group(1)), MONTHS[m.group(2)], int(m.group(3)) if m.group(3) else None, post_date)
        out["night_date_method"] = "date_vnochi"
        return out
    if RE_DAY.search(head):
        out["period_kind"] = "day"
        m = RE_ANYDATE.search(text)
        if m:
            out["night_date"] = resolve_year(int(m.group(1)), MONTHS[m.group(2)], int(m.group(3)) if m.group(3) else None, post_date)
            out["night_date_method"] = "day_date_in_text"
        return out
    # 2022-era: header carries the date; no night phrase
    m = RE_ANYDATE.search(text[:300])
    if m:
        out["period_kind"] = "day"
        out["night_date"] = resolve_year(int(m.group(1)), MONTHS[m.group(2)], int(m.group(3)) if m.group(3) else None, post_date)
        out["night_date_method"] = "header_date"
        return out
    out["period_kind"] = "unknown"
    return out


# ---------------------------------------------------------------- launched
RE_ATTACK_PARA = re.compile(r"(?:атакував|атакували|застосував|застосували|застосовано|випустив|випущено|запустив|завда[вл]\w* (?:масованого |комбінованого )?удар|здійснив (?:масовану |комбіновану )?атаку|застосуванн|виявлено|зафіксовано|супровід|[Пп]уски?\b)", re.I)
RE_ZASOBAMI = re.compile(r"(?<!влучанн\w{0,3} )(?<!падінн\w{0,3} )(" + NUM_RE + r")(?:-ма|-ми|-м|-х|-ти|-ох)? (?:зас[оі]б\w* повітряного нападу|повітрян\w+ ці\w+(?= противника| —| –| -|:))", re.I)
RE_ZAGALOM = re.compile(r"(?:Загалом|У цілому|Всього)[^.\n]*?(?:застосува\w+|випустив|випущено)[^.\n]*?(\d+)", re.I)
RE_SUBSET = re.compile(r"(?:із|з) них|у тому числі|в т\.? ?ч\.?|зокрема", re.I)
RE_COUNT_CLAUSE = re.compile(
    r"(?<![\d.:А-ЯІЇЄа-яіїєA-Za-z/-])(" + NUM_RE + r")(?:-ма|-ми|-м|-х|-ти|-та|-ть|-ох|-ьма|-ом)?\s+((?:[^\d;\n.,(]|(?<=[-/А-ЯA-Zа-яa-z\d])\d|\.(?=\S)){2,120}?)(?=[;,.\n(]|\s+(?:із|з|та|і|а також)\s+" + NUM_RE + r"\s|$)", re.I)


RE_SINGULAR_MISSILE = re.compile(
    r"(?<![\d\w]\s)(?<!\d\s)((?:(?:балістичн|крилат|керован|протирадіолокаційн|аеробалістичн|протикорабельн|зенітн|гіперзвуков)\w+\s+){1,2}(?:авіаційн\w+\s+)?ракет(?:ою|а|у)\b[^,;.\n(]{0,45})", re.I)


def clause_entries(block: str) -> list[dict]:
    """Return [{count, type_raw, weapon_class}] for 'N <weapon desc>' clauses in a block of text.
    Unnumbered singular missiles ("балістичною ракетою Іскандер-М") count as 1."""
    out = []
    for m in RE_SINGULAR_MISSILE.finditer(block):
        pre = block[max(0, m.start() - 30): m.start()]
        if re.search(r"(?:" + NUM_RE + r")(?:-\w+)?\s+$", pre) or re.search(r"(?:типу|ракет\w*|та|і|,)\s+$", pre) and re.search(r"\d\s+\S+\s+$", pre):
            continue
        if re.search(r"ракет(?:ами|и|ам)\s*$", pre):
            continue
        desc = m.group(1).strip()
        out.append({"count": 1, "type_raw": desc[:90], "weapon_class": weapon_class(desc), "subset": False, "approx": False, "implicit_one": True})
    # strip the time window "(з 18:00 24 березня)" and "станом на 08:00"
    block = RE_START.sub(" ", block)
    block = re.sub(r"\([^()\n]{0,160}\)", " ", block)  # parentheticals are notes/subsets ("(майже 800 БпЛА)", "(22 ракети і 524 БпЛА)")
    block = re.sub(r"(?:\d{1,2}(?:-го|-е)?\s+)?" + MONTH_RE + r"(?:\s+\d{4})?(?:\s+року)?", " ", block)  # dates are not counts
    block = re.sub(r"(?<!\d)(?:19|20)\d{2}(?:-му|-го|-й)?(?:\s+(?:року|рік|р\.))?", " ", block)
    block = re.sub(r"\d{1,2}[.:]\d{2}", " ", block)
    for m in RE_COUNT_CLAUSE.finditer(block):
        n = num_at(m.group(1))
        desc = m.group(2).strip()
        if n is None or not desc or n > 1500:  # years and junk
            continue
        if re.match(r"^(року|рік|роки|" + "|".join(MONTHS) + r")\b", desc):
            continue
        if not (W_UAV.search(desc) or W_MISSILE.search(desc) or re.search(r"засоб|ціл", desc)):
            continue
        # subset clauses ("понад 80 із них – шахеди") are kept but flagged
        pre = block[max(0, m.start() - 24): m.start()]
        subset = bool(RE_SUBSET.search(desc[:20])) or bool(re.search(r"(із|з) них\s*$", desc)) or bool(RE_SUBSET.search(pre))
        approx = bool(re.search(r"(близько|понад|щонайменше|до|не менше|мінімум)\s*$", pre))
        out.append({"count": n, "type_raw": desc[:90], "weapon_class": weapon_class(desc), "subset": subset, "approx": approx})
    return out


RE_SEP = re.compile(r"^\s*(?:➖{3,}|-{5,}|_{5,}|—{3,})\s*$", re.M)


def split_header(text: str) -> tuple[str, str]:
    """Return (header, body). Header = the uppercase headline before the ➖/---- separator (or line 1 if shouty)."""
    m = RE_SEP.search(text[:400])
    if m:
        return text[:m.start()].strip(), text[m.end():].strip()
    first, _, rest = text.partition("\n")
    letters = [c for c in first if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        return first.strip(), rest.strip()
    return "", text


def split_blocks(text: str) -> tuple[str, str]:
    """Return (attack_block, destroyed_block). Blocks are paragraph runs of the body (header excluded)."""
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=[💥❗✊🇺🇦✈🛩📢])", text) if p.strip()]
    attack, destroyed = [], []
    mode = None
    for p in paras:
        low = p.lower()
        if re.search(r"збито|збиття|знищено|знищення|знешкоджено|подавлено|уражено", low) and not (RE_ATTACK_PARA.search(p) and not re.search(r"^💥|протиповітряною обороною|станом на", low)):
            mode = "d"
        elif RE_ATTACK_PARA.search(p):
            mode = "a"
        elif re.match(r"^[-–▪️•]", p) or re.search(r"\n[-–▪️•]", p):
            pass  # continuation bullets keep the current mode
        elif re.search(r"відбивали|тримаймо|разом – до|влучання|падіння|локаці|основн\w+ напрям", low):
            mode = None
        if mode == "a":
            attack.append(p)
        elif mode == "d":
            destroyed.append(p)
    return "\n".join(attack), "\n".join(destroyed)


RE_ZAGALOM_SENT = re.compile(r"(?:Загалом|У цілому|Всього|Усього|За попередніми результатами)[^.\n]*?(?:застосува\w+|випустив|випущено|атакував)[^\n]*?(?:\.(?=\s|$)|\n|$)", re.I)


def parse_launched(text: str, attack_block: str) -> tuple[int | None, str | None, list[dict]]:
    entries = clause_entries(attack_block) if attack_block else []
    by_type = [e for e in entries]
    for src in (attack_block, text):
        for m in RE_ZASOBAMI.finditer(src or ""):
            ctx = src[max(0, m.start() - 80): m.start()]
            if RE_ATTACK_PARA.search(ctx) and not re.search(r"влучанн|падінн", ctx):
                return num_at(m.group(1)), "zasobamy", by_type
    if m := RE_ZAGALOM_SENT.search(text):
        ents = [e for e in clause_entries(m.group(0)) if not e["subset"]]
        if ents and ents[0]["weapon_class"] == "any":
            return ents[0]["count"], "zagalom", by_type
        if ents:
            return sum(e["count"] for e in ents), "zagalom_sum", by_type
    top = [e for e in entries if not e["subset"] and e["weapon_class"] != "any"]
    if top:
        # "атакував N <uav>" plus other top-level clauses (missiles) are summed
        return sum(e["count"] for e in top), "sum_clauses", by_type
    return None, None, by_type


# ---------------------------------------------------------------- destroyed
RE_DESTROYED_HDR = re.compile(r"(?:ЗБИТО/ПОДАВЛЕНО|ЗБИТО/ПРИДУШЕНО|ЗБИТО|ЗНИЩЕНО|ЗНЕШКОДЖЕНО|ПОДАВЛЕНО)\s+(?:ЩОНАЙМЕНШЕ |ПОНАД |БЛИЗЬКО )?(?:(" + NUM_RE + r")\s+)?(?=(?:[^\n]{0,40}?(?:РАКЕТ|БПЛА|БпЛА|ШАХЕД|ЦІЛ|ДРОН|БЕЗПІЛОТ|ЛІТАК|ВЕРТОЛ|КАЛІБР|КИНДЖАЛ|ІСКАНДЕР|ОРЛАН)))", re.I)
RE_SHOT_FIRE = re.compile(r"(\d+)\s*[—–-]\s*збит[оі] вогневими", re.I)
RE_EW_LOST = re.compile(r"(\d+)(?:[^.\n\d;]|\.(?=\S)){0,90}?локаційно втрачен", re.I)
RE_EW_LOST2 = re.compile(r"(\d+)\s*[—–-]\s*локаційно втрачені/подавлені", re.I)
RE_EW_LOST3 = re.compile(r"(\d+)(?:[^.\n\d;]|\.(?=\S)){0,90}?(?:не досягли (?:своїх )?цілей|подавлен\w* (?:засобами )?РЕБ)", re.I)
RE_DESTROYED_SENT = re.compile(
    r"(?:збито/подавлено|збито/придушено|збито|збиття|знищено|знищення|знищили|збили|знешкоджено|подавлено|уражено)\s+(?:не менше |щонайменше |до |близько )?(?:(" + NUM_RE + r")(?:-ти|-х|-ма|-ми)?\s+)?([^.\n;]{0,200})", re.I)
RE_SINGULAR = re.compile(r"^(?:крилат\w+ ракет\w+|балістичн\w+ ракет\w+|аеробалістичн\w+ ракет\w+|керован\w+ авіаційн\w+ ракет\w+|зенітн\w+ керован\w+ ракет\w+|ракет[уи]\b|ударн\w+ БпЛА|розвідувальн\w+ БпЛА|«?шахед[а»]*\b|ворож\w+ БпЛА)", re.I)
RE_ALL_DESTROYED = re.compile(r"[Уу]сі (?:\d+ )?(«?шахеди»?|ударні БпЛА|ворожі БпЛА|безпілотники|дрони|повітряні цілі|цілі|ракети|крилаті ракети)[^.\n]{0,60}?(?:збито|знищено|знешкоджено)", re.I)
RE_ALL_DESTROYED = re.compile(RE_ALL_DESTROYED.pattern.replace("{0,60}", "{0,120}"), re.I)
RE_NOT_COUNTED = re.compile(r"імітатор|не досягли|локаційно", re.I)


def parse_destroyed(text: str, destroyed_block: str, header: str, launched_entries: list[dict]) -> dict:
    out = {"destroyed_total": None, "destroyed_method": None, "shot_down": None, "ew_lost": None, "destroyed_by_type": []}
    block = destroyed_block or ""
    entries = clause_entries(block) if block else []
    out["destroyed_by_type"] = entries
    # the "збито N ... та M ракети" sentence: sum top-level non-subset entries in that sentence
    # 1) the headline is the Air Force's own total: "ЗБИТО 45 КРИЛАТИХ РАКЕТ, ЗНЕШКОДЖЕНО 266 ВОРОЖИХ БПЛА"
    hdr = RE_DESTROYED_HDR.search(header)
    if hdr:
        hsent = header[hdr.start():]
        if hdr.group(1) is None:  # "ЗБИТО КРИЛАТУ РАКЕТУ ТА 79 ..." -> implicit 1
            hsent = re.sub(r"^(\S+\s+)", r"\g<1>1 ", hsent, count=1)
        hents = [e for e in clause_entries(hsent) if not e["subset"] and not RE_NOT_COUNTED.search(e["type_raw"])]
        anyc = [e for e in hents if e["weapon_class"] == "any"]
        if anyc:
            out["destroyed_total"], out["destroyed_method"] = anyc[0]["count"], "header_total"
        elif hents:
            out["destroyed_total"], out["destroyed_method"] = sum(e["count"] for e in hents), "header_sum" if len(hents) > 1 else "header"
    m, n0, sent = None, None, ""
    for src in ((block, text, header) if out["destroyed_total"] is None else ()):
        for cand in RE_DESTROYED_SENT.finditer(src):
            if cand.group(1) is not None and num_at(cand.group(1)) is not None:
                m, n0, sent = cand, num_at(cand.group(1)), cand.group(0)
                break
            if cand.group(1) is None and RE_SINGULAR.search(cand.group(2)):
                m, n0, sent = cand, 1, re.sub(r"^(\S+\s+)", r"\g<1>1 ", cand.group(0), count=1)
                break
        if m:
            break
    if m:
        sent_entries = clause_entries(sent)
        top = [e for e in sent_entries if not e["subset"] and not RE_NOT_COUNTED.search(e["type_raw"])]
        if n0 is not None:
            if top and top[0]["count"] == n0 and len(top) > 1 and all(e["weapon_class"] != "any" for e in top):
                out["destroyed_total"] = sum(e["count"] for e in top)
                out["destroyed_method"] = "sum_sentence"
            else:
                out["destroyed_total"] = n0
                out["destroyed_method"] = "sentence"
    if out["destroyed_total"] is None and (m := RE_ALL_DESTROYED.search(text)):
        what = m.group(1).lower()
        if re.search(r"ціл", what):
            cls = None
        elif re.search(r"ракет", what):
            cls = {"kinzhal", "ballistic", "cruise", "kab", "missile_other"}
        else:
            cls = {"shahed", "jet_uav", "recon_uav"}
        sel = [e for e in launched_entries if not e["subset"] and e["weapon_class"] != "any" and (cls is None or e["weapon_class"] in cls)]
        if sel:
            out["destroyed_total"], out["destroyed_method"] = sum(e["count"] for e in sel), "all_destroyed"
    if m := RE_SHOT_FIRE.search(text):
        out["shot_down"] = int(m.group(1))
    for rx in (RE_EW_LOST2, RE_EW_LOST, RE_EW_LOST3):
        if m := rx.search(text):
            out["ew_lost"] = int(m.group(1))
            break
    return out


# ---------------------------------------------------------------- directions, locations, oblasts
RE_DIRECTIONS = re.compile(r"(?:із|з|зі) напрямк(?:ів|у)?:?\s*([^.;\n]+?)(?=[.;\n]|,?\s*(?:понад|близько|до)\s+\d+\s+(?:із|з) них|$)", re.I)
RE_COMPASS = re.compile(r"(?:із|з|зі)\s+((?:північн|південн|східн|західн)[\w-]*(?:\s*(?:,|та|і|й)\s*(?:північн|південн|східн|західн)[\w-]*)*)\s+напрям", re.I)
RE_HIT = re.compile(r"влучанн\w*[^.\n]{0,120}?(?:на|у|в)\s+(" + NUM_RE + r")\s+локаці", re.I)
RE_DEBRIS = re.compile(r"падінн\w*[^.\n]{0,60}?(?:на|у|в)\s+(" + NUM_RE + r")\s+локаці", re.I)
RE_MAIN_TARGET = re.compile(r"[Оо]сновн\w+ напрям\w+ (?:повітряного |ракетного |комбінованого )?удару\s*[—–-]\s*([^.\n!]+)")
RE_AFFECTED = re.compile(r"(?:постраждал[аи]|зазнал[аи] (?:удару|атаки))\s+([^.\n!]+)")
OBL_PAT = {code: re.compile("|".join(v["patterns"]), re.I) for code, v in TAX["oblasts"].items()}


def oblast_codes(s: str) -> list[str]:
    codes = []
    for code, rx in OBL_PAT.items():
        if rx.search(s):
            codes.append(code)
    # 'Київщина' matches UA-32 only; 'столиця' UA-30; keep both when both present
    return sorted(codes)


def clean_direction(s: str) -> list[str]:
    s = re.sub(r"\s*[—–-]\s*(?:рф\.?|росія|ТОТ[^,;]*|Крим\.?|АР Крим\.?|тимчасово окупован[^,;]*)", "", s, flags=re.I)
    s = re.sub(r"\((?:[^)]*)\)", "", s)
    parts = [p.strip(" .;:–—-") for p in re.split(r",|/| та | і ", s)]
    return [p for p in parts if p and not re.search(r"^(рф|росія|тот)\b", p, re.I)]


def parse_misc(text: str) -> dict:
    out = {"launch_directions": [], "hit_locations_n": None, "debris_locations_n": None,
           "main_target_oblasts_raw": None, "main_target_oblasts": []}
    dirs = []
    for m in RE_DIRECTIONS.finditer(text):
        dirs += clean_direction(m.group(1))
    for m in RE_COMPASS.finditer(text):
        dirs += [p.strip() for p in re.split(r",|та|і\b|й\b", m.group(1)) if p.strip()]
    seen = set()
    out["launch_directions"] = [d for d in dirs if not (d in seen or seen.add(d))]
    if m := RE_HIT.search(text):
        out["hit_locations_n"] = num_at(m.group(1))
    if m := RE_DEBRIS.search(text):
        out["debris_locations_n"] = num_at(m.group(1))
    m = RE_MAIN_TARGET.search(text) or RE_AFFECTED.search(text)
    if m:
        out["main_target_oblasts_raw"] = m.group(1).strip()[:200]
        out["main_target_oblasts"] = oblast_codes(m.group(1))
    return out


# ---------------------------------------------------------------- driver
def parse_post(text: str, post_date: dt.date) -> dict:
    text = text.replace(" ", " ").replace(" ", " ")
    row = parse_period(text, post_date)
    if row["period_kind"] in ("month", "week"):
        row.update({"total_launched": None, "total_launched_method": None, "by_type": [], "destroyed_total": None,
                    "destroyed_method": None, "shot_down": None, "ew_lost": None, "destroyed_by_type": [],
                    "launch_directions": [], "hit_locations_n": None, "debris_locations_n": None,
                    "main_target_oblasts_raw": None, "main_target_oblasts": [], "parse_status": "not_night_period"})
        return row
    header, body = split_header(text)
    attack_block, destroyed_block = split_blocks(body)
    total, method, by_type = parse_launched(body, attack_block)
    row.update({"total_launched": total, "total_launched_method": method, "by_type": by_type})
    row.update(parse_destroyed(body, destroyed_block, header, by_type))
    row.update(parse_misc(body))
    if row["period_kind"] == "night" and row["night_date"] and total is not None and row["destroyed_total"] is not None:
        st = "ok"
    elif row["period_kind"] == "night" and row["night_date"]:
        st = "partial_night"
    elif row["period_kind"] == "day":
        st = "day_period"
    else:
        st = "unparsed"
    row["parse_status"] = st
    return row


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t = pd.read_parquet(IN_PATH)
    k = t[(t.channel == "kpszsu") & (t.post_type == "daily_summary")].sort_values("ts_utc").reset_index(drop=True)
    log(f"kpszsu daily_summary posts: {len(k)}")
    rows = []
    for r in k.itertuples(index=False):
        post_date = pd.Timestamp(r.ts_kyiv).date()
        p = parse_post(r.text, post_date)
        rows.append({
            "channel": r.channel, "msg_id": int(r.msg_id), "ts_utc": r.ts_utc, "ts_kyiv": r.ts_kyiv,
            "post_date_kyiv": post_date, "n_chars": int(r.n_chars), "type_method": r.type_method,
            **{kk: (json.dumps(v, ensure_ascii=False) if kk in ("by_type", "destroyed_by_type") else v) for kk, v in p.items()},
            "parser_version": PARSER_VERSION,
        })
    df = pd.DataFrame(rows)
    df["night_date"] = pd.to_datetime(df["night_date"]).dt.date
    df["n_uav_launched"] = df["by_type"].map(lambda s: sum(e["count"] for e in json.loads(s)
                                                          if not e["subset"] and e["weapon_class"] in ("shahed", "jet_uav", "recon_uav")) or None)
    df["n_missile_launched"] = df["by_type"].map(lambda s: sum(e["count"] for e in json.loads(s)
                                                              if not e["subset"] and e["weapon_class"] in ("kinzhal", "ballistic", "cruise", "kab", "missile_other")) or None)
    df.to_parquet(OUT_PATH, index=False)
    counts = {
        "input_posts": int(len(k)),
        "rows": int(len(df)),
        "parse_status": df["parse_status"].value_counts().to_dict(),
        "period_kind": df["period_kind"].value_counts(dropna=False).to_dict(),
        "night_date_method": df["night_date_method"].value_counts(dropna=False).to_dict(),
        "total_launched_method": df["total_launched_method"].value_counts(dropna=False).to_dict(),
        "destroyed_method": df["destroyed_method"].value_counts(dropna=False).to_dict(),
        "nonnull": {c: int(df[c].notna().sum()) for c in ["night_date", "total_launched", "destroyed_total", "shot_down", "ew_lost", "hit_locations_n", "debris_locations_n"]},
        "has_directions": int(df["launch_directions"].map(len).gt(0).sum()),
        "has_main_target": int(df["main_target_oblasts"].map(len).gt(0).sum()),
        "by_year_status": df.groupby(df["ts_kyiv"].dt.year)["parse_status"].value_counts().unstack(fill_value=0).to_dict(),
    }
    write_meta(OUT_PATH, inputs={"posts_typed": IN_PATH, "taxonomy": TAXONOMY}, counts=counts,
               extra={"parser_version": PARSER_VERSION, "taxonomy_version": TAX["version"]})
    qa = df[df.parse_status.isin(["partial_night", "unparsed"])][["msg_id", "ts_kyiv", "parse_status", "period_kind", "total_launched", "destroyed_total"]]
    qa = qa.merge(k[["msg_id", "text"]], on="msg_id")  # k is kpszsu-only, msg_id unique within channel
    qa["first_line"] = qa.text.str.split("\n").str[0].str[:120]
    qa.drop(columns="text").to_csv(OUT_DIR / "summaries_qa_unparsed.csv", index=False)
    log(json.dumps({kk: counts[kk] for kk in ("rows", "parse_status", "nonnull")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
