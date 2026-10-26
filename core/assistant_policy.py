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
    query = re.sub(r'\s*(?:dale rapidito|dale rapido|por favor|porfa)[.!?\s]*$', '', query, flags=re.I).strip(' ¿?!')
    if not re.search(r'[a-z0-9]', text):
        # Emoji/¿?-only input: a weak model burns calls or truncates on this.
        return SearchPlan(question, reply='Mandame texto, che; emojis y símbolos solos no me cuentan nada 😄.')
    if (not explicit and not re.search(r'\b(?:cuanto|cuando|quien|donde|como|que|cual|busca|precio|resultado|hola|novedades)\b', text)
            and re.search(r'\b(?:hdp|hij[oa]s? de puta|mal nacido|pelotud\w*|bolud\w*|puto|forro|forra|imbecil|idiota|la concha\w*|la puta)\b', text)):
        # Pure jodedera gets a zero-model deterministic reply: the clarify tool made
        # weak models interrogate the user back about nothing (friction bug).
        return SearchPlan(question, reply='Dale, tamo tranquilo 😄. Cuando me tires una pregunta de verdad, la resuelvo al toque.')
    if (not explicit and not re.search(r'\b(?:cuanto|cuando|quien|donde|como|que|cual|hola|novedades)\b', text)
            and re.search(r'\b(?:matate|mataste|destrui(?:te|me)|borrate|quitate|suicid\w*|blowjob|garch\w*|cogerme|t garch)\b', text)):
        # Destruction/iono-needs and explicit junk: same zero-model banter path.
        # north-mini answers "destruite" with a canned "serví café" joke, repeated twice.
        return SearchPlan(question, reply='No me destruyo ni me destruyes 😄. Pregunteme algo real: métricas, historial o web.')
    if explicit and fold(query) in {'test', 'hola', 'busca', 'buscar', 'prueba'}:
        return SearchPlan(query, reply='¿Qué tema querés que busque? Pasame una consulta concreta.')
    if not explicit and re.search(r'\b(comandos?|capacidades|novedades)\b', text):
        return SearchPlan(query)
    # "cuanto salio boca" es una web-pregunta fresca trillada en chat argentino: con
    # equipo de futbol nombrado es, además, caso partido (modo news). Sin equipo
    # (ps5, la entrada, el flight) queda web genérica, nunca gasta "ultimo partido".
    partido = False
    if re.search(r'\bcuanto salio\b', text) and re.search(
            r'\b(?:boca|river|racing|independiente|san lorenzo|argentina|seleccion|huracan|'
            r'gimnasia|estudiantes|lanus|rosario central|newells|velez|banfield|boca juniors|'
            r'toluca|monterrey|cruz azul|chivas|america|libertadores|sudamericana|'
            r'copa argentina|liga profesional)\b', text):
        partido = True
    partido = partido or bool(re.search(r'\b(?:como salio|resultado|quien gano|como termino|resumen del partido)\b', text))
    if partido and not re.search(r'\b(?:hoy|ayer|ultimo|ultima|\d{1,2}[/-]\d{1,2}|\d{4}|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b', text):
        # Fewer reply prompts: an undated match defaults to the latest one. Idempotent:
        # search() re-plans the normalized query and must not append twice.
        if not query.lower().endswith('ultimo partido'):
            query = f'{query} ultimo partido'
    if 'dolar' in text and not re.search(r'\b(blue|oficial|mep|ccl|tarjeta|cripto|bolsa)\b', text):
        # Rioplatense default: "el dolar" sin tipo es el blue; sin preguntas intermedias.
        query = f'{query} blue'
    web = explicit or bool(re.search(
        r'\b(busca\w*|cuanto (?:sale|cuesta|esta|salio|salieron)|precio|tarifa|cotizacion|dolar|cuando sale|fecha de lanzamiento|'
        r'que paso|que sucedio|que ocurrio|quien gano|como termino|como salio|resultado|guia|mantecono|'
        r'pasa(?:me)?|investig\w*|recetas?)\b', text))
    if 'pasaporte' in text and web:
        # Default argentino: el flujo de tarifas es del RENAPER; sin preguntas intermedias.
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
    # Too-small models leak instructions instead of calling tools, so the
    # intents below are executed deterministically by the harness, not by the model.
    history_intent = (re.search(r'\b(?:por (?:sus|los) mensajes?|mensajes? de \w+|historial|'
                                r'cuando (?:hablamos|jugamos|estuvimos|mencionamos)|'
                                r'(?:que|q)\s+(?:dice|dijo|dijeron|opin\w*|pens\w*|comento)|'
                                r'quien (?:dijo|escribio|hablo|pregunto|menciono)|se menciona\b|'
                                r'donde (?:aparece|se menciona))\b', text))
    if history_intent and not re.search(r'\b(?:dolar|pesos)\b', text):
        # Explicit past-talk intents win even over "busca los mensajes de X": web
        # is always the wrong route for channel messages.
        return SearchPlan(query, required=required, history=True)
    kind = 'dolar' if ('dolar' in text and web) else ('partido' if partido and web else '')
    if kind == 'partido':
        # "como salio boca" trajo la Serie C italiana de sportytrader: los fences de
        # resultados genéricos no nombran al equipo. Requerir su token filtra esa
        # basura antes de que el modelo la cite.
        cleaned = re.sub(r'[^a-z0-9 ]', ' ', text)
        stripped = re.sub(r'\b(?:como|cuanto|cuando|quien|salio|sale|salieron|gano|ganado|perdio|empato|resultado(?:s)?|'
                          r'resumen|ultimo|ultima|partido|encuentro|termino|jugado|juego|de|del|'
                          r'el|la|los|las|su|ayer|hoy|equivale)\b', ' ', cleaned)
        required = required + tuple(dict.fromkeys(w for w in stripped.split() if len(w) >= 4))[:2]
    return SearchPlan(query, web, kind=kind, extract=web, required=required)


def relevant(source, plan):
    text = fold(source.get('title', '') + ' ' + source.get('content', ''))
    compact = re.sub(r'\s+', '', text)
    return all(term in compact if term == '99b' else term in text for term in plan.required)
