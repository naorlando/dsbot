import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.channel_curator import ChannelCurator


class CuratorPrivacyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'curator.json'
        self.now = 1000.0
        self.curator = self.make()

    def make(self):
        return ChannelCurator(self.path, clock=lambda: self.now, min_messages=1)

    def row(self, message=1234567890123456789, channel=987654321098765432, text='Apuesto por rojo'):
        return {'fecha': '2026-10-29 12:30', 'autor': 'Ana', 'texto': text,
                'message_id': message, 'channel_id': channel}

    def public(self, row):
        return {key: row[key] for key in ('fecha', 'autor', 'texto')}

    def result(self, rows, topic='Ronda', summary='Ana apostó por rojo.'):
        return {'bullets': [{'topic': topic, 'summary': summary,
                             'evidence': [self.public(row) for row in rows]}]}

    async def store(self, rows=None, topic='Ronda'):
        rows = rows or [self.row()]
        for row in rows:
            self.assertTrue(self.curator.observe(row))
        complete = AsyncMock(return_value=self.result(rows, topic=topic))
        self.assertTrue(await self.curator.curate(complete))
        return complete

    async def test_ids_internal_only_and_reload_preserves_revocation(self):
        rows = [self.row(), self.row(222222222222222222, text='Apuesto por azul')]
        complete = await self.store(rows)
        messages = complete.call_args.kwargs['messages']
        self.assertEqual(json.loads(messages[1]['content'])['messages'],
                         [self.public(row) for row in rows])
        for row in rows:
            for key in ('message_id', 'channel_id'):
                self.assertNotIn(key, json.dumps(messages))
                self.assertNotIn(str(row[key]), json.dumps(messages))
                self.assertNotIn(str(row[key]), self.curator.digest())
        reloaded = self.make()
        self.assertEqual(reloaded.bullets, self.curator.bullets)
        self.assertEqual(reloaded.status()['revocable_bullets'], 1)
        self.assertEqual(reloaded.status()['legacy_bullets'], 0)
        for row in reloaded.bullets[0]['evidence']:
            self.assertIsInstance(row['message_id'], str)
            self.assertIsInstance(row['channel_id'], str)
        self.assertEqual(reloaded.forget_by_id(rows[1]['message_id'], rows[1]['channel_id']), 1)
        self.assertEqual(self.make().bullets, [])

    async def test_metadata_and_status_never_contain_text_or_author(self):
        await self.store()
        result = json.dumps([self.curator.metadata(), self.curator.status()])
        for text in ('Ana', 'Apuesto', 'Ronda', '2026-10-29', 'topic', 'summary', 'texto', 'autor'):
            self.assertNotIn(text, result)
        self.assertIn(str(self.row()['message_id']), json.dumps(self.curator.metadata()))
        self.assertNotIn(str(self.row()['message_id']), json.dumps(self.curator.status()))

    async def test_legacy_notes_are_not_falsely_revocable(self):
        await self.store([self.public(self.row())])
        loaded = self.make()
        self.assertEqual(loaded.status()['legacy_bullets'], 1)
        self.assertFalse(loaded.metadata()[0]['revocable'])
        self.assertEqual(loaded.metadata()[0]['sources'], [])
        self.assertEqual(loaded.invalidate_message(self.row()['message_id']), 0)
        self.assertEqual(len(self.make().bullets), 1)
        self.assertEqual(loaded.forget_author('Ana'), 1)

    async def test_mixed_legacy_and_scoped_sources_not_fully_revocable(self):
        await self.store([self.row(), self.public(self.row(text='Apuesto por azul'))])
        self.assertFalse(self.make().metadata()[0]['revocable'])
        self.assertEqual(self.curator.invalidate_message(self.row()['message_id']), 1)

    async def test_unknown_or_wrong_channel_does_not_remove_other_sources(self):
        await self.store()
        version = self.curator.status()['privacy_version']
        self.assertEqual(self.curator.invalidate_message(self.row()['message_id'], 222), 0)
        self.assertEqual(len(self.curator.bullets), 1)
        self.assertEqual(self.curator.status()['privacy_version'], version + 1)
        self.assertEqual(self.curator.invalidate_message(999), 0)
        self.assertEqual(self.curator.invalidate_message(str(self.row()['message_id'])), 1)
        self.assertEqual(self.make().bullets, [])

    async def test_edit_delete_invalidates_shared_bullet_and_pending_scope(self):
        first = self.row(111, 10)
        second = self.row(222, 10, text='Apuesto por azul')
        await self.store([first, second])
        self.curator.observe(first)
        self.curator.observe(self.row(111, 20))
        self.curator.observe(self.row(333, 10))
        self.assertEqual(self.curator.invalidate_message(111, 10), 1)
        self.assertEqual(self.curator.pending_count, 2)
        pending = [row for _, row in self.curator._pending]
        self.assertEqual([(r['message_id'], r['channel_id']) for r in pending],
                         [('111', '20'), ('333', '10')])
        self.assertEqual(self.make().bullets, [])
        self.assertEqual(self.make().status()['privacy_version'], 1)
        # An edit can now be observed with the same ID and new literal content.
        edited = self.row(111, 10, text='Apuesto por verde')
        self.assertTrue(self.curator.observe(edited))
        self.assertTrue(await self.curator.curate(AsyncMock(return_value=self.result(
            [edited], summary='Ana apostó por verde.'))))
        self.assertEqual(self.curator.bullets[0]['evidence'][0]['texto'], edited['texto'])
        self.assertEqual(self.curator.forget_by_id(111, 10), 1)

    async def test_model_cannot_inject_ids_or_change_literal_evidence(self):
        row = self.row()
        for evidence in ([row], [dict(self.public(row), texto='Apuesto por azul')],
                         [dict(self.public(row), message_id='111')]):
            with self.subTest(evidence=evidence):
                self.path.unlink(missing_ok=True)
                self.curator = self.make()
                self.curator.observe(row)
                result = self.result([row])
                result['bullets'][0]['evidence'] = evidence
                self.assertFalse(await self.curator.curate(AsyncMock(return_value=result)))
                self.assertEqual(self.curator.bullets, [])

    async def test_ambiguous_identical_literals_never_guess_provenance(self):
        self.curator.observe(self.row(111))
        self.curator.observe(self.row(222))
        self.assertFalse(await self.curator.curate(AsyncMock(return_value=self.result([self.row(111)]))))
        self.assertEqual(self.curator.bullets, [])

    def test_invalid_ids_cannot_become_legacy_sources(self):
        for value in (True, False, -1, 0, 1.5, 'bad', '', '1' * 21, '١٢٣'):
            with self.subTest(value=value):
                self.assertFalse(self.curator.observe(self.row(value)))
                self.assertFalse(self.curator.observe(self.row(channel=value)))
                self.assertEqual(self.curator.invalidate_message(value), 0)
        row = self.row()
        del row['channel_id']
        self.assertFalse(self.curator.observe(row))
        self.assertEqual(self.curator.status()['privacy_version'], 0)

    async def test_sensitive_generated_text_rejected_not_merely_scrubbed(self):
        for text in ('fixture@example.invalid', 'tel: 5551234', 'DNI: 12345678',
                     'mi dirección: Calle Falsa 123', 'password=fixture'):
            for field in ('topic', 'summary'):
                with self.subTest(text=text, field=field):
                    self.path.unlink(missing_ok=True)
                    self.curator = self.make()
                    self.curator.observe(self.row())
                    result = self.result([self.row()])
                    result['bullets'][0][field] = text
                    self.assertFalse(await self.curator.curate(AsyncMock(return_value=result)))
                    self.assertEqual(self.make().bullets, [])

    async def test_sensitive_loaded_evidence_and_summary_rejected(self):
        await self.store()
        original = json.loads(self.path.read_text(encoding='utf-8'))
        for text in ('fixture@example.invalid', 'tel: 5551234', 'DNI: 12345678',
                     'mi dirección: Calle Falsa 123', 'password=fixture'):
            for field in ('topic', 'summary', 'texto', 'autor', 'fecha'):
                with self.subTest(text=text, field=field):
                    payload = json.loads(json.dumps(original))
                    if field in ('topic', 'summary'):
                        payload['bullets'][0][field] = text
                    else:
                        payload['bullets'][0]['evidence'][0][field] = text
                    self.path.write_text(json.dumps(payload), encoding='utf-8')
                    self.assertEqual(self.make().bullets, [])
                    self.assertEqual(json.loads(self.path.read_text(encoding='utf-8'))['bullets'], [])

    async def test_personal_profiles_cannot_hide_in_literal_source_evidence(self):
        await self.store()
        original = json.loads(self.path.read_text(encoding='utf-8'))
        for text in ('Ana es irresponsable', 'Ana siempre apuesta', 'soy impulsiva',
                     'I am reckless', 'perfil de personalidad: impulsiva'):
            with self.subTest(text=text):
                self.assertFalse(self.curator.observe(self.row(text=text)))
                payload = json.loads(json.dumps(original))
                payload['bullets'][0]['evidence'][0]['texto'] = text
                self.path.write_text(json.dumps(payload), encoding='utf-8')
                self.assertEqual(self.make().bullets, [])

    async def test_inflight_invalidation_cannot_resurrect_old_message(self):
        row = self.row()
        self.curator.observe(row)
        started, release = asyncio.Event(), asyncio.Event()

        async def complete(messages, tools):
            started.set()
            await release.wait()
            return self.result([row])

        task = asyncio.create_task(self.curator.curate(complete))
        await started.wait()
        self.curator.invalidate_message(row['message_id'], row['channel_id'])
        edited = self.row(text='Apuesto por verde')
        self.curator.observe(edited)
        release.set()
        self.assertFalse(await task)
        self.assertEqual(self.curator.bullets, [])
        self.assertEqual([r['texto'] for _, r in self.curator._pending], [edited['texto']])
        self.assertEqual(self.make().bullets, [])

    async def test_persistence_failure_leaves_reload_barrier_not_stale_notes(self):
        await self.store()
        stale = self.path.read_bytes()
        with patch('core.channel_curator.os.replace', side_effect=OSError('fixture')):
            self.assertEqual(self.curator.invalidate_message(self.row()['message_id']), 1)
        self.assertEqual(self.path.read_bytes(), stale)
        self.assertTrue(self.curator.status()['read_only'])
        self.assertFalse(self.curator.status()['persisted'])
        self.assertTrue(self.curator._barrier_path.exists())
        self.assertEqual(self.curator.digest(), '')
        self.assertFalse(self.curator.observe(self.row()))
        loaded = self.make()
        self.assertEqual(loaded.digest(), '')
        self.assertTrue(loaded.status()['read_only'])
        self.assertFalse(loaded.save())

    async def test_inflight_failure_save_cannot_bypass_erasure_barrier(self):
        await self.store()
        row = self.row(text='Apuesto por azul')
        self.curator.observe(row)

        async def complete(messages, tools):
            with patch.object(self.curator, '_write', return_value=False):
                self.curator.invalidate_message(row['message_id'])
            return self.result([row])

        self.assertFalse(await self.curator.curate(complete))
        self.assertEqual(self.curator.bullets, [])
        self.assertEqual(self.make().bullets, [])
        self.assertTrue(self.make().status()['read_only'])

    async def test_author_forget_uses_same_fail_closed_barrier(self):
        await self.store()
        with patch.object(self.curator, '_write', return_value=False):
            self.assertEqual(self.curator.forget_author('Ana'), 1)
        self.assertEqual(self.make().bullets, [])

    async def test_barrier_creation_failure_deletes_stale_json(self):
        await self.store()
        self.curator._barrier_path.mkdir()  # Cannot open a directory as a marker.
        self.assertEqual(self.curator.invalidate_message(self.row()['message_id']), 1)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.make().bullets, [])

    async def test_successful_erasure_clears_barrier_and_allows_new_notes(self):
        await self.store()
        self.assertEqual(self.curator.invalidate_message(self.row()['message_id']), 1)
        self.assertFalse(self.curator._barrier_path.exists())
        self.assertFalse(self.curator.status()['read_only'])
        self.assertTrue(self.curator.status()['persisted'])
        await self.store([self.row(222, text='Apuesto por azul')])
        self.assertEqual(self.make().status()['revocable_bullets'], 1)

    async def test_marker_alone_fences_restart_after_interrupted_erasure(self):
        await self.store()
        self.curator._barrier_path.write_text('privacy erasure pending\n', encoding='ascii')
        self.assertEqual(self.make().bullets, [])
        self.assertTrue(self.make().status()['read_only'])


if __name__ == '__main__':
    unittest.main()
