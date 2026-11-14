r"""Curador offline: califica las respuestas de Botón sin LLM ni red.

Lee un export de `scripts/export_channel.py` y aplica chequeos determinísticos
a cada mensaje del bot: eco de la pregunta, persona rota, acción falsa, handles
internos, respuesta vacía, respuesta larga, cita ignorada y día de la semana
contradictorio. No juzga si la respuesta es *buena*: detecta fallos concretos y
deja el resto como "sin marcar", que es lo honesto.

Uso:
    .venv\Scripts\python.exe scripts\rate_answers.py channel_history.json
    ... --json report.json --bot boton --examples 5

Salida: resumen por flag, peores respuestas y distribución de score 0-5.
Nunca imprime secretos: el export ya viene sanitizado por el bot.
"""

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

WEEKDAYS = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')
MONTHS = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
          'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
STOP = frozenset('''para como cuando donde porque sobre entre desde hasta tambien
también ahora ahora mismo algo algun alguna algunos alguien nada nunca siempre
pero sino aunque entonces ademas además cada cosa cosas hacer haces hizo tengo
tenes tenés tiene tienen estas estás estoy estas esto esta ésta este eso esa ese
muy mas más menos vos vosotros nosotros ustedes ellos ellas nos les por que qué
quien quién cual cuál cuales cuáles todo toda todos todas otro otra otros otras
bien mal re che dale bueno buena jaja jajaja jsjs jsjsj igual medio re
'''.split())

_URL = re.compile(r'(?:https?://|www\.)\S+', re.I)
_MENTION = re.compile(r'<[@#!&:][^>]*>|@\d+')
_EMOJI = re.compile(r'[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]')
_HANDLE = re.compile(r'(?<![\w/])(?:m|msg)[-_]?\d{1,6}(?!\d)', re.I)
_PERSONA = re.compile(
    r'\b(?:como (?:un )?(?:modelo|asistente|ia|inteligencia artificial)|'
    r'no (?:tengo|puedo tener) acceso|no puedo acceder|soy un asistente|'
    r'no estoy programad[oa]|mis (?:limitaciones|capacidades))\b', re.I)
# Volcado de razonamiento: el modelo narra el pedido en vez de responderlo.
_META = re.compile(
    r'\b(?:el usuario (?:pregunta|pide|quiere|dice)|el asistente|'
    r'datos provistos|respuesta apropiada|debo responder|según los datos|'
    r'basándonos en los datos|no hay contexto claro)\b', re.I)
_ACTION = re.compile(
    r'\b(?:ya (?:lo|la|los|las) (?:hice|borré|borre|envié|envie|apagué|apague|cambié|cambie)|'
    r'listo,? (?:ya )?(?:lo|la) (?:hice|borré|borre|envié|envie)|'
    r'lo (?:borré|borre|envié|envie|apagué|apague) por vos)\b', re.I)
_THIRD = re.compile(r'\b(?:el bot|botón|boton|el asistente) (?:dijo|respondió|respondio|piensa|opina)\b', re.I)
_HOY = re.compile(r'\bhoy\s*(?:es|,)?\s*(?:el\s+)?(lunes|martes|miércoles|jueves|viernes|sábado|domingo)\b', re.I)
_DATE = re.compile(r'\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b')


def fold(text):
    value = unicodedata.normalize('NFD', str(text or ''))
    return ''.join(char for char in value if unicodedata.category(char) != 'Mn').lower()


def tokens(text):
    clean = _MENTION.sub(' ', _URL.sub(' ', fold(text)))
    clean = _EMOJI.sub(' ', clean)
    return {word for word in re.findall(r'[a-z0-9]{4,}', clean) if word not in STOP}


def parse_ts(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def art(moment):
    return moment.astimezone(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)


def is_bot(row, bot_name):
    if row.get('bot') is True:
        return True
    author = str(row.get('author') or '')
    return fold(author) == fold(bot_name)


def invocation_of(row):
    content = str(row.get('content') or '').strip()
    match = re.match(r'^!bot[oó]n\b\s*(.*)$', content, re.I | re.S)
    return match.group(1).strip() if match else content


def evaluate(answer, request, quoted, moment, quoted_is_bot=False):
    """Devuelve (score 0-5, lista de flags)."""
    flags = []
    text = str(answer or '').strip()
    req = tokens(invocation_of(request)) if request else set()
    ans = tokens(text)
    if not text or len(_EMOJI.sub('', text).strip()) < 8:
        flags.append('vacio')
    if _HANDLE.search(text):
        flags.append('handle')
    if _PERSONA.search(text):
        flags.append('persona')
    if _META.search(text):
        flags.append('meta')
    if _ACTION.search(text):
        flags.append('accion_falsa')
    if _THIRD.search(text):
        flags.append('tercera_persona')
    if len(text) > 700:
        flags.append('demasiado_largo')
    if req and len(req) >= 2 and len(req & ans) / len(req) >= 0.8:
        flags.append('eco')
        if text.endswith('?'):
            flags.append('eco_pregunta')
    # Sólo importa cuando el humano citó al bot: ahí "ignorar la cita" es el
    # fallo real (no reconoce su propio texto).
    if quoted and quoted_is_bot:
        quote_tokens = tokens(quoted)
        if quote_tokens and not (quote_tokens & ans):
            flags.append('cita_ignorada')
    if moment is not None:
        weekday = art(moment).weekday()
        stated = _HOY.search(text)
        if stated and fold(WEEKDAYS[weekday]) != fold(stated.group(1)):
            flags.append('dia_mal')
        for day, month, _year in _DATE.findall(text):
            try:
                if not (1 <= int(day) <= 31 and 1 <= int(month) <= 12):
                    flags.append('fecha_mal')
            except ValueError:
                flags.append('fecha_mal')
    score = 5
    for flag, penalty in (('eco', 3), ('eco_pregunta', 2), ('persona', 3),
                          ('meta', 3), ('accion_falsa', 3), ('tercera_persona', 2),
                          ('dia_mal', 2), ('fecha_mal', 2), ('vacio', 2), ('handle', 2),
                          ('demasiado_largo', 1), ('cita_ignorada', 1)):
        if flag in flags:
            score -= penalty
    return max(0, score), flags


def analyse(rows, bot_name='boton', include_auto=False):
    ordered = sorted(rows, key=lambda row: str(row.get('ts') or ''))
    index = {str(row.get('id')): row for row in ordered}
    results = []
    for position, row in enumerate(ordered):
        if not is_bot(row, bot_name):
            continue
        # Avisos de juego y posts automáticos no son respuestas: no se califican
        # salvo que se pidan explícitamente.
        if not include_auto and not row.get('reply_to'):
            continue
        previous = [item for item in ordered[max(0, position - 6):position] if not is_bot(item, bot_name)]
        request = next((item for item in reversed(previous)
                        if str(item.get('content') or '').lstrip().lower().startswith(('!bot', '!botó'))),
                       previous[-1] if previous else None)
        # El humano citó al bot cuando el mensaje que el bot responde es, a su
        # vez, una respuesta al bot. Ahí "ignorar la cita" es el fallo real.
        parent_id = request.get('reply_to') if request else None
        quoted_row = index.get(str(parent_id)) if parent_id else None
        quoted = quoted_row.get('content') if quoted_row else None
        quoted_is_bot = bool(quoted_row and is_bot(quoted_row, bot_name))
        score, flags = evaluate(row.get('content'), request, quoted, parse_ts(row.get('ts')), quoted_is_bot)
        results.append({'id': row.get('id'), 'ts': row.get('ts'), 'score': score, 'flags': flags,
                        'content': str(row.get('content') or '')[:400],
                        'request': str(request.get('content') or '')[:200] if request else None})
    return results


def report(results, examples=3):
    total = len(results)
    if not total:
        return 'No hay respuestas del bot en el export.'
    counts = Counter(flag for row in results for flag in row['flags'])
    scores = sorted(row['score'] for row in results)
    average = sum(scores) / total
    median = scores[total // 2] if total % 2 else (scores[total // 2 - 1] + scores[total // 2]) / 2
    lines = [f'Respuestas analizadas: {total}',
             'Score determinístico (detecta fallos concretos, NO mide relevancia):',
             f'  promedio: {average:.2f}/5   mediana: {median:.1f}',
             'Distribución: ' + '  '.join(f'{value}→{scores.count(value)}' for value in range(6))]
    if counts:
        lines.append('')
        lines.append('Fallos detectados (una respuesta puede tener varios):')
        for flag, count in counts.most_common():
            lines.append(f'  {flag:18} {count:4}  ({count / total:.0%})')
            for row in [item for item in results if flag in item['flags']][:examples]:
                lines.append(f'      [{row["ts"]}] {row["content"][:160]!r}')
    worst = [row for row in results if row['score'] <= 2][:max(examples, 5)]
    if worst:
        lines.append('')
        lines.append('Peores respuestas:')
        for row in worst:
            lines.append(f'  {row["score"]}/5 [{row["ts"]}] flags={",".join(row["flags"]) or "-"}')
            lines.append(f'      pedido:  {(row["request"] or "-")[:140]!r}')
            lines.append(f'      respuesta: {row["content"][:180]!r}')
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Califica respuestas de Botón sin LLM.')
    parser.add_argument('export', nargs='?', default='channel_history.json')
    parser.add_argument('--bot', default='boton')
    parser.add_argument('--json', dest='json_path')
    parser.add_argument('--examples', type=int, default=3)
    parser.add_argument('--all', dest='include_auto', action='store_true',
                        help='incluye avisos automáticos (no conversacionales)')
    args = parser.parse_args(argv)
    try:
        with open(args.export, encoding='utf-8') as handle:
            rows = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f'No pude leer {args.export}: {type(exc).__name__}', file=sys.stderr)
        return 1
    if not isinstance(rows, list):
        print('El export no es una lista de mensajes.', file=sys.stderr)
        return 1
    results = analyse(rows, args.bot, args.include_auto)
    print(report(results, max(1, args.examples)))
    if args.json_path:
        with open(args.json_path, 'w', encoding='utf-8') as handle:
            json.dump(results, handle, ensure_ascii=False, indent=1)
        print(f'\nDetalle: {args.json_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
