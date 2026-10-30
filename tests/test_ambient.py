import re
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from core.ambient import ambient

NOW = datetime(2026, 10, 25, 21, 0, tzinfo=timezone.utc)
ROW_DATE = re.compile(r"^\d{2}-\d{2} \d{2}:\d{2} \S+: ")


def message(text, author="Nano", days_ago=0, bot=False, mentions=None, reference=None):
    author_mock = MagicMock()
    author_mock.display_name = author
    author_mock.bot = bot
    row = MagicMock()
    row.author = author_mock
    row.created_at = NOW - timedelta(days=days_ago)
    row.content = text
    row.mentions = mentions if mentions is not None else []
    row.reference = reference
    return row


class DigestTests(unittest.TestCase):
    def test_digest_builds_block(self):
        block = ambient([
            message("jugamos al CSGO re brutal", "Nano", days_ago=3),
            message("dale, el CSGO a las diez", "Fer", days_ago=2),
            message("punto, nos vemos ahí", "Nano", days_ago=1),
        ], now=NOW)
        self.assertTrue(block.startswith("Preludio del canal:"))
        self.assertIn("Últimos 3 mensajes legibles:", block)
        self.assertIn("10-22 21:00 Nano:", block)
        self.assertIn("10-24 21:00 Nano:", block)
        self.assertIn("nos vemos ahí", block)
        # Rows are chronological and one single line each, right after the header.
        body = block.split("\n", 2)[2]
        for line in body.split("\n"):
            self.assertRegex(line, ROW_DATE)
        self.assertLess(block.index("10-22"), block.index("10-24"))

    def test_topics_after_fold(self):
        block = ambient([
            message("el DOOM-eterno arrancó bien", "Nano", days_ago=1),
            message("qué grande el DOOM ETERNO", "Fer", days_ago=1),
        ], now=NOW)
        # Fold kills the case and the hyphen: "doom" and "eterno" are the topics.
        self.assertIn("doom", block)
        self.assertIn("eterno", block)

    def test_dict_rows_supported(self):
        block = ambient([{"created_at": NOW - timedelta(minutes=5),
                          "author": {"display_name": "Nano", "bot": False},
                          "content": "partido a las 9"}], now=NOW)
        self.assertIn("Nano: partido a las 9", block)
        self.assertIn("Últimos 1 mensajes legibles:", block)


class PrivacyTests(unittest.TestCase):
    def test_urls_are_omitted(self):
        block = ambient([message("mirá esto https://evil.test/path?x=1 dale", "Nano", days_ago=0)], now=NOW)
        self.assertIn("[enlace omitido]", block)
        self.assertNotIn("evil.test", block)

    def test_secrets_are_omitted(self):
        block = ambient([message("mi clave es sk-or-v1-AAAAAAAAAAAAAAAAAAAA yeah", "Nano", 0)], now=NOW)
        self.assertIn("[clave omitida]", block)
        self.assertNotIn("sk-or-v1", block)

    def test_mentions_become_names_or_mentions(self):
        fer = MagicMock()
        fer.id = "123"
        fer.display_name = "Fer"
        block = ambient([
            message("<@123> venite a jugar", "Nano", days_ago=0, mentions=[fer]),
            message("<@999> iba a armar el evento", "Fer", days_ago=0),
        ], now=NOW)
        self.assertIn("@Fer venite", block)
        self.assertNotIn("<@123>", block)
        self.assertIn("[mención] iba", block)
        self.assertNotIn("<@999>", block)

    def test_at_everyone_fully_anonymized(self):
        block = ambient([message("@everyone @here aviso del toro", "Nano", days_ago=0)], now=NOW)
        self.assertIn("[mención] [mención]", block)
        self.assertNotIn("everyone", block)

    def test_reply_marker_is_anonymous(self):
        block = ambient([message("ya lo subí igual", "Nano", days_ago=0,
                                 reference={"message_id": 987, "channel_id": 55})], now=NOW)
        self.assertIn("↩ ya lo subí", block)
        self.assertNotIn("987", block)


class BoundTests(unittest.TestCase):
    def test_char_cap_and_tail_truncation(self):
        texts = [message(f"mensaje viejo número {i} del lunes largo " + "x" * 200, "Viejo", days_ago=40 - i)
                 for i in range(40)]
        first_row = message("ESTE es el último y debe quedar ps", "Nano", days_ago=0)
        block = ambient(texts + [first_row], now=NOW, max_chars=900)
        self.assertLessEqual(len(block), 900)
        self.assertIn("ESTE es el último y debe quedar ps", block)
        self.assertNotIn("mensaje viejo número 0", block)

    def test_500_message_window_stays_bounded(self):
        rows = [message(f"charla número {i}", f"Voz{i % 7}", days_ago=i / 100) for i in range(500)]
        block = ambient(rows, now=NOW)
        self.assertLessEqual(len(block), 2600)
        self.assertNotIn("charla número 499", block)  # oldest rows were dropped
        self.assertIn("charla número 0", block)  # the newest never falls out
        declared = int(re.search(r"Últimos (\d+) mensajes legibles:", block).group(1))
        body_lines = block.split("\n", 2)[2].count("\n") + 1
        self.assertEqual(declared, body_lines)
        self.assertLessEqual(declared, 100)  # window honoured even under the char cap

    def test_window_param_respected_and_clamped(self):
        rows = [message(f"charla número {i}", "Nano", days_ago=i / 10) for i in range(600)]
        self.assertIn("Últimos 5 mensajes legibles:", ambient(rows, now=NOW, window=5, max_chars=8000))
        clamped = ambient(rows, now=NOW, window=99999, max_chars=8000)
        declared = int(re.search(r"Últimos (\d+) mensajes legibles:", clamped).group(1))
        self.assertLessEqual(declared, 500)  # window=99999 was clamped to MAX_WINDOW

    def test_max_chars_clamped(self):
        rows = [message("charla corta", "Nano", days_ago=i / 10) for i in range(600)]
        block = ambient(rows, now=NOW, max_chars=99999)
        self.assertLessEqual(len(block), 8000)  # 99999 was clamped to HARD_MAX_CHARS
        self.assertGreater(len(block), 0)


class FilterTests(unittest.TestCase):
    def test_bots_commands_empty_and_undated_excluded(self):
        rows = [
            message("hola gente, cómo andan", "Nano", days_ago=0),
            message("estado actualizado", "RoboBot", days_ago=0, bot=True),
            message("!ban todo", "Malito", days_ago=0),
            message("   ", "Nano", days_ago=0),
            message("sin fecha digna", "Nano", days_ago=0),
        ]
        rows[4].created_at = "ayer"
        block = ambient(rows, now=NOW)
        self.assertIn("hola gente", block)
        self.assertIn("Últimos 1 mensajes legibles:", block)
        self.assertNotIn("RoboBot", block)
        self.assertNotIn("!ban", block)

    def test_age_window_excludes_stale_rows(self):
        rows = [message("charla de la vieja semana", "Vieja", days_ago=30),
                message("charla de hoy", "Nano", days_ago=0)]
        block = ambient(rows, now=NOW, max_age_days=14)
        self.assertIn("charla de hoy", block)
        self.assertNotIn("vieja semana", block)
        self.assertIn("Últimos 1 mensajes legibles:", block)


class ShapeTests(unittest.TestCase):
    def test_empty_and_all_junk_return_empty_string(self):
        self.assertEqual(ambient([], now=NOW), "")
        self.assertEqual(ambient(None), "")
        self.assertEqual(ambient([message("", "Nano", 0), message("!comando", "Nano", 0)], now=NOW), "")

    def test_error_in_row_fails_closed(self):
        broken = MagicMock()
        broken.created_at = 3  # not a datetime-like value
        self.assertEqual(ambient([broken]), "")

    def test_compact_stable_format(self):
        rows = [message("el DOOM del sábado", "Nano", days_ago=i % 3 + 1) for i in range(4)]
        first, second = ambient(rows, now=NOW), ambient(rows, now=NOW)
        self.assertEqual(first, second)  # deterministic, no random dynamics
        self.assertEqual(first, first.strip())
        self.assertNotIn("\r", first)
        self.assertNotIn("\n\n", first)  # compact: no blank lines, no double breaks
        self.assertNotIn("  ", first.replace("Nano: ", ""))  # collapsed spacing


if __name__ == "__main__":
    unittest.main()
