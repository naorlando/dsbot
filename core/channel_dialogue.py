"""Scoped, ephemeral channel dialogue. Discord objects are never retained or fetched.

Hard bounds: 100 turns, three days, 800 text characters per turn, 500 per reply
excerpt, 80 per author, and 7,000 per render. Caller limits can lower these.
Wall-clock expiry never goes backwards, even if the supplied clock does.
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


_URL = re.compile(r"(?:[a-z][a-z0-9+.-]{0,20}://|www\.|discord\.gg/|discord(?:app)?\.com/invite/)\S+", re.I)
_USER_MENTION = re.compile(r"<@!?(\d+)>|(?<![\w@])@(\d+)\b")
_OTHER_MENTION = re.compile(r"<@&\d+>|<#\d+>|@(?:everyone|here)\b", re.I)
_SNOWFLAKE = re.compile(r"(?<!\d)\d{15,22}(?!\d)")
_RECENT = "DIÁLOGO RECIENTE (prioridad)\n"
_BACKGROUND = "ANTECEDENTES (menor prioridad)\n"
_EMPTY_QUESTION = "Te llaman para sumarte a la conversación actual."
RECENT_SECONDS = 3600


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
    value = SECRET_PATTERN.sub("[secreto]", _plain(value))
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
        channel = _id(getattr(getattr(message, "channel", None), "id", None))
        # Also accept explicit scope fields in lightweight message adapters.
        guild_field = _id(getattr(message, "guild_id", None))
        channel_field = _id(getattr(message, "channel_id", None))
        return (self.guild_id is not None and self.channel_id is not None
                and (guild or guild_field) == self.guild_id
                and (channel or channel_field) == self.channel_id
                and guild_field in (None, self.guild_id)
                and channel_field in (None, self.channel_id))

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
            # Future-dated input must not retain content indefinitely.
            return min(timestamp, now) if math.isfinite(timestamp) else None
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
        return _Turn(message_id, created, "asistente" if own else "humano",
                     name or ("Botón" if own else "Persona"), text)

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
        for field, expected in (("guild_id", self.guild_id), ("channel_id", self.channel_id)):
            value = getattr(reference, field, None)
            if value is not None and _id(value) != expected:
                return None
        parent_id = _id(getattr(reference, "message_id", None))
        if parent_id in self._blocked:
            return None
        if parent_id in self._rows:
            return self._reply_copy(self._rows[parent_id])
        for field in ("resolved", "cached_message"):
            parent = self._clone(getattr(reference, field, None), now, text_limit=500)
            if parent and (parent_id is None or parent.message_id == parent_id):
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
    def _stamp(row):
        return datetime.fromtimestamp(row.created_at, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def _block(self, row, handles, text_limit=48, reply_limit=48, current=False):
        parent = row if current else self._parent(row)
        result = ""
        if not current:
            result = (f"{handles[row.message_id]} | {self._stamp(row)} | {row.role} | "
                      f"autor={_quote(row.author)}: {_quote(row.text[:text_limit])}")
        if parent:
            prefix = "Referencia del mensaje actual" if current else "  Responde"
            reply = (f"{prefix} a {handles[parent.message_id]} | {self._stamp(parent)} | {parent.role} | "
                     f"autor={_quote(parent.author)}: {_quote(parent.text[:reply_limit])}")
            result += ("\n" if result else "") + reply
        return result

    def _pack(self, blocks, handles, budget):
        """Keep a chronological suffix, then spend spare space newest-first."""
        selected = []
        used = 0
        for row, current in reversed(blocks):
            text = self._block(row, handles, current=current)
            cost = len(text) + bool(selected)
            if used + cost > budget:
                break
            selected.append([row, current, 48, 48, text])
            used += cost
        for block in selected:
            row, current = block[:2]
            for field, maximum in ((2, 800), (3, 500)):
                low, high = block[field], maximum
                while low < high:
                    middle = (low + high + 1) // 2
                    caps = [block[2], block[3]]
                    caps[field - 2] = middle
                    candidate = self._block(row, handles, *caps, current=current)
                    if used - len(block[4]) + len(candidate) <= budget:
                        low = middle
                    else:
                        high = middle - 1
                block[field] = low
                candidate = self._block(row, handles, block[2], block[3], current=current)
                used += len(candidate) - len(block[4])
                block[4] = candidate
        return "\n".join(block[4] for block in reversed(selected))

    def render(self, current_message=None, max_chars=7000, recent_limit=24) -> str:
        """Conversation data, oldest first; at most 25% of the budget is background.

        The current invocation is omitted. Only its scoped parent may be added.
        Replies never trigger a fetch, and local mN handles never expose IDs.
        """
        now = self._now()
        self._prune(now)
        budget = _limit(max_chars, 7000, 7000)
        recent_limit = _limit(recent_limit, 24, 24, minimum=1)
        if not budget or (current_message is not None and not self._in_scope(current_message)):
            return ""
        rows = list(self._rows.values())
        current_parent = None
        if current_message is not None:
            current_id = _id(getattr(current_message, "id", None))
            created = self._timestamp(current_message, now)
            rows = [row for row in rows if row.message_id != current_id and (
                created is None or current_id is None
                or (row.created_at, row.message_id) < (created, current_id))]
            current_parent = self._resolve_reply(current_message, now)
        if not rows and current_parent is None:
            return ""
        handles = {}
        for row in rows:
            handles.setdefault(row.message_id, f"m{len(handles) + 1}")
        for row in rows:
            parent = self._parent(row)
            if parent:
                handles.setdefault(parent.message_id, f"m{len(handles) + 1}")
        if current_parent:
            handles.setdefault(current_parent.message_id, f"m{len(handles) + 1}")
        # Message count alone is not recency: a quiet channel can keep yesterday's
        # topic inside its last 24 turns. Mark that material as background.
        at = self._timestamp(current_message, now) if current_message is not None else now
        at = now if at is None else at
        recent_rows = [row for row in rows[-recent_limit:] if at - row.created_at <= RECENT_SECONDS]
        recent_ids = {row.message_id for row in recent_rows}
        older = [(row, False) for row in rows if row.message_id not in recent_ids]
        recent = [(row, False) for row in recent_rows]
        if current_parent:
            # Shown once, as the explicit reference of the current invocation.
            keep = current_parent.message_id
            older = [item for item in older if item[0].message_id != keep]
            recent = [item for item in recent if item[0].message_id != keep]
            recent.append((current_parent, True))
        background_budget = budget // 4
        background = self._pack(older, handles, background_budget - len(_BACKGROUND) - 2)
        prefix = _BACKGROUND + background + "\n\n" if background else ""
        if not recent:
            return (prefix + _RECENT + "No hay mensajes de la última hora; los antecedentes no confirman estados actuales.")[:budget]
        body = self._pack(recent, handles, budget - len(prefix) - len(_RECENT))
        if body:
            return prefix + _RECENT + body
        # Tiny caller budgets still get the newest text, not an old header fragment.
        row, current = recent[-1]
        return (f"{row.role} {_quote(row.author)}: " + row.text)[:budget]

    def invocation(self, message, question) -> str:
        """Sanitized current command; preserve the assistant's 4,000-char input cap."""
        now = self._now()
        self._prune(now)
        if not self._in_scope(message):
            return ""
        author = _clean(getattr(getattr(message, "author", None), "display_name", ""), limit=80) or "Persona"
        text = _clean(question, _mentions(message), limit=4000) or _EMPTY_QUESTION
        lines = [f"Autor actual: {author}"]
        parent = self._resolve_reply(message, now)
        if parent:
            name = "Botón" if parent.role == "asistente" else parent.author
            lines.append(f"Responde a {name}: {parent.text}")
        lines.append(f"Mensaje actual: {text}")
        return "\n".join(lines)

    def reply_is_own(self, message) -> bool:
        """A scoped cached/resolved reply is an explicit call, without network I/O."""
        now = self._now()
        self._prune(now)
        parent = self._resolve_reply(message, now)
        return parent is not None and parent.role == "asistente"
