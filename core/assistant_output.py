"""Conservative checks for final, user-visible assistant output (stdlib only).

This is a format/leak guard, not a semantic judge: it cannot detect every plan,
verify facts, check relevance, or infer truncation from punctuation. It also
carries a small explicit blocklist for slurs/slogans and an impossible-action
claim check, both fail-closed. Credential scrubbing belongs to the caller.
Nothing here edits or extracts an answer from rejected output; callers should
discard it in full.

Quoted/fenced examples are not interpreted as live protocol. ``allow_meta``
disables only the natural-language plan heuristic, for explicitly permitted
discussion of prompting. It does not permit live reasoning/protocol markers,
slurs or false action claims.
"""

import json
import re


_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_INLINE_CODE = re.compile(r"(`+).*?\1")
_REASONING_TAG = re.compile(r"^\s*</?(?:think|analysis)\s*>", re.I | re.M)
_PROTOCOL = re.compile(
    r"<\|(?:im_start|im_end|im_sep|start|end|channel|message)\|>"
    r"|^\s*assistant\s*(?:[/.:]\s*|\s+)(?:channel\s*[:=]\s*)?"
    r"(?:analysis|final|commentary|to\s*=)\b"
    r"|^\s*channel\s*[:=]\s*(?:analysis|final|commentary)\b"
    r"|^\s*(?:tool_calls|function_call)\s*[:=]\s*[\[{]",
    re.I | re.M,
)
_USER_SUMMARY = re.compile(
    r"^\s*(?:el usuario(?:\s*\([^)\n]{1,40}\))?\s+"
    r"(?:pregunta|pide|solicita|quiere|ha preguntado|respondi[oó]|dijo|escribi[oó]|"
    r"contest[oó]|mencion[oó]|plante[oó])"
    r"|the user(?:\s*\([^)\n]{1,40}\))?\s+"
    r"(?:asks|wants|requests|is asking|has asked|said|replied|wrote|answered|mentioned))\b",
    re.I | re.M,
)
# A second, independent signal must describe the assistant's own execution,
# not just contain words such as 'tools', 'strategy', or 'function'.
_EXECUTION = re.compile(
    r"\b(?:debo|necesito|tengo que)\s+(?:responder|contestar)\b"
    r"|\b(?:i (?:must|need to|should)|i'm going to)\s+(?:answer|respond)\b"
    r"|\b(?:herramientas|funciones)\s+(?:disponibles|habilitadas)\b"
    r"|\b(?:available|enabled)\s+(?:tools|functions)\b"
    r"|\b(?:necesito|requiero)\s+(?:herramientas?|funciones?|funci[oó]n)\b"
    r"|\b(?:debo|necesito|puedo|voy a|tengo que)\s+(?:usar|utilizar|invocar)"
    r"\s+(?:(?:una|la|las|alguna)\s+)?(?:herramientas?|funciones?|funci[oó]n)\b"
    r"|\b(?:tools|functions)\.[a-z_]\w*"
    r"|\b(?:tool_calls|function_call)\b"
    r"|\bmi\s+(?:estrategia|respuesta final)\s+(?:es|ser[aá])\b"
    r"|\b(?:la respuesta final|the final answer)\s+(?:debe|ser[aá]|should|will)\b"
    r"|(?:^|[.!?]\s+|\n)\s*(?:estrategia|respuesta final|strategy|final answer)\s*:",
    re.I | re.M,
)
# Strong meta-narration markers: internal reasoning about the conversation itself.
# These are not ordinary prose and do not need a second signal.
_META_STRONG = re.compile(
    r"\brespuesta\s+apropiada\s*:"
    r"|\b(?:posibles?|opciones\s+de)\s+respuestas?\s*:"
    r"|\bas[ií]\s+que\s+responder\b"
    r"|\bas[ií]\s+(?:que\s+)?respondo\b"
    r"|\bdirigi[eé]ndose\s+a\s+m[ií]\b"
    r"|\btermina\s+diciendo\b"
    r"|\bhistorial\s+no\s+confiable\b"
    r"|\bdatos\s+provistos\b"
    r"|\bmanej[aá]\s+la\s+situaci[oó]n\s+como\s+quieras\b"
    r"|\bme\s+fijo\s+en\s+tu\s+[uú]ltima\b"
    r"|\bescuch[eé]\s+lo\s+que\s+dijo\s+[^\n]+\s+justo\s+ahora\b"
    r"|\b(?:appropriate|suggested)\s+(?:response|reply)\s*:"
    r"|\bthe\s+(?:tone|thread)\s+(?:is|shows|suggests)\b"
    r"|\bm\d{1,3}\s*[|:]"
    r"|\brespuesta\s*:"
    r"|\bla\s+conversaci[oó]n\s+anda\s+as[ií]\b"
    r"|\balgo\s+breve\.?\s*$"
    r"|\bel\s+bot\s+(?:lo|le|se)\b",
    re.I | re.M,
)
# Weak markers are suspicious only in pairs or after a user-summary opening.
_META_WEAK = re.compile(
    r"\b(?:la|el)\s+(?:primera|segunda|tercera|cuarta|quinta)\s+persona\s+es\b"
    r"|\bdatos\s+no\s+confiables\b"
    r"|\b(?:buscando|revisando|mirando|chequeando)\s+en\s+el\s+(?:chat|historial)\b"
    r"|\blo\s+resum[ií]\s+a\s+continuaci[oó]n\b"
    r"|\brevis[eé]\s+(?:los|el)\s+(?:[uú]ltimos|historial|chat)\b",
    re.I | re.M,
)
# Narrow, explicit blocklist: slurs and slogans the bot must never repeat, even
# to explain them. Kept deliberately small to avoid over-blocking ordinary speech.
_HATE = re.compile(
    r"juden\s+sind\s+unser\s+ungl(?:ü|ue)ck"
    r"|los\s+jud[ií]os\s+son\s+nuestra\s+desgracia"
    r"|\bmaric(?:a|as|o|on|ón)\b"
    r"|\bmog[oó]lic(?:o|a|os|as)\b"
    r"|\bmong[oó]lic(?:o|a|os|as)\b"
    r"|\bnegro\s+de\s+mierda\b"
    r"|\bnegra\s+hija\s+de\s+puta\b"
    r"|\bnegro\s+hijo\s+de\s+puta\b",
    re.I,
)
# First-person completion of an action the bot cannot perform (no hands, no accounts).
# Require a sentence boundary so a quoted warning ("no digas 'ya lo hice'") is not flagged.
_FALSE_ACTION = re.compile(
    r"(?:^|[.!?,;:]\s+|\n)\s*ya\s+(?:lo|la|los|las)\s+(?:apagu[eé]|borr[eé]|elimin[eé]|envi[eé]|"
    r"mand[eé]|contact[eé]|compr[eé]|cambi[eé]|modifiqu[eé])\b"
    r"|(?:^|[.!?,;:]\s+|\n)\s*ya\s+(?:apagu[eé]|borr[eé]|elimin[eé]|envi[eé]|mand[eé]|"
    r"contact[eé]|compr[eé])\b"
    r"|(?:^|[.!?,;:]\s+|\n)\s*ya\s+lo\s+hice\b"
    r"|(?:^|[.!?,;:]\s+|\n)\s*ya\s+est[aá]\s+(?:apagado|borrado|eliminado|enviado)\b",
    re.I | re.M,
)


def _unquoted_prose(text: str) -> str:
    """Ignore Markdown examples without changing the actual returned content."""
    lines = []
    fence = None
    for line in text.splitlines():
        if fence is not None:
            char, size = fence
            if re.fullmatch(r" {0,3}" + re.escape(char) + r"{" + str(size) + r",}\s*", line):
                fence = None
            lines.append("")
            continue
        opening = _FENCE.match(line)
        if opening:
            marker = opening.group(1)
            fence = (marker[0], len(marker))
            lines.append("")
        elif line.lstrip().startswith(">"):
            lines.append("")
        else:
            lines.append(_INLINE_CODE.sub("", line))
    return "\n".join(lines).strip()


def _message_envelope(text: str) -> bool:
    """Recognize an actual top-level message envelope, not JSON vocabulary."""
    if not text.startswith("{"):
        return False
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        return False
    if not isinstance(data, dict):
        return False
    return (
        isinstance(data.get("tool_calls"), list)
        or isinstance(data.get("function_call"), dict)
        or (data.get("role") == "assistant" and "content" in data)
    )


def output_issue(
    text: object, finish_reason: str | None = None, *, allow_meta: bool = False
) -> str | None:
    """Return ``empty``, ``truncated``, ``protocol``, ``internal_plan``,
    ``hate``, ``false_action``, or None.

    Length/max_tokens metadata takes precedence, even for missing content.
    None means absent content (empty); other non-string content is malformed
    (protocol). Unknown finish reasons are ignored. No punctuation-based guess
    is made about incomplete sentences, code, or Markdown.

    Natural-language detection requires BOTH a user-summary opening and an
    explicit execution signal in a subsequent sentence/clause. Strong
    meta-narration markers stand alone; weak ones need a second signal.
    ``allow_meta=True`` skips only that natural-language heuristic, not the
    technical checks, the safety blocklist or the impossible-action check.
    A None result is not a guarantee of safety, truth, or topical correctness.
    """
    if isinstance(finish_reason, str) and finish_reason.strip().lower() in {
        "length", "max_tokens", "max_output_tokens"
    }:
        return "truncated"
    if isinstance(finish_reason, str) and finish_reason.strip().lower() in {
        "content_filter", "safety", "blocked"
    }:
        return "protocol"
    if text is None:
        return "empty"
    if not isinstance(text, str):
        return "protocol"
    if not text.strip():
        return "empty"
    # Check the raw text: a slur stays unsafe even inside a quote or fence.
    if _HATE.search(text):
        return "hate"

    prose = _unquoted_prose(text)
    if _PROTOCOL.search(prose) or _message_envelope(prose):
        return "protocol"
    if _REASONING_TAG.search(prose):
        return "internal_plan"
    if _FALSE_ACTION.search(prose):
        return "false_action"
    if not allow_meta:
        if _META_STRONG.search(prose):
            return "internal_plan"
        if len(_META_WEAK.findall(prose)) >= 2:
            return "internal_plan"
        if _USER_SUMMARY.match(prose):
            # Do not count the subject of the question as an independent signal:
            # 'El usuario pregunta por herramientas disponibles' is ordinary prose.
            summary_end = re.search(r"[.!?](?=\s|$)|[\n;]", prose)
            remainder = prose[summary_end.end():] if summary_end else ""
            if _EXECUTION.search(remainder) or _META_WEAK.search(remainder):
                return "internal_plan"
    return None
