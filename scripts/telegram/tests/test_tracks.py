"""Unit tests for 20_extract_tracks.py (30 fixture strings; run: .venv/bin/python -I -m pytest or python -I this file)."""
import importlib.util, pathlib, sys
import yaml

HERE = pathlib.Path(__file__).resolve().parent
TG = HERE.parent
sys.path.insert(0, str(TG))
_spec = importlib.util.spec_from_file_location("extract_tracks", TG / "20_extract_tracks.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)
CFG = M.Cfg(yaml.safe_load((TG / "taxonomy.yaml").read_text(encoding="utf-8")))

# (text, expected fields of row [idx]) ; only listed fields are asserted
CASES = [
    ("🛵 Полтавщина: БпЛА курсом на Шишаки.", 0, dict(weapon_class="shahed", oblast_raw="Полтавщина", oblast_iso="UA-53", settlement_raw="Шишаки", settlement_role="target", heading_raw="курсом на Шишаки")),
    ("🛵 Група ударних БпЛА на Чернігівщині повз Гончарівське курсом на Київщину.", 0, dict(oblast_raw="Чернігівщині", settlement_raw="Гончарівське", settlement_role="location", heading_raw="курсом на Київщину")),
    ("Швидкісна ціль на Миколаївщині.", 0, dict(weapon_class="ballistic", oblast_raw="Миколаївщині", oblast_iso="UA-48", settlement_raw=None)),
    ("🛵 Жмеринка.", 0, dict(weapon_class="shahed", settlement_raw="Жмеринка", settlement_role="bare", oblast_raw=None, oblast_iso="UA-05")),
    ("⚠Увага!\n🛵Запоріжжя - в районі міста ворожі БпЛА.\nПеребувайте в укриттях!", 0, dict(settlement_raw="Запоріжжя", oblast_iso="UA-23")),
    ("🏍 Одещина: реактивний БпЛА курсом на Маяки/Біляївку з півдня.", 0, dict(weapon_class="jet_uav", oblast_raw="Одещина", settlement_raw="Маяки", settlements_all="Маяки|Біляївку")),
    ("2 групи КР повз Гайсин, Вінниччина, західним курсом", 0, dict(weapon_class="cruise", count=2, count_unit="groups", settlement_raw="Гайсин", oblast_raw="Вінниччина", heading_raw="західним курсом")),
    ("Сумщина:\n13х БпЛА від Білопілля повз Буринь на Конотоп/район.\nКурс Західний.", 0, dict(count=13, oblast_raw="Сумщина", oblast_role="context", settlement_raw="Буринь", heading_raw="Курс Західний")),
    ("Київ:\n🅿️1х Нивки", 0, dict(weapon_class="jet_uav", count=1, settlement_raw="Нивки", oblast_iso="UA-30")),
    ("Київщина:\n🅿️1х Чабани / Хотів у напрямку Васильків.\nВисота 2,6км", 0, dict(settlement_raw="Чабани", oblast_iso="UA-32", heading_raw="у напрямку Васильків")),
    ("⚠️ 27х БпЛА через Чернігівщину у напрямку Київщини.\n⚠️ 14х БпЛА через Сумщину у напрямку Чернігівської та Полтавської областей.", 1, dict(count=14, oblast_raw="Сумщину", oblast_iso="UA-59", settlement_raw=None)),
    ("⚠️ 4х БпЛА повз Павлоград, Дніпропетровської області.", 0, dict(count=4, settlement_raw="Павлоград", oblast_raw="Дніпропетровської області", oblast_iso="UA-12")),
    ("❗️ Одеса — 2х БпЛА на місто.", 0, dict(count=2, settlement_raw="Одеса", oblast_iso="UA-51")),
    ("❗️ Дніпро / Самар — 5х БпЛА у напрямку міст.", 0, dict(count=5, settlement_raw="Дніпро", settlements_all="Дніпро|Самар")),
    ("⚠️ Бровари — 1х БпЛА повз місто на Дніпровський район Києва.", 0, dict(settlement_raw="Бровари", raion_raw="Дніпровський район")),
    ("Рух ударних БпЛА:\n🛵 БпЛА на півночі Київщини рухаються у західному напрямку.\n🛵БпЛА на Чернігівщині, курс - південно-західний.", 1, dict(oblast_raw="Чернігівщині", heading_raw="курс - південно-західний")),
    ("🛵 БпЛА в Шосткинському районі Сумщини, курс західний.", 0, dict(oblast_raw="Сумщини", raion_raw="Шосткинському районі", settlement_raw=None)),
    ("🏍 Реактивний БпЛА на Миколаївщині, повз н.п.Снігурівка курс північно-західний", 0, dict(weapon_class="jet_uav", settlement_raw="Снігурівка", settlement_role="location")),
    ("🛵 Ворожі БпЛА на Чернігівщині (н.п. Борзна)", 0, dict(settlement_raw="Борзна", oblast_raw="Чернігівщині")),
    ("🛵 БпЛА змінили курс на Дніпро", 0, dict(settlement_raw="Дніпро", settlement_role="target", oblast_iso="UA-12")),
    ("❗️ 1 група КР Калібр повз Новий Буг у напрямку Кропивницького району Кіровоградської області.", 0, dict(weapon_class="cruise", settlement_raw="Новий Буг", raion_raw="Кропивницького району", oblast_iso="UA-35")),
    ("❗️ 1х крилата ракета у напрямку Козин, Глеваха, Васильків", 0, dict(weapon_class="cruise", settlement_raw="Козин", settlements_all="Козин|Глеваха|Васильків")),
    ("🛸На сході Сумщини - ворожий розвідувальний БпЛА!", 0, dict(weapon_class="recon_uav", oblast_raw="Сумщини")),
    ("🛵 Нові групи ворожих БпЛА заходять на Дніпропетровщину з ТОТ Запоріжжя, курс - північно-західний!", 0, dict(oblast_raw="Дніпропетровщину", oblast_role="target", settlement_raw="Запоріжжя", settlement_role="origin")),
    ("Декілька цілей на Дніпропетровщину.", 0, dict(weapon_class="unknown", count=None, count_unit="vague", oblast_iso="UA-12")),
    ("❗️ Павлоград під атакою БпЛА — 9х БпЛА на місто.", 0, dict(count=9, settlement_raw="Павлоград")),
    ("🚀 Ракета на Черкащині ➡️ курсом на Київщину!", 0, dict(weapon_class="unknown", oblast_raw="Черкащині", oblast_iso="UA-71")),
    ("⚠️ 9х одинарних БпЛА на Черкащині та Кіровоградщині через Уманський район у напрямку Вінниччини.", 0, dict(count=9, oblast_raw="Черкащині", raion_raw="Уманський район", heading_raw="у напрямку Вінниччини")),
    ("Ворожий БпЛА у напрямку Миргорода з півночі.", 0, dict(settlement_raw="Миргорода", settlement_role="target", oblast_iso="UA-53")),
    ("1х Нивки на Відрадний.", 0, dict(count=1, settlement_raw="Нивки", settlements_all="Нивки|Відрадний")),
]


def _run():
    assert len(CASES) == 30
    bad = []
    for text, idx, exp in CASES:
        rows = M.extract_post(CFG, text, text[:2])
        if idx >= len(rows):
            bad.append((text[:50], "missing row", idx)); continue
        for k, v in exp.items():
            if rows[idx][k] != v:
                bad.append((text[:50], k, rows[idx][k], v))
    return bad


def test_fixtures():
    bad = _run()
    assert not bad, "\n".join(map(str, bad))


def test_multi_row_counts():
    assert len(M.extract_post(CFG, CASES[10][0])) == 2
    assert len(M.extract_post(CFG, CASES[15][0])) == 2


if __name__ == "__main__":
    b = _run()
    print("FAIL" if b else "OK", len(CASES), "fixtures")
    for x in b:
        print(" ", x)
    sys.exit(1 if b else 0)
