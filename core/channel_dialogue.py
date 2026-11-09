"""Scoped, ephemeral channel dialogue. Discord objects are never retained or fetched.

Hard bounds: 100 turns, three days, 800 text characters per turn, 500 per reply
excerpt, 80 per author, and 7,000 per render. Caller limits can lower these.
Rendered as a readable Argentina-time chat: recent turns first, then whatever
older context fits without half-sentences. Wall-clock expiry never goes
backwards, even if the supplied clock does.
"""

import json
import math
import re
import time
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import SimpleNamespace

from core.assistant_secrets import SECRET_PATTERN
from core.assistant_scope import channel_in_scope, public_thread
from core.assistant_privacy import scrub_private
from core.assistant_clock import argentina_now


_URL = re.compile(r"(?:[a-z][a-z0-9+.-]{0,20}://|www\.|discord\.gg/|discord(?:app)?\.com/invite/)\S+", re.I)
_USER_MENTION = re.compile(r"<@!?(\d+)>|(?<![\w@])@(\d+)\b")
_OTHER_MENTION = re.compile(r"<@&\d+>|<#\d+>|@(?:everyone|here)\b", re.I)
_SNOWFLAKE = re.compile(r"(?<!\d)\d{15,22}(?!\d)")
_RECENT = "DIÁLOGO RECIENTE (prioridad)\n"
_BACKGROUND = "ANTECEDENTES (menor prioridad)\n"
_EMPTY_QUESTION = "Te llaman para sumarte a la conversación actual."
RECENT_SECONDS = 3600
# Discord timestamps and the local clock can disagree by fractions of a second.
# Clamping a live message to "now" made it sort *before* the warm-start rows
# observed microseconds later, dropping the newest turn from the prompt.
FUTURE_TOLERANCE_SECONDS = 60


def _limit(value, default, maximum, minimum=0):
    try:
        return max(minimum, min(maximum, int(value)))
    except (ValueError, TypeError, OverflowError):
        return default


def _id(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        number = int(value)
        return number if number > 0 else None
    except (ValueError, TypeError):
        return None


def _plain(value):
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFC", value[:16000])
    # Flatten every field, not just content: names cannot introduce new headers.
    value = "".join(" " if char.isspace() else char
                    for char in value if not unicodedata.category(char).startswith("C")
                    or char.isspace())
    return " ".join(value.split())


def _clean(value, mentions=None, limit=800):
    value = SECRET_PATTERN.sub("[secreto]", scrub_private(_plain(value))).replace("[secreto omitido]", "[secreto]")
    value = _URL.sub("[enlace]", value)
    value = _OTHER_MENTION.sub("[mención]", value)
    value = _USER_MENTION.sub(
        lambda match: (mentions or {}).get(_id(match[1] or match[2]), "[mención]"), value)
    value = _SNOWFLAKE.sub("[id]", value)
    return value.replace("@", "")[:limit]


def _mentions(message):
    result = {}
    # discord.py supplies a list. Do not consume arbitrary/lazy iterators (no I/O).
    users = getattr(message, "mentions", ())
    if not isinstance(users, (list, tuple)):
        return result
    for user in users[:100]:
        user_id = _id(getattr(user, "id", None))
        if user_id is not None:
            result[user_id] = _clean(getattr(user, "display_name", ""), limit=80) or "Persona"
    return result


def _quote(text):
    return json.dumps(text, ensure_ascii=False)


@dataclass(frozen=True)
class _Turn:
    message_id: int
    created_at: float
    role: str
    author: str
    text: str
    reply: "_Turn | None" = None
    channel_id: int = 0
    thread: str = ""


class ChannelDialogue:
    def __init__(self, guild_id, channel_id, bot_id=None, max_messages=100,
                 max_age_seconds=259200, clock=time.time):
        self.guild_id = _id(guild_id)
        self.channel_id = _id(channel_id)
        self.bot_id = _id(bot_id)
        self.max_messages = _limit(max_messages, 100, 100)
        self.max_age_seconds = _limit(max_age_seconds, 259200, 259200)
        self.clock = clock
        self._last_now = float("-inf")
        self._rows = {}
        # Last 100 deleted/rejected IDs prevent stale resolved copies resurfacing.
        self._blocked = OrderedDict()

    def _now(self):
        now = float(self.clock())
        if not math.isfinite(now):
            raise ValueError("El reloj debe devolver un timestamp finito.")
        self._last_now = max(self._last_now, now)
        return self._last_now

    def _in_scope(self, message):
        guild = _id(getattr(getattr(message, "guild", None), "id", None))
        channel_object = getattr(message, "channel", None)
        channel = _id(getattr(channel_object, "id", None))
        # Also accept explicit scope fields in lightweight message adapters.
        guild_field = _id(getattr(message, "guild_id", None))
        channel_field = _id(getattr(message, "channel_id", None))
        return (self.guild_id is not None and self.channel_id is not None
                and (guild or guild_field) == self.guild_id
                and (channel_in_scope(channel_object, self.channel_id)
                     or (channel is None and channel_field == self.channel_id))
                and guild_field in (None, self.guild_id)
                and channel_field in (None, channel or self.channel_id))

    def _timestamp(self, message, now):
        created = getattr(message, "created_at", None)
        if created is None:
            return now
        if not isinstance(created, datetime):
            return None
        try:
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            timestamp = created.timestamp()
            # Future-dated input must not retain content indefinitely, but a
            # small skew is normal and must not reorder the dialogue.
            return (timestamp if timestamp <= now + FUTURE_TOLERANCE_SECONDS
                    else now) if math.isfinite(timestamp) else None
        except (ValueError, OverflowError, OSError):
            return None

    def _clone(self, message, now, text_limit=800, observing=False):
        if not self._in_scope(message):
            return None
        message_id = _id(getattr(message, "id", None))
        if (message_id is None or self._blocked.get(message_id) is True
                or (message_id in self._blocked and not observing)):
            return None
        author = getattr(message, "author", None)
        own = self.bot_id is not None and _id(getattr(author, "id", None)) == self.bot_id
        if author is None or (getattr(author, "bot", False) and not own):
            return None
        raw = _plain(getattr(message, "content", ""))
        if raw.startswith("!") and raw.split(maxsplit=1)[0].casefold() not in ("!boton", "!botón"):
            return None
        created = self._timestamp(message, now)
        if created is None or now - created >= self.max_age_seconds:
            return None
        text = _clean(raw, _mentions(message), text_limit)
        if not text:
            return None
        name = _clean(getattr(author, "display_name", ""), limit=80)
        channel = getattr(message, "channel", None)
        return _Turn(message_id, created, "asistente" if own else "humano",
                     name or ("Botón" if own else "Persona"), text,
                     channel_id=_id(getattr(channel, "id", None)) or self.channel_id,
                     thread=_clean(getattr(channel, "name", ""), limit=80)
                     if public_thread(channel, self.channel_id) else "")

    def _prune(self, now):
        for key, row in list(self._rows.items()):
            if now - row.created_at >= self.max_age_seconds:
                del self._rows[key]
            elif row.reply and now - row.reply.created_at >= self.max_age_seconds:
                self._rows[key] = replace(row, reply=None)

    @staticmethod
    def _reply_copy(row):
        return replace(row, text=row.text[:500], reply=None)

    def _resolve_reply(self, message, now):
        if not self._in_scope(message):
            return None
        reference = getattr(message, "reference", None)
        if reference is None:
            return None
        origin_channel = _id(getattr(getattr(message, "channel", None), "id", None)) or self.channel_id
        for field, expected in (("guild_id", self.guild_id), ("channel_id", origin_channel)):
            value = getattr(reference, field, None)
            if value is not None and _id(value) != expected:
                return None
        parent_id = _id(getattr(reference, "message_id", None))
        if parent_id in self._blocked:
            return None
        if parent_id in self._rows:
            parent = self._rows[parent_id]
            return self._reply_copy(parent) if parent.channel_id == origin_channel else None
        for field in ("resolved", "cached_message"):
            parent = self._clone(getattr(reference, field, None), now, text_limit=500)
            if (parent and parent.channel_id == origin_channel
                    and (parent_id is None or parent.message_id == parent_id)):
                return parent
        return None

    def observe(self, message, *, historical=False) -> bool:
        """Upsert one accepted message; return False for rejected or evicted input."""
        now = self._now()
        self._prune(now)
        if historical:
            if not self._in_scope(message):
                return False
            mid = _id(getattr(message, "id", None))
            if mid in self._blocked:
                return False
            if mid in self._rows:
                return True  # A newer gateway event wins over a stale REST snapshot.
        row = self._clone(message, now, observing=not historical)
        if row is None:
            # An edit into an administrative command must not preserve its old text.
            if not historical and self._in_scope(message):
                message_id = _id(getattr(message, "id", None))
                if message_id is not None:
                    self._discard(message_id)
                    self._block_id(message_id, deleted=self._blocked.get(message_id, False))
            return False
        self._blocked.pop(row.message_id, None)
        for key, previous in list(self._rows.items()):
            if previous.reply and previous.reply.message_id == row.message_id:
                self._rows[key] = replace(previous, reply=self._reply_copy(row))
        self._rows[row.message_id] = replace(row, reply=self._resolve_reply(message, now))
        ordered = sorted(self._rows.values(), key=lambda turn: (turn.created_at, turn.message_id))
        self._rows = {turn.message_id: turn for turn in ordered[-self.max_messages:]} if self.max_messages else {}
        return row.message_id in self._rows

    def _discard(self, message_id):
        self._rows.pop(message_id, None)
        for key, row in list(self._rows.items()):
            if row.reply and row.reply.message_id == message_id:
                self._rows[key] = replace(row, reply=None)

    def remove(self, message_id) -> None:
        """Remove a turn and any copied reply excerpts of that turn."""
        message_id = _id(message_id)
        if message_id is None:
            return
        self._discard(message_id)
        self._block_id(message_id, deleted=True)

    def _block_id(self, message_id, deleted):
        self._blocked[message_id] = deleted
        self._blocked.move_to_end(message_id)
        while len(self._blocked) > 100:
            self._blocked.popitem(last=False)

    def clear(self) -> None:
        self._rows.clear()
        self._blocked.clear()

    def contains(self, message_id) -> bool:
        self._prune(self._now())
        return _id(message_id) in self._rows

    def edit(self, message_id, content, mentions=()) -> bool:
        """Apply a partial raw gateway edit without fetching or losing author/role."""
        self._prune(self._now())
        mid = _id(message_id)
        if mid is None or self._blocked.get(mid) is True or not isinstance(content, str):
            return False
        row = self._rows.get(mid)
        if row is None:
            row = next((r.reply for r in self._rows.values() if r.reply and r.reply.message_id == mid), None)
        if row is None:
            return False
        raw = _plain(content)
        if not raw or (raw.startswith('!') and raw.split(maxsplit=1)[0].casefold() not in ('!boton', '!botón')):
            self._discard(mid)
            self._block_id(mid, deleted=False)
            return False
        people = []
        for who in mentions if isinstance(mentions, (list, tuple)) else ():
            if isinstance(who, dict):
                member = who.get('member') if isinstance(who.get('member'), dict) else {}
                people.append(SimpleNamespace(id=who.get('id'), display_name=
                    member.get('nick') or who.get('global_name') or who.get('username') or 'Persona'))
        updated = replace(row, text=_clean(raw, _mentions(SimpleNamespace(mentions=people)), 800))
        if mid in self._rows:
            self._rows[mid] = updated
        for key, child in list(self._rows.items()):
            if child.reply and child.reply.message_id == mid:
                self._rows[key] = replace(child, reply=self._reply_copy(updated))
        return True

    def _parent(self, row):
        if not row.reply:
            return None
        return self._reply_copy(self._rows.get(row.reply.message_id, row.reply))

    @staticmethod
    def _name(row):
        # The bot is one participant, not the account name it happens to use.
        return "Botón" if row.role == "asistente" else row.author

    @staticmethod
    def _stamp(row, now):
        """Short Argentina-time stamp: only the date when it is not today."""
        moment = argentina_now(datetime.fromtimestamp(row.created_at, timezone.utc))
        today = argentina_now(datetime.fromtimestamp(now, timezone.utc)).date()
        return moment.strftime("%H:%M") if moment.date() == today else moment.strftime("%d/%m %H:%M")

    def _block(self, row, now, text_limit=800, reply_limit=200, include_reply=True):
        name = self._name(row)
        stamp = self._stamp(row, now)
        text = _quote(row.text[:text_limit])
        if include_reply and row.reply:
            parent = self._parent(row) or row.reply
            line = (f"{stamp} {name} (responde a {self._name(parent)}: "
                    f"{_quote(parent.text[:reply_limit])}): {text}")
        else:
            line = f"{stamp} {name}: {text}"
        if row.thread:
            line += " [hilo: " + _quote(row.thread) + "]"
        return line

    def _pack(self, rows, budget, now, min_text=120, include_reply=True):
        """Keep a chronological suffix and spend spare space newest-first.

        A row is only included if it fits with at least ``min_text`` characters:
        half-sentences confuse a small model more than an absent old turn.
        """
        selected, used = [], 0
        for row in reversed(rows):
            text = self._block(row, now, min_text, 80 if include_reply else 0, include_reply)
            cost = len(text) + bool(selected)
            if used + cost > budget:
                break
            selected.append([row, min_text, 80 if include_reply else 0, text])
            used += cost
        for block in selected:
            row = block[0]
            fields = ((1, 800),) + (((2, 200),) if include_reply else ())
            for field, maximum in fields:
                low, high = block[field], maximum
                while low < high:
                    middle = (low + high + 1) // 2
                    caps = [block[1], block[2]]
                    caps[field - 1] = middle
                    candidate = self._block(row, now, caps[0], caps[1], include_reply)
                    if used - len(block[3]) + len(candidate) <= budget:
                        low = middle
                    else:
                        high = middle - 1
                block[field] = low
                candidate = self._block(row, now, block[1], block[2], include_reply)
                used += len(candidate) - len(block[3])
                block[3] = candidate
        return "\n".join(block[3] for block in reversed(selected))

    def render(self, current_message=None, max_chars=7000, recent_limit=24) -> str:
        """Conversation data as a readable chat, oldest first.

        The current invocation is omitted; its optional parent is quoted by
        ``invocation()``. Replies are shown once, inline and before the reply
        text, so authorship and thread direction cannot be read backwards.
        """
        now = self._now()
        self._prune(now)
        budget = _limit(max_chars, 7000, 7000)
        recent_limit = _limit(recent_limit, 24, 24, minimum=1)
        if not budget or (current_message is not None and not self._in_scope(current_message)):
            return ""
        rows = list(self._rows.values())
        if current_message is not None:
            current_id = _id(getattr(current_message, "id", None))
            created = self._timestamp(current_message, now)
            rows = [row for row in rows if row.message_id != current_id and (
                created is None or current_id is None
                or (row.created_at, row.message_id) < (created, current_id))]
        if not rows:
            return ""
        # Message count alone is not recency: a quiet channel can keep yesterday's
        # topic inside its last 24 turns. Mark that material as background.
        at = self._timestamp(current_message, now) if current_message is not None else now
        at = now if at is None else at
        recent = [row for row in rows[-recent_limit:] if at - row.created_at <= RECENT_SECONDS]
        recent_ids = {row.message_id for row in recent}
        older = [row for row in rows if row.message_id not in recent_ids]
        # Recent turns get the budget first; old material only uses what is left.
        body = self._pack(recent, budget - len(_RECENT), now)
        remaining = budget - len(_RECENT) - len(body)
        background = ""
        if older and remaining > len(_BACKGROUND) + 2 + 160:
            background = self._pack(older[-8:], remaining - len(_BACKGROUND) - 2, now,
                                    min_text=160, include_reply=False)
        prefix = _BACKGROUND + background + "\n\n" if background else ""
        if not recent:
            return (prefix + _RECENT + "No hay mensajes de la última hora; los antecedentes no confirman estados actuales.")[:budget]
        if body:
            return prefix + _RECENT + body
        # Tiny caller budgets still get the newest text, not an old header fragment.
        row = recent[-1]
        return (f"{self._name(row)}: " + row.text)[:budget]

    def invocation(self, message, question) -> str:
        """Sanitized current command as the last line of the same chat."""
        now = self._now()
        self._prune(now)
        if not self._in_scope(message):
            return ""
        author = _clean(getattr(getattr(message, "author", None), "display_name", ""), limit=80) or "Persona"
        text = _clean(question, _mentions(message), limit=4000) or _EMPTY_QUESTION
        created = self._timestamp(message, now)
        stamp = self._stamp(_Turn(0, now if created is None else created, "humano", author, text), now)
        parent = self._resolve_reply(message, now)
        if parent:
            name = "Botón" if parent.role == "asistente" else parent.author
            line = f"{stamp} {author} (responde a {name}: {_quote(parent.text[:200])}): {text}"
        else:
            line = f"{stamp} {author}: {text}"
        channel = getattr(message, "channel", None)
        if public_thread(channel, self.channel_id):
            line += " [hilo: " + _clean(getattr(channel, "name", ""), limit=80) + "]"
        return line

    def reply_is_own(self, message) -> bool:
        """A scoped cached/resolved reply is an explicit call, without network I/O."""
        now = self._now()
        self._prune(now)
        parent = self._resolve_reply(message, now)
        return parent is not None and parent.role == "asistente"
