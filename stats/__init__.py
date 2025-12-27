"""
Módulo de Estadísticas
Organización modular de todas las funcionalidades de stats del bot
"""

# Embeds
from stats.embeds import (
    create_overview_embed,
    create_games_ranking_embed,
    create_voice_ranking_embed,
    create_users_ranking_embed,
    create_messages_ranking_embed,
    create_timeline_embed
)

# UI Components
from stats.ui_components import (
    StatsView,
    StatsSelect,
    PeriodSelect
)

# Commands Setup Functions
from stats.commands_basic import setup_basic_commands
from stats.commands_advanced import setup_advanced_commands
from stats.commands_voice import setup_voice_commands

__all__ = [
    # Embeds
    'create_overview_embed',
    'create_games_ranking_embed',
    'create_voice_ranking_embed',
    'create_users_ranking_embed',
    'create_messages_ranking_embed',
    'create_timeline_embed',
    # UI Components
    'StatsView',
    'StatsSelect',
    'PeriodSelect',
    # Setup Functions
    'setup_basic_commands',
    'setup_advanced_commands',
    'setup_voice_commands',
]

