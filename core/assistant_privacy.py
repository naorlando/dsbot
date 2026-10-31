"""Bounded, local, best-effort privacy checks (no network/classifier).

Recognises credentials, email, formatted/labelled phones, explicit DNI numbers
and explicitly personal home addresses. It deliberately does not classify all
numbers, prices, street names, unlabeled identifiers, obfuscations or personal
traits. Callers must still forbid profiling and enforce opt-in/access controls.
Oversized input is rejected wholesale, never truncated before inspection.
"""

import re
import unicodedata

from core.assistant_secrets import SECRET_PATTERN

MAX_PRIVATE_CHARS = 32768
_OVERSIZED = '[contenido omitido por límite de privacidad]'
_CREDENTIAL = re.compile(
    r"-----BEGIN [^-\r\n]*PRIVATE KEY-----[\s\S]*?(?:-----END [^-\r\n]*PRIVATE KEY-----|$)"
    r"|\b(?:mfa\.[A-Za-z0-9_-]{12,}|[A-Za-z0-9_-]{20,32}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{20,})"
    r"|\b(?:sk-[A-Za-z0-9_-]{8,}|tvly-(?:dev|prod)-[A-Za-z0-9_-]{8,}|gsk_[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|github_pat_[A-Za-z0-9_]{12,}|AKIA[A-Z0-9]{16})"
    r"|\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"
    r"|\b(?:[a-z][a-z0-9]{0,32}[_-]){0,8}(?:(?:api|access|private|secret)[ _-]?key|token|secret|password|passwd|contrase[nñ]a|clave|authorization)[\"']?\s*[:=]\s*(?:(?:Bearer|Basic)\s+)?(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;]+)",
    re.I,
)
# Unfamiliar token-like strings need both letters and digits. Pure numeric
# identifiers/prices and long ordinary words are not generic credentials.
_TOKEN = re.compile(r'(?<![\w])[A-Za-z0-9_+/=-]{24,}(?:\.[A-Za-z0-9_+/=-]+)*(?![\w])')
_EMAIL = re.compile(r'(?<![\w.+-])[\w.!#$%&\x27*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+', re.I)
_DNI = re.compile(
    r'\bD\.?\s*N\.?\s*I\.?(?:\s+(?:n(?:ro|umero|úmero)?\.?|es|number))?'
    r'\s*[:#=°º-]?\s*\d(?:[ .-]?\d){6,8}[A-Za-z]?(?!\w)', re.I)
_PHONE = re.compile(
    r'\b(?:tel[eé]fono|tel\.?|celular|cel\.?|m[oó]vil|whatsapp|phone|mobile)'
    r'\s*(?:(?:es|is|number|nro\.?)\s*)?[:=]?\s*\+?\d[\d ().-]{5,32}\d'
    r'|(?<!\w)\+\d[\d ().-]{6,30}\d'
    r'|(?<![\w\d])(?:\(\d{2,4}\)[ .-]*\d{3,4}[ .-]\d{4}'
    r'|\d{2,4}[ .-]\d{3,4}[ .-]\d{4})(?![\w\d])', re.I)
_HOME = re.compile(
    r'\b(?:\b(?:mi|su|tu)\s+direcci[oó]n(?:\s+(?:personal|particular|de\s+casa))?'
    r'|domicilio(?:\s+(?:personal|particular))?'
    r'|direcci[oó]n\s+(?:personal|particular|de\s+(?:mi\s+)?casa)'
    r'|direcci[oó]n(?=\s*[:=])'
    r'|(?:my\s+)?home\s+address|I\s+live\s+at|vivo\s+en'
    r'|vive\s+en|mi\s+casa\s+(?:est[aá]|queda)\s+en)'
    r'\s*(?:(?:es|is|est[aá]|queda)\s*(?:en\s*)?|[:=])?\s*'
    r'(?=[^\r\n;!?]{0,160}\d)[^\r\n;!?]{1,240}', re.I)


def _text(value):
    if not isinstance(value, str):
        return ''
    # Strip invisible formatting before matching, not after it, so a zero-width
    # character cannot trivially split a labelled credential/email.
    return ''.join(c for c in unicodedata.normalize('NFKC', value)
                   if not unicodedata.category(c).startswith('C') or c.isspace())


def _token_private(match):
    value = match.group()
    return any(c.isalpha() for c in value) and any(c.isdigit() for c in value)


def _phone_private(match):
    return 7 <= sum(c.isdigit() for c in match.group()) <= 15


def has_private_data(text):
    """Reject recognised private data or input beyond the inspection bound.

    False is NOT a guarantee of anonymity/safety; no inferred traits are checked.
    Non-text values return False (callers validate their own shapes).
    """
    if not isinstance(text, str):
        return False
    if len(text) > MAX_PRIVATE_CHARS:
        return True
    text = _text(text)
    if len(text) > MAX_PRIVATE_CHARS:
        return True
    return (any(pattern.search(text) for pattern in
                (SECRET_PATTERN, _CREDENTIAL, _EMAIL, _DNI, _HOME))
            or any(_token_private(m) for m in _TOKEN.finditer(text))
            or any(_phone_private(m) for m in _PHONE.finditer(text)))


def scrub_private(text):
    """Return bounded redacted text for dialogue/current context, not storage.

    Inspect before any caller truncation. Oversized strings are omitted entirely
    rather than exposing a prefix or an uninspected tail. Idempotent placeholders.
    """
    if not isinstance(text, str):
        return ''
    if len(text) > MAX_PRIVATE_CHARS:
        return _OVERSIZED
    text = _text(text)
    if len(text) > MAX_PRIVATE_CHARS:
        return _OVERSIZED
    for pattern, replacement in ((SECRET_PATTERN, '[secreto omitido]'),
                                 (_CREDENTIAL, '[secreto omitido]'),
                                 (_EMAIL, '[correo omitido]'),
                                 (_DNI, '[DNI omitido]'),
                                 (_HOME, '[domicilio omitido]')):
        text = pattern.sub(replacement, text)
    text = _TOKEN.sub(lambda m: '[secreto omitido]' if _token_private(m) else m.group(), text)
    text = _PHONE.sub(lambda m: '[teléfono omitido]' if _phone_private(m) else m.group(), text)
    # Replacements can expand short matches, so bound the output too. Everything
    # was already inspected; this cap cannot expose an uninspected credential.
    return text[:MAX_PRIVATE_CHARS]
