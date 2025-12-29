"""
Módulo de Agregadores de Datos
Funciones para agregar y procesar estadísticas
"""

from typing import Dict, List, Tuple
from datetime import datetime, timedelta


def aggregate_game_stats(stats_data: Dict) -> Dict[str, Dict]:
    """
    Agrega estadísticas de juegos de todos los usuarios
    
    Args:
        stats_data: Datos completos de stats
        
    Returns:
        Dict con {game_name: {minutes, count, players, parties}}
    """
    game_stats = {}
    
    for user_data in stats_data.get('users', {}).values():
        for game, data in user_data.get('games', {}).items():
            if game not in game_stats:
                game_stats[game] = {
                    'minutes': 0,
                    'count': 0,
                    'players': set(),
                    'parties': 0
                }
            
            game_stats[game]['minutes'] += data.get('total_minutes', 0)
            game_stats[game]['count'] += data.get('count', 0)
            game_stats[game]['players'].add(user_data.get('username', 'Unknown'))
    
    # Convertir sets a listas y contar
    for game in game_stats:
        players = game_stats[game]['players']
        game_stats[game]['player_count'] = len(players)
        game_stats[game]['player_list'] = list(players)
        del game_stats[game]['players']
    
    return game_stats


def aggregate_voice_stats(stats_data: Dict) -> List[Tuple[str, int, int]]:
    """
    Agrega estadísticas de voz de todos los usuarios
    
    Args:
        stats_data: Datos completos de stats
        
    Returns:
        Lista de tuplas (username, minutes, count) ordenada por tiempo
    """
    voice_stats = []
    
    for user_id, user_data in stats_data.get('users', {}).items():
        username = user_data.get('username', 'Unknown')
        voice = user_data.get('voice', {})
        
        minutes = voice.get('total_minutes', 0)
        count = voice.get('count', 0)
        
        if minutes > 0 or count > 0:
            voice_stats.append((username, minutes, count))
    
    # Ordenar por tiempo
    voice_stats.sort(key=lambda x: x[1], reverse=True)
    
    return voice_stats


def aggregate_game_time_by_user(stats_data: Dict) -> List[Tuple[str, int, int, int]]:
    """
    Agrega tiempo de juego por usuario
    
    Args:
        stats_data: Datos completos de stats
        
    Returns:
        Lista de tuplas (username, minutes, games_count, unique_games) ordenada por tiempo
    """
    user_stats = []
    
    for user_id, user_data in stats_data.get('users', {}).items():
        username = user_data.get('username', 'Unknown')
        games = user_data.get('games', {})
        
        total_minutes = sum(g.get('total_minutes', 0) for g in games.values())
        total_count = sum(g.get('count', 0) for g in games.values())
        unique_games = len(games)
        
        if total_minutes > 0 or total_count > 0:
            user_stats.append((username, total_minutes, total_count, unique_games))
    
    # Ordenar por tiempo
    user_stats.sort(key=lambda x: x[1], reverse=True)
    
    return user_stats


def aggregate_party_stats(stats_data: Dict) -> Dict:
    """
    Agrega estadísticas de parties
    
    Args:
        stats_data: Datos completos de stats
        
    Returns:
        Dict con estadísticas de parties
    """
    # TODO: Implementar cuando se agreguen stats de parties al JSON
    party_stats = {
        'total_parties': 0,
        'by_game': {},
        'by_user': {},
        'largest_party': 0,
        'longest_party_minutes': 0
    }
    
    return party_stats


def aggregate_message_stats(stats_data: Dict) -> List[Tuple[str, int, int]]:
    """
    Agrega estadísticas de mensajes por usuario
    
    Args:
        stats_data: Datos completos de stats
        
    Returns:
        Lista de tuplas (username, count, characters) ordenada por count
    """
    message_stats = []
    
    for user_id, user_data in stats_data.get('users', {}).items():
        username = user_data.get('username', 'Unknown')
        messages = user_data.get('messages', {})
        
        count = messages.get('count', 0)
        characters = messages.get('characters', 0)
        
        if count > 0:
            message_stats.append((username, count, characters))
    
    # Ordenar por count
    message_stats.sort(key=lambda x: x[1], reverse=True)
    
    return message_stats


def get_top_players_for_game(stats_data: Dict, game_name: str, limit: int = 10) -> List[Tuple[str, int, int]]:
    """
    Obtiene los mejores jugadores de un juego específico
    
    Args:
        stats_data: Datos completos de stats
        game_name: Nombre del juego
        limit: Límite de jugadores
        
    Returns:
        Lista de tuplas (username, minutes, count) ordenada por tiempo
    """
    players = []
    
    for user_id, user_data in stats_data.get('users', {}).items():
        username = user_data.get('username', 'Unknown')
        games = user_data.get('games', {})
        
        if game_name in games:
            game_data = games[game_name]
            minutes = game_data.get('total_minutes', 0)
            count = game_data.get('count', 0)
            
            if minutes > 0 or count > 0:
                players.append((username, minutes, count))
    
    # Ordenar por tiempo
    players.sort(key=lambda x: x[1], reverse=True)
    
    return players[:limit]


def calculate_daily_activity(stats_data: Dict, days: int = 7) -> Dict[str, int]:
    """
    Calcula la actividad diaria para los últimos N días
    
    Args:
        stats_data: Datos de stats
        days: Número de días a calcular
    
    Returns:
        Dict con fecha (YYYY-MM-DD) -> count
    """
    daily = {}
    
    # Inicializar los últimos N días con 0
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        daily[date] = 0
    
    # Contar actividad por día (de daily_connections)
    for user_data in stats_data.get('users', {}).values():
        connections = user_data.get('daily_connections', {})
        
        if isinstance(connections, dict):
            by_date = connections.get('by_date', {})
            
            for date_str, count in by_date.items():
                if date_str in daily:
                    daily[date_str] += count
    
    return daily


def find_common_games(stats_data: Dict, user_id1: str, user_id2: str) -> List[str]:
    """
    Encuentra juegos en común entre dos usuarios
    
    Args:
        stats_data: Datos completos de stats
        user_id1: ID del primer usuario
        user_id2: ID del segundo usuario
        
    Returns:
        Lista de nombres de juegos en común
    """
    users = stats_data.get('users', {})
    
    user1_data = users.get(user_id1, {})
    user2_data = users.get(user_id2, {})
    
    games1 = set(user1_data.get('games', {}).keys())
    games2 = set(user2_data.get('games', {}).keys())
    
    return list(games1 & games2)


def calculate_total_server_time(stats_data: Dict) -> Tuple[int, int, int]:
    """
    Calcula el tiempo total del servidor
    
    Args:
        stats_data: Datos completos de stats
        
    Returns:
        Tupla (game_minutes, voice_minutes, total_minutes)
    """
    total_game_minutes = 0
    total_voice_minutes = 0
    
    for user_data in stats_data.get('users', {}).values():
        # Sumar juegos
        games = user_data.get('games', {})
        total_game_minutes += sum(g.get('total_minutes', 0) for g in games.values())
        
        # Sumar voz
        voice = user_data.get('voice', {})
        total_voice_minutes += voice.get('total_minutes', 0)
    
    total_minutes = total_game_minutes + total_voice_minutes
    
    return total_game_minutes, total_voice_minutes, total_minutes


def get_game_stats_detailed(stats_data: Dict, game_name: str) -> Dict:
    """
    Obtiene estadísticas detalladas de un juego
    
    Args:
        stats_data: Datos completos de stats
        game_name: Nombre del juego
        
    Returns:
        Dict con estadísticas detalladas del juego
    """
    result = {
        'total_minutes': 0,
        'total_sessions': 0,
        'unique_players': 0,
        'player_list': [],
        'top_players': [],
        'first_played': None,
        'last_played': None,
        'parties': 0  # TODO: Implementar cuando tengamos stats de parties
    }
    
    players = []
    all_dates = []
    
    for user_data in stats_data.get('users', {}).values():
        username = user_data.get('username', 'Unknown')
        games = user_data.get('games', {})
        
        if game_name in games:
            game_data = games[game_name]
            
            minutes = game_data.get('total_minutes', 0)
            count = game_data.get('count', 0)
            
            result['total_minutes'] += minutes
            result['total_sessions'] += count
            
            players.append((username, minutes, count))
            
            # Fechas
            if game_data.get('first_played'):
                all_dates.append(game_data['first_played'])
            if game_data.get('last_played'):
                all_dates.append(game_data['last_played'])
    
    # Top players
    players.sort(key=lambda x: x[1], reverse=True)
    result['top_players'] = players[:10]
    result['unique_players'] = len(players)
    result['player_list'] = [p[0] for p in players]
    
    # Fechas
    if all_dates:
        all_dates.sort()
        result['first_played'] = all_dates[0]
        result['last_played'] = all_dates[-1]
    
    return result

