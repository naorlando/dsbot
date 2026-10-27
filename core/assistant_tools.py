"""Bounded no-key tools for the agent (arithmetic, weather) plus the Google
grounding search call. Everything is read-only and fail-closed: no secrets,
no execution, fixed timeouts and response-size ceilings."""
import ast
import asyncio
import json
import operator
import re
import datetime
from urllib.parse import quote, urlparse

from core.assistant_trace import event

# --- Tool schemas (same shape as the ones in assistant.py) -------------------

CALC_TOOL = {"type": "function", "function": {
    "name": "calc", "description": "Cálculo aritmético exacto (suma, resta, multiplicación, división, porcentajes). Usalo en vez de calcular de cabeza.",
    "parameters": {"type": "object", "properties": {
        "expression": {"type": "string", "description": "Expresión con números y + - * / % ( ). Ej: 375*(24000+375*20)", "maxLength": 120}},
        "required": ["expression"], "additionalProperties": False}}}

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


class GroundError(Exception):
    """Google grounding call failed; caller falls back to Tavily."""


async def google_ground(session, key, question, model):
    """Native Gemini call with the google_search server tool. Returns
    (grounded_text, sources) — the text is the grounded answer; sources carry
    the real URLs Google used (uri + title + cited segments as content).
    One retry with backoff on 429/503: the free tier shares one RPM bucket
    between grounding and the LLM chain, so bursts overflow constantly."""
    prompt = ('Buscá en la web y respondé breve en español rioplatense, con datos concretos, '
              'fechas y cifras. Pregunta: ' + str(question).strip()[:300])
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {"maxOutputTokens": 900}}
    url = ('https://generativelanguage.googleapis.com/v1beta/models/'
           + quote(model or 'gemini-3.5-flash-lite') + ':generateContent')
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    data = None
    for attempt in (1, 2):
        event('http_start', service='ground')
        try:
            async with session.post(url, headers=headers, json=body, timeout=28) as response:
                if response.status in (429, 503) and attempt == 1:
                    event('http_error', service='ground', status=response.status, retry=True)
                    await asyncio.sleep(2.5)
                    continue
                if response.status != 200:
                    event('http_error', service='ground', status=response.status)
                    raise GroundError(f"google ground http {response.status}")
                raw = await response.read()
                if len(raw) > 900_000:
                    event('http_error', service='ground', status='too_large')
                    raise GroundError("google ground too large")
                data = json.loads(raw.decode('utf-8', 'replace'))
            break
        except GroundError:
            raise
        except Exception as exc:  # aiohttp errors, timeouts, json errors
            event('http_error', service='ground', status=type(exc).__name__)
            raise GroundError("google ground unavailable") from exc
    candidates = data.get('candidates') if isinstance(data, dict) else []
    candidate = candidates[0] if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict) else {}
    content = candidate.get('content') if isinstance(candidate.get('content'), dict) else {}
    parts_list = content.get('parts') if isinstance(content.get('parts'), list) else []
    text = ''.join(str(part.get('text', '')) for part in parts_list
                   if isinstance(part, dict) and isinstance(part.get('text'), str))[:1900].strip()
    if not text:
        event('ground', status='no_text')
        raise GroundError("google ground empty")
    meta = candidate.get('groundingMetadata') if isinstance(candidate.get('groundingMetadata'), dict) else {}
    chunks = [c.get('web', {}) for c in (meta.get('groundingChunks') or []) if isinstance(c, dict) and isinstance(c.get('web'), dict)]
    citations = {}
    for support in (meta.get('groundingSupports') or []):
        if not isinstance(support, dict):
            continue
        segment = support.get('segment') if isinstance(support.get('segment'), dict) else {}
        snippet = _compact(str(segment.get('text', '')), 400)
        for index in support.get('groundingChunkIndices') or []:
            if isinstance(index, int) and snippet:
                citations.setdefault(index, []).append(snippet)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sources = []
    for index, webdoc in enumerate(chunks):
        uri = str(webdoc.get('uri', ''))[:300]
        parsed = urlparse(uri)
        if (parsed.scheme not in {'https', 'http'} or not parsed.netloc
                or parsed.username or any(ch.isspace() or ch in '<>' for ch in uri)):
            continue
        host = parsed.hostname or ''
        if any(host == bad or host.endswith('.' + bad) for bad in
               ('facebook.com', 'tiktok.com', 'instagram.com', 'pinterest.com')):
            continue
        sources.append({"title": _compact(webdoc.get('title', ''), 120), "url": uri,
                        "content": '\n'.join(citations.get(index, []))[:1500],
                        "published_date": "no informada", "retrieved_at": now})
        if len(sources) >= 5:
            break
    event('ground', status='ok', sources=len(sources), chars=len(text))
    return text, sources


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
