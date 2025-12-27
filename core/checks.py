"""
Módulo de validaciones y checks
Maneja verificaciones de permisos y canal
"""

import os
import logging
from core.persistence import get_stats_channel_id

logger = logging.getLogger('dsbot')


def is_owner(ctx):
    """
    Verifica si el usuario es owner del bot (por ID de Discord).
    El/los owner(s) se configuran con la variable de entorno DISCORD_OWNER_ID.
    
    Soporta múltiples owners separados por comas:
    DISCORD_OWNER_ID=123456789012345678,987654321098765432
    """
    owner_ids_str = os.getenv('DISCORD_OWNER_ID')
    
    if not owner_ids_str:
        logger.warning('⚠️  DISCORD_OWNER_ID no configurado - comandos de owner deshabilitados')
        return False
    
    # Separar por comas y limpiar espacios
    owner_ids = [id.strip() for id in owner_ids_str.split(',')]
    
    return str(ctx.author.id) in owner_ids


async def check_stats_channel(ctx, bot):
    """
    Verifica si el comando de stats se ejecuta en el canal correcto.
    Retorna True si puede continuar, False si debe abortar.
    """
    stats_channel_id = get_stats_channel_id()
    
    # Si no hay canal de stats configurado, permitir en cualquier canal
    if not stats_channel_id:
        return True
    
    # Si estamos en el canal correcto, continuar
    if ctx.channel.id == stats_channel_id:
        return True
    
    # Si no estamos en el canal correcto, redirigir
    stats_channel = bot.get_channel(stats_channel_id)
    if stats_channel:
        await ctx.send(f'📊 Los comandos de estadísticas solo funcionan en {stats_channel.mention}\n💡 Usa `!channels` para ver la configuración actual.')
    else:
        await ctx.send(f'⚠️ El canal de estadísticas configurado no existe (ID: {stats_channel_id})\n💡 Usa `!unsetstatschannel` para desconfigurar o `!setstatschannel` para cambiar.')
    
    return False

