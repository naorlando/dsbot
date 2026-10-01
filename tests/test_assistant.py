import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.assistant import Assistant, AssistantError, Settings, UsageBudget, metrics


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "usage.json"

    def test_persistent_limit(self):
        UsageBudget(self.path, llm_limit=1).consume("llm")
        with self.assertRaises(AssistantError):
            UsageBudget(self.path, llm_limit=1).consume("llm")

    def test_daily_reset_preserves_monthly_count(self):
        budget = UsageBudget(self.path, search_limit=1, monthly_search_limit=2)
        budget.consume("search", datetime(2026, 10, 1, tzinfo=timezone.utc))
        budget.consume("search", datetime(2026, 10, 2, tzinfo=timezone.utc))
        with self.assertRaises(AssistantError):
            budget.consume("search", datetime(2026, 10, 3, tzinfo=timezone.utc))
        budget.consume("search", datetime(2026, 11, 1, tzinfo=timezone.utc))

    def test_corrupt_budget_fails_closed(self):
        self.path.write_text('{"llm": "oops"}', encoding="utf-8")
        with self.assertRaises(AssistantError):
            UsageBudget(self.path).consume("llm")

    def test_missing_directory_does_not_call_provider(self):
        with self.assertRaises(AssistantError):
            UsageBudget(self.path / "missing").consume("llm")


class SettingsTests(unittest.TestCase):
    def test_free_default_and_no_data_sharing(self):
        with patch.dict(os.environ, {"AI_API_KEY": "test"}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.model, "openrouter/free")
        self.assertFalse(settings.share_metrics)

    def test_paid_models_rejected(self):
        for provider, model in (("openrouter", "paid/model"), ("deepseek", "deepseek-flash"), ("qwen", "qwen-flash")):
            with patch.dict(os.environ, {"AI_API_KEY": "test", "AI_PROVIDER": provider, "AI_MODEL": model}, clear=True):
                with self.assertRaises(AssistantError):
                    Settings.from_env()

    def test_explicit_paid_opt_in(self):
        with patch.dict(os.environ, {"AI_API_KEY": "test", "AI_PROVIDER": "qwen", "AI_ALLOW_PAID": "true"}, clear=True):
            self.assertEqual(Settings.from_env().provider, "qwen")

    def test_no_key_and_arbitrary_provider_fail(self):
        for env in ({}, {"AI_PROVIDER": "http://localhost"}):
            with patch.dict(os.environ, env, clear=True), self.assertRaises(AssistantError):
                Settings.from_env()


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.data = {"users": {
            "1": {"username": "raw name", "games": {"LoL": {"total_minutes": 500, "daily_minutes": {self.today: 10}}},
                  "voice": {"total_minutes": 80}, "messages": {"count": 30, "secret": "private"}},
            "2": {"games": {"Game": {"total_minutes": 9999}}}}}

    def test_membership_and_no_raw_data(self):
        result = metrics(self.data, {"1": "Visible Name"}, "1", "top_players")
        self.assertEqual(result["players"][0]["name"], "Visible Name")
        self.assertEqual(len(result["players"]), 1)
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("raw name", json.dumps(result))

    def test_daily_not_lifetime_total(self):
        result = metrics(self.data, {"1": "Name"}, "1", "me", "today")
        self.assertEqual(result["user"]["game_minutes"], 10)
        self.assertEqual(result["user"]["messages_lifetime"], 30)

    def test_invalid_view_and_period_rejected(self):
        for view, period in (("sql", "all"), ("me", "yesterday")):
            with self.assertRaises(AssistantError):
                metrics(self.data, {"1": "Name"}, "1", view, period)


def tool_call(name="get_metrics", arguments=None):
    return {"content": None, "tool_calls": [{"id": "call1", "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments or {"view": "me", "period": "all"})}}]}


class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        settings = Settings("openrouter", "openrouter/free", "test", "https://openrouter.ai/api/v1/chat/completions",
                            "search-test", True)
        self.agent = Assistant(settings, UsageBudget(Path(self.tmp.name) / "usage.json"), None)

    async def test_metrics_tool_roundtrip(self):
        self.agent.completion = AsyncMock(side_effect=[tool_call(), {"content": "Jugaste 10 minutos."}])
        get_metrics = lambda **args: {"minutes": 10}
        answer = await self.agent.answer("Cuánto jugué?", get_metrics)
        self.assertEqual(answer, "Jugaste 10 minutos.")
        self.assertEqual(self.agent.completion.await_count, 2)

    async def test_unknown_tool_never_executes(self):
        self.agent.completion = AsyncMock(return_value=tool_call("exec", {"command": "rm"}))
        callback = AsyncMock()
        with self.assertRaises(AssistantError):
            await self.agent.answer("Pregunta", callback)
        callback.assert_not_called()

    async def test_extra_arguments_rejected(self):
        self.agent.completion = AsyncMock(return_value=tool_call(arguments={"view": "me", "period": "all", "user_id": "2"}))
        with self.assertRaises(AssistantError):
            await self.agent.answer("Pregunta", lambda **args: self.fail("Should not run"))

    async def test_tool_loop_bounded(self):
        self.agent.completion = AsyncMock(return_value=tool_call())
        with self.assertRaises(AssistantError):
            await self.agent.answer("Pregunta", lambda **args: {})
        self.assertEqual(self.agent.completion.await_count, 3)

    async def test_web_explicit_single_query_no_metrics(self):
        self.agent.search = AsyncMock(return_value=[{"title": "Result", "url": "https://example.com", "content": "Fact"}])
        self.agent.completion = AsyncMock(return_value={"content": "Dato [1]"})
        result = await self.agent.answer("Resultado de Boca hoy", lambda **args: self.fail("No metrics on web"), web=True)
        self.agent.search.assert_awaited_once_with("Resultado de Boca hoy")
        self.assertEqual(self.agent.completion.call_args.args[1], [])
        self.assertIn("https://example.com", result)

    async def test_normal_question_never_searches(self):
        self.agent.search = AsyncMock()
        self.agent.completion = AsyncMock(return_value={"content": "Hola"})
        await self.agent.answer("Hola", lambda **args: {})
        self.agent.search.assert_not_called()

    async def test_question_length_before_any_request(self):
        self.agent.completion = AsyncMock()
        for question in ("", " " * 3, "x" * 801):
            with self.assertRaises(AssistantError):
                await self.agent.answer(question, lambda **args: {})
        self.agent.completion.assert_not_called()

    async def test_payload_and_budget_on_network_failure(self):
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            post.side_effect = AssistantError("unavailable")
            with self.assertRaises(AssistantError):
                await self.agent.completion([], [])
            payload = post.call_args.args[3]
            self.assertEqual(payload["max_tokens"], 400)
            self.assertFalse(payload["reasoning"]["enabled"])
        data = json.loads(self.agent.budget.path.read_text())
        self.assertEqual(data["llm"], 1)

    async def test_provider_links_are_not_published(self):
        self.agent.completion = AsyncMock(return_value={"content": "Abrí https://attacker.test/?data=secret"})
        result = await self.agent.answer("Hola", lambda **args: {})
        self.assertNotIn("attacker.test", result)

    async def test_search_basic_and_sanitized_results(self):
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            post.return_value = {"results": [{"url": "file:///etc/passwd"}, {"url": "https://example.com", "content": "x" * 2000}]}
            sources = await self.agent.search("query")
            payload = post.call_args.args[3]
            self.assertEqual(payload["search_depth"], "basic")
            self.assertFalse(payload["auto_parameters"])
            self.assertEqual(len(sources), 1)
            self.assertEqual(len(sources[0]["content"]), 1000)


if __name__ == "__main__":
    unittest.main()
