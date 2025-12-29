"""
Módulo de Datos
Exporta agregadores y filtros
"""

from .aggregators import (
    aggregate_game_stats,
    aggregate_voice_stats,
    aggregate_game_time_by_user,
    aggregate_party_stats,
    aggregate_message_stats,
    get_top_players_for_game,
    calculate_daily_activity,
    find_common_games,
    calculate_total_server_time,
    get_game_stats_detailed
)

from .filters import (
    filter_by_period,
    filter_by_game,
    filter_by_user,
    filter_active_users
)

__all__ = [
    # Aggregators
    'aggregate_game_stats',
    'aggregate_voice_stats',
    'aggregate_game_time_by_user',
    'aggregate_party_stats',
    'aggregate_message_stats',
    'get_top_players_for_game',
    'calculate_daily_activity',
    'find_common_games',
    'calculate_total_server_time',
    'get_game_stats_detailed',
    # Filters
    'filter_by_period',
    'filter_by_game',
    'filter_by_user',
    'filter_active_users'
]

