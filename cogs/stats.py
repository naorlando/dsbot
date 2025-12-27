"""
Cog de Estadísticas
Carga todos los comandos relacionados con estadísticas del bot
"""

from discord.ext import commands
import logging
from stats import (
    setup_basic_commands,
    setup_advanced_commands,
    setup_voice_commands
)

logger = logging.getLogger('dsbot')


class StatsCog(commands.Cog, name='Estadísticas'):
    """Cog para manejar todos los comandos de estadísticas"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("StatsCog inicializado")
    
    async def cog_load(self):
        """Se ejecuta cuando el cog se carga"""
        logger.info("Cargando comandos de estadísticas...")
        
        # Cargar comandos básicos
        await setup_basic_commands(self.bot)
        logger.info("✓ Comandos básicos cargados (stats, topgames, topmessages, etc.)")
        
        # Cargar comandos avanzados
        await setup_advanced_commands(self.bot)
        logger.info("✓ Comandos avanzados cargados (statsmenu, timeline, compare, export, etc.)")
        
        # Cargar comandos de voz
        await setup_voice_commands(self.bot)
        logger.info("✓ Comandos de voz cargados (voicetime, voicetop)")
        
        logger.info("📊 Todos los comandos de estadísticas cargados exitosamente")
    
    async def cog_unload(self):
        """Se ejecuta cuando el cog se descarga"""
        logger.info("StatsCog descargado")


async def setup(bot: commands.Bot):
    """Función requerida por discord.py para cargar el cog"""
    await bot.add_cog(StatsCog(bot))

