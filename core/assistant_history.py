"""Bounded read-only scanner of the assistant's own channel history.

Discord already stores the channel's past; this tool only pages through a
fixed recent window, matches the user's own words, and returns short dated
rows. The model never chooses the window, the keywords or the row count.
"""

import re
import unicodedata

from core.assistant_trace import event

MAX_MESSAGES = 500
MAX_ROWS = 8
MAX_AGE_DAYS = 14
MAX_EXCERPT = 160
MAX_QUESTION_CHARS = 800

_STOPWORDS = {
    "que", "como", "para", "una", "uno", "unos", "unas", "los", "las", "del", "con", "por", "pero",
    "este", "esta", "esto", "estos", "estas", "ese", "esa", "eso", "cuando", "donde", "quien",
    "porque", "sobre", "entre", "hacia", "desde", "hasta", "tambien", "mas", "nos", "les",
    "hay", "fue", "vos", "usted", "che", "bueno", "dale",
}

_TOKEN = re.compile(r"[a-z0-9]{3,}", re.I)


def fold(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower())
                   if not unicodedata.combining(c))


def keywords(question):
    """The user's own significant words, never model-generated queries."""
    text = fold(str(question or ""))[:MAX_QUESTION_CHARS]
    tokens = []
    for token in _TOKEN.findall(text):
        if token in _STOPWORDS:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens[:6]


def _excerpt(text):
    text = re.sub(r"https?://\S+", "[enlace]", str(text))
    text = re.sub(r"@everyone|@here", "[mención]", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_EXCERPT]


def _row_from(message):
    """Only the fields that may leave the bot; no IDs, no attachments, no metadata."""
    author = getattr(getattr(message, "author", None), "display_name", "")
    if not isinstance(author, str) or not author or author.strip() == "":
        return None
    when = getattr(message, "created_at", None)
    if when is None:
        return None
    content = message.content if isinstance(message.content, str) else ""
    if fold(content).startswith("!"):  # commands add noise, not context
        return None
    return {"fecha": when.strftime("%Y-%m-%d %H:%M"), "autor": author[:64],
            "texto": _excerpt(content)}


async def scan_history(channel, question, now=None, limit=None):
    """Page a bounded recent window and match any of the question's keywords.

    Fails open with an empty result on any Discord error: the tool must never
    break an answer, the same contract as the web search path.
    """
    tokens = keywords(question)
    result = {"scanned": 0, "window_days": MAX_AGE_DAYS,
              "matches": [], "note": "Sólo el canal del asistente, ventana fija y reciente."}
    if not tokens or not hasattr(channel, "history"):
        return result
    try:
        limit = limit or MAX_MESSAGES
        rows = []
        iterator = channel.history(limit=limit, oldest_first=False)
        async for message in iterator:
            result["scanned"] += 1
            if now is not None:
                when = getattr(message, "created_at", None)
                if when is not None and getattr(when, "tzinfo", None) is not None:
                    age_days = (now - when).total_seconds() / 86400
                    if age_days > MAX_AGE_DAYS:
                        break  # history is newest-first; older rows are out of window
                else:
                    break
            if getattr(getattr(message, "author", None), "bot", False):
                continue
            text = message.content if isinstance(message.content, str) else ""
            if not text.strip():
                continue
            folded = fold(text)
            score = sum(1 for token in tokens if token in folded)
            if not score:
                continue
            row = _row_from(message)
            if row:
                rows.append((score, row))
    except Exception as exc:  # noqa: BLE001 - arbitrary discord errors must not break answers
        event('history_scan', status='error', error_type=type(exc).__name__)
        return result
    scored = sorted(rows, key=lambda row: row[0], reverse=True)
    result["matches"] = [row for _, row in scored[:MAX_ROWS]]
    event('history_scan', status='ok', scanned=result["scanned"], matches=len(result["matches"]))
    return result


def history_summary(scan):
    """Deterministic reply from the scan, used when a weak model echoes
    instructions instead of answering from the rows it was given."""
    matches = scan.get("matches", []) if isinstance(scan, dict) else []
    if not matches:
        return ("Busqué en el historial reciente del canal (14 días) y no encontré mensajes "
                "que coincidan. Probá nombrar de otra forma el tema que querés ubicar.")
    lines = [f"• {row['fecha']} — {row['autor']}: «{row['texto']}»" for row in matches[:5]]
    return ("Esto encontré en el historial reciente del canal:\n" + "\n".join(lines)
            + "\n(ventana de 14 días; no leo nada privado ni de otros servidores)")
