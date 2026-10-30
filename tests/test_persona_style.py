"""Tests de estilo del SYSTEM de Botón + fixture del Top de jerga.

Los tests de estilo asercan PROPIEDADES de la voz, no texto exacto: van a seguir
corriendo cuando el dueño aplique el patch de voz (docs/JERGA.md) sobre
core/assistant.py, y si el patch patea una propiedad, el test lo canta.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.assistant import SYSTEM

import scripts.jerga_top as jerga_top


class PersonaStyleTests(unittest.TestCase):
    """Propiedades de la voz de Botón (aguantan patchs de redacción)."""

    def test_mentions_banter_or_play(self):
        # Habla de joda/bardeo/juego: el server se banda entre sí.
        lower = SYSTEM.lower()
        hits = [w for w in ("banter", "jodo", "jodá", "juego", "barde", "corazonada", "humor", "humour")
                if w in lower]
        self.assertTrue(hits, "El SYSTEM debería mencionar banter/juego/bardeo en alguna forma")

    def test_bans_internal_state_talk(self):
        # Prohibición explícita de hablar de estado interno / herramientas.
        self.assertIn("no tengo herramientas", SYSTEM)

    def test_asks_for_corazonada_when_no_data(self):
        self.assertIn("corazonada", SYSTEM.lower())

    def test_no_formal_assistant_words(self):
        # Nada de "asistente virtual" ni de language de callcenter.
        lower = SYSTEM.lower()
        for phrase in ("asistente virtual", "en qué puedo ayudarte", "¿en qué puedo ayudar"):
            self.assertNotIn(phrase, lower)

    def test_rioplatense_voice_markers(self):
        # Voseo presente (sos/respondé) y señales ríoplatenses.
        lower = SYSTEM.lower()
        self.assertTrue(
            ("sos" in lower) or ("respondé" in lower) or ("rioplatense" in lower),
            "El SYSTEM debería tener voz rioplatense (voseo o 'rioplatense')",
        )

    def test_prompt_reasonable_length(self):
        # Hoy el SYSTEM mide ~2228 chars. Empado el test en 2500 para que corra HOY
        # y que un patch de voz exageradamente largo quede detectado igual.
        self.assertLessEqual(len(SYSTEM), 2500)
        self.assertGreaterEqual(len(SYSTEM), 200)


# --- Fixture del Top de jerga (scripts/jerga_top.py) -------------------------


def mini_historial():
    """12+ mensajes de 3 autores con jerga clara y algo de ruido a filtrar."""
    base = [
        ("ana", "boludo la estoy pasando increíble jajajaja"),
        ("ana", "che alguien jugó al partido? CUAK"),
        ("lui", "che boludo, perdimos Zzz"),
        ("lui", "gato el arquero, no ataja ni una piñata jajaja"),
        ("lui", "boludo qué jugada, no la puedo creer Zzz"),
        ("mirta", "che, flashear ese último mensaje? casi muero"),
        ("mirta", "nadie pidió pero llegó la maldición jajajsdfds"),
        ("ana", "@mirta mirá vos https://no-es-jerga.example.com !boton stats"),
        ("mirta", "che piola el asado de hoy, jajaja"),
        ("lui", "basado y con onda, casi como Zzz"),
        ("ana", "trucha el resultado, nadie pidió esto"),
        ("mirta", "gato mirta mirta mirta"),
    ]
    msgs = []
    for i, (author, content) in enumerate(base):
        msgs.append({"ts": f"2026-10-2{i}T12:00:00Z", "author": author,
                     "bot": False, "content": content})
    return msgs


class JergaTopTests(unittest.TestCase):
    def test_analyze_ranks_jerga_and_filters_noise(self):
        result = jerga_top.analyze(mini_historial(), top_n=10)
        terms = [tok for tok, _n, _s in result]
        self.assertIn("boludo", terms)
        self.assertIn("che", terms)
        self.assertIn("jajaja", terms)
        self.assertIn("nadie", terms) and self.assertIn("pidió", terms)
        # ruido: urls, mentions, comandos y nombres de users... nunca en el TOP
        for prohibited in ("https", "example", "com", "mirta", "lui", "ana"):
            self.assertNotIn(prohibited, terms)
        # ordenado desc por usos
        counts = [n for _t, n, _s in result]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_single_author_dominated_tokens_excluded(self):
        # "CHE" solía venir solo de mirta: ainki igual quedó con más autores lean.
        hist = [
            {"ts": "t1", "author": "solitario", "bot": False, "content": "palabrita única jajaja"},
            {"ts": "t2", "author": "solitario", "bot": False, "content": "palabrita única jajaja"},
            {"ts": "t3", "author": "solitario", "bot": False, "content": "palabrita única jajaja"},
            {"ts": "t4", "author": "solitario", "bot": False, "content": "palabrita única jajaja"},
        ]
        terms = [tok for tok, _n, _s in jerga_top.analyze(hist)]
        self.assertNotIn("palabrita", terms)

    def test_sample_truncated_to_120(self):
        result = jerga_top.analyze(mini_historial())
        for _t, _n, sample in result:
            self.assertLessEqual(len(sample), 120)

    def test_main_with_fixture_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "channel_history.json"
            path.write_text(json.dumps(mini_historial()), encoding="utf-8")
            with patch.object(jerga_top, "DEFAULT_PATH", path):
                code = jerga_top.main(["jerga_top.py"])
        self.assertEqual(code, 0)

    def test_main_without_file_is_graceful(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "no_existe.json"
            code = jerga_top.main(["jerga_top.py", str(path)])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
