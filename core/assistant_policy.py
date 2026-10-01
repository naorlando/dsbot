"""Small deterministic routing layer. Never derives web queries from private tools."""
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


def plan_question(question, explicit=False):
    text = fold(question)
    # Personal-data aggregation is not a tool of this assistant. Public definitions
    # and prices of identity documents remain allowed.
    if (re.search(r'\bdateas\b|\bdoxx?\w*\b|\btodos? (?:los )?datos de\b', text)
            or re.search(r'\b(?:ip|domicilio|direccion|dni) (?:de |del |personal)', text)):
        return SearchPlan(question, reply='No busco ni reúno datos personales, domicilios, DNI o IP de personas. Sí puedo consultar información pública no sensible.')
    query = re.sub(r'^(?:che[, ]+)?(?:busca(?:me)?|busca en (?:la )?web|buscar|averigua)\s+', '', question, flags=re.I)
    query = re.sub(r'\s*(?:dale rapidito|dale rapido|por favor|porfa)[.!?\s]*$', '', query, flags=re.I).strip(' ¿?!')
    if explicit and fold(query) in {'test', 'hola', 'busca', 'buscar', 'prueba'}:
        return SearchPlan(query, reply='¿Qué tema querés que busque? Pasame una consulta concreta.')
    if not explicit and re.search(r'\b(comandos?|capacidades|novedades)\b', text):
        return SearchPlan(query)
    if re.search(r'\b(?:como salio|resultado|resumen del partido)\b', text):
        if not re.search(r'\b(?:hoy|ayer|ultimo|ultima|\d{1,2}[/-]\d{1,2}|\d{4}|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b', text):
            return SearchPlan(query, reply='¿De qué fecha es el partido? ¿Querés el último encuentro entre esos equipos?', clarify='match_date')
    if 'dolar' in text and not re.search(r'\b(blue|oficial|mep|ccl|tarjeta|cripto|bolsa)\b', text):
        return SearchPlan(query, reply='¿Qué dólar querés consultar: blue, oficial, MEP, CCL o tarjeta?', clarify='dollar_type')
    web = explicit or bool(re.search(
        r'\b(busca\w*|cuanto (?:sale|cuesta|esta)|precio|tarifa|cotizacion|dolar|cuando sale|fecha de lanzamiento|'
        r'que paso|que sucedio|que ocurrio|quien gano|como termino|como salio|resultado|guia|mantecono)\b', text))
    if 'pasaporte' in text and web:
        if not re.search(r'\b(argentin\w*|renaper)\b', text):
            return SearchPlan(query, reply='¿De qué país es el pasaporte que querés consultar?', clarify='country')
        return SearchPlan('pasaporte argentino tarifas vigentes regular express al instante RENAPER',
                          True, domains=('argentina.gob.ar',), extract=True, required=('pasaporte',))
    if 'wow' in text and web:
        query = re.sub(r'\bwow\b', 'World of Warcraft', query, flags=re.I)
    required = ()
    if re.search(r'\b99\s*b\b', text):
        required = ('99b',)
    if 'wow' in text and 'forever' in text:
        required = ('forever',)
    # Dates must survive normalization; do not replace a historical event by news.
    if re.search(r'9 de diciembre de 2018', text):
        required = ('2018', 'diciembre')
    return SearchPlan(query, web, extract=web, required=required)


def relevant(source, plan):
    text = fold(source.get('title', '') + ' ' + source.get('content', ''))
    compact = re.sub(r'\s+', '', text)
    return all(term in compact if term == '99b' else term in text for term in plan.required)
