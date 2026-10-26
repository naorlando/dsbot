import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from core.assistant_history import keywords, scan_history

NOW = datetime(2026, 10, 25, 21, 0, tzinfo=timezone.utc)


def message(text, author="Nano", days_ago=0, bot=False):
    author_mock = MagicMock()
    author_mock.display_name = author
    author_mock.bot = bot
    row = MagicMock()
    row.author = author_mock
    row.created_at = NOW - timedelta(days=days_ago)
    row.content = text
    return row


class FakeChannel:
    def __init__(self, rows):
        self._rows = rows
        self.seen_limits = []

    def history(self, limit=None, oldest_first=False):
        self.seen_limits.append(limit)
        async def flow():
            for row in self._rows:
                yield row
        return flow()


class KeywordsTests(unittest.TestCase):
    def test_fold_and_stopwords(self):
        # "cuando" and "fue" are stopwords; only meaningful words survive
        self.assertEqual(keywords("¿Cuándo fue el DOOM de julio?"), ["doom", "julio"])

    def test_short_or_empty_question(self):
        for question in ("", "  ", "qué", None):
            self.assertEqual(keywords(question), [])

    def test_bounded_tokens(self):
        tokens = keywords(" ".join(f"palabra{i}" for i in range(20)))
        self.assertEqual(len(tokens), 6)


class ScanTests(unittest.IsolatedAsyncioTestCase):
    async def test_matches_rows_with_date_author_snippet(self):
        channel = FakeChannel([
            message("jugamos al CSGO tertulio re brutal", "Nano", 2),
            message("no tengo idea qué me contás", "Otro", 1),
            message("recordá que el sábado jugamos CSGO", "Fer", 3),
        ])
        result = await scan_history(channel, "cuándo jugamos csgo?", now=NOW)
        self.assertEqual(len(result["matches"]), 2)
        self.assertEqual(result["matches"][0]["autor"], "Nano")
        self.assertIn("CSGO", result["matches"][0]["texto"])
        self.assertLessEqual(len(result["matches"][0]["texto"]), 200)

    async def test_bots_commands_links_and_empty_skipped(self):
        channel = FakeChannel([
            message("csgo https://spam.test/x", "Nano", 1),
            message("csgo", "RoboBot", 1, bot=True),
            message("!topvoice", "Nano", 1),
            message("   ", "Nano", 1),
            message("hablando de csgo normal", "Fer", 1),
        ])
        result = await scan_history(channel, "csgo", now=NOW)
        self.assertEqual(len(result["matches"]), 2)
        self.assertNotIn("spam.test", result["matches"][0]["texto"])
        self.assertIn("[enlace]", result["matches"][0]["texto"])

    async def test_window_is_hard_bounded(self):
        channel = FakeChannel([message("csgo ayer", "Nano", days_ago=days) for days in range(30)])
        result = await scan_history(channel, "el csgo de ayer", now=NOW, limit=100)
        self.assertEqual(result["scanned"], 16)  # stops right past the 14-day window
        self.assertEqual(result["matches"][0]["texto"], "csgo ayer")

    async def test_discord_error_fails_open(self):
        broken = MagicMock()
        broken.history = MagicMock(side_effect=RuntimeError("discord down"))
        result = await scan_history(broken, "csgo", now=NOW)
        self.assertEqual(result["matches"], [])

    async def test_no_channel_or_no_keywords(self):
        self.assertEqual((await scan_history(None, "csgo"))["matches"], [])
        channel = FakeChannel([message("csgo", "Nano", 1)])
        self.assertEqual((await scan_history(channel, "qué"))["matches"], [])
        self.assertEqual(channel.seen_limits, [])  # never even pages Discord

    async def test_rows_never_contain_ids_or_attatchments(self):
        channel = FakeChannel([message("jugamos csgo el otro día", "Nano", 0)])
        result = await scan_history(channel, "csgo", now=NOW)
        self.assertEqual(set(result["matches"][0]), {"fecha", "autor", "texto"})

    async def test_mentions_anonymized(self):
        channel = FakeChannel([message("@everyone @here pasando a decir csgo", "Nano", 0)])
        result = await scan_history(channel, "csgo", now=NOW)
        self.assertIn("[mención]", result["matches"][0]["texto"])
        self.assertNotIn("@", result["matches"][0]["texto"])


if __name__ == "__main__":
    unittest.main()
