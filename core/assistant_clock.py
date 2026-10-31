"""Request-time clock context, independent of the host locale and timezone data."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _utc_now(now=None):
    """Treat an injected naive datetime as UTC, never as the host's local time."""
    instant = datetime.now(timezone.utc) if now is None else now
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(timezone.utc)


def clock_context(now=None):
    """Spanish clock string suitable for SYSTEM and grounded-search prompts.

    Windows may lack the IANA database. The deterministic UTC-03 fallback
    requires no tzdata dependency (and does not infer the machine timezone).
    """
    utc = _utc_now(now)
    try:
        argentina = ZoneInfo('America/Argentina/Buenos_Aires')
    except ZoneInfoNotFoundError:
        argentina = timezone(timedelta(hours=-3))
    local = utc.astimezone(argentina)
    weekdays = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')
    months = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
              'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
    return (f'Fecha y hora actual en Argentina (America/Argentina/Buenos_Aires): '
            f'{weekdays[local.weekday()]} {local.day} de {months[local.month - 1]} '
            f'de {local.year}, {local.isoformat(timespec="seconds")}. '
            f'Fecha y hora actual UTC: {utc.isoformat(timespec="seconds")}.')
