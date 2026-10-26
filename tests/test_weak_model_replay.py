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

    async def test_three_matches_collapse_to_freshest_quote(self):
        self.agent.search = AsyncMock(return_value=[
            {'url': 'https://trendsmask.test', 'content': 'El ultimo partido de Boca fue un empate 0-0 contra Barracas Central, Torneo Clausura 2025.'},
            {'url': 'https://sporting.test/sanlorenzo', 'content': 'Boca le gano 2-0 a San Lorenzo en el Nuevo Gasometro, por la fecha 10 del Clausura 2026.'},
            {'url': 'https://sporting.test/talleres', 'content': 'Boca derroto a Talleres por 2-1 en el partido de la jornada 13 del Clausura 2026 en La Bombonera.'}])
        self.agent.completion = AsyncMock(return_value={"content": json.dumps({"status": "answer", "evidence": [
            {"source": 1, "quote": "El ultimo partido de Boca fue un empate 0-0 contra"},
            {"source": 2, "quote": "Boca le gano 2-0 a San Lorenzo en el Nuevo"},
            {"source": 3, "quote": "Boca derroto a Talleres por 2-1 en el partido"}]})})
        answer = await self.agent.answer("como salio boca", lambda **a: {}, web=True)
        self.assertIn('Talleres', answer)
        self.assertIn('2-1', answer)
        self.assertNotIn('Barracas', answer)
        self.assertNotIn('San Lorenzo', answer)

    async def test_clarification_tool_not_offered_for_non_question(self):
        # "sos un hdp man dale" hit ask_clarification in production: pure friction.
        plan = plan_question("sos un hdp man dale")
        answer_produced_by_policy = plan.reply
        self.assertIn('tranquilo', answer_produced_by_policy)
        # A non-question with no interrogative cue never gets the clarify tool.
        self.agent.completion = AsyncMock(side_effect=[{"content": "Tamo tranquilo."}])
        answer = await self.agent.answer("hoy la cancha re abierta man", lambda **a: self.fail("no metrics"))
        self.assertEqual(answer, "Tamo tranquilo.")
        tools = [t["function"]["name"] for t in self.agent.completion.call_args.args[1]]
        self.assertNotIn("ask_clarification", tools)

    async def test_clarification_tool_still_available_for_real_questions(self):
        self.agent.completion = AsyncMock(side_effect=[{"content": "Hola."}])
        await self.agent.answer("cuanto jugue hoy mal", lambda **a: {"minutes": 2})
        tools = [t["function"]["name"] for t in self.agent.completion.call_args.args[1]]
        self.assertIn("ask_clarification", tools)

    async def test_glued_canned_sentences_are_collapsed(self):
        self.agent.completion = AsyncMock(return_value={
            "content": "Por qué no intentas crear algo, como servir café? ¿Por qué no intentas crear algo, como servir café? ¿?"})
        answer = await self.agent.answer("di algo raro para probar", lambda **a: self.fail("no metrics"))
        self.assertEqual(answer.count('servir café'), 1)

    async def test_memory_mask_echo_is_never_published(self):
        self.agent.search = AsyncMock(return_value=[{'url': 'https://dolarhoy.test', 'content': 'Dolar blue Compra$1.5450.00%Venta$1.5650.00% Actualizado'}])
        await self.agent.answer('cuanto esta el dolar', lambda **a: {}, web=True, conversation_key=(1, 2, 3))
        # Next turn in the same conversation carries the internal note in history;
        # north-mini recited it verbatim as the answer (production 11:13).
        self.agent.completion = AsyncMock(return_value={
            "content": "Consulté una búsqueda web: una nueva pregunta requiere evidencia nueva."})
        answer = await self.agent.answer("cualquier otra cosa sin web", lambda **a: self.fail("no metrics"),
                                         conversation_key=(1, 2, 3))
        self.assertIn('trabó la lengua', answer)


class RoutingTests(unittest.TestCase):
    def test_history_intents_bypass_model_decisions(self):
        for question in ('por sus mensajes, donde esta @Wire', 'cuando jugamos csgo?',
                         'quien hablo de pino', 'cuando hablamos de la juntada',
                         'que dice hiken?', 'q opinas de q joaco se fue a japon',
                         'busca los mensajes de hiken que nombran one piece'):
            self.assertTrue(plan_question(question).history, question)
        self.assertFalse(plan_question('cuanto esta el dolar').history)
        self.assertFalse(plan_question('que juegos juega agu').history)
        # Public-figure news stays on the web path.
        self.assertFalse(plan_question('quien gano el repechage ayer').history)

    def test_banter_covers_destroy_and_explicit_junk(self):
        for question in ('destruite', 'matate', 'blowjob', 't garch?',
                         'servime un cafe y destruite'):
            self.assertTrue(plan_question(question).reply, question)
        # north-mini's canned "serví café" joke never reaches production again.
        self.assertNotIn('café', plan_question('servime un cafe y destruite').reply)

    def test_emoji_only_input_is_rejected_without_model(self):
        plan = plan_question('🎢🤸‍♂️🙃🏈👰')
        self.assertTrue(plan.reply)

    def test_new_web_verbs_route_search(self):
        self.assertTrue(plan_question('pasame el tema mas famoso de rick astley').web)
        self.assertTrue(plan_question('dame la receta de la coca cola').web)
        self.assertTrue(plan_question('investiga y dame la receta de la coca cola').web)

    def test_pure_banter_gets_zero_model_reply(self):
        plan = plan_question('sos un hdp man dale')
        self.assertTrue(plan.reply)
        self.assertIn('tranquilo', plan.reply)
        self.assertFalse(plan.web)
        # Inside a real question, insult words don't hijack the route.
        self.assertFalse(plan_question('que jodido estas boludo, cuanto esta el dolar').reply)
        self.assertTrue(plan_question('que jodido estas boludo, cuanto esta el dolar').web)

    def test_partido_kind_marked_for_freshness_filter(self):
        plan = plan_question('como salio boca')
        self.assertEqual(plan.kind, 'partido')
        # The sportytrader Serie C source never named the team; require its token so
        # generic-results pages are filtered before the model quotes them.
        self.assertIn('boca', plan.required)
        self.assertIn('river', plan_question('quien gano river hoy').required)
        self.assertIn('boca', plan_question('como salio boca el 27/09').required)
        from core.assistant_policy import relevant
        self.assertFalse(relevant({'title': 'Serie C', 'content': 'AS Cittadella FC Arzignano Valchiampo 1 0 Fin Union Brescia'}, plan))
        self.assertTrue(relevant({'title': 'Crónica', 'content': 'Boca se impuso 2-1 ante Talleres en La Bombonera'}, plan))
        self.assertEqual(plan_question('cuanto esta el dolar').kind, 'dolar')
        self.assertEqual(plan_question('que paso el 9 de diciembre de 2018').kind, '')

    async def test_partido_quote_without_result_is_never_published(self):
        # "El arquero de Boca... se aseguró la punta" (deploy 18:42): no score, yet published.
        self.agent.search = AsyncMock(return_value=[
            {'url': 'https://smsport.test', 'content':
             'Boca se aseguró la punta de la Anual a dos fechas del final. '
             'El arquero desvió la pelota tras una media vuelta de Morales dentro del área chica. '}])
        self.agent.completion = AsyncMock(return_value={"content": json.dumps(
            {"status": "answer", "evidence": [
                {"source": 1, "quote": "El arquero de Boca, en el tercer minuto de descuento, desvió la pelota tras una media vuelta de Morales"}]})})
        answer = await self.agent.answer("como salio boca", lambda **a: {}, web=True)
        self.assertNotIn('desv', answer)
        self.assertIn('No pude confirmar', answer)

    async def test_general_question_answered_directly_without_capabilities(self):
        # "haceme un itinerario de 30 dias en japon" got a refusal + capability bullets.
        self.agent.completion = AsyncMock(side_effect=[
            {"content": "Buena meta. Día 1-7 Tokio: Asakusa..."}])
        answer = await self.agent.answer("haceme un itinerario de 30 dias en japon",
                                         lambda **a: self.fail("no metrics"))
        self.assertIn('Tokio', answer)
        system = self.agent.completion.call_args.args[0][0]["content"]
        self.assertNotIn("Capacidades reales", system)
        self.assertIn("sólo lectura es sobre datos", system)
