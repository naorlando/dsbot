"""
Light Persistence para notificaciones de voice pendientes
SIMPLIFICADO: Solo voice, games no necesita persistence
"""

import json
import os
import logging
from core.persistence import DATA_DIR

logger = logging.getLogger('dsbot')

PENDING_NOTIFICATIONS_FILE = os.path.join(DATA_DIR, 'pending_notifications.json')

_pending_notifications = {
    "voice": {}
}


def _load_pending():
    """Carga notificaciones pendientes desde archivo"""
    global _pending_notifications
    try:
        if os.path.exists(PENDING_NOTIFICATIONS_FILE):
            with open(PENDING_NOTIFICATIONS_FILE, 'r', encoding='utf-8') as f:
                _pending_notifications = json.load(f)
                # Asegurar estructura voice
                if "voice" not in _pending_notifications:
                    _pending_notifications["voice"] = {}
                logger.debug(f'Pending notifications cargadas: {len(_pending_notifications["voice"])} voice')
    except Exception as e:
        logger.error(f'Error cargando pending notifications: {e}')
        _pending_notifications = {"voice": {}}


def _save_pending():
    """Guarda notificaciones pendientes en archivo"""
    try:
        with open(PENDING_NOTIFICATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(_pending_notifications, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f'Error guardando pending notifications: {e}')


# ==================== VOICE ====================

def save_voice_notification(user_id: str, username: str, channel_name: str):
    """
    Guarda una notificación de voice pendiente.
    
    Args:
        user_id: ID del usuario
        username: Nombre del usuario
        channel_name: Nombre del canal de voz
    """
    _load_pending()
    
    _pending_notifications['voice'][user_id] = {
        'user_id': user_id,
        'username': username,
        'channel_name': channel_name
    }
    
    _save_pending()
    logger.debug(f'💾 Pending notification guardada: {username} en voz')


def remove_voice_notification(user_id: str):
    """
    Elimina una notificación de voice pendiente.
    
    Args:
        user_id: ID del usuario
    """
    _load_pending()
    
    if user_id in _pending_notifications['voice']:
        del _pending_notifications['voice'][user_id]
        _save_pending()
        logger.debug(f'🗑️  Pending notification eliminada: {user_id}')


def get_pending_voice_notifications() -> dict:
    """
    Obtiene todas las notificaciones de voice pendientes.
    
    Returns:
        Diccionario de notificaciones de voice: {user_id: {data}}
    """
    _load_pending()
    return _pending_notifications['voice'].copy()


# Inicializar al importar el módulo
_load_pending()
