"""Opt-in real API smoke test: synthetic metrics only, no production Discord/data.

Run from repo root: python -m scripts.test_assistant_live [help|metrics|web|clarify|memory]
Credentials are read only from process environment. Never printed or saved.
Each run consumes up to 3 free LLM requests and at most one Tavily basic credit.
"""

import argparse
import asyncio
import json
import logging
import tempfile
from pathlib import Path

import aiohttp

from core.assistant import Assistant, AssistantError, Settings, UsageBudget


class Probe(Assistant):
    def __init__(self, *args):
        super().__init__(*args)
        self.tools_used = []

    async def completion(self, messages, tools, **kwargs):
        message = await super().completion(messages, tools, **kwargs)
        self.tools_used.extend(call["function"]["name"] for call in message.get("tool_calls", []))
        return message


async def main(scenario):
    settings = Settings.from_env()
    questions = {
        "help": "Consultá tu ayuda y decime qué comando muestra el ranking de tiempo en voz esta semana.",
        "metrics": "Consultá mis métricas de hoy y decime cuántos minutos jugué. No inventes cifras.",
        "web": "¿Qué es la plataforma Railway para desplegar aplicaciones? Buscá fuentes web.",
        "clarify": "¿Cómo salió el partido? No te dije equipos, torneo ni fecha: usá tu herramienta para preguntarme qué partido.",
        "memory": "Sin usar herramientas, recordá esta palabra de prueba para mi próximo mensaje: farol.",
    }
    expected = {"help": "get_bot_help", "metrics": "get_metrics", "web": "search_web", "clarify": "ask_clarification"}
    def synthetic_metrics(view, period):
        return {"period": period, "user": {"name": "Usuario de prueba", "game_minutes": 12},
                "note": "Datos ficticios de prueba; no corresponden a ningún miembro de Discord."}
    with tempfile.TemporaryDirectory(prefix="dsbot-live-") as temp:
        async with aiohttp.ClientSession() as session:
            agent = Probe(settings, UsageBudget(Path(temp) / "usage.json", llm_limit=3, search_limit=1), session)
            try:
                key = (1, 2, 3)  # Synthetic identifiers; never sent to a provider.
                answer = await asyncio.wait_for(agent.answer(questions[scenario], synthetic_metrics, conversation_key=key), timeout=60)
                if scenario == "memory":
                    answer = await asyncio.wait_for(agent.answer("¿Qué palabra te pedí recordar?", synthetic_metrics,
                                                                conversation_key=key), timeout=60)
            except AssistantError as error:
                print(json.dumps({"scenario": scenario, "passed": False, "tools": agent.tools_used,
                                  "error": str(error)}, ensure_ascii=False))
                return 1
            success = ("farol" in answer.lower()) if scenario == "memory" else expected[scenario] in agent.tools_used
            if scenario == "help":
                success = success and "!topvoice" in answer and "week" in answer
            elif scenario == "metrics":
                success = success and "12" in answer
            elif scenario == "web":
                success = success and "Fuentes consultadas:" in answer
            print(json.dumps({"scenario": scenario, "passed": success, "tools": agent.tools_used,
                              "answer": answer}, ensure_ascii=False))
            return 0 if success else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=["help", "metrics", "web", "clarify", "memory"])
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(main(args.scenario)))
    except AssistantError as error:
        print(json.dumps({"passed": False, "error": str(error)}, ensure_ascii=False))
        raise SystemExit(1) from None
    except (asyncio.TimeoutError, aiohttp.ClientError):
        print('{"passed": false, "error": "timeout or connection failure"}')
        raise SystemExit(1) from None
