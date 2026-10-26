"""Bounded HTML reading for a fixed official page, not an arbitrary URL tool."""
import asyncio
import re
from html.parser import HTMLParser

import aiohttp

from urllib.parse import urlparse

RENAPER_URL = 'https://www.argentina.gob.ar/interior/renaper/tarifario-de-tramites-de-renaper'


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.hidden += 1
        if not self.hidden and tag in {'li', 'p', 'br', 'h1', 'h2', 'h3', 'h4', 'tr'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.hidden = max(0, self.hidden - 1)
        if not self.hidden and tag in {'li', 'p', 'h1', 'h2', 'h3', 'h4', 'tr'}:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def passport_section(html):
    parser = VisibleText()
    parser.feed(html)
    text = ''.join(parser.parts)
    match = re.search(r'\bPASAPORTE\b(.*?)\bOTROS TRÁMITES\b', text, re.S)
    if not match:
        return ''
    return '\n'.join(re.sub(r'\s+', ' ', line).strip() for line in match.group(0).splitlines() if line.strip())[:5000]


async def official_passport(session):
    """URL literal; no redirects, cookies, credentials, model arguments or DNS target input."""
    try:
        async with session.get(RENAPER_URL, allow_redirects=False,
                               timeout=aiohttp.ClientTimeout(total=8)) as response:
            if response.status != 200 or 'text/html' not in response.headers.get('Content-Type', ''):
                return ''
            chunks, size = [], 0
            async for chunk in response.content.iter_chunked(8192):
                size += len(chunk)
                if size > 262144:
                    return ''
                chunks.append(chunk)
            return passport_section(b''.join(chunks).decode('utf-8'))
    except (aiohttp.ClientError, asyncio.TimeoutError, UnicodeError, ValueError):
        return ''


# Deterministic dollar reading: a too-small model misquotes live prices, so the
# harness extracts compra/venta directly from the pages. No LLM, no invented cents.
PRICE = r'(\d{1,3}[.,]\d{3})(?:,(\d{2}))?'


def _money(value):
    """'1.557' + '40' -> '1.557,40' (es-AR thousands dot, decimals comma)."""
    return value.group(1) + (',' + value.group(2) if value.group(2) else '')


def _blue_block(content):
    """Text around 'dólar blue' up to the next dollar type, whitespace-normalized."""
    text = re.sub(r'\s+', ' ', content).strip()
    match = re.search(r'(?i)d[oó]lar blue(.{0,700}?)(?=d[oó]lar (?:oficial|mayorista|mep|bolsa|ccl|contado|tarjeta|turista|libre|digital)\b|$)',
                      text, re.S)
    return match.group(1) if match else ''


def _pair(block, value_first):
    found = {}
    for kind in ('compra', 'venta'):
        # Tables put the word first ("Compra$1.545..."); prose puts it after.
        pattern = (PRICE + r'\D{0,12}?\b' + kind + r'\b') if value_first else (r'\b' + kind + r'\D{0,8}?' + PRICE)
        match = re.search(pattern, block, re.I)
        if match:
            found[kind] = _money(match)
    compra, venta = found.get('compra'), found.get('venta')
    return (compra, venta) if compra and venta else None


def dollar_quote(content):
    """(compra, venta) textual found in one page text, or None."""
    block = _blue_block(content)
    if not block:
        return None
    pair = _pair(block, value_first=False)
    if not pair or pair[0] == pair[1]:
        # One side swallowed the other's price (prose word order): restart
        # with the value-precedes-word strategy, so both sides are independent.
        pair = _pair(block, value_first=True)
    return pair if pair and pair[0] != pair[1] else pair


def dollar_answer(sources):
    """Deterministic reply for 'cuánto está el dólar': zero model calls."""
    for index, source in enumerate(sources, start=1):
        quote = dollar_quote(source.get('content', ''))
        if not quote:
            continue
        compra, venta = quote
        host = urlparse(source['url']).hostname or ''
        link = re.sub(r'([*_`~|<>])', r'\\\1', source['url'])
        return (f'Dólar blue hoy: compra ${compra} / venta ${venta}.\n'
                f'Fuente: [{index}] <{link}> ({host}). No es recomendación financiera.')
