"""Free no-key agentic tools (arithmetic, wikipedia, weather) plus generative
scaffolds for creative requests. Everything is read-only, bounded and fail-closed:
no secrets, no execution, fixed timeouts and response-size ceilings."""
import ast
import json
import operator
import re
from urllib.parse import quote

from core.assistant_trace import event

# --- Tool schemas (same shape as the ones in assistant.py) -------------------

CALC_TOOL = {"type": "function", "function": {
    "name": "calc", "description": "Cálculo aritmético exacto (suma, resta, multiplicación, división, porcentajes). Usalo en vez de calcular de cabeza.",
    "parameters": {"type": "object", "properties": {
        "expression": {"type": "string", "description": "Expresión con números y + - * / % ( ). Ej: 375*(24000+375*20)", "maxLength": 120}},
        "required": ["expression"], "additionalProperties": False}}}

WIKI_TOOL = {"type": "function", "function": {
    "name": "wiki_summary", "description": "Resumen de Wikipedia (es) para conocimiento estable: quién es o fue alguien, qué es una cosa. No sirve para datos actuales.",
    "parameters": {"type": "object", "properties": {
        "topic": {"type": "string", "description": "Título del artículo o nombre, en limpio", "maxLength": 80}},
        "required": ["topic"], "additionalProperties": False}}}

WEATHER_TOOL = {"type": "function", "function": {
    "name": "weather_check", "description": "Clima actual y próximos 3 días de una ciudad, con datos reales de Open-Meteo.",
    "parameters": {"type": "object", "properties": {
        "place": {"type": "string", "description": "Nombre de ciudad, sin país si es Argentina", "maxLength": 80}},
        "required": ["place"], "additionalProperties": False}}}


# --- Bounded HTTP GET used only against fixed free endpoints -----------------

async def get_json(session, url):
    """GET a known free endpoint; fail-closed to {} on any network or response issue."""
    event('http_start', service='free_api')
    try:
        async with session.get(url, headers={"User-Agent": "Boton/1.0 (server read-only agent)"},
                               timeout=9) as response:
            if response.status != 200:
                event('http_error', service='free_api', status=response.status)
                return {}
            body = await response.read()
            if len(body) > 900_000:
                event('http_error', service='free_api', status='too_large')
                return {}
            return json.loads(body.decode('utf-8', 'replace'))
    except Exception as exc:  # aiohttp errors, json errors, timeouts
        event('http_error', service='free_api', status=type(exc).__name__)
        return {}


def _compact(text, limit=650):
    return re.sub(r'\s+', ' ', str(text)).strip()[:limit]


# --- calc ------------------------------------------------------------------

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
}


def calc_eval(expression):
    """Exact arithmetic with an explicit evaluator: no eval(), no names, no
    attribute access — anything malformed or funny just raises."""
    if not isinstance(expression, str) or len(expression) > 120:
        raise ValueError
    normalized = expression.strip().replace(',', '').replace('^', '**')
    bare = normalized.replace('**', '')
    if not bare or not re.fullmatch(r"[0-9+\-*/%().\s]+", bare):
        raise ValueError
    try:
        tree = ast.parse(normalized, mode='eval')
    except (ValueError, SyntaxError):
        raise ValueError from None

    def walk(node, depth=0):
        depth += 1
        if depth > 25:
            raise OverflowError
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError
            if abs(node.value) > 10**15:
                raise OverflowError
            return node.value
        if isinstance(node, ast.BinOp):
            op = _OPS.get(type(node.op))
            if op is None:
                raise ValueError
            left, right = walk(node.left, depth), walk(node.right, depth)
            if isinstance(node.op, ast.Pow) and (abs(right) > 1000 or len(str(op(left, right))) > 40):
                raise OverflowError
            return op(left, right)
        if isinstance(node, ast.UnaryOp):
            value = walk(node.operand, depth)
            return -value if isinstance(node.op, ast.USub) else value
        raise ValueError

    try:
        result = walk(tree.body)
    except ZeroDivisionError:
        raise ValueError from None
    if isinstance(result, float) and result.is_integer() and abs(result) < 10**12:
        result = int(result)
    if not isinstance(result, (int, float)) or abs(result) > 10**15 or result != result:
        raise ValueError
    return result


# --- wikipedia --------------------------------------------------------------

async def wiki_lookup(session, topic):
    """Deterministic ES-wikipedia search + summary for stable knowledge."""
    cleaned = _compact(topic, 80)
    if not cleaned or not re.match(r'^[\w\s\-.:áéíóúñüÁÉÍÓÚÑÜ]+$', cleaned, re.I):
        raise ValueError
    rows = await get_json(
        session, 'https://es.wikipedia.org/w/rest.php/v1/search/page?q='
        + quote(cleaned) + '&limit=3')
    pages = rows.get('pages') if isinstance(rows, dict) else []
    if not isinstance(pages, list) or not pages:
        return {"topic": cleaned, "status": "not_found"}
    page = pages[0] if isinstance(pages[0], dict) else {}
    title = _compact(page.get('title', cleaned), 80)
    summary = await get_json(
        session, 'https://es.wikipedia.org/api/rest_v1/page/summary/' + quote(title))
    text = ''
    url = ''
    if isinstance(summary, dict):
        text = _compact(summary.get('extract', ''), 650)
        urls = summary.get('content_urls') if isinstance(summary.get('content_urls'), dict) else {}
        if isinstance(urls, dict):
            desktop = urls.get('desktop') if isinstance(urls.get('desktop'), dict) else {}
            url = _compact(desktop.get('page', ''), 200)
    if not text:
        text = _compact(page.get('description', ''), 300)
    if not text:
        return {"topic": title, "status": "not_found"}
    return {"topic": title, "summary": text, "url": url or '(no informada)'}


# --- weather ----------------------------------------------------------------

async def weather_check(session, place):
    """Open-Meteo geocoding + 3-day forecast, two fixed free endpoints."""
    cleaned = _compact(place, 80)
    if not cleaned or not re.match(r'^[\w\s\-.:áéíóúñüÁÉÍÓÚÑÜ,]+$', cleaned, re.I):
        raise ValueError
    geo = await get_json(
        session, 'https://geocoding-api.open-meteo.com/v1/search?name='
        + quote(cleaned) + '&count=1&language=es&format=json')
    found = geo.get('results') if isinstance(geo, dict) else []
    if not isinstance(found, list) or not found:
        return {"status": "not_found", "place": cleaned}
    hit = found[0] if isinstance(found[0], dict) else {}
    lat, lon = hit.get('latitude'), hit.get('longitude')
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return {"status": "not_found", "place": cleaned}
    data = await get_json(
        session, 'https://api.open-meteo.com/v1/forecast?latitude=' + str(lat)
        + '&longitude=' + str(lon)
        + '&current=temperature_2m,apparent_temperature,precipitation,weather_code'
        '&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max'
        '&forecast_days=3&timezone=America%2FArgentina%2FBuenos_Aires')
    if not isinstance(data, dict) or not data.get('daily'):
        return {"status": "not_found", "place": cleaned}
    current = data.get('current') if isinstance(data.get('current'), dict) else {}
    daily = data.get('daily')

    def _cell(index, key):
        row = daily.get(key)
        try:
            return float(row[index])
        except (IndexError, TypeError, ValueError):
            return None

    placename = _compact((str(hit.get('name', cleaned)) + (', ' + str(hit['country']) if hit.get('country') else '')), 90)
    dates = daily.get('time') if isinstance(daily.get('time'), list) else []
    days = [{"fecha": dates[i], "max": _cell(i, 'temperature_2m_max'),
             "min": _cell(i, 'temperature_2m_min'),
             "lluvia_%": _cell(i, 'precipitation_probability_max')}
            for i in range(min(3, len(dates)))]
    return {"status": "ok", "place": placename, "now": {
        "temp": current.get('temperature_2m'),
        "sensacion": current.get('apparent_temperature'),
        "precipitacion_mm": current.get('precipitation')}, "dias": days}


# --- generative scaffolds ----------------------------------------------------

TRAVEL_SCAFFOLD = (
    'Este pedido es creativo y general: respondelo completo de una sola vez, con tu propio '
    'conocimiento, sin herramientas y SIN negarlo ni mencionar capacidades. Estructura obligatoria: '
    '(1) ruta por ciudades o etapas con los días; (2) qué ver y comer en cada etapa; '
    '(3) transporte y presupuesto estimado; (4) tres consejos prácticos. '
    'Formato: títulos cortos con bullets, mensaje de a lo sumo 1200 caracteres.')

RECIPE_SCAFFOLD = (
    'Este pedido es creativo y general: entregá la receta completa de una vez, con tu propio '
    'conocimiento, sin herramientas y SIN negarlo. Estructura obligatoria: ingredientes en lista '
    'con cantidades, pasos numerados breves y un tip final. Máximo 900 caracteres.')

RECS_SCAFFOLD = (
    'Este pedido es de recomendaciones: respuesta de una sola vez con tu propio conocimiento, '
    'sin herramientas y SIN pedir más datos. De 3 a 5 opciones con una línea explicando por qué '
    'cada una. Máximo 800 caracteres.')

SCAFFOLDS = (
    (re.compile(r'\b(?:itinerario|plan de viaje|\d+\s*d[ií]as? (?:en|por) \w+|viaje de \d+ dias?)\b', re.I),
     TRAVEL_SCAFFOLD),
    (re.compile(r'\brecetas?\b|\bc[oó]mo se hace (?:la )?\w+\b', re.I), RECIPE_SCAFFOLD),
    (re.compile(r'\b(?:recomend(?:a|ame|acione s?)|qu[eé] (?:veo|juego|leo|escucho|hago si))\b', re.I),
     RECS_SCAFFOLD),
)


def scaffold_for(question):
    """Creative requests need structure, or a weak model refuses or answers meta."""
    for matcher, text in SCAFFOLDS:
        if matcher.search(question):
            return text
    return None
