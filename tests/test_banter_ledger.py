import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core.banter_ledger import TTL_SECONDS, BanterLedger


class BanterLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        dirpath = Path(self.tmp.name)
        self.path = dirpath / 'banter.json'
        self.now = 0.0
        self.ledger = BanterLedger(path=self.path, clock=lambda: self.now)

    def tearDown(self):
        self.tmp.cleanup()

    # -- add / shapes ------------------------------------------------------

    def test_add_returns_entry_persists_and_reloads(self):
        self.now = 100.0
        entry = self.ledger.add('Wire', 'se la jugó por rojo', 'apuesta')
        self.assertEqual(entry['user'], 'Wire')
        self.assertEqual(entry['what'], 'se la jugó por rojo')
        self.assertEqual(entry['label'], 'apuesta')
        self.assertEqual(entry['ts'], 100.0)
        self.assertTrue(entry['persisted'])
        self.assertFalse(entry['read_only'])
        reloaded = BanterLedger(path=self.path, clock=lambda: self.now)
        self.assertEqual(reloaded.recall(), [entry])

    def test_default_label_and_free_form_label_cap(self):
        entry = self.ledger.add('Wire', 'predijo que Boca sale campeón')
        self.assertEqual(entry['label'], 'chiste')
        self.now += 1.0
        long_label = 'x' * 90
        self.assertEqual(len(self.ledger.add('Wire', 'otra', long_label)['label']), 40)

    def test_field_caps_user_and_what(self):
        self.assertEqual(len(self.ledger.add('u' * 100, 'w' * 500)['user']), 80)
        self.assertEqual(len(self.ledger.recall()[0]['what']), 300)

    def test_rejects_empty_user_or_what(self):
        self.assertIsNone(self.ledger.add('', 'algo'))
        self.assertIsNone(self.ledger.add('Wire', '   '))
        self.assertIsNone(self.ledger.add(None, 'algo'))

    # -- caps --------------------------------------------------------------

    def test_global_cap_drops_oldest(self):
        for i in range(125):
            self.now += 1.0
            self.ledger.add(f'user{i}', f'chanza numero {i}')
        self.assertEqual(len(self.ledger.entries), 120)
        self.assertEqual(len(self.ledger.recall()), 10)
        recalled_whats = [entry['what'] for entry in self.ledger.recall()]
        self.assertEqual(recalled_whats[0], 'chanza numero 124')
        self.assertNotIn('chanza numero 0', ' '.join(recalled_whats))

    def test_per_user_cap_drops_that_users_oldest(self):
        for i in range(22):
            self.now += 1.0
            self.ledger.add('wire', f'apuesta wire {i}', 'apuesta')
        self.now += 1.0
        self.ledger.add('otro', 'chanza de otro')
        wire = self.ledger.recall('wire')
        self.assertEqual(len(wire), 10)
        self.assertEqual(wire[0]['what'], 'apuesta wire 21')
        wire_all = [entry['what'] for entry in self.ledger.entries if entry['user'] == 'wire']
        self.assertEqual(len(wire_all), 20)
        self.assertNotIn('apuesta wire 0', wire_all)
        self.assertNotIn('apuesta wire 1', wire_all)
        self.assertEqual(self.ledger.user_tally('wire'), {'apuesta': 20})
        self.assertEqual(len(self.ledger.recall('otro')), 1)

    # -- dedupe ------------------------------------------------------------

    def test_dedupe_bumps_ts_and_label_without_length(self):
        self.now = 10.0
        self.ledger.add('Wire', 'se la jugo por rojo', 'apuesta')
        self.now = 20.0
        entry = self.ledger.add(' wire  ', 'SE LA JUGO POR ROJO', 'bardeo')
        self.assertEqual(len(self.ledger.entries), 1)
        self.assertEqual(entry['ts'], 20.0)
        self.assertEqual(entry['label'], 'bardeo')
        self.assertEqual(self.ledger.recall()[0]['ts'], 20.0)

    def test_reloaded_dedupe_per_user_cap_kept_from_disk(self):
        for i in range(6):
            self.now += 1.0
            self.ledger.add('wire', f'chanza {i}', 'apuesta')
        reloaded = BanterLedger(path=self.path, clock=lambda: self.now)
        self.assertEqual(len(reloaded.recall('wire')), 6)
        reloaded.add('wire', 'CHANZA 0', 'bardeo')  # same normalised what: bump
        self.assertNotIn('chanza 0', [entry['what'] for entry in reloaded.recall('wire')])
        again = BanterLedger(path=self.path, clock=lambda: self.now)
        self.assertEqual(reloaded.entries, again.entries)

    # -- persistence: corrupt + read-only ---------------------------------

    def test_corrupt_file_loads_empty_and_recovers(self):
        self.path.write_text('{truncated json...', encoding='utf-8')
        broken = BanterLedger(path=self.path, clock=lambda: self.now)
        self.assertEqual(broken.recall(), [])
        self.assertEqual(broken.digest(), '')
        self.assertIsNone(broken.add('', 'x'))
        self.assertIsNone(broken.add('wire', ''))
        entry = broken.add('wire', 'volvió a la carga', 'bardeo')
        self.assertIsNotNone(entry)
        self.assertEqual(BanterLedger(path=self.path, clock=lambda: self.now).recall(), [entry])

    def test_entries_without_a_list_are_empty(self):
        self.path.write_text('{"entries": "no es lista"}', encoding='utf-8')
        self.assertEqual(BanterLedger(path=self.path, clock=lambda: self.now).recall(), [])

    def test_write_failure_degrades_to_read_only(self):
        # Point the ledger at the directory itself: every write attempt fails
        # (os.replace over a directory can never succeed), no false success.
        self.ledger = BanterLedger(path=self.tmp.name, clock=lambda: self.now)
        self.assertIsNone(self.ledger.add('', 'x'))
        entry = self.ledger.add('wire', 'se la jugó, fail-closed', 'apuesta')
        self.assertIsNotNone(entry)
        self.assertFalse(entry['persisted'])
        self.assertTrue(entry['read_only'])
        self.assertEqual(self.ledger.recall(), [])
        self.assertTrue(self.ledger.read_only)
        again = self.ledger.add('wire', 'otra más')
        self.assertFalse(again['persisted'])
        self.assertTrue(again['read_only'])
        self.assertEqual(self.ledger.recall(), [])
        leftovers = [name for name in Path(self.tmp.name).iterdir()]
        self.assertEqual(leftovers, [])

    def test_failed_update_preserves_existing_durable_entry(self):
        original = self.ledger.add('wire', 'una apuesta', 'apuesta')
        self.now += 10
        with patch('core.banter_ledger.os.replace', side_effect=OSError('disk unavailable')):
            result = self.ledger.add('wire', 'una apuesta', 'bardeo')
        self.assertFalse(result['persisted'])
        self.assertTrue(result['read_only'])
        recalled = self.ledger.recall()[0]
        self.assertEqual(recalled['label'], original['label'])
        self.assertEqual(recalled['ts'], original['ts'])
        self.assertTrue(recalled['persisted'])
        self.assertTrue(recalled['read_only'])
        reloaded = BanterLedger(self.path, clock=lambda: self.now)
        self.assertEqual(reloaded.entries, self.ledger.entries)

    def test_default_clock_is_unix_time_and_survives_restart(self):
        ledger = BanterLedger(self.path)
        before = time.time()
        entry = ledger.add('wire', 'una apuesta')
        self.assertGreaterEqual(entry['ts'], before)
        self.assertLessEqual(entry['ts'], time.time())
        self.assertEqual(BanterLedger(self.path).recall(), [entry])

    def test_default_clock_discards_legacy_uptime_and_implausible_rows(self):
        now = time.time()
        rows = [{'user': 'wire', 'what': str(ts), 'ts': ts}
                for ts in (100.0, 0, None, True, float('nan'), float('inf'), 10**400,
                           now + 100, now - TTL_SECONDS, now)]
        self.path.write_text(json.dumps({'version': 1, 'entries': rows}), encoding='utf-8')
        loaded = BanterLedger(self.path)
        self.assertEqual([row['ts'] for row in loaded.recall()], [now])
        disk = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(disk['version'], 2)
        self.assertEqual(len(disk['entries']), 1)

    def test_load_persists_scrubbing_and_drops_extra_fields(self):
        self.path.write_text(json.dumps({'version': 1, 'entries': [{
            'user': 'wire', 'what': 'mirá https://example.com', 'label': 'chiste',
            'ts': self.now, 'raw_text': 'not retained'}]}), encoding='utf-8')
        loaded = BanterLedger(self.path, clock=lambda: self.now)
        self.assertTrue(loaded.recall()[0]['persisted'])
        raw = self.path.read_text(encoding='utf-8')
        self.assertNotIn('example.com', raw)
        self.assertNotIn('raw_text', raw)

    def test_load_cleanup_failure_does_not_claim_sanitized_snapshot_persisted(self):
        self.path.write_text(json.dumps({'version': 1, 'entries': [{
            'user': 'wire', 'what': 'mirá https://example.com', 'label': 'chiste',
            'ts': self.now}]}), encoding='utf-8')
        with patch('core.banter_ledger.os.replace', side_effect=OSError('disk unavailable')):
            loaded = BanterLedger(self.path, clock=lambda: self.now)
        row = loaded.recall()[0]
        self.assertNotIn('https://', row['what'])
        self.assertFalse(row['persisted'])
        self.assertTrue(row['read_only'])

    def test_injected_zero_based_clock_is_preserved_on_load(self):
        self.ledger.add('wire', 'at fake zero')
        self.assertEqual(BanterLedger(self.path, clock=lambda: 0.0).recall()[0]['ts'], 0.0)

    def test_ttl_hides_expired_rows_in_all_read_apis_and_purges_disk(self):
        self.ledger.add('wire', 'temporal', 'apuesta')
        self.now = TTL_SECONDS
        self.assertEqual(self.ledger.recall(), [])
        self.assertEqual(self.ledger.digest(), '')
        self.assertEqual(self.ledger.user_tally('wire'), {})
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8'))['entries'], [])

    def test_ttl_applies_on_load_and_on_writes(self):
        self.ledger.add('wire', 'vieja')
        self.now = TTL_SECONDS
        self.assertEqual(BanterLedger(self.path, clock=lambda: self.now).recall(), [])
        self.ledger.add('wire', 'nueva')
        self.assertEqual([row['what'] for row in self.ledger.recall()], ['nueva'])

    def test_ttl_still_hides_expired_rows_when_cleanup_cannot_persist(self):
        self.ledger.add('wire', 'temporal')
        self.now = TTL_SECONDS
        with patch('core.banter_ledger.os.replace', side_effect=OSError('disk unavailable')):
            self.assertEqual(self.ledger.recall(), [])
        self.assertTrue(self.ledger.read_only)
        self.assertEqual(self.ledger.digest(), '')
        self.assertEqual(self.ledger.user_tally('wire'), {})

    def test_forget_is_scoped_case_insensitive_and_durable(self):
        self.ledger.add('Wire', 'primera')
        self.ledger.add('wire', 'segunda')
        self.ledger.add('pino', 'conservar')
        result = self.ledger.forget(' WIRE ')
        self.assertEqual(result, {'deleted': 2, 'persisted': True, 'read_only': False})
        self.assertEqual(self.ledger.recall('wire'), [])
        loaded = BanterLedger(self.path, clock=lambda: self.now)
        self.assertEqual([row['user'] for row in loaded.recall()], ['pino'])
        self.assertEqual(loaded.forget('unknown')['deleted'], 0)

    def test_forget_failure_reports_no_durable_deletion(self):
        self.ledger.add('wire', 'una apuesta')
        with patch('core.banter_ledger.os.replace', side_effect=OSError('disk unavailable')):
            result = self.ledger.forget('wire')
        self.assertEqual(result, {'deleted': 0, 'persisted': False, 'read_only': True})
        self.assertEqual(len(self.ledger.recall('wire')), 1)
        self.assertFalse(self.ledger.forget('wire')['persisted'])
        self.assertEqual(len(BanterLedger(self.path, clock=lambda: self.now).recall('wire')), 1)

    def test_invalid_forget_does_not_remove_any_user(self):
        self.ledger.add('wire', 'una apuesta')
        for user in (None, '', '   ', 123):
            self.assertFalse(self.ledger.forget(user)['persisted'])
        self.assertEqual(len(self.ledger.recall()), 1)

    # -- recall ------------------------------------------------------------

    def test_recall_order_limit_and_user_scope(self):
        for i in range(15):
            self.now += 1.0
            self.ledger.add('wire' if i % 2 else 'pino', f'dijo {i}', 'chiste')
        global_recall = self.ledger.recall()
        self.assertEqual(len(global_recall), 10)
        self.assertEqual(global_recall[0]['what'], 'dijo 14')
        self.assertEqual(global_recall[-1]['what'], 'dijo 5')
        wire = self.ledger.recall('WIRE')
        self.assertEqual([entry['what'] for entry in wire][:2], ['dijo 13', 'dijo 11'])
        self.assertEqual(len(wire), 7)
        self.assertEqual(self.ledger.recall('nadie'), [])

    # -- digest ------------------------------------------------------------

    def test_digest_empty_is_empty(self):
        self.assertEqual(self.ledger.digest(), '')

    def test_digest_format_with_labels_and_days(self):
        self.ledger.add('Pino', 'dijo que Boca salía campeón', 'predicción')
        self.now += 86400.0
        self.ledger.add('Wire', 'se la jugó por rojo', 'apuesta')
        self.now += 172800.0
        digest = self.ledger.digest()
        self.assertTrue(digest.startswith('Cosas que se dijeron para bardear (últimas):'))
        self.assertIn('- [apuesta] Wire: se la jugó por rojo (hace 2 días)', digest)
        self.assertIn('- [predicción] Pino: dijo que Boca salía campeón (hace 3 días)', digest)
        self.assertLess(digest.index('[apuesta]'), digest.index('[predicción]'))

    def test_digest_singular_day_and_less_than_one(self):
        self.ledger.add('Wire', 'recién agregada', 'chiste')
        self.assertIn('(menos de un día)', self.ledger.digest())
        self.now += 86400.0
        self.ledger.add('Pino', 'de ayer', 'bardeo')
        self.assertIn('(hace 1 día)', self.ledger.digest())
        self.assertIn('(menos de un día)', self.ledger.digest())

    def test_digest_char_cap_without_broken_lines(self):
        for i in range(20):
            self.now += 1.0
            self.ledger.add(f'user{i}', 'chanza ' + 'x' * 200)
        digest = self.ledger.digest(max_chars=400)
        self.assertLessEqual(len(digest), 400)
        for line in digest.splitlines():
            self.assertTrue(line.startswith('- ') or line.startswith('Cosas'))
            self.assertLess(len(line), 250)

    # -- tally -------------------------------------------------------------

    def test_user_tally_counts_per_label(self):
        for what, label in (('a', 'apuesta'), ('b', 'apuesta'), ('c', 'bardeo')):
            self.now += 1.0
            self.ledger.add('wire', what, label)
        self.now += 1.0
        self.ledger.add('pino', 'd', 'chiste')
        self.assertEqual(self.ledger.user_tally('wire'), {'apuesta': 2, 'bardeo': 1})
        self.assertEqual(self.ledger.user_tally('WIRE'), {'apuesta': 2, 'bardeo': 1})
        self.assertEqual(self.ledger.user_tally('pino'), {'chiste': 1})
        self.assertEqual(self.ledger.user_tally('nadie'), {})

    # -- privacy scrubbing -------------------------------------------------

    def test_secrets_urls_and_mentions_scrubbed(self):
        self.now = 5.0
        entry = self.ledger.add(
            'wire',
            'dijo sk-or-v1-abcdefgh123456 que mirá https://example.com/la-apuesta @everyone')
        self.assertNotIn('sk-or-v1-abcdefgh123456', entry['what'])
        self.assertNotIn('https://', entry['what'])
        self.assertNotIn('@everyone', entry['what'])
        self.assertIn('[clave omitida]', entry['what'])
        self.assertIn('[enlace omitido]', entry['what'])
        self.assertIn('[mención]', entry['what'])
        raw = json.loads(self.path.read_text(encoding='utf-8'))
        dumped = json.dumps(raw, ensure_ascii=False)
        self.assertNotIn('sk-or-v1-abcdefgh123456', dumped)
        self.assertNotIn('example.com', dumped)

    def test_scrubbing_survives_reload(self):
        self.ledger.add('wire', 'clave tvly-dev-abcdefghijklmnop pegada', 'bardeo')
        reloaded = BanterLedger(path=self.path, clock=lambda: self.now)
        recalled = reloaded.recall()[0]['what']
        self.assertNotIn('tvly-dev-abcdefghijklmnop', recalled)
        self.assertIn('[clave omitida]', recalled)


if __name__ == '__main__':
    unittest.main()
