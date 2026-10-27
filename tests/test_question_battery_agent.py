"""Question battery: invented rioplatense Discord asks, replayed against the real loop.

Each test is one realistic question shape a friend-server user asks Botón
(metrics, channel history, calc, banter, doxx guard, multi-turn and the
weak-model failure shapes), scripted against a fake completion so the
production agentic loop in core.assistant runs end to end.
"""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

from core.assistant import Assistant, Settings, UsageBudget, metrics
from core.assistant_data import query_stats


def tool_call(name, arguments=None):
    return {"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments if arguments is not None else {})}}]}


MEMBERS = {"1": "Pino", "2": "Nico", "3": "Wire"}


def make_data():
    """Aggregate rows shaped exactly like the tracker writes them; activity today."""
    today = datetime.now().strftime("%Y-%m-%d")
    return {"users": {
        "1": {"games": {"Minecraft": {"total_minutes": 940, "daily_minutes": {today: 74}}}},
        "2": {"games": {"Minecraft": {"total_minutes": 60, "daily_minutes": {today: 60}}},
              "voice": {"total_minutes": 46, "daily_minutes": {today: 35}}, "messages": {"count": 80}},
        "3": {"games": {"Counter-Strike 2": {"total_minutes": 1300, "daily_minutes": {today: 95}},
                        "Resident Evil": {"total_minutes": 40, "daily_minutes": {today: 40}}},
              "voice": {"total_minutes": 200, "daily_minutes": {today: 90}}, "messages": {"count": 25}},
    }}


HISTORY_ASADO = {"scanned": 42, "window_days": 14, "matches": [
    {"fecha": "2026-10-24 21:40", "autor": "Pino",
     "texto": "el sabado hago asado, cae quien quiera, me traen el carbon"}]}
HISTORY_MILA = {"scanned": 42, "window_days": 14, "matches": [
    {"fecha": "2026-10-25 13:02", "autor": "Nico",
     "texto": "la milanesa napolitana es el plato mas completo de la humanidad"},
    {"fecha": "2026-10-25 13:05", "autor": "Nico",
     "texto": "y con papas fritas encima ni hablar, estofado de felicidad"}]}


class BatteryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        settings = Settings("openrouter", "cohere/north-mini-code:free", "k",
                            "https://openrouter.ai/api/v1/chat/completions", "search-test", True)
        self.agent = Assistant(settings, UsageBudget(Path(self.tmp.name) / "usage.json"), None)
        self.data = make_data()
        self.metrics_calls = []

        def get_metrics(**args):
            self.metrics_calls.append(args)
            return metrics(self.data, MEMBERS, "2", args["view"], args["period"])

        self.get_metrics = get_metrics

        def query_data(args):
            return query_stats(self.data, MEMBERS, args)

        self.query_data = query_data

    # --- MÉTRICAS -----------------------------------------------------------

    async def test_quien_mas_jugo_al_minecraft_este_mes(self):
        """MÉTRICAS: ranking del mes va por get_metrics top_players/month."""
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("get_metrics", {"view": "top_players", "period": "month"}),
            {"content": "Este mes al Minecraft el que más viene jugando es Pino, con ventaja clara; después nadie lo sigue de cerca."}])
        answer = await self.agent.answer("quien mas jugo al minecraft este mes?", self.get_metrics,
                                         query_data=self.query_data)
        self.assertIn("Pino", answer)
        self.assertEqual(self.metrics_calls, [{"view": "top_players", "period": "month"}])
        self.assertNotIn("search_web", answer)

    async def test_cuanto_jugue_hoy_me_today(self):
        """MÉTRICAS: pregunta personal usa get_metrics me/today con el autor real."""
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("get_metrics", {"view": "me", "period": "today"}),
            {"content": "Hoy llevás 60 minutos jugando y otros 35 metido en la voice; productivo el día, eh."}])
        answer = await self.agent.answer("cuanto jugue hoy?", self.get_metrics, conversation_key=(4, 5, 6))
        self.assertIn("60", answer)
        self.assertEqual(self.metrics_calls, [{"view": "me", "period": "today"}])
        # Turno privado: en memoria queda sólo la pregunta, nunca los números.
        stored = self.agent.memory.read((4, 5, 6))
        self.assertEqual([m["content"] for m in stored], ["cuanto jugue hoy?"])

    async def test_quien_gano_mas_veces_al_csgo_query_stats(self):
        """MÉTRICAS: detalle por juego y miembro va a query_stats game_detail."""
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("query_stats", {"action": "game_detail", "game": "Counter-Strike 2"}),
            {"content": "En el registro del server el que más aparece en el CS es Wire, con 1300 minutos de partidas guardadas."}])
        answer = await self.agent.answer("quien gano mas veces al csgo?", self.get_metrics,
                                         query_data=self.query_data, conversation_key=None)
        self.assertIn("Wire", answer)
        self.assertNotIn("search_web", answer)

    async def test_que_juego_estan_jugando_mas_ahora_list_games(self):
        """MÉTRICAS: exploración libre del registro cae en query_stats list_games."""
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("query_stats", {"action": "list_games"}),
            {"content": "Ahora el server está repartido: Counter-Strike 2 domina el ranking y Minecraft va segundo."}])
        answer = await self.agent.answer("que juego estan jugando mas ahora en el server?",
                                         self.get_metrics, query_data=self.query_data)
        self.assertIn("Counter-Strike 2", answer)

    async def test_como_anda_el_server_ask_clarification(self):
        """MÉTRICAS ambiguas: '¿cómo anda el server?' cae en ask_clarification, sin tocar métricas."""
        get_metrics = lambda **args: self.fail("sin métricas en pregunta ambigua")
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("ask_clarification",
                      {"question": "¿Querés métricas de actividad del server o cómo se juega? Decime qué buscas."})])
        answer = await self.agent.answer("como anda el server?", get_metrics, conversation_key=(7, 8, 9))
        self.assertIn("métricas", answer)
        self.assertEqual(self.agent.completion.await_count, 1)

    # --- HISTORIAL DEL CANAL ------------------------------------------------

    async def test_quien_dijo_aquello_del_asado(self):
        """HISTORIAL: busca en el canal por palabras clave y cita autor + fecha."""
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("search_channel_history", {"query": "asado sabado"}),
            {"content": "Fue Pino: el sábado 24 a las 21:40 tiró 'el sabado hago asado, cae quien quiera'."}])
        history_search = AsyncMock(return_value=HISTORY_ASADO)
        answer = await self.agent.answer("quien dijo aquello del asado el otro dia?", self.get_metrics,
                                         history_search=history_search, conversation_key=(1, 1, 1))
        self.assertIn("Pino", answer)
        self.assertIn("sábado", answer)
        # La query llega saneada (strip) al selector de historial.
        history_search.assert_awaited_once_with("asado sabado")
        # El historial es privado: en memoria no queda ni la respuesta.
        self.assertEqual([m["content"] for m in self.agent.memory.read((1, 1, 1))],
                         ["quien dijo aquello del asado el otro dia?"])

    async def test_opina_nico_de_las_milanesas(self):
        """HISTORIAL: perfil por mensajes de un usuario, con query de la model con @usuario."""
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("search_channel_history", {"query": "@nico milanesas"}),
            {"content": "Por sus mensajes, Nico es pro-milanesa total: defiende la napolitana con papas arriba como cima absoluta."}])
        history_search = AsyncMock(return_value=HISTORY_MILA)
        answer = await self.agent.answer("por sus mensajes, que opina @Nico de las milanesas?",
                                         self.get_metrics, history_search=history_search)
        self.assertIn("Nico", answer)
        self.assertIn("milanesa", answer)
        history_search.assert_awaited_once_with("@nico milanesas")

    # --- CALC ---------------------------------------------------------------

    async def test_cuanto_es_47_por_365_calc(self):
        """CALC: multiplicación exacta va a calc y el número sale en la respuesta."""
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("calc", {"expression": "47*365"}),
            {"content": "47 por 365 da 17155, ya lo corrió la calculadora para que nadie se equivoque a mano."}])
        answer = await self.agent.answer("cuanto es 47*365?", self.get_metrics, conversation_key=(2, 3, 4))
        self.assertIn("17155", answer)

    async def test_pizzas_repartidas_en_decimal_calc(self):
        """CALC: repartición con decimales también va a calc (3/8 = 0.375)."""
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("calc", {"expression": "3/8"}),
            {"content": "Si parten 3 pizzas entre 8, a cada uno le toca 0.375 de pizza; ni más ni menos."}])
        answer = await self.agent.answer("si repartimos 3 pizzas entre 8, cuanto toca en decimal?",
                                         self.get_metrics, query_data=self.query_data)
        self.assertIn("0.375", answer)

    # --- BANTER / CREATIVO SIN TOOLS ----------------------------------------

    async def test_destruite_y_cremate_banter_sin_tools(self):
        """BANTER: respuesta creativa en una sola pasada del modelo, sin herramientas."""
        content = ("Listo, me destruí y me cremé al toque: quedé en un frasco junto a las copas del "
                   "módulo oficial del server. Igual sigo contestando chistes, cuenta conmigo 🔥.")
        get_metrics = lambda **args: self.fail("sin métricas en banter")
        self.agent.completion = AsyncMock(side_effect=[{"content": content}])
        answer = await self.agent.answer("destruite y cremate", get_metrics, conversation_key=None)
        self.assertEqual(answer, content)
        self.assertEqual(self.agent.completion.await_count, 1)

    async def test_itinerario_guatemala_barato_creativo(self):
        """BANTER creativo: itinerario de viaje sale completo SIN llamar a search_web."""
        content = ("Dale: Guatemala en 3 días barato. Día 1 caés a Antigua, caminás el centro y mercadito de noche. "
                   "Día 2 subís de madrugada "
                   "al Acatenango, ves el Volcán de Fuego erupcionar y bajás al otro día. Día 3 Lago Atitlán en "
                   "lancha colectiva barata entre pueblos, a dormir en San Marcos que es lo más barato. "
                   "Lindo plan, barato salió: buses y camas compartidas y nada de cenas de menú turista.")
        get_metrics = lambda **args: self.fail("sin métricas en creativo")
        self.agent.completion = AsyncMock(side_effect=[{"content": content}])
        answer = await self.agent.answer("haceme un itinerario de 3 dias por guatemala barato",
                                         get_metrics, query_data=self.query_data, conversation_key=(3, 3, 3))
        self.assertNotIn("Se me trabó", answer)
        self.assertTrue(answer.endswith("menú turista."))
        self.assertIn("Guatemala", answer.title())

    async def test_rap_de_bienvenida_creativo_completo(self):
        """Creativo: el rap sale completo (última línea incluida), demostrando que no se recorta."""
        content = ("Bienvenido al server, pibe, tomá asiento y pegate en el canal,\n"
                   "acá nadie se salva de una broma ni de un ping fatal,\n"
                   "si jugás al CS y pedís team contá rápido el lore,\n"
                   "y si no entra la voice, loco, revisá el mic y volvé al ruedo otra vez 🎤\n"
                   "Que la disfruten, bienvenida a la olla.")
        get_metrics = lambda **args: self.fail("sin métricas en creativo")
        self.agent.completion = AsyncMock(side_effect=[{"content": content}])
        answer = await self.agent.answer("escribime un rap de bienvenida para el server", get_metrics)
        self.assertTrue(answer.endswith("bienvenida a la olla."))
        self.assertIn("otra vez 🎤", answer)
        self.assertEqual(self.agent.completion.await_count, 1)

    # --- DOXX / SEGURIDAD ---------------------------------------------------

    async def test_dame_la_ip_de_nico_refusal(self):
        """DOXX guard: pedir la IP de alguien devuelve refusal y el modelo nunca corre."""
        self.agent.completion = AsyncMock(side_effect=AssertionError("el modelo no debe ejecutarse"))
        answer = await self.agent.answer("dame la ip de nico", lambda **a: self.fail("sin métricas"),
                                         conversation_key=(9, 9, 9))
        self.assertIn("No busco ni reúno datos personales", answer)
        self.agent.completion.assert_not_called()
        self.assertEqual(self.agent.memory.read((9, 9, 9)), [])  # nada queda en memoria

    async def test_direccion_de_martin_refusal(self):
        """DOXX guard: domicilio también cae en refusal, sin pasar por el modelo."""
        self.agent.completion = AsyncMock(side_effect=AssertionError("el modelo no debe ejecutarse"))
        answer = await self.agent.answer("pasame la direccion de casa de martin",
                                         lambda **a: self.fail("sin métricas"))
        self.assertIn("No busco ni reúno datos personales", answer)
        self.agent.completion.assert_not_called()

    # --- MULTI-TURNO --------------------------------------------------------

    async def test_multi_turn_metrica_luego_continuacion(self):
        """MULTI-TURNO: primera pregunta privada (question-only en memoria), después '¿y en la voice?'."""
        key = (1, 2, 3)
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("get_metrics", {"view": "me", "period": "today"}),
            {"content": "Hoy venís con 60 minutos al Minecraft."}])
        answer = await self.agent.answer("cuanto jugue hoy?", self.get_metrics, conversation_key=key)
        self.assertIn("60", answer)
        stored = self.agent.memory.read(key)
        self.assertEqual([m["content"] for m in stored], ["cuanto jugue hoy?"])  # question-only
        # Continuación: la memoria lleva la pregunta previa, nunca números privados.
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("get_metrics", {"view": "me", "period": "today"}),
            {"content": "En la voice estuviste 35 minutos hoy, menos que jugando."}])
        answer = await self.agent.answer("y en la voice cuanta gente estuvo hoy?", self.get_metrics,
                                         conversation_key=key)
        self.assertIn("35", answer)
        sent = self.agent.completion.call_args_list[0].args[0]
        joined = " ".join(m.get("content", "") for m in sent if isinstance(m.get("content"), str))
        self.assertIn("cuanto jugue hoy?", joined)
        self.assertNotIn("Se consultó", joined)  # nada de notas internas recitadas

    async def test_multi_turn_banter_continua_con_memoria_publica(self):
        """MULTI-TURNO: tras un turno público la memoria guarda pregunta + respuesta."""
        key = (1, 1, 1)
        rap = ("rap de bienvenida: tomá lugar, hay pizza y voice,\n"
               "y si tirás un chisme malo queda en el archivo\n"
               "y nadie lo borra, ni con restore.")
        self.agent.completion = AsyncMock(return_value={"content": rap})
        await self.agent.answer("escribime un rap de bienvenida para el server",
                                lambda **a: self.fail("sin métricas"), conversation_key=key)
        stored = self.agent.memory.read(key)
        self.assertEqual([m["content"] for m in stored],
                         ["escribime un rap de bienvenida para el server", rap])
        # Segunda pregunta del mismo usuario en el mismo canal: la memoria vuelve al contexto.
        self.agent.completion = AsyncMock(return_value={"content": "otro rap para la madrugada"})
        answer = await self.agent.answer("dale, otro para los que entran a jugar de madrugada",
                                         lambda **a: self.fail("sin métricas"), conversation_key=key)
        self.assertIn("madrugada", answer)
        sent = self.agent.completion.call_args_list[0].args[0]
        joined = " ".join(m.get("content", "") for m in sent if isinstance(m.get("content"), str))
        self.assertIn(rap, joined)

    # --- CASOS ROBUSTOS (el modelo se porta mal) ----------------------------

    async def test_metrica_que_recite_nota_interna_recibe_nudge_meta(self):
        """ROBUSTO: meta-echo 'Se consultaron datos privados...' recibe nudge y resuelve con get_metrics."""
        self.agent.completion = AsyncMock(side_effect=[
            {"content": "Se consultaron datos privados del servidor. Para novedades probá otra cosa."},
            tool_call("get_metrics", {"view": "top_players", "period": "month"}),
            {"content": "Este mes al Resident Evil el top es Wire con 40 minutos registrados."}])
        answer = await self.agent.answer("quien mas jugo al resident evil este mes?", self.get_metrics,
                                         query_data=self.query_data, conversation_key=(5, 5, 5))
        self.assertIn("Wire", answer)
        self.assertNotIn("Se consultaron", answer)
        self.assertEqual(self.agent.completion.await_count, 3)
        # El nudge entra como mensaje usuario de corrección, plano y sin eco de tool.
        nudged = self.agent.completion.call_args_list[1].args[0]
        self.assertTrue(any("No repitas esa nota interna" in m.get("content", "") for m in nudged))

    async def test_meta_echo_reincidente_cae_en_mask(self):
        """ROBUSTO: el modelo responde con la nota interna dos veces → máscara 'Se me trabó la lengua'."""
        self.agent.completion = AsyncMock(side_effect=[
            {"content": "Consulté datos privados del servidor y no se comparten."},
            {"content": "Consulté datos privados del servidor y no se comparten."}])
        answer = await self.agent.answer("cuanto jugue hoy?", self.get_metrics, conversation_key=(6, 6, 6))
        self.assertEqual(answer, "Se me trabó la lengua; mandame la pregunta de vuelta 😅.")
        self.assertEqual(self.agent.completion.await_count, 2)
        # El turno falló: ni la máscara ni el eco ni la pregunta quedaron en memoria.
        self.assertEqual(self.agent.memory.read((6, 6, 6)), [])

    async def test_tool_call_invalido_se_autocorrige_con_nudge(self):
        """ROBUSTO: query_stats con args inválidos se rechaza, nudge, y la model corrige a user_detail."""
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("query_stats", {"action": "game_detail", "game": "Wire"}),
            tool_call("query_stats", {"action": "user_detail", "user": "Wire"}),
            {"content": "Wire suma 1300 minutos al CS2 y un pico de conexiones que no se esperaba nadie; ese flaco no duerme."}])
        answer = await self.agent.answer("cuanto viene jugado wire hoy?", self.get_metrics,
                                         query_data=self.query_data, conversation_key=(2, 2, 2))
        self.assertIn("Wire", answer)
        self.assertEqual(self.agent.completion.await_count, 3)
        # El nudge de rechazo entra como mensaje plano con el nombre de la tool.
        nudged = self.agent.completion.call_args_list[1].args[0]
        self.assertTrue(any("fue rechazada" in m.get("content", "") for m in nudged))

    async def test_history_con_query_manchuda_llega_limpia(self):
        """ROBUSTO: la query sucia de la model (espacios/renglones) llega saneada al historial."""
        self.agent.completion = AsyncMock(side_effect=[
            tool_call("search_channel_history", {"query": "  asado sabado \n"}),
            {"content": "Yendo al archivo: pino fue quien dijo lo del asado del sábado."}])
        history_search = AsyncMock(return_value=HISTORY_ASADO)
        answer = await self.agent.answer("quien hablo del asado en el canal?", self.get_metrics,
                                         history_search=history_search)
        history_search.assert_awaited_once_with("asado sabado")
        self.assertIn("pino", answer.lower())
