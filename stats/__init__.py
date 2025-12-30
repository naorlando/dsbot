"""
Módulo de Estadísticas - Refactorizado
Contiene todos los comandos y visualizaciones de estadísticas del bot
"""

# Importar setup functions de todos los comandos
from .commands.rankings import setup_ranking_commands
from .commands.games import setup_game_commands
from .commands.parties import setup_party_commands
from .commands.user import setup_user_commands
from .commands.social import setup_social_commands
from .commands.utils import setup_utils_commands

# Importar funciones de visualización para uso externo
from .visualization import *
from .data import *

__all__ = [
    # Setup functions para comandos
    'setup_ranking_commands',
    'setup_game_commands',
    'setup_party_commands',
    'setup_user_commands',
    'setup_social_commands',
    'setup_utils_commands',
]
