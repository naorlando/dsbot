import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.feedback import FeedbackStore, sentiment


class SentimentTests(unittest.TestCase):
    def test_known_emojis(self):
        for emoji in ('👍', '❤️', '😂', '🔥'):
            self.assertEqual(sentiment(emoji), 1, emoji)
        for emoji in ('👎', '💩', '🤡'):
            self.assertEqual(sentiment(emoji), -1, emoji)

    def test_unknown_and_garbage(self):
        for value in ('🍕', '', None, 3, [], {}):
            self.assertEqual(sentiment(value), 0, value)


class FeedbackStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'feedback.json'
        self.store = FeedbackStore(self.path, clock=lambda: 1000, salt='test')

    def tearDown(self):
        self.directory.cleanup()

    def test_only_tracked_answers_accept_votes(self):
        self.assertFalse(self.store.knows(10))
        self.assertEqual(self.store.record(10, '👍', 'u1'), 0)
        self.assertTrue(self.store.track(10))
        self.assertTrue(self.store.knows(10))
        self.assertEqual(self.store.record(10, '👍', 'u1'), 1)

    def test_track_is_idempotent(self):
        self.store.track(10)
        self.store.track(10)
        self.assertEqual(self.store.snapshot()['answers'], 1)

    def test_same_person_cannot_double_vote(self):
        self.store.track(10)
        self.store.record(10, '👍', 'u1')
        self.store.record(10, '👍', 'u1')
        self.store.record(10, '❤️', 'u1')
        self.assertEqual(self.store.snapshot()['up'], 1)

    def test_changing_vote_replaces_it(self):
        self.store.track(10)
        self.store.record(10, '👍', 'u1')
        self.store.record(10, '👎', 'u1')
        snapshot = self.store.snapshot()
        self.assertEqual((snapshot['up'], snapshot['down'], snapshot['net']), (0, 1, -1))

    def test_unknown_emoji_is_ignored(self):
        self.store.track(10)
        self.assertEqual(self.store.record(10, '🍕', 'u1'), 0)
        self.assertEqual(self.store.snapshot()['net'], 0)

    def test_voter_hash_never_contains_the_raw_id(self):
        self.store.track(10)
        self.store.record(10, '👍', '123456789012345678')
        raw = self.path.read_text(encoding='utf-8')
        self.assertNotIn('123456789012345678', raw)

    def test_snapshot_separates_positive_and_negative_answers(self):
        self.store.track(10)
        self.store.track(11)
        self.store.track(12)
        self.store.record(10, '👍', 'u1')
        self.store.record(11, '👎', 'u2')
        snapshot = self.store.snapshot()
        self.assertEqual((snapshot['positive'], snapshot['negative'], snapshot['voted']), (1, 1, 2))
        self.assertEqual(snapshot['answers'], 3)

    def test_forget_removes_the_message_and_its_votes(self):
        self.store.track(10)
        self.store.record(10, '👍', 'u1')
        self.assertTrue(self.store.forget(10))
        self.assertIsNone(self.store.score(10))
        self.assertEqual(self.store.snapshot()['up'], 0)

    def test_bounded_answers_evict_the_oldest(self):
        for index in range(500):
            self.store.track(1000 + index)
        self.assertEqual(self.store.snapshot()['answers'], 400)
        self.assertFalse(self.store.knows(1000))
        self.assertTrue(self.store.knows(1499))

    def test_bounded_voters_per_answer(self):
        self.store.track(10)
        for index in range(100):
            self.store.record(10, '👍', f'u{index}')
        self.assertLessEqual(self.store.snapshot()['up'], 40)

    def test_persists_and_reloads(self):
        self.store.track(10)
        self.store.record(10, '👍', 'u1')
        again = FeedbackStore(self.path, clock=lambda: 1000, salt='test')
        self.assertTrue(again.knows(10))
        self.assertEqual(again.score(10), 1)

    def test_corrupt_file_loads_empty(self):
        for payload in ('{broken', '[]', 'null', '"x"', '{"answers": []}'):
            with self.subTest(payload=payload):
                self.path.write_text(payload, encoding='utf-8')
                store = FeedbackStore(self.path, clock=lambda: 1000, salt='test')
                self.assertEqual(store.snapshot()['answers'], 0)

    def test_write_failure_degrades_to_read_only(self):
        with patch.object(Path, 'mkdir', side_effect=OSError('no space')):
            self.assertFalse(self.store.track(10))
        self.assertTrue(self.store.read_only)

    def test_ids_must_be_plausible_snowflakes(self):
        for value in (0, -1, True, 'abc', None, 2 ** 70):
            with self.subTest(value=value):
                self.assertFalse(self.store.track(value))
                self.assertFalse(self.store.knows(value))

    def test_snapshot_is_content_free(self):
        self.store.track(10)
        self.store.record(10, '👎', 'u1')
        text = json.dumps(self.store.snapshot())
        self.assertNotIn('u1', text)
        self.assertNotIn('10', text.replace('"answers"', ''))


class FeedbackPathTests(unittest.TestCase):
    def test_env_override(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'custom.json'
            with patch.dict(os.environ, {'FEEDBACK_PATH': str(target)}, clear=False):
                store = FeedbackStore()
                self.assertEqual(store.path, target)


if __name__ == '__main__':
    unittest.main()
