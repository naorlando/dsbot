"""Bounded, content-free operational state. All state here clears on restart.

Only fixed provider labels, counters and the last <=256 latency samples are
exported. Endpoints, model names, credentials and arbitrary event fields never
appear in snapshots. Circuit breakers do not retry or perform any I/O.
"""

import contextvars
import math
import threading
import time
from collections import deque


PROVIDERS = frozenset({'google', 'groq', 'cerebras', 'openrouter', 'openai',
                       'anthropic', 'custom', 'other', 'unknown'})
REASONS = frozenset({'rate_limit', 'provider_error', 'invalid_tool', 'invalid_response'})


def _provider(value):
    return value if type(value) is str and value in PROVIDERS else 'other'


def _duration(value):
    if type(value) in (int, float) and 0 <= value <= 86400000:
        return float(value)
    return None


def _one_of(value, choices):
    return type(value) is str and value in choices


class Operations:
    """Lifetime counters and rolling nearest-rank p50/p95 latencies in ms."""

    def __init__(self, max_samples=256, clock=time.monotonic):
        if type(max_samples) is not int or not 1 <= max_samples <= 256:
            raise ValueError('max_samples must be between 1 and 256')
        self.clock = clock
        self.started = clock()
        self.max_samples = max_samples
        self._lock = threading.RLock()
        self._counts = dict.fromkeys(('answers', 'requests', 'rate_limits',
                                     'provider_errors', 'evidence_errors', 'invalid_tool'), 0)
        self._providers = {name: {'rate_limits': 0, 'provider_errors': 0}
                           for name in sorted(PROVIDERS)}
        self._latencies = {name: deque(maxlen=max_samples)
                           for name in ('answer_ms', 'request_ms')}
        # Provider association is task-local, including interleaved async calls.
        self._active = contextvars.ContextVar('operations_provider', default='unknown')
        self._http_failed = contextvars.ContextVar('operations_http_failed', default=False)
        self._http_started = contextvars.ContextVar('operations_http_started', default=None)

    def _failure(self, provider, rate_limit):
        self._counts['provider_errors'] += 1
        self._providers[provider]['provider_errors'] += 1
        if rate_limit:
            self._counts['rate_limits'] += 1
            self._providers[provider]['rate_limits'] += 1

    def record(self, stage, **fields):
        """Consume the existing event API; never retain arbitrary values.

        A provider event associates subsequent llm HTTP events with that attempt.
        A following provider_failover is deduplicated against its HTTP error.
        Direct provider_error events accept only the fixed reason vocabulary.
        """
        if type(stage) is not str:
            return
        with self._lock:
            if stage == 'start':
                self._active.set('unknown')
                self._http_failed.set(False)
                self._http_started.set(None)
            elif stage == 'provider':
                self._active.set(_provider(fields.get('provider', fields.get('name', 'unknown'))))
                self._http_failed.set(False)
            elif stage == 'http_start':
                self._counts['requests'] += 1
                self._http_failed.set(False)
                self._http_started.set(self.clock())
            elif stage == 'end':
                self._counts['answers'] += 1
                self._latency('answer_ms', fields)
                self._active.set('unknown')
                self._http_failed.set(False)
                self._http_started.set(None)
            elif stage == 'http_end':
                self._finish_request(fields)
            elif stage == 'http_error':
                if fields.get('service') in ('llm', 'ground'):
                    default = 'google' if fields.get('service') == 'ground' else self._active.get()
                    provider = _provider(fields.get('provider', default))
                    self._failure(provider, fields.get('status') == 429)
                    self._http_failed.set(True)
                self._finish_request(fields)
            elif stage == 'provider_failover':
                if not self._http_failed.get():
                    provider = _provider(fields.get('provider', fields.get('name', self._active.get())))
                    rate_limit = (fields.get('error') == 'RateLimited'
                                  or fields.get('reason') == 'rate_limit'
                                  or fields.get('status') == 429)
                    self._failure(provider, rate_limit)
                    self._finish_request(fields)
                self._http_failed.set(False)
            elif stage == 'provider_error' and _one_of(fields.get('reason'), REASONS):
                self._failure(_provider(fields.get('provider', self._active.get())),
                              fields['reason'] == 'rate_limit')
            elif stage == 'evidence' and _one_of(fields.get('status'), {
                    'error', 'rejected', 'no_sources', 'insufficient_retry'}):
                self._counts['evidence_errors'] += 1
            elif stage == 'ground' and _one_of(fields.get('status'), {
                    'error', 'unpublishable', 'empty', 'incomplete_or_blocked',
                    'no_text', 'text_too_large', 'no_sources'}):
                self._counts['evidence_errors'] += 1
            elif stage == 'tool' and fields.get('status') == 'invalid':
                self._counts['invalid_tool'] += 1

    def _latency(self, kind, fields):
        duration = _duration(fields.get('milliseconds'))
        if duration is not None:
            self._latencies[kind].append(duration)

    def _finish_request(self, fields):
        duration = _duration(fields.get('milliseconds'))
        started = self._http_started.get()
        if duration is None and started is not None:
            duration = _duration((self.clock() - started) * 1000)
        if duration is not None:
            self._latencies['request_ms'].append(duration)
        self._http_started.set(None)

    def snapshot(self):
        with self._lock:
            latencies = {}
            for name, samples in self._latencies.items():
                values = sorted(samples)
                latencies[name] = {
                    'samples': len(values),
                    'p50': values[math.ceil(len(values) * .50) - 1] if values else None,
                    'p95': values[math.ceil(len(values) * .95) - 1] if values else None,
                }
            return {'counts': dict(self._counts),
                    'providers': {name: dict(counts) for name, counts in self._providers.items()},
                    'latencies': latencies, 'max_samples': self.max_samples,
                    'uptime_seconds': max(0.0, self.clock() - self.started),
                    'volatile': True}


class ProviderHealth:
    """Per-(endpoint, provider, model) circuit breaker, bounded to <=32 entries.

    Rate limits open immediately; three invalid-tool failures open by default.
    Other provider errors do not open a circuit. Expiry permits the next attempt;
    validated success resets all failure state. Transport success preserves an
    invalid-tool streak across invocations. Capacity exhaustion denies new entries,
    rather than evicting an open circuit and bypassing its cooldown.
    """

    def __init__(self, cooloff=600, invalid_tool_threshold=3, max_providers=32,
                 clock=time.monotonic):
        if type(max_providers) is not int or not 1 <= max_providers <= 32:
            raise ValueError('max_providers must be between 1 and 32')
        if type(invalid_tool_threshold) is not int or invalid_tool_threshold < 1:
            raise ValueError('invalid_tool_threshold must be positive')
        if type(cooloff) not in (int, float) or not math.isfinite(cooloff) or cooloff <= 0:
            raise ValueError('cooloff must be positive and finite')
        self.clock = clock
        self.cooloff = cooloff
        self.invalid_tool_threshold = invalid_tool_threshold
        self.max_providers = max_providers
        self._entries = {}
        self._lock = threading.RLock()

    @staticmethod
    def _key(entry):
        # Deliberately never read entry.key, or stringify/repr the entry.
        parts = (entry.endpoint, entry.provider, entry.model)
        if any(type(value) is not str or not value or len(value) > limit
               for value, limit in zip(parts, (4096, 128, 512))):
            raise ValueError('invalid provider entry')
        return parts

    def _state(self, key, now):
        state = self._entries.get(key)
        if state is not None:
            if state['until'] and now >= state['until']:
                state.update(until=0, invalid_tool=0, reason=None)
            return state
        if len(self._entries) >= self.max_providers:
            # Only fully reset entries can be recycled, never failure streaks.
            reusable = next((old for old, item in self._entries.items()
                             if (not item['until'] or now >= item['until'])
                             and (not item['invalid_tool'] or item['until'])), None)
            if reusable is None:
                return None
            del self._entries[reusable]
        state = {'until': 0, 'invalid_tool': 0, 'reason': None}
        self._entries[key] = state
        return state

    def allowed(self, entry):
        with self._lock:
            now = self.clock()
            state = self._state(self._key(entry), now)
            return state is not None and now >= state['until']

    def failure(self, entry, reason):
        if type(reason) is not str or reason not in REASONS:
            raise ValueError('unknown provider failure reason')
        with self._lock:
            now = self.clock()
            state = self._state(self._key(entry), now)
            if state is None:
                return
            state['reason'] = reason
            if reason in {'invalid_tool', 'invalid_response'}:
                state['invalid_tool'] = min(self.invalid_tool_threshold, state['invalid_tool'] + 1)
            if reason == 'rate_limit' or state['invalid_tool'] >= self.invalid_tool_threshold:
                state['until'] = max(state['until'], now + self.cooloff)

    def success(self, entry, validated=False):
        """Record transport success, or validated=True after response validation.

        A 200 response alone must not erase malformed-tool failures. An already
        open invalid-tool circuit also survives a late in-flight HTTP success.
        """
        with self._lock:
            state = self._state(self._key(entry), self.clock())
            if state is not None:
                if validated:
                    state.update(until=0, invalid_tool=0, reason=None)
                elif state['invalid_tool'] < self.invalid_tool_threshold:
                    state.update(until=0, reason='invalid_tool' if state['invalid_tool'] else None)

    def reset(self):
        """Explicitly clear all in-memory circuit state (also cleared at restart)."""
        with self._lock:
            self._entries.clear()

    def snapshot(self):
        with self._lock:
            now = self.clock()
            providers = {}
            for (_, name, _), state in self._entries.items():
                counts = providers.setdefault(_provider(name), {'tracked': 0, 'open': 0})
                counts['tracked'] += 1
                counts['open'] += int(state['until'] > now)
            return {'tracked': len(self._entries),
                    'open': sum(value['open'] for value in providers.values()),
                    'capacity': self.max_providers, 'providers': providers,
                    'volatile': True}


operations = Operations()
provider_health = ProviderHealth()
