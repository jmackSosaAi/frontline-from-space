"""Full-history pull of public Telegram channels via the Telegram API (Telethon). Backup to fetch_telegram_preview.py.
Needs TG_API_ID and TG_API_HASH in .env. First run is interactive: Telethon asks for Jackson's phone, login code
(and 2FA password) and writes tg_frontline.session, which is a full login to his account (gitignored; delete when done).
Read-only: never joins channels or sends messages. Writes data/raw/telegram_api/<handle>.jsonl, resumable by msg_id.
Usage: python3 -I scripts/fetch_telegram_api.py [handle ...]"""
import asyncio, json, pathlib, sys
from telethon import TelegramClient
from telethon.errors import FloodWaitError

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/telegram_api"; OUT.mkdir(parents=True, exist_ok=True)
ENV = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l and not l.startswith("#"))
CHANNELS = sys.argv[1:] or ["kpszsu", "VA_Kyiv", "synegubov", "odeskaODA", "dnipropetrovskaODA",
                            "zoda_gov_ua", "kozytskyy_maksym_official", "war_monitor", "monitoringwar"]

async def pull(client, handle):
    path = OUT / f"{handle}.jsonl"
    last = 0
    if path.exists():
        for line in path.open():
            last = max(last, json.loads(line)["msg_id"])
    n = 0
    with path.open("a") as f:
        while True:
            try:
                async for m in client.iter_messages(handle, reverse=True, min_id=last, wait_time=1):
                    fwd = getattr(getattr(m.fwd_from, "from_id", None), "channel_id", None) if m.fwd_from else None
                    f.write(json.dumps({"channel": handle, "msg_id": m.id, "date_utc": m.date.isoformat(),
                                        "text": m.message or "", "views": m.views, "has_media": m.media is not None,
                                        "edit_date_utc": m.edit_date.isoformat() if m.edit_date else None,
                                        "forwarded_from_channel": fwd}, ensure_ascii=False) + "\n")
                    last = m.id; n += 1
                    if n % 1000 == 0:
                        f.flush(); print(handle, n, m.date.date(), flush=True)
                break
            except FloodWaitError as e:
                print(f"{handle}: FloodWait {e.seconds}s", flush=True); await asyncio.sleep(e.seconds + 5)
    print(f"done {handle}: {n} new posts", flush=True)

async def main():
    async with TelegramClient(str(ROOT / "tg_frontline"), int(ENV["TG_API_ID"]), ENV["TG_API_HASH"]) as client:
        for h in CHANNELS:
            await pull(client, h)

asyncio.run(main())
