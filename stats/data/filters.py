"""
Módulo de Filtros de Datos
Funciones para filtrar estadísticas por período
"""

from typing import Dict
from datetime import timedelta

from core.assistant_clock import argentina_now


def filter_by_period(stats_data: Dict, period: str = 'all') -> Dict:
    """
    Filtra estadísticas por período de tiempo.

    El corte es el día ART (America/Argentina/Buenos_Aires), no la medianoche
    UTC: a las 22:00 ART el día UTC ya cambió y "hoy" mostraba ayer.

    Args:
        stats_data: Datos completos de stats
        period: 'today', 'week', 'month', 'year', 'all'

    Returns:
        Dict filtrado, con `total_minutes` recalculado desde `daily_minutes`
        para el período. `count` sigue siendo histórico: no hay conteo diario.
    """
    if period == 'all':
        return stats_data
    days = {'today': 1, 'week': 7, 'month': 30, 'year': 365}.get(period)
    if days is None:
        return stats_data
    today = argentina_now().date()
    start = (today - timedelta(days=days - 1)).isoformat()
    end = today.isoformat()

    def window(daily):
        return {date: value for date, value in (daily or {}).items()
                if isinstance(date, str) and start <= date <= end}

    filtered = {'users': {}}
    for user_id, user_data in stats_data.get('users', {}).items():
        games = {}
        for game_name, game_data in user_data.get('games', {}).items():
            daily = window(game_data.get('daily_minutes'))
            if not daily:
                continue
            games[game_name] = {**game_data, 'daily_minutes': daily,
                                'total_minutes': round(sum(daily.values()), 1)}
        voice = user_data.get('voice', {})
        daily = window(voice.get('daily_minutes'))
        voice = {**voice, 'daily_minutes': daily,
                 'total_minutes': round(sum(daily.values()), 1)}
        if games or daily:
            filtered['users'][user_id] = {
                'username': user_data.get('username', 'Unknown'),
                'games': games,
                'voice': voice,
                'messages': user_data.get('messages', {}),
                'reactions': user_data.get('reactions', {}),
                'stickers': user_data.get('stickers', {}),
                'daily_connections': user_data.get('daily_connections', {}),
            }
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

