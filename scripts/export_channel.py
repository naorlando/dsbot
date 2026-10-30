r"""One-off: dump a Discord channel's history to JSON, via the BOT token.

Only paginated read-only GETs; no SDK. Run from the repo root:

    set DISCORD_TOKEN=...           (cópialo un momento desde Railway)
    set CHANNEL_ID=1139681313197133874
    .venv\Scripts\python.exe scripts\export_channel.py

Output: channel_history.json (gitignored; contains private messages).
Defaults: last 14 days / at most 42,000 messages. EXPORT_DAYS=0 explicitly
removes the date cutoff; EXPORT_MAX_MESSAGES still bounds the export.
An atomic checkpoint every 20 pages preserves progress if interrupted.
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

import aiohttp

API = "https://discord.com/api/v10"


def checkpoint(rows, name="channel_history.json"):
    temporary = name + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(sorted(rows, key=lambda row: row["ts"] or ""), handle,
                  ensure_ascii=False, indent=1)
    os.replace(temporary, name)


async def main():
    # Optional local config file (gitignored): scripts/.env_local with
    # DISCORD_TOKEN=... y CHANNEL_ID=... — delete it after the export.
    local = os.path.join(os.path.dirname(__file__), ".env_local")
    if os.path.exists(local):
        with open(local, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())
    token = os.environ.get("DISCORD_TOKEN") or os.environ.get("DISCORD_BOT_TOKEN")
    channel = os.environ.get("CHANNEL_ID")
    days_limit = int(os.environ.get("EXPORT_DAYS", "14")) or None
    max_messages = min(150_000, max(1, int(os.environ.get("EXPORT_MAX_MESSAGES", "42000"))))
    if not token or not channel:
        sys.exit("faltan DISCORD_TOKEN y CHANNEL_ID.")
    out, before, pages = [], None, 0
    timeout = aiohttp.ClientTimeout(total=25)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            params = {"limit": 100}
            if before:
                params["before"] = before
            for attempt in (1, 2, 3):
                async with session.get(f"{API}/channels/{channel}/messages",
                                       headers={"Authorization": "Bot " + token},
                                       params=params) as response:
                    if response.status == 429:
                        delay = float((await response.json()).get("retry_after", 1.0))
                        if not 0 <= delay <= 60:
                            sys.exit("Discord pidió una pausa larga; se conserva el último checkpoint.")
                        await asyncio.sleep(delay)
                        continue
                    if response.status != 200:
                        sys.exit(f"Discord {response.status}; exportación interrumpida.")
                    batch = await response.json()
                    break
            else:
                sys.exit("se finieron los 3 reintentos del rate limit")
            if not batch:
                break
            for message in batch:
                if len(out) >= max_messages:
                    break
                # Bounded export: stop the window at EXPORT_DAYS if set.
                if days_limit is not None:
                    created_ms = ((int(message["id"]) >> 22) + 1420070400000) / 1000
                    if time.time() - created_ms > days_limit * 86400:
                        break
                content = message.get("content") or ""
                author = message.get("author") or {}
                if content.strip():
                    out.append({
                        "ts": message.get("timestamp"),
                        "author": author.get("username"),
                        "bot": bool(author.get("bot")),
                        "content": content,
                    })
            if days_limit is not None and len(batch) > 0:
                first_ms = ((int(batch[-1]["id"]) >> 22) + 1420070400000) / 1000
                if time.time() - first_ms > days_limit * 86400:
                    break
            before = batch[-1]["id"]
            pages += 1
            if pages % 20 == 0:
                checkpoint(out)
                print(f"...{len(out)} mensajes, {pages} paginas", flush=True)
            if len(out) >= max_messages:
                break
            if len(batch) < 100:
                break
            await asyncio.sleep(0.25)
    name = "channel_history.json"
    checkpoint(out, name)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"{len(out)} mensajes, {pages} paginas exportadas a {name} ({stamp})")
    print("acordate de vaciar DISCORD_TOKEN de tus variables locales despues de correr esto")


if __name__ == "__main__":
    asyncio.run(main())
