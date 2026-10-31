"""Ambient commentator: LLM-written one-liners for automatic notifications.

Same privacy and budget rules as the interactive assistant: facts are
real aggregates passed by the caller, the model only writes the wording.
Every call site must keep its existing template as fallback, so a
provider outage or exhausted budget can never silence a notification.
"""

import json
import logging
import re

from datetime import datetime

from core.assistant import (AssistantError, SECRET_PATTERN, chain_post,
                            entry_from_settings)
from core.assistant_trace import event

logger = logging.getLogger("dsbot")

KINDS = {
    "connection_milestone": "Sepas cuánto se reenganchó a Discord hoy; burlate amistosamente de la cantidad de reconexiones.",
    "party_formed": "Party armada; comentá la hora, el día y el juego con ironía (temprano entre semana, noche de los días, domingo).",
    "daily_digest": "Resumen del día del servidor: un dato destacado y una lectura libre de la situación, siempre con humor amistoso.",
}

COMPOSER_PROMPT = """Sos Botón, un participante más de un servidor de amigos en Discord. Redactás avisos de
servicio cortos en español rioplatense con humor amistoso según datos REALES que te pasamos. Reglas duras:
- De 1 a 2 frases, máximo 300 caracteres, sin saludos ni despedidas.
- Son mensajes automáticos del bot, no una intervención en la charla: no respondas a
  nadie ni opines del hilo; sólo informá el hecho con humor.
- Chicanada amistosa hacia quien nombran los datos; nunca insultos sobre sexualidad,
  salud, discapacidad, etnia, género, religión, laburo real de la persona, dinero
  personal, política ni familia.
- Usá SOLAMENTE los datos dados; no inventes usuarios, juegos, cifras ni hechos.
- No uses URLs, menciones, @everyone, @here, comandos, ni más de un emoji.
- Devolvé sólo el texto del mensaje, sin comillas, formato ni explicaciones."""


def sanitize(text):
    """Same output hygiene as the assistant: no secrets, links or pings."""
    if not isinstance(text, str):
        return None
    text = SECRET_PATTERN.sub("[clave omitida]", text)
    text = re.sub(r"https?://\S+", "[enlace omitido]", text)
    text = re.sub(r"@everyone|@here", "[mención]", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).replace("`", "").strip()
    return text[:400] or None


TEMPLATE_DIGEST = "📋 Resumen de {dia}: {juegos_min} de juegos ({juegos}) y {voz_min} de voz."

def template_digest(facts):
    """Deterministic fallback when the composer is unavailable. Never invents data."""
    try:
        games = facts.get("juegos_del_dia") if isinstance(facts, dict) else None
        if isinstance(games, list) and games and all(isinstance(item, dict) for item in games):
            games = ", ".join(str(item.get("game", "?")) for item in games[:3])
        if not isinstance(games, str):
            games = ""
        return TEMPLATE_DIGEST.format(
            dia=facts.get("dia", "hoy"), juegos_min=facts.get("minutos_totales_juegos", "?"),
            juegos=games or "sin partidas", voz_min=facts.get("minutos_totales_voz", "?"))[:300]
    except (AttributeError, KeyError, TypeError, ValueError):
        return "Resumen del día: los datos no pudieron leerse."


class Commentator:
    def __init__(self, session, budget, settings):
        self.session, self.budget, self.settings = session, budget, settings

    def _entries(self):
        return self.settings.chain or (entry_from_settings(self.settings),)

    def _facts(self, kind, facts, now):
        now = now or datetime.now()
        hour = now.strftime("%H:%M")
        weekday = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")[now.weekday()]
        return (f"Tipo de mensaje: {kind}. {KINDS[kind]}\n"
                f"Hora local: {hour} ({weekday}).\n"
                f"Datos reales: {json.dumps(facts, ensure_ascii=False)}")

    async def compose(self, kind, facts, now=None):
        if kind not in KINDS or not isinstance(facts, dict):
            logger.warning("Ambient: tipo de mensaje o datos inválidos (%s)", type(kind).__name__)
            return None
        try:
            self.budget.consume("ambient")
        except AssistantError:
            event('ambient', kind=kind, status='budget')
            return None
        now = now or datetime.now()
        payload_for = lambda entry: {  # noqa: E731 - one line per entry, same shape as the assistant
            "model": entry.model, "messages": [
                {"role": "system", "content": COMPOSER_PROMPT},
                {"role": "user", "content": self._facts(kind, facts, now)}],
            "max_tokens": 220, "stream": False, "temperature": 1.1,
            **({"reasoning": {"enabled": False}, "provider": {"require_parameters": True}}
               if entry.provider == "openrouter" else {"enable_thinking": False} if entry.provider == "qwen"
               else {"thinking": {"type": "disabled"}} if entry.provider == "deepseek" else {})}
        try:
            data = await chain_post(self.session, self._entries(), payload_for)
        except AssistantError as exc:
            event('ambient', kind=kind, status='provider_error', error_type=type(exc).__name__)
            logger.warning("Ambient: proveedor no disponible (%s); uso plantilla", type(exc).__name__)
            return None
        try:
            message = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            message = None
        text = sanitize(message)
        event('ambient', kind=kind, status='composed' if text else 'empty')
        return text


async def maybe_compose(bot, kind, facts):
    """Never raises and never breaks a notification; None means use the template."""
    commentator = getattr(bot, "commentator", None)
    if commentator is None:
        return None
    try:
        return await commentator.compose(kind, facts)
    except Exception as exc:  # noqa: BLE001 - notifications must not depend on the composer
        logger.warning("Ambient: composición falló (%s); uso plantilla", type(exc).__name__)
        return None
