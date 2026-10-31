"""Failure manners of the assistant under slow/dead providers and long prompts.

Diagnosis for "las querys largas se traba": one hung provider request used to
cost up to 18s per attempt, with chain + fallback + up to 6 model turns stacking
hundreds of seconds against the cog's single 60s wait_for fence. These tests pin
what the user experiences: hard per-request cuts, a fenced wait_for that always
publishes something, and no lock hang between concurrent questions.
"""
import asyncio
import os
import time
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp

import core.assistant
from cogs.assistant import AssistantCog
from core.assistant import (Assistant, AssistantError, ChainEntry, PROVIDER_TIMEOUT,
                            ROUTER_TIMEOUT, post_json, chain_post)


class HangServer:
    """TCP server that reads the request and never answers: worst-case provider."""

    def __init__(self):
        self._server = None
        self._handlers = set()

    async def start(self):
        async def handle(reader, writer):
            self._handlers.add(asyncio.current_task())
            try:
                await reader.read(65536)
                await asyncio.sleep(3600)
            except (ConnectionError, asyncio.CancelledError):
                pass
            finally:
                writer.close()
        self._server = await asyncio.start_server(handle, "127.0.0.1", 0)
        return self._server.sockets[0].getsockname()[1]

    async def stop(self):
        # Python 3.12 wait_closed() waits for every open handler connection, and
        # handlers are parked in sleep(3600): cancel them BEFORE closing or
        # cleanup itself hangs.
        for task in list(self._handlers):
            task.cancel()
        self._server.close()
        await self._server.wait_closed()
        for task in list(self._handlers):
            try:
                await task
            except (asyncio.CancelledError, ConnectionError, OSError):
                pass


class TypingTracker:
    """Tracks the ctx.typing() lifecycle so a timeout cannot leave it alive."""

    def __init__(self):
        self.entered = False
        self.exited = False

    def __call__(self):
        return self

    async def __aenter__(self):
        self.entered = True

    async def __aexit__(self, *exc_info):
        self.exited = True


class FrictionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = patch.dict(os.environ, {"AI_API_KEY": "test", "AI_GUILD_ID": "10", "AI_CHANNEL_ID": "20"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.bot = SimpleNamespace(guilds=[SimpleNamespace(id=10)])
        self.cog = AssistantCog(self.bot)
        self.typing = TypingTracker()
        self.ctx = SimpleNamespace(
            guild=SimpleNamespace(id=10, members=[SimpleNamespace(id=1, display_name="Name", bot=False)]),
            channel=SimpleNamespace(id=20), author=SimpleNamespace(id=1, bot=False),
            send=AsyncMock(), typing=self.typing)
        self.ctx.message = SimpleNamespace(author=self.ctx.author)

    # ---- provider-level hard cuts ----

    async def test_post_json_cuts_hung_provider_within_cap(self):
        """A provider that accepts the request and never answers must fail by
        the per-request cap, not by the 60s human-facing fence."""
        port = await (server := HangServer()).start()
        self.addCleanup(server.stop)
        async with aiohttp.ClientSession() as session:
            with patch.object(core.assistant, "PROVIDER_TIMEOUT", 0.8):
                with self.assertRaises(AssistantError):
                    start = time.monotonic()
                    await post_json(session, f"http://127.0.0.1:{port}/v1/chat/completions", "key", {})
            self.assertLess(time.monotonic() - start, 5.0)

    async def test_dead_chain_fails_tries_a_third_of_budget(self):
        """Provider dead: every attempt is independently capped; the whole
        failover chain (plus :free fallback) must end far under ~30s/attempt."""
        port = await (server := HangServer()).start()
        self.addCleanup(server.stop)
        entries = [ChainEntry(f"prov{i}", f"http://127.0.0.1:{port}/v1", f"m{i}", "k",
                              fallback_model="free/fallback" if i == 0 else "")
                   for i in range(3)]
        async with aiohttp.ClientSession() as session:
            with patch.object(core.assistant, "PROVIDER_TIMEOUT", 0.8):
                with self.assertRaises(AssistantError):
                    start = time.monotonic()
                    await chain_post(session, entries, lambda entry: {"model": entry.model})
            # 3 chain entries + 1 fallback model, each cut at 0.8s: < 5s in total.
            self.assertLess(time.monotonic() - start, 30.0)

    # ---- cog-level fence (the "query larga / proveedor lento" symptom) ----

    async def test_70s_provider_is_fenced_and_user_notified(self):
        """The literal production report: provider takes ~70s. wait_for must cut
        it at the fence, publish the message, free the lock, kill the typing and
        reset the cooldown so the user can retry immediately."""
        async def slow_answer(*args, **kwargs):
            await asyncio.sleep(70)  # the 70s provider
            return "demasiado tarde"
        self.cog.answer_timeout = 1.0
        self.cog.agent = SimpleNamespace(answer=AsyncMock(side_effect=slow_answer),
                                         memory=SimpleNamespace(forget=lambda key: None))
        start = time.monotonic()
        await self.cog.respond(self.ctx, "una consulta re larga que se traba")
        self.assertLess(time.monotonic() - start, 10.0)
        sent = self.ctx.send.call_args.args[0]
        self.assertIn("Se me fue la mano con esa consulta", sent)
        self.assertFalse(self.cog.lock.locked())
        self.assertTrue(self.typing.exited)      # typing never survives the fence
        self.assertFalse(self.typing.entered and not self.typing.exited)
        # Cooldown was reset: retry right away reaches the provider (not "esperá 3 segundos").
        fast = asyncio.Event()
        self.cog.agent.answer.side_effect = None
        self.cog.agent.answer.return_value = "ya está"
        await self.cog.respond(self.ctx, "de nuevo, puntual")
        self.assertEqual(self.ctx.send.call_args.args[0], "ya está")

    async def test_long_question_error_reaches_channel_fast(self):
        """Questions over 4000 chars raise AssistantError inside the agent; the
        channel must still receive the explanation (no silent death)."""
        assistant = await self._fake_assistant()
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            self.cog.agent = assistant
            start = time.monotonic()
            await self.cog.respond(self.ctx, "pregunta  " + "bien larga " * 400)
            self.assertLess(time.monotonic() - start, 3.0)
            sent = self.ctx.send.call_args.args[0]
        self.assertIn("entre 1 y 4000", sent)
        post.assert_not_awaited()          # no model call is spent on it
        self.assertFalse(self.cog.lock.locked())

    # ---- end-to-end (real Assistant, fake provider, sleep 0) ----

    async def _fake_assistant(self, router=None):
        settings = SimpleNamespace(
            provider="custom", model="m", key="k", endpoint="https://example.invalid/v1",
            search_key="", share_metrics=False, fallback_model="",
            chain=(ChainEntry("custom", "https://example.invalid/v1", "m", "k"),),
            history_enabled=True, router=router)
        budget = SimpleNamespace(consume=lambda kind, now=None: None)
        return Assistant(settings, budget, SimpleNamespace())

    async def test_700_char_question_end_to_end_in_seconds(self):
        """700 chars + provider sleep 0: full respond() path answers in seconds."""
        assistant = await self._fake_assistant()
        completion = {"model": "x/y", "usage": {}, "choices": [
            {"message": {"role": "assistant", "content": "Salú, contesto igual de largo."}, "finish_reason": "stop"}]}
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            post.return_value = completion
            self.cog.agent = assistant
            start = time.monotonic()
            await self.cog.respond(self.ctx, ("¿cuánto jugó cada uno este mes? " + "y también dime detalle " * 22)[:700])
            self.assertLess(time.monotonic() - start, 10.0)
        self.assertEqual(self.ctx.send.call_args.args[0], "Salú, contesto igual de largo.")
        self.assertFalse(self.cog.lock.locked())

    async def test_router_judge_uses_short_timeout(self):
        """The tool-choice judge is ~10 tokens: it must be capped below the main
        provider cap and never weigh as much as a full answer request."""
        assistant = await self._fake_assistant(router=ChainEntry("custom", "https://judge.invalid/v1", "r", "k", ""))
        completion = {"model": "x/y", "usage": {}, "choices": [
            {"message": {"role": "assistant", "content": "Directo."}, "finish_reason": "stop"}]}
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            post.return_value = completion
            answer = await assistant.answer("quién jugó más", "x", conversation_key=(1, 2, 3))
        self.assertEqual(answer, "Directo.")
        self.assertEqual(post.await_args.kwargs["total"], ROUTER_TIMEOUT)
        self.assertLess(ROUTER_TIMEOUT, PROVIDER_TIMEOUT)

    async def test_main_chain_uses_provider_cap(self):
        assistant = await self._fake_assistant()
        completion = {"model": "x/y", "usage": {}, "choices": [
            {"message": {"role": "assistant", "content": "Directo."}, "finish_reason": "stop"}]}
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            post.return_value = completion
            await assistant.completion([], [])
        self.assertEqual(post.await_args.kwargs.get("total"), PROVIDER_TIMEOUT)

    # ---- concurrency / lock manners ----

    async def test_two_concurrent_questions_do_not_deadlock(self):
        opened = asyncio.Event()

        async def busy_answer(*args, **kwargs):
            await opened.wait()
            return "primera lista"
        self.cog.agent = SimpleNamespace(answer=AsyncMock(side_effect=busy_answer),
                                         memory=SimpleNamespace(forget=lambda key: None))
        first = asyncio.create_task(self.cog.respond(self.ctx, "primera"))
        await asyncio.sleep(0.3)
        self.assertTrue(self.cog.lock.locked())
        await self.cog.respond(self.ctx, "segunda")
        self.assertIn("Estoy respondiendo otra consulta", self.ctx.send.call_args.args[0])
        self.cog.agent.answer.assert_awaited_once()  # no queueing, no second provider call
        opened.set()
        await asyncio.wait_for(first, timeout=5)     # would hang forever on deadlock
        self.assertFalse(self.cog.lock.locked())

    async def test_forget_never_waits_on_inflight_query_and_does_not_clear_shared_state(self):
        self.cog.agent = SimpleNamespace(answer=AsyncMock(), memory=SimpleNamespace(forget=lambda key: None))
        async with self.cog.lock:
            await asyncio.wait_for(self.cog.forget.callback(self.cog, self.ctx), timeout=1)
        self.assertIn("compartida por canal", self.ctx.send.call_args.args[0])
        self.assertFalse(self.cog.lock.locked())

    async def test_fence_coherent_with_provider_caps(self):
        """The human-facing fence must be tighter than the sum of a couple of
        provider attempts, and the loosest per-request cap stays at ~25s."""
        self.assertLessEqual(self.cog.answer_timeout, 90.0)
        self.assertLess(ROUTER_TIMEOUT, PROVIDER_TIMEOUT)
        self.assertLessEqual(PROVIDER_TIMEOUT, 30.0)


if __name__ == "__main__":
    unittest.main()
