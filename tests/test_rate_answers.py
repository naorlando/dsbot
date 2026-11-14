"""El curador determinístico detecta fallos concretos, no relevancia."""

import unittest

from scripts.rate_answers import analyse, evaluate, is_bot


def row(id, content, *, bot=False, author="boton", ts="2026-11-08T18:00:00+00:00",
        reply_to=None):
    return {"id": str(id), "ts": ts, "author": author, "bot": bot,
            "content": content, "reply_to": reply_to}


class EvaluateTests(unittest.TestCase):
    def test_echo_of_the_request(self):
        score, flags = evaluate("quien acaba de boostear el server",
                                row(1, "!boton quien acaba de boostear el server"),
                                None, None)
        self.assertIn("eco", flags)
        self.assertLess(score, 3)

    def test_internal_reasoning_dump(self):
        score, flags = evaluate("El usuario pregunta qué es lo más viejo que tengo guardado.",
                                row(1, "!boton que es lo mas viejo"), None, None)
        self.assertIn("meta", flags)
        self.assertLessEqual(score, 2)

    def test_fake_action(self):
        _, flags = evaluate("Listo, ya lo apagué.", row(1, "!boton apagalo"), None, None)
        self.assertIn("accion_falsa", flags)

    def test_handle_leak(self):
        _, flags = evaluate("m83 viene diciendo cualquier cosa", row(1, "!boton que pasa"), None, None)
        self.assertIn("handle", flags)

    def test_clean_answer_has_no_flags(self):
        score, flags = evaluate("Ni idea, pero el sábado jugamos al CSGO.", row(1, "!boton que jugamos"),
                                None, None)
        self.assertEqual(flags, [])
        self.assertEqual(score, 5)

    def test_quoted_bot_text_is_only_checked_when_the_human_quoted_the_bot(self):
        _, flags = evaluate("Nada que ver con eso.", row(1, "!boton y eso?"),
                            "texto previo del bot", None, quoted_is_bot=True)
        self.assertIn("cita_ignorada", flags)
        _, flags = evaluate("Nada que ver con eso.", row(1, "!boton y eso?"),
                            "texto de otra persona", None, quoted_is_bot=False)
        self.assertNotIn("cita_ignorada", flags)


class AnalyseTests(unittest.TestCase):
    def test_automatic_notices_are_excluded_by_default(self):
        rows = [
            row(1, "!boton hola", bot=False, author="Nano"),
            row(2, "Hola Nano, todo bien.", bot=True, reply_to="1"),
            row(3, "🎮 **Nano** está jugando **CSGO**", bot=True),
        ]
        self.assertEqual(len(analyse(rows)), 1)
        self.assertEqual(len(analyse(rows, include_auto=True)), 2)

    def test_request_is_the_closest_human_message(self):
        rows = [
            row(1, "!boton que jugamos hoy", bot=False, author="Nano"),
            row(2, "El usuario pregunta que jugamos hoy.", bot=True, reply_to="1"),
        ]
        result = analyse(rows)[0]
        self.assertIn("meta", result["flags"])
        self.assertEqual(result["request"], "!boton que jugamos hoy")

    def test_is_bot_by_flag_or_name(self):
        self.assertTrue(is_bot(row(1, "x", bot=True), "boton"))
        self.assertTrue(is_bot(row(1, "x", bot=False, author="Botón"), "boton"))
        self.assertFalse(is_bot(row(1, "x", bot=False, author="Nano"), "boton"))


if __name__ == "__main__":
    unittest.main()
