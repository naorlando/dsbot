import asyncio
import contextvars
import hashlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.assistant_operations import Operations, ProviderHealth
from core import assistant_trace


def entry(provider='google', endpoint='https://private.example/secret-endpoint',
          model='private-model', key='private-api-key'):
    return SimpleNamespace(provider=provider, endpoint=endpoint, model=model, key=key)


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.now = 10
        self.operations = Operations(clock=lambda: self.now)

    def test_existing_events_count_and_deduplicate_failover(self):
        record = self.operations.record
        record('provider', name='groq')
        record('http_start', service='llm')
        record('http_error', service='llm', status=429)
        record('provider_failover', name='groq', error='RateLimited')
        record('provider', name='cerebras')
        record('http_start', service='llm')
        record('provider_failover', name='cerebras', error='AssistantError')
        record('evidence', status='rejected', reason='private content')
        record('ground', status='no_sources')
        record('tool', status='invalid')
        snapshot = self.operations.snapshot()
        self.assertEqual(snapshot['counts'], {
            'answers': 0, 'requests': 2, 'rate_limits': 1,
            'provider_errors': 2, 'evidence_errors': 2, 'invalid_tool': 1})
        self.assertEqual(snapshot['providers']['groq'], {'provider_errors': 1, 'rate_limits': 1})
        self.assertEqual(snapshot['providers']['cerebras']['provider_errors'], 1)

    def test_rolling_latency_cap_nearest_rank_and_uptime(self):
        for i in range(1000):
            self.operations.record('end', milliseconds=i)
            self.operations.record('http_end', milliseconds=i * 2)
        self.now = 25
        snapshot = self.operations.snapshot()
        self.assertEqual(snapshot['latencies']['answer_ms'],
                         {'samples': 256, 'p50': 871.0, 'p95': 987.0})
        self.assertEqual(snapshot['latencies']['request_ms'],
                         {'samples': 256, 'p50': 1742.0, 'p95': 1974.0})
        self.assertEqual(snapshot['uptime_seconds'], 15)
        self.assertTrue(snapshot['volatile'])
        self.assertEqual(len(self.operations._latencies['answer_ms']), 256)
        with self.assertRaises(ValueError):
            Operations(max_samples=257)

    def test_invalid_durations_are_ignored(self):
        for value in (None, True, -1, float('inf'), float('nan'), '123', 86400001, {}):
            self.operations.record('end', milliseconds=value)
        self.assertEqual(self.operations.snapshot()['latencies']['answer_ms'],
                         {'samples': 0, 'p50': None, 'p95': None})

    def test_arbitrary_fields_and_provider_cardinality_never_exported(self):
        secret = 'Sensitive question or credential'
        hashed = hashlib.sha256(secret.encode()).hexdigest()
        for i in range(1000):
            self.operations.record('provider', name=f'{secret}-{i}')
            self.operations.record('http_error', service='llm', status=429,
                                   question=secret, question_hash=hashed, endpoint=secret)
            self.operations.record(secret, payload=secret)
        self.operations.record('evidence', status={})
        self.operations.record('provider_error', reason=[])
        snapshot = self.operations.snapshot()
        exported = json.dumps(snapshot)
        self.assertNotIn(secret, exported)
        self.assertNotIn(hashed, exported)
        self.assertEqual(len(snapshot['providers']), 9)
        self.assertEqual(snapshot['providers']['other']['rate_limits'], 1000)
        self.assertLess(len(exported), 2000)

    def test_provider_association_is_context_local(self):
        async def request(provider):
            self.operations.record('provider', name=provider)
            await asyncio.sleep(0)
            self.operations.record('http_error', service='llm', status=429)

        async def run():
            await asyncio.gather(request('google'), request('groq'))

        asyncio.run(run())
        snapshot = self.operations.snapshot()
        self.assertEqual(snapshot['providers']['google']['rate_limits'], 1)
        self.assertEqual(snapshot['providers']['groq']['rate_limits'], 1)

    def test_unrelated_web_errors_do_not_poison_provider_counts(self):
        self.operations.record('provider', name='google')
        self.operations.record('http_error', service='web', status=429)
        self.assertEqual(self.operations.snapshot()['counts']['provider_errors'], 0)

    def test_ground_rate_limit_is_google_and_failed_requests_have_latency(self):
        self.operations.record('http_start', service='ground')
        self.now = 10.5
        self.operations.record('http_error', service='ground', status=429)
        snapshot = self.operations.snapshot()
        self.assertEqual(snapshot['providers']['google']['rate_limits'], 1)
        self.assertEqual(snapshot['latencies']['request_ms'],
                         {'samples': 1, 'p50': 500.0, 'p95': 500.0})

    def test_transport_exception_failover_has_latency_without_http_error(self):
        self.operations.record('provider', name='groq')
        self.operations.record('http_start', service='llm')
        self.now = 11
        self.operations.record('provider_failover', name='groq', error='AssistantError')
        snapshot = self.operations.snapshot()
        self.assertEqual(snapshot['providers']['groq']['provider_errors'], 1)
        self.assertEqual(snapshot['latencies']['request_ms']['p95'], 1000.0)

    def test_snapshot_is_detached_and_fresh_instance_clears(self):
        self.operations.record('end', milliseconds=42)
        snapshot = self.operations.snapshot()
        snapshot['counts']['answers'] = 999
        snapshot['providers']['google']['rate_limits'] = 999
        self.assertEqual(self.operations.snapshot()['counts']['answers'], 1)
        self.assertEqual(self.operations.snapshot()['providers']['google']['rate_limits'], 0)
        self.assertEqual(Operations().snapshot()['counts']['answers'], 0)

    def test_trace_never_logs_question_hash_or_untrusted_fields(self):
        secret = 'a unique private question'
        with patch.object(assistant_trace, 'operations', self.operations), \
                self.assertLogs('dsbot', level='INFO') as logs:
            with assistant_trace.execution(secret):
                assistant_trace.event('tool_args', topic=secret, key=secret)
            self.assertEqual(assistant_trace.current_trace.get(), 'standalone')
            with self.assertRaisesRegex(RuntimeError, 'private exception'):
                with assistant_trace.execution(secret):
                    raise RuntimeError('private exception')
        self.assertNotIn(secret, '\n'.join(logs.output))
        self.assertNotIn(hashlib.sha256(secret.encode()).hexdigest()[:12], '\n'.join(logs.output))
        self.assertEqual(self.operations.snapshot()['counts']['answers'], 2)
        self.assertNotIn(secret, json.dumps(self.operations.snapshot()))
        self.assertNotIn(hashlib.sha256(secret.encode()).hexdigest()[:12],
                         json.dumps(self.operations.snapshot()))

    def test_stage_and_trace_are_allowlisted_before_logging(self):
        secret = 'secret-in-stage-or-trace'
        with patch.object(assistant_trace, 'operations', self.operations), \
                self.assertLogs('dsbot', level='INFO') as logs:
            token = assistant_trace.current_trace.set(secret)
            try:
                assistant_trace.event(secret, payload=secret)
                assistant_trace.event('http_error', service=secret, status=secret)
            finally:
                assistant_trace.current_trace.reset(token)
        self.assertEqual(len(logs.output), 1)
        self.assertNotIn(secret, '\n'.join(logs.output))
        self.assertIn('trace=standalone stage=http_error', logs.output[0])

    def test_context_state_does_not_export_raw_provider(self):
        context = contextvars.copy_context()
        context.run(self.operations.record, 'provider', name='arbitrary-secret')
        self.assertEqual(context.run(self.operations._active.get), 'other')


class ProviderHealthTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.health = ProviderHealth(clock=lambda: self.now)
        self.entry = entry()

    def test_rate_limit_cooloff_and_success(self):
        self.assertTrue(self.health.allowed(self.entry))
        self.health.failure(self.entry, 'rate_limit')
        self.assertFalse(self.health.allowed(self.entry))
        self.now = 599.999
        self.assertFalse(self.health.allowed(self.entry))
        self.now = 600
        self.assertTrue(self.health.allowed(self.entry))
        self.health.failure(self.entry, 'rate_limit')
        self.health.success(self.entry)
        self.assertTrue(self.health.allowed(self.entry))

    def test_three_invalid_calls_open_and_success_resets_streak(self):
        for _ in range(2):
            self.health.failure(self.entry, 'invalid_tool')
            self.assertTrue(self.health.allowed(self.entry))
        self.health.success(self.entry, validated=True)
        for _ in range(2):
            self.health.failure(self.entry, 'invalid_tool')
        self.assertTrue(self.health.allowed(self.entry))
        self.health.failure(self.entry, 'invalid_tool')
        self.assertFalse(self.health.allowed(self.entry))
        self.now = 600
        self.assertTrue(self.health.allowed(self.entry))
        self.health.failure(self.entry, 'invalid_tool')
        self.assertTrue(self.health.allowed(self.entry))

    def test_provider_errors_do_not_add_unrequested_retry_policy(self):
        for _ in range(10):
            self.health.failure(self.entry, 'provider_error')
        self.assertTrue(self.health.allowed(self.entry))
        with self.assertRaises(ValueError):
            self.health.failure(self.entry, 'raw exception details')

    def test_transport_success_keeps_invalid_streak_across_invocations(self):
        for _ in range(2):
            self.health.success(self.entry)
            self.health.failure(self.entry, 'invalid_tool')
            self.assertTrue(self.health.allowed(self.entry))
        self.health.success(self.entry, validated=False)
        self.health.failure(self.entry, 'invalid_tool')
        self.assertFalse(self.health.allowed(self.entry))
        # Even a late transport success cannot close a malformed-tool circuit.
        self.health.success(self.entry)
        self.assertFalse(self.health.allowed(self.entry))
        self.health.success(self.entry, validated=True)
        self.assertTrue(self.health.allowed(self.entry))
        self.health.failure(self.entry, 'invalid_tool')
        self.assertTrue(self.health.allowed(self.entry))

    def test_reset_clears_all_provider_state(self):
        self.health.failure(self.entry, 'rate_limit')
        self.health.reset()
        self.assertEqual(self.health.snapshot()['tracked'], 0)
        self.assertTrue(self.health.allowed(self.entry))

    def test_scope_excludes_key_and_includes_endpoint_provider_model(self):
        self.health.failure(self.entry, 'rate_limit')
        self.assertFalse(self.health.allowed(entry(key='different-key')))
        self.assertTrue(self.health.allowed(entry(endpoint='https://other.example/')))
        self.assertTrue(self.health.allowed(entry(provider='groq')))
        self.assertTrue(self.health.allowed(entry(model='other-model')))

    def test_snapshot_contains_no_endpoint_model_or_credentials(self):
        self.health.failure(self.entry, 'rate_limit')
        snapshot = self.health.snapshot()
        self.assertEqual(snapshot['providers']['google'], {'tracked': 1, 'open': 1})
        exported = json.dumps(snapshot)
        for private in (self.entry.key, self.entry.endpoint, self.entry.model):
            self.assertNotIn(private, exported)
        self.assertNotIn(self.entry.key, repr(self.health.__dict__))

    def test_never_reads_entry_key(self):
        class Entry:
            endpoint = 'https://example.com'
            provider = 'google'
            model = 'm'

            @property
            def key(self):
                raise AssertionError('must not read credentials')

        self.assertTrue(self.health.allowed(Entry()))
        self.health.failure(Entry(), 'rate_limit')
        self.health.success(Entry())

    def test_bounded_capacity_does_not_evict_open_circuits(self):
        entries = [entry(model=f'model-{i}') for i in range(33)]
        for item in entries[:32]:
            self.health.failure(item, 'rate_limit')
        self.assertFalse(self.health.allowed(entries[-1]))
        self.health.failure(entries[-1], 'rate_limit')
        self.assertEqual(self.health.snapshot()['tracked'], 32)
        for item in entries[:32]:
            self.assertFalse(self.health.allowed(item))
        self.now = 600
        self.assertTrue(self.health.allowed(entries[-1]))
        self.assertLessEqual(self.health.snapshot()['tracked'], 32)
        with self.assertRaises(ValueError):
            ProviderHealth(max_providers=33)

    def test_capacity_does_not_evict_partial_invalid_streaks(self):
        health = ProviderHealth(max_providers=1, clock=lambda: self.now)
        health.failure(self.entry, 'invalid_tool')
        self.assertFalse(health.allowed(entry(model='other')))
        health.success(self.entry, validated=True)
        self.assertTrue(health.allowed(entry(model='other')))


if __name__ == '__main__':
    unittest.main()
