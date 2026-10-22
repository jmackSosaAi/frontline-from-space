"""Telegram public web-preview scrape (Route A, planning/scout_telegram.md §3). No login, no API, no account.

Pulls the full post history of public official / monitoring channels from https://t.me/s/<handle>?before=<msg_id>
(t.me robots.txt is 404). Added after prereg-v1 as an additional validation-event source (set "V-telegram"); see
DEVIATIONS.md 2026-10-22. Nothing here is territorial-control data: @DeepStateUA is EXCLUDED and must never be added.

Per channel:
  1. verify: the preview page must show the expected title fragment and >= MIN_SUBS subscribers, else skip + report
     (also skipped when the channel hides its preview).
  2. backfill: page backwards with ?before=<lowest msg_id saved> until the first post (resumable at any point).
  3. head top-up: page forwards with ?after=<highest msg_id saved> to catch posts made during the backfill.
  4. finalise: rewrite the file deduped and sorted oldest -> newest, then write its manifest record to
     data/manifest_parts/telegram_preview.json (file, url, bytes, rows, sha256, set "V-telegram", retrieved_utc).

Output: data/raw/telegram/<handle>.jsonl, one JSON object per post:
  channel, msg_id, date_utc, text, views (as displayed, e.g. "23.2K"), has_media, forwarded_from_channel (public
  channel handle when the preview links one, else null). No user/author/signature data is stored.
State: data/raw/telegram/_state/<handle>.json  Logs: data/raw/telegram/_logs/

Politeness: one request at a time per process, ~2 s between pages, User-Agent with CONTACT_EMAIL from .env,
backoff on 429/5xx/network errors (Retry-After honoured). Run at most 2 processes at once.
Telegram terms §1.5: data obtained from Telegram must not be used to train or fine-tune AI/ML models.

Run:  python3 -I scripts/fetch_telegram_preview.py kpszsu VA_Kyiv ...     (channels run sequentially)
      python3 -I scripts/fetch_telegram_preview.py --verify-only <handles>
"""
import datetime, fcntl, hashlib, html, json, os, pathlib, random, re, sys, time, urllib.error, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
OUT = RAW / "telegram"
STATE = OUT / "_state"
PART = ROOT / "data/manifest_parts/telegram_preview.json"
DELAY = 2.0
MIN_SUBS = 10_000
SET = "V-telegram"
FORBIDDEN = {"deepstateua", "deepstate_ua", "deepstatemap"}  # gated territorial-control source (C1 family)

# handle -> fragment that must appear in the preview title (checked 2026-10-22)
EXPECTED = {
    "kpszsu": "Повітряні Сили",
    "VA_Kyiv": "Київська міська військова адміністрація",
    "synegubov": "Синєгубов",
    "odeskaODA": "Одеська ОДА",
    "dnipropetrovskaODA": "Дніпропетровська ОДА",
    "zoda_gov_ua": "Запорізька ОВА",
    "kozytskyy_maksym_official": "Львівська ОВА",
    "war_monitor": "monitor",
    "monitoringwar": "monitorwar",
}


def env(key, default=""):
    try:
        for line in (ROOT / ".env").read_text().splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"\'')
    except FileNotFoundError:
        pass
    return default


UA = f"frontline-from-space research ({env('CONTACT_EMAIL', 'jmackney@uchicago.edu')})"


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def log(*a):
    print(now(), *a, flush=True)


def fetch(url):
    """GET with backoff on 429 / 5xx / network errors. Returns (final_url, text)."""
    wait = 30
    for attempt in range(12):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.geturl(), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 429 or 500 <= e.code < 600:
                ra = e.headers.get("Retry-After")
                s = int(ra) if ra and ra.isdigit() else wait
                log(f"HTTP {e.code} on {url}; sleeping {s}s"); time.sleep(s); wait = min(wait * 2, 900); continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            log(f"net error {e!r} on {url}; sleeping {wait}s"); time.sleep(wait); wait = min(wait * 2, 900); continue
    raise RuntimeError(f"giving up on {url}")


def subs_count(s):
    m = re.search(r'<span class="counter_value">([^<]+)</span> <span class="counter_type">subscribers', s)
    if not m:
        return None
    v = m.group(1).strip().upper().replace(" ", "")
    mult = {"K": 1e3, "M": 1e6}.get(v[-1:], 1)
    try:
        return int(float(v.rstrip("KM")) * mult)
    except ValueError:
        return None


def title_of(s):
    m = re.search(r'tgme_channel_info_header_title">(.*?)</div>', s, re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else None


def verify(handle):
    final, s = fetch(f"https://t.me/s/{handle}")
    t, n = title_of(s), subs_count(s)
    has_posts = f'data-post="{handle}/' in s or 'data-post="' in s
    info = {"handle": handle, "title": t, "subscribers": n, "verified_badge": "verified-icon" in s,
            "preview": has_posts and "/s/" in final, "checked_utc": now()}
    exp = EXPECTED.get(handle)
    ok = bool(t and exp and exp.lower() in t.lower() and n and n >= MIN_SUBS and info["preview"])
    info["ok"] = ok
    if not ok:
        info["reason"] = ("preview hidden" if not info["preview"] else
                          "title mismatch" if not (t and exp and exp.lower() in t.lower()) else "too few subscribers")
    return info, s


TEXT_RE = re.compile(r'<div class="tgme_widget_message_text js-message_text"[^>]*>(.*?)</div>', re.S)
MEDIA_RE = re.compile(r'class="tgme_widget_message_(?:photo|video|roundvideo|document|voice|audio|sticker|grouped|animated)')
FWD_RE = re.compile(r'<a class="tgme_widget_message_forwarded_from_name" href="https://t\.me/([A-Za-z0-9_]+)(?:/\d+)?"')


def parse(page, handle):
    """Return list of post dicts. Only channel-level fields; author/signature/user blocks are ignored."""
    posts = []
    chunks = re.split(r'(?=<div class="tgme_widget_message_wrap)', page)
    for c in chunks:
        m = re.search(r'data-post="([^"/]+)/(\d+)"', c)
        if not m or m.group(1).lower() != handle.lower():
            continue
        tm = re.search(r'<time datetime="([^"]+)"', c)
        date = None
        if tm:
            try:
                date = datetime.datetime.fromisoformat(tm.group(1)).astimezone(datetime.timezone.utc).isoformat()
            except ValueError:
                date = tm.group(1)
        tx = TEXT_RE.search(c)
        text = ""
        if tx:
            text = re.sub(r"<br\s*/?>", "\n", tx.group(1))
            text = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
        vw = re.search(r'class="tgme_widget_message_views">([^<]+)<', c)
        fw = FWD_RE.search(c)
        posts.append({"channel": handle, "msg_id": int(m.group(2)), "date_utc": date, "text": text,
                      "views": vw.group(1).strip() if vw else None, "has_media": bool(MEDIA_RE.search(c)),
                      "forwarded_from_channel": fw.group(1) if fw else None})
    return posts


def load_state(handle):
    p = STATE / f"{handle}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_state(handle, st):
    STATE.mkdir(parents=True, exist_ok=True)
    p = STATE / f"{handle}.json"
    tmp = p.with_suffix(".tmp"); tmp.write_text(json.dumps(st, indent=1, ensure_ascii=False)); os.replace(tmp, p)


def load_ids(path):
    ids = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                try: ids.add(int(json.loads(line)["msg_id"]))
                except Exception: pass  # tolerate a truncated last line from an interrupted run
    return ids


def write_manifest(rel, url, path, rows):
    PART.parent.mkdir(parents=True, exist_ok=True)
    b = path.read_bytes()
    e = {"file": rel, "url": url, "bytes": len(b), "rows": rows, "sha256": hashlib.sha256(b).hexdigest(),
         "set": SET, "retrieved_utc": now()}
    lock = PART.with_suffix(".lock")
    with open(lock, "w") as lf:  # two processes may finish at once
        fcntl.flock(lf, fcntl.LOCK_EX)
        man = json.loads(PART.read_text()) if PART.exists() else []
        man = [m for m in man if m["file"] != rel] + [e]
        tmp = PART.with_suffix(".tmp"); tmp.write_text(json.dumps(man, indent=1, ensure_ascii=False)); os.replace(tmp, PART)
        fcntl.flock(lf, fcntl.LOCK_UN)
    return e


def finalise(handle, path):
    rows = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try: p = json.loads(line); rows[int(p["msg_id"])] = p
            except Exception: pass
    tmp = path.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as fo:
        for k in sorted(rows):
            fo.write(json.dumps(rows[k], ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return write_manifest(str(path.relative_to(RAW)), "https://t.me/s/%s?before={msg_id}" % handle, path, len(rows))


def scrape(handle, first_page=None):
    path = OUT / f"{handle}.jsonl"
    st = load_state(handle)
    ids = load_ids(path)
    pages = st.get("pages", 0)
    log(f"[{handle}] start: {len(ids)} posts on disk, backfill_done={st.get('backfill_done', False)}")
    with open(path, "a", encoding="utf-8") as fo:
        def add(posts):
            new = [p for p in posts if p["msg_id"] not in ids]
            for p in new:
                ids.add(p["msg_id"]); fo.write(json.dumps(p, ensure_ascii=False) + "\n")
            fo.flush()
            return new

        # 2. backfill, newest -> oldest
        if not st.get("backfill_done"):
            before = min(ids) if ids else None
            while True:
                if before is None and first_page is not None:
                    page, first_page = first_page, None
                else:
                    time.sleep(DELAY + random.uniform(0, 0.5))
                    _, page = fetch(f"https://t.me/s/{handle}" + (f"?before={before}" if before else ""))
                posts = parse(page, handle)
                new = add(posts)
                pages += 1
                if posts:
                    oldest = min(p["msg_id"] for p in posts)
                else:
                    mb = re.search(r'data-before="(\d+)"', page)
                    oldest = int(mb.group(1)) if mb else None
                if pages % 25 == 0 or pages <= 3:
                    d = min((p["date_utc"] or "") for p in posts) if posts else "-"
                    log(f"[{handle}] page {pages} before={before} got={len(posts)} new={len(new)} total={len(ids)} oldest_date={d}")
                st.update({"pages": pages, "lowest_msg_id": min(ids) if ids else None, "updated_utc": now()})
                save_state(handle, st)
                if oldest is None or oldest <= 1 or (before is not None and oldest >= before):
                    break
                before = oldest
            st["backfill_done"] = True; save_state(handle, st)
            log(f"[{handle}] backfill done: {len(ids)} posts, {pages} pages")

        # 3. head top-up, oldest -> newest from the highest id saved
        while ids:
            after = max(ids)
            time.sleep(DELAY + random.uniform(0, 0.5))
            _, page = fetch(f"https://t.me/s/{handle}?after={after}")
            pages += 1
            new = add([p for p in parse(page, handle) if p["msg_id"] > after])
            if not new:
                break
            log(f"[{handle}] head top-up +{len(new)}")
    st.update({"pages": pages, "updated_utc": now()}); save_state(handle, st)
    e = finalise(handle, path)
    st.update({"complete_utc": now(), "rows": e["rows"], "sha256": e["sha256"]}); save_state(handle, st)
    log(f"[{handle}] DONE rows={e['rows']} bytes={e['bytes']} sha256={e['sha256'][:12]}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    verify_only = "--verify-only" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for i, h in enumerate(args):
        if h.lower().lstrip("@") in FORBIDDEN:
            log(f"[{h}] REFUSED: gated territorial-control source"); report.append({"handle": h, "ok": False, "reason": "forbidden"}); continue
        if i:
            time.sleep(DELAY)
        info, page = verify(h)
        report.append(info)
        st = load_state(h); st["verify"] = info; save_state(h, st)
        log(f"[{h}] verify ok={info['ok']} title={info['title']!r} subs={info['subscribers']} badge={info['verified_badge']}"
            + ("" if info["ok"] else f" SKIP: {info['reason']}"))
        if not info["ok"] or verify_only:
            continue
        try:
            scrape(h, first_page=page if not load_ids(OUT / f"{h}.jsonl") else None)
        except Exception as ex:
            log(f"[{h}] FAILED {ex!r}; rerun to resume")
    log("summary", json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
