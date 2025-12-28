"""
Módulo de validaciones y checks
Maneja verificaciones de permisos y canal
"""

import os
import logging
from discord.ext import commands
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


def stats_channel_only():
    """
    Decorador que verifica que el comando se ejecute en el canal de stats.
    Si no está en el canal correcto, muestra mensaje de redirección y aborta.
    
    Uso:
        @bot.command(name='stats')
        @stats_channel_only()
        async def show_stats(ctx, ...):
            ...
    """
    async def predicate(ctx):
        stats_channel_id = get_stats_channel_id()
        
        # Si no hay canal configurado, permitir en cualquier canal
        if not stats_channel_id:
            return True
        
        # Si estamos en el canal correcto, continuar
        if ctx.channel.id == stats_channel_id:
            return True
        
        # Si no estamos en el canal correcto, mostrar mensaje y abortar
        stats_channel = ctx.bot.get_channel(stats_channel_id)
        
        if stats_channel:
            message = f'{ctx.author.mention} 📊 Los comandos de estadísticas solo funcionan en {stats_channel.mention}\n💡 Usa `!channels` para ver la configuración actual.'
        else:
            message = f'{ctx.author.mention} ⚠️ El canal de estadísticas configurado no existe (ID: {stats_channel_id})\n💡 Usa `!unsetstatschannel` para desconfigurar.'
        
        # Enviar mensaje que se autodestruye rápido (5s)
        # Nota: En comandos de mensaje tradicionales no hay forma nativa de hacer mensajes
        # "ephemeral" (solo visibles para el autor). Este mensaje es visible para todos pero
        # se borra rápido para minimizar spam.
        await ctx.send(message, delete_after=5)
        
        return False
    
    return commands.check(predicate)


async def check_stats_channel(ctx, bot):
    """
    Función helper para verificar canal de stats (mantenida para compatibilidad).
    Retorna True si puede continuar, False si debe abortar.
    
    DEPRECATED: Usar el decorador @stats_channel_only() en su lugar.
    """
    stats_channel_id = get_stats_channel_id()
    
    if not stats_channel_id:
        return True
    
    if ctx.channel.id == stats_channel_id:
        return True
    
    # Mostrar mensaje de redirección
    stats_channel = bot.get_channel(stats_channel_id)
    if stats_channel:
        await ctx.send(
            f'{ctx.author.mention} 📊 Los comandos de estadísticas solo funcionan en {stats_channel.mention}',
            delete_after=5
        )
    else:
        await ctx.send(
            f'{ctx.author.mention} ⚠️ Canal de stats no existe (ID: {stats_channel_id})',
            delete_after=5
        )
    
    return False

