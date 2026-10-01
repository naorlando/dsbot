import asyncio
import os
import unittest
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
        self.assertEqual(self.cog.agent.answer.call_args.kwargs["conversation_key"], (10, 20, 1))
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
        self.assertIn("tardó demasiado", self.ctx.send.call_args.args[0])
        self.assertFalse(self.cog.lock.locked())

    async def test_session_lifecycle_closes(self):
        await self.cog.cog_load()
        self.assertFalse(self.cog.session.closed)
        await self.cog.cog_unload()
        self.assertTrue(self.cog.session.closed)

    async def test_boton_aliases_registered(self):
        self.assertIn("boton", self.cog.ask.aliases)
        self.assertIn("botón", self.cog.ask.aliases)

    async def test_forget_and_status_do_not_spend_model_calls(self):
        key = (10, 20, 1)
        self.cog.agent.memory.remember(key, "hola", "hola")
        await self.cog.forget.callback(self.cog, self.ctx)
        self.assertEqual(self.cog.agent.memory.read(key), [])
        await self.cog.status.callback(self.cog, self.ctx)
        self.assertIn("últimos 5 mensajes", self.ctx.send.call_args.args[0])
        self.cog.agent.answer.assert_not_called()

    async def test_forget_wrong_scope_does_not_clear(self):
        key = (10, 20, 1)
        self.cog.agent.memory.remember(key, "hola", "hola")
        self.ctx.channel.id = 99
        await self.cog.forget.callback(self.cog, self.ctx)
        self.assertTrue(self.cog.agent.memory.read(key))
        self.ctx.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
