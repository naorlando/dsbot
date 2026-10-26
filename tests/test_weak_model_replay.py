"""Replay harness: production failure shapes (deploy 7c2b10a) reproduced locally.

The failures were model-dependent (cohere/north-mini-code:free): a paraphrased
quote rejected by evidence validation, a surrendered "insufficient" after one
retry, and an instruction echo instead of a tool call. The harness now answers
these deterministically, so the replay asserts the model call count collapse.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from core.assistant import Assistant, Settings, UsageBudget
from core.assistant_policy import plan_question


def tool_call(name, arguments=None):
    return {"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments if arguments is not None else {})}}]}


class ReplayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        settings = Settings("openrouter", "cohere/north-mini-code:free", "k", "https://openrouter.ai/api/v1/chat/completions",
                            "search-test", True)
        self.agent = Assistant(settings, UsageBudget(Path(self.tmp.name) / "usage.json"), None)

    # --- 1. Dólar: era reject-quote + insufficient; ahora ni llama al modelo ---
    async def test_dollar_answered_from_sources_without_model(self):
        dollarhoy = {'url': 'https://dolarhoy.com/', 'content':
                     'Dolar hoy cotizacionDolar blue Compra$1.5450.00%Venta$1.5650.00% Actualizado '
                     '25/10/26 09:53 PMDolar Blue HistoricoDolar blueCompra$1.545Venta$1.5650.00%'
                     'Dolar Oficial Compra$1.500Venta$1.550'}
        self.agent.search = AsyncMock(return_value=[dollarhoy,
            {'url': 'https://x.com/dolarblue', 'content': 'el dolar subio tras el 0.11%'}])
        self.agent.completion = AsyncMock(side_effect=AssertionError("el modelo no debe ejecutarse"))
        answer = await self.agent.answer("cuanto esta el dolar hoy", lambda **a: {}, web=True)
        self.assertIn('$1.545', answer)
        self.assertIn('$1.565', answer)
        self.assertIn('dolarhoy.com', answer)
        self.agent.completion.assert_not_called()

    # --- 2. Historial por mensajes: era eco de instrucciones; ahora filas forzadas ---
    async def test_member_location_gets_rows_injected_not_echoed(self):
        rows = {"scanned": 30, "window_days": 14, "matches": [
            {"fecha": "2026-10-25 20:10", "autor": "Pino",
             "texto": "wire esta jugando en la voice 2 con galante"}]}

        async def weak_completion(messages, tools, **kwargs):
            # Replay: sin filas contestaba recitando instrucciones; con filas responde.
            if any('Resultados' in m['content'] for m in messages if m['role'] == 'user'):
                return {"content": "Wire apareció en #general el 25/10 a las 20:10, jugando en la voice con galante."}
            return {"content": "Busca en el historial reciente de este canal. Utiliza search_channel_history antes de responder."}

        self.agent.completion = AsyncMock(side_effect=weak_completion)
        self.agent.search = AsyncMock(side_effect=AssertionError("sin web"))
        history_search = AsyncMock(return_value=rows)
        answer = await self.agent.answer("por sus mensajes, donde esta @Wire",
                                         lambda **a: self.fail("no metrics"), history_search=history_search)
        self.assertIn('25/10', answer)
        history_search.assert_awaited_once_with("por sus mensajes, donde esta @Wire")
        self.assertNotIn('search_channel_history', answer)

    async def test_instruction_echo_falls_back_to_deterministic_rows(self):
        rows = {"scanned": 30, "window_days": 14, "matches": [
            {"fecha": "2026-10-25 20:10", "autor": "Pino", "texto": "wire esta en la voice 2"}]}

        async def hopeless_completion(messages, tools, **kwargs):
            # Even with rows on the table, the model recites its instructions.
            return {"content": "Debo utilizar la herramienta search_channel_history para el historial reciente."}

        self.agent.completion = AsyncMock(side_effect=hopeless_completion)
        history_search = AsyncMock(return_value=rows)
        answer = await self.agent.answer("por sus mensajes, donde esta @Wire",
                                         lambda **a: self.fail("no metrics"), history_search=history_search)
        self.assertIn('2026-10-25 20:10', answer)
        self.assertIn('Pino', answer)
        self.assertNotIn('search_channel_history', answer)

    # --- 3. Dólar vía evidencia (parser sin datos): la cadena de intentos sobrevive ---
    async def test_rejected_quote_then_insufficient_gets_second_reread(self):
        literal = 'Apertura del blue: $1.480 en Banco Provincia.'
        sources = [{'url': 'https://example.com', 'content': literal + ' Nota de hoy.'}]
        self.agent.search = AsyncMock(return_value=sources)
        self.agent.completion = AsyncMock(side_effect=[
            {"content": json.dumps({"status": "answer", "evidence": [
                {"source": 1, "quote": "el blue cotizaba arriba de mil" }]})},   # paraphrased → rejected
            {"content": json.dumps({"status": "insufficient", "evidence": []})}, # surrendered (production shape)
            {"content": json.dumps({"status": "answer", "evidence": [
                {"source": 1, "quote": literal}]})},                             # re-read succeeds
        ])
        answer = await self.agent.answer("cuanto esta el dolar blue hoy en Argentina hoy en Argentina", lambda **a: {}, web=True)
        self.assertIn('$1.480', answer)
        self.assertEqual(self.agent.completion.await_count, 3)

    async def test_still_insufficient_after_two_rereads_is_respected(self):
        self.agent.search = AsyncMock(return_value=[{'url': 'https://example.com', 'content': 'tema sin datos'}])
        self.agent.completion = AsyncMock(return_value={
            "content": json.dumps({"status": "insufficient", "evidence": []})})
        answer = await self.agent.answer("tema sin datos en la web en la web", lambda **a: {}, web=True)
        self.assertIn('No pude confirmar', answer)
        self.assertEqual(self.agent.completion.await_count, 3)


class RoutingTests(unittest.TestCase):
    def test_history_intents_bypass_model_decisions(self):
        for question in ('por sus mensajes, donde esta @Wire', 'cuando jugamos csgo?',
                         'quien hablo de pino', 'cuando hablamos de la juntada'):
            self.assertTrue(plan_question(question).history, question)
        self.assertFalse(plan_question('cuanto esta el dolar').history)
        self.assertFalse(plan_question('que juegos juega agu').history)
