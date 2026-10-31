"""Conservative checks for final, user-visible assistant output (stdlib only).

This is a format/leak guard, not a semantic judge: it cannot detect every plan,
verify facts, check relevance, or infer truncation from punctuation. Credential
scrubbing belongs to the caller. Nothing here edits or extracts an answer from
rejected output; callers should discard it in full.

Quoted/fenced examples are not interpreted as live protocol. ``allow_meta``
disables only the natural-language plan heuristic, for explicitly permitted
discussion of prompting. It does not permit live reasoning/protocol markers.
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
    r"^(?:el usuario\s+(?:pregunta|pide|solicita|quiere|ha preguntado)"
    r"|the user\s+(?:asks|wants|requests|is asking|has asked))\b",
    re.I,
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
    """Return ``empty``, ``truncated``, ``protocol``, ``internal_plan``, or None.

    Length/max_tokens metadata takes precedence, even for missing content.
    None means absent content (empty); other non-string content is malformed
    (protocol). Unknown finish reasons are ignored. No punctuation-based guess
    is made about incomplete sentences, code, or Markdown.

    Natural-language detection requires BOTH a user-summary opening and an
    explicit execution signal in a subsequent sentence/clause. An isolated
    'El usuario pregunta' is allowed.
    ``allow_meta=True`` skips that heuristic, not technical format checks.
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

    prose = _unquoted_prose(text)
    if _PROTOCOL.search(prose) or _message_envelope(prose):
        return "protocol"
    if _REASONING_TAG.search(prose):
        return "internal_plan"
    if not allow_meta and _USER_SUMMARY.match(prose):
        # Do not count the subject of the question as an independent signal:
        # 'El usuario pregunta por herramientas disponibles' is ordinary prose.
        summary_end = re.search(r"[.!?](?=\s|$)|[\n;]", prose)
        if summary_end and _EXECUTION.search(prose[summary_end.end():]):
            return "internal_plan"
    return None
