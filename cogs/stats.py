"""
Cog de Estadísticas - Refactorizado
Carga todos los comandos relacionados con estadísticas del bot
"""

from discord.ext import commands
import logging
from stats import (
    setup_ranking_commands,
    setup_game_commands,
    setup_party_commands,
    setup_user_commands,
    setup_social_commands
)

logger = logging.getLogger('dsbot')


class StatsCog(commands.Cog, name='Estadísticas'):
    """Cog para manejar todos los comandos de estadísticas"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("StatsCog inicializado")
    
    async def cog_load(self):
        """Se ejecuta cuando el cog se carga"""
        logger.info("🔄 Cargando comandos de estadísticas refactorizados...")
        
        # Cargar comandos de rankings
        setup_ranking_commands(self.bot)
        logger.info("✓ Rankings cargados (topgamers, topvoice, topchat)")
        
        # Cargar comandos de juegos
        setup_game_commands(self.bot)
        logger.info("✓ Juegos cargados (topgames, topgame, mygames)")
        
        # Cargar comandos de parties
        setup_party_commands(self.bot)
        logger.info("✓ Parties cargados (partymaster, partywith, partygames)")
        
        # Cargar comandos de usuario
        setup_user_commands(self.bot)
        logger.info("✓ Usuario cargados (stats, mystats, compare)")
        
        # Cargar comandos sociales
        setup_social_commands(self.bot)
        logger.info("✓ Sociales cargados (topreactions, topstickers)")
        
        logger.info("📊 Todos los comandos de estadísticas cargados exitosamente")
    
    async def cog_unload(self):
        """Se ejecuta cuando el cog se descarga"""
        logger.info("StatsCog descargado")


async def setup(bot: commands.Bot):
    """Función requerida por discord.py para cargar el cog"""
    await bot.add_cog(StatsCog(bot))

