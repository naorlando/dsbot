import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.assistant import AssistantError, RateLimited, Settings
from core.commentator import Commentator, KINDS, maybe_compose, sanitize, template_digest


def settings_with(chain=(), provider="openrouter", model="cohere/north-mini-code:free"):
    return Settings(provider, model, "hidden", "fixed", chain=chain)


def responder(content='Buen pedido, alguien se reenganchó 💀'):
    return {'choices': [{'message': {'content': content}}]}


class SanitizeTests(unittest.TestCase):
    def test_strips_links_pings_and_secrets(self):
        self.assertEqual(sanitize("mirá https://spam.test/x y esta es otra cosa"), "mirá [enlace omitido] y esta es otra cosa")
        self.assertEqual(sanitize("conde sk-or-v1-abcdefghij123 y listo"), "conde [clave omitida] y listo")
        self.assertEqual(sanitize("@everyone atento @Here"), "[mención] atento [mención]")
        self.assertEqual(sanitize(None), None)
        self.assertEqual(sanitize("   "), None)

    def test_length_clamped(self):
        self.assertEqual(len(sanitize("a" * 500)), 400)


class ComposeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.budget_path = Path(self.tmp.name) / "ambient.json"
        # Note: budget file lives elsewhere; Commentator gets any budget object.

    def _commentator(self, settings=None, budget=None):
        from core.assistant import UsageBudget
        return Commentator(None, budget or UsageBudget(self.budget_path),
                           settings or settings_with())

    async def test_compose_returns_sanitized_text(self):
        commentator = self._commentator()
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            post.return_value = responder()
            text = await commentator.compose("daily_digest", {"dia": "sábado"})
        self.assertEqual(text, "Buen pedido, alguien se reenganchó 💀")
        payload = post.call_args.args[3]  # (session, endpoint, key, payload)
        self.assertEqual(payload["max_tokens"], 220)
        self.assertEqual(payload["temperature"], 1.1)

    async def test_budget_exhausted_conservative_and_returns_none(self):
        from core.assistant import UsageBudget
        budget = UsageBudget(self.budget_path, ambient_limit=1)
        commentator = self._commentator(budget=budget)
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            post.return_value = responder()
            self.assertEqual(await commentator.compose("party_formed", {"game": "LoL"}),
                             "Buen pedido, alguien se reenganchó 💀")
            self.assertIsNone(await commentator.compose("party_formed", {"game": "LoL"}))
            self.assertEqual(post.await_count, 1)
        self.assertIn('"ambient": 1', self.budget_path.read_text())

    async def test_provider_error_returns_none_for_template(self):
        commentator = self._commentator()
        with patch("core.assistant.post_json", new_callable=AsyncMock, side_effect=AssistantError("down")):
            self.assertIsNone(await commentator.compose("connection_milestone", {"member": "N", "count": 10}))

    async def test_rate_limited_across_whole_chain_returns_none(self):
        from core.assistant import ChainEntry
        entries = (ChainEntry('openrouter', 'https://a.test', 'm:free', 'k1'),
                   ChainEntry('groq', 'https://b.test', 'm2', 'k2'))
        commentator = self._commentator(settings=settings_with(chain=entries))
        with patch("core.assistant.post_json", new_callable=AsyncMock, side_effect=RateLimited("cap")) as post:
            self.assertIsNone(await commentator.compose("daily_digest", {"dia": "viernes"}))
        self.assertEqual(post.await_count, 2)

    async def test_chain_failover_uses_second_provider(self):
        from core.assistant import ChainEntry
        entries = (ChainEntry('openrouter', 'https://a.test', 'm:free', 'k1'),
                   ChainEntry('groq', 'https://b.test', 'm2', 'k2'))
        commentator = self._commentator(settings=settings_with(chain=entries))
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            post.side_effect = [RateLimited("cap"), responder()]
            text = await commentator.compose("daily_digest", {"dia": "viernes"})
        self.assertEqual(text, "Buen pedido, alguien se reenganchó 💀")
        self.assertEqual(post.call_args_list[0].args[1], 'https://a.test')
        self.assertEqual(post.call_args_list[1].args[1], 'https://b.test')

    async def test_invalid_kind_or_facts_rejected(self):
        commentator = self._commentator()
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            self.assertIsNone(await commentator.compose("otro", {"a": 1}))
            self.assertIsNone(await commentator.compose("daily_digest", "facts"))
            post.assert_not_called()

    async def test_plain_payload_for_non_openrouter_entries(self):
        from core.assistant import ChainEntry
        commentator = self._commentator(settings=settings_with(chain=(
            ChainEntry('google', 'https://a.test', 'gemini-x', 'k1'),)))
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            post.return_value = responder()
            await commentator.compose("daily_digest", {"dia": "viernes"})
        payload = post.call_args.args[3]  # (session, endpoint, key, payload)
        self.assertNotIn("reasoning", payload)
        self.assertNotIn("provider", payload)
        self.assertEqual(payload["model"], "gemini-x")


class TemplateDigestTests(unittest.TestCase):
    def test_deterministic_template(self):
        facts = {"dia": "sábado", "minutos_totales_juegos": 120.0,
                 "juegos_del_dia": [{"game": "LoL", "minutes": 100}, {"game": "CS", "minutes": 20}],
                 "minutos_totales_voz": 45}
        first = template_digest(facts)
        self.assertEqual(first, template_digest(facts))
        self.assertIn("LoL", first)
        self.assertIn("120.0", first)

    def test_broken_facts_never_raises(self):
        for facts in (None, [], {"juegos_del_dia": None}, {}):
            try:
                template_digest(facts)
            except Exception:  # noqa: BLE001
                self.fail("template_digest must never raise")


class MaybeComposeTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_or_broken_commentator_returns_none(self):
        self.assertIsNone(await maybe_compose(MagicMock(), "daily_digest", {"a": 1}))
        bot = MagicMock()
        bot.commentator = Commentator(None, AsyncMock(), settings_with())
        with patch.object(bot.commentator, "compose", side_effect=RuntimeError("boom")):
            self.assertIsNone(await maybe_compose(bot, "daily_digest", {"a": 1}))

    async def test_writer_only_kinds(self):
        self.assertEqual(sorted(KINDS), sorted(['connection_milestone', 'party_formed', 'daily_digest']))


if __name__ == "__main__":
    unittest.main()
