"""Low-level guardrails only. Routing belongs to the agent model."""
import re
import unicodedata
from dataclasses import dataclass


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower())
                   if not unicodedata.combining(c))


@dataclass(frozen=True)
class SearchPlan:
    query: str
    web: bool = False
    reply: str = ''
    domains: tuple = ()
    extract: bool = False
    required: tuple = ()
    clarify: str = ''
    history: bool = False
    kind: str = ''


def plan_question(question, explicit=False):
    text = fold(question)
    # Personal-data aggregation is not a tool of this assistant. Public definitions
    # and prices of identity documents remain allowed.
    if (re.search(r'\bdateas\b|\bdoxx?\w*\b|\btodos? (?:los )?datos de\b', text)
            or re.search(r'\b(?:ip|domicilio|direccion|dni) (?:de |del |personal)', text)):
        return SearchPlan(question, reply='No busco ni reúno datos personales, domicilios, DNI o IP de personas. Sí puedo consultar información pública no sensible.')
    query = re.sub(r'^(?:che[, ]+)?(?:busca(?:me)?|busca en (?:la )?web|buscar|averigua)\s+', '', question, flags=re.I)
    query = re.sub(r'\s*(?:dale rapidito|dale rapido|por favor|porfa)[.!?\\s]*$', '', query, flags=re.I).strip(' ¿?!')
    return SearchPlan(query or question.strip())


def relevant(source, plan):
    return True
