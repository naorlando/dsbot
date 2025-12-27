"""
Módulo de Embeds para Estadísticas
Funciones para crear todos los embeds de visualización de stats
"""

import discord
from typing import Dict
from datetime import datetime
from stats_viz import create_bar_chart, create_timeline_chart, calculate_daily_activity, format_time


async def create_overview_embed(filtered_stats: Dict, period_label: str) -> discord.Embed:
    """Crea embed con vista general de estadísticas"""
    embed = discord.Embed(
        title=f'📊 Vista General',
        description=f'› {period_label}',
        color=discord.Color.dark_teal()
    )
    
    users = filtered_stats.get('users', {})
    total_users = len(users)
    
    # Contar totales (con tiempo, mensajes, reacciones, stickers, conexiones)
    total_games = 0
    total_voice = 0
    total_game_minutes = 0
    total_voice_minutes = 0
    total_messages = 0
    total_characters = 0
    total_reactions = 0
    total_stickers = 0
    total_active_days = 0
    unique_games = set()
    unique_emojis = set()
    unique_stickers = set()
    
    for user_data in users.values():
        for game_name, game_data in user_data.get('games', {}).items():
            total_games += game_data.get('count', 0)
            total_game_minutes += game_data.get('total_minutes', 0)
            unique_games.add(game_name)
        
        voice_data = user_data.get('voice', {})
        total_voice += voice_data.get('count', 0)
        total_voice_minutes += voice_data.get('total_minutes', 0)
        
        messages_data = user_data.get('messages', {})
        total_messages += messages_data.get('count', 0)
        total_characters += messages_data.get('characters', 0)
        
        reactions_data = user_data.get('reactions', {})
        total_reactions += reactions_data.get('total', 0)
        for emoji in reactions_data.get('by_emoji', {}).keys():
            unique_emojis.add(emoji)
        
        stickers_data = user_data.get('stickers', {})
        total_stickers += stickers_data.get('total', 0)
        for sticker in stickers_data.get('by_name', {}).keys():
            unique_stickers.add(sticker)
        
        daily_connections = user_data.get('daily_connections', {})
        total_active_days += len(daily_connections)
    
    # Resumen con TODAS las stats
    resumen_lines = [
        f'**Usuarios activos:** {total_users}',
        f'**Sesiones de juego:** {total_games} (⏱️ {format_time(total_game_minutes)})',
        f'**Juegos únicos:** {len(unique_games)}',
        f'**Entradas a voz:** {total_voice} (⏱️ {format_time(total_voice_minutes)})',
    ]
    
    if total_messages > 0:
        estimated_words = total_characters // 5
        resumen_lines.append(f'**Mensajes:** {total_messages:,} (~{estimated_words:,} palabras)')
    
    if total_reactions > 0:
        resumen_lines.append(f'**Reacciones:** {total_reactions:,} ({len(unique_emojis)} emojis)')
    
    if total_stickers > 0:
        resumen_lines.append(f'**Stickers:** {total_stickers:,} ({len(unique_stickers)} únicos)')
    
    if total_active_days > 0:
        resumen_lines.append(f'**Días activos:** {total_active_days} días totales')
    
    resumen_lines.append(f'**Tiempo total:** ⏱️ {format_time(total_game_minutes + total_voice_minutes)}')
    
    embed.add_field(
        name='📈 Resumen',
        value='\n'.join(resumen_lines),
        inline=False
    )
    
    # Top 3 juegos POR TIEMPO
    game_stats = {}
    for user_data in users.values():
        for game, data in user_data.get('games', {}).items():
            if game not in game_stats:
                game_stats[game] = {'count': 0, 'minutes': 0}
            game_stats[game]['count'] += data.get('count', 0)
            game_stats[game]['minutes'] += data.get('total_minutes', 0)
    
    if game_stats:
        # Ordenar por TIEMPO primero
        top_games = sorted(game_stats.items(), key=lambda x: x[1]['minutes'], reverse=True)[:3]
        games_text = '\n'.join([
            f'{i+1}. **{game}**: ⏱️ {format_time(data["minutes"])} ({data["count"]} sesiones)' 
            for i, (game, data) in enumerate(top_games)
        ])
        embed.add_field(name='🎮 Top 3 Juegos', value=games_text, inline=True)
    
    # Top 3 usuarios POR TIEMPO TOTAL (voz + juegos)
    user_activity = []
    for user_id, user_data in users.items():
        games_count = sum(g['count'] for g in user_data.get('games', {}).values())
        voice_count = user_data.get('voice', {}).get('count', 0)
        
        # Tiempo total = juegos + voz
        game_minutes = sum(g.get('total_minutes', 0) for g in user_data.get('games', {}).values())
        voice_minutes = user_data.get('voice', {}).get('total_minutes', 0)
        total_minutes = game_minutes + voice_minutes
        
        total_count = games_count + voice_count
        if total_count > 0:
            user_activity.append((
                user_data.get('username', 'Unknown'), 
                total_minutes,  # Ordenar por tiempo
                total_count
            ))
    
    if user_activity:
        # Ordenar por TIEMPO TOTAL
        top_users = sorted(user_activity, key=lambda x: x[1], reverse=True)[:3]
        users_text = []
        for i, (name, minutes, count) in enumerate(top_users):
            users_text.append(f'{i+1}. **{name}**: ⏱️ {format_time(minutes)} ({count} sesiones)')
        embed.add_field(name='👥 Top 3 Usuarios', value='\n'.join(users_text), inline=True)
    
    return embed


async def create_games_ranking_embed(filtered_stats: Dict, period_label: str) -> discord.Embed:
    """Crea embed con ranking de juegos y gráfico (ordenado por TIEMPO)"""
    embed = discord.Embed(
        title=f'🎮 Top Juegos',
        description=f'› {period_label}',
        color=discord.Color.dark_gold()
    )
    
    # Recopilar juegos con tiempo y sesiones
    game_stats = {}
    for user_data in filtered_stats.get('users', {}).values():
        for game, data in user_data.get('games', {}).items():
            if game not in game_stats:
                game_stats[game] = {'minutes': 0, 'count': 0}
            game_stats[game]['minutes'] += data.get('total_minutes', 0)
            game_stats[game]['count'] += data.get('count', 0)
    
    if not game_stats:
        embed.description = 'No hay juegos registrados en este período.'
        return embed
    
    # Ordenar por TIEMPO y tomar top 10
    top_games = sorted(game_stats.items(), key=lambda x: x[1]['minutes'], reverse=True)[:10]
    
    # Crear gráfico ASCII con TIEMPO (convertir a tuplas para el chart)
    chart_data = [(game, data['minutes']) for game, data in top_games]
    chart = create_bar_chart(chart_data, max_width=15)
    
    embed.description = f'```\n{chart}\n```'
    
    # Total con tiempo
    total_minutes = sum(data['minutes'] for data in game_stats.values())
    total_sessions = sum(data['count'] for data in game_stats.values())
    
    embed.add_field(
        name='📊 Total',
        value=(
            f'**{len(game_stats)}** juegos únicos\n'
            f'**{total_sessions}** sesiones\n'
            f'⏱️ **{format_time(total_minutes)}** jugados'
        ),
        inline=False
    )
    
    return embed


async def create_voice_ranking_embed(filtered_stats: Dict, period_label: str) -> discord.Embed:
    """Crea embed con ranking de actividad de voz (ordenado por TIEMPO)"""
    embed = discord.Embed(
        title=f'🎙️ Top Voz',
        description=f'› {period_label}',
        color=discord.Color.dark_purple()
    )
    
    # Recopilar actividad de voz CON TIEMPO
    voice_stats = []
    total_minutes = 0
    total_sessions = 0
    for user_data in filtered_stats.get('users', {}).values():
        username = user_data.get('username', 'Unknown')
        count = user_data.get('voice', {}).get('count', 0)
        minutes = user_data.get('voice', {}).get('total_minutes', 0)
        if count > 0:
            voice_stats.append((username, minutes, count))  # Ordenar por minutos
            total_minutes += minutes
            total_sessions += count
    
    if not voice_stats:
        embed.description = 'No hay actividad de voz registrada en este período.'
        return embed
    
    # Ordenar por TIEMPO y tomar top 8
    top_voice = sorted(voice_stats, key=lambda x: x[1], reverse=True)[:8]
    
    # Crear gráfico ASCII con TIEMPO
    chart_data = [(name, minutes) for name, minutes, _ in top_voice]
    chart = create_bar_chart(chart_data, max_width=15)
    
    embed.description = f'```\n{chart}\n```'
    
    embed.add_field(
        name='📊 Total',
        value=(
            f'**{len(voice_stats)}** usuarios activos\n'
            f'**{total_sessions}** sesiones\n'
            f'⏱️ **{format_time(total_minutes)}** en voz'
        ),
        inline=False
    )
    
    return embed


async def create_users_ranking_embed(filtered_stats: Dict, period_label: str) -> discord.Embed:
    """Crea embed con ranking de usuarios (ordenado por TIEMPO TOTAL)"""
    embed = discord.Embed(
        title=f'👥 Top Usuarios',
        description=f'› {period_label}',
        color=discord.Color.dark_green()
    )
    
    # Calcular actividad total por usuario CON TIEMPO Y MENSAJES
    user_activity = []
    for user_data in filtered_stats.get('users', {}).values():
        username = user_data.get('username', 'Unknown')
        games_count = sum(g['count'] for g in user_data.get('games', {}).values())
        voice_count = user_data.get('voice', {}).get('count', 0)
        messages_count = user_data.get('messages', {}).get('count', 0)
        
        # Tiempo total = juegos + voz
        game_minutes = sum(g.get('total_minutes', 0) for g in user_data.get('games', {}).values())
        voice_minutes = user_data.get('voice', {}).get('total_minutes', 0)
        total_minutes = game_minutes + voice_minutes
        total_sessions = games_count + voice_count
        
        if total_sessions > 0 or messages_count > 0:
            user_activity.append((username, total_minutes, total_sessions, games_count, voice_count, messages_count))
    
    if not user_activity:
        embed.description = 'No hay actividad registrada en este período.'
        return embed
    
    # Ordenar por TIEMPO TOTAL
    top_users = sorted(user_activity, key=lambda x: x[1], reverse=True)[:8]
    
    # Crear gráfico ASCII con TIEMPO
    chart_data = [(name, minutes) for name, minutes, _, _, _, _ in top_users]
    chart = create_bar_chart(chart_data, max_width=15)
    
    embed.description = f'```\n{chart}\n```'
    
    # Detalles (incluir mensajes si hay)
    details = []
    for i, (name, minutes, total, games, voice, messages) in enumerate(top_users[:5], 1):
        medal = ['🥇', '🥈', '🥉'][i-1] if i <= 3 else f'{i}.'
        detail_line = f'{medal} **{name}**: ⏱️ {format_time(minutes)} '
        detail_line += f'({total} sesiones: 🎮 {games} | 🔊 {voice}'
        if messages > 0:
            detail_line += f' | 💬 {messages:,}'
        detail_line += ')'
        details.append(detail_line)
    
    embed.add_field(name='📋 Detalle Top 5', value='\n'.join(details), inline=False)
    
    return embed


async def create_messages_ranking_embed(filtered_stats: Dict, period_label: str) -> discord.Embed:
    """Crea embed con ranking de mensajes"""
    embed = discord.Embed(
        title=f'💬 Top Mensajes',
        description=f'› {period_label}',
        color=discord.Color.dark_teal()
    )
    
    # Recopilar mensajes por usuario
    message_stats = []
    total_messages = 0
    total_chars = 0
    
    for user_data in filtered_stats.get('users', {}).values():
        username = user_data.get('username', 'Unknown')
        messages_data = user_data.get('messages', {})
        msg_count = messages_data.get('count', 0)
        msg_chars = messages_data.get('characters', 0)
        
        if msg_count > 0:
            message_stats.append((username, msg_count, msg_chars))
            total_messages += msg_count
            total_chars += msg_chars
    
    if not message_stats:
        embed.description = 'No hay mensajes registrados en este período.'
        return embed
    
    # Ordenar por cantidad de mensajes
    top_messages = sorted(message_stats, key=lambda x: x[1], reverse=True)[:8]
    
    # Crear gráfico ASCII
    chart_data = [(name, count) for name, count, _ in top_messages]
    chart = create_bar_chart(chart_data, max_width=15)
    
    embed.description = f'```\n{chart}\n```'
    
    # Detalles
    details = []
    for i, (name, count, chars) in enumerate(top_messages[:5], 1):
        medal = ['🥇', '🥈', '🥉'][i-1] if i <= 3 else f'{i}.'
        avg = chars // count if count > 0 else 0
        estimated_words = chars // 5
        details.append(
            f'{medal} **{name}**: {count:,} mensajes '
            f'({estimated_words:,} palabras, ~{avg} chars/msg)'
        )
    
    embed.add_field(name='📋 Detalle Top 5', value='\n'.join(details), inline=False)
    
    # Total
    estimated_total_words = total_chars // 5
    embed.add_field(
        name='📊 Total',
        value=(
            f'**{len(message_stats)}** usuarios activos\n'
            f'**{total_messages:,}** mensajes\n'
            f'**{estimated_total_words:,}** palabras aprox.'
        ),
        inline=False
    )
    
    return embed


async def create_timeline_embed(stats_data: Dict, period_label: str) -> discord.Embed:
    """Crea embed con línea de tiempo de actividad"""
    embed = discord.Embed(
        title=f'📈 Línea de Tiempo',
        description=f'› Actividad de los últimos 7 días',
        color=discord.Color.dark_orange()
    )
    
    # Calcular actividad diaria
    daily_activity = calculate_daily_activity(stats_data, days=7)
    
    # Crear gráfico
    chart = create_timeline_chart(daily_activity, days=7)
    
    embed.description = f'```\n{chart}\n```'
    
    # Resumen
    total = sum(daily_activity.values())
    avg = total / 7 if total > 0 else 0
    max_day = max(daily_activity.items(), key=lambda x: x[1])
    
    embed.add_field(
        name='📊 Resumen',
        value=(
            f'**Total 7 días:** {total} eventos\n'
            f'**Promedio diario:** {avg:.1f} eventos\n'
            f'**Día más activo:** {datetime.strptime(max_day[0], "%Y-%m-%d").strftime("%d/%m")} ({max_day[1]} eventos)'
        ),
        inline=False
    )
    
    return embed

