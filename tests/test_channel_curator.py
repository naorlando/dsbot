import asyncio
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.channel_curator import ChannelCurator, SYSTEM_PROMPT, TTL_SECONDS


class ChannelCuratorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'curator.json'
        self.now = 1000.0
        self.curator = self.make(min_messages=1)

    def make(self, **kwargs):
        return ChannelCurator(self.path, clock=lambda: self.now, **kwargs)

    def row(self, number=0, author='Ana', text=None):
        return {'fecha': f'2026-10-29 12:{number % 60:02d}', 'autor': author,
                'texto': text or f'Apuesto por rojo en la ronda {number}'}

    def observe(self, count=1, author='Ana'):
        rows = [self.row(i, author) for i in range(count)]
        for row in rows:
            self.assertTrue(self.curator.observe(row))
        return rows

    def response(self, rows, topic='Apuesta de la ronda', summary='Ana apostó por rojo.'):
        return {'content': json.dumps({'bullets': [
            {'topic': topic, 'summary': summary, 'evidence': rows[:2]}]}, ensure_ascii=False)}

    async def curate_one(self, number=0, topic='Apuesta de la ronda'):
        row = self.row(number)
        self.curator.observe(row)
        return await self.curator.curate(AsyncMock(return_value=self.response([row], topic=topic)))

    def test_public_api_defaults_and_configuration(self):
        signature = inspect.signature(ChannelCurator)
        self.assertEqual(signature.parameters['min_messages'].default, 50)
        self.assertEqual(signature.parameters['interval_seconds'].default, 7200)
        self.assertEqual(signature.parameters['max_daily'].default, 6)
        for kwargs in ({'min_messages': 0}, {'min_messages': True}, {'max_daily': -1},
                       {'max_daily': True}, {'interval_seconds': float('nan')},
                       {'interval_seconds': -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.make(**kwargs)

    def test_default_message_trigger(self):
        self.curator = self.make()
        self.observe(49)
        self.assertFalse(self.curator.due())
        self.observe()
        self.assertTrue(self.curator.due())

    def test_interval_requires_ten_and_exact_threshold(self):
        self.curator = self.make()
        self.observe(9)
        self.now += 7200
        self.assertFalse(self.curator.due())
        self.observe()
        self.assertTrue(self.curator.due())

    def test_interval_not_early_and_empty_queue_never_due(self):
        self.curator = self.make()
        self.now += 100000
        self.assertFalse(self.curator.due())
        self.observe(10)
        self.curator.last_curated = self.now
        self.now += 7199
        self.assertFalse(self.curator.due())
        self.now += 1
        self.assertTrue(self.curator.due())

    def test_queue_bounded_and_raws_never_persisted(self):
        self.observe(151)
        self.assertEqual(len(self.curator._pending), 100)
        self.assertEqual(self.curator.pending_count, 151)
        saved = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(saved['pending_count'], 151)
        self.assertEqual(saved['bullets'], [])
        self.assertNotIn('Apuesto', self.path.read_text(encoding='utf-8'))
        self.assertNotIn('autor', self.path.read_text(encoding='utf-8'))

    def test_observe_copies_and_rejects_invalid_or_sensitive_rows(self):
        row = self.row()
        self.curator.observe(row)
        row['texto'] = 'changed'
        self.assertNotEqual(self.curator._pending[0][1]['texto'], 'changed')
        for value in (None, [], {}, {'fecha': 1, 'autor': 'Ana', 'texto': 'a'},
                      self.row(text='   '), self.row(text='Ana tiene un diagnóstico de salud'),
                      self.row(text='Su religión es privada'), self.row(text='Su etnia es privada'),
                      self.row(text='Ana es gay'), self.row(text='Perfil de personalidad')):
            with self.subTest(value=value):
                self.assertFalse(self.curator.observe(value))
        self.assertEqual(self.curator.pending_count, 1)

    async def test_success_one_call_no_tools_and_exact_sources(self):
        rows = self.observe(3)
        complete = AsyncMock(return_value=self.response(rows))
        self.assertTrue(await self.curator.curate(complete))
        complete.assert_awaited_once()
        arguments = complete.call_args.kwargs
        self.assertEqual(arguments['tools'], [])
        messages = arguments['messages']
        self.assertEqual([m['role'] for m in messages], ['system', 'user'])
        self.assertEqual(messages[0]['content'], SYSTEM_PROMPT)
        self.assertEqual(json.loads(messages[1]['content'])['messages'], rows)
        self.assertIn('NO CONFIABLES', SYSTEM_PROMPT)
        for trait in ('religión', 'etnia', 'género', 'salud', 'sexualidad'):
            self.assertIn(trait, SYSTEM_PROMPT)
        self.assertEqual(self.curator.pending_count, 0)
        self.assertEqual(len(self.curator._pending), 0)
        self.assertEqual(self.curator.bullets[0]['evidence'], rows[:2])
        self.assertEqual(self.curator.bullets[0]['ts'], self.now)
        self.assertEqual(self.curator.bullets[0]['expiry'], self.now + TTL_SECONDS)
        reloaded = self.make()
        self.assertEqual(reloaded.bullets, self.curator.bullets)
        self.assertEqual(reloaded.daily_count, 1)
        self.assertEqual(reloaded.last_curated, self.now)
        self.assertEqual(reloaded.pending_count, 0)

    async def test_not_due_does_not_call_model(self):
        complete = AsyncMock()
        self.assertFalse(await self.curator.curate(complete))
        complete.assert_not_called()

    async def test_empty_bullets_is_a_valid_success_and_direct_dict_supported(self):
        self.observe()
        self.assertTrue(await self.curator.curate(AsyncMock(return_value={'bullets': []})))
        self.assertEqual(self.curator.pending_count, 0)
        self.assertEqual(self.curator.bullets, [])

    async def test_failure_keeps_pending_and_cooldown_survives_restart(self):
        self.observe()
        complete = AsyncMock(side_effect=RuntimeError('must not log this payload'))
        self.assertFalse(await self.curator.curate(complete))
        self.assertEqual(self.curator.pending_count, 1)
        self.assertEqual(len(self.curator._pending), 1)
        self.assertEqual(self.curator.last_curated, 1000.0)
        self.assertFalse(self.curator.due())
        self.now += 599
        self.assertFalse(self.curator.due())
        self.now += 1
        self.assertTrue(self.curator.due())
        reloaded = self.make(min_messages=1)
        self.assertEqual(reloaded.daily_count, 1)
        self.assertEqual(reloaded.pending_count, 1)
        self.assertEqual(len(reloaded._pending), 0)
        self.assertFalse(reloaded.due())  # restart cannot recreate raw messages

    async def test_cooldown_blocks_new_observations_after_restart(self):
        self.observe()
        await self.curator.curate(AsyncMock(return_value={'content': 'not JSON'}))
        self.curator = self.make(min_messages=1)
        self.observe()
        self.assertFalse(self.curator.due())
        self.now += 600
        self.assertTrue(self.curator.due())

    async def test_invalid_output_matrix_never_consumes_observations(self):
        row = self.row()
        valid = {'topic': 'Ronda', 'summary': 'Ana apostó por rojo.', 'evidence': [row]}
        invalid = [None, [], {}, {'content': '```json\n{}\n```'},
                   {'content': '{"bullets":[],"bullets":[]}'},
                   {'content': 'x' * 64001}, {'content': '{}', 'tool_calls': [{}]},
                   {'bullets': 'bad'}, {'bullets': [valid] * 13},
                   {'bullets': [dict(valid, topic='')]},
                   {'bullets': [dict(valid, summary='x' * 221)]},
                   {'bullets': [dict(valid, summary='   ')]},
                   {'bullets': [dict(valid, topic='x' * 81)]},
                   {'bullets': [dict(valid, evidence=[])]},
                   {'bullets': [dict(valid, evidence=[row] * 3)]},
                   {'bullets': [dict(valid, evidence=[row, row])]},
                   {'bullets': [dict(valid, evidence=[dict(row, texto='Apuesto por azul')])]},
                   {'bullets': [dict(valid, evidence=[dict(row, autor='Beto')])]},
                   {'bullets': [dict(valid, evidence=[dict(row, fecha='ayer')])]},
                   {'bullets': [dict(valid, evidence=[dict(row, extra='not allowed')])]},
                   {'bullets': [dict(valid, evidence=[None])]},
                   {'bullets': [dict(valid, extra='not allowed')]},
                   {'bullets': [valid, valid]}]
        for result in invalid:
            with self.subTest(result=str(result)[:140]):
                self.path.unlink(missing_ok=True)
                self.curator = self.make(min_messages=1)
                self.observe()
                before = self.curator.last_curated
                self.assertFalse(await self.curator.curate(AsyncMock(return_value=result)))
                self.assertEqual(self.curator.pending_count, 1)
                self.assertEqual(self.curator.last_curated, before)
                self.assertEqual(self.curator.bullets, [])

    async def test_false_known_author_attribution_rejected(self):
        ana = self.row(author='Ana')
        beto = self.row(1, author='Beto')
        self.curator.observe(ana)
        self.curator.observe(beto)
        result = self.response([ana], summary='Beto apostó por rojo.')
        self.assertFalse(await self.curator.curate(AsyncMock(return_value=result)))
        self.assertEqual(self.curator.pending_count, 2)

    async def test_invented_named_author_not_in_snapshot_rejected(self):
        rows = self.observe()
        result = self.response(rows, summary='Carlos apostó por rojo.')
        self.assertFalse(await self.curator.curate(AsyncMock(return_value=result)))
        self.assertEqual(self.curator.pending_count, 1)

    async def test_personal_profiles_and_sensitive_summaries_rejected(self):
        for summary in ('Ana es irresponsable.', 'Ana siempre apuesta.', 'Su religión es X.',
                        'Ana tiene diabetes.', 'Su etnia es X.', 'Ana is gay.'):
            with self.subTest(summary=summary):
                self.path.unlink(missing_ok=True)
                self.curator = self.make(min_messages=1)
                rows = self.observe()
                self.assertFalse(await self.curator.curate(AsyncMock(return_value=self.response(rows, summary=summary))))
                self.assertEqual(self.curator.bullets, [])

    async def test_snapshot_watermark_retains_new_rows(self):
        rows = self.observe(5)
        started, release = asyncio.Event(), asyncio.Event()

        async def complete(messages, tools):
            started.set()
            await release.wait()
            return self.response(rows)

        task = asyncio.create_task(self.curator.curate(complete))
        await started.wait()
        new = self.row(20, 'Beto')
        self.curator.observe(new)
        release.set()
        self.assertTrue(await task)
        self.assertEqual(self.curator.pending_count, 1)
        self.assertEqual([r for _, r in self.curator._pending], [new])
        self.assertEqual(self.make().pending_count, 1)

    async def test_watermark_handles_queue_overflow_during_await(self):
        self.observe(150)

        async def complete(messages, tools):
            snapshot = json.loads(messages[1]['content'])['messages']
            self.assertEqual(len(snapshot), 100)
            self.observe(120, author='Beto')
            return self.response(snapshot)

        self.assertTrue(await self.curator.curate(complete))
        self.assertEqual(self.curator.pending_count, 120)
        self.assertEqual(len(self.curator._pending), 100)
        self.assertTrue(all(r['autor'] == 'Beto' for _, r in self.curator._pending))

    async def test_single_flight_lock_no_duplicate_or_queued_calls(self):
        rows = self.observe()
        started, release = asyncio.Event(), asyncio.Event()

        async def completion(messages, tools):
            started.set()
            await release.wait()
            return self.response(rows)

        complete = AsyncMock(side_effect=completion)
        first = asyncio.create_task(self.curator.curate(complete))
        await started.wait()
        self.assertFalse(self.curator.due())
        self.assertFalse(await self.curator.curate(complete))
        release.set()
        self.assertTrue(await first)
        complete.assert_awaited_once()
        self.assertFalse(self.curator._lock.locked())

    async def test_wait_for_timeout_cancels_call_and_keeps_queue(self):
        self.observe()
        cancelled = asyncio.Event()

        async def blocked(messages, tools):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        with patch('core.channel_curator.TIMEOUT_SECONDS', 0.01):
            self.assertFalse(await self.curator.curate(blocked))
        self.assertTrue(cancelled.is_set())
        self.assertEqual(self.curator.pending_count, 1)
        self.assertFalse(self.curator._lock.locked())

    async def test_external_cancellation_safe_and_releases_lock(self):
        self.observe()
        started = asyncio.Event()

        async def blocked(messages, tools):
            started.set()
            await asyncio.Event().wait()

        task = asyncio.create_task(self.curator.curate(blocked))
        await started.wait()
        task.cancel()
        self.assertFalse(await task)
        self.assertEqual(self.curator.pending_count, 1)
        self.assertFalse(self.curator._lock.locked())

    async def test_default_daily_cap_persisted_and_utc_rollover(self):
        for i in range(6):
            self.assertTrue(await self.curate_one(i, topic=f'Ronda {i}'))
        self.observe()
        self.assertFalse(self.curator.due())
        self.curator = self.make(min_messages=1)
        self.assertEqual(self.curator.daily_count, 6)
        self.observe()
        self.assertFalse(self.curator.due())
        self.now = 86400.0
        self.assertTrue(self.curator.due())
        self.assertTrue(await self.curator.curate(AsyncMock(return_value={'bullets': []})))
        self.assertEqual(self.curator.daily_count, 1)
        self.assertEqual(self.make().daily_count, 1)

    async def test_failures_spend_daily_budget_without_consuming_messages(self):
        self.curator = self.make(min_messages=1, max_daily=2)
        self.observe()
        for _ in range(2):
            self.assertFalse(await self.curator.curate(AsyncMock(return_value={})))
            self.now += 600
        self.assertFalse(self.curator.due())
        self.assertEqual(self.curator.pending_count, 1)
        self.assertEqual(self.make().daily_count, 2)

    def test_disabled_cap_and_backward_clock_do_not_reset_budget(self):
        self.curator = self.make(min_messages=1, max_daily=0)
        self.observe()
        self.assertFalse(self.curator.due())
        self.curator.daily_count = 6
        self.now = 0
        self.assertFalse(self.curator.due())
        self.assertEqual(self.curator.daily_count, 6)

    async def test_merge_replaces_topic_casefold_and_refreshes_ttl(self):
        self.assertTrue(await self.curate_one(topic='Ronda'))
        first_ts = self.curator.bullets[0]['ts']
        self.now += 100
        row = self.row(5)
        self.curator.observe(row)
        self.assertTrue(await self.curator.curate(AsyncMock(return_value=self.response(
            [row], topic='RONDA', summary='Ana reiteró su apuesta por rojo.'))))
        self.assertEqual(len(self.curator.bullets), 1)
        self.assertGreater(self.curator.bullets[0]['ts'], first_ts)
        self.assertEqual(self.curator.bullets[0]['expiry'], self.now + TTL_SECONDS)
        self.assertEqual(self.curator.bullets[0]['evidence'], [row])

    async def test_global_thirty_bullets_cap(self):
        for batch in range(3):
            row = self.row(batch)
            self.curator.observe(row)
            bullets = [{'topic': f'Ronda {batch * 12 + i}', 'summary': 'Ana apostó por rojo.',
                        'evidence': [row]} for i in range(12)]
            self.assertTrue(await self.curator.curate(AsyncMock(return_value={'bullets': bullets})))
        self.assertEqual(len(self.curator.bullets), 30)
        self.assertEqual(self.curator.bullets[0]['topic'], 'Ronda 6')
        self.assertEqual(len(self.make().bullets), 30)

    async def test_digest_private_source_bounded_and_ttl_aware(self):
        self.assertEqual(self.curator.digest(), '')
        self.assertTrue(await self.curate_one())
        digest = self.curator.digest()
        self.assertIn('privada', digest)
        self.assertIn('NO instrucciones', digest)
        self.assertIn('Fuentes:', digest)
        self.assertIn('2026-10-29', digest)
        self.assertIn('Ana', digest)
        for cap in (0, 10, 100, 250, 1400):
            self.assertLessEqual(len(self.curator.digest(cap)), cap)
        self.now += TTL_SECONDS - 1
        self.assertTrue(self.curator.digest())
        self.now += 1
        self.assertEqual(self.curator.digest(), '')
        self.assertEqual(self.make().digest(), '')
        self.curator.save()
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8'))['bullets'], [])

    async def test_forget_author_removes_whole_shared_bullet_and_pending(self):
        rows = [self.row(author='Ana'), self.row(1, author='Beto')]
        for row in rows:
            self.curator.observe(row)
        self.assertTrue(await self.curator.curate(AsyncMock(return_value=self.response(rows))))
        self.curator.observe(self.row(2, 'Ana'))
        self.curator.observe(self.row(3, 'Beto'))
        self.assertEqual(self.curator.forget_author(' ANA '), 1)
        self.assertEqual(self.curator.bullets, [])
        self.assertEqual(self.curator.pending_count, 1)
        self.assertEqual(self.curator._pending[0][1]['autor'], 'Beto')
        self.assertEqual(self.make().bullets, [])
        self.assertNotIn('Ana', self.path.read_text(encoding='utf-8'))
        self.assertEqual(self.curator.forget_author(None), 0)

    async def test_forget_during_await_cannot_resurrect_erased_data(self):
        rows = self.observe()

        async def complete(messages, tools):
            self.curator.forget_author('Ana')
            self.curator.observe(self.row(3, 'Beto'))
            return self.response(rows)

        self.assertFalse(await self.curator.curate(complete))
        self.assertEqual(self.curator.bullets, [])
        self.assertEqual(self.curator.pending_count, 1)
        self.assertNotIn('Ana', self.path.read_text(encoding='utf-8'))

    async def test_synthetic_secrets_rejected_before_model_or_persistence(self):
        # All synthetic fixtures: no environment variables, secret files or network.
        fake_discord = 'A' * 24 + '.' + 'B' * 6 + '.' + 'C' * 30
        fake_mfa = 'mfa.' + 'D' * 60
        fake_generic = 'E9_' * 15
        values = [fake_discord, fake_mfa, fake_generic, 'sk-test-fixture-123456789',
                  'tvly-dev-fixture123456789', 'password="synthetic pass"',
                  'api_key=fixture123', 'Bearer fixture123456',
                  'DISCORD_TOKEN=shortfixture', 'client_secret=anotherfixture',
                  'AWS_SECRET_ACCESS_KEY=fixturekey', '"token": "jsonfixture"',
                  '-----BEGIN PRIVATE KEY-----\nfixture only\n-----END PRIVATE KEY-----']
        for value in values:
            with self.subTest(value=value):
                self.assertFalse(self.curator.observe(self.row(text='Apuesto por rojo. ' + value)))
        complete = AsyncMock()
        self.assertFalse(await self.curator.curate(complete))
        complete.assert_not_called()
        self.assertFalse(self.path.exists())
        self.assertEqual(self.curator.pending_count, 0)

    async def test_urls_and_mentions_scrubbed_everywhere(self):
        values = ['https://example.invalid/private?q=fixture', 'www.example.invalid',
                  'discord.gg/fixture', '<@12345>', '<@!12345>', '<@&12345>',
                  '<#12345>', '@everyone', '@here', '@someone']
        self.assertTrue(self.curator.observe(self.row(text='Apuesto por rojo. ' + ' '.join(values))))

        async def complete(messages, tools):
            payload = messages[1]['content']
            for value in values:
                self.assertNotIn(value, payload)
            sanitized = json.loads(payload)['messages'][0]
            return self.response([sanitized], topic='Ronda', summary='Ana apostó por rojo.')

        self.assertTrue(await self.curator.curate(complete))
        persisted = self.path.read_text(encoding='utf-8')
        self.assertIn('[enlace omitido]', persisted)
        self.assertIn('[mención omitida]', persisted)
        for value in values:
            self.assertNotIn(value, persisted)
            self.assertNotIn(value, self.curator.digest())
        self.assertEqual(self.make().bullets, self.curator.bullets)

    async def test_raw_or_changed_evidence_not_accepted_after_sanitization(self):
        row = self.row(text='Apuesto por rojo https://example.invalid')
        self.curator.observe(row)
        self.assertFalse(await self.curator.curate(AsyncMock(return_value=self.response([row]))))
        self.assertEqual(self.curator.pending_count, 1)

    async def test_output_sanitized_too_and_logs_counters_only(self):
        rows = self.observe()
        result = self.response(rows, summary='Ana apostó por rojo. https://example.invalid @everyone')
        with patch('core.channel_curator.event') as trace:
            self.assertTrue(await self.curator.curate(AsyncMock(return_value=result)))
            for call in trace.call_args_list:
                self.assertEqual(call.args, ('channel_curator',))
                self.assertTrue(all(type(value) is int for value in call.kwargs.values()))
        self.assertNotIn('https://', self.curator.digest())
        self.assertNotIn('@everyone', self.curator.digest())

    def test_missing_corrupt_and_malformed_files_are_safe(self):
        for contents in ('{broken', '[]', '{"version":1,"bullets":"bad"}',
                         '{"version":1,"pending_count":[],"daily_count":"bad","day":-1}',
                         '{"version":1,"last_curated":NaN,"retry_at":Infinity}'):
            with self.subTest(contents=contents):
                self.path.write_text(contents, encoding='utf-8')
                curator = self.make()
                self.assertEqual(curator.digest(), '')
                self.assertEqual(curator.pending_count, 0)
                self.assertEqual(curator.daily_count, 0)
                self.assertTrue(curator.save())
        self.path.write_bytes(b'\xff\xfe invalid utf8')
        self.assertEqual(self.make().digest(), '')

    async def test_malformed_loaded_bullets_rejected_and_expiry_not_extendable(self):
        await self.curate_one()
        payload = json.loads(self.path.read_text(encoding='utf-8'))
        valid = payload['bullets'][0]
        for entry in (dict(valid, expiry=self.now + TTL_SECONDS + 1),
                      dict(valid, ts=float('nan')), dict(valid, expiry='later'),
                      dict(valid, ts=10 ** 1000), dict(valid, expiry=10 ** 1000),
                      dict(valid, summary='Ana es un perfil de personalidad'),
                      dict(valid, evidence=None), dict(valid, evidence=[{}]),
                      dict(valid, evidence=[dict(valid['evidence'][0], texto='secret=fixture')])):
            with self.subTest(entry=entry):
                payload['bullets'] = [entry]
                self.path.write_text(json.dumps(payload), encoding='utf-8')
                self.assertEqual(self.make().digest(), '')

    async def test_atomic_replace_failure_preserves_previous_file_and_pending(self):
        rows = self.observe()
        before = self.path.read_bytes()
        with patch('core.channel_curator.os.replace', side_effect=OSError('fixture')):
            self.assertFalse(self.curator.save())
            complete = AsyncMock(return_value=self.response(rows))
            self.assertFalse(await self.curator.curate(complete))
            complete.assert_not_called()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.curator.pending_count, 1)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    async def test_commit_write_failure_never_consumes_snapshot(self):
        rows = self.observe()
        real_write = self.curator._write
        writes = 0

        def write(**changes):
            nonlocal writes
            writes += 1
            return False if writes == 2 else real_write(**changes)

        with patch.object(self.curator, '_write', side_effect=write):
            self.assertFalse(await self.curator.curate(AsyncMock(return_value=self.response(rows))))
        self.assertEqual(self.curator.pending_count, 1)
        self.assertEqual(self.curator.bullets, [])
        self.assertEqual(len(self.curator._pending), 1)

    def test_bad_path_is_safe(self):
        curator = ChannelCurator(self.tmp.name, clock=lambda: self.now, min_messages=1)
        self.assertTrue(curator.observe(self.row()))
        self.assertFalse(curator.save())
        self.assertEqual(curator.digest(), '')
        self.assertEqual(list(Path(self.tmp.name).glob('*.tmp')), [])


if __name__ == '__main__':
    unittest.main()
