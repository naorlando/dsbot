"""
Módulo de cooldown (anti-spam)
Maneja el sistema de cooldown de 10 minutos para eventos
"""

import logging
from datetime import datetime, timedelta
from core.persistence import stats, save_stats

logger = logging.getLogger('dsbot')


def check_cooldown(user_id, event_key, cooldown_seconds=600):
    """
    Verifica si pasó el tiempo de cooldown desde el último evento similar.
    
    Args:
        user_id: ID del usuario
        event_key: Clave del evento (ej: 'game:Fortnite', 'voice', 'daily_connection')
        cooldown_seconds: Tiempo de cooldown en segundos (default: 600 = 10 minutos)
    
    Retorna True si puede registrar el evento, False si está en cooldown.
    """
    cooldown_key = f"{user_id}:{event_key}"
    last_time_str = stats['cooldowns'].get(cooldown_key)
    
    if last_time_str:
        try:
            last_time = datetime.fromisoformat(last_time_str)
            if datetime.now() - last_time < timedelta(seconds=cooldown_seconds):
                logger.debug(f'Cooldown activo para {cooldown_key} ({cooldown_seconds}s)')
                return False
        except ValueError:
            pass
    
    # Actualizar cooldown
    stats['cooldowns'][cooldown_key] = datetime.now().isoformat()
    save_stats()
    return True


def is_cooldown_passed(user_id, event_key, cooldown_seconds=600):
    """
    Verifica si pasó el tiempo de cooldown SIN actualizarlo.
    Útil para verificar el estado del cooldown sin consumirlo.
    
    Args:
        user_id: ID del usuario
        event_key: Clave del evento
        cooldown_seconds: Tiempo de cooldown en segundos
    
    Retorna True si el cooldown ya pasó, False si aún está activo.
    """
    cooldown_key = f"{user_id}:{event_key}"
    last_time_str = stats['cooldowns'].get(cooldown_key)
    
    if not last_time_str:
        return True  # No hay cooldown registrado, se considera que pasó
    
    try:
        last_time = datetime.fromisoformat(last_time_str)
        return datetime.now() - last_time >= timedelta(seconds=cooldown_seconds)
    except ValueError:
        return True  # Error al parsear, se considera que pasó

