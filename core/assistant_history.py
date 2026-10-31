"""Bounded read-only scanner of the assistant's own channel history.

Discord already stores the channel's past; this tool only pages through a
fixed recent window and returns short, sanitized dated rows. Free-text search
terms may be refined by the caller, but never change the scan or output caps.
"""

import re
import unicodedata
from datetime import datetime, timedelta, timezone

from core.assistant_trace import event
from core.assistant_privacy import MAX_PRIVATE_CHARS, scrub_private

MAX_MESSAGES = 1000
MAX_ROWS = 12
MAX_AGE_DAYS = 30
MAX_EXCERPT = 160
MAX_QUESTION_CHARS = 800

_STOPWORDS = {
    "que", "como", "para", "una", "uno", "unos", "unas", "los", "las", "del", "con", "por", "pero",
    "este", "esta", "esto", "estos", "estas", "ese", "esa", "eso", "cuando", "donde", "quien",
    "porque", "sobre", "entre", "hacia", "desde", "hasta", "tambien", "mas", "nos", "les",
    "hay", "fue", "vos", "usted", "che", "bueno", "dale",
}

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_QUERY_SEPARATOR = re.compile(r"[,;|\n]|\bOR\b", re.I)
_URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
_MENTION = re.compile(r"<@!?\d+>|<@&\d+>|<#\d+>|@[^\s<>@]+", re.I)
_DISCORD_TOKEN = re.compile(
    r"(?<![\w-])(?:[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6}\."
    r"[A-Za-z0-9_-]{20,}|mfa\.[A-Za-z0-9_-]{20,})(?![\w-])"
)
_API_KEY = re.compile(
    r"\b(?:sk-|gsk_|gh[pousr]_|github_pat_|xox[baprs]-)[A-Za-z0-9_-]{12,}"
)
_CREDENTIAL = re.compile(
    r"\b((?:api[_-]?key|access[_-]?token|discord[_-]?token|bot[_-]?token|"
    r"token|secret|password|authorization)[\"']?\s*[:=]\s*)"
    r"(?:(?:Bearer|Basic)\s+)?(?:[\"'][^\"'\r\n]*[\"']|[^\s,;]+)", re.I
)


def fold(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower())
                   if not unicodedata.combining(c))


def keywords(question):
    """Bounded significant words from a free-text query, with OR semantics."""
    text = fold(str(question or ""))[:MAX_QUESTION_CHARS]
    tokens = []
    for token in _TOKEN.findall(text):
        if len(token) < 3 or token in _STOPWORDS or token == "or":
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens[:6]


def _sanitize(text):
    # Redact before truncating: cutting a credential first can expose its prefix.
    text = str(text)
    if len(text) > MAX_PRIVATE_CHARS:
        return scrub_private(text)
    text = _DISCORD_TOKEN.sub("[secreto]", text)
    text = _API_KEY.sub("[secreto]", text)
    text = _CREDENTIAL.sub(lambda match: match[1] + "[secreto]", text)
    text = scrub_private(text).replace('[secreto omitido]', '[secreto]')
    text = _URL.sub("[enlace]", text)
    text = _MENTION.sub("[mención]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _excerpt(text):
    return _sanitize(text)[:MAX_EXCERPT]


def _row_from(message):
    """Only the fields that may leave the bot; no IDs, no attachments, no metadata."""
    if getattr(getattr(message, "author", None), "bot", False):
        return None
    author = getattr(getattr(message, "author", None), "display_name", "")
    if not isinstance(author, str) or not author or author.strip() == "":
        return None
    when = getattr(message, "created_at", None)
    if when is None:
        return None
    content = getattr(message, "content", "")
    if not isinstance(content, str) or not content.strip():
        return None
    if fold(content).lstrip().startswith("!"):  # commands add noise, not context
        return None
    return {"fecha": when.strftime("%Y-%m-%d %H:%M"), "autor": _sanitize(author)[:64],
             "texto": _excerpt(content)}


def _normalized_words(text):
    return _TOKEN.findall(fold(text))


def _score(author, text, tokens, phrases):
    fields = [_normalized_words(_sanitize(value)) for value in (author, text)]
    words = {word for field in fields for word in field}
    score = sum(token in words for token in tokens)
    # Pad the normalized phrase to preserve word boundaries (lol != lola).
    for phrase in phrases:
        if any(f" {phrase} " in f" {' '.join(field)} " for field in fields):
            score += len(tokens) + 1
    return score


def _utc(when):
    if not isinstance(when, datetime):
        return None
    if when.tzinfo is None:
        return when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc)


async def scan_history(channel, question, now=None, limit=None):
    """Search content and names with OR keywords and a full-phrase score bonus.

    Commas, semicolons, pipes, newlines and OR separate alternative phrases.
    ``truncated`` flags a scan/output cap or an interrupted scan; ``scan_error``
    is null on success, or a safe error code (never Discord's raw error text).
    ``min_date``/``max_date`` cover inspected messages within the time window,
    not just matches. An empty successful result is distinct from denied access.
    """
    tokens = keywords(question)
    result = {"scanned": 0, "window_days": MAX_AGE_DAYS,
              "matches": [], "note": "Sólo el canal del asistente, ventana fija y reciente.",
              "truncated": False, "scan_error": None, "min_date": None, "max_date": None}
    if not tokens:
        return result
    if not callable(getattr(channel, "history", None)):
        result["scan_error"] = "history_unavailable"
        return result
    try:
        scan_limit = MAX_MESSAGES if limit is None else max(0, min(MAX_MESSAGES, int(limit)))
    except (TypeError, ValueError, OverflowError):
        scan_limit = MAX_MESSAGES
    if not scan_limit:
        result["truncated"] = True
        return result
    phrases = []
    for query in _QUERY_SEPARATOR.split(str(question or "")[:MAX_QUESTION_CHARS]):
        words = _normalized_words(query)
        if len(words) > 1 and any(token in words for token in tokens):
            phrases.append(" ".join(words))
    cutoff = (_utc(now) or datetime.now(timezone.utc)) - timedelta(days=MAX_AGE_DAYS)
    rows = []
    try:
        iterator = channel.history(limit=scan_limit, oldest_first=False).__aiter__()
        # Some adapters/fakes ignore history(limit=...). Enforce it here too.
        while result["scanned"] < scan_limit:
            try:
                message = await iterator.__anext__()
            except StopAsyncIteration:
                break
            result["scanned"] += 1
            when = _utc(getattr(message, "created_at", None))
            if when is None:
                continue
            if when < cutoff:
                break  # Discord history is newest-first.
            date = when.isoformat()
            result["min_date"] = min(result["min_date"] or date, date)
            result["max_date"] = max(result["max_date"] or date, date)
            row = _row_from(message)
            if not row:
                continue
            # Match sanitized fields, not credentials, mention IDs or link targets.
            score = _score(message.author.display_name, message.content, tokens, phrases)
            if score:
                rows.append((score, row))
        else:
            result["truncated"] = True
    except Exception as exc:  # noqa: BLE001 - arbitrary discord errors must not break answers
        denied = isinstance(exc, PermissionError) or getattr(exc, "status", None) in (401, 403)
        denied = denied or type(exc).__name__ in {"Forbidden", "Unauthorized"}
        result["scan_error"] = "permission_denied" if denied else "discord_error"
        result["truncated"] = True
        event('history_scan', status='error', error_type=type(exc).__name__)
    scored = sorted(rows, key=lambda row: row[0], reverse=True)
    result["matches"] = [row for _, row in scored[:MAX_ROWS]]
    result["truncated"] = result["truncated"] or len(scored) > MAX_ROWS
    if result["scan_error"] is None:
        event('history_scan', status='ok', scanned=result["scanned"], matches=len(result["matches"]))
    return result
