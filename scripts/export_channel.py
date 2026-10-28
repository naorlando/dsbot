r"""One-off: dump a Discord channel's history to JSON, via the BOT token.

Only paginated read-only GETs; no SDK. Run from the repo root:

    set DISCORD_TOKEN=...           (cópialo un momento desde Railway)
    set CHANNEL_ID=1139681313197133874
    .venv\Scripts\python.exe scripts\export_channel.py

Output: channel_history.json (add it to .gitignore afterwards — it holds
other people's messages, never commit it).
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

import aiohttp

API = "https://discord.com/api/v10"


async def main():
    token = os.environ.get("DISCORD_TOKEN")
    channel = os.environ.get("CHANNEL_ID")
    if not token or not channel:
        sys.exit("m ls DISCORD_TOKEN y CHANNEL_ID.")
    out, before, pages = [], None, 0
    async with aiohttp.ClientSession() as session:
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
                        await asyncio.sleep(delay)
                        continue
                    if response.status != 200:
                        body = await response.text()
                        sys.exit(f"Discord {response.status}: {body[:200]}")
                    batch = await response.json()
                    break
            else:
                sys.exit("se finieron los 3 reintentos del rate limit")
            if not batch:
                break
            for message in batch:
                content = message.get("content") or ""
                author = message.get("author") or {}
                if content.strip():
                    out.append({
                        "ts": message.get("timestamp"),
                        "author": author.get("username"),
                        "bot": bool(author.get("bot")),
                        "content": content,
                    })
            before = batch[-1]["id"]
            pages += 1
            if len(batch) < 100:
                break
            await asyncio.sleep(0.4)
    rows = sorted(out, key=lambda row: row["ts"] or "")
    name = "channel_history.json"
    with open(name, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=1)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"{len(rows)} mensajes, {pages} paginas exportadas a {name} ({stamp})")
    print("acordate de vaciar DISCORD_TOKEN de tus variables locales despues de correr esto")


if __name__ == "__main__":
    asyncio.run(main())
