#!/usr/bin/env python
"""L4 resolve: canonical weapon_class / oblast (ISO 3166-2:UA) + settlement and launch-site geocoding.

In place on data/interim/telegram/extract/{tracks,launches,launch_intel,impacts}.parquet (adds columns; the
columns this script adds are dropped and rebuilt on every run, so it is idempotent). impacts.parquet is
skipped with a note when 23_extract_impacts.py has not run.

Settlements: VIINA tessellation (data/raw/viina/gn_UA_tess.geojson, GeoNames P-features) first,
GeoNames UA (P-features absent from the tessellation) second. Oblast-constrained when an oblast is known.
Declensions: both gazetteer names and queries go through the same suffix stemmer
(Козелець / Козельці / Козелецького району -> 'козелц'). Tiers: exact > stem > vowel-fold.
Ambiguous or unmatched -> null (geo_method says why). Never guessed.
Launch sites: taxonomy.yaml gazetteer (hand coordinates) + oblast-only fallback; no coordinates for
places outside the gazetteer.
Added columns:
  all tables : weapon_class_canon, weapon_canon_src
  tracks     : oblast_iso_canon, oblast_canon_src, geo_* (settlement_raw, else raion_raw)
  launches   : target_oblast_iso, target_oblast_iso_all, geo_* (target_settlement_raw), site_* (launch_site_raw)
  launch_intel: loc_* (location_raw)
  impacts    : weapon_class_canon/weapon_canon_src (weapon_raw via taxonomy + the frontline classes below),
               oblast_iso_canon/oblast_canon_src (oblast_raw, else the channel's home oblast; VA_Kyiv -> UA-30),
               geo_* (settlement_raw, else raion_raw, constrained to the oblast; a Kyiv-city row with no
               settlement is geocoded to the city feature with geo_level 'city', geo_conf 0.3)
Impacts-only weapon classes (resolver-side, not in taxonomy.yaml, which is the launch/track contract):
  fpv (FPV drones), artillery (tube/MLRS/mortar/tank fire), missile (unspecified "ракета"). fpv is tested before
  the taxonomy's shahed pattern (FPV-дрон would otherwise match 'дрон'); artillery after it, so mixed strings
  ("безпілотники та артилерія") keep the drone class.
geo_*: geo_method, geo_conf, geo_level {settlement, raion, raion_seat, hromada_seat, city}, geo_name, geo_id, geo_n_cand,
       geo_oblast_iso, lat, lon, h3_r5
"""
from __future__ import annotations
import sys, pathlib, json, hashlib, zipfile, math, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import regex as re
import yaml
import pandas as pd
import h3
from _common import ROOT, INTERIM, TAXONOMY, sha256_file, log

EXTRACT = INTERIM / "extract"
VIINA = ROOT / "data" / "raw" / "viina" / "gn_UA_tess.geojson"
GEONAMES = ROOT / "data" / "raw" / "gazetteer" / "geonames_UA.zip"
RESOLVE_VERSION = "resolve-1"
POP_DOMINANCE = True   # accept one candidate when it has pop >= POPDOM_MIN and >=20x the population of every rival
POPDOM_MIN = 5000

ADM1_NAME_ISO = {"Cherkasy": "UA-71", "Chernihiv": "UA-74", "Chernivtsi": "UA-77", "Dnipropetrovs'k": "UA-12",
                 "Donets'k": "UA-14", "Ivano-Frankivs'k": "UA-26", "Kharkiv": "UA-63", "Kherson": "UA-65",
                 "Khmel'nyts'kyy": "UA-68", "Kirovohrad": "UA-35", "Crimea": "UA-43", "Kiev City": "UA-30",
                 "Kiev": "UA-32", "Luhans'k": "UA-09", "L'viv": "UA-46", "Mykolayiv": "UA-48", "Odessa": "UA-51",
                 "Poltava": "UA-53", "Rivne": "UA-56", "Sevastopol'": "UA-40", "Sumy": "UA-59",
                 "Ternopil'": "UA-61", "Transcarpathia": "UA-21", "Vinnytsya": "UA-05", "Volyn": "UA-07",
                 "Zaporizhzhya": "UA-23", "Zhytomyr": "UA-18"}
GN_ADMIN1_ISO = {1: "UA-71", 2: "UA-74", 3: "UA-77", 4: "UA-12", 5: "UA-14", 6: "UA-26", 7: "UA-63", 8: "UA-65",
                 9: "UA-68", 10: "UA-35", 11: "UA-43", 12: "UA-30", 13: "UA-32", 14: "UA-09", 15: "UA-46",
                 16: "UA-48", 17: "UA-51", 18: "UA-53", 19: "UA-56", 20: "UA-40", 21: "UA-59", 22: "UA-61",
                 23: "UA-05", 24: "UA-07", 25: "UA-21", 26: "UA-23", 27: "UA-18"}
KYIV_PAIR = {"UA-30", "UA-32"}

# --------------------------------------------------------------------------- name normalisation
_APOS = re.compile(r"[ʼ'’`´′ʹ‘]")
_CYR = re.compile(r"[а-яіїєґё]", re.I)
_PREFIX = re.compile(r"^(?:м\.|с\.|смт\.?|н\.\s?п\.|с-ще|місто|село|селище|селі|селищі|місті|місту|міста|селом)\s*", re.I)
_OBLAST_FORM = re.compile(r"(?:щин|чин|чч)\w*$|област|\bобл\b", re.I)
_RAION_WORD = re.compile(r"\b(?:район\w*|р-н\w*|райони)\b", re.I)
_HROMADA_WORD = re.compile(r"\b(?:громад\w*|ТГ|ОТГ|тергромад\w*)\b", re.I)   # "Покровська громада" -> seat of the hromada


def norm(s: str) -> str:
    s = _APOS.sub("", s.strip().lower().replace("ё", "е"))
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[-–—]", " ", s)
    s = re.sub(r"[^\p{L}\d ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_VOWELS = "аеєиіїоуюяй"
_CONS_SUFFIX = ("ів", "їв", "ев", "єв", "ов", "ом", "ем", "єм", "ам", "ям", "ах", "ях", "ою", "ею", "єю")


_ADJ_END = ("ого", "ому", "ими", "ий", "ій", "ою", "ої", "их", "им", "ім")


def stem_word(w: str) -> str:
    w = w.replace("ь", "")
    for suf in _ADJ_END:  # adjectival declension (Кривого Рогу -> крив рог)
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            break
    for _ in range(3):
        n0 = w
        t = w.rstrip(_VOWELS)
        if len(t) >= 3:
            w = t
        for suf in _CONS_SUFFIX:
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                w = w[: -len(suf)]
                break
        if w == n0:
            break
    if len(w) > 4 and w.endswith("ец"):
        w = w[:-2] + "ц"
    return w


def stem(s: str) -> str:
    return " ".join(stem_word(w) for w in norm(s).split())


def fold(k: str) -> str:
    return re.sub(r"[іїиоеє]", "о", k)


_ADJ = re.compile(r"^(.+?)(ск|цк)(?:ий|ого|ому|им|ім|ій|а|у|ою|ої|е|і|их|ими)?$")


def adj_base(word: str):
    """'козелецького' -> ['козелец', 'козелецк'] ; None when not an adjective in -ськ/-цьк."""
    w = word.replace("ь", "")
    m = _ADJ.match(w)
    if not m:
        return None
    base = m.group(1) + ("ц" if m.group(2) == "цк" else "")
    # Козелецького -> козелец / козелецк ; Покровська -> покров (Покров) then покровск (Покровське)
    return [base, base + "к"] if m.group(2) == "цк" else [base, base + "ск"]


def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(d))


def h3r5(lat, lon):
    return h3.latlng_to_cell(lat, lon, 5) if lat is not None and lon is not None else None


# --------------------------------------------------------------------------- gazetteer
# 2023-24 decommunisation renames absent from the GeoNames alternate names (normalised query -> old name).
RENAMED = {"звягель": "новоград волинський", "звягеля": "новоград волинський", "звягелі": "новоград волинський",
           "шептицький": "червоноград", "шептицького": "червоноград",
           "самар": "новомосковськ", "самарі": "новомосковськ", "самара": "новомосковськ",       # Novomoskovsk -> Samar (2024)
           "златопіль": "первомайський", "златополі": "первомайський", "златополя": "первомайський",  # Pervomaiskyi -> Zlatopil (2024)
           "кривийріг": "кривий ріг", "кривомуроз": "кривий ріг", "кривомурозі": "кривий ріг"}
# Resolver-side launch-site additions (spelling variants of taxonomy sites; a few more airfields/cities seen in the
# corpus). Coordinates approximate (city/airfield centroid, few km). Sites I am not sure of are left out, not guessed.
EXTRA_SITES = {
    "belgorod": {"patterns": ["Білгород"]},
    "voronezh": {"patterns": ["Вороніж"]},
    "savasleyka": {"patterns": ["Савалсейк", "Саваслейк"]},
    "primorsko_akhtarsk": {"patterns": ["Приморськ\\w*\\W*Ахтарськ"]},
    "olenya": {"patterns": ["Олен\\b", "Олен(?=\\W|$)"]},
    "black_sea": {"patterns": ["\\bЧМ\\b", "Чорн\\w+ мор"]},
    "engels": {"patterns": ["Енгельс"]},
    "ukrainka": {"name": "Ukrainka AB (Amur)", "lat": 51.17, "lon": 128.45, "kind": "airbase", "patterns": ["Українка"]},
    "machulishchi": {"name": "Machulishchi AB (Belarus)", "lat": 53.78, "lon": 27.57, "kind": "airbase", "patterns": ["Мачулищ"]},
    "dyagilevo": {"name": "Dyagilevo AB (Ryazan)", "lat": 54.64, "lon": 39.57, "kind": "airbase", "patterns": ["Дягіл", "Дягил"]},
    "akhtubinsk": {"name": "Akhtubinsk (Astrakhan)", "lat": 48.27, "lon": 46.18, "kind": "range", "patterns": ["Ахтубінськ", "Ахтубинск"]},
    "tambov": {"name": "Tambov", "lat": 52.73, "lon": 41.45, "kind": "city", "patterns": ["Тамбов"]},
}

# Home oblast of each regional channel (taxonomy.yaml channel_groups.regional); fallback when oblast_raw is empty
# or unparseable. VA_Kyiv is the Kyiv City Military Administration: city (UA-30), never the oblast.
CHANNEL_HOME_OBLAST = {"VA_Kyiv": "UA-30", "dnipropetrovskaODA": "UA-12", "kozytskyy_maksym_official": "UA-46",
                       "odeskaODA": "UA-51", "synegubov": "UA-63", "zoda_gov_ua": "UA-23"}
# Frontline weapon classes seen in regional impact posts (impacts.parquet only). Order relative to the taxonomy
# classes matters: fpv before shahed, artillery and missile after it.
EXTRA_WEAPON_BEFORE_SHAHED = [("fpv", r"FPV|фпв|fpv-?дрон|ФПВ")]
EXTRA_WEAPON_AFTER = [("artillery", r"артилер|артобстріл|артудар|РСЗВ|реактивн\w* систем|Град|Ураган|Смерч|Торнадо|міномет|танков|ствольн|обстріл з (артилерії|танк)"),
                      ("missile", r"ракет")]


class Gaz:
    def __init__(self, tax: dict):
        self.tax = tax
        self.feats: list[dict] = []
        self.ix = {t: collections.defaultdict(list) for t in ("exact", "stem", "fold")}
        self.raion: dict[str, list] = collections.defaultdict(list)  # adj-stem -> [(iso, lat, lon, name)]
        self._load_viina()
        self._load_geonames()
        # alias: Kyiv city oblique forms
        self.oblast_pats = []
        for k, v in tax["oblasts"].items():
            self.oblast_pats.append((k, re.compile("|".join(v["patterns"]), re.I)))
        self.kyiv_city = re.compile("|".join(tax["oblasts"]["UA-30"]["patterns"]), re.I)
        self.kyiv_obl = re.compile("|".join(tax["oblasts"]["UA-32"]["patterns"]), re.I)
        self.sites = {k: dict(v) for k, v in tax["launch_sites"].items()}
        for k, v in EXTRA_SITES.items():  # resolver-side additions; taxonomy.yaml (contract) left untouched
            if k in self.sites:
                self.sites[k]["patterns"] = list(self.sites[k]["patterns"]) + v.get("patterns", [])
            else:
                self.sites[k] = v
        self.site_pats = [(k, re.compile("|".join(v["patterns"]), re.I)) for k, v in self.sites.items()]
        self.weapon_pats = [(c, re.compile("|".join(tax["weapon_classes"][c]), re.I))
                            for c in ["kinzhal", "kab", "ballistic", "cruise", "jet_uav", "recon_uav", "shahed"]]
        self.weapon_classes = set(tax["weapon_classes"])
        tp = {c: p for c, p in self.weapon_pats}
        self.impact_weapon_pats = [(c, tp[c]) for c in ["kinzhal", "kab", "ballistic", "cruise", "jet_uav", "recon_uav"]] \
            + [(c, re.compile(p, re.I)) for c, p in EXTRA_WEAPON_BEFORE_SHAHED] + [("shahed", tp["shahed"])] \
            + [(c, re.compile(p, re.I)) for c, p in EXTRA_WEAPON_AFTER]
        self._cache: dict = {}

    def _add(self, src, gid, name, alts, lat, lon, iso, pop, code):
        names = set()
        for n in [name] + (alts.split(",") if isinstance(alts, str) else []):
            if n and _CYR.search(n) and not re.search(r"\d", n):
                nn = norm(n)
                if len(nn) >= 2:
                    names.add(nn)
        if not names or iso is None:
            return
        i = len(self.feats)
        self.feats.append(dict(src=src, id=gid, name=name, lat=float(lat), lon=float(lon), iso=iso, pop=int(pop or 0),
                               code=code, names=names))
        for nn in names:
            self.ix["exact"][nn].append(i)
            st = stem(nn)
            if len(st.replace(" ", "")) >= 3:
                self.ix["stem"][st].append(i)
                self.ix["fold"][fold(st)].append(i)

    def _load_viina(self):
        log("load VIINA tessellation properties")
        g = json.load(open(VIINA, encoding="utf-8"))
        self.tess_ids = set()
        for f in g["features"]:
            p = f["properties"]
            # GeoNames admin1_code first (curated); the tessellation's spatial ADM1_NAME puts border-adjacent
            # polygons in the neighbouring oblast (Vyshhorod -> Kyiv city), so it is only the fallback (code 0).
            try:
                iso = GN_ADMIN1_ISO.get(int(float(p["admin1_code"])))
            except Exception:
                iso = None
            if iso is None:
                iso = ADM1_NAME_ISO.get(p.get("ADM1_NAME"))
            gid = int(p["geonameid"])
            self.tess_ids.add(gid)
            self._add("viina", gid, p["name"], p.get("alternatenames"), p["latitude"], p["longitude"], iso,
                      p.get("population"), p.get("feature_code"))
        self.n_viina = len(self.feats)
        del g

    def _load_geonames(self):
        log("load GeoNames UA")
        z = zipfile.ZipFile(GEONAMES)
        u = pd.read_csv(z.open("UA.txt"), sep="\t", header=None, dtype=str, quoting=3, keep_default_na=False)
        for r in u.itertuples(index=False):
            cls, code = r[6], r[7]
            if cls == "P" and int(r[0]) not in self.tess_ids:
                try:
                    iso = GN_ADMIN1_ISO.get(int(r[10]))
                except Exception:
                    iso = None
                self._add("geonames", int(r[0]), r[1], r[3], r[4], r[5], iso, r[14] or 0, code)
            elif code == "ADM2":
                try:
                    iso = GN_ADMIN1_ISO.get(int(r[10]))
                except Exception:
                    iso = None
                if iso is None:
                    continue
                for n in [r[1]] + r[3].split(","):
                    if not _CYR.search(n):
                        continue
                    ws = [w for w in norm(_RAION_WORD.sub(" ", n)).split() if w]
                    if len(ws) != 1:
                        continue
                    bs = adj_base(ws[0])
                    key = stem_word(bs[0]) if bs else stem_word(ws[0])
                    rec = (iso, float(r[4]), float(r[5]), r[1], int(r[0]))
                    if rec not in self.raion[key]:
                        self.raion[key].append(rec)
        log(f"gazetteer: {self.n_viina} viina + {len(self.feats) - self.n_viina} geonames-only features; {len(self.raion)} raion keys")

    # ------------------------------------------------------------------ oblast
    def oblast_all(self, raw):
        """-> (list of ISO, flag). Segments split on ; , / ' та ' ' і '."""
        if not isinstance(raw, str) or not raw.strip():
            return [], "empty"
        if raw.strip().lower() in ("<national>", "україна", "україни", "по всій україні"):
            return [], "national"
        out = []
        for seg in re.split(r"[;,/]|\s+та\s+|\s+і\s+|\s+й\s+", raw):
            seg = seg.strip()
            if not seg:
                continue
            iso = None
            if self.kyiv_obl.search(seg):
                iso = "UA-32"
            elif self.kyiv_city.search(seg):
                iso = "UA-30"
            else:
                for k, pat in self.oblast_pats:
                    if k in ("UA-30", "UA-32"):
                        continue
                    if pat.search(seg):
                        iso = k
                        break
            if iso and iso not in out:
                out.append(iso)
        return out, ("ok" if out else "no_match")

    # ------------------------------------------------------------------ settlement geocode
    def _cands(self, tier, key, cset, src):
        out = []
        for i in self.ix[tier].get(key, ()):
            f = self.feats[i]
            if (src == "viina") != (f["src"] == "viina"):
                continue
            if cset is None or f["iso"] in cset:
                out.append(i)
        return out

    def _pick(self, idxs, raion_pt):
        """-> (idx|None, how, n)"""
        fs = [self.feats[i] for i in idxs]
        n = len(fs)
        if n == 1:
            return idxs[0], "", 1
        pts = [(f["lat"], f["lon"]) for f in fs]
        if max(hav(pts[0], p) for p in pts) <= 5.0:  # duplicate entries of one place
            return max(idxs, key=lambda i: self.feats[i]["pop"]), "dup", n
        if raion_pt is not None:
            ds = sorted((hav(raion_pt, p), i) for p, i in zip(pts, idxs))
            if ds[0][0] <= 40 and (len(ds) == 1 or ds[1][0] >= 2 * ds[0][0] + 5):
                return ds[0][1], "raion", n
        if POP_DOMINANCE:
            top = max(idxs, key=lambda i: self.feats[i]["pop"])
            tp = self.feats[top]["pop"]
            if tp >= POPDOM_MIN and all(tp >= 20 * max(self.feats[i]["pop"], 1) for i in idxs if i != top):
                return top, "popdom", n
        return None, "ambiguous", n

    def _raion_point(self, raion_raw, cset):
        if not isinstance(raion_raw, str):
            return None
        ws = [w for w in norm(_RAION_WORD.sub(" ", raion_raw)).split() if w]
        if len(ws) != 1:
            return None
        bs = adj_base(ws[0])
        key = stem_word(bs[0]) if bs else stem_word(ws[0])
        recs = [r for r in self.raion.get(key, ()) if cset is None or r[0] in cset]
        return (recs[0][1], recs[0][2]) if len(recs) == 1 else None

    def geocode(self, raw, iso=None, raion_raw=None, role=None):
        k = (raw, iso, raion_raw, role)
        if k not in self._cache:
            self._cache[k] = self._geocode(raw, iso, raion_raw, role)
        return self._cache[k]

    @staticmethod
    def _res(method, conf=None, level=None, f=None, n=0, **kw):
        d = dict(geo_method=method, geo_conf=conf, geo_level=level, geo_name=None, geo_id=None, geo_n_cand=n,
                 geo_oblast_iso=None, lat=None, lon=None, h3_r5=None)
        if f is not None:
            d.update(geo_name=f["name"], geo_id=f["id"], geo_oblast_iso=f["iso"], lat=f["lat"], lon=f["lon"],
                     h3_r5=h3r5(f["lat"], f["lon"]))
        d.update(kw)
        return d

    def _geocode(self, raw, iso, raion_raw, role=None):
        s = raw if isinstance(raw, str) else ""
        s = s.split("/")[0].split("|")[0].strip()
        cset = None
        if isinstance(iso, str) and iso:
            cset = KYIV_PAIR if iso in KYIV_PAIR else {iso}
        if not s:
            if isinstance(raion_raw, str) and raion_raw.strip():
                return self._raion_only(raion_raw, cset)
            return self._res("none_empty")
        s = _PREFIX.sub("", s)
        if _OBLAST_FORM.search(s) and self.oblast_all(s)[0]:
            return self._res("none_oblast_name")
        raion_pt = self._raion_point(raion_raw, cset)
        # "<Adj> району": seat of the raion; "<Adj> громада": seat of the hromada (same mechanism, own level)
        seat = False; seat_level = "raion_seat"
        if _RAION_WORD.search(s):
            seat = True
            s = _RAION_WORD.sub(" ", s)
        elif _HROMADA_WORD.search(s):
            seat = True; seat_level = "hromada_seat"
            s = _HROMADA_WORD.sub(" ", s)
        ws = norm(s).split()
        if not ws:
            return self._res("none_empty")
        queries = []  # (tier, key, conf, level)
        if seat:
            if len(ws) != 1:
                return self._res("none_unparsed")
            bs = adj_base(ws[0])
            if not bs:
                return self._res("none_unparsed")
            for b in bs:
                queries.append(("stem", stem_word(b), 0.6, seat_level))
        else:
            full = " ".join(ws)
            if len(full.replace(" ", "")) < 3:
                return self._res("none_short")
            full = RENAMED.get(full, full)
            alias = {"києва": "київ", "києву": "київ", "києві": "київ", "київ": "київ", "києвом": "київ"}.get(full)
            if alias:
                full = alias
            queries.append(("exact", full, 0.95, "settlement"))
            st = stem(full)
            if len(st.replace(" ", "")) >= 3:
                queries.append(("stem", st, 0.85, "settlement"))
                if cset is not None:  # vowel-fold is too loose nationwide
                    queries.append(("fold", fold(st), 0.6, "settlement"))
        pen = 0.15 if cset is None else 0.0
        amb_seen = None
        for src in ("viina", "geonames"):
            for tier, key, conf, level in queries:
                idxs = self._cands(tier, key, cset, src)
                if not idxs:
                    continue
                i, how, n = self._pick(idxs, raion_pt)
                if i is None:
                    amb_seen = (src, n)
                    break  # ambiguous at the first tier that has any candidate: do not fall to a looser tier
                c = conf - pen - {"": 0, "dup": 0.0, "raion": 0.25, "popdom": 0.2}[how]
                meth = f"{src}_{tier}" + (f"_{how}" if how else "") + ("_natl" if cset is None else "")
                return self._res(meth, round(c, 2), level, self.feats[i], n)
            if amb_seen and cset is None:
                return self._res(f"none_ambiguous_{amb_seen[0]}", None, None, None, amb_seen[1])
            if amb_seen:
                break
        # nothing (or only an ambiguous set) inside the stated oblast. The oblast may be a target/origin/context
        # rather than the place's own, so look nationwide (flagged *_xoblast):
        #  - a dominant town (popdom) is accepted whatever the oblast role;
        #  - a nationally unique name only when the extractor did not say the oblast is where the place is.
        if cset is not None and not seat:
            for src in ("viina", "geonames"):
                for tier, qi in (("exact", 0), ("stem", 1)):
                    if qi >= len(queries):
                        continue
                    idxs = self._cands(tier, queries[qi][1], None, src)
                    if not idxs:
                        continue
                    i, how, n = self._pick(idxs, None)
                    if i is None:
                        break
                    if how == "popdom":
                        return self._res(f"{src}_{tier}_xoblast_popdom", 0.4 if tier == "exact" else 0.35, "settlement", self.feats[i], n)
                    if how in ("", "dup") and role != "location" and self.feats[i]["pop"] >= 2000:  # villages in the wrong oblast stay null
                        return self._res(f"{src}_{tier}_xoblast", 0.5 if tier == "exact" else 0.4, "settlement", self.feats[i], n)
                    break
        if amb_seen:
            return self._res(f"none_ambiguous_{amb_seen[0]}", None, None, None, amb_seen[1])
        return self._res("none_unmatched")

    def _raion_only(self, raion_raw, cset):
        ws = [w for w in norm(_RAION_WORD.sub(" ", raion_raw)).split() if w]
        if len(ws) != 1:
            return self._res("none_empty")
        bs = adj_base(ws[0])
        key = stem_word(bs[0]) if bs else stem_word(ws[0])
        recs = [r for r in self.raion.get(key, ()) if cset is None or r[0] in cset]
        if len(recs) != 1:
            return self._res("none_raion_ambiguous" if recs else "none_raion_unmatched", n=len(recs))
        r = recs[0]
        f = dict(name=r[3], id=r[4], iso=r[0], lat=r[1], lon=r[2])
        return self._res("geonames_raion" + ("" if cset else "_natl"), 0.4 if cset else 0.25, "raion", f, 1)

    # ------------------------------------------------------------------ launch sites
    def site(self, raw, key_hint=None):
        """-> dict(site_key, site_name, site_kind, site_lat, site_lon, site_h3_r5, site_geo_method, site_geo_conf, site_oblast_iso)"""
        k = ("site", raw, key_hint)
        if k in self._cache:
            return self._cache[k]
        out = dict(site_key=None, site_name=None, site_kind=None, site_lat=None, site_lon=None, site_h3_r5=None,
                   site_geo_method="none_empty", site_geo_conf=None, site_oblast_iso=None)
        s = raw if isinstance(raw, str) else ""
        if s.strip():
            hit, how = None, None
            for key, pat in self.site_pats:
                if pat.search(s):
                    hit, how = key, "gazetteer_pattern"
                    break
            if hit is None and key_hint in self.sites:
                hit, how = key_hint, "gazetteer_extract_key"
            if hit is None:
                # stem fallback on the first word(s) against pattern-free gazetteer names (declension, ъ/ь variants)
                ns = norm(s)
                for key, v in self.sites.items():
                    cands = {stem(re.sub(r"[^\p{L} -]", "", v["name"].split(" (")[0].split(" / ")[0]))}
                    if any(len(c) >= 4 and stem(ns).startswith(c) for c in cands):
                        hit, how = key, "gazetteer_stem"
                        break
            if hit:
                v = self.sites[hit]
                region = bool(re.search(r"(област|обл\b|щин|ськ(ої|а|ий|ого)\b)", s, re.I)) and v["kind"] in ("city", "airbase")
                out.update(site_key=hit, site_name=v["name"], site_kind=v["kind"], site_lat=v["lat"], site_lon=v["lon"],
                           site_h3_r5=h3r5(v["lat"], v["lon"]), site_geo_method=how,
                           site_geo_conf=0.6 if region else 0.9)
            else:
                isos, _ = self.oblast_all(s)
                if isos:
                    out.update(site_oblast_iso=isos[0], site_geo_method="oblast_only", site_geo_conf=0.5)
                else:
                    out.update(site_geo_method="none_unmatched")
        self._cache[k] = out
        return out

    # ------------------------------------------------------------------ weapon
    def weapon(self, cls, raw, impact=False):
        if isinstance(cls, str) and cls in self.weapon_classes and cls != "unknown":
            return cls, "extract"
        if isinstance(raw, str):
            for c, p in (self.impact_weapon_pats if impact else self.weapon_pats):
                if p.search(raw):
                    return c, "taxonomy_raw"
        if isinstance(cls, str) and cls == "unknown":
            return "unknown", "extract"
        return None, "none"


# --------------------------------------------------------------------------- table drivers
GEO_COLS = ["geo_method", "geo_conf", "geo_level", "geo_name", "geo_id", "geo_n_cand", "geo_oblast_iso", "lat", "lon", "h3_r5"]
SITE_COLS = ["site_key", "site_name", "site_kind", "site_lat", "site_lon", "site_h3_r5", "site_geo_method",
             "site_geo_conf", "site_oblast_iso"]
ADDED = {
    "tracks": ["weapon_class_canon", "weapon_canon_src", "oblast_iso_canon", "oblast_canon_src"] + GEO_COLS,
    "launches": ["weapon_class_canon", "weapon_canon_src", "target_oblast_iso", "target_oblast_iso_all"] + GEO_COLS + SITE_COLS,
    "launch_intel": ["weapon_class_canon", "weapon_canon_src"] + ["loc_" + c for c in SITE_COLS],
    "impacts": ["weapon_class_canon", "weapon_canon_src", "oblast_iso_canon", "oblast_canon_src"] + GEO_COLS,
}


def base_hash(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(",".join(df.columns).encode())
    h.update(pd.util.hash_pandas_object(df.astype(str), index=False).values.tobytes())
    return h.hexdigest()


def load_base(name):
    p = EXTRACT / f"{name}.parquet"
    df = pd.read_parquet(p)
    return p, df.drop(columns=[c for c in ADDED[name] if c in df.columns])


def apply_geo(df, G, raw_col, iso_col, raion_col=None, prefix="", role_col=None):
    keys = list(zip(df[raw_col], df[iso_col] if iso_col else [None] * len(df),
                    df[raion_col] if raion_col else [None] * len(df)))
    roles = list(df[role_col]) if role_col else [None] * len(df)
    nn = lambda x: None if (x is None or (isinstance(x, float) and x != x)) else x
    res = [G.geocode(nn(a), nn(b), nn(c), nn(r)) for (a, b, c), r in zip(keys, roles)]
    for col in GEO_COLS:
        df[prefix + col] = [r[col] for r in res]


def write_pq(df, p):
    tmp = p.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(p)


def main():
    tax = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    G = Gaz(tax)
    stats, inputs = {}, {}

    # ---- tracks
    p, t = load_base("tracks")
    inputs["tracks_base"] = base_hash(t)
    wc = [G.weapon(a, b) for a, b in zip(t.weapon_class, t.weapon_raw)]
    t["weapon_class_canon"], t["weapon_canon_src"] = [w[0] for w in wc], [w[1] for w in wc]
    oc, osrc = [], []
    for iso, raw in zip(t.oblast_iso, t.oblast_raw):
        if isinstance(iso, str):
            oc.append(iso); osrc.append("extract")
            continue
        isos, fl = G.oblast_all(raw)
        oc.append(isos[0] if isos else None); osrc.append("taxonomy_raw" if isos else "none")
    t["oblast_iso_canon"], t["oblast_canon_src"] = oc, osrc
    apply_geo(t, G, "settlement_raw", "oblast_iso_canon", "raion_raw", role_col="oblast_role")
    write_pq(t, p)
    ms = t.geo_method.fillna("none")
    stats["tracks"] = dict(rows=len(t), with_settlement_raw=int(t.settlement_raw.notna().sum()),
                           geocoded_settlement=int(((t.geo_level == "settlement") & t.lat.notna()).sum()),
                           geocoded_any=int(t.lat.notna().sum()),
                           oblast_canon_nonnull=int(t.oblast_iso_canon.notna().sum()),
                           weapon_canon_nonnull=int(t.weapon_class_canon.notna().sum()),
                           geo_method=ms.value_counts().to_dict())
    log(f"tracks {stats['tracks']['geocoded_settlement']}/{stats['tracks']['with_settlement_raw']} settlements geocoded")

    # ---- launches
    p, l = load_base("launches")
    inputs["launches_base"] = base_hash(l)
    wc = [G.weapon(a, b) for a, b in zip(l.weapon_class, l.weapon_raw)]
    l["weapon_class_canon"], l["weapon_canon_src"] = [w[0] for w in wc], [w[1] for w in wc]
    first, allv = [], []
    for raw in l.target_oblast_raw:
        isos, _ = G.oblast_all(raw)
        first.append(isos[0] if isos else None); allv.append("|".join(isos) if isos else None)
    l["target_oblast_iso"], l["target_oblast_iso_all"] = first, allv
    apply_geo(l, G, "target_settlement_raw", "target_oblast_iso")
    sites = [G.site(r, k) for r, k in zip(l.launch_site_raw, l.launch_site_key)]
    for c in SITE_COLS:
        l[c] = [s[c] for s in sites]
    write_pq(l, p)
    stats["launches"] = dict(rows=len(l), target_oblast_raw=int(l.target_oblast_raw.notna().sum()),
                             target_oblast_iso=int(l.target_oblast_iso.notna().sum()),
                             target_settlement_raw=int(l.target_settlement_raw.notna().sum()),
                             target_settlement_geocoded=int(l.lat.notna().sum()),
                             launch_site_raw=int(l.launch_site_raw.notna().sum()),
                             launch_site_resolved_coords=int(l.site_lat.notna().sum()),
                             launch_site_oblast_only=int((l.site_geo_method == "oblast_only").sum()),
                             weapon_canon_src=l.weapon_canon_src.value_counts().to_dict())

    # ---- launch_intel
    p, i = load_base("launch_intel")
    inputs["launch_intel_base"] = base_hash(i)
    wc = [G.weapon(a, None) for a in i.weapon_hint]
    i["weapon_class_canon"], i["weapon_canon_src"] = [w[0] for w in wc], [w[1] for w in wc]
    sites = [G.site(r, k) for r, k in zip(i.location_raw, i.location_key)]
    for c in SITE_COLS:
        i["loc_" + c] = [s[c] for s in sites]
    write_pq(i, p)
    stats["launch_intel"] = dict(rows=len(i), location_raw=int(i.location_raw.notna().sum()),
                                 location_resolved_coords=int(i.loc_site_lat.notna().sum()),
                                 location_oblast_only=int((i.loc_site_geo_method == "oblast_only").sum()))

    # ---- impacts (LLM extraction; absent until 23_extract_impacts.py has run)
    if (EXTRACT / "impacts.parquet").exists():
        p, m = load_base("impacts")
        inputs["impacts_base"] = base_hash(m)
        wc = [G.weapon(None, r, impact=True) for r in m.weapon_raw]
        m["weapon_class_canon"], m["weapon_canon_src"] = [w[0] for w in wc], [w[1] for w in wc]
        oc, osrc = [], []
        for ch, raw in zip(m.channel, m.oblast_raw):
            isos, fl = G.oblast_all(raw)
            if isos:
                oc.append(isos[0]); osrc.append("taxonomy_raw")
            elif ch in CHANNEL_HOME_OBLAST:
                oc.append(CHANNEL_HOME_OBLAST[ch]); osrc.append("channel_home")
            else:
                oc.append(None); osrc.append("none")
        m["oblast_iso_canon"], m["oblast_canon_src"] = oc, osrc
        apply_geo(m, G, "settlement_raw", "oblast_iso_canon", "raion_raw")
        # Kyiv city rows with no settlement/raion match: the city itself is the settlement (flagged, low conf)
        kyiv = (m.oblast_iso_canon == "UA-30") & m.lat.isna() & m.settlement_raw.isna()
        if kyiv.any():
            kg = G.geocode("Київ", "UA-30", None, None)
            if kg["lat"] is not None:
                for col in GEO_COLS:
                    m.loc[kyiv, col] = kg[col]
                m.loc[kyiv, "geo_method"] = "kyiv_city_default"; m.loc[kyiv, "geo_level"] = "city"; m.loc[kyiv, "geo_conf"] = 0.3
        write_pq(m, p)
        has_place = m.settlement_raw.notna() | m.raion_raw.notna()
        stats["impacts"] = dict(rows=len(m), with_settlement_raw=int(m.settlement_raw.notna().sum()),
                                with_settlement_or_raion=int(has_place.sum()),
                                geocoded_settlement=int(((m.geo_level == "settlement") & m.lat.notna()).sum()),
                                geocoded_raion_level=int(m.geo_level.isin(["raion", "raion_seat", "hromada_seat"]).sum()),
                                geocoded_kyiv_city_default=int(kyiv.sum()),
                                geocoded_any=int(m.lat.notna().sum()),
                                geocode_rate_of_settlement_raw=round(float(((m.geo_level == "settlement") & m.lat.notna() & m.settlement_raw.notna()).sum() / max(m.settlement_raw.notna().sum(), 1)), 4),
                                geocode_rate_any_of_rows=round(float(m.lat.notna().mean()), 4),
                                oblast_canon_src=m.oblast_canon_src.value_counts().to_dict(),
                                oblast_iso_canon=m.oblast_iso_canon.value_counts().to_dict(),
                                weapon_class_canon=m.weapon_class_canon.fillna("<none>").value_counts().to_dict(),
                                geo_method=m.geo_method.fillna("none").value_counts().to_dict())
        log(f"impacts {stats['impacts']['geocoded_settlement']}/{stats['impacts']['with_settlement_raw']} settlements geocoded; "
            f"{stats['impacts']['geocoded_any']}/{len(m)} rows with coordinates")
        um = m[m.settlement_raw.notna() & m.lat.isna()].groupby(["settlement_raw", "oblast_iso_canon", "geo_method"], dropna=False).size() \
            .reset_index(name="n").sort_values("n", ascending=False).head(300)
        um.to_csv(EXTRACT / "resolve_unmatched_impacts_top300.csv", index=False)
    else:
        log("impacts.parquet absent: skipped")

    # ---- unmatched report (interim only)
    um = t[t.settlement_raw.notna() & t.lat.isna()].groupby(["settlement_raw", "oblast_iso_canon", "geo_method"], dropna=False).size() \
        .reset_index(name="n").sort_values("n", ascending=False).head(300)
    um.to_csv(EXTRACT / "resolve_unmatched_top300.csv", index=False)
    ul = pd.concat([l[l.launch_site_raw.notna() & l.site_lat.isna()][["launch_site_raw"]].rename(columns={"launch_site_raw": "raw"}),
                    i[i.location_raw.notna() & i.loc_site_lat.isna()][["location_raw"]].rename(columns={"location_raw": "raw"})])
    ul.value_counts().reset_index(name="n").head(200).to_csv(EXTRACT / "resolve_unmatched_sites_top200.csv", index=False)

    meta = dict(script="30_resolve.py", resolve_version=RESOLVE_VERSION, prompt_version=None,
                written_utc=pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
                inputs={"viina_tess": {"path": str(VIINA.relative_to(ROOT)), "sha256": sha256_file(VIINA)},
                        "geonames_UA": {"path": str(GEONAMES.relative_to(ROOT)), "sha256": sha256_file(GEONAMES)},
                        "taxonomy": {"path": str(TAXONOMY.relative_to(ROOT)), "sha256": sha256_file(TAXONOMY)},
                        **{k: {"sha256_of_pre_resolve_columns": v} for k, v in inputs.items()}},
                settings=dict(pop_dominance=POP_DOMINANCE, tiers=["exact", "stem", "fold"],
                              gazetteer_features=len(G.feats), viina_features=G.n_viina),
                added_columns=ADDED, counts=stats)
    (EXTRACT / "resolve_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str))
    log("done")


if __name__ == "__main__":
    main()
