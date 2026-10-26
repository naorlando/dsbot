"""Validated read-only exploration of the bot's own aggregated stats.

Only aggregates already saved by tracking are exposed: display names,
minutes and counters, clamped rows. No IDs, raw usernames, message
contents or full record dumps. Raises ValueError on invalid input; the
agent loop converts that into a safe user-facing error.
"""

import re
from datetime import datetime, timedelta


_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
_ACTIONS = {"list_games", "game_detail", "user_detail", "day_summary"}


def _fold(value):
    return value.casefold()


def _resolve(query, pool):
    """Case-insensitive unique match; ambiguous or unknown names are rejected."""
    q = _fold(query.strip())
    matches = [k for k in pool if _fold(k) == q]
    if len(matches) == 1:
        return matches[0]
    matches = [k for k in pool if _fold(k).startswith(q)]
    if len(matches) == 1:
        return matches[0]
    matches = [k for k in pool if q in _fold(k)]
    if len(matches) == 1:
        return matches[0]
    raise ValueError


def _day_minutes(record, day):
    daily = record.get("daily_minutes", {})
    if not isinstance(daily, dict):
        return 0.0
    value = daily.get(day)
    return round(value, 1) if isinstance(value, (int, float)) and value >= 0 else 0.0


def _minutes(record, since=None):
    """Total minutes, or minutes from `since` (inclusive) using daily buckets."""
    if not isinstance(record, dict):
        return 0.0
    total = record.get("total_minutes", 0)
    if not isinstance(total, (int, float)) or total < 0:
        return 0.0
    if since is None:
        return round(float(total), 1)
    daily = record.get("daily_minutes", {})
    if not isinstance(daily, dict):
        return 0.0
    return round(sum(value for key, value in daily.items()
                     if isinstance(value, (int, float)) and value >= 0
                     and isinstance(key, str) and _DATE_PATTERN.fullmatch(key)
                     and since <= key), 1)


def _counter(value):
    return value if isinstance(value, (int, float)) and 0 <= value else 0


def _game_records(data, member_uids):
    """name -> {uid: record} for current members only."""
    index = {}
    for uid in member_uids:
        games = data.get("users", {}).get(uid, {}).get("games", {})
        if isinstance(games, dict):
            for name, record in games.items():
                if isinstance(name, str) and isinstance(record, dict):
                    index.setdefault(name, {})[uid] = record
    return index


def day_digest(data, member_names, now=None):
    """Facts for the nightly digest; same privacy rules as query_stats.

    Returns None when nothing was tracked that day, so the caller can skip.
    """
    if not isinstance(data, dict) or not isinstance(member_names, dict):
        raise ValueError
    now = now or datetime.now()
    day = now.strftime("%Y-%m-%d")
    member_uids = {str(uid) for uid in member_names if str(uid) in data.get("users", {})}
    display = {uid: str(member_names[uid])[:64] for uid in member_uids}
    users = data.get("users", {})
    games, voice_rows, connection_rows, voice_total, game_total = {}, {}, [], 0.0, 0.0
    for uid in member_uids:
        user = users.get(uid, {})
        for name, record in (user.get("games", {}) if isinstance(user.get("games"), dict) else {}).items():
            if isinstance(name, str) and isinstance(record, dict):
                minutes = _day_minutes(record, day)
                if minutes > 0:
                    games[name[:80]] = games.get(name[:80], 0.0) + minutes
                    game_total += minutes
        voice = user.get("voice", {})
        if isinstance(voice, dict):
            minutes = _day_minutes(voice, day)
            if minutes > 0:
                voice_rows.append({"member": display[uid], "minutes": minutes})
                voice_total += minutes
        connections = user.get("daily_connections", {})
        if isinstance(connections, dict):
            count = (connections.get("by_date", {}) if isinstance(connections.get("by_date"), dict) else {}).get(day)
            if isinstance(count, (int, float)) and count > 0:
                connection_rows.append({"member": display[uid], "connections": round(count)})
    if not game_total and not voice_total and not connection_rows:
        return None
    top_games = [{"game": name, "minutes": round(minutes, 1)}
                 for name, minutes in sorted(games.items(), key=lambda row: row[1], reverse=True)[:3]]
    return {"fecha": day,
            "dia": ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")[now.weekday()],
            "minutos_totales_juegos": round(game_total, 1) or "cero",
            "juegos_del_dia": top_games or "ninguno",
            "minutos_totales_voz": round(voice_total, 1) or "cero",
            "voz_por_miembro": sorted(voice_rows, key=lambda row: row["minutes"], reverse=True)[:3] or "nadie",
            "conexiones_de_hoy": sorted(connection_rows, key=lambda row: row["connections"], reverse=True)[:3] or "nadie se reconectó"}


def query_stats(data, member_names, args, now=None):
    """Dispatch validated args; rows clamped; display names only."""
    if not isinstance(data, dict) or not isinstance(args, dict) or not isinstance(member_names, dict):
        raise ValueError
    if set(args) - {"action", "game", "user", "date"}:
        raise ValueError
    action = args.get("action")
    if action not in _ACTIONS:
        raise ValueError
    game = args.get("game")
    user = args.get("user")
    day = args.get("date")
    for value in (game, user):
        if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 80):
            raise ValueError
    if action == "day_summary":
        if not isinstance(day, str) or not _DATE_PATTERN.fullmatch(day.strip() or "x") or day != day.strip():
            raise ValueError
        try:
            datetime.strptime(day, "%Y-%m-%d")
        except ValueError:
            raise ValueError
    elif day is not None:
        raise ValueError
    if action == "game_detail" and (not game or user):
        raise ValueError
    if action == "user_detail" and (not user or game):
        raise ValueError

    member_uids = {str(uid) for uid in member_names if str(uid) in data.get("users", {})}
    users = data.get("users", {})
    display = {uid: str(member_names[uid])[:64] for uid in member_uids}
    games = _game_records(data, member_uids)
    result = {"action": action,
              "note": "Sólo tiempo ya guardado; sesiones en curso pueden faltar."}

    if action == "list_games":
        rows = [{"game": name[:80], "minutes": round(sum(_minutes(record)
                 for record in records.values()), 1)}
                for name, records in games.items()]
        rows.sort(key=lambda row: row["minutes"], reverse=True)
        result["games"] = rows[:10] or "No hay juegos registrados todavía."
        return result

    if action == "game_detail":
        target = _resolve(game, list(games))
        records = games[target]
        players = sorted(
            [{"member": display[uid], "minutes": _minutes(record)}
             for uid, record in records.items()],
            key=lambda row: row["minutes"], reverse=True)
        today = (now or datetime.now()).date()
        series = []
        for index in range(14):
            key = (today - timedelta(days=13 - index)).isoformat()
            series.append({"date": key, "minutes": round(sum(
                _day_minutes(record, key) for record in records.values()), 1)})
        result.update(game=target,
                      players=players[:8] or "Nadie jugó a ese juego todavía.",
                      days=series)
        return result

    if action == "user_detail":
        pool = {display[uid]: uid for uid in member_uids}
        chosen = _resolve(user, list(pool))
        uid = pool[chosen]
        record = users.get(uid, {})
        messages = record.get("messages", {})
        voice = record.get("voice", {})
        reactions = record.get("reactions", {})
        stickers = record.get("stickers", {})
        connections = record.get("daily_connections", {})
        personal = connections.get("personal_record", {}) if isinstance(connections, dict) else {}
        game_rows = [{"game": name[:80], "minutes": _minutes(game_record)}
                     for name, game_record in record.get("games", {}).items()
                     if isinstance(name, str) and isinstance(game_record, dict)]
        game_rows.sort(key=lambda row: row["minutes"], reverse=True)
        return {**result,
                "member": chosen,
                "games": game_rows[:8] or "Sin juegos registrados.",
                "voice_minutes": _minutes(voice),
                "voice_connections": _counter(voice.get("count")) if isinstance(voice, dict) else 0,
                "messages_lifetime": _counter(messages.get("count")) if isinstance(messages, dict) else 0,
                "reactions_total": _counter(reactions.get("total")) if isinstance(reactions, dict) else 0,
                "stickers_total": _counter(stickers.get("total")) if isinstance(stickers, dict) else 0,
                "connections_total": _counter(connections.get("total")) if isinstance(connections, dict) else 0,
                "connections_record": {"count": _counter(personal.get("count")),
                                       "date": str(personal.get("date"))[:10]} if isinstance(personal, dict) else {}}

    if action == "day_summary":
        rows = []
        voice_rows = []
        for uid in member_uids:
            user = users.get(uid, {})
            connections = user.get("daily_connections", {})
            if isinstance(connections, dict):
                by_date = connections.get("by_date", {})
                count = by_date.get(day) if isinstance(by_date, dict) else None
                if isinstance(count, (int, float)) and count > 0:
                    voice_rows.append({"member": display[uid], "connections": round(count)})
            for name, game_record in (user.get("games", {}) if isinstance(user.get("games"), dict) else {}).items():
                if not isinstance(name, str) or not isinstance(game_record, dict):
                    continue
                daily = game_record.get("daily_minutes", {})
                minutes = daily.get(day) if isinstance(daily, dict) else None
                if isinstance(minutes, (int, float)) and minutes > 0:
                    rows.append({"member": display[uid], "game": name[:80], "minutes": round(minutes, 1)})
            voice = user.get("voice", {})
            if isinstance(voice, dict):
                voice_daily = voice.get("daily_minutes", {})
                voice_minutes = voice_daily.get(day) if isinstance(voice_daily, dict) else None
                if isinstance(voice_minutes, (int, float)) and voice_minutes > 0:
                    rows.append({"member": display[uid], "game": "(voz)", "minutes": round(voice_minutes, 1)})
        rows.sort(key=lambda row: row["minutes"], reverse=True)
        return {**result,
                "date": day,
                "activity": rows[:12] or "Nada registrado ese día.",
                "connections": sorted(voice_rows, key=lambda row: row["connections"], reverse=True)[:8]}

    raise ValueError
