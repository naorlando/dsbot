"""Discord integration checks, offline and without reading production data."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from cogs.assistant import AssistantCog
from core.assistant import AssistantError, UsageBudget
from core.channel_dialogue import ChannelDialogue


def channel(mid=20, kind=None, parent=20):
    return SimpleNamespace(id=mid, name="partida del viernes", parent_id=parent,
                           type=SimpleNamespace(name=kind))


def message(mid=1, ch=None, content="Nos juntamos a jugar", user=1, bot=False):
    return SimpleNamespace(id=mid, channel=ch or channel(), guild=SimpleNamespace(id=10),
                           created_at=datetime.now(timezone.utc), content=content, mentions=[],
                           author=SimpleNamespace(id=user, bot=bot, display_name="Persona"), reference=None)


class ThreadScopeTests(unittest.TestCase):
    def setUp(self):
        self.dialogue = ChannelDialogue(10, 20, bot_id=99)

    def test_public_thread_is_shared_and_named_but_private_and_other_parent_are_not(self):
        self.assertTrue(self.dialogue.observe(message()))
        public = message(2, channel(21, "public_thread"), "El hilo público juega mañana")
        self.assertTrue(self.dialogue.observe(public))
        for ch in (channel(22, "private_thread"), channel(23, "public_thread", parent=88), channel(24)):
            self.assertFalse(self.dialogue.observe(message(3, ch, "dato fuera de alcance")))
        text = self.dialogue.render()
        self.assertIn("Nos juntamos", text)
        self.assertIn("hilo=", text)
        self.assertIn("partida del viernes", text)
        self.assertNotIn("fuera de alcance", text)
        self.assertIn("Hilo actual:", self.dialogue.invocation(public, "opiná"))

    def test_references_must_stay_inside_actual_thread(self):
        self.dialogue.observe(message(10, content="Botón en el padre", user=99, bot=True))
        summoned = message(11, channel(21, "public_thread"))
        summoned.reference = SimpleNamespace(message_id=10, channel_id=21, guild_id=10)
        self.assertFalse(self.dialogue.reply_is_own(summoned))
        own = message(12, channel(21, "public_thread"), user=99, bot=True)
        self.dialogue.observe(own)
        summoned.reference.message_id = 12
        self.assertTrue(self.dialogue.reply_is_own(summoned))

    def test_personal_identifiers_are_scrubbed_before_ram_and_parent_render(self):
        self.dialogue.observe(message(content="Mi email es persona@example.com y mi DNI es 12.345.678"))
        text = self.dialogue.render()
        self.assertNotIn("persona@example.com", text)
        self.assertNotIn("12.345.678", text)

    def test_bearer_payload_is_not_left_behind_after_redacting_its_label(self):
        self.dialogue.observe(message(content="Authorization: Bearer private_auth"))
        self.assertNotIn('private_auth', self.dialogue.render())

    def test_literal_web_selection_cannot_publish_contact_or_id_data(self):
        from core.assistant_evidence import render_evidence
        for quote in ('El correo es persona@example.com para este dato.',
                      'Su DNI es 12.345.678, según el registro.'):
            with self.subTest(quote=quote), self.assertRaises(ValueError):
                render_evidence(json.dumps({'status': 'answer', 'evidence': [{'source': 1, 'quote': quote}]}),
                                [{'url': 'https://example.com/report', 'content': quote}])


class OperationalCogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"AI_API_KEY": "test", "AI_GUILD_ID": "10", "AI_CHANNEL_ID": "20",
                                      "DISCORD_OWNER_ID": "1"}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.bot = SimpleNamespace(guilds=[SimpleNamespace(id=10)])
        self.cog = AssistantCog(self.bot)

    def ctx(self, user=1, ch=None):
        msg = message(ch=ch, user=user)
        return SimpleNamespace(author=msg.author, guild=msg.guild, channel=msg.channel,
                               message=msg, send=AsyncMock())

    async def test_owner_only_diagnostics_do_not_call_models(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cog.agent = SimpleNamespace(budget=UsageBudget(Path(tmp.name) / "usage.json"), completion=AsyncMock())
        for ctx in (self.ctx(user=2), self.ctx(ch=channel(88)), self.ctx(ch=channel(21, "private_thread"))):
            await self.cog.operational_status.callback(self.cog, ctx)
            ctx.send.assert_not_awaited()
        ctx = self.ctx()
        await self.cog.operational_status.callback(self.cog, ctx)
        text = " ".join(call.args[0] for call in ctx.send.await_args_list)
        self.assertIn("operacion_desde_reinicio", text)
        self.assertNotIn("test", text)
        self.cog.agent.completion.assert_not_awaited()
        self.assertFalse((Path(tmp.name) / "usage.json").exists())

    async def test_owner_revoke_is_by_ids_not_display_name(self):
        self.cog.curator = SimpleNamespace(invalidate_message=Mock(return_value=1),
                                           status=lambda: {'persisted': True})
        ctx = self.ctx(user=2)
        await self.cog.remove_source.callback(self.cog, ctx, "123", "20")
        self.cog.curator.invalidate_message.assert_not_called()
        ctx = self.ctx()
        await self.cog.remove_source.callback(self.cog, ctx, "Persona", "20")
        self.cog.curator.invalidate_message.assert_not_called()
        await self.cog.remove_source.callback(self.cog, ctx, "123", "20")
        self.cog.curator.invalidate_message.assert_called_once_with("123", "20")

    async def test_uncached_thread_delete_still_revokes_exact_curated_source(self):
        self.cog.curator = SimpleNamespace(invalidate_message=Mock(),
            metadata=lambda: [{'sources': [{'message_id': '100', 'channel_id': '21'}]}])
        payload = SimpleNamespace(guild_id=10, channel_id=21, message_id=100)
        await self.cog.on_raw_message_delete(payload)
        self.cog.curator.invalidate_message.assert_called_once_with(100, 21)
        payload.guild_id = 99
        await self.cog.on_raw_message_delete(payload)
        self.assertEqual(self.cog.curator.invalidate_message.call_count, 1)


class BudgetSnapshotTests(unittest.TestCase):
    def test_snapshot_never_consumes_and_backward_clock_never_resets(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "budget.json"
            budget = UsageBudget(path, llm_limit=1)
            later = datetime(2026, 11, 2, tzinfo=timezone.utc)
            earlier = datetime(2026, 11, 1, tzinfo=timezone.utc)
            self.assertEqual(budget.snapshot(later)["used"]["llm"], 0)
            self.assertFalse(path.exists())
            budget.consume("llm", later)
            raw = path.read_text()
            self.assertEqual(budget.snapshot(earlier)["used"]["llm"], 1)
            self.assertEqual(path.read_text(), raw)
            with self.assertRaises(AssistantError):
                budget.consume("llm", earlier)

    def test_corrupt_file_blocks_snapshot_instead_of_claiming_zero_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "budget.json"
            path.write_text("not json")
            with self.assertRaises(AssistantError):
                UsageBudget(path).snapshot()


class ProviderIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_malformed_200_reply_fails_over_and_eventually_opens_its_circuit(self):
        from core.assistant import ChainEntry, chain_post
        from core.assistant_operations import provider_health
        one = ChainEntry('openrouter', 'https://bad-envelope.test', 'm:free', 'hidden')
        two = ChainEntry('groq', 'https://good-envelope.test', 'fixed', 'hidden')
        good = {'choices': [{'message': {'content': 'Respuesta válida.'}}]}
        with patch('core.assistant.post_json', new_callable=AsyncMock) as post:
            post.side_effect = [{'choices': []}, good] * 3 + [good]
            for _ in range(4):
                result = await chain_post(None, [one, two], lambda entry: {})
                self.assertEqual(result['choices'][0]['message']['content'], 'Respuesta válida.')
            self.assertFalse(provider_health.allowed(one))
            self.assertEqual(post.await_count, 7)
            self.assertEqual(post.await_args_list[-1].args[1], two.endpoint)

    async def test_private_tool_names_and_nested_values_are_scrubbed_before_next_completion(self):
        from core.assistant import Assistant, Settings
        snapshots = []
        async def complete(messages, tools, **kwargs):
            snapshots.append(json.dumps(messages, ensure_ascii=False))
            if len(snapshots) == 1:
                return {'tool_calls': [{'type': 'function', 'id': '1', 'function': {
                    'name': 'get_metrics', 'arguments': '{"view":"top_players","period":"all"}'}}]}
            return {'content': 'Hay actividad guardada.'}
        with tempfile.TemporaryDirectory() as tmp:
            agent = Assistant(Settings('openrouter', 'm:free', 'hidden', 'https://tool.test',
                                       share_metrics=True), UsageBudget(Path(tmp) / 'usage.json'), None)
            agent.completion = complete
            await agent.answer('ranking', lambda **kwargs: {'players': [
                {'name': 'persona@example.com', 'game': 'Authorization: Bearer private_auth', 'minutes': 25}]})
        self.assertNotIn('persona@example.com', snapshots[-1])
        self.assertNotIn('private_auth', snapshots[-1])
        self.assertIn('25', snapshots[-1])

    def test_insufficient_evidence_still_has_unconfirmed_footer_and_real_links(self):
        from core.assistant_evidence import render_evidence
        result = render_evidence('{"status":"insufficient","evidence":[]}',
                                 [{'url': 'https://example.com/source', 'content': 'Un dato distinto.'}])
        for piece in ('https://example.com/source', 'Fuentes consultadas', 'sin confirmación', 'UTC'):
            self.assertIn(piece, result)

    async def test_rate_limit_skips_provider_next_question_and_keeps_fallback_free(self):
        from core.assistant import ChainEntry, RateLimited, chain_post
        from core.assistant_operations import provider_health
        one = ChainEntry('openrouter', 'https://quota.test', 'a:free', 'hidden')
        two = ChainEntry('groq', 'https://other.test', 'fixed', 'hidden')
        with patch('core.assistant.post_json', new_callable=AsyncMock) as post:
            good = {'choices': [{'message': {'content': 'Listo.'}}]}
            post.side_effect = [RateLimited('quota'), good, good]
            await chain_post(None, [one, two], lambda entry: {})
            self.assertFalse(provider_health.allowed(one))
            await chain_post(None, [one, two], lambda entry: {})
            self.assertEqual([call.args[1] for call in post.await_args_list],
                             [one.endpoint, two.endpoint, two.endpoint])

    async def test_invalid_tool_streak_is_attributed_to_actual_provider(self):
        from core.assistant import Assistant, ChainEntry, Settings
        from core.assistant_operations import provider_health
        entry = ChainEntry('openrouter', 'https://malformed.test', 'm:free', 'hidden')
        settings = Settings(entry.provider, entry.model, entry.key, entry.endpoint, chain=(entry,))
        invalid = {'choices': [{'message': {'tool_calls': [{'type': 'function', 'id': 'a',
                    'function': {'name': 'unknown', 'arguments': '{}'}}]}}]}
        with tempfile.TemporaryDirectory() as tmp:
            agent = Assistant(settings, UsageBudget(Path(tmp) / 'usage.json'), None)
            with patch('core.assistant.post_json', new_callable=AsyncMock, return_value=invalid) as post:
                for _ in range(2):
                    with self.assertRaises(AssistantError):
                        await agent.answer('hola', lambda **kw: {})
                self.assertFalse(provider_health.allowed(entry))
                # Two invalid responses first invocation, third response next;
                # transport 200s do not continually reset the failure streak.
                self.assertEqual(post.await_count, 3)

    async def test_curator_budget_does_not_consume_interactive_budget(self):
        from core.assistant import Assistant, Settings
        with tempfile.TemporaryDirectory() as tmp:
            interactive = UsageBudget(Path(tmp) / 'interactive.json')
            curator = UsageBudget(Path(tmp) / 'curator.json', llm_limit=24)
            agent = Assistant(Settings('openrouter', 'm:free', 'hidden', 'https://budget.test'), interactive, None)
            with patch('core.assistant.post_json', new_callable=AsyncMock,
                       return_value={'choices': [{'message': {'content': '{}'}}]}):
                await agent.completion([], [], usage_budget=curator)
            self.assertEqual(interactive.snapshot()['used']['llm'], 0)
            self.assertEqual(curator.snapshot()['used']['llm'], 1)

    async def test_search_does_not_send_personal_data_or_spend_search_budget(self):
        from core.assistant import Assistant, Settings
        with tempfile.TemporaryDirectory() as tmp:
            budget = UsageBudget(Path(tmp) / 'usage.json')
            agent = Assistant(Settings('openrouter', 'm:free', 'hidden', 'https://budget.test'), budget, None)
            with patch('core.assistant.post_json', new_callable=AsyncMock) as post:
                with self.assertRaises(AssistantError):
                    await agent.web_research('buscá persona@example.com')
                post.assert_not_awaited()
            self.assertEqual(budget.snapshot()['used']['search'], 0)
