"""
Discord Activity Bot - Main Entry Point
Bot simplificado usando sistema de Cogs para modularidad
"""

import discord
from discord.ext import commands
import logging
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('dsbot')

# Inicializar config y stats ANTES de crear el bot
from core.persistence import config, stats, DATA_DIR

logger.info(f'✅ Canal configurado: {config.get("channel_id")}')
logger.info(f'📁 Directorio de datos: {DATA_DIR}')
logger.info(f'📊 Usuarios registrados: {len(stats.get("users", {}))}')

# Configurar intents necesarios
intents = discord.Intents.default()
intents.presences = True
intents.members = True
intents.message_content = True

# Crear bot
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)


async def load_extensions():
    """Carga todos los cogs del bot"""
    cogs = [
        'cogs.events',
        'cogs.config',
        'cogs.stats',
        'cogs.utility',
    ]
    if os.getenv('ENABLE_WRAPPED_SCHEDULER', 'false').lower() == 'true':
        cogs.append('cogs.wrapped_event')
        logger.info('🎁 ENABLE_WRAPPED_SCHEDULER: cargando cogs.wrapped_event')
    
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logger.info(f'✅ Cog cargado: {cog}')
        except Exception as e:
            logger.error(f'❌ Error cargando {cog}: {e}')


@bot.event
async def setup_hook():
    """Hook para cargar extensiones antes de que el bot se conecte"""
    await load_extensions()


# Obtener token y ejecutar bot
token = os.getenv('DISCORD_BOT_TOKEN')
if not token:
    logger.error('❌ ERROR: No se encontró DISCORD_BOT_TOKEN en las variables de entorno')
    logger.error('Por favor, crea un archivo .env con:')
    logger.error('DISCORD_BOT_TOKEN=tu_token_aqui')
    exit(1)

try:
    bot.run(token, reconnect=True, log_handler=None)
except discord.errors.PrivilegedIntentsRequired:
    logger.error('❌ ERROR: Privileged Gateway Intents no habilitados')
    logger.error('Habilita "Presence Intent" y "Server Members Intent" en:')
    logger.error('https://discord.com/developers/applications')
    logger.error('Bot Settings > Privileged Gateway Intents')
except discord.errors.LoginFailure:
    logger.error('❌ ERROR: Token inválido')
    logger.error('Verifica que DISCORD_BOT_TOKEN sea correcto')
except Exception as e:
    logger.error(f'❌ ERROR inesperado: {e}')

