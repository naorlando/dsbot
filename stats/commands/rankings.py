"""
Comandos de Rankings
!topgamers, !topvoice, !topchat
"""

import discord
from discord.ext import commands
from typing import Optional
import json

from core.persistence import STATS_FILE
from ..visualization import (
    create_ranking_visual,
    format_time,
    format_large_number,
    get_period_label
)
from ..data import (
    aggregate_game_time_by_user,
    aggregate_voice_stats,
    aggregate_message_stats,
    filter_by_period
)


def setup_ranking_commands(bot):
    """Registra los comandos de rankings"""
    
    @bot.command(name='topgamers', aliases=['topgaming', 'gamers'])
    async def topgamers_command(ctx, period: str = 'all'):
        """
        🎮 Top jugadores por tiempo de juego
        
        Uso: !topgamers [period]
        Períodos: today, week, month, all
        
        Ejemplo: !topgamers week
        """
        # Validar período
        valid_periods = ['today', 'week', 'month', 'all']
        if period not in valid_periods:
            await ctx.send(f"❌ Período inválido. Usa: {', '.join(valid_periods)}")
            return
        
        # Cargar stats
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
        except Exception as e:
            await ctx.send(f"❌ Error al cargar estadísticas: {e}")
            return
        
        # Filtrar por período
        if period != 'all':
            stats_data = filter_by_period(stats_data, period)
        
        # Agregar datos
        user_stats = aggregate_game_time_by_user(stats_data)
        
        if not user_stats:
            await ctx.send(f"📊 No hay datos de juegos para el período: {get_period_label(period)}")
            return
        
        # Preparar datos para el gráfico
        top_10 = user_stats[:10]
        data_tuples = []
        
        for username, minutes, sessions, unique_games in top_10:
            extra_info = f"{sessions} sesiones • {unique_games} juegos"
            data_tuples.append((username, minutes, extra_info))
        
        # Crear gráfico
        title = f"🎮 TOP GAMERS - {get_period_label(period).upper()}"
        chart = create_ranking_visual(data_tuples, title, max_display=10, value_formatter=format_time)
        
        # Enviar
        try:
            await ctx.send(f"```{chart}```")
        except discord.HTTPException:
            # Fallback si el mensaje es muy largo
            await ctx.send(f"📊 **{title}**\n\n" + "\n".join([
                f"{i+1}. **{name}** - {format_time(mins)} ({extra})"
                for i, (name, mins, extra) in enumerate(data_tuples)
            ]))
    
    
    @bot.command(name='topvoice', aliases=['topvoz', 'voice'])
    async def topvoice_command(ctx, period: str = 'all'):
        """
        🔊 Top usuarios por tiempo en voz
        
        Uso: !topvoice [period]
        Períodos: today, week, month, all
        
        Ejemplo: !topvoice month
        """
        # Validar período
        valid_periods = ['today', 'week', 'month', 'all']
        if period not in valid_periods:
            await ctx.send(f"❌ Período inválido. Usa: {', '.join(valid_periods)}")
            return
        
        # Cargar stats
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
        except Exception as e:
            await ctx.send(f"❌ Error al cargar estadísticas: {e}")
            return
        
        # Filtrar por período
        if period != 'all':
            stats_data = filter_by_period(stats_data, period)
        
        # Agregar datos
        voice_stats = aggregate_voice_stats(stats_data)
        
        if not voice_stats:
            await ctx.send(f"📊 No hay datos de voz para el período: {get_period_label(period)}")
            return
        
        # Preparar datos para el gráfico
        top_10 = voice_stats[:10]
        data_tuples = []
        
        for username, minutes, count in top_10:
            extra_info = f"{count} sesiones"
            data_tuples.append((username, minutes, extra_info))
        
        # Crear gráfico
        title = f"🔊 TOP VOZ - {get_period_label(period).upper()}"
        chart = create_ranking_visual(data_tuples, title, max_display=10, value_formatter=format_time)
        
        # Enviar
        try:
            await ctx.send(f"```{chart}```")
        except discord.HTTPException:
            # Fallback
            await ctx.send(f"📊 **{title}**\n\n" + "\n".join([
                f"{i+1}. **{name}** - {format_time(mins)} ({extra})"
                for i, (name, mins, extra) in enumerate(data_tuples)
            ]))
    
    
    @bot.command(name='topchat', aliases=['topmessages', 'chatters'])
    async def topchat_command(ctx):
        """
        💬 Top usuarios por mensajes enviados
        
        Uso: !topchat
        
        Muestra los usuarios más activos en chat
        """
        # Cargar stats
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
        except Exception as e:
            await ctx.send(f"❌ Error al cargar estadísticas: {e}")
            return
        
        # Agregar datos
        message_stats = aggregate_message_stats(stats_data)
        
        if not message_stats:
            await ctx.send("📊 No hay datos de mensajes")
            return
        
        # Preparar datos para el gráfico
        top_10 = message_stats[:10]
        data_tuples = []
        
        for username, count, characters in top_10:
            avg_chars = int(characters / count) if count > 0 else 0
            extra_info = f"Promedio: {avg_chars} caracteres/msg"
            data_tuples.append((username, count, extra_info))
        
        # Crear gráfico
        title = "💬 TOP CHAT - MENSAJES ENVIADOS"
        # Formatter para mensajes: agregar "msgs"
        msg_formatter = lambda x: f"{x:,} msgs"
        chart = create_ranking_visual(data_tuples, title, max_display=10, value_formatter=msg_formatter)
        
        # Enviar
        try:
            await ctx.send(f"```{chart}```")
        except discord.HTTPException:
            # Fallback
            await ctx.send(f"📊 **{title}**\n\n" + "\n".join([
                f"{i+1}. **{name}** - {format_large_number(count)} mensajes ({extra})"
                for i, (name, count, extra) in enumerate(data_tuples)
            ]))
    
    
    @bot.command(name='topusers')
    async def topusers_deprecated(ctx):
        """
        ⚠️ Comando deprecado
        
        Este comando ha sido reemplazado por comandos más específicos:
        • !topgamers - Ranking por tiempo de juego
        • !topvoice - Ranking por tiempo en voz
        • !topchat - Ranking por mensajes
        """
        embed = discord.Embed(
            title="⚠️ Comando Deprecado",
            description=(
                "El comando `!topusers` ya no está disponible.\n\n"
                "**Usa estos comandos más específicos:**\n"
                "• `!topgamers [period]` - Top jugadores por tiempo\n"
                "• `!topvoice [period]` - Top usuarios en voz\n"
                "• `!topchat` - Top usuarios por mensajes\n\n"
                "**Períodos disponibles:** today, week, month, all"
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text="💡 Estos comandos ofrecen rankings más detallados y precisos")
        await ctx.send(embed=embed)

