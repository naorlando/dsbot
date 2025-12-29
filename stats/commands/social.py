"""
Comandos Sociales
!topreactions, !topstickers, !compare
"""

import discord
from discord.ext import commands
import json

from core.persistence import STATS_FILE
from ..visualization import (
    create_bar_chart,
    format_large_number
)


def setup_social_commands(bot):
    """Registra los comandos sociales"""
    
    @bot.command(name='topreactions', aliases=['reactions'])
    async def topreactions_command(ctx):
        """
        😄 Top usuarios por reacciones enviadas
        
        Uso: !topreactions
        """
        await ctx.send("⏳ Contando reacciones...")
        
        # Cargar stats
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
        except Exception as e:
            await ctx.send(f"❌ Error al cargar estadísticas: {e}")
            return
        
        # Agregar datos
        reaction_stats = []
        
        for user_id, user_data in stats_data.get('users', {}).items():
            username = user_data.get('username', 'Unknown')
            reactions = user_data.get('reactions', {})
            count = reactions.get('count', 0)
            
            if count > 0:
                reaction_stats.append((username, count))
        
        if not reaction_stats:
            await ctx.send("📊 No hay datos de reacciones")
            return
        
        # Ordenar
        reaction_stats.sort(key=lambda x: x[1], reverse=True)
        
        # Crear gráfico
        chart = create_bar_chart(
            reaction_stats[:10],
            max_width=25,
            title="😄 TOP REACCIONES",
            show_percentage=True,
            style="gradient"
        )
        
        await ctx.send(f"```{chart}```")
    
    
    @bot.command(name='topstickers', aliases=['stickers'])
    async def topstickers_command(ctx):
        """
        🎨 Top usuarios por stickers enviados
        
        Uso: !topstickers
        """
        await ctx.send("⏳ Contando stickers...")
        
        # Cargar stats
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
        except Exception as e:
            await ctx.send(f"❌ Error al cargar estadísticas: {e}")
            return
        
        # Agregar datos
        sticker_stats = []
        
        for user_id, user_data in stats_data.get('users', {}).items():
            username = user_data.get('username', 'Unknown')
            stickers = user_data.get('stickers', {})
            count = stickers.get('count', 0)
            
            if count > 0:
                sticker_stats.append((username, count))
        
        if not sticker_stats:
            await ctx.send("📊 No hay datos de stickers")
            return
        
        # Ordenar
        sticker_stats.sort(key=lambda x: x[1], reverse=True)
        
        # Crear gráfico
        chart = create_bar_chart(
            sticker_stats[:10],
            max_width=25,
            title="🎨 TOP STICKERS",
            show_percentage=True,
            style="gradient"
        )
        
        await ctx.send(f"```{chart}```")

