"""Anonymized regression shapes: assert the actual input, not live-model quality."""
import copy
import json
import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, patch

from cogs.assistant import AssistantCog
from core.assistant import Assistant, AssistantError, ChainEntry, Settings, UsageBudget


@asynccontextmanager
async def typing():
    yield


class ConversationReplayTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"AI_API_KEY": "test", "AI_GUILD_ID": "10", "AI_CHANNEL_ID": "20"}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)
        self.people = [N(id=1, display_name="Alba", bot=False), N(id=2, display_name="Bruno", bot=False)]
        self.own = N(id=99, display_name="Botón", bot=True)
        self.guild = N(id=10, members=self.people)
        self.channel = N(id=20)
        self.bot = N(guilds=[self.guild], user=self.own)
        self.cog = AssistantCog(self.bot)
        self.settings = Settings("openrouter", "m:free", "test", "fixed", "search", True)
        self.agent = Assistant(self.settings, UsageBudget(self.path / "usage.json"), None)
        self.cog.agent = self.agent
        self.cog.warm_started = True
        self.at = datetime.now(timezone.utc) - timedelta(minutes=10)

    def message(self, id, text, who=0, *, age_hours=None, parent=None, cached_id=None, mentions=()):
        reference = N(message_id=parent.id if parent else cached_id, resolved=parent,
                      guild_id=10, channel_id=20) if parent or cached_id else None
        created = self.at + timedelta(seconds=id)
        if age_hours is not None:
            created = datetime.now(timezone.utc) - timedelta(hours=age_hours)
        return N(id=id, content=text, guild=self.guild, channel=self.channel,
                 author=self.own if who == "bot" else self.people[who], created_at=created,
                 mentions=list(mentions), reference=reference)

    def ctx(self, request, answer="respuesta", response_id=100):
        return N(guild=self.guild, channel=self.channel, author=request.author, message=request,
                 typing=typing, send=AsyncMock(), reply=AsyncMock(return_value=
                     self.message(response_id, answer, "bot", parent=request)))

    async def test_second_author_gets_both_question_and_actual_bot_reply(self):
        first = self.message(1, "!boton hoy celebramos el cumple y queremos stream")
        self.agent.completion = AsyncMock(return_value={"content": "¡Feliz cumple! Prendan stream."})
        first_ctx = self.ctx(first, "¡Feliz cumple! Prendan stream.", 2)
        await self.cog.respond(first_ctx, "hoy celebramos el cumple y queremos stream")
        first_ctx.reply.assert_awaited_once()
        self.assertFalse(first_ctx.reply.await_args.kwargs["mention_author"])
        captured = []

        async def complete(messages, tools, **kw):
            captured.append(copy.deepcopy(messages))
            return {"content": "Sí, ya lo saludamos; falta el stream."}

        self.agent.completion = complete
        second = self.message(3, "!boton no lo saludaste", who=1)
        await self.cog.respond(self.ctx(second, response_id=4), "no lo saludaste")
        payload = json.dumps(captured[0], ensure_ascii=False)
        self.assertIn("hoy celebramos", payload)
        self.assertIn("¡Feliz cumple! Prendan stream.", payload)
        self.assertIn("asistente", payload)
        self.assertIn("Alba", payload)
        self.assertIn("Bruno", captured[0][-1]["content"])
        self.assertIn("no lo saludaste", captured[0][-1]["content"])

    async def test_opina_prefers_recent_stream_to_yesterdays_software(self):
        await self.cog.on_message(self.message(1, "charla vieja de software", age_hours=15))
        await self.cog.on_message(self.message(2, "prendan stream que ya terminó la reunión"))
        captured = []

        async def complete(messages, tools, **kw):
            captured.append(copy.deepcopy(messages))
            return {"content": "De una, es momento de prender stream."}

        self.agent.completion = complete
        await self.cog.respond(self.ctx(self.message(3, "!boton opina", who=1)), "opina")
        context = next(m["content"] for m in captured[0] if "ANTECEDENTES" in m["content"])
        background, recent = context.split("DIÁLOGO RECIENTE", 1)
        self.assertIn("charla vieja de software", background)
        self.assertNotIn("charla vieja de software", recent)
        self.assertIn("prendan stream", recent)

    async def test_current_declarative_followup_keeps_author_and_previous_assistant(self):
        await self.cog.on_message(self.message(1, "!boton mi amigo está de cumpleaños"))
        await self.cog.on_message(self.message(2, "¡Feliz cumpleaños!", "bot"))
        self.agent.completion = AsyncMock(return_value={"content": "Por lo que contás, hay que convencerlo."})
        await self.cog.respond(self.ctx(self.message(3, "!boton encima nunca se quiere juntar")),
                               "encima nunca se quiere juntar")
        sent = self.agent.completion.call_args.args[0]
        payload = json.dumps(sent, ensure_ascii=False)
        self.assertIn("mi amigo está de cumpleaños", payload)
        self.assertIn("¡Feliz cumpleaños!", payload)
        self.assertIn("encima nunca se quiere juntar", sent[-1]["content"])

    async def test_reply_without_ping_invokes_bot_and_resolves_cached_parent(self):
        parent = self.message(1, "La propuesta es jugar el viernes.", "bot")
        await self.cog.on_message(parent)
        current = self.message(2, "y si lo pasamos al sábado?", who=1, cached_id=parent.id)
        self.bot.get_context = AsyncMock(return_value=self.ctx(current))
        self.agent.completion = AsyncMock(return_value={"content": "Sábado también sirve."})
        await self.cog.on_message(current)
        self.agent.completion.assert_awaited_once()
        self.assertIn("La propuesta es jugar el viernes", self.agent.completion.call_args.args[0][-1]["content"])

    async def test_direct_mention_is_one_invocation_and_other_mentions_are_resolved(self):
        current = self.message(1, "<@99> qué opinás de lo que contó <@2>?", mentions=[self.own, self.people[1]])
        self.bot.get_context = AsyncMock(return_value=self.ctx(current))
        self.agent.completion = AsyncMock(return_value={"content": "Banco la propuesta."})
        await self.cog.on_message(current)
        self.agent.completion.assert_awaited_once()
        last = self.agent.completion.call_args.args[0][-1]["content"]
        self.assertIn("Bruno", last)
        self.assertNotIn("<@2>", last)

    async def test_bare_command_is_a_valid_summons_with_or_without_recent_chat(self):
        self.agent.completion = AsyncMock(return_value={"content": "¿Qué andan armando?"})
        await self.cog.respond(self.ctx(self.message(1, "!boton")), "")
        self.agent.completion.assert_awaited_once()
        self.assertIn("sumarte a la conversación", self.agent.completion.call_args.args[0][-1]["content"])

    async def test_explicit_web_excludes_legacy_memory_invocation_and_dialogue(self):
        self.agent.memory.remember((10, 20, 1), "SECRETO_DEL_CANAL", "respuesta privada")
        self.agent.web_research = AsyncMock(return_value=("", [{"url": "https://example.com",
            "content": "Resultado público comprobado: ganó el equipo azul."}]))
        snapshots = []

        async def complete(messages, tools, **kw):
            snapshots.append(copy.deepcopy(messages))
            return {"content": json.dumps({"status": "answer", "evidence": [{"source": 1, "passage": 1}]})}

        self.agent.completion = complete
        await self.agent.answer("resultado público", lambda **kw: {}, web=True, conversation_key=(10, 20, 1),
            dialogue_context="SECRETO_DEL_CANAL", invocation="Autor privado", ambient_digest="nota privada")
        serialized = json.dumps(snapshots)
        for private in ("SECRETO_DEL_CANAL", "Autor privado", "nota privada", "respuesta privada"):
            self.assertNotIn(private, serialized)

    async def test_internal_plan_is_discarded_and_retried_once_without_more_tools(self):
        leak = "El usuario pide un chiste. Debo responder y revisar las herramientas disponibles."
        captured = []
        outputs = iter([{"content": leak}, {"content": "Ese lag ya paga alquiler en el servidor."}])

        async def complete(messages, tools, **kw):
            captured.append((copy.deepcopy(messages), copy.deepcopy(tools)))
            return next(outputs)

        self.agent.completion = complete
        result = await self.agent.answer("hacé un chiste", lambda **kw: {})
        self.assertIn("lag", result)
        self.assertNotIn(leak, json.dumps(captured[1][0]))
        self.assertEqual(captured[1][1], [])

    async def test_repeated_plan_never_publishes_and_logs_no_response_content(self):
        leak = "El usuario pide un chiste. Debo responder y revisar las herramientas disponibles."
        self.agent.completion = AsyncMock(return_value={"content": leak})
        with self.assertLogs("dsbot", level="INFO") as logs:
            with self.assertRaises(AssistantError):
                await self.agent.answer("chiste", lambda **kw: {})
        self.assertNotIn(leak, "\n".join(logs.output))
        self.assertEqual(self.agent.completion.await_count, 2)

    async def test_first_pass_model_may_answer_directly_and_spends_the_normal_budget(self):
        from dataclasses import replace
        self.agent.settings = replace(self.settings, router=ChainEntry("openrouter", "fixed", "r:free", "test"))
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            post.return_value = {"choices": [{"message": {"content": "Banco prender stream."}, "finish_reason": "stop"}]}
            result = await self.agent.answer("opina", lambda **kw: {}, dialogue_context="prendan stream")
        self.assertIn("stream", result)
        self.assertEqual(post.call_args.args[3]["tool_choice"], "auto")
        self.assertEqual(json.loads(self.agent.budget.path.read_text())["llm"], 1)

    async def test_exact_http_payload_is_json_serializable_and_clearly_separates_roles(self):
        await self.cog.on_message(self.message(1, "Terminó la reunión; prendan stream."))
        await self.cog.on_message(self.message(2, "Banco, lo hacemos después de cenar.", "bot"))
        request = self.message(3, "!boton opina", who=1)
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            post.return_value = {"choices": [{"message": {"content": "Banco el stream después de cenar."},
                                               "finish_reason": "stop"}]}
            await self.cog.respond(self.ctx(request), "opina")
        # This is the body passed to the HTTP client, not a reconstructed prompt.
        wire = json.loads(json.dumps(post.call_args.args[3], ensure_ascii=False))
        self.assertEqual([m["role"] for m in wire["messages"]], ["system", "user", "user"])
        self.assertNotIn("Terminó la reunión", wire["messages"][0]["content"])
        data = wire["messages"][1]["content"]
        self.assertIn("humano", data)
        self.assertIn("asistente", data)
        self.assertIn("Terminó la reunión", data)
        self.assertIn("Banco, lo hacemos después de cenar", data)
        current = wire["messages"][-1]["content"]
        self.assertIn("Autor actual: Bruno", current)
        self.assertTrue(current.endswith("Mensaje actual: opina"))
        self.assertNotIn("!boton opina", data)
        self.assertEqual(wire["tool_choice"], "auto")
        self.assertNotIn("Authorization", wire)
        self.assertNotIn("SimpleNamespace", json.dumps(wire))

    async def test_provider_truncation_metadata_survives_parsing_and_gets_one_repair(self):
        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            post.side_effect = [
                {"choices": [{"message": {"content": "incompleto"}, "finish_reason": "max_tokens"}]},
                {"choices": [{"message": {"content": "Respuesta terminada."}, "finish_reason": "stop"}]}]
            answer = await self.agent.answer("opiná", lambda **kw: {})
        self.assertEqual(answer, "Respuesta terminada.")
        self.assertEqual(post.await_count, 2)
        second = post.await_args_list[1].args[3]
        self.assertEqual(second["tool_choice"], "none")
        self.assertNotIn("incompleto", json.dumps(second))
