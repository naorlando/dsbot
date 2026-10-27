"""Replay harness: production failure shapes reproduced against the agentic loop.

The old deterministic customs (dolar parser, forced history scan, partido
filters, scaffolds) are gone: the model decides with its tool menu. The
replays assert the agentic equivalents still hold — evidence retries,
fail-closed guards, budget charges and the Google-grounded search path.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.assistant import Assistant, AssistantError, Settings, UsageBudget
from core.assistant_policy import plan_question
from core.assistant_tools import GroundError


def tool_call(name, arguments=None):
    return {"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments if arguments is not None else {})}}]}


def web_answer(quote="Dato actual confirmado", source=1):
    return {"content": json.dumps({"status": "answer", "evidence": [{"source": source, "quote": quote}]})}


class ReplayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        settings = Settings("openrouter", "cohere/north-mini-code:free", "k", "https://openrouter.ai/api/v1/chat/completions",
                            "search-test", True)
        self.agent = Assistant(settings, UsageBudget(Path(self.tmp.name) / "usage.json"), None)

    # --- 1. Search: budget se cobra una vez por investigación, el modelo decide ---
    async def test_search_budget_consumed_once_per_research(self):
        self.agent.search = AsyncMock(return_value=[
            {"url": "https://example.com", "content": "Dato actual confirmado"}])
        self.agent.completion = AsyncMock(return_value=web_answer())
        await self.agent.answer("cuanto esta el dolar", lambda **a: {}, web=True)
        self.assertEqual(self.agent.search.await_count, 1)
        self.assertEqual(json.loads(self.agent.budget.path.read_text())["search"], 1)

    # --- 2. Grounding Google primero, Tavily sólo como respaldo ---
    async def test_google_grounding_ships_direct_answer_without_model(self):
        sources = [{"title": "T", "url": "https://sporting.test/cronica", "content": "Boca gano 2-1"}]
        with patch("core.assistant.provider_key", return_value="gkey"), \
                patch("core.assistant.google_ground", new_callable=AsyncMock) as ground:
            ground.return_value = ("Boca gano 2-1 ante Talleres anoche.", sources)
            self.agent.completion = AsyncMock(side_effect=AssertionError("el modelo no debe ejecutarse"))
            self.agent.search = AsyncMock(side_effect=AssertionError("sin tavily"))
            answer = await self.agent.answer("cuanto salio boca", lambda **a: {}, web=True)
        self.assertIn("2-1", answer)
        self.assertIn("Fuentes consultadas", answer)
        self.assertIn("https://sporting.test/cronica", answer)
        self.agent.completion.assert_not_called()
        ground.assert_awaited_once()

    async def test_ground_failure_falls_back_to_tavily(self):
        with patch("core.assistant.provider_key", return_value="gkey"), \
                patch("core.assistant.google_ground", new_callable=AsyncMock) as ground:
            ground.side_effect = GroundError("google ground rate limited")
            self.agent.search = AsyncMock(return_value=[
                {"url": "https://example.com", "content": "Dato actual confirmado"}])
            self.agent.completion = AsyncMock(return_value=web_answer())
            answer = await self.agent.answer("cuanto esta el dolar", lambda **a: {}, web=True)
        self.assertIn("Dato actual confirmado", answer)
        self.agent.search.assert_awaited_once()
        self.assertEqual(self.agent.completion.await_count, 1)

    async def test_web_tool_grounds_and_does_not_call_model_on_hit(self):
        # El modelo pide search_web en el agente y el harness responde directo.
        with patch("core.assistant.provider_key", return_value="gkey"), \
                patch("core.assistant.google_ground", new_callable=AsyncMock) as ground:
            ground.return_value = ("Salio 2-1 de visitante.", [
                {"title": "T", "url": "https://sporting.test/x", "content": ""}])
            self.agent.completion = AsyncMock(side_effect=[tool_call("search_web", {}),
                                                           AssertionError("no debería haber segunda llamada")])
            answer = await self.agent.answer("cuanto salio racing", lambda **a: {})
        self.assertIn("2-1", answer)
        self.assertEqual(self.agent.completion.await_count, 1)

    # --- 3. Historial: la herramienta es del modelo y escribe su propio query ---
    async def test_history_tool_call_with_model_written_query(self):
        rows = {"scanned": 30, "window_days": 14, "matches": [
            {"fecha": "2026-10-25 20:10", "autor": "Pino",
             "texto": "wire esta jugando en la voice 2 con galante"}]}
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("search_channel_history", {"query": "@wire voice galante"}),
            {"content": "Wire apareció en #general el 25/10 a las 20:10, jugando en la voice con galante."}])
        self.agent.search = AsyncMock(side_effect=AssertionError("sin web"))
        history_search = AsyncMock(return_value=rows)
        answer = await self.agent.answer("por sus mensajes, donde esta @Wire",
                                         lambda **a: self.fail("no metrics"), history_search=history_search)
        self.assertIn("25/10", answer)
        history_search.assert_awaited_once_with("@wire voice galante")
        self.assertNotIn("search_channel_history", answer)

    # --- 4. Reintentos de evidencia sobreviven en el path Tavily ---
    async def test_rejected_quote_then_insufficient_gets_second_reread(self):
        literal = "Apertura del blue: $1.480 en Banco Provincia."
        sources = [{"url": "https://example.com", "content": literal + " Nota de hoy."}]
        self.agent.search = AsyncMock(return_value=sources)
        self.agent.completion = AsyncMock(side_effect=[
            {"content": json.dumps({"status": "answer", "evidence": [
                {"source": 1, "quote": "el blue cotizaba arriba de mil"} ]})},   # paraphrased → rejected
            {"content": json.dumps({"status": "insufficient", "evidence": []})}, # surrendered (production shape)
            {"content": json.dumps({"status": "answer", "evidence": [
                {"source": 1, "quote": literal}]})},                             # re-read succeeds
        ])
        answer = await self.agent.answer("cuanto esta el dolar blue hoy en Argentina", lambda **a: {}, web=True)
        self.assertIn("$1.480", answer)
        self.assertEqual(self.agent.completion.await_count, 3)

    async def test_still_insufficient_after_two_rereads_is_respected(self):
        self.agent.search = AsyncMock(return_value=[{"url": "https://example.com", "content": "tema sin datos"}])
        self.agent.completion = AsyncMock(return_value={
            "content": json.dumps({"status": "insufficient", "evidence": []})})
        answer = await self.agent.answer("tema sin datos en la web", lambda **a: {}, web=True)
        self.assertIn("No pude confirmar", answer)
        self.assertEqual(self.agent.completion.await_count, 3)

    # --- 5. Guardas fail-closed que siguen aplicando ---
    async def test_instruction_echo_after_history_scan_fails_closed(self):
        rows = {"scanned": 30, "window_days": 14, "matches": [
            {"fecha": "2026-10-25 20:10", "autor": "Pino", "texto": "wire esta en la voice 2"}]}
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("search_channel_history", {"query": "@wire"}),
            {"content": "Debo utilizar la herramienta search_channel_history para el historial reciente."}])
        history_search = AsyncMock(return_value=rows)
        with self.assertRaises(AssistantError) as ctx:
            await self.agent.answer("por sus mensajes, donde esta @Wire",
                                    lambda **a: self.fail("no metrics"), history_search=history_search)
        self.assertNotIn("Debo utilizar", str(ctx.exception))

    async def test_clarification_tool_still_available_for_real_questions(self):
        self.agent.completion = AsyncMock(side_effect=[{"content": "Hola."}])
        await self.agent.answer("cuanto jugue hoy mal", lambda **a: {"minutes": 2})
        tools = [t["function"]["name"] for t in self.agent.completion.call_args.args[1]]
        self.assertIn("ask_clarification", tools)

    async def test_glued_canned_sentences_are_collapsed(self):
        self.agent.completion = AsyncMock(return_value={
            "content": "Por qué no intentas crear algo, como servir café? ¿Por qué no intentas crear algo, como servir café? ¿?"})
        answer = await self.agent.answer("di algo raro para probar", lambda **a: self.fail("no metrics"))
        self.assertEqual(answer.count("servir café"), 1)

    async def test_memory_mask_echo_is_never_published(self):
        self.agent.search = AsyncMock(return_value=[
            {"url": "https://example.com", "content": "Dolar blue Compra$1.545 Venta$1.565"}])
        self.agent.completion = AsyncMock(return_value=web_answer(quote="Dolar blue Compra$1.545 Venta$1.565"))
        await self.agent.answer("cuanto esta el dolar", lambda **a: {}, web=True, conversation_key=(1, 2, 3))
        # Next turn in the same conversation carries the internal note in history;
        # north-mini recited it verbatim as the answer (production 11:13).
        self.agent.completion = AsyncMock(return_value={
            "content": "Consulté una búsqueda web: una nueva pregunta requiere evidencia nueva."})
        answer = await self.agent.answer("cualquier otra cosa sin web", lambda **a: self.fail("no metrics"),
                                         conversation_key=(1, 2, 3))
        self.assertIn("trabó la lengua", answer)


class RoutingTests(unittest.TestCase):
    def test_doxx_refusal_only_custom_in_policy(self):
        for question in ("busca dateas una persona", "dame la IP de alguien",
                         "todos los datos de alguien", "domicilio de pino"):
            self.assertTrue(plan_question(question).reply, question)
        # Public identity fees are not doxxing; normal questions pass untouched.
        self.assertFalse(plan_question("cuanto sale el DNI argentino").reply)
        self.assertFalse(plan_question("cuanto esta el dolar").reply)
        self.assertFalse(plan_question("haceme un itinerario de 30 dias en japon").reply)

    def test_query_cleanup_strips_search_verbs(self):
        self.assertEqual(plan_question("buscame el tema mas famoso de rick astley dale rapidito").query,
                         "el tema mas famoso de rick astley")
