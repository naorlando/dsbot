import asyncio
import os
import unittest
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cogs.assistant import AssistantCog
from core.assistant_memory import ConversationMemory


@asynccontextmanager
async def typing():
    yield


class CogTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = patch.dict(os.environ, {"AI_API_KEY": "test", "AI_GUILD_ID": "10", "AI_CHANNEL_ID": "20"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.bot = SimpleNamespace(guilds=[SimpleNamespace(id=10)])
        self.cog = AssistantCog(self.bot)
        self.cog.agent = SimpleNamespace(answer=AsyncMock(return_value="Respuesta @everyone"), memory=ConversationMemory())
        self.ctx = SimpleNamespace(
            guild=SimpleNamespace(id=10, members=[SimpleNamespace(id=1, display_name="Name", bot=False)]),
            channel=SimpleNamespace(id=20), author=SimpleNamespace(id=1, bot=False), send=AsyncMock(), typing=typing)
        self.ctx.message = SimpleNamespace(author=self.ctx.author)

    async def test_wrong_channel_and_dm_do_not_call_provider(self):
        self.ctx.channel.id = 99
        await self.cog.respond(self.ctx, "hola")
        self.ctx.guild = None
        await self.cog.respond(self.ctx, "hola")
        self.cog.agent.answer.assert_not_called()

    async def test_wrong_guild_and_bots_do_not_call_provider(self):
        self.ctx.guild.id = 99
        await self.cog.respond(self.ctx, "hola")
        self.ctx.guild.id = 10
        self.ctx.author.bot = True
        await self.cog.respond(self.ctx, "hola")
        self.cog.agent.answer.assert_not_called()

    async def test_multi_guild_rejected(self):
        self.bot.guilds.append(SimpleNamespace(id=11))
        await self.cog.respond(self.ctx, "hola")
        self.cog.agent.answer.assert_not_called()

    async def test_shared_cooldown_and_mentions_suppressed(self):
        await self.cog.respond(self.ctx, "hola")
        await self.cog.respond(self.ctx, "web", web=True)
        self.cog.agent.answer.assert_awaited_once()
        self.assertEqual(self.cog.agent.answer.call_args.kwargs["conversation_key"], (10, 20))
        allowed = self.ctx.send.call_args_list[0].kwargs["allowed_mentions"]
        self.assertFalse(allowed.everyone)
        self.assertFalse(allowed.users)
        self.assertFalse(allowed.roles)

    async def test_busy_does_not_queue(self):
        async with self.cog.lock:
            await self.cog.respond(self.ctx, "hola")
        self.cog.agent.answer.assert_not_called()

    async def test_unexpected_error_is_contained(self):
        self.cog.agent.answer.side_effect = RuntimeError("SECRET")
        await self.cog.respond(self.ctx, "hola")
        self.assertNotIn("SECRET", str(self.ctx.send.call_args))
        self.assertFalse(self.cog.lock.locked())

    async def test_timeout_is_contained(self):
        self.cog.agent.answer.side_effect = asyncio.TimeoutError()
        await self.cog.respond(self.ctx, "hola")
        self.assertIn("Se me fue la mano", self.ctx.send.call_args.args[0])
        self.assertFalse(self.cog.lock.locked())

    async def test_session_lifecycle_closes(self):
        with tempfile.TemporaryDirectory() as tmp, patch('cogs.assistant.DATA_DIR', Path(tmp)):
            await self.cog.cog_load()
            self.assertFalse(self.cog.session.closed)
            await self.cog.cog_unload()
            self.assertTrue(self.cog.session.closed)

    async def test_boton_aliases_registered(self):
        self.assertEqual(self.cog.ask.name, "boton")
        self.assertEqual(self.cog.ask.aliases, ["botón"])

    async def test_forget_and_status_do_not_spend_model_calls(self):
        key = (10, 20, 1)
        self.cog.agent.memory.remember(key, "hola", "hola")
        await self.cog.forget.callback(self.cog, self.ctx)
        # The legacy per-user reset is a notice now: shared dialogue is untouched.
        self.assertTrue(self.cog.agent.memory.read(key))
        self.assertIn("compartida por canal", self.ctx.send.call_args.args[0])
        await self.cog.status.callback(self.cog, self.ctx)
        self.assertIn("todos comparten el contexto", self.ctx.send.call_args.args[0])
        self.cog.agent.answer.assert_not_called()

    async def test_forget_wrong_scope_does_not_clear(self):
        key = (10, 20, 1)
        self.cog.agent.memory.remember(key, "hola", "hola")
        self.ctx.channel.id = 99
        await self.cog.forget.callback(self.cog, self.ctx)
        self.assertTrue(self.cog.agent.memory.read(key))
        self.ctx.send.assert_not_called()


class DigestLoopTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = patch.dict(os.environ, {"AI_API_KEY": "test", "AI_GUILD_ID": "10", "AI_CHANNEL_ID": "20"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.channel = SimpleNamespace(send=AsyncMock())
        self.guild = SimpleNamespace(id=10, members=[
            SimpleNamespace(id=1, display_name="Wire", bot=False),
            SimpleNamespace(id=2, display_name="Robot", bot=True)])
        self.bot = SimpleNamespace(guilds=[self.guild], get_guild=lambda gid: self.guild,
                                   get_channel=lambda cid: self.channel)
        self.cog = AssistantCog(self.bot)
        self.facts = {"dia": "domingo", "minutos_totales_juegos": 60.0,
                      "juegos_del_dia": [{"game": "LoL", "minutes": 60}],
                      "jugadores_por_juego": [{"game": "LoL", "players": [{"member": "Wire", "minutes": 60}]}],
                      "minutos_totales_voz": 0}

    @staticmethod
    def art(hour, day=8):
        return datetime(2026, 11, day, hour, 0, tzinfo=timezone(timedelta(hours=-3)))

    async def run_loop(self, now, facts=None, composed=None):
        with patch("cogs.assistant.argentina_now", return_value=now), \
             patch("cogs.assistant.day_digest", return_value=facts) as digest, \
             patch("cogs.assistant.maybe_compose", AsyncMock(return_value=composed)) as compose:
            await self.cog.digest_loop.coro(self.cog)
        return digest, compose

    async def test_fires_at_argentina_hour_with_previous_utc_bucket_once(self):
        digest, compose = await self.run_loop(self.art(21), facts=self.facts)
        digest.assert_called_once()
        args, kwargs = digest.call_args
        self.assertEqual(kwargs["day"], "2026-11-08")
        self.assertEqual(kwargs["now"].hour, 21)
        self.assertEqual(args[1], {"1": "Wire"})
        compose.assert_awaited_once()
        self.channel.send.assert_awaited_once()
        self.assertIn("Resumen de domingo", self.channel.send.call_args.args[0])
        # A second tick inside the same hour must not resend.
        await self.run_loop(self.art(21), facts=self.facts)
        self.channel.send.assert_awaited_once()

    async def test_silent_outside_configured_hour(self):
        digest, _ = await self.run_loop(self.art(20), facts=self.facts)
        digest.assert_not_called()
        self.channel.send.assert_not_awaited()

    async def test_no_activity_marks_the_day_without_sending(self):
        digest, compose = await self.run_loop(self.art(21), facts=None)
        digest.assert_called_once()
        compose.assert_not_awaited()
        self.channel.send.assert_not_awaited()
        self.assertEqual(self.cog.digest_last, "2026-11-08")
        # Nothing tracked: no retry noise later in the same hour.
        await self.run_loop(self.art(21), facts=self.facts)
        self.channel.send.assert_not_awaited()

    async def test_composer_text_used_and_failure_allows_retry(self):
        await self.run_loop(self.art(21, day=8), facts=self.facts, composed="texto del compositor")
        self.assertEqual(self.channel.send.call_args.args[0], "texto del compositor")
        self.channel.send.side_effect = RuntimeError("discord down")
        await self.run_loop(self.art(21, day=9), facts=self.facts)
        self.assertIsNone(self.cog.digest_last)  # retried on the next tick


if __name__ == "__main__":
    unittest.main()
