import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from core.assistant_history import MAX_MESSAGES, MAX_ROWS, _row_from, keywords, scan_history

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
        self.yielded = 0

    def history(self, limit=None, oldest_first=False):
        self.seen_limits.append(limit)
        async def flow():
            for row in self._rows:
                self.yielded += 1
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

    def test_multi_query_or_and_accents(self):
        self.assertEqual(keywords("One Piece OR Japón | LoL"), ["one", "piece", "japon", "lol"])


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
        channel = FakeChannel([message("csgo ayer", "Nano", days_ago=days) for days in range(40)])
        result = await scan_history(channel, "el csgo de ayer", now=NOW, limit=100)
        self.assertEqual(result["scanned"], 32)  # includes day 30, stops at day 31
        self.assertEqual(result["window_days"], 30)
        self.assertEqual(len(result["matches"]), 12)
        self.assertEqual(result["matches"][0]["texto"], "csgo ayer")

    async def test_discord_error_fails_open(self):
        broken = MagicMock()
        broken.history = MagicMock(side_effect=RuntimeError("discord down"))
        result = await scan_history(broken, "csgo", now=NOW)
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["scan_error"], "discord_error")
        self.assertTrue(result["truncated"])

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

    async def test_names_are_searchable_with_accents(self):
        channel = FakeChannel([message("sale una partida", "Nánó", 1)])
        result = await scan_history(channel, "nano", now=NOW)
        self.assertEqual(result["matches"][0]["autor"], "Nánó")

    async def test_full_phrase_ranks_above_separate_words(self):
        channel = FakeChannel([
            message("one episodio y otra piece", "A", 0),
            message("me gusta One Piece", "B", 1),
            message("JAPÓN estuvo genial", "C", 2),
        ])
        result = await scan_history(channel, "one piece OR japon", now=NOW)
        self.assertEqual([row["autor"] for row in result["matches"]], ["B", "A", "C"])

    async def test_alternative_queries_and_refinements(self):
        rows = [message("viajé a Japón", "A"), message("miramos one piece", "B"), message("csgo", "C")]
        for separator in (" OR ", " | ", ", ", "; ", "\n"):
            with self.subTest(separator=separator):
                result = await scan_history(FakeChannel(rows), "one piece" + separator + "japon", now=NOW)
                self.assertEqual({row["autor"] for row in result["matches"]}, {"A", "B"})
        refined = await scan_history(FakeChannel(rows), "japón", now=NOW)
        self.assertEqual([row["autor"] for row in refined["matches"]], ["A"])

    async def test_normalized_token_boundaries_not_substrings(self):
        channel = FakeChannel([
            message("lola juega", "Dolores"),
            message("LÓL!", "A"),
            message("prelolpost", "B"),
            message("¿lol?", "C"),
            message("lol2", "D"),
            message("ñlolá", "E"),
        ])
        result = await scan_history(channel, "lol", now=NOW)
        self.assertEqual([row["autor"] for row in result["matches"]], ["A", "C"])

    async def test_searches_full_text_not_only_excerpt(self):
        channel = FakeChannel([message("antes " * 40 + "Japón")])
        result = await scan_history(channel, "japon", now=NOW)
        self.assertEqual(len(result["matches"]), 1)
        self.assertLessEqual(len(result["matches"][0]["texto"]), 160)

    async def test_commands_are_not_context_even_when_query_matches(self):
        channel = FakeChannel([
            message("!boton one piece", "A"),
            message(" \n !boton japon", "B"),
            message("one piece", "Bot", bot=True),
            message("one piece", "Persona"),
        ])
        result = await scan_history(channel, "one piece japon", now=NOW)
        self.assertEqual([row["autor"] for row in result["matches"]], ["Persona"])

    async def test_hard_message_cap_even_if_adapter_ignores_limit(self):
        for limit in (None, MAX_MESSAGES + 9000, "invalid", float("inf")):
            with self.subTest(limit=limit):
                channel = FakeChannel([message("csgo")] * (MAX_MESSAGES + 20))
                result = await scan_history(channel, "csgo", now=NOW, limit=limit)
                self.assertEqual(channel.seen_limits, [1000])
                self.assertEqual(result["scanned"], 1000)
                self.assertEqual(channel.yielded, 1000)
                self.assertEqual(len(result["matches"]), MAX_ROWS)
                self.assertTrue(result["truncated"])

    async def test_smaller_requested_limit(self):
        channel = FakeChannel([message("csgo")] * 20)
        result = await scan_history(channel, "csgo", now=NOW, limit=3)
        self.assertEqual(channel.seen_limits, [3])
        self.assertEqual(channel.yielded, 3)
        self.assertEqual(len(result["matches"]), 3)
        self.assertTrue(result["truncated"])

    async def test_zero_and_negative_limits_never_scan_unbounded(self):
        for limit in (0, -1):
            channel = FakeChannel([message("csgo")])
            result = await scan_history(channel, "csgo", now=NOW, limit=limit)
            self.assertEqual(result["scanned"], 0)
            self.assertEqual(channel.seen_limits, [])
            self.assertTrue(result["truncated"])

    async def test_successful_no_matches_is_not_an_error(self):
        result = await scan_history(FakeChannel([message("otra cosa")]), "csgo", now=NOW)
        self.assertEqual(result["matches"], [])
        self.assertIsNone(result["scan_error"])
        self.assertFalse(result["truncated"])

    async def test_missing_history_is_reported(self):
        result = await scan_history(None, "csgo", now=NOW)
        self.assertEqual(result["scan_error"], "history_unavailable")

    async def test_permission_errors_are_distinct_and_do_not_leak_details(self):
        forbidden = type("Forbidden", (Exception,), {})
        http_error = RuntimeError("secret auth details")
        http_error.status = 403
        for error in (PermissionError("private token"), forbidden("private"), http_error):
            channel = MagicMock()
            channel.history.side_effect = error
            result = await scan_history(channel, "csgo", now=NOW)
            self.assertEqual(result["scan_error"], "permission_denied")
            self.assertNotIn(str(error), str(result))
            self.assertEqual(result["matches"], [])

    async def test_partial_scan_preserves_matches_and_reports_error(self):
        class InterruptedChannel:
            def history(self, **kwargs):
                async def flow():
                    yield message("csgo", days_ago=2)
                    raise PermissionError("no access")
                return flow()
        result = await scan_history(InterruptedChannel(), "csgo", now=NOW)
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["scanned"], 1)
        self.assertEqual(result["scan_error"], "permission_denied")
        self.assertTrue(result["truncated"])

    async def test_date_metadata_covers_scan_not_only_matches(self):
        channel = FakeChannel([
            message("unmatched", days_ago=1),
            message("csgo", days_ago=5),
            message("unmatched", days_ago=30),
            message("too old", days_ago=31),
        ])
        result = await scan_history(channel, "csgo", now=NOW)
        self.assertEqual(result["min_date"], (NOW - timedelta(days=30)).isoformat())
        self.assertEqual(result["max_date"], (NOW - timedelta(days=1)).isoformat())
        self.assertFalse(result["truncated"])

    async def test_missing_dates_are_skipped_not_scan_stoppers(self):
        missing = message("csgo")
        missing.created_at = None
        result = await scan_history(FakeChannel([missing, message("csgo")]), "csgo", now=NOW)
        self.assertEqual(len(result["matches"]), 1)

    async def test_default_now_still_enforces_thirty_days(self):
        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return NOW
        with patch("core.assistant_history.datetime", FrozenDatetime):
            recent = message("csgo", days_ago=20)
            old = message("csgo", days_ago=31)
            recent.created_at = FrozenDatetime.fromisoformat(recent.created_at.isoformat())
            old.created_at = FrozenDatetime.fromisoformat(old.created_at.isoformat())
            result = await scan_history(FakeChannel([recent, old]), "csgo")
        self.assertEqual(len(result["matches"]), 1)


class SanitizationTests(unittest.TestCase):
    def test_redacts_mentions_and_urls_in_text_and_author(self):
        value = "https://private.test/x www.private.test @everyone @here <@123> <@!456> <@&789> <#123> @nano"
        row = _row_from(message("csgo " + value, value))
        for field in ("autor", "texto"):
            self.assertNotIn("private.test", row[field])
            self.assertNotIn("@", row[field])
            self.assertNotIn("123", row[field])
            self.assertIn("[enlace]", row[field])
            self.assertIn("[mención]", row[field])

    def test_redacts_credentials_in_text_and_author(self):
        secrets = [
            "A" * 24 + "." + "b" * 6 + "." + "C" * 38,
            "mfa." + "a" * 80,
            "sk-proj-" + "a" * 30,
            "ghp_" + "a" * 30,
            'api_key="private value"',
            "token=private_token",
            "Authorization: Bearer private_auth",
            '"password": "private_password"',
        ]
        for secret in secrets:
            with self.subTest(secret=secret):
                row = _row_from(message("csgo " + secret, secret))
                for field in ("autor", "texto"):
                    self.assertNotIn(secret, row[field])
                    self.assertNotIn("private", row[field])
                    self.assertIn("[secreto]", row[field])

    def test_secret_is_redacted_before_excerpt_truncation(self):
        token = "A" * 24 + "." + "b" * 6 + "." + "C" * 38
        row = _row_from(message("x" * 150 + " " + token, "x" * 55 + " " + token))
        self.assertNotIn("A", row["texto"])
        self.assertNotIn("A", row["autor"])

    def test_row_builder_rejects_bots_commands_and_missing_data(self):
        for row in (message("hi", bot=True), message(" \n!boton hi"),
                    message("hi", author=" "), message("  ")):
            self.assertIsNone(_row_from(row))


if __name__ == "__main__":
    unittest.main()
