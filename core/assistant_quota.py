"""Atomic local daily invocation quota; no conversation data or plaintext IDs.

The HMAC key comes only from the environment; the file stores a public random
installation salt and keyed user digests, never credentials. snapshot() exposes
aggregate usage only. A missing
file after initialization, corruption, capacity exhaustion or a failed write
denies consumption. Intended for a single bot process; instances/threads in that
process share a lock and reload the file before every operation.
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import threading
from datetime import date, datetime, timezone
from pathlib import Path


class QuotaError(Exception):
    """Safe integration error; reason is fixed, never a path, ID or payload."""

    def __init__(self, reason='storage'):
        messages = {'exhausted': 'Llegaste a tu cuota diaria de Botón; se renueva a las 00:00 UTC.',
                    'capacity': 'Se alcanzó la capacidad de cuotas de Botón; probá mañana.',
                    'storage': 'No puedo verificar tu cuota; me detuve por seguridad.',
                    'identity': 'No puedo verificar quién hace la consulta.',
                    'clock': 'No puedo verificar la fecha de la cuota; probá más tarde.'}
        self.reason = reason if reason in messages else 'storage'
        super().__init__(messages[self.reason])


class UserDailyQuota:
    """consume(user_id, now=None) persists one invocation and returns remaining.

    `now` accepts a UTC/aware datetime or a Unix timestamp; naive datetimes are
    treated as UTC. A persisted high-water UTC day prevents clock rollback from
    granting another reset, including across restarts. No active user is evicted.
    snapshot(now=None) reads without writing or consuming an invocation.
    """

    _lock = threading.RLock()
    _max_bytes = 262144

    def __init__(self, path, limit=40, max_entries=1024):
        if type(limit) is not int or not 1 <= limit <= 2147483647:
            raise ValueError('limit must be a positive integer')
        if type(max_entries) is not int or not 1 <= max_entries <= 1024:
            raise ValueError('max_entries must be between 1 and 1024')
        self.path = Path(path)
        self.limit = limit
        self.max_entries = max_entries
        key = next((os.getenv(name) for name in ('AI_QUOTA_KEY', 'DISCORD_BOT_TOKEN', 'AI_API_KEY',
                    'GOOGLE_API_KEY', 'GEMINI_API_KEY', 'GROQ_API_KEY', 'CEREBRAS_API_KEY') if os.getenv(name)), '')
        if not key:
            raise QuotaError()
        self._key = hashlib.sha256(('boton-quota-v2\0' + key).encode('utf-8')).digest()
        with self._lock:
            try:
                self._read()
            except FileNotFoundError:
                # An empty install has no consumed day yet; the first consume
                # anchors it, including when callers inject a test clock.
                state = {'version': 2, 'day': date.min.isoformat(),
                         'salt': secrets.token_hex(32), 'users': {}}
                state['key_check'] = self._check(state['salt'])
                self._write(state)
            except (OSError, ValueError, TypeError, OverflowError, RecursionError):
                raise QuotaError() from None

    @staticmethod
    def _day(now):
        try:
            if now is None:
                now = datetime.now(timezone.utc)
            elif type(now) in (int, float):
                now = datetime.fromtimestamp(now, timezone.utc)
            if not isinstance(now, datetime):
                raise ValueError
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            return now.astimezone(timezone.utc).date().isoformat()
        except (ValueError, TypeError, OverflowError, OSError):
            raise QuotaError('clock') from None

    @staticmethod
    def _pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate field')
            result[key] = value
        return result

    def _read(self):
        with self.path.open('rb') as handle:
            data = handle.read(self._max_bytes + 1)
        if len(data) > self._max_bytes:
            raise ValueError('oversized quota')
        state = json.loads(data, object_pairs_hook=self._pairs)
        if type(state) is not dict or set(state) != {'version', 'day', 'salt', 'key_check', 'users'}:
            raise ValueError('invalid quota')
        if type(state['version']) is not int or state['version'] != 2:
            raise ValueError('invalid version')
        day = state['day']
        if type(day) is not str or date.fromisoformat(day).isoformat() != day:
            raise ValueError('invalid day')
        if any(type(state[key]) is not str or not re.fullmatch('[0-9a-f]{64}', state[key])
               for key in ('salt', 'key_check')):
            raise ValueError('invalid salt or key check')
        users = state['users']
        if type(users) is not dict or len(users) > self.max_entries:
            raise ValueError('invalid users')
        for identity, used in users.items():
            if not re.fullmatch('[0-9a-f]{64}', identity):
                raise ValueError('invalid identity')
            if type(used) is not int or not 1 <= used <= 2147483647:
                raise ValueError('invalid usage')
        return state

    def _load(self):
        try:
            return self._read()
        except (OSError, ValueError, TypeError, OverflowError, RecursionError):
            raise QuotaError() from None

    def _write(self, state):
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # mkstemp creates a private file (0600 on POSIX), on the same volume
            # as the destination. Never truncate the last known-good state.
            descriptor, temporary = tempfile.mkstemp(prefix='.assistant-quota-',
                                                     suffix='.tmp', dir=self.path.parent)
            with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as handle:
                json.dump(state, handle, separators=(',', ':'), sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            temporary = None
        except (OSError, ValueError, TypeError):
            raise QuotaError() from None
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    def _check(self, salt):
        return hmac.new(self._key, ('key-check\0' + salt).encode('ascii'), hashlib.sha256).hexdigest()

    def _identity(self, user_id, salt):
        if type(user_id) not in (str, int):
            raise QuotaError('identity')
        try:
            value = str(user_id)
            if not value or len(value) > 256:
                raise ValueError
            encoded = value.encode('utf-8')
        except (ValueError, UnicodeError):
            raise QuotaError('identity')
        return hmac.new(self._key, bytes.fromhex(salt) + b'\0user\0' + encoded, hashlib.sha256).hexdigest()

    def consume(self, user_id, now=None):
        today = self._day(now)
        with self._lock:
            state = self._load()
            identity = self._identity(user_id, state['salt'])
            if today > state['day']:
                state.update(day=today, users={})
                state['key_check'] = self._check(state['salt'])
            if not hmac.compare_digest(state['key_check'], self._check(state['salt'])):
                # Rotating a provider/Discord key must not grant every member a
                # second quota on the same UTC day. Resume at next daily rollover.
                raise QuotaError()
            users = state['users']
            if identity not in users and len(users) >= self.max_entries:
                raise QuotaError('capacity')
            used = users.get(identity, 0)
            if used >= self.limit:
                raise QuotaError('exhausted')
            users[identity] = used + 1
            self._write(state)
            return self.limit - used - 1

    def snapshot(self, now=None):
        today = self._day(now)
        with self._lock:
            state = self._load()
            users = state['users'] if today <= state['day'] else {}
            return {'limit': self.limit, 'used': sum(users.values()), 'users': len(users)}
