"""
Comandos Sociales
!topreactions, !topstickers, !compare
"""

import discord
from discord.ext import commands
import json

from core.persistence import STATS_FILE
from core.checks import stats_channel_only
from ..visualization import (
    create_bar_chart,
    format_large_number
)
from ..embeds import create_connections_ranking_embed
from stats_viz import get_period_label


def setup_social_commands(bot):
    """Registra los comandos sociales"""
    
    @bot.command(name='topreactions', aliases=['reactions'])
    async def topreactions_command(ctx):
        """
        😄 Top usuarios por reacciones enviadas
        
        Uso: !topreactions
        """
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
            count = reactions.get('total', 0) or reactions.get('count', 0)
            
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
            count = stickers.get('total', 0) or stickers.get('count', 0)
            
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

    @bot.command(name='topconnections', aliases=['conexiones'])
    @stats_channel_only()
    async def topconnections_command(ctx, timeframe: str = 'week'):
        """
        📱 Ranking de conexiones diarias (offline → online)

        Uso: !topconnections [today|week|month|all]
        """
        tf = timeframe.lower().strip()
        valid = ('today', 'week', 'month', 'all')
        if tf not in valid:
            await ctx.send(f"❌ Período inválido. Usa: {', '.join(valid)}")
            return
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
        except Exception as e:
            await ctx.send(f"❌ Error al cargar estadísticas: {e}")
            return
        label = get_period_label(tf)
        embed = await create_connections_ranking_embed(stats_data, label, timeframe=tf)
        await ctx.send(embed=embed)

