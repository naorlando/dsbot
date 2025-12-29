"""
Pending Notifications - Persistencia ligera para notificaciones
Resuelve inconsistencias de notificaciones durante reinicios del bot
"""

import json
import logging
from typing import Dict, Optional
from pathlib import Path
from core.persistence import DATA_DIR

logger = logging.getLogger('dsbot')

# Archivo de persistencia
PENDING_FILE = Path(DATA_DIR) / 'pending_notifications.json'


def _load_pending() -> dict:
    """Carga el archivo de notificaciones pendientes"""
    if not PENDING_FILE.exists():
        return {'voice': {}, 'games': {}, 'parties': {}}
    
    try:
        with open(PENDING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f'Error cargando pending notifications: {e}')
        return {'voice': {}, 'games': {}, 'parties': {}}


def _save_pending(data: dict):
    """Guarda el archivo de notificaciones pendientes"""
    try:
        with open(PENDING_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f'Error guardando pending notifications: {e}')


# ========== VOICE NOTIFICATIONS ==========

def save_voice_notification(user_id: str, username: str, channel_name: str):
    """
    Guarda que se envió una notificación de entrada a voz.
    Esto permite enviar la notificación de salida si el bot reinicia.
    
    Args:
        user_id: ID del usuario
        username: Nombre del usuario
        channel_name: Nombre del canal de voz
    """
    data = _load_pending()
    data['voice'][user_id] = {
        'username': username,
        'channel_name': channel_name,
        'notification_sent': True,
        'needs_exit_notification': True
    }
    _save_pending(data)
    logger.debug(f'💾 Pending notification guardada: {username} en voz')


def remove_voice_notification(user_id: str):
    """
    Elimina la notificación pendiente cuando se envía la salida de voz.
    
    Args:
        user_id: ID del usuario
    """
    data = _load_pending()
    if user_id in data['voice']:
        del data['voice'][user_id]
        _save_pending(data)
        logger.debug(f'🗑️  Pending notification eliminada: {user_id}')


def get_pending_voice_notifications() -> Dict[str, dict]:
    """
    Retorna todas las notificaciones de voz pendientes.
    
    Returns:
        Dict con formato: {user_id: {username, channel_name, ...}}
    """
    data = _load_pending()
    return data.get('voice', {})


# ========== GAME NOTIFICATIONS ==========

def save_game_notification(user_id: str, username: str, game_name: str):
    """
    Guarda que se envió una notificación de inicio de juego.
    
    Args:
        user_id: ID del usuario
        username: Nombre del usuario
        game_name: Nombre del juego
    """
    data = _load_pending()
    
    # Para juegos, usamos user_id + game_name como key
    # (un usuario puede jugar múltiples juegos)
    key = f"{user_id}_{game_name}"
    
    data['games'][key] = {
        'user_id': user_id,
        'username': username,
        'game_name': game_name,
        'notification_sent': True,
        'needs_exit_notification': True
    }
    _save_pending(data)
    logger.debug(f'💾 Pending notification guardada: {username} jugando {game_name}')


def remove_game_notification(user_id: str, game_name: str):
    """
    Elimina la notificación pendiente cuando se envía la salida de juego.
    
    Args:
        user_id: ID del usuario
        game_name: Nombre del juego
    """
    data = _load_pending()
    key = f"{user_id}_{game_name}"
    
    if key in data['games']:
        del data['games'][key]
        _save_pending(data)
        logger.debug(f'🗑️  Pending notification eliminada: {user_id} - {game_name}')


def get_pending_game_notifications() -> Dict[str, dict]:
    """
    Retorna todas las notificaciones de juegos pendientes.
    
    Returns:
        Dict con formato: {key: {user_id, username, game_name, ...}}
    """
    data = _load_pending()
    return data.get('games', {})


# ========== UTILITY ==========

def clear_all_pending():
    """Elimina todas las notificaciones pendientes (útil para testing)"""
    _save_pending({'voice': {}, 'games': {}, 'parties': {}})
    logger.info('🗑️  Todas las pending notifications eliminadas')


def get_stats() -> dict:
    """
    Retorna estadísticas de notificaciones pendientes.
    
    Returns:
        Dict con counts de cada tipo
    """
    data = _load_pending()
    return {
        'voice_pending': len(data.get('voice', {})),
        'games_pending': len(data.get('games', {})),
        'total_pending': len(data.get('voice', {})) + len(data.get('games', {}))
    }

