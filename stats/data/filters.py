"""
Módulo de Filtros de Datos
Funciones para filtrar estadísticas por período
"""

from typing import Dict
from datetime import datetime, timedelta


def filter_by_period(stats_data: Dict, period: str = 'all') -> Dict:
    """
    Filtra estadísticas por período de tiempo
    
    Args:
        stats_data: Datos completos de stats
        period: 'today', 'week', 'month', 'all'
    
    Returns:
        Dict filtrado con solo los datos del período
    """
    now = datetime.now()
    
    if period == 'all':
        return stats_data
    
    # Calcular fecha límite
    if period == 'today':
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        cutoff = now - timedelta(days=7)
    elif period == 'month':
        cutoff = now - timedelta(days=30)
    elif period == 'year':
        cutoff = now - timedelta(days=365)
    else:
        return stats_data
    
    # Filtrar datos
    filtered = {'users': {}}
    
    for user_id, user_data in stats_data.get('users', {}).items():
        filtered_user = {
            'username': user_data.get('username', 'Unknown'),
            'games': {},
            'voice': {'count': 0, 'total_minutes': 0, 'last_join': None},
            'messages': user_data.get('messages', {}),  # Mensajes se mantienen
            'reactions': user_data.get('reactions', {}),  # Reacciones se mantienen
            'stickers': user_data.get('stickers', {})  # Stickers se mantienen
        }
        
        # Filtrar juegos por last_played
        for game_name, game_data in user_data.get('games', {}).items():
            try:
                last_played = datetime.fromisoformat(game_data.get('last_played', ''))
                if last_played >= cutoff:
                    filtered_user['games'][game_name] = game_data
            except:
                pass
        
        # Filtrar voz por last_join
        voice = user_data.get('voice', {})
        if voice.get('last_join'):
            try:
                last_join = datetime.fromisoformat(voice['last_join'])
                if last_join >= cutoff:
                    filtered_user['voice'] = voice
            except:
                pass
        
        # Solo agregar si tiene datos en el período
        if filtered_user['games'] or filtered_user['voice'].get('count', 0) > 0:
            filtered['users'][user_id] = filtered_user
    
    return filtered


def filter_by_game(stats_data: Dict, game_name: str) -> Dict:
    """
    Filtra estadísticas para un juego específico
    
    Args:
        stats_data: Datos completos de stats
        game_name: Nombre del juego
    
    Returns:
        Dict filtrado con solo datos del juego
    """
    filtered = {'users': {}}
    
    for user_id, user_data in stats_data.get('users', {}).items():
        games = user_data.get('games', {})
        
        if game_name in games:
            filtered['users'][user_id] = {
                'username': user_data.get('username', 'Unknown'),
                'games': {game_name: games[game_name]}
            }
    
    return filtered


def filter_by_user(stats_data: Dict, user_id: str) -> Dict:
    """
    Filtra estadísticas para un usuario específico
    
    Args:
        stats_data: Datos completos de stats
        user_id: ID del usuario
    
    Returns:
        Dict con datos del usuario o vacío si no existe
    """
    users = stats_data.get('users', {})
    
    if user_id in users:
        return {'users': {user_id: users[user_id]}}
    
    return {'users': {}}


def filter_active_users(stats_data: Dict, min_activity: int = 1) -> Dict:
    """
    Filtra usuarios activos (con al menos X actividad)
    
    Args:
        stats_data: Datos completos de stats
        min_activity: Mínimo de actividad (sesiones) requerida
    
    Returns:
        Dict filtrado con solo usuarios activos
    """
    filtered = {'users': {}}
    
    for user_id, user_data in stats_data.get('users', {}).items():
        # Contar actividad total
        games_count = sum(g.get('count', 0) for g in user_data.get('games', {}).values())
        voice_count = user_data.get('voice', {}).get('count', 0)
        total_activity = games_count + voice_count
        
        if total_activity >= min_activity:
            filtered['users'][user_id] = user_data
    
    return filtered

