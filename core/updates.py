"""
Helpers para publicar novedades curadas del bot.
"""

from pathlib import Path


def _default_updates_path() -> Path:
    return Path(__file__).resolve().parents[1] / 'docs' / 'UPDATES.md'


def load_update_sections(limit: int = 3, updates_path: Path | None = None):
    """Carga secciones Markdown de docs/UPDATES.md."""
    path = updates_path or _default_updates_path()
    if not path.exists():
        return []

    sections = []
    current_title = None
    current_lines = []

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if line.startswith('## '):
            if current_title:
                sections.append((current_title, current_lines))
            current_title = line[3:].strip()
            current_lines = []
        elif current_title and line:
            current_lines.append(line)

    if current_title:
        sections.append((current_title, current_lines))

    return sections[:limit]


def format_latest_update_for_deploy(max_items: int = 3) -> str | None:
    """Devuelve un resumen corto de la última novedad para el mensaje de deploy."""
    sections = load_update_sections(limit=1)
    if not sections:
        return None

    title, lines = sections[0]
    bullets = lines[:max_items]
    if not bullets:
        return f'**Última novedad:** {title}'

    summary = '\n'.join(bullets)
    return f'**Última novedad:** {title}\n{summary}'
