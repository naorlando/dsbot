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
    
    El cooldown es PREDECIBLE: se cuenta desde la última notificación EXITOSA.
    Si pasaron >cooldown_seconds desde la última notificación → Permite nueva notificación.
    Si pasaron <cooldown_seconds → Rechaza sin actualizar el timestamp.
    
    Args:
        user_id: ID del usuario
        event_key: Clave del evento (ej: 'game:Fortnite', 'voice', 'daily_connection')
        cooldown_seconds: Tiempo de cooldown en segundos (default: 600 = 10 minutos)
    
    Retorna True si puede registrar el evento, False si está en cooldown.
    """
    cooldown_key = f"{user_id}:{event_key}"
    last_time_str = stats['cooldowns'].get(cooldown_key)
    now = datetime.now()
    
    if last_time_str:
        try:
            last_time = datetime.fromisoformat(last_time_str)
            time_since_last = (now - last_time).total_seconds()
            
            if time_since_last < cooldown_seconds:
                # Cooldown activo: NO actualizar timestamp (cooldown predecible)
                logger.debug(f'⏳ En cooldown: {cooldown_key} ({int(time_since_last)}s desde última notificación < {cooldown_seconds}s)')
                return False
        except ValueError:
            pass
    
    # Cooldown pasó o no existía: Actualizar y permitir notificación
    stats['cooldowns'][cooldown_key] = now.isoformat()
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

