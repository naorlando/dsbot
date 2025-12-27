"""
Módulo de Comandos Avanzados de Estadísticas
Comandos complejos e interactivos: statsmenu, statsgames, statsvoice, timeline, compare, statsuser, export
"""

import discord
from discord.ext import commands
from datetime import datetime
import json
import os
from core.persistence import stats, DATA_DIR
from core.checks import check_stats_channel
from stats_viz import (
    filter_by_period, get_period_label, create_comparison_chart, 
    create_user_detail_view
)
from stats.embeds import (
    create_overview_embed, create_games_ranking_embed, 
    create_voice_ranking_embed, create_timeline_embed
)
from stats.ui_components import StatsView
import logging

logger = logging.getLogger('dsbot')


async def setup_advanced_commands(bot: commands.Bot):
    """Registra los comandos avanzados de stats"""
    
    @bot.command(name='statsmenu', aliases=['statsinteractive'])
    async def stats_menu(ctx):
        """
        Abre el menú interactivo de estadísticas
        
        Ejemplo: !statsmenu
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx):
            return
        
        view = StatsView(period='all')
        filtered_stats = filter_by_period(stats, 'all')
        embed = await create_overview_embed(filtered_stats, 'Histórico')
        
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @bot.command(name='statsgames')
    async def stats_games_cmd(ctx, period: str = 'all'):
        """
        Muestra ranking de juegos con gráfico
        
        Ejemplos:
        - !statsgames
        - !statsgames today
        - !statsgames week
        - !statsgames month
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx):
            return
        
        if period not in ['today', 'week', 'month', 'all']:
            await ctx.send('❌ Período inválido. Usa: `today`, `week`, `month`, `all`')
            return
        
        filtered_stats = filter_by_period(stats, period)
        period_label = get_period_label(period)
        embed = await create_games_ranking_embed(filtered_stats, period_label)
        
        await ctx.send(embed=embed)

    @bot.command(name='statsvoice')
    async def stats_voice_cmd(ctx, period: str = 'all'):
        """
        Muestra ranking de actividad de voz con gráfico
        
        Ejemplos:
        - !statsvoice
        - !statsvoice today
        - !statsvoice week
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx):
            return
        
        if period not in ['today', 'week', 'month', 'all']:
            await ctx.send('❌ Período inválido. Usa: `today`, `week`, `month`, `all`')
            return
        
        filtered_stats = filter_by_period(stats, period)
        period_label = get_period_label(period)
        embed = await create_voice_ranking_embed(filtered_stats, period_label)
        
        await ctx.send(embed=embed)

    @bot.command(name='timeline')
    async def timeline_cmd(ctx, days: int = 7):
        """
        Muestra línea de tiempo de actividad
        
        Ejemplos:
        - !timeline
        - !timeline 14
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx):
            return
        
        if days < 1 or days > 30:
            await ctx.send('❌ Días debe estar entre 1 y 30')
            return
        
        embed = await create_timeline_embed(stats, f'Últimos {days} días')
        await ctx.send(embed=embed)

    @bot.command(name='compare')
    async def compare_users_cmd(ctx, user1: discord.Member, user2: discord.Member):
        """
        Compara estadísticas entre dos usuarios
        
        Ejemplo: !compare @usuario1 @usuario2
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx):
            return
        
        user1_id = str(user1.id)
        user2_id = str(user2.id)
        
        user1_data = stats.get('users', {}).get(user1_id, {})
        user2_data = stats.get('users', {}).get(user2_id, {})
        
        if not user1_data:
            await ctx.send(f'❌ {user1.display_name} no tiene estadísticas registradas.')
            return
        
        if not user2_data:
            await ctx.send(f'❌ {user2.display_name} no tiene estadísticas registradas.')
            return
        
        comparison = create_comparison_chart(user1_data, user2_data, user1.display_name, user2.display_name)
        
        embed = discord.Embed(description=comparison, color=discord.Color.gold())
        await ctx.send(embed=embed)

    @bot.command(name='statsuser')
    async def stats_user_detail(ctx, member: discord.Member = None):
        """
        Muestra estadísticas detalladas de un usuario
        
        Ejemplos:
        - !statsuser
        - !statsuser @usuario
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx):
            return
        
        if member is None:
            member = ctx.author
        
        user_id = str(member.id)
        user_data = stats.get('users', {}).get(user_id, {})
        
        if not user_data:
            await ctx.send(f'📊 {member.display_name} no tiene estadísticas registradas.')
            return
        
        embed = create_user_detail_view(user_data, member.display_name)
        await ctx.send(embed=embed)

    @bot.command(name='export')
    async def export_stats(ctx, format: str = 'json'):
        """
        Exporta las estadísticas a un archivo
        
        Formatos disponibles: json, csv
        
        Ejemplos:
        - !export
        - !export json
        - !export csv
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx):
            return
        
        if format not in ['json', 'csv']:
            await ctx.send('❌ Formato inválido. Usa: `json` o `csv`')
            return
        
        try:
            if format == 'json':
                # Exportar como JSON
                filename = f'stats_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                filepath = DATA_DIR / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(stats, f, indent=2, ensure_ascii=False)
                
                await ctx.send(
                    f'📊 Estadísticas exportadas a JSON',
                    file=discord.File(filepath, filename=filename)
                )
                
                # Limpiar archivo temporal
                os.remove(filepath)
            
            elif format == 'csv':
                # Exportar como CSV
                import csv
                filename = f'stats_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                filepath = DATA_DIR / filename
                
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    
                    # Header
                    writer.writerow(['Usuario', 'Juego/Actividad', 'Tipo', 'Count', 'Última Actividad'])
                    
                    # Datos
                    for user_id, user_data in stats.get('users', {}).items():
                        username = user_data.get('username', 'Unknown')
                        
                        # Juegos
                        for game, game_data in user_data.get('games', {}).items():
                            writer.writerow([
                                username,
                                game,
                                'Juego',
                                game_data.get('count', 0),
                                game_data.get('last_played', '')
                            ])
                        
                        # Voz
                        voice = user_data.get('voice', {})
                        if voice.get('count', 0) > 0:
                            writer.writerow([
                                username,
                                'Actividad de Voz',
                                'Voz',
                                voice.get('count', 0),
                                voice.get('last_join', '')
                            ])
                
                await ctx.send(
                    f'📊 Estadísticas exportadas a CSV',
                    file=discord.File(filepath, filename=filename)
                )
                
                # Limpiar archivo temporal
                os.remove(filepath)
            
            logger.info(f'Stats exportadas por {ctx.author.display_name} en formato {format}')
        
        except Exception as e:
            logger.error(f'Error al exportar stats: {e}')
            await ctx.send(f'❌ Error al exportar: {str(e)}')

