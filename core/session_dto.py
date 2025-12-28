"""
Módulo DTO (Data Transfer Object) para persistencia de estadísticas
Solo guarda datos en stats.json, sin lógica de negocio
"""

import logging
from datetime import datetime
from core.persistence import stats, save_stats

logger = logging.getLogger('dsbot')


def _ensure_user_exists(user_id: str, username: str):
    """Asegura que el usuario existe en stats con estructura completa"""
    if user_id not in stats['users']:
        stats['users'][user_id] = {
            'username': username,
            'games': {},
            'voice': {
                'count': 0,
                'last_join': None,
                'total_minutes': 0,
                'daily_minutes': {},
                'current_session': None
            },
            'messages': {'count': 0, 'characters': 0, 'last_message': None},
            'reactions': {'total': 0, 'by_emoji': {}},
            'stickers': {'total': 0, 'by_name': {}},
            'daily_connections': {
                'total': 0,
                'by_date': {},
                'personal_record': {'count': 0, 'date': None}
            }
        }
    else:
        # Actualizar username si cambió
        stats['users'][user_id]['username'] = username


# ==================== JUEGOS ====================

def save_game_time(user_id: str, username: str, game_name: str, minutes: int):
    """
    Guarda tiempo jugado. Solo persistencia, sin lógica de negocio.
    
    Args:
        user_id: ID del usuario
        username: Nombre del usuario
        game_name: Nombre del juego
        minutes: Minutos jugados
    """
    _ensure_user_exists(user_id, username)
    
    if game_name not in stats['users'][user_id]['games']:
        stats['users'][user_id]['games'][game_name] = {
            'count': 0,
            'first_played': datetime.now().isoformat(),
            'last_played': None,
            'total_minutes': 0,
            'daily_minutes': {},
            'current_session': None
        }
    
    game_data = stats['users'][user_id]['games'][game_name]
    
    # Actualizar total
    game_data['total_minutes'] = game_data.get('total_minutes', 0) + minutes
    
    # Actualizar daily
    today = datetime.now().strftime('%Y-%m-%d')
    if 'daily_minutes' not in game_data:
        game_data['daily_minutes'] = {}
    game_data['daily_minutes'][today] = game_data['daily_minutes'].get(today, 0) + minutes
    
    save_stats()
    logger.debug(f'💾 Tiempo guardado: {username} jugó {game_name} por {minutes} min')


def increment_game_count(user_id: str, username: str, game_name: str):
    """
    Incrementa contador de veces jugado. Solo persistencia.
    
    Args:
        user_id: ID del usuario
        username: Nombre del usuario
        game_name: Nombre del juego
    """
    _ensure_user_exists(user_id, username)
    
    if game_name not in stats['users'][user_id]['games']:
        stats['users'][user_id]['games'][game_name] = {
            'count': 0,
            'first_played': datetime.now().isoformat(),
            'last_played': None,
            'total_minutes': 0,
            'daily_minutes': {},
            'current_session': None
        }
    
    game_data = stats['users'][user_id]['games'][game_name]
    game_data['count'] += 1
    game_data['last_played'] = datetime.now().isoformat()
    
    save_stats()
    logger.debug(f'💾 Contador incrementado: {username} jugó {game_name} ({game_data["count"]} veces)')


def set_game_session_start(user_id: str, username: str, game_name: str):
    """
    Establece el inicio de una sesión de juego en stats.
    Solo persistencia, sin lógica de negocio.
    """
    _ensure_user_exists(user_id, username)
    
    if game_name not in stats['users'][user_id]['games']:
        stats['users'][user_id]['games'][game_name] = {
            'count': 0,
            'first_played': datetime.now().isoformat(),
            'last_played': None,
            'total_minutes': 0,
            'daily_minutes': {},
            'current_session': None
        }
    
    stats['users'][user_id]['games'][game_name]['current_session'] = {
        'start': datetime.now().isoformat()
    }
    
    save_stats()
    logger.debug(f'💾 Sesión iniciada: {username} - {game_name}')


def clear_game_session(user_id: str, game_name: str):
    """
    Limpia la sesión actual de un juego.
    Solo persistencia, sin lógica de negocio.
    """
    if user_id not in stats['users']:
        return
    
    if game_name not in stats['users'][user_id]['games']:
        return
    
    stats['users'][user_id]['games'][game_name]['current_session'] = None
    save_stats()


# ==================== VOZ ====================

def save_voice_time(user_id: str, username: str, minutes: int, channel_name: str = None):
    """
    Guarda tiempo en voz. Solo persistencia, sin lógica de negocio.
    
    Args:
        user_id: ID del usuario
        username: Nombre del usuario
        minutes: Minutos en voz
        channel_name: Nombre del canal (opcional, para logging)
    """
    _ensure_user_exists(user_id, username)
    
    voice_data = stats['users'][user_id]['voice']
    
    # Actualizar total
    voice_data['total_minutes'] = voice_data.get('total_minutes', 0) + minutes
    
    # Actualizar daily
    today = datetime.now().strftime('%Y-%m-%d')
    if 'daily_minutes' not in voice_data:
        voice_data['daily_minutes'] = {}
    voice_data['daily_minutes'][today] = voice_data['daily_minutes'].get(today, 0) + minutes
    
    save_stats()
    if channel_name:
        logger.debug(f'💾 Tiempo guardado: {username} estuvo {minutes} min en {channel_name}')
    else:
        logger.debug(f'💾 Tiempo guardado: {username} estuvo {minutes} min en voz')


def increment_voice_count(user_id: str, username: str):
    """
    Incrementa contador de veces que entró a voz. Solo persistencia.
    
    Args:
        user_id: ID del usuario
        username: Nombre del usuario
    """
    _ensure_user_exists(user_id, username)
    
    voice_data = stats['users'][user_id]['voice']
    voice_data['count'] += 1
    voice_data['last_join'] = datetime.now().isoformat()
    
    save_stats()
    logger.debug(f'💾 Contador incrementado: {username} entró a voz ({voice_data["count"]} veces)')


def set_voice_session_start(user_id: str, username: str, channel_name: str):
    """
    Establece el inicio de una sesión de voz en stats.
    Solo persistencia, sin lógica de negocio.
    """
    _ensure_user_exists(user_id, username)
    
    stats['users'][user_id]['voice']['current_session'] = {
        'channel': channel_name,
        'start': datetime.now().isoformat()
    }
    
    save_stats()
    logger.debug(f'💾 Sesión iniciada: {username} en {channel_name}')


def clear_voice_session(user_id: str):
    """
    Limpia la sesión actual de voz.
    Solo persistencia, sin lógica de negocio.
    """
    if user_id not in stats['users']:
        return
    
    stats['users'][user_id]['voice']['current_session'] = None
    save_stats()


# ==================== MENSAJES ====================

def save_message_event(user_id: str, username: str, message_length: int):
    """
    Guarda un mensaje en las estadísticas. Solo persistencia.
    
    Args:
        user_id: ID del usuario
        username: Nombre del usuario
        message_length: Longitud del mensaje en caracteres
    """
    _ensure_user_exists(user_id, username)
    
    messages_data = stats['users'][user_id]['messages']
    messages_data['count'] += 1
    messages_data['characters'] += message_length
    messages_data['last_message'] = datetime.now().isoformat()
    
    save_stats()
    
    # Log solo cada 10 mensajes para no spamear logs
    if messages_data['count'] % 10 == 0:
        logger.debug(f'💾 Stats: {username} - {messages_data["count"]} mensajes, {messages_data["characters"]} chars')


# ==================== REACCIONES ====================

def save_reaction_event(user_id: str, username: str, emoji: str):
    """
    Guarda una reacción en las estadísticas. Solo persistencia.
    
    Args:
        user_id: ID del usuario
        username: Nombre del usuario
        emoji: Emoji usado
    """
    _ensure_user_exists(user_id, username)
    
    reactions_data = stats['users'][user_id]['reactions']
    reactions_data['total'] += 1
    
    if 'by_emoji' not in reactions_data:
        reactions_data['by_emoji'] = {}
    reactions_data['by_emoji'][emoji] = reactions_data['by_emoji'].get(emoji, 0) + 1
    
    save_stats()
    logger.debug(f'💾 Reacción guardada: {username} usó {emoji}')


# ==================== STICKERS ====================

def save_sticker_event(user_id: str, username: str, sticker_name: str):
    """
    Guarda un sticker en las estadísticas. Solo persistencia.
    
    Args:
        user_id: ID del usuario
        username: Nombre del usuario
        sticker_name: Nombre del sticker
    """
    _ensure_user_exists(user_id, username)
    
    stickers_data = stats['users'][user_id]['stickers']
    stickers_data['total'] += 1
    
    if 'by_name' not in stickers_data:
        stickers_data['by_name'] = {}
    stickers_data['by_name'][sticker_name] = stickers_data['by_name'].get(sticker_name, 0) + 1
    
    save_stats()
    logger.debug(f'💾 Sticker guardado: {username} usó {sticker_name}')


# ==================== CONEXIONES ====================

def save_connection_event(user_id: str, username: str):
    """
    Guarda una conexión diaria. Solo persistencia.
    
    Args:
        user_id: ID del usuario
        username: Nombre del usuario
    
    Returns:
        tuple: (count_today, broke_record)
    """
    _ensure_user_exists(user_id, username)
    
    today = datetime.now().strftime('%Y-%m-%d')
    connections = stats['users'][user_id]['daily_connections']
    
    # Incrementar contadores
    connections['total'] += 1
    connections['by_date'][today] = connections['by_date'].get(today, 0) + 1
    
    # Obtener contador actual del día
    count_today = connections['by_date'][today]
    
    # Verificar récord personal
    broke_record = False
    personal_record = connections['personal_record']
    if count_today > personal_record['count']:
        personal_record['count'] = count_today
        personal_record['date'] = today
        broke_record = True
    
    save_stats()
    logger.debug(f'💾 Conexión guardada: {username} ({count_today} veces hoy, {connections["total"]} total)')
    
    return count_today, broke_record

