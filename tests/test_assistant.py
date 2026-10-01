import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.assistant import Assistant, AssistantError, Settings, UsageBudget, metrics, bot_help


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
        "name": name, "arguments": json.dumps(arguments if arguments is not None else {"view": "me", "period": "all"})}}]}


def web_answer(quote='Dato actual confirmado', count=1):
    return {'content': json.dumps({'status': 'answer', 'evidence': [
        {'source': i, 'quote': quote} for i in range(1, count + 1)]})}


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
        self.agent.search = AsyncMock(return_value=[{"title": "Result", "url": "https://example.com", "content": "Dato actual confirmado"}])
        self.agent.completion = AsyncMock(return_value=web_answer())
        result = await self.agent.answer("Resultado de Boca hoy", lambda **args: self.fail("No metrics on web"), web=True)
        self.agent.search.assert_awaited_once_with("Resultado de Boca hoy")
        self.assertEqual(self.agent.completion.call_args.args[1], [])
        self.assertIn("https://example.com", result)

    async def test_normal_question_never_searches(self):
        self.agent.search = AsyncMock()
        self.agent.completion = AsyncMock(return_value={"content": "Hola"})
        await self.agent.answer("Hola", lambda **args: {})
        self.agent.search.assert_not_called()

    async def test_help_tool_roundtrip(self):
        self.agent.completion = AsyncMock(side_effect=[tool_call("get_bot_help", {"topic": "commands"}), {"content": "Usá !topvoice week."}])
        answer = await self.agent.answer("Qué comando muestra el ranking de voz?", lambda **args: self.fail("No metrics"))
        self.assertIn("!topvoice", answer)
        messages = self.agent.completion.call_args.args[0]
        self.assertIn("topvoice", messages[-1]["content"])
        first = self.agent.completion.call_args_list[0]
        self.assertEqual(first.kwargs["tool_choice"], "required")
        self.assertEqual([t["function"]["name"] for t in first.args[1]], ["get_bot_help"])

    async def test_model_decides_web_but_cannot_rewrite_query(self):
        self.agent.search = AsyncMock(return_value=[{"title": "Dato", "url": "https://example.com", "content": "Dato actual confirmado"}])
        self.agent.completion = AsyncMock(side_effect=[tool_call("search_web", {}), web_answer()])
        result = await self.agent.answer("Algún dato interesante?", lambda **args: self.fail("No metrics"))
        self.agent.search.assert_awaited_once_with("Algún dato interesante?")
        self.assertIn("Fuentes consultadas", result)
        names = [t["function"]["name"] for t in self.agent.completion.call_args.args[1]]
        self.assertNotIn("search_web", names)
        self.assertNotIn("get_metrics", names)

    async def test_search_query_argument_is_rejected(self):
        self.agent.search = AsyncMock()
        self.agent.completion = AsyncMock(return_value=tool_call("search_web", {"query": "private data"}))
        with self.assertRaises(AssistantError):
            await self.agent.answer("Hola", lambda **args: {})
        self.agent.search.assert_not_called()

    async def test_metrics_then_web_is_rejected(self):
        self.agent.search = AsyncMock()
        self.agent.completion = AsyncMock(side_effect=[tool_call(), tool_call("search_web", {})])
        with self.assertRaises(AssistantError):
            await self.agent.answer("Métricas y web", lambda **args: {"private": "data"})
        self.agent.search.assert_not_called()

    async def test_web_then_metrics_is_rejected(self):
        self.agent.search = AsyncMock(return_value=[{'content': 'Dato actual confirmado', 'url': 'https://example.com'}])
        self.agent.completion = AsyncMock(side_effect=[tool_call("search_web", {}), tool_call()])
        callback = AsyncMock()
        with self.assertRaises(AssistantError):
            await self.agent.answer("Web y métricas", callback)
        callback.assert_not_called()

    async def test_search_cannot_repeat_even_with_empty_results(self):
        self.agent.search = AsyncMock(return_value=[])
        self.agent.completion = AsyncMock(return_value=tool_call("search_web", {}))
        result = await self.agent.answer("Pregunta", lambda **args: {})
        self.assertIn('No encontré fuentes', result)
        self.agent.completion.assert_awaited_once()
        self.agent.search.assert_awaited_once()

    async def test_unconfigured_web_not_offered_and_help_always_available(self):
        self.agent.settings = Settings("openrouter", "openrouter/free", "test", "fixed")
        self.agent.completion = AsyncMock(return_value={"content": "Hola"})
        await self.agent.answer("Hola", lambda **args: {})
        names = [t["function"]["name"] for t in self.agent.completion.call_args.args[1]]
        self.assertEqual(names, ["get_bot_help", "ask_clarification"])

    async def test_explicit_web_without_key_before_llm(self):
        self.agent.settings = Settings("openrouter", "openrouter/free", "test", "fixed")
        self.agent.completion = AsyncMock()
        with self.assertRaises(AssistantError):
            await self.agent.answer("Pregunta", lambda **args: {}, web=True)
        self.agent.completion.assert_not_called()

    async def test_invalid_help_topic_or_path_never_reads_file(self):
        for args in ({"topic": "../../.env"}, {"topic": "commands", "path": ".env"}):
            self.agent.completion = AsyncMock(return_value=tool_call("get_bot_help", args))
            with self.assertRaises(AssistantError):
                await self.agent.answer("Ayuda", lambda **args: {})

    async def test_three_sources_fit_without_truncating_urls(self):
        sources = [{"title": "Dato", "content": f"Dato actual confirmado {i}", "url": "https://example.com/" + str(i) + "x" * 270} for i in range(3)]
        self.agent.search = AsyncMock(return_value=sources)
        self.agent.completion = AsyncMock(return_value={'content': json.dumps({'status': 'answer', 'evidence': [
            {'source': i + 1, 'quote': s['content']} for i, s in enumerate(sources)]})})
        result = await self.agent.answer("Pregunta", lambda **args: {}, web=True)
        self.assertLessEqual(len(result), 1990)
        for source in sources:
            self.assertIn(source["url"], result)

    async def test_parallel_tools_and_invalid_identifier_rejected_before_callback(self):
        callback = AsyncMock()
        for message in (dict(tool_call(), tool_calls=tool_call()["tool_calls"] * 2),
                        {"tool_calls": [dict(tool_call()["tool_calls"][0], id=123)]}):
            self.agent.completion = AsyncMock(return_value=message)
            with self.assertRaises(AssistantError):
                await self.agent.answer("Pregunta", callback)
        callback.assert_not_called()


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
            self.assertEqual(len(sources[0]["content"]), 1500)

    async def test_clarification_ends_turn_without_other_tools(self):
        self.agent.search = AsyncMock()
        callback = AsyncMock()
        self.agent.completion = AsyncMock(return_value=tool_call("ask_clarification", {"question": "¿Qué equipo y fecha?"}))
        answer = await self.agent.answer("Partido?", callback, conversation_key=(1, 2, 3))
        self.assertEqual(answer, "¿Qué equipo y fecha?")
        callback.assert_not_called()
        self.agent.search.assert_not_called()
        self.agent.completion.assert_awaited_once()
        self.assertEqual(len(self.agent.memory.read((1, 2, 3))), 2)

    async def test_invalid_clarification_rejected(self):
        for args in ({"question": " "}, {"question": 123}, {"question": "x" * 221}, {"question": "Qué?", "query": "secret"}):
            self.agent.completion = AsyncMock(return_value=tool_call("ask_clarification", args))
            with self.assertRaises(AssistantError):
                await self.agent.answer("Pregunta", lambda **args: {})

    async def test_malformed_tool_payloads_fail_closed(self):
        for message in ({"tool_calls": "bad"}, {"tool_calls": [None]}, {"tool_calls": [{"function": []}]},
                        {"tool_calls": [dict(tool_call()["tool_calls"][0], type="shell")]}, None):
            self.agent.completion = AsyncMock(return_value=message)
            with self.assertRaises(AssistantError):
                await self.agent.answer("Pregunta", lambda **args: self.fail("Must not execute"))

    async def test_memory_isolation_and_no_tool_results(self):
        key = (1, 2, 3)
        self.agent.completion = AsyncMock(side_effect=[tool_call(), {"content": "PRIVATE: 999 minutos"}])
        await self.agent.answer("Cuánto jugué?", lambda **args: {"secret": "PRIVATE"}, conversation_key=key)
        self.assertNotIn("PRIVATE", json.dumps(self.agent.memory.read(key)))
        self.agent.completion = AsyncMock(return_value={"content": "Hola"})
        await self.agent.answer("Y hoy?", lambda **args: {}, conversation_key=key)
        sent = self.agent.completion.call_args.args[0]
        self.assertIn("Cuánto jugué?", json.dumps(sent, ensure_ascii=False))
        self.assertNotIn("PRIVATE", json.dumps(sent))
        await self.agent.answer("Hola", lambda **args: {}, conversation_key=(1, 2, 4))
        self.assertNotIn("Cuánto jugué?", json.dumps(self.agent.completion.call_args.args[0], ensure_ascii=False))

    async def test_failure_does_not_update_memory(self):
        self.agent.completion = AsyncMock(side_effect=AssistantError("unavailable"))
        with self.assertRaises(AssistantError):
            await self.agent.answer("Hola", lambda **args: {}, conversation_key=(1, 2, 3))
        self.assertEqual(self.agent.memory.read((1, 2, 3)), [])

    async def test_recognizable_credentials_not_sent_or_remembered(self):
        self.agent.completion = AsyncMock()
        with self.assertRaises(AssistantError):
            await self.agent.answer("mi clave sk-or-v1-" + "x" * 20, lambda **args: {}, conversation_key=(1, 2, 3))
        self.agent.completion.assert_not_called()
        self.assertEqual(self.agent.memory.read((1, 2, 3)), [])

    async def test_malformed_search_results(self):
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            post.return_value = {"results": "bad"}
            with self.assertRaises(AssistantError):
                await self.agent.search("query")
            post.return_value = {"results": [None, {"url": 123}, {"url": "https://example.com"}]}
            self.assertEqual(len(await self.agent.search("query")), 1)


class HelpTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings("openrouter", "openrouter/free", "SECRET", "fixed")

    def test_only_fixed_topics_allowed(self):
        with self.assertRaises(AssistantError):
            bot_help(self.settings, ".env")

    def test_commands_and_updates_from_public_docs(self):
        self.assertIn("topvoice", bot_help(self.settings, "commands")["content"])
        self.assertTrue(bot_help(self.settings, "updates")["sections"])

    def test_capabilities_match_flags_without_credentials(self):
        result = bot_help(self.settings, "capabilities")
        self.assertFalse(result["web_enabled"])
        self.assertFalse(result["metrics_enabled"])
        self.assertNotIn("SECRET", json.dumps(result))
        configured = Settings("openrouter", "openrouter/free", "SECRET", "fixed", "search-secret", True)
        result = bot_help(configured, "capabilities")
        self.assertTrue(result["web_enabled"])
        self.assertTrue(result["metrics_enabled"])


if __name__ == "__main__":
    unittest.main()
