"""
Módulo de tracking de estadísticas
Maneja el registro de eventos de juegos, voz, mensajes, reacciones, stickers
"""

import logging
from datetime import datetime
from core.persistence import stats, save_stats

logger = logging.getLogger('dsbot')


def record_game_event(user_id, username, game_name):
    """Registra un evento de juego en las estadísticas"""
    if user_id not in stats['users']:
        stats['users'][user_id] = {
            'username': username,
            'games': {},
            'voice': {'count': 0, 'last_join': None},
            'messages': {'count': 0, 'characters': 0},
            'reactions': {'total': 0, 'by_emoji': {}},
            'stickers': {'total': 0, 'by_name': {}},
            'daily_connections': {
                'total': 0,
                'by_date': {},
                'personal_record': {'count': 0, 'date': None}
            }
        }
    
    if game_name not in stats['users'][user_id]['games']:
        stats['users'][user_id]['games'][game_name] = {
            'count': 0,
            'first_played': datetime.now().isoformat(),
            'last_played': None
        }
    
    # Asegurar que tiene todos los campos nuevos
    game_data = stats['users'][user_id]['games'][game_name]
    if 'total_minutes' not in game_data:
        game_data['total_minutes'] = 0
    if 'daily_minutes' not in game_data:
        game_data['daily_minutes'] = {}
    if 'current_session' not in game_data:
        game_data['current_session'] = None
    
    stats['users'][user_id]['games'][game_name]['count'] += 1
    stats['users'][user_id]['games'][game_name]['last_played'] = datetime.now().isoformat()
    stats['users'][user_id]['username'] = username
    save_stats()
    
    logger.info(f'📊 Stats: {username} jugó {game_name} ({stats["users"][user_id]["games"][game_name]["count"]} veces)')


def record_message_event(user_id, username, message_length):
    """Registra un mensaje en las estadísticas"""
    if user_id not in stats['users']:
        stats['users'][user_id] = {
            'username': username,
            'games': {},
            'voice': {'count': 0, 'last_join': None, 'total_minutes': 0, 'daily_minutes': {}},
            'messages': {'count': 0, 'characters': 0, 'last_message': None},
            'reactions': {'total': 0, 'by_emoji': {}},
            'stickers': {'total': 0, 'by_name': {}},
            'daily_connections': {
                'total': 0,
                'by_date': {},
                'personal_record': {'count': 0, 'date': None}
            }
        }
    
    # Asegurar que existe la estructura de mensajes
    if 'messages' not in stats['users'][user_id]:
        stats['users'][user_id]['messages'] = {'count': 0, 'characters': 0, 'last_message': None}
    
    stats['users'][user_id]['messages']['count'] += 1
    stats['users'][user_id]['messages']['characters'] += message_length
    stats['users'][user_id]['messages']['last_message'] = datetime.now().isoformat()
    stats['users'][user_id]['username'] = username
    
    save_stats()
    
    # Log solo cada 10 mensajes para no spamear logs
    if stats['users'][user_id]['messages']['count'] % 10 == 0:
        logger.debug(f'📊 Stats: {username} - {stats["users"][user_id]["messages"]["count"]} mensajes, {stats["users"][user_id]["messages"]["characters"]} chars')


def start_game_session(user_id, username, game_name):
    """Inicia una sesión de juego para tracking de tiempo"""
    if user_id not in stats['users']:
        stats['users'][user_id] = {
            'username': username,
            'games': {},
            'voice': {'count': 0, 'last_join': None},
            'messages': {'count': 0, 'characters': 0},
            'reactions': {'total': 0, 'by_emoji': {}},
            'stickers': {'total': 0, 'by_name': {}},
            'daily_connections': {
                'total': 0,
                'by_date': {},
                'personal_record': {'count': 0, 'date': None}
            }
        }
    
    if game_name not in stats['users'][user_id]['games']:
        stats['users'][user_id]['games'][game_name] = {
            'count': 0,
            'first_played': datetime.now().isoformat(),
            'last_played': None,
            'total_minutes': 0,
            'daily_minutes': {},
            'current_session': None
        }
    
    # Guardar sesión actual
    stats['users'][user_id]['games'][game_name]['current_session'] = {
        'start': datetime.now().isoformat()
    }
    stats['users'][user_id]['username'] = username
    
    save_stats()
    logger.debug(f'🕐 Sesión de juego iniciada: {username} - {game_name}')


def end_game_session(user_id, username, game_name):
    """Finaliza una sesión de juego y calcula el tiempo"""
    if user_id not in stats['users']:
        return
    
    if game_name not in stats['users'][user_id]['games']:
        return
    
    game_data = stats['users'][user_id]['games'][game_name]
    current_session = game_data.get('current_session')
    
    if not current_session:
        return
    
    try:
        start_time = datetime.fromisoformat(current_session['start'])
        end_time = datetime.now()
        duration = end_time - start_time
        minutes = int(duration.total_seconds() / 60)
        
        # Solo contar si jugó más de 1 minuto
        if minutes >= 1:
            # Actualizar total
            game_data['total_minutes'] = game_data.get('total_minutes', 0) + minutes
            
            # Actualizar daily
            today = datetime.now().strftime('%Y-%m-%d')
            if 'daily_minutes' not in game_data:
                game_data['daily_minutes'] = {}
            game_data['daily_minutes'][today] = game_data['daily_minutes'].get(today, 0) + minutes
            
            logger.info(f'🕐 Sesión finalizada: {username} jugó {game_name} por {minutes} min')
        
        # Limpiar sesión actual
        game_data['current_session'] = None
        save_stats()
        
    except Exception as e:
        logger.error(f'Error al finalizar sesión de juego: {e}')
        game_data['current_session'] = None
        save_stats()


def record_voice_event(user_id, username):
    """Registra un evento de entrada a voz en las estadísticas"""
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
            'messages': {'count': 0, 'characters': 0},
            'reactions': {'total': 0, 'by_emoji': {}},
            'stickers': {'total': 0, 'by_name': {}},
            'daily_connections': {
                'total': 0,
                'by_date': {},
                'personal_record': {'count': 0, 'date': None}
            }
        }
    
    # Asegurar que voice tenga todos los campos
    voice = stats['users'][user_id].get('voice', {})
    if 'total_minutes' not in voice:
        voice['total_minutes'] = 0
    if 'daily_minutes' not in voice:
        voice['daily_minutes'] = {}
    if 'current_session' not in voice:
        voice['current_session'] = None
    
    stats['users'][user_id]['voice']['count'] += 1
    stats['users'][user_id]['voice']['last_join'] = datetime.now().isoformat()
    stats['users'][user_id]['username'] = username
    save_stats()
    
    logger.info(f'📊 Stats: {username} entró a voz ({stats["users"][user_id]["voice"]["count"]} veces)')


def start_voice_session(user_id, username, channel_name):
    """Inicia una sesión de voz para tracking de tiempo"""
    if user_id not in stats['users']:
        stats['users'][user_id] = {
            'username': username,
            'games': {},
            'voice': {
                'count': 0,
                'total_minutes': 0,
                'daily_minutes': {},
                'current_session': None
            },
            'messages': {'count': 0, 'characters': 0},
            'reactions': {'total': 0, 'by_emoji': {}},
            'stickers': {'total': 0, 'by_name': {}},
            'daily_connections': {
                'total': 0,
                'by_date': {},
                'personal_record': {'count': 0, 'date': None}
            }
        }
    
    # Guardar sesión actual
    stats['users'][user_id]['voice']['current_session'] = {
        'channel': channel_name,
        'start': datetime.now().isoformat()
    }
    stats['users'][user_id]['username'] = username
    
    save_stats()
    logger.debug(f'🕐 Sesión de voz iniciada: {username} en {channel_name}')


def end_voice_session(user_id, username):
    """Finaliza una sesión de voz y calcula el tiempo"""
    if user_id not in stats['users']:
        return
    
    voice_data = stats['users'][user_id].get('voice', {})
    current_session = voice_data.get('current_session')
    
    if not current_session:
        return
    
    try:
        start_time = datetime.fromisoformat(current_session['start'])
        end_time = datetime.now()
        duration = end_time - start_time
        minutes = int(duration.total_seconds() / 60)
        
        # Solo contar si estuvo más de 1 minuto
        if minutes >= 1:
            # Actualizar total
            voice_data['total_minutes'] = voice_data.get('total_minutes', 0) + minutes
            
            # Actualizar daily
            today = datetime.now().strftime('%Y-%m-%d')
            if 'daily_minutes' not in voice_data:
                voice_data['daily_minutes'] = {}
            voice_data['daily_minutes'][today] = voice_data['daily_minutes'].get(today, 0) + minutes
            
            logger.info(f'🕐 Sesión finalizada: {username} estuvo {minutes} min en {current_session["channel"]}')
        
        # Limpiar sesión actual
        voice_data['current_session'] = None
        save_stats()
        
    except Exception as e:
        logger.error(f'Error al finalizar sesión de voz: {e}')
        voice_data['current_session'] = None
        save_stats()


def record_connection_event(user_id, username):
    """
    Registra una conexión diaria del usuario (offline → online)
    Retorna el contador actual del día y si rompió récord personal
    """
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Inicializar estructura si no existe
    if user_id not in stats['users']:
        stats['users'][user_id] = {
            'username': username,
            'games': {},
            'voice': {'count': 0},
            'messages': {'count': 0, 'characters': 0},
            'reactions': {'total': 0, 'by_emoji': {}},
            'stickers': {'total': 0, 'by_name': {}},
            'daily_connections': {
                'total': 0,
                'by_date': {},
                'personal_record': {
                    'count': 0,
                    'date': None
                }
            }
        }
    
    # Asegurar que existe la estructura de conexiones
    if 'daily_connections' not in stats['users'][user_id]:
        stats['users'][user_id]['daily_connections'] = {
            'total': 0,
            'by_date': {},
            'personal_record': {
                'count': 0,
                'date': None
            }
        }
    
    connections = stats['users'][user_id]['daily_connections']
    
    # Asegurar campos
    if 'total' not in connections:
        connections['total'] = 0
    if 'by_date' not in connections:
        connections['by_date'] = {}
    if 'personal_record' not in connections:
        connections['personal_record'] = {'count': 0, 'date': None}
    
    # Incrementar contadores
    connections['total'] += 1
    connections['by_date'][today] = connections['by_date'].get(today, 0) + 1
    
    # Actualizar username
    stats['users'][user_id]['username'] = username
    
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
    
    logger.info(f'📱 Conexión: {username} ({count_today} veces hoy, {connections["total"]} total)')
    
    return count_today, broke_record

