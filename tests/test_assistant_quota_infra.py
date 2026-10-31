import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.assistant_quota import QuotaError, UserDailyQuota


class UserDailyQuotaTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'AI_QUOTA_KEY': 'synthetic-quota-key-never-live'})
        env.start()
        self.addCleanup(env.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'quota.json'
        self.now = datetime(2026, 1, 10, 12, tzinfo=timezone.utc)
        self.quota = UserDailyQuota(self.path)

    def test_default_exhaustion_persists_across_instances(self):
        for remaining in reversed(range(40)):
            self.assertEqual(self.quota.consume(12345, self.now), remaining)
        with self.assertRaises(QuotaError) as error:
            UserDailyQuota(self.path).consume(12345, self.now)
        self.assertEqual(error.exception.reason, 'exhausted')
        self.assertEqual(self.quota.snapshot(self.now), {'limit': 40, 'used': 40, 'users': 1})

    def test_users_are_independent_and_string_id_cannot_bypass(self):
        quota = UserDailyQuota(self.path, limit=1)
        quota.consume(123, self.now)
        with self.assertRaises(QuotaError):
            quota.consume('123', self.now)
        self.assertEqual(quota.consume(456, self.now), 0)

    def test_utc_rollover_and_backward_clock_no_reset_even_after_restart(self):
        quota = UserDailyQuota(self.path, limit=1)
        quota.consume('u', self.now)
        with self.assertRaises(QuotaError):
            quota.consume('u', self.now - timedelta(days=1))
        tomorrow = self.now + timedelta(days=1)
        self.assertEqual(quota.consume('u', tomorrow), 0)
        restarted = UserDailyQuota(self.path, limit=1)
        with self.assertRaises(QuotaError):
            restarted.consume('u', self.now)
        with self.assertRaises(QuotaError):
            restarted.consume('u', tomorrow)
        self.assertEqual(restarted.consume('u', tomorrow + timedelta(days=1)), 0)

    def test_timezone_uses_utc_day_and_timestamp_works(self):
        quota = UserDailyQuota(self.path, limit=1)
        midnight = datetime(2026, 1, 11, tzinfo=timezone.utc)
        quota.consume('u', midnight - timedelta(seconds=1))
        self.assertEqual(quota.consume('u', midnight.timestamp()), 0)
        same_day = midnight.astimezone(timezone(timedelta(hours=-3)))
        with self.assertRaises(QuotaError):
            quota.consume('u', same_day)

    def test_snapshot_does_not_write_or_consume_or_persist_rollover(self):
        self.quota.consume('u', self.now)
        before = self.path.read_bytes()
        with patch('core.assistant_quota.os.replace', side_effect=AssertionError('read must not write')):
            for _ in range(10):
                self.assertEqual(self.quota.snapshot(self.now)['used'], 1)
            self.assertEqual(self.quota.snapshot(self.now + timedelta(days=1)),
                             {'limit': 40, 'used': 0, 'users': 0})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.quota.consume('u', self.now), 38)

    def test_capacity_fails_closed_without_evicting_users(self):
        quota = UserDailyQuota(self.path, limit=2, max_entries=2)
        quota.consume('first', self.now)
        quota.consume('second', self.now)
        before = self.path.read_bytes()
        with self.assertRaises(QuotaError) as error:
            quota.consume('third', self.now)
        self.assertEqual(error.exception.reason, 'capacity')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(quota.consume('first', self.now), 0)
        with self.assertRaises(QuotaError):
            quota.consume('first', self.now)
        self.assertEqual(quota.consume('third', self.now + timedelta(days=1)), 1)

    def test_confidentiality_hmac_secret_stable_per_install_and_not_exported(self):
        identity = 'private-discord-identity-9876543210'
        self.quota.consume(identity, self.now)
        text = self.path.read_text(encoding='utf-8')
        self.assertNotIn(identity, text)
        state = json.loads(text)
        digest = next(iter(state['users']))
        self.assertRegex(digest, '^[0-9a-f]{64}$')
        UserDailyQuota(self.path).consume(identity, self.now)
        self.assertEqual(list(json.loads(self.path.read_bytes())['users']), [digest])
        second_path = Path(self.directory.name) / 'other.json'
        second = UserDailyQuota(second_path)
        second.consume(identity, self.now)
        self.assertNotIn(digest, json.loads(second_path.read_bytes())['users'])
        snapshot = json.dumps(self.quota.snapshot(self.now))
        self.assertNotIn('synthetic-quota-key-never-live', text)
        self.assertNotIn('secret', state)
        for private in (identity, digest, state['salt'], state['key_check']):
            self.assertNotIn(private, snapshot)
        self.assertEqual(set(self.quota.snapshot(self.now)), {'limit', 'used', 'users'})

    def test_corrupt_file_fails_closed_constructor_consume_and_snapshot(self):
        for data in (b'not json', b'{}', b'[]', b'\xff', b'x' * 262145):
            with self.subTest(data=data[:20]):
                self.path.write_bytes(data)
                for action in (lambda: UserDailyQuota(self.path),
                               lambda: self.quota.consume('u', self.now),
                               lambda: self.quota.snapshot(self.now)):
                    with self.assertRaises(QuotaError) as error:
                        action()
                    self.assertEqual(error.exception.reason, 'storage')
                    self.assertNotIn(str(self.path), str(error.exception))
                self.assertEqual(self.path.read_bytes(), data)

    def test_malformed_state_and_duplicate_fields_fail_closed(self):
        original = json.loads(self.path.read_bytes())
        variants = [dict(original, version=True), dict(original, salt='short'),
                    dict(original, day='2026-99-10'), dict(original, users={'raw-id': 1}),
                    dict(original, users={'a' * 64: True}),
                    dict(original, users={'a' * 64: -1})]
        for state in variants:
            self.path.write_text(json.dumps(state), encoding='utf-8')
            with self.assertRaises(QuotaError):
                self.quota.consume('u', self.now)
        self.path.write_text('{"version":1,"version":1}', encoding='utf-8')
        with self.assertRaises(QuotaError):
            UserDailyQuota(self.path)

    def test_missing_file_after_initialization_fails_closed(self):
        self.quota.consume('u', self.now)
        self.path.unlink()
        with self.assertRaises(QuotaError):
            self.quota.consume('u', self.now)
        with self.assertRaises(QuotaError):
            self.quota.snapshot(self.now)
        self.assertFalse(self.path.exists())

    def test_atomic_replace_failure_preserves_previous_state_and_cleans_temp(self):
        self.quota.consume('u', self.now)
        before = self.path.read_bytes()
        with patch('core.assistant_quota.os.replace', side_effect=OSError('secret storage path')):
            with self.assertRaises(QuotaError) as error:
                self.quota.consume('u', self.now)
            self.assertEqual(error.exception.reason, 'storage')
            self.assertNotIn('secret storage path', str(error.exception))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('.assistant-quota-*.tmp')), [])
        self.assertEqual(self.quota.snapshot(self.now)['used'], 1)

    def test_fsync_failure_denies_consumption_preserves_state(self):
        before = self.path.read_bytes()
        with patch('core.assistant_quota.os.fsync', side_effect=OSError('disk failure')):
            with self.assertRaises(QuotaError):
                self.quota.consume('u', self.now)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('.assistant-quota-*.tmp')), [])

    def test_initial_write_failure_fails_closed(self):
        path = Path(self.directory.name) / 'new.json'
        with patch('core.assistant_quota.os.replace', side_effect=PermissionError):
            with self.assertRaises(QuotaError):
                UserDailyQuota(path)
        self.assertFalse(path.exists())

    def test_atomic_write_same_directory_and_private_permissions(self):
        real_replace = os.replace
        calls = []

        def replace(source, destination):
            self.assertEqual(Path(source).parent, self.path.parent)
            self.assertEqual(Path(destination), self.path)
            json.loads(Path(source).read_bytes())
            calls.append(True)
            real_replace(source, destination)

        with patch('core.assistant_quota.os.replace', side_effect=replace):
            self.quota.consume('u', self.now)
        self.assertEqual(calls, [True])
        if os.name != 'nt':
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_concurrent_instances_do_not_lose_consumption(self):
        quotas = [UserDailyQuota(self.path, limit=20) for _ in range(3)]

        def consume(index):
            try:
                quotas[index % len(quotas)].consume('u', self.now)
                return True
            except QuotaError:
                return False

        with ThreadPoolExecutor(max_workers=8) as pool:
            admitted = list(pool.map(consume, range(50)))
        self.assertEqual(sum(admitted), 20)
        self.assertEqual(self.quota.snapshot(self.now)['used'], 20)

    def test_invalid_identity_and_clock_raise_safe_errors(self):
        for identity in (None, True, object(), '', 'x' * 257, '\ud800'):
            with self.assertRaises(QuotaError) as error:
                self.quota.consume(identity, self.now)
            self.assertEqual(error.exception.reason, 'identity')
        for now in ('not a clock', float('inf'), float('nan')):
            with self.assertRaises(QuotaError) as error:
                self.quota.consume('u', now)
            self.assertEqual(error.exception.reason, 'clock')
        self.assertEqual(self.quota.snapshot(self.now)['used'], 0)

    def test_key_rotation_never_grants_a_second_quota_that_day(self):
        self.quota.consume('u', self.now)
        with patch.dict(os.environ, {'AI_QUOTA_KEY': 'different-synthetic-env-key'}):
            restarted = UserDailyQuota(self.path)
            with self.assertRaises(QuotaError):
                restarted.consume('u', self.now)
            self.assertEqual(restarted.consume('u', self.now + timedelta(days=1)), 39)

    def test_missing_environment_secret_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(QuotaError):
                UserDailyQuota(self.path)

    def test_configuration_caps_and_usage_rejects_bool(self):
        for options in ({'max_entries': 1025}, {'max_entries': 0},
                        {'limit': 0}, {'limit': True}):
            with self.assertRaises(ValueError):
                UserDailyQuota(self.path, **options)


if __name__ == '__main__':
    unittest.main()
