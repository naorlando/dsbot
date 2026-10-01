"""Bounded HTML reading for a fixed official page, not an arbitrary URL tool."""
import asyncio
import re
from html.parser import HTMLParser

import aiohttp

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
