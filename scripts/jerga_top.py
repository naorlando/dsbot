"""Analiza localmente channel_history.json y lista términos candidatos a jerga.

Uso:
    python scripts/jerga_top.py [ruta/al/channel_history.json]

Espera una lista de mensajes: {"ts": "...", "author": "...", "bot": bool, "content": "..."}
La CLI muestra términos y conteos, nunca citas. Aun así su salida es privada:
el filtro no reconoce todos los nombres propios ni es un anonimizador completo.

Si no hay JSON todavía, avisa y termina sin romper: el fixture para probarlo
vive en tests/test_persona_style.py (armamos un mini historial en tempdir).
"""

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "channel_history.json"
SAMPLE_LEN = 120
TOP_N = 40
MIN_TOKEN_LEN = 3
MAX_AUTHOR_DOMINANCE = 0.7  # si un solo author genera >70% de los usos (y >=3 usos), fuera

# Stop-words en español standard (más "/"-casos que salen del tokenizador).
STOPWORDS = {
    "que", "los", "las", "del", "por", "una", "para", "con", "como", "pero", "más", "mas",
    "este", "esta", "esto", "estos", "estas", "ese", "esa", "eso", "aquel", "aquella",
    "todo", "toda", "todos", "todas", "otro", "otra", "otros", "otras", "mismo", "misma",
    "nada", "algo", "cual", "cuales", "quien", "quienes",
    "donde", "cuando", "cuanto", "cuanta", "sobre", "entre", "desde", "hasta", "segun",
    "sin", "ante", "tras", "durante", "mediante", "porque", "porqué", "aunque", "si",
    "sí", "nope", "hay", "está", "estan", "estás", "estoy", "estas", "era", "eras",
    "eres", "soy", "somos", "son", "fue", "fueron", "iba", "van", "voy", "vas", " va ",
    "the", "and", "for", "you", "your", "not", "with", "this", "that", "have", "from",
    "ok", "okay", "aja", "ah", "eh", "uf", "ey", "mmm", "uh",
    # comandos del bot (van aparte, no son vocabulario):
    "boton",
}

# Casos slash / basura de Discord: se borran del contenido antes de tokenizar.
RE_URL_STRIP = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
RE_MENTION_STRIP = re.compile(r"<@\d+>|<@&\d+>|<#\d+>|@\w+")
RE_COMMAND_STRIP = re.compile(r"(?<!\w)[!/]\w+", re.IGNORECASE)
RE_EMOJI_STRIP = re.compile(r":[a-z0-9_]+:|[\U0001F000-\U0001FAFF\u2600-\u27BF]", re.IGNORECASE)

RE_NUMBER = re.compile(r"^\d+([.,]\d+)?$")

# Agrupar risas reconocibles, incluso con una cola rota; no "sos", "ojos" o "hijos".
RE_LAUGH = re.compile(r"^(?:[ajh]*j[aeiou]j[aeiou]|(?:js|sj){2})[a-z]*$", re.IGNORECASE)


def is_laugh(token):
    return bool(RE_LAUGH.fullmatch(token.lower()))


def tokenize(content):
    """Tokens minúsculos, sin mentions/urls/comandos/emojis/números."""
    text = RE_URL_STRIP.sub(" ", content)
    text = RE_MENTION_STRIP.sub(" ", text)
    text = RE_COMMAND_STRIP.sub(" ", text)
    text = RE_EMOJI_STRIP.sub(" ", text)
    raw = re.findall(r"[\w']+", text)
    out = []
    for tok in raw:
        low = tok.lower()
        if len(low) < MIN_TOKEN_LEN:
            continue
        # No incluir blobs alfanuméricos, IDs o posibles claves como candidatos.
        # Esto NO reemplaza una revisión privada antes de compartir resultados.
        if len(low) > 40 or not re.fullmatch(r"[a-záéíóúüñ]+", low):
            continue
        if RE_NUMBER.match(low):
            continue
        if low in STOPWORDS:
            continue
        out.append("jajaja" if is_laugh(tok) else low)
    return out


def analyze(messages, top_n=TOP_N, sample_len=SAMPLE_LEN):
    """Devuelve [(termino, usos, mensaje_ejemplo), ...] ordenado por usos desc."""
    counts = Counter()
    authors = defaultdict(Counter)
    samples = {}
    messages = list(messages or [])
    # Usernames are not a complete roster of names, but must not become "jerga".
    name_tokens = set()
    for msg in messages:
        name_tokens.update(re.findall(r"[\w']+", str(msg.get("author") or "").casefold()))
    for msg in messages or []:
        if msg.get("bot"):
            continue  # los mensajess del bot contaminan el estilo del server
        if re.match(r"^\s*[!/]\w+", str(msg.get("content") or "")):
            continue  # las pruebas y preguntas al bot no son charla espontánea
        author = str(msg.get("author") or "?")
        sample = re.sub(r"\s+", " ", str(msg.get("content") or "")).strip()[:sample_len]
        for tok in tokenize(msg.get("content") or ""):
            if tok.casefold() in name_tokens:
                continue
            counts[tok] += 1
            authors[tok][author] += 1
            samples.setdefault(tok, sample)
    result = []
    for tok, n in counts.most_common():
        per_author = authors[tok]
        if n >= 3 and max(per_author.values()) / n > MAX_AUTHOR_DOMINANCE:
            continue  # dominado por un solo (quizá un user con muletina propia): fuera
        result.append((tok, n, samples.get(tok, "")))
        if len(result) >= top_n:
            break
    return result


def format_top(result, top_n=TOP_N, include_samples=False):
    lines = []
    for rank, (tok, n, sample) in enumerate(result[:top_n], 1):
        line = f"{rank:>3}. {tok} ({n})"
        if include_samples:
            line += f" — {sample or '(sin mensaje)'}"
        lines.append(line)
    return "\n".join(lines)


def main(argv):
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_PATH
    if not path.exists():
        print(f"[jerga_top] No encuentro {path}: todavía no llegó la exportación de #general.")
        print("[jerga_top] Cuando exista, volvé a correr: python scripts/jerga_top.py")
        return 1
    try:
        messages = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"[jerga_top] {path} no se pudo parsear: {exc}")
        return 1
    if not isinstance(messages, list):
        print(f"[jerga_top] {path} no es una lista de mensajes (¿export mal hecho?).")
        return 1
    result = analyze(messages)
    if not result:
        print("[jerga_top] Corrida sin resultados (¿todo era bot o comandos?).")
        return 1
    print(format_top(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
