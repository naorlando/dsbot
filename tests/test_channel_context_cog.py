import os
import tempfile
import unittest
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from cogs.assistant import AssistantCog
from core.assistant_memory import ConversationMemory
from core.banter_ledger import BanterLedger
from core.channel_curator import ChannelCurator


class ChannelCogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"AI_API_KEY": "test", "AI_GUILD_ID": "10", "AI_CHANNEL_ID": "20"}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.bot = SimpleNamespace(guilds=[SimpleNamespace(id=10)])
        self.cog = AssistantCog(self.bot)

    def message(self, id=1, content="organizamos partida", author=1, guild=10, channel=20, bot=False):
        return SimpleNamespace(id=id, content=content, created_at=datetime.now(timezone.utc),
            guild=SimpleNamespace(id=guild), channel=SimpleNamespace(id=channel),
            author=SimpleNamespace(id=author, bot=bot, display_name=f"Jugador{author}"))

    async def test_every_human_message_can_enter_context_without_a_mention(self):
        for i in range(130):
            await self.cog.on_message(self.message(id=i + 1, content=f"turno_{i}_completo"))
        text = self.cog.dialogue.render()
        self.assertIn("turno_129_completo", text)
        self.assertNotIn("turno_0_completo", text)
        self.assertIsNone(self.cog.curator)
        self.assertFalse(self.cog.channel_memory_enabled)

    async def test_admin_commands_other_bots_and_other_scopes_never_enter_context(self):
        for msg in [self.message(content="!olvidar"), self.message(bot=True),
                    self.message(guild=99), self.message(channel=99)]:
            await self.cog.on_message(msg)
        self.assertFalse(self.cog.dialogue.render())
        self.bot.guilds.append(SimpleNamespace(id=11))
        await self.cog.on_message(self.message())
        self.assertFalse(self.cog.dialogue.render())

    async def test_edit_and_delete_update_the_prompt_buffer(self):
        await self.cog.on_message(self.message())
        updated = self.message(content="nuevo texto")
        await self.cog.on_message_edit(self.message(), updated)
        self.assertIn("nuevo texto", self.cog.dialogue.render())
        await self.cog.on_message_delete(updated)
        self.assertFalse(self.cog.dialogue.render())

    async def test_warm_start_fetches_at_most_100_once_and_merges_live_messages(self):
        rows = [self.message(id=i) for i in range(100)]
        channel = SimpleNamespace()

        async def history(**kwargs):
            for row in reversed(rows):
                yield row

        channel.history = Mock(side_effect=history)
        await self.cog.on_message(self.message(id=101, content="mensaje_en_vivo"))
        await self.cog._warm_start(channel)
        await self.cog._warm_start(channel)
        channel.history.assert_called_once_with(limit=100, oldest_first=False)
        self.assertTrue(self.cog.dialogue.contains(101))
        self.assertIn("mensaje_en_vivo", self.cog.dialogue.render())

    async def test_opt_in_curator_observes_messages_and_is_not_run_in_listener(self):
        self.cog.curator = ChannelCurator(self.path / "curator.json", min_messages=2)
        self.cog.agent = SimpleNamespace(completion=AsyncMock())
        await self.cog.on_message(self.message(content="el viernes jugamos al equipo azul"))
        self.assertEqual(self.cog.curator.pending_count, 1)
        self.cog.agent.completion.assert_not_awaited()

    async def test_background_curator_uses_the_budgeted_completion_and_skips_busy_bot(self):
        curator = SimpleNamespace(due=Mock(return_value=True), curate=AsyncMock(return_value=True))
        self.cog.curator = curator
        self.cog.agent = SimpleNamespace(completion=AsyncMock())
        async with self.cog.lock:
            await self.cog.curator_loop.coro(self.cog)
        curator.curate.assert_not_awaited()
        await self.cog.curator_loop.coro(self.cog)
        curator.curate.assert_awaited_once()
        callback = curator.curate.await_args.args[0]
        await callback([], [])
        self.cog.agent.completion.assert_awaited_once_with([], [], total=18, max_tokens=1600)

    async def test_legacy_reset_is_a_notice_and_preserves_shared_dialogue_and_ledger(self):
        ledger = BanterLedger(self.path / "banter.json")
        ledger.add("Jugador1", "apostó al equipo azul")
        ledger.add("Jugador2", "apostó al equipo verde")
        self.cog.curator = ChannelCurator(self.path / "curator.json")
        await self.cog.on_message(self.message())
        self.cog.agent = SimpleNamespace(banter=ledger, memory=ConversationMemory())
        self.cog.agent.memory.remember((10, 20, 1), "hola", "hola")
        msg = self.message()
        ctx = SimpleNamespace(guild=msg.guild, channel=msg.channel, author=msg.author, send=AsyncMock())
        await self.cog.forget.callback(self.cog, ctx)
        self.assertTrue(ledger.recall("Jugador1"))
        self.assertTrue(ledger.recall("Jugador2"))
        # There is no per-user chat to erase: the shared pool survives the old command.
        self.assertTrue(self.cog.agent.memory.read((10, 20, 1)))
        self.assertTrue(self.cog.dialogue.render())
        self.assertEqual(self.cog.curator.pending_count, 1)

    async def test_saved_notes_command_is_scoped_and_does_not_call_a_model(self):
        self.cog.agent = SimpleNamespace(completion=AsyncMock(), banter=None)
        msg = self.message()
        ctx = SimpleNamespace(guild=msg.guild, channel=msg.channel, author=msg.author, send=AsyncMock())
        await self.cog.memory_status.callback(self.cog, ctx)
        self.assertIn("desactivada", ctx.send.call_args.args[0])
        self.cog.agent.completion.assert_not_awaited()
        ctx.channel.id = 99
        ctx.send.reset_mock()
        await self.cog.memory_status.callback(self.cog, ctx)
        ctx.send.assert_not_awaited()

    async def test_sample_calibrated_curation_thresholds_and_cooldown(self):
        now = [0.0]
        curator = ChannelCurator(self.path / "curator.json", clock=lambda: now[0], min_messages=40,
            interval_seconds=7200, temporal_min_messages=10, min_gap_seconds=900,
            retry_seconds=1800, max_daily=24)
        row = {"fecha": "2026-10-29 12:00", "autor": "Jugador", "texto": "El viernes jugamos una partida."}
        for _ in range(9):
            curator.observe(row)
        now[0] = 7200
        self.assertFalse(curator.due())
        curator.observe(row)
        self.assertTrue(curator.due())
        self.assertTrue(await curator.curate(AsyncMock(return_value={"bullets": []})))
        for _ in range(40):
            curator.observe(row)
        self.assertFalse(curator.due())  # even 40 new rows cannot bypass the cooldown
        now[0] += 900
        self.assertTrue(curator.due())


class SecretScrubTests(unittest.TestCase):
    def test_shared_filter_catches_synthetic_discord_and_google_credentials(self):
        from core.assistant_secrets import SECRET_PATTERN
        for sample in ["A" * 24 + "." + "B" * 6 + "." + "C" * 30, "AIza" + "x" * 35]:
            self.assertIsNotNone(SECRET_PATTERN.search(sample))
            self.assertNotIn(sample, SECRET_PATTERN.sub("[omitida]", sample))
