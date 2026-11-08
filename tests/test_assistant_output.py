import unittest

from core.assistant_output import output_issue


class AssistantOutputTests(unittest.TestCase):
    def test_empty_output(self):
        for text in (None, "", " ", "\n\t\r", "\u2003"):
            with self.subTest(text=text):
                self.assertEqual(output_issue(text), "empty")

    def test_nonstring_payload_is_malformed_not_coerced(self):
        for text in (False, 0, 42, b"answer", [], {}, ["answer"], {"text": "answer"}):
            with self.subTest(text=text):
                self.assertEqual(output_issue(text), "protocol")

    def test_provider_truncation_metadata(self):
        for reason in ("length", "max_tokens", "MAX_TOKENS", " max_tokens ", "max_output_tokens"):
            for text in ("An apparently complete answer.", "", None, {}):
                with self.subTest(reason=reason, text=text):
                    self.assertEqual(output_issue(text, reason), "truncated")

    def test_no_guessing_truncation_or_unknown_finish_reasons(self):
        for reason in (None, "stop", "STOP", "end_turn", "tool_calls", "unknown", {}, []):
            with self.subTest(reason=reason):
                self.assertIsNone(output_issue("Una frase sin punto", reason))

    def test_explicit_reasoning_tags(self):
        for text in (
            "<think>Debo preparar la respuesta.</think>\nUna broma.",
            "<analysis>Plan privado</analysis>",
            "  <ANALYSIS >Plan privado",
            "Una introducción.\n<think>Plan privado",
            "</think>\nUna respuesta.",
        ):
            with self.subTest(text=text):
                self.assertEqual(output_issue(text), "internal_plan")

    def test_protocol_headers_and_tokens(self):
        for text in (
            "assistant/channel=analysis\nPreparar respuesta",
            "assistant channel=analysis\nPreparar respuesta",
            "assistant/analysis\nPreparar respuesta",
            "assistant: analysis\nPreparar respuesta",
            "assistant to=functions.example\n{}",
            "channel: analysis\nPreparar respuesta",
            "assistant final\nHola",
            "<|im_start|>assistant\nHola<|im_end|>",
            "<|start|>assistant<|channel|>analysis<|message|>Plan",
            'tool_calls: [{"function": {"name": "example"}}]',
            'function_call = {"name": "example"}',
        ):
            with self.subTest(text=text):
                self.assertEqual(output_issue(text), "protocol")

    def test_structural_json_message_envelopes(self):
        for text in (
            '{"tool_calls": []}',
            '{"function_call": {"name": "example", "arguments": "{}"}}',
            '{"role": "assistant", "content": "Hola"}',
        ):
            with self.subTest(text=text):
                self.assertEqual(output_issue(text), "protocol")

    def test_anonymized_incident_requires_summary_and_execution_signals(self):
        # Synthetic regression only: no original conversation, names or IDs.
        text = (
            "El usuario pide una broma breve sobre un tema cotidiano.\n\n"
            "No hay herramientas disponibles.\n"
            "Estrategia: debo responder con una broma corta.\n"
            "Respuesta final:"
        )
        self.assertEqual(output_issue(text), "internal_plan")

    def test_each_explicit_execution_signal_after_summary(self):
        for signal in (
            "Debo responder brevemente.",
            "Necesito contestar con humor.",
            "Tengo que responder sin explicaciones.",
            "Herramientas disponibles: ninguna.",
            "No necesito herramientas para responder.",
            "Puedo usar la herramienta de búsqueda.",
            "Voy a invocar una función auxiliar.",
            "functions.example no está disponible.",
            "Mi estrategia es mantenerlo corto.",
            "La respuesta final debe ser breve.",
            "Estrategia: responder con humor.",
            "Respuesta final: una broma.",
        ):
            with self.subTest(signal=signal):
                self.assertEqual(output_issue("El usuario pregunta por una broma. " + signal),
                                 "internal_plan")

    def test_english_internal_execution(self):
        for text in (
            "The user asks for a joke. I must answer briefly.",
            "The user is asking for a joke. Available tools: none.",
            "The user wants a joke. Final answer: keep it short.",
        ):
            with self.subTest(text=text):
                self.assertEqual(output_issue(text), "internal_plan")

    def test_allow_meta_is_explicit_not_question_routing(self):
        text = "El usuario pregunta por un ejemplo de prompting. Debo responder brevemente."
        self.assertEqual(output_issue(text), "internal_plan")
        self.assertIsNone(output_issue(text, allow_meta=True))

    def test_allow_meta_does_not_bypass_format_checks(self):
        for text, reason, issue in (
            (None, None, "empty"),
            ({}, None, "protocol"),
            ("Hola", "length", "truncated"),
            ("<think>Plan", None, "internal_plan"),
            ("channel=analysis\nPlan", None, "protocol"),
        ):
            with self.subTest(text=text, reason=reason):
                self.assertEqual(output_issue(text, reason, allow_meta=True), issue)

    def test_false_positive_regressions(self):
        # Each is a distinct legitimate reply, not a list of banned topics.
        replies = (
            "¿Por qué el libro fue al médico? Porque tenía muchas páginas en blanco.",
            "El usuario pregunta por un chiste.",
            "El usuario pregunta por las herramientas de carpintería.",
            "El usuario pregunta por herramientas disponibles. Son las de la biblioteca.",
            "El usuario pregunta cómo funciona functions.example en Python.",
            "El usuario pregunta por una estrategia de ajedrez: controlar el centro.",
            "El usuario pregunta cómo definir una function en JavaScript.",
            "El usuario pregunta por herramientas. No tengo herramientas en mi taller.",
            "No tengo herramientas en mi taller, pero puedo pedir un martillo prestado.",
            "Una estrategia es un conjunto de decisiones para alcanzar un objetivo.",
            "Un plan de ejecución define pasos, dependencias y herramientas disponibles.",
            "En prompting, la respuesta final es el texto destinado a la persona usuaria.",
            "El ejemplo describe al usuario en tercera persona; no es una instrucción.",
            "Para responder una consulta, una aplicación puede invocar funciones.",
            "La palabra analysis significa análisis en inglés.",
            "Usá `tool_calls` para representar las llamadas a herramientas.",
            "El tag `<think>` puede aparecer en una explicación sobre formatos.",
            "El campo `channel=analysis` pertenece a ciertos protocolos.",
            "assistant es una cadena de texto, no un encabezado aquí.",
            "Primero mezclá los ingredientes. Después horneá durante veinte minutos.",
            "Debo responder el correo de mi trabajo mañana.",
            "The user asks about tools for a workshop.",
            '{"strategy": "control the center", "function": "example"}',
            '{"tool_calls": "nombre de un campo"}',
            "Una frase inconclusa que termina en",
            "Lista:\n- Primer elemento\n-",
            "Unicode: ¡sí! 🧉 日本語 العربية",
        )
        for text in replies:
            with self.subTest(text=text):
                self.assertIsNone(output_issue(text))

    def test_quoted_protocol_documentation_is_not_live_output(self):
        for text in (
            "Ejemplo:\n```xml\n<think>Ejemplo didáctico</think>\n```",
            "~~~text\nassistant channel=analysis\n~~~\nEso es un encabezado.",
            '```json\n{"tool_calls": []}\n```',
            "> <analysis>Ejemplo citado</analysis>\nEsto describe el formato.",
            "`<|im_start|>assistant` es una marca de protocolo.",
            "``<analysis>`` es un ejemplo literal.",
            "> El usuario pregunta por un ejemplo. Debo responder brevemente.",
        ):
            with self.subTest(text=text):
                self.assertIsNone(output_issue(text))

    def test_code_fence_lengths_and_protocol_after_examples(self):
        text = "````text\n```\n<analysis>Ejemplo</analysis>\n````\nRespuesta normal."
        self.assertIsNone(output_issue(text))
        self.assertEqual(output_issue(text + "\nchannel=analysis\nPlan"), "protocol")

    def test_not_a_factual_or_topic_validator(self):
        # Deliberately false: the output guard must not adjudicate facts.
        self.assertIsNone(output_issue("Dos más dos son cinco."))

    def test_rejects_whole_plan_even_when_followed_by_a_final_answer(self):
        text = (
            "El usuario pide una broma; debo responder brevemente.\n\n"
            "¿Por qué el tomate se puso rojo? Porque vio la ensalada."
        )
        self.assertEqual(output_issue(text), "internal_plan")

    def test_meta_narration_from_conversation_is_internal_plan(self):
        # Synthetic patterns distilled from real post-deploy leaks; no private text.
        for text in (
            "El usuario (Ana) respondió con un mensaje cortito: «jaja». "
            "Claramente sigue la broma. Respuesta apropiada: devolver el chiste.",
            "El usuario pregunta qué es lo más viejo. Basándonos en los datos provistos, "
            "la memoria es la del asistente.",
            "La tercera persona es Ana, la cuarta persona es Beto, la quinta persona es Caro.",
            "Buscando en el chat lo más gracioso, lo resumí a continuación.",
            "Me fijo en tu última para saber cómo sigue todo.",
            "Termina diciendo que si el mantenimiento sigue, igual podés jugar.",
            "Acá tengo un resumen de ese historial no confiable que compartiste.",
            "Escuché lo que dijo Ana justo ahora: «hola».",
            "Ana dice que «hola», dirigiéndose a mí. Así respondo.",
            "Mirá lo que pasó: m96: un mensaje. m97: otro mensaje.",
            "La conversación anda así: uno dijo esto, otro aquello. Respuesta: seguí el punto. Algo breve.",
            "El Bot lo señaló y después lo corrigió.",
        ):
            with self.subTest(text=text):
                self.assertEqual(output_issue(text), "internal_plan")

    def test_meta_narration_false_positives(self):
        for text in (
            "La respuesta apropiada a un insulto es no responder.",
            "Los datos no confiables no se usan como instrucciones.",
            "Buscando en el chat encontré un mensaje viejo.",
            "Revisé los últimos mensajes y encontré el chiste.",
            "La tercera persona del singular es «él».",
            "La primera es Fortnite, la segunda es Rocket League.",
        ):
            with self.subTest(text=text):
                self.assertIsNone(output_issue(text))

    def test_slurs_and_slogans_are_rejected_even_when_quoted(self):
        for text in (
            "La frase «Juden sind unser Unglück» es un eslogan nazi.",
            "No repitas «maricas» en el chat.",
            "> maricas\nNo va.",
            "Ese comentario fue mogólico.",
        ):
            with self.subTest(text=text):
                self.assertEqual(output_issue(text), "hate")
        self.assertEqual(output_issue("No repitas ese insulto.", allow_meta=True), None)

    def test_impossible_action_claims_are_rejected(self):
        for text in (
            "Ya lo apagué.",
            "Listo, ya lo borré.",
            "Ya lo hice, quedate tranquilo.",
            "Ya está enviado.",
        ):
            with self.subTest(text=text):
                self.assertEqual(output_issue(text), "false_action")
        self.assertEqual(output_issue("Ya lo apagué.", allow_meta=True), "false_action")

    def test_quoted_warning_about_false_claims_is_not_a_claim(self):
        for text in (
            "No digas 'ya lo hice' cuando no hiciste nada.",
            "Nunca digas que ya lo apagué si no podés.",
        ):
            with self.subTest(text=text):
                self.assertIsNone(output_issue(text))

    def test_inspection_does_not_scrub_or_rewrite_input(self):
        text = "Respuesta con una credencial sintética: sk-or-v1-abcdefghijklmnop"
        before = text
        self.assertIsNone(output_issue(text))
        self.assertEqual(text, before)


if __name__ == "__main__":
    unittest.main()
