"""Keep documented numeric contracts tied to implementation, not paragraph wording.

ASISTENTE_LIGHT documents all budgets/tools; MEMORIA_CANAL documents the subset
relevant to dialogue, history and input/model limits. Scope numeric matches to
their property: unrelated three-second timeouts/three-source caps are valid.
These are documentation/protocol checks, not validation of real model conduct.
"""

import ast
import inspect
import re
import textwrap
import unicodedata
import unittest
from pathlib import Path

import core.assistant as assistant_module
from core.assistant import Assistant, MAX_QUESTION_CHARS, Settings, UsageBudget, bot_help
from core.assistant_history import MAX_AGE_DAYS, MAX_MESSAGES
from core.channel_dialogue import ChannelDialogue


DOCS = Path(__file__).resolve().parents[1] / "docs"


def normalize(text):
    text = "".join(char for char in unicodedata.normalize("NFKD", text.lower())
                   if not unicodedata.combining(char))
    return " ".join(text.replace("*", "").replace("`", "").split())


def blocks(text, *markers):
    paragraphs = re.split(r"\n\s*\n|\n(?=\d+\.\s)", text)
    return "\n".join(normalize(part) for part in paragraphs
                     if any(marker in normalize(part) for marker in markers))


def values(text, pattern):
    return {int(match) for match in re.findall(pattern, normalize(text))}


def loop_limits():
    """Read actual guards/constants, not duplicated public capability claims."""
    def number(node):
        value = node.value if isinstance(node, ast.Constant) else (
            getattr(assistant_module, node.id, None) if isinstance(node, ast.Name) else None)
        if type(value) is not int:
            raise AssertionError("Loop guard no longer uses an integer constant")
        return value

    tree = ast.parse(textwrap.dedent(inspect.getsource(Assistant._answer)))
    model = [number(node.comparators[0]) for node in ast.walk(tree)
             if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
             and node.left.id == "model_requests" and isinstance(node.ops[0], ast.GtE)]
    turns = [number(node.iter.args[0]) for node in ast.walk(tree)
             if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == "turn"
             and isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name)
             and node.iter.func.id == "range" and len(node.iter.args) == 1]
    tools = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.BoolOp):
            continue
        names = {part.id for part in ast.walk(node.test) if isinstance(part, ast.Name)}
        if not {"final_only", "searched", "turn"} <= names:
            continue
        tools.extend(number(part.comparators[0]) for part in ast.walk(node.test)
                     if isinstance(part, ast.Compare) and isinstance(part.left, ast.Name)
                     and part.left.id == "turn" and isinstance(part.ops[0], ast.Lt))
    if len(model) != 1 or len(turns) != 1 or len(tools) != 1:
        raise AssertionError("Assistant loop guards changed; update the contract extractor")
    return model[0], turns[0], tools[0]


MODEL_PATTERN = r"\b(?:maximo|hasta)\s+(\d+)\s+(?:llamadas|pasos)\s+(?:de|del)\s+modelo\b"
QUESTION_PATTERN = r"\bpreguntas?\s*(?:\|\s*|(?:(?:de\s+)?hasta|a)\s+)(\d+)\s+caracteres\b"


class AssistantContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.light = (DOCS / "ASISTENTE_LIGHT.md").read_text(encoding="utf-8")
        cls.memory = (DOCS / "MEMORIA_CANAL.md").read_text(encoding="utf-8")

    def test_implementation_and_public_capabilities_agree(self):
        model, turns, tools = loop_limits()
        self.assertEqual((model, turns, tools), (6, 6, 4))
        self.assertEqual(MAX_QUESTION_CHARS, 4000)
        self.assertEqual((MAX_MESSAGES, MAX_AGE_DAYS), (1000, 30))
        dialogue = ChannelDialogue(10, 20, 99)
        self.assertEqual(dialogue.max_messages, 100)
        defaults = inspect.signature(UsageBudget).parameters
        self.assertEqual(defaults["llm_limit"].default, 400)
        self.assertEqual(defaults["ambient_limit"].default, 240)
        settings = Settings("openrouter", "synthetic:free", "synthetic", "https://example.invalid", "", False)
        capabilities = bot_help(settings, "capabilities")
        self.assertEqual(capabilities["model_calls_per_question"], model)
        self.assertEqual(capabilities["max_tools_per_question"], tools)
        self.assertEqual(capabilities["llm_calls_per_day"], defaults["llm_limit"].default)
        self.assertEqual(capabilities["ambient_calls_per_day"], defaults["ambient_limit"].default)
        self.assertEqual(capabilities["dialogue"]["messages"], dialogue.max_messages)

    def test_both_documents_state_current_model_and_input_caps(self):
        model, _, _ = loop_limits()
        for name, text in (("ASISTENTE_LIGHT.md", self.light), ("MEMORIA_CANAL.md", self.memory)):
            with self.subTest(document=name):
                self.assertEqual(values(text, MODEL_PATTERN), {model}, "Missing or stale model limit")
                self.assertEqual(values(text, QUESTION_PATTERN), {MAX_QUESTION_CHARS}, "Missing or stale input limit")

    def test_shared_dialogue_is_not_confused_with_historical_search(self):
        expected = ChannelDialogue(10, 20, 99).max_messages
        for name, text in (("ASISTENTE_LIGHT.md", self.light), ("MEMORIA_CANAL.md", self.memory)):
            with self.subTest(document=name):
                dialogue = blocks(text, "memoria conversacional:", "dialogo compartido")
                self.assertEqual(values(dialogue, r"\bhasta\s+(\d+)\s+mensajes\b"), {expected})
                history = blocks(text, "search_channel_history", "busqueda historica:")
                windows = re.findall(r"\b(\d+)\s+mensajes.{0,100}?\b(\d+)\s+dias\b", normalize(history))
                self.assertEqual({(int(count), int(days)) for count, days in windows},
                                 {(MAX_MESSAGES, MAX_AGE_DAYS)})

    def test_light_document_states_actual_tool_and_daily_budgets(self):
        _, _, tools = loop_limits()
        self.assertEqual(values(self.light, r"\b(\d+)\s+herramientas\s+(?:en total|por pregunta)\b"), {tools})
        defaults = inspect.signature(UsageBudget).parameters
        interactive = values(self.light, r"\b(?:limita|limite|presupuesto)\b[^.]{0,100}?\b(\d+)\s+"
                             r"llamadas\s*/\s*dia[^.]{0,80}?interactiv")
        interactive |= values(self.light, r"\bpresupuesto interactivo\s*\|\s*(\d+)\s+llamadas\s*/\s*dia\b")
        self.assertEqual(interactive, {defaults["llm_limit"].default})
        ambient = blocks(self.light, "ai_ambient_limit", "assistant_ambient.json")
        ambient_limits = values(ambient, r"\b(?:default|defecto)\s+(\d+)\s*/\s*dia\b")
        ambient_limits |= values(ambient, r"\bavisos automaticos\s*\|\s*(\d+)\s*/\s*dia\b")
        self.assertEqual(ambient_limits, {defaults["ambient_limit"].default})

    def test_numeric_matching_rejects_stale_property_not_unrelated_threes(self):
        text = "Hasta 3 llamadas de modelo; timeout de 3 segundos y hasta 3 fuentes."
        self.assertEqual(values(text, MODEL_PATTERN), {3})
        self.assertNotEqual(values(text, MODEL_PATTERN), {loop_limits()[0]})
        self.assertEqual(values("Máximo 6 llamadas de modelo, 3 segundos y 3 fuentes.", MODEL_PATTERN), {6})
