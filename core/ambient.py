"""Compact ambient digest of the channel's recent conversation.

The owner already pages Discord (bounded fetch) and hands this module raw
message-like objects or dict clones; there is no Discord I/O here. The digest
gives the model the channel's flowing context — a topic prelude plus the last
readable lines — so every turn keeps the channel's thread without keyword
scans. Like every private read, the digest is context only: it must never mix
with web search results in the same answer.
"""

import re

from core.assistant_secrets import SECRET_PATTERN
from core.assistant_history import MAX_AGE_DAYS, MAX_EXCERPT, fold
from core.assistant_trace import event

DEFAULT_MAX_CHARS = 2600
MIN_MAX_CHARS = 600
HARD_MAX_CHARS = 8000
DEFAULT_WINDOW = 100
MAX_WINDOW = 500
MAX_INPUT = 2000
MAX_NAME = 64
MAX_TOPICS = 14

_URL = re.compile(r"https?://[^\s<>]+")
_AT_EVERYONE = re.compile(r"@everyone|@here", re.I)
_MENTION = re.compile(r"<@!?(\d{1,20})>")
_LEFTOVER_TAG = re.compile(r"<[@#!&:]\d{1,20}>")
_TOKEN = re.compile(r"[a-z0-9]{3,}")

# Same stopword list as the keyword scanner: ambient topics use the same
# notion of a significant word, so both tools agree on what matters.
_STOPWORDS = {
    "que", "como", "para", "una", "uno", "unos", "unas", "los", "las", "del", "con", "por", "pero",
    "este", "esta", "esto", "estos", "estas", "ese", "esa", "eso", "cuando", "donde", "quien",
    "porque", "sobre", "entre", "hacia", "desde", "hasta", "tambien", "mas", "nos", "les",
    "hay", "fue", "vos", "usted", "che", "bueno", "dale",
}


def _get(obj, name):
    """Read one field from a discord-like object or dict clone, always safe.

    Never returns None (empty string instead) but the value itself is NOT
    validated here: callers keep their isinstance checks before using it.
    """
    if isinstance(obj, dict):
        value = obj.get(name)
    else:
        value = getattr(obj, name, None)
    return "" if value is None else value


def _names_map(discord_messages):
    """Visible names of mentioned users, harvested from the given rows only.

    Only list/tuple `mentions` count; a mock auto-attribute is not a list, so a
    bare MagicMock never fabricates entries. Works with dicts too.
    """
    names = {}
    for message in list(discord_messages)[:MAX_INPUT]:
        mentions = _get(message, "mentions")
        if not isinstance(mentions, (list, tuple)):
            continue
        for who in list(mentions)[:50]:
            if isinstance(who, dict):
                uid, name = who.get("id"), who.get("display_name")
            else:
                uid, name = getattr(who, "id", None), getattr(who, "display_name", None)
            if not isinstance(name, str) or not name.strip():
                continue
            if isinstance(uid, (int, str)) and str(uid).isdigit():
                names[str(uid)] = name.strip()[:MAX_NAME]
    return names


def _clean_text(content):
    """One bounded line: no secrets, no links, no embedded newlines."""
    text = SECRET_PATTERN.sub("[clave omitida]", content)
    text = _URL.sub("[enlace omitido]", text)
    text = re.sub(r"\s*\n\s*", " / ", text.replace("\r", ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_EXCERPT]


def _too_old(when, now, max_age_days):
    """Optional age cut, only computable with two aware datetimes."""
    if not max_age_days or now is None:
        return False
    try:
        if getattr(when, "tzinfo", None) is None or getattr(now, "tzinfo", None) is None:
            return False
        return (now - when).total_seconds() / 86400 > max_age_days
    except TypeError:
        return False


def _row(message, names, now=None, max_age_days=None):
    """(when, date, author, text) or None; mirrors _row_from's strict filters."""
    author_obj = _get(message, "author")
    author = _get(author_obj, "display_name")
    if not isinstance(author, str) or not author.strip():
        return None
    if bool(_get(author_obj, "bot")):
        return None
    when = _get(message, "created_at")
    if not hasattr(when, "strftime"):
        return None
    content = _get(message, "content")
    content = content if isinstance(content, str) else ""
    if not content.strip() or fold(content).startswith("!"):  # commands add noise
        return None
    if _too_old(when, now, max_age_days):
        return None
    text = _clean_text(content)

    def _sub(match):
        name = names.get(match.group(1))
        return "@" + name if name else "[mención]"

    text = _MENTION.sub(_sub, text)
    text = _LEFTOVER_TAG.sub("[mención]", text)
    text = _AT_EVERYONE.sub("[mención]", text)
    reference = _get(message, "reference")
    reply_id = (reference.get("message_id") if isinstance(reference, dict)
                else getattr(reference, "message_id", None))
    if isinstance(reply_id, (int, str)) and str(reply_id).strip():
        text = "↩ " + text
    return when, when.strftime("%m-%d %H:%M"), author.strip()[:MAX_NAME], text


def _topics(rows):
    """Most repeated significant tokens, ties broken by first appearance."""
    counts, order = {}, {}
    for when, _date, _author, text in rows:
        for token in _TOKEN.findall(fold(text)):
            if token in _STOPWORDS:
                continue
            counts[token] = counts.get(token, 0) + 1
            if token not in order:
                order[token] = len(order)
    ranked = sorted((token for token in counts if not token.isdigit()),  # words, not counts/numerals
                    key=lambda token: (-counts[token], order[token]))
    return ranked[:MAX_TOPICS]


def ambient(discord_messages, now=None, max_chars=DEFAULT_MAX_CHARS, window=DEFAULT_WINDOW,
            max_age_days=None):
    """Plain-text channel context: topic prelude + last N readable lines.

    `discord_messages` is a pre-fetched, already-bounded list (raw discord.py
    messages or dict clones); order does not matter — rows are sorted by their
    own created_at. Returns "" when there is nothing readable, and always
    stays within `max_chars` (clamped to [600, 8000]); `window` is clamped to
    [1, 500]. Fails closed: any surprise yields "" and never raises.
    """
    if not isinstance(discord_messages, (list, tuple)) or not discord_messages:
        return ""
    try:
        max_chars = max(MIN_MAX_CHARS, min(int(max_chars), HARD_MAX_CHARS))
        window = max(1, min(int(window), MAX_WINDOW))
        names = _names_map(discord_messages)
        rows = []
        for message in list(discord_messages)[:MAX_INPUT]:
            row = _row(message, names, now, max_age_days)
            if row:
                rows.append(row)
        if not rows:
            return ""
        rows.sort(key=lambda row: row[0])  # chronological, regardless of input order
        rows = rows[-window:]              # keep the newest tail of the window
        topics = _topics(rows)
        if topics:
            prelude = "Preludio del canal: temas que más se repiten — " + ", ".join(topics)
        else:
            prelude = "Preludio del canal: charla general sin temas dominantes en la ventana."
        lines = [f"{date} {author}: {text}" for _when, date, author, text in rows]
        while lines:
            block = (prelude + "\nÚltimos %d mensajes legibles:\n" % len(lines)
                     + "\n".join(lines))
            if len(block) <= max_chars:
                break
            lines.pop(0)  # tail truncation: the oldest lines go first
        else:
            return ""
        if not lines:
            return ""
        event('ambient', status='ok', rows=len(lines), chars=len(block))
        return block[:max_chars]
    except Exception as exc:  # noqa: BLE001 - ambient context must never break an answer
        event('ambient', status='error', error_type=type(exc).__name__)
        return ""
