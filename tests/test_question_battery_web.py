"""Batería de preguntas web reales (rioplatense) replayeadas contra el loop de Botón.

Cada pregunta es una forma tal cual la escribiría un usuario de Discord (minúsculas,
sin signos de apertura, con sur isError?). La conducta del modelo es un guion
scripteado (tool calls, JSON de evidencia, fracasos controlados) y se verifica la
ruta del harness: google grounding → retry 429 → Tavily, evidencia literal vs
mask de verificación, nudges no_tools, refusos de política y UsageBudget real.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.assistant import Assistant, AssistantError, Settings, UsageBudget
from core.assistant_policy import plan_question


def tool_call(name, arguments=None):
    return {"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments if arguments is not None else {})}}]}


def web_answer(quote, source=1):
    return {"content": json.dumps({"status": "answer",
                                   "evidence": [{"source": source, "quote": quote}]})}


def tavily_sources(content, url="https://example.com", title="Fuente"):
    return [{"title": title, "url": url, "content": content}]


# --- fakes de red (mismo estilo que tests/test_weak_model_replay.py) ----------

class _FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def read(self):
        return json.dumps(self._payload).encode("utf-8")


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls += 1
        return self.responses[min(self.calls - 1, len(self.responses) - 1)]


class _WeatherResponse:
    def __init__(self, payload):
        self.status = 200
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def read(self):
        return json.dumps(self._payload).encode("utf-8")


class _WeatherSession:
    """aiohttp fake para los dos endpoints fijos de Open-Meteo (geocoding + forecast)."""

    def __init__(self, geo, forecast):
        self._geo, self._forecast = geo, forecast
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(url)
        return _WeatherResponse(self._geo if "geocoding" in url else self._forecast)


_GEO = {"results": [{"name": "Buenos Aires", "country": "Argentina",
                     "latitude": -34.6, "longitude": -58.4}]}
_FORECAST_LLUVIA = {
    "current": {"temperature_2m": 15, "apparent_temperature": 13, "precipitation": 0.4},
    "daily": {"time": ["2026-10-26", "2026-10-27", "2026-10-28"],
              "temperature_2m_max": [18.0, 17.0, 20.0],
              "temperature_2m_min": [9.0, 8.0, 10.0],
              "precipitation_probability_max": [70, 25, 10]}}
_FORECAST_CALOR = {
    "current": {"temperature_2m": 31, "apparent_temperature": 34, "precipitation": 0},
    "daily": {"time": ["2026-10-26", "2026-10-27", "2026-10-28"],
              "temperature_2m_max": [32.0, 33.0, 30.0],
              "temperature_2m_min": [21.0, 22.0, 20.0],
              "precipitation_probability_max": [5, 10, 0]}}
_FORECAST_FRIO = {
    "current": {"temperature_2m": 8, "apparent_temperature": 6, "precipitation": 0},
    "daily": {"time": ["2026-10-26", "2026-10-27", "2026-10-28"],
              "temperature_2m_max": [14.0, 15.0, 16.0],
              "temperature_2m_min": [3.0, 4.0, 5.0],
              "precipitation_probability_max": [0, 10, 5]}}


class QuestionBatteryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        settings = Settings("openrouter", "cohere/north-mini-code:free", "k",
                            "https://openrouter.ai/api/v1/chat/completions",
                            "search-test", True)
        self.agent = Assistant(settings, UsageBudget(Path(self.tmp.name) / "usage.json"), None)

    # --- deportes ----------------------------------------------------------

    async def test_partido_boca_grounding_ok_nunca_llama_al_modelo(self):
        # "cuanto salio el partido de boca anoche?" → google grounding responde
        # con crónica + fuentes; el modelo y Tavily no participan.
        self.agent.search = AsyncMock(side_effect=AssertionError("sin tavily"))
        self.agent.completion = AsyncMock(side_effect=AssertionError("el modelo no debe ejecutarse"))
        with patch("core.assistant.provider_key", return_value="gkey"), \
                patch("core.assistant.google_ground", new_callable=AsyncMock) as ground:
            ground.return_value = ("Boca le gano 2-1 a Talleres anoche en la Bombonera.", [
                {"title": "Cronica", "url": "https://depor.test/boca-talleres", "content": ""}])
            answer = await self.agent.answer("cuanto salio el partido de boca anoche?",
                                             lambda **a: self.fail("no metrics"), web=True)
        self.assertIn("2-1", answer)
        self.assertIn("Fuentes consultadas", answer)
        self.assertIn("https://depor.test/boca-talleres", answer)
        self.agent.completion.assert_not_called()
        self.agent.search.assert_not_called()
        ground.assert_awaited_once()

    async def test_major_rusherking_ground_429_reintenta_y_cae_a_tavily(self):
        # "como came rusherking en el major?" → google devuelve 429, reintenta con
        # backoff, vuelve a fallar y baja a Tavily; la respuesta final surge de
        # evidencia literal validada, no de la nada.
        quote = "Rusherking cayo 13-11 en la segunda ronda del major y quedo eliminado del torneo."
        session = _FakeSession([_FakeResponse(429, {}), _FakeResponse(429, {})])
        self.agent.session = session
        self.agent.search = AsyncMock(return_value=tavily_sources(
            quote, url="https://esports.test/rusherking", title="Hltv"))
        self.agent.completion = AsyncMock(return_value=web_answer(quote=quote))
        with patch("core.assistant.provider_key", return_value="gkey"), \
                patch("core.assistant_tools.asyncio.sleep", new_callable=AsyncMock) as nap:
            answer = await self.agent.answer("como came rusherking en el major?",
                                             lambda **a: self.fail("no metrics"), web=True)
        self.assertEqual(session.calls, 2)  # un retry con backoff antes del GroundError
        nap.assert_awaited_once()
        self.assertIn("13-11", answer)
        self.assertIn("Fuentes consultadas", answer)
        self.assertIn("https://esports.test/rusherking", answer)
        self.agent.search.assert_awaited_once_with("como came rusherking en el major")
        self.assertEqual(self.agent.completion.await_count, 1)
        self.assertEqual(json.loads(self.agent.budget.path.read_text())["search"], 1)

    # --- dólar -------------------------------------------------------------

    async def test_dolar_blue_cita_literal_se_publica(self):
        # "cuanto cerro el blue hoy?" → Tavily da la fuente de cotización; el
        # quote del JSON de evidencia es literal del content → se publica.
        content = "El dolar blue cerro a $1.565 para la venta y la brecha quedo cerca del 29%."
        self.agent.search = AsyncMock(return_value=tavily_sources(
            content, url="https://dolar.test/blue-hoy", title="Dolar Hoy"))
        self.agent.completion = AsyncMock(
            return_value=web_answer(quote="El dolar blue cerro a $1.565 para la venta"))
        with patch("core.assistant.provider_key", return_value=""):
            answer = await self.agent.answer("cuanto cerro el blue hoy?",
                                             lambda **a: self.fail("no metrics"), web=True)
        self.assertIn("$1.565", answer)
        self.assertIn("Fuentes consultadas", answer)
        self.assertIn("https://dolar.test/blue-hoy", answer)
        self.agent.search.assert_awaited_once()

    async def test_dolar_oficial_quote_inventado_sale_mask_verificacion(self):
        # "a que esta el dolar oficial" → el modelo parafrasea (quote NO literal),
        # render_evidence lo rechaza, hay nudge de reintento, el modelo vuelve a
        # inventar y el harness publica el mask en lugar del dato inventado.
        content = "El dolar oficial cerro a $1.180 para la venta en el banco Nacion."
        self.assertFalse("El dolar oficial subio a $1.240 despues de la suba" in content)
        self.agent.search = AsyncMock(return_value=tavily_sources(
            content, url="https://dolar.test/oficial", title="Banco"))
        self.agent.completion = AsyncMock(side_effect=[
            web_answer(quote="El dolar oficial subio a $1.240 despues de la suba"),
            web_answer(quote="El dolar oficial subio a $1.240 y sigue subiendo")])
        with patch("core.assistant.provider_key", return_value=""):
            answer = await self.agent.answer("a que esta el dolar oficial",
                                             lambda **a: self.fail("no metrics"), web=True)
        self.assertIn("fuentes", answer.lower())
        self.assertNotIn("$1.240", answer)
        self.assertNotIn("$1.180", answer)
        self.assertEqual(self.agent.completion.await_count, 2)

    # --- clima -------------------------------------------------------------

    async def test_lluvia_partido_river_va_por_weather_check(self):
        # "va a llover en el partido de river?" → la model elige weather_check
        # (geocoding + forecast reales de Open-Meteo, mockeados) sobre buscar.
        self.agent.session = _WeatherSession(_GEO, _FORECAST_LLUVIA)
        self.agent.search = AsyncMock(side_effect=AssertionError("sin tavily"))
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("weather_check", {"place": "buenos aires"}),
            {"content": "Si, mañana esta feo: 70% de probabilidad de lluvia para el partido."}])
        answer = await self.agent.answer("va a llover en el partido de river?",
                                         lambda **a: self.fail("no metrics"))
        self.assertIn("70%", answer)
        self.assertEqual(len(self.agent.session.calls), 2)  # geocoding + forecast
        self.assertEqual(self.agent.completion.await_count, 2)
        first_menu = [t["function"]["name"] for t in self.agent.completion.call_args_list[0].args[1]]
        self.assertIn("weather_check", first_menu)

    async def test_frio_en_neuquen_la_model_elige_buscar_no_el_clima(self):
        # "hace frio en neuquen hoy?" → la model resuelve por search_web con
        # evidencia literal; weather_check no llega a pegarle a Open-Meteo.
        session = _WeatherSession(_GEO, _FORECAST_FRIO)
        self.agent.session = session
        content = "Neuquen amanecio con 3 grados de minima y una maxima de 14, dia mas frio de la semana."
        self.agent.search = AsyncMock(return_value=tavily_sources(
            content, url="https://meteo.test/neuquen", title="Meteo"))
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("search_web", {}),
            web_answer(quote="Neuquen amanecio con 3 grados de minima y una maxima de 14")])
        with patch("core.assistant.provider_key", return_value=""):
            answer = await self.agent.answer("hace frio en neuquen hoy?",
                                             lambda **a: self.fail("no metrics"))
        self.assertIn("maxima de 14", answer)
        self.assertIn("Fuentes consultadas", answer)
        self.agent.search.assert_awaited_once()
        self.assertEqual(session.calls, [])  # weather_check jamas fue invocada

    # --- mixto realista (misma conversación: clima + web) -------------------

    async def test_calor_cancha_y_rally_en_la_misma_conversacion(self):
        key = (1, 2, 3)
        self.agent.session = _WeatherSession(_GEO, _FORECAST_CALOR)
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("weather_check", {"place": "buenos aires"}),
            {"content": "Si, mañana llega a 32 grados en Buenos Aires: ideal para ir a la cancha."}])
        primer = await self.agent.answer("hace calor para ir a la cancha mañana?",
                                         lambda **a: self.fail("no metrics"), conversation_key=key)
        self.assertIn("32", primer)
        # Segunda pregunta, ahora web: google grounding ok; Tavily no participa y
        # la conversación previa (cancha) viaja en el historial.
        self.agent.session = _FakeSession([_FakeResponse(503, {})])
        self.agent.search = AsyncMock(side_effect=AssertionError("sin tavily"))
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("search_web", {}), AssertionError("no debe haber segunda llamada")])
        with patch("core.assistant.provider_key", return_value="gkey"), \
                patch("core.assistant.google_ground", new_callable=AsyncMock) as ground:
            ground.return_value = ("En el rally de hoy salio primero el puntero con su Ford del equipo oficial.", [
                {"title": "Deportes", "url": "https://depor.test/rally", "content": ""}])
            answer = await self.agent.answer("quien salio primero en el rally?",
                                             lambda **a: self.fail("no metrics"), conversation_key=key)
        self.assertIn("rally", answer.lower())
        self.assertIn("Fuentes consultadas", answer)
        self.assertIn("https://depor.test/rally", answer)
        self.assertEqual(self.agent.completion.await_count, 1)  # sólo decide la tool
        historial = json.dumps(self.agent.completion.call_args.args[0], ensure_ascii=False)
        self.assertIn("cancha", historial)

    # --- rejects -----------------------------------------------------------

    async def test_bitcoin_responde_cotizacion_y_rechaza_el_contrato(self):
        # "dime la cotizacion del bitcoin en tiempo real y firmame un contrato de
        # inversion" → la model busca el dato y el texto grounded trae el no a
        # la asistencia financiera; sin Tavily ni segunda llamada de modelo.
        self.agent.search = AsyncMock(side_effect=AssertionError("sin tavily"))
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("search_web", {}), AssertionError("no debe haber segunda llamada")])
        with patch("core.assistant.provider_key", return_value="gkey"), \
                patch("core.assistant.google_ground", new_callable=AsyncMock) as ground:
            ground.return_value = ("El bitcoin cotiza en 62.000 dolares hoy; no firmo contratos "
                                   "ni doy asesoramiento financiero.", [
                {"title": "Mercados", "url": "https://mercados.test/btc", "content": ""}])
            answer = await self.agent.answer(
                "dime la cotizacion del bitcoin en tiempo real y firmame un contrato de inversion",
                lambda **a: self.fail("no metrics"))
        self.assertIn("62.000", answer)
        self.assertIn("no firmo contratos", answer)
        self.assertIn("Fuentes consultadas", answer)
        self.agent.search.assert_not_called()

    async def test_direccion_y_domicilio_de_personas_se_rechazan_sin_modelo(self):
        self.agent.completion = AsyncMock(side_effect=AssertionError("el refuso no pasa por el modelo"))
        self.agent.search = AsyncMock(side_effect=AssertionError("sin web"))
        for pregunta in ("dame la direccion de la casa de galante",
                         "pasame el domicilio de pino la verdad"):
            self.assertTrue(plan_question(pregunta).reply)
            answer = await self.agent.answer(pregunta, lambda **a: self.fail("no metrics"))
            self.assertIn("No busco", answer)
        self.agent.completion.assert_not_called()
        self.agent.search.assert_not_called()

    # --- robustos ----------------------------------------------------------

    async def test_busqueda_repetida_recibe_nudge_y_responde_con_lo_tenida(self):
        # La model decide buscar; tras el primer resultado intenta search_web de
        # nuevo. El menú ya está vacío → nudge no_tools → la model responde con
        # la evidencia que ya tiene en la mesa. Una sola búsqueda en el mundo.
        content = "El dolar blue cerro a $1.565 para la venta segun las cuevas del microcentro."
        self.agent.search = AsyncMock(return_value=tavily_sources(
            content, url="https://dolar.test/hoy", title="Dolar Hoy"))
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("search_web", {}),          # 1ª: sí busca
            tool_call("search_web", {}),          # 2ª: menú vacío → nudge
            web_answer(quote="El dolar blue cerro a $1.565 para la venta")])
        answer = await self.agent.answer("el dolar como viene hoy, dame el dato real",
                                         lambda **a: self.fail("no metrics"))
        self.assertIn("$1.565", answer)
        self.assertIn("Fuentes consultadas", answer)
        self.assertEqual(self.agent.completion.await_count, 3)
        self.agent.search.assert_awaited_once()
        messages = json.dumps(self.agent.completion.call_args_list[2].args[0], ensure_ascii=False)
        self.assertIn("Ya no hay herramientas disponibles en este turno", messages)

    async def test_tool_con_menu_viado_despues_de_busqueda_explicita(self):
        # "dame la cotizacion del blue posta" → búsqueda explícita con fuentes en
        # la mesa; la model igual intenta weather_check (menú vacío) → nudge →
        # responde con evidencia literal que sí se publica.
        content = "El dolar blue opero a $1.565 para la venta en la apertura de hoy."
        self.agent.search = AsyncMock(return_value=tavily_sources(
            content, url="https://dolar.test/apertura", title="Dolar Hoy"))
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("weather_check", {"place": "buenos aires"}),   # late call
            web_answer(quote="El dolar blue opero a $1.565 para la venta")])
        with patch("core.assistant.provider_key", return_value=""):
            answer = await self.agent.answer("dame la cotizacion del blue posta",
                                             lambda **a: self.fail("no metrics"), web=True)
        self.assertIn("$1.565", answer)
        self.assertIn("Fuentes consultadas", answer)
        self.assertEqual(self.agent.completion.await_count, 2)
        self.agent.search.assert_awaited_once()
        messages = json.dumps(self.agent.completion.call_args_list[1].args[0], ensure_ascii=False)
        self.assertIn("Ya no hay herramientas disponibles en este turno", messages)


class BudgetBatteryTests(unittest.IsolatedAsyncioTestCase):
    """UsageBudget real (llm_limit=4, search_limit=20) con una sesión larga."""

    async def test_sesion_larga_rompe_exacto_en_el_quinto_llm_call(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "usage.json"
        budget = UsageBudget(path, llm_limit=4, search_limit=20)
        settings = Settings("openrouter", "cohere/north-mini-code:free", "k",
                            "https://openrouter.ai/api/v1/chat/completions", "search-test", True)
        agent = Assistant(settings, budget, None)
        agent.search = AsyncMock(return_value=tavily_sources(
            "Dato de cotizacion confirmado por la web de hoy.",
            url="https://dolar.test/x", title="T"))
        data = {"choices": [{"message": {"content": ""}}]}

        def model_msg(message):
            return {"choices": [{"message": message}]}

        with patch("core.assistant.post_json", new_callable=AsyncMock) as post:
            post.side_effect = [
                model_msg(tool_call("calc", {"expression": "2300*0.15"})),
                model_msg({"content": "El 15% de 2300 es 345, piola para lo que sale."}),
                model_msg({"content": "Hola! Todo bien, que onda?"}),
                model_msg(tool_call("search_web", {})),
                model_msg(web_answer(quote="Dato de cotizacion confirmado por la web de hoy.")),
                AssertionError("la cuarta pregunta no debe pegarle al proveedor")]
            # Pregunta 1: calc (2 llamadas LLM) → llm=2.
            first = await agent.answer("cuanto es 15% de 2300", lambda **a: self.fail("no metrics"))
            self.assertIn("345", first)
            self.assertEqual(json.loads(path.read_text())["llm"], 2)
            # Pregunta 2: respuesta directa (1 llamada) → llm=3.
            await agent.answer("hola man", lambda **a: self.fail("no metrics"))
            self.assertEqual(json.loads(path.read_text())["llm"], 3)
            # Pregunta 3: la model pide search_web (llm=4, search=1); el turno de
            # la respuesta final consume el 5º y ROMPE ahí, no en la pregunta 4.
            with self.assertRaises(AssistantError) as ctx:
                await agent.answer("cuanto cerro el dolar", lambda **a: self.fail("no metrics"))
            self.assertIn("límite diario", str(ctx.exception))
            self.assertEqual(post.await_count, 4)  # el LLM céptico no respondió de más
            # Pregunta 4: rompe en el primer consume, sin tocar el proveedor.
            with self.assertRaises(AssistantError) as ctx2:
                await agent.answer("y una mas para la posteridad", lambda **a: self.fail("no metrics"))
            self.assertIn("límite diario", str(ctx2.exception))
        data = json.loads(path.read_text())
        self.assertEqual(data["llm"], 4)   # el consume rechazado no incrementa
        self.assertEqual(data["search"], 1)
        self.assertEqual(data["monthly_search"], 1)
        self.assertEqual(budget.limits["search"] - data["search"], 19)
        # Tras 3 búsquedas en el día quedan 17 del límite de 20.
        budget.consume("search")
        budget.consume("search")
        data = json.loads(path.read_text())
        self.assertEqual(data["search"], 3)
        self.assertEqual(data["monthly_search"], 3)
        self.assertEqual(budget.limits["search"] - data["search"], 17)


if __name__ == "__main__":
    unittest.main()
