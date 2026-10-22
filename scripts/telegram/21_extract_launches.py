#!/usr/bin/env python
"""L3: posts_typed.parquet -> extract/launches.parquet + extract/launch_intel.parquet

Regex-first (taxonomy.yaml vocab). Rows the regexes cannot resolve keep nulls and a
parse_status in {ok, partial, unresolved}; those are the LLM fallback set (not called here).

launches     : kpszsu posts typed `launch` (🚀 / ☄ / 💣 / "Пуски ...").
               Fields: event_kind {launch, repeat_launch, threat}, weapon_class, weapon_raw,
               launch_site_raw, launch_direction_raw, target_oblast_raw, count, count_raw.
launch_intel : war_monitor + monitoringwar + kpszsu posts typed `launch_intel`, plus
               kpszsu/monitor posts typed alert/aviation_activity/launch whose text names a
               carrier platform (Tu-95/160/22M3, MiG-31K, ships, subs).
               Fields: platform, platforms_all, n_platforms, n_platforms_raw, salvo_max,
               location_raw, location_key, status, eta_minutes, eta_raw, obs_time_raw,
               weapon_hint.
"""
from __future__ import annotations
import sys, pathlib, datetime as dt
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import regex as re
import yaml
import pandas as pd
from _common import INTERIM, TAXONOMY, write_meta, log

F = re.IGNORECASE | re.UNICODE
OUT = INTERIM / "extract"
LET = "а-яіїєґa-z"          # letter class for manual word boundaries (\b fails after U+FE0F)

# ----------------------------------------------------------------------------- shared vocab
NUM_WORDS = {"один": 1, "одна": 1, "одного": 1, "два": 2, "дві": 2, "двох": 2, "пара": 2, "пари": 2,
             "три": 3, "трьох": 3, "чотири": 4, "чотирьох": 4, "п'ять": 5, "п’ять": 5, "п'яти": 5,
             "шість": 6, "шести": 6, "сім": 7, "семи": 7, "вісім": 8, "восьми": 8, "дев'ять": 9,
             "десять": 10, "десяти": 10, "дванадцять": 12}
VAGUE_N = re.compile(rf"(?<![{LET}])(декілька|кілька|низк[аи]|груп[аи]|кількість буде уточнюватись)(?![{LET}])", F)


def tax_classes(tax):
    return [(k, re.compile("|".join(v), F)) for k, v in tax["weapon_classes"].items()]


def weapon_class(text, classes):
    """First class in taxonomy order (= specificity order) whose pattern hits; (class, raw span)."""
    for k, rx in classes:
        m = rx.search(text)
        if m:
            return k, m.group(0)
    return None, None


def oblast_rx(tax):
    """One regex that captures the inflected oblast/city word (stem extended to word end)."""
    alts = []
    for code, o in tax["oblasts"].items():
        for p in o["patterns"]:
            p = p.replace(r"\b", "").lstrip("^").replace(r"\s*(м\.?\s*)?", "")
            alts.append(p)
    body = "|".join(f"(?:{a})" for a in alts)
    return re.compile(rf"(?<![{LET}])(?:{body})[{LET}'’ʼ\-]*", F)


def site_rx(tax):
    rows = []
    for key, s in tax["launch_sites"].items():
        for p in s["patterns"]:
            p = p.replace(r"\b", rf"(?![{LET}])")
            rows.append((key, re.compile(rf"(?<![{LET}])(?:{p})[{LET}'’ʼ\-]*", F)))
    return rows


# ----------------------------------------------------------------------------- launches
LAUNCH_LINE = re.compile(r"🚀|☄|💣|пуск|запуск|КАБ|баліст|авіабомб|керован(их|і) авіаційн|ракет", F)
# settlement target: "КАБи на Дніпро", "КАБ повз Вільнянськ", "в напрямку Миколаєва"
SETTLEMENT = re.compile(rf"(?<![{LET}])(?:на|повз|курсом на|у напрямку|в напрямку|в бік|у бік)\s+(?:н\.п\.\s*|м\.\s*|с\.\s*|смт\s*)?((?-i:[А-ЯІЇЄҐ])[{LET}'’ʼ\-]+(?:\s+(?-i:[А-ЯІЇЄҐ])[{LET}'’ʼ\-]+)?)", F)
REPEAT = re.compile(rf"(?<![{LET}])(повторн|ще |черговий|нові пуски)", F)
THREAT = re.compile(rf"загроз[аиу]|ймовірн|можлив[аіе]|існує", F)
# origin: "з Криму", "з Брянської та Курської областей", "з аеродрому Шайковка", "з акваторії Чорного моря"
ORIGIN = re.compile(
    rf"(?<![{LET}])(?:з|зі|із)\s+(?!оголош|півд|півн|сход|заход|східн|західн|північн|південн)"
    rf"((?:аеродрому|акваторії|району|боку|напрямку|території|окупован(?:ого|ої)|тимчасово окупован(?:ого|ої))?\s*"
    rf"(?-i:[А-ЯІЇЄҐ])[{LET}'’ʼ\-\.«»\"]*(?:\s+(?:та|і|й|,)\s*(?-i:[А-ЯІЇЄҐ])[{LET}'’ʼ\-]*)*(?:\s+(?:област(?:ей|і)|моря|рф))?)", F | re.V0)
DIRECTION = re.compile(
    rf"(?<![{LET}])(?:з|зі|із)\s+((?:півд(?:ня|енн(?:ого|о-східного|о-західного|ий))(?:\s+(?:сходу|заходу))?|півн(?:очі|ічн(?:ого|о-східного|о-західного))(?:\s+(?:сходу|заходу))?|сход(?:у)|східн(?:ого)|заход(?:у)|західн(?:ого))"
    rf"(?:\s*(?:та|і|,)\s*(?:півд(?:ня|енн(?:ого|о-східного|о-західного))|півн(?:очі|ічн(?:ого|о-східного|о-західного))|сход(?:у)|східн(?:ого)|заход(?:у)|західн(?:ого)))*(?:\s+напрям(?:ку|ків))?)", F)
COUNT = re.compile(rf"(?<![\d.,:])(\d{{1,2}})(?:-?(?:х|ти|ох|ма|ьох|и))?\s*[хx×]?\s*(?=(?:КАБ|ракет|авіабомб|пуск|балістичн|крилат|Х-|Калібр|Іскандер|одиниц|шт))", F)
NAT = re.compile(r"по всій території України|вся Україна|всієї України|де оголошен[ао] (повітряна )?тривог", F)


def extract_launch(text, classes, obl_rx, sites):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    span_lines = [l for l in lines if LAUNCH_LINE.search(l)] or lines[:1]
    span = " ⏎ ".join(span_lines)
    # strip boilerplate so oblast/site regexes don't hit "сигнали повітряної тривоги" etc.
    core = re.sub(r"Не ігноруйте[^⏎]*|Будьте[^⏎]*|Слідкуйте[^⏎]*", "", span)
    wc, wraw = weapon_class(core, classes)
    if wc is None and re.search(r"☄|баліст", core, F):
        wc, wraw = "ballistic", "☄"
    if wc is None and re.search(rf"(?<![{LET}])(пуск|запуск)", core, F):
        wc, wraw = "unknown", "пуск"
    # the taxonomy puts kab after kinzhal; "Пуски ракет" alone -> unknown
    kind = "threat" if THREAT.search(core) and not re.search(rf"(?<![{LET}])пуск", core, F) else \
           ("repeat_launch" if REPEAT.search(core) else "launch")
    site_raw, site_key = None, None
    for key, rx in sites:
        m = rx.search(core)
        if m and (site_raw is None or m.start() < site_raw[1]):
            site_raw, site_key = (m.group(0), m.start()), key
    origin = ORIGIN.search(core)
    if origin:
        o = origin.group(1).strip(" .!,")
        # ORIGIN may grab the target ("на Сумщину" never starts with з, fine) or an oblast list
        if site_raw is None:
            site_raw = (o, origin.start())
    site_raw = site_raw[0] if site_raw else None
    direction = DIRECTION.search(core)
    dir_raw = direction.group(1) if direction else None
    # targets: oblast words NOT inside the origin clause
    tgt_text = core
    if origin:
        tgt_text = core[:origin.start()] + " " + core[origin.end():]
    tgts = []
    for m in obl_rx.finditer(tgt_text):
        w = m.group(0).rstrip("-'’ʼ")
        if w not in tgts:
            tgts.append(w)
    target = "; ".join(tgts) if tgts else ("<national>" if NAT.search(core) else None)
    settle = None
    for m in SETTLEMENT.finditer(tgt_text):
        w = m.group(1)
        if not obl_rx.match(w) and not re.match(r"(Увага|Пуск|КАБ|Загроз|Не |Півд|Півн|Схід|Захід|Межі|Територ)", w):
            settle = w; break
    cm = COUNT.search(core)
    count = int(cm.group(1)) if cm else None
    status = "ok" if wc and (target or settle or site_raw or dir_raw) else ("partial" if (wc or target or settle or site_raw) else "unresolved")
    return dict(event_kind=kind, weapon_class=wc, weapon_raw=wraw, launch_site_raw=site_raw, launch_site_key=site_key,
                launch_direction_raw=dir_raw, target_oblast_raw=target, target_settlement_raw=settle, count=count,
                count_raw=cm.group(0).strip() if cm else None, text_span=span[:300], parse_status=status)


# ----------------------------------------------------------------------------- launch intel
PLATFORMS = [
    ("Tu-160",   re.compile(r"Ту-?\s?160|Tu-?160", F)),
    ("Tu-95",    re.compile(r"Ту-?\s?95|Tu-?95", F)),
    ("Tu-22M3",  re.compile(r"Ту-?\s?22|Tu-?22", F)),
    ("MiG-31K",  re.compile(r"МіГ-?\s?31|Миг-?31|MiG-?31", F)),
    ("tactical", re.compile(rf"Су-?\s?(34|35|24|25|30|57|27)(?![\d])", F)),
    ("other_aircraft", re.compile(r"А-50|Іл-\s?(76|96|22|80)|ІЛ-\s?76|Ил-76|Ту-?\s?(214|134|154)|Ан-\s?\d+", F)),
    ("submarine", re.compile(r"підводн|субмарин|\bПЧ\b", F)),
    ("ship",     re.compile(rf"ракетонос|носі[їйв]в?\s+(?:ракет|крилат|КР|«?\"?Калібр)|(?<![{LET}])носі[їйв]в?(?![{LET}])(?![^\n]{{0,15}}(?:надзвук|гіперзвук|аеробал|Х-47|Кинджал))|фрегат|корвет|(?<![{LET}])МРК(?![{LET}])|корабл|катер|флоту?(?![{LET}])|\bБДК\b|портах базування|порти базування", F)),
    ("ground",   re.compile(rf"наземн(их|і|ими) пусков|пускових (установок|комплексів)|ОТРК|Іскандер|С-300|С-400|ППО рф|ворожої ППО|ППО (противника|ворога)", F)),
    ("strategic_aviation", re.compile(rf"стратегічн(а|ої|у|ою) авіаці|стратегічн(их|і) бомбардувальник|(?-i:ДА) (рф|ВКС)|бортів (?-i:ДА)(?![{LET}])", F)),
]
N_PLAT = re.compile(
    rf"(?<![\d.,:\-])(\d{{1,2}})(?:-?(?:х|ти|ох|ма|ьох|и))?\s*[хx×]?\s*"
    rf"(?=(?:борт|літак|одиниц|шт\b|носі|МіГ|Ту-|ТУ-|Су-|екіпаж|стратег|бомбард|ракетонос|підводн|кораб|МРК|фрегат|носи))", F)
N_PLAT_WORD = re.compile(
    rf"(?<![{LET}])({'|'.join(map(re.escape, NUM_WORDS))})\s+(?:борт|літак|одиниц|носі|МіГ|Ту-|Су-|бомбард|ракетонос|підводн|кораб|МРК|фрегат|стратег)", F)
SALVO = re.compile(r"боєзапас(?:ом)?\s*(?:до|—|-|:)?\s*(\d{1,3})", F)
OBS_TIME = re.compile(r"станом на\s*(\d{1,2}[:.]\d{2}(?:\s*\d{2}\.\d{2}\.\d{2,4})?|зараз)", F)
# ETA: "входження ... о 04:00", "розрахунково о 04:00-04:30", "очікуємо на вихід приблизно о 5-6 ранку", "через 30 хв", "~1.5 год"
ETA_CLOCK = re.compile(
    rf"(входження|вихід|вихода|виходу|пуск[иі]?|рубеж|розрахунков|очіку|орієнтовно|підл[іь]т|досягн|прибутт|над Україною)[^\n⏎]{{0,80}}?(?<![{LET}\d])(?:(?:о|об|на|з|близько|~)\s*)?~?\s*(\d{{1,2}})(?:(?:[:.](\d{{2}})(?![.\d]))|(?=\s*(?:[-–]\s*\d{{1,2}}\s*)?(?:ранку|ночі|вечора|дня)))(?:\s*[-–]\s*\d{{1,2}}(?:[:.]\d{{2}})?)?(?:\s*(ранку|ночі|вечора|дня))?", F)
ETA_REL = re.compile(
    rf"(через|за|протягом|орієнтовно|приблизно|~)\s*(?:наступн(?:их|і)\s*)?(\d{{1,2}}(?:[.,]\d)?)(?:\s*[-–]\s*\d{{1,2}})?\s*(хв|год|годин|години)", F)

SECTION_SPLIT = re.compile(r"(?:^|\n|⏎|\s)[—–\-]\s*(?=Стратегічна|Авіація|БпЛА|Флот|Балістика)", F)

STATUS_RULES = [
    ("landed",  re.compile(rf"посадк|залишають|лишають|покидають|здійснили посадку|(?<![{LET}])сі(ли|в)(?![{LET}])|приземлил|повернул(ис|ася)|залишають пускові|лишають пускові|зворотн(ім|ьому|ьо|ьому) (курс|напрям)|у зворотньому|відбій|відбой|без (ракетних )?пусків|покинули пускові", F)),
    ("launch_likely_strong", re.compile(rf"(імовірн[іоа]?|ймовірн[іоа]?|можлив[іеа]?|якщо|вероятн[а-яё]*|возможн[а-яё]*|загроз[аиу])\s+(пуск|запуск|вильот|вил[іе]т|зльот|зл[іь]т)|пусковий маневр|команда на пуск", F)),
    ("launch_confirmed", re.compile(rf"(зафіксован[оі]|відмічен[оі]|здійсн(ено|или|ив)|виконан[оі]|відбул(ися|ись|ася))\s+(?:\d+[хx]?\s*)?(пуск|запуск)(?![^\n⏎]{{0,25}}(БпЛА|дрон|шахед|Шахед|не підтверд))|(?<![{LET}])(за)?пуск(и|ів)?\s+(КР|ракет|крилат|Х-|Калібр|Кинджал)(?![^\n⏎]{{0,20}}(буде|будуть|очіку|не фіксу|не було|відсутн|не підтверд|не виключ))|випущен|відпрацював|(?<![{LET}])запустил|група КР|КР (курсом|у напрямку|на|через)", F)),
    ("false_alarm", re.compile(rf"тренуван|тренувальн|навчальн|планов(ий|е|і) (політ|виліт)|хибн|не підтверд|передислокац|перебазув|урядов(і|ий|ого) борт|спостережний політ", F)),
    ("inactive", re.compile(rf"заведен[оі] (в|у|до) (пункт|порт)|(?<![{LET}])не активн|неактивн", F)),
    ("takeoff", re.compile(rf"(?<![{LET}])зл[іь]т(?!н)|зльот|злетіл|вил[іе]т(?!ають)|вильот|взл[её]т|піднял(ис|ася)|підняття|(?<!не )активність .{{0,30}}(борт|Ту-|МіГ|Су-)|відмічається активність", F)),
    ("launch_likely", re.compile(rf"пускових рубеж|пускові рубежі|на рубеж|загроз[аиу] (запуску|пуску|пусків|застосування|ракет)|ймовірн(і|ість|ий|о) (пуск|застосув|вих)|будуть виконувати пуски|очікуємо (на )?(вихід|пуск)|можлив(і|ий|е|а) (пуск|застосув|вих|запуск)|ракетн(а|у|ої) небезпек|підвищена загроза|імовірн", F)),
    ("airborne", re.compile(rf"вход(ять|ить) (у|в|до)|увійшл[иа]|заход(ять|ить) (у|в)|у (Чорному|Азовському|Каспійському|Середземному) морі|виведен[оі](?![{LET}])|вийшл[иа] (в|у) море|залп|над ПП|у повітрі|в повітрі|маневру|рухаються|рухається|прямують|прямує|курс(ом)?(?![{LET}])|у напрямку|в напрямку|в акваторії|над акваторі|здійснюють політ|входження|перебува(є|ють) (в|у|над)|(?<!не )активність|(?<!не )активна(?![{LET}])|в морі|у морі|вийшл[аи] в море|виведен[оі] в море|на бойов(е|ому) чергуван", F)),
    ("active", re.compile(rf"робот[ау] (ворожої |ворожих )?(ЗРК )?(С-300|С-400|ППО)|комунікаці[їй] пунктів управління|активність пунктів управління|відмічено роботу", F)),
    ("inactive", re.compile(rf"не активна|неактивна|без вильотів|без змін|у портах|в портах|порти базування|пунктах базування|на аеродром(ах|і) базування|присутність \d+[хx]? ?бортів|зберігається присутність|відсутн|не фіксу|спокійн|на ае перебува|перебува(є|ють) на (ае|аеродром)|перебуває \d+", F)),
]


def extract_intel(text, ts_kyiv, classes, sites):
    core = re.sub(r"@\w+|#\w+|https?://\S+", "", text)
    core_short = core[:700]
    found = []
    for name, rx in PLATFORMS:
        m = rx.search(core_short)
        if m:
            found.append((m.start(), name))
    found.sort()
    plats = [n for _, n in found]
    # drop the generic label when a concrete type is named
    if "strategic_aviation" in plats and any(p in plats for p in ("Tu-95", "Tu-160", "Tu-22M3")):
        plats.remove("strategic_aviation")
    platform = plats[0] if plats else None
    n_raw, n = None, None
    m = N_PLAT.search(core_short)
    if m:
        n_raw, n = m.group(0).strip(), int(m.group(1))
    else:
        mw = N_PLAT_WORD.search(core_short)
        if mw:
            n_raw, n = mw.group(0).strip(), NUM_WORDS[mw.group(1).lower()]
        else:
            mv = VAGUE_N.search(core_short)
            if mv:
                n_raw = mv.group(0)
    if n is None:
        mo = re.search(rf"(?<![\d.,:\-])(\d{{1,2}})-го\s+(?:борт|Ту-|МіГ|Су-)", core_short, F)
        if mo:
            n_raw, n = mo.group(0).strip(), int(mo.group(1))
    sm = SALVO.search(core_short)
    salvo = int(sm.group(1)) if sm else None
    loc_raw, loc_key, loc_pos = None, None, None
    for key, rx in sites:
        mm = rx.search(core_short)
        if mm and (loc_pos is None or mm.start() < loc_pos):
            loc_raw, loc_key, loc_pos = mm.group(0), key, mm.start()
    if loc_raw is None:
        # un-gazetteered airfields: ае «Українка», аеродрому "Бєлая", з аеродрому Хотілово
        mm = re.search(rf"(?<![{LET}])(?:в/)?ае(?:родром(?:у|і|ах)?)?\s+[«\"“]?\s*((?-i:[А-ЯІЇЄҐ])[{LET}\-\d]*(?:-\d)?)", core_short, F)
        if mm:
            loc_raw = mm.group(0).strip()
        elif (mm := re.search(rf"(?<![{LET}])(?:з|із|зі)\s+(?:району|акваторії|боку)\s+((?-i:[А-ЯІЇЄҐ])[{LET}'’ʼ\-]+(?:\s+(?:моря|області|обл\.))?)", core_short, F)):
            loc_raw = mm.group(1)
        elif re.search(r"європейськ(ій|ої) частин", core_short, F):
            loc_raw = "європейська частина рф"
        elif re.search(r"над ПП\s*(рф|РФ)|ПП рф", core_short, F):
            loc_raw = "ПП рф"
    ot = OBS_TIME.search(core_short)
    obs_raw = ot.group(1) if ot else None
    scrub = OBS_TIME.sub(" ", core_short)

    def _status(txt):
        for name, rx in STATUS_RULES:
            if rx.search(txt):
                return name
        return None

    status = None
    secs = SECTION_SPLIT.split(scrub)
    if len(secs) >= 3:   # 📡 Обстановка-style report: per-section status, pick the first active section
        strat = next((x for x in secs if re.match(r"\s*(Стратегічна авіація|Авіація)", x, F)), None)
        fleet = next((x for x in secs if re.match(r"\s*Флот", x, F)), None)
        st_s = ("inactive" if re.search(r"не активн|неактивн", strat, F) else _status(strat)) if strat else None
        st_f = _status(fleet) if fleet else None
        if strat and st_s not in (None, "inactive"):
            status = st_s
            platform = next((n for n in plats if n != "ship"), platform)
        elif fleet and st_f not in (None, "inactive"):
            status, platform = st_f, "ship"
            mf = N_PLAT.search(fleet)
            if mf:
                n_raw, n = mf.group(0).strip(), int(mf.group(1))
        else:
            status = "inactive" if (st_s == "inactive" or st_f == "inactive") else _status(scrub)
            if platform == "ship" and "strategic_aviation" in plats:
                platform = "strategic_aviation"
    else:
        status = _status(scrub)
    # ETA
    eta_min, eta_raw = None, None
    mc = None
    if platform:
        hits = list(ETA_CLOCK.finditer(scrub))
        mc = next((h for h in hits if h.group(1).lower().startswith(("вход", "над укр", "підл"))), hits[0] if hits else None)
    mr = ETA_REL.search(scrub) if platform else None
    if mr and (not mc or mr.start() < mc.start()):
        v = float(mr.group(2).replace(",", "."))
        eta_min = int(round(v * (60 if mr.group(3).startswith("год") else 1)))
        eta_raw = mr.group(0).strip()
    elif mc:
        hh, mi = int(mc.group(2)), int(mc.group(3) or 0)
        if 0 <= hh <= 23 and ts_kyiv is not None and pd.notna(ts_kyiv):
            tgt = ts_kyiv.replace(hour=hh, minute=mi, second=0, microsecond=0)
            if tgt < ts_kyiv:
                tgt += dt.timedelta(days=1)
            d = int((tgt - ts_kyiv).total_seconds() // 60)
            if 0 <= d <= 12 * 60:   # beyond 12h it is not an ETA
                eta_min, eta_raw = d, mc.group(0).strip()[-40:]
    wh, _ = weapon_class(core_short, classes)
    if wh == "shahed" and platform not in (None, "ground"):
        wh = None  # "ударних БпЛА" mentioned alongside carriers: not the carrier's weapon
    if status == "launch_likely_strong":
        status = "launch_likely"
    pstat = "ok" if (platform and status) else ("partial" if (platform or status) else "unresolved")
    return dict(platform=platform, platforms_all="; ".join(plats) if plats else None, n_platforms=n,
                n_platforms_raw=n_raw, salvo_max=salvo, location_raw=loc_raw, location_key=loc_key,
                status=status, eta_minutes=eta_min, eta_raw=eta_raw, obs_time_raw=obs_raw,
                weapon_hint=wh, text_span=core_short[:300], parse_status=pstat)


# ----------------------------------------------------------------------------- main
PLATFORM_ANY = re.compile(r"Ту-?\s?(95|160|22)|МіГ-?\s?31|Миг-31|ракетонос|носі[їйв]в?\s+(ракет|крилат|Калібр)|підводн|фрегат|МРК\b|стратегічн(а|ої) авіаці", F)
BASE_COLS = ["channel", "msg_id", "ts_utc", "ts_kyiv", "post_type", "type_rule"]


def main() -> None:
    tax = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    classes, obl, sites = tax_classes(tax), oblast_rx(tax), site_rx(tax)
    src = INTERIM / "posts_typed.parquet"
    df = pd.read_parquet(src)
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- launches
    L = df[(df.channel == "kpszsu") & (df.post_type == "launch")].copy()
    log(f"launches: {len(L)} kpszsu launch posts")
    rows = [extract_launch(t, classes, obl, sites) for t in L["text_norm"]]
    out = pd.concat([L[BASE_COLS].reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    out["parse_method"] = "regex"
    dst = OUT / "launches.parquet"
    out.to_parquet(dst, index=False)
    c = {"rows": int(len(out)), "parse_status": out.parse_status.value_counts().to_dict(),
         "event_kind": out.event_kind.value_counts().to_dict(),
         "weapon_class": out.weapon_class.fillna("<null>").value_counts().to_dict(),
         "has_target": int(out.target_oblast_raw.notna().sum()), "has_site": int(out.launch_site_raw.notna().sum()),
         "has_direction": int(out.launch_direction_raw.notna().sum()), "has_count": int(out["count"].notna().sum())}
    write_meta(dst, inputs={"posts_typed": src, "taxonomy": TAXONOMY}, counts=c,
               extra={"taxonomy_version": tax["version"], "selection": "channel==kpszsu & post_type==launch"})
    log(f"launches parse_status {c['parse_status']}")

    # ---- launch intel
    chans = ["kpszsu", "war_monitor", "monitoringwar"]
    base = df.channel.isin(chans)
    primary = base & (df.post_type == "launch_intel")
    supp = base & df.post_type.isin(["alert", "aviation_activity", "launch"]) & df.text_norm.map(lambda t: bool(PLATFORM_ANY.search(t)))
    I = df[primary | supp].copy()
    I["selection"] = ["typed" if p == "launch_intel" else "platform_mention" for p in I.post_type]
    log(f"launch_intel: {int(primary.sum())} typed + {int((supp & ~primary).sum())} platform-mention posts")
    rows = [extract_intel(t, ts, classes, sites) for t, ts in zip(I["text_norm"], I["ts_kyiv"])]
    out = pd.concat([I[BASE_COLS + ["selection"]].reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    out["parse_method"] = "regex"
    dst = OUT / "launch_intel.parquet"
    out.to_parquet(dst, index=False)
    c = {"rows": int(len(out)), "by_channel": out.channel.value_counts().to_dict(),
         "by_selection": out.selection.value_counts().to_dict(),
         "parse_status": out.parse_status.value_counts().to_dict(),
         "platform": out.platform.fillna("<null>").value_counts().to_dict(),
         "status": out.status.fillna("<null>").value_counts().to_dict(),
         "has_n": int(out.n_platforms.notna().sum()), "has_location": int(out.location_raw.notna().sum()),
         "has_eta": int(out.eta_minutes.notna().sum())}
    write_meta(dst, inputs={"posts_typed": src, "taxonomy": TAXONOMY}, counts=c,
               extra={"taxonomy_version": tax["version"],
                      "selection": "post_type==launch_intel in AF+monitor, plus alert/aviation_activity/launch posts naming a carrier platform",
                      "status_enum_note": "spec enum + inactive (no activity / in port) + active (RU AD working, C2 comms) + null (unresolved); airborne also covers ships deployed at sea"})
    log(f"launch_intel parse_status {c['parse_status']}")


if __name__ == "__main__":
    main()
