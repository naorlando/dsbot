"""
Comandos de Juegos
!topgames, !topgame
"""

import discord
from discord.ext import commands
import json

from core.persistence import STATS_FILE
from ..visualization import (
    create_bar_chart,
    create_ranking_visual,
    format_time,
    format_list_with_commas,
    format_date
)
from ..data import (
    aggregate_game_stats,
    get_top_players_for_game,
    get_game_stats_detailed
)


def setup_game_commands(bot):
    """Registra los comandos de juegos"""
    
    @bot.command(name='topgames', aliases=['populargames', 'games'])
    async def topgames_command(ctx, sort_by: str = 'time'):
        """
        🎮 Top juegos más jugados
        
        Uso: !topgames [sort_by]
        Sort options:
        - time: Por tiempo total jugado (default)
        - players: Por cantidad de jugadores
        - sessions: Por número de sesiones
        
        Ejemplo: !topgames players
        """
        await ctx.send("⏳ Calculando juegos más populares...")
        
        # Validar sort_by
        valid_sorts = ['time', 'players', 'sessions']
        if sort_by not in valid_sorts:
            await ctx.send(f"❌ Orden inválido. Usa: {', '.join(valid_sorts)}")
            return
        
        # Cargar stats
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
        except Exception as e:
            await ctx.send(f"❌ Error al cargar estadísticas: {e}")
            return
        
        # Agregar datos
        game_stats = aggregate_game_stats(stats_data)
        
        if not game_stats:
            await ctx.send("📊 No hay datos de juegos")
            return
        
        # Ordenar según criterio
        if sort_by == 'time':
            sorted_games = sorted(game_stats.items(), key=lambda x: x[1]['minutes'], reverse=True)
            title = "🎮 TOP JUEGOS - POR TIEMPO JUGADO"
            value_key = 'minutes'
            format_func = format_time
        elif sort_by == 'players':
            sorted_games = sorted(game_stats.items(), key=lambda x: x[1]['player_count'], reverse=True)
            title = "🎮 TOP JUEGOS - POR CANTIDAD DE JUGADORES"
            value_key = 'player_count'
            format_func = lambda x: f"{x} jugadores"
        else:  # sessions
            sorted_games = sorted(game_stats.items(), key=lambda x: x[1]['count'], reverse=True)
            title = "🎮 TOP JUEGOS - POR NÚMERO DE SESIONES"
            value_key = 'count'
            format_func = lambda x: f"{x} sesiones"
        
        # Preparar datos para el gráfico
        top_15 = sorted_games[:15]
        data_for_chart = []
        
        for game_name, stats in top_15:
            value = stats[value_key]
            
            # Info extra según el criterio
            if sort_by == 'time':
                extra = f"{stats['count']} sesiones • {stats['player_count']} jugadores"
            elif sort_by == 'players':
                extra = f"{format_time(stats['minutes'])} • {stats['count']} sesiones"
            else:
                extra = f"{format_time(stats['minutes'])} • {stats['player_count']} jugadores"
            
            data_for_chart.append((game_name, value, extra))
        
        # Crear gráfico
        chart = create_ranking_visual(data_for_chart, title, max_display=15)
        
        # Enviar
        try:
            await ctx.send(f"```{chart}```")
        except discord.HTTPException:
            # Fallback
            await ctx.send(f"📊 **{title}**\n\n" + "\n".join([
                f"{i+1}. **{name}** - {format_func(value)}\n    └─ {extra}"
                for i, (name, value, extra) in enumerate(data_for_chart)
            ]))
    
    
    @bot.command(name='topgame', aliases=['gamestats', 'gameinfo'])
    async def topgame_command(ctx, *, game_name: str = None):
        """
        📊 Estadísticas detalladas de un juego
        
        Uso: !topgame <nombre del juego>
        
        Muestra:
        - Tiempo total jugado
        - Número de jugadores
        - Top jugadores del juego
        - Fechas de actividad
        - (Próximamente) Parties formadas
        
        Ejemplo: !topgame Hades
        """
        if not game_name:
            await ctx.send("❌ Debes especificar el nombre del juego.\nEjemplo: `!topgame Hades`")
            return
        
        await ctx.send(f"⏳ Buscando estadísticas de **{game_name}**...")
        
        # Cargar stats
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
        except Exception as e:
            await ctx.send(f"❌ Error al cargar estadísticas: {e}")
            return
        
        # Obtener stats del juego
        game_stats = get_game_stats_detailed(stats_data, game_name)
        
        if game_stats['unique_players'] == 0:
            # Intentar búsqueda case-insensitive
            all_games = aggregate_game_stats(stats_data)
            game_lower = game_name.lower()
            matches = [g for g in all_games.keys() if game_lower in g.lower()]
            
            if matches:
                suggestions = format_list_with_commas(matches[:5], max_items=3)
                await ctx.send(
                    f"❌ No se encontró el juego **{game_name}**.\n\n"
                    f"💡 ¿Quisiste decir? {suggestions}\n\n"
                    f"Usa `!topgames` para ver todos los juegos."
                )
            else:
                await ctx.send(
                    f"❌ No se encontró el juego **{game_name}**.\n\n"
                    f"Usa `!topgames` para ver la lista de juegos disponibles."
                )
            return
        
        # Crear embed detallado
        embed = discord.Embed(
            title=f"🎮 {game_name}",
            description="Estadísticas Detalladas",
            color=discord.Color.blue()
        )
        
        # Stats generales
        total_time = format_time(game_stats['total_minutes'])
        embed.add_field(
            name="📊 Resumen",
            value=(
                f"⏱️ **Tiempo Total:** {total_time}\n"
                f"🎯 **Sesiones:** {game_stats['total_sessions']:,}\n"
                f"👥 **Jugadores:** {game_stats['unique_players']}\n"
            ),
            inline=False
        )
        
        # Fechas
        if game_stats['first_played']:
            first = format_date(game_stats['first_played'])
            last = format_date(game_stats['last_played'])
            embed.add_field(
                name="📅 Actividad",
                value=f"**Primera vez:** {first}\n**Última vez:** {last}",
                inline=False
            )
        
        # Top jugadores
        if game_stats['top_players']:
            top_5 = game_stats['top_players'][:5]
            players_text = "\n".join([
                f"{i+1}. **{name}** - {format_time(mins)} ({sessions} sesiones)"
                for i, (name, mins, sessions) in enumerate(top_5)
            ])
            embed.add_field(
                name="🏆 Top Jugadores",
                value=players_text,
                inline=False
            )
        
        # TODO: Agregar stats de parties cuando esté implementado
        # if game_stats['parties'] > 0:
        #     embed.add_field(
        #         name="👥 Parties",
        #         value=f"**Parties formadas:** {game_stats['parties']}",
        #         inline=False
        #     )
        
        embed.set_footer(text="💡 Usa !topgame <juego> para ver stats de otros juegos")
        
        await ctx.send(embed=embed)
    
    
    @bot.command(name='mygames', aliases=['misjuegos'])
    async def mygames_command(ctx):
        """
        🎮 Tus juegos más jugados
        
        Uso: !mygames
        
        Muestra tu top 10 de juegos por tiempo jugado
        """
        await ctx.send("⏳ Buscando tus juegos...")
        
        # Cargar stats
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
        except Exception as e:
            await ctx.send(f"❌ Error al cargar estadísticas: {e}")
            return
        
        # Buscar datos del usuario
        user_id = str(ctx.author.id)
        users = stats_data.get('users', {})
        
        if user_id not in users:
            await ctx.send("❌ No tienes estadísticas registradas aún.")
            return
        
        user_data = users[user_id]
        games = user_data.get('games', {})
        
        if not games:
            await ctx.send("📊 Aún no has jugado ningún juego.")
            return
        
        # Ordenar por tiempo
        sorted_games = sorted(
            games.items(),
            key=lambda x: x[1].get('total_minutes', 0),
            reverse=True
        )
        
        # Preparar datos
        top_10 = sorted_games[:10]
        data_for_chart = []
        
        for game_name, game_data in top_10:
            minutes = game_data.get('total_minutes', 0)
            sessions = game_data.get('count', 0)
            extra = f"{sessions} sesiones"
            data_for_chart.append((game_name, minutes, extra))
        
        # Crear gráfico
        title = f"🎮 TUS JUEGOS - {ctx.author.display_name.upper()}"
        chart = create_ranking_visual(data_for_chart, title, max_display=10)
        
        # Enviar
        try:
            await ctx.send(f"```{chart}```")
        except discord.HTTPException:
            # Fallback
            await ctx.send(f"📊 **{title}**\n\n" + "\n".join([
                f"{i+1}. **{name}** - {format_time(mins)} ({extra})"
                for i, (name, mins, extra) in enumerate(data_for_chart)
            ]))

