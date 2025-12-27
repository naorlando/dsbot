"""
Módulo de Comandos Básicos de Estadísticas
Comandos simples para consultar stats: stats, topgames, topmessages, topreactions, topemojis, topstickers, topusers
"""

import discord
from discord.ext import commands
from datetime import datetime
from core.persistence import stats
from core.checks import check_stats_channel
from stats_viz import format_time


async def setup_basic_commands(bot: commands.Bot):
    """Registra los comandos básicos de stats"""
    
    # Evitar registro duplicado
    if 'stats' in bot.all_commands:
        return
    
    @bot.command(name='stats', aliases=['mystats'])
    async def show_stats(ctx, member: discord.Member = None):
        """Muestra estadísticas de un usuario
        
        Ejemplos:
        - !stats - Tus estadísticas
        - !stats @usuario - Estadísticas de otro usuario
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx, ctx.bot):
            return
        
        if member is None:
            member = ctx.author
        
        user_id = str(member.id)
        
        if user_id not in stats['users']:
            await ctx.send(f'📊 {member.display_name} no tiene estadísticas registradas aún.')
            return
        
        user_stats = stats['users'][user_id]
        
        # Crear embed
        embed = discord.Embed(
            title=f'📊 Estadísticas de {member.display_name}',
            color=discord.Color.blue()
        )
        
        # Estadísticas de juegos (ORDENAR POR TIEMPO)
        games = user_stats.get('games', {})
        if games:
            game_lines = []
            # Ordenar por tiempo de juego
            for game, data in sorted(games.items(), key=lambda x: x[1].get('total_minutes', 0), reverse=True)[:5]:
                minutes = data.get('total_minutes', 0)
                count = data.get('count', 0)
                game_lines.append(f'• {game}: ⏱️ **{format_time(minutes)}** ({count} sesiones)')
            
            # Total de tiempo de juegos
            total_game_minutes = sum(g.get('total_minutes', 0) for g in games.values())
            embed.add_field(
                name='🎮 Juegos',
                value='\n'.join(game_lines) + f'\n\n**Total:** {len(games)} juegos (⏱️ {format_time(total_game_minutes)})',
                inline=False
            )
        
        # Estadísticas de voz
        voice = user_stats.get('voice', {})
        if voice.get('count', 0) > 0:
            last_join = voice.get('last_join')
            if last_join:
                try:
                    last_dt = datetime.fromisoformat(last_join)
                    time_ago = datetime.now() - last_dt
                    if time_ago.days > 0:
                        time_str = f'hace {time_ago.days} días'
                    elif time_ago.seconds > 3600:
                        time_str = f'hace {time_ago.seconds // 3600} horas'
                    else:
                        time_str = f'hace {time_ago.seconds // 60} minutos'
                except:
                    time_str = 'Desconocido'
            else:
                time_str = 'Desconocido'
            
            # Formatear tiempo total (usar helper)
            total_minutes = voice.get('total_minutes', 0)
            
            voice_text = f'⏱️ Tiempo total: **{format_time(total_minutes)}**\nEntradas: **{voice["count"]}** sesiones\nÚltima vez: {time_str}'
            
            embed.add_field(
                name='🔊 Voz',
                value=voice_text,
                inline=False
            )
        
        # Estadísticas de mensajes
        messages = user_stats.get('messages', {})
        if messages.get('count', 0) > 0:
            msg_count = messages['count']
            msg_chars = messages.get('characters', 0)
            
            # Calcular promedio de caracteres por mensaje
            avg_chars = msg_chars // msg_count if msg_count > 0 else 0
            
            # Estimar palabras (promedio ~5 chars por palabra)
            estimated_words = msg_chars // 5
            
            messages_text = (
                f'Total: **{msg_count:,}** mensajes\n'
                f'Caracteres: **{msg_chars:,}** (~{estimated_words:,} palabras)\n'
                f'Promedio: **{avg_chars}** chars/mensaje'
            )
            
            embed.add_field(
                name='💬 Mensajes',
                value=messages_text,
                inline=False
            )
        
        # Estadísticas de reacciones
        reactions = user_stats.get('reactions', {})
        if reactions.get('total', 0) > 0:
            total_reactions = reactions['total']
            by_emoji = reactions.get('by_emoji', {})
            
            # Top 3 emojis más usados
            top_emojis = sorted(by_emoji.items(), key=lambda x: x[1], reverse=True)[:3]
            emojis_text = ' | '.join([f'{emoji} {count}' for emoji, count in top_emojis])
            
            reactions_text = (
                f'Total: **{total_reactions:,}** reacciones\n'
                f'Top 3: {emojis_text}'
            )
            
            embed.add_field(
                name='👍 Reacciones',
                value=reactions_text,
                inline=False
            )
        
        # Estadísticas de stickers
        stickers = user_stats.get('stickers', {})
        if stickers.get('total', 0) > 0:
            total_stickers = stickers['total']
            by_name = stickers.get('by_name', {})
            
            # Sticker favorito
            if by_name:
                favorite = max(by_name.items(), key=lambda x: x[1])
                stickers_text = (
                    f'Total: **{total_stickers:,}** stickers\n'
                    f'Favorito: **{favorite[0]}** ({favorite[1]} veces)'
                )
            else:
                stickers_text = f'Total: **{total_stickers:,}** stickers'
            
            embed.add_field(
                name='🎨 Stickers',
                value=stickers_text,
                inline=False
            )
        
        # Estadísticas de conexiones diarias
        daily_connections = user_stats.get('daily_connections', {})
        if daily_connections:
            total_days = len(daily_connections)
            
            # Contar días este mes
            current_month = datetime.now().strftime('%Y-%m')
            days_this_month = sum(1 for date in daily_connections.keys() if date.startswith(current_month))
            
            # Última conexión
            last_connection = max(daily_connections.keys()) if daily_connections else None
            if last_connection:
                try:
                    last_dt = datetime.strptime(last_connection, '%Y-%m-%d')
                    days_ago = (datetime.now() - last_dt).days
                    if days_ago == 0:
                        time_str = 'hoy'
                    elif days_ago == 1:
                        time_str = 'ayer'
                    else:
                        time_str = f'hace {days_ago} días'
                except:
                    time_str = 'Desconocido'
            else:
                time_str = 'Desconocido'
            
            connections_text = (
                f'Días activos: **{total_days}** días ({days_this_month} este mes)\n'
                f'Última conexión: {time_str}'
            )
            
            embed.add_field(
                name='🌐 Actividad',
                value=connections_text,
                inline=False
            )
        
        await ctx.send(embed=embed)

    @bot.command(name='topgames')
    async def top_games(ctx, limit: int = 5):
        """Muestra los juegos más jugados (ordenado por TIEMPO)
        
        Ejemplo: !topgames o !topgames 10
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx, ctx.bot):
            return
        
        # Recopilar todos los juegos CON TIEMPO
        game_stats = {}
        for user_data in stats['users'].values():
            for game, data in user_data.get('games', {}).items():
                if game not in game_stats:
                    game_stats[game] = {'minutes': 0, 'count': 0}
                game_stats[game]['minutes'] += data.get('total_minutes', 0)
                game_stats[game]['count'] += data.get('count', 0)
        
        if not game_stats:
            await ctx.send('📊 No hay juegos registrados aún.')
            return
        
        # Ordenar por TIEMPO y limitar
        top = sorted(game_stats.items(), key=lambda x: x[1]['minutes'], reverse=True)[:limit]
        
        embed = discord.Embed(
            title=f'🏆 Top {len(top)} Juegos Más Jugados',
            color=discord.Color.gold()
        )
        
        lines = []
        for i, (game, data) in enumerate(top, 1):
            medal = ['🥇', '🥈', '🥉'][i-1] if i <= 3 else f'{i}.'
            lines.append(f'{medal} **{game}**: ⏱️ {format_time(data["minutes"])} ({data["count"]} sesiones)')
        
        embed.description = '\n'.join(lines)
        await ctx.send(embed=embed)

    @bot.command(name='topmessages')
    async def top_messages(ctx, limit: int = 5):
        """Muestra los usuarios más activos en mensajes
        
        Ejemplo: !topmessages o !topmessages 10
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx, ctx.bot):
            return
        
        # Recopilar mensajes por usuario
        message_activity = []
        for user_id, user_data in stats['users'].items():
            messages_data = user_data.get('messages', {})
            msg_count = messages_data.get('count', 0)
            msg_chars = messages_data.get('characters', 0)
            
            if msg_count > 0:
                message_activity.append({
                    'username': user_data.get('username', 'Usuario Desconocido'),
                    'count': msg_count,
                    'characters': msg_chars
                })
        
        if not message_activity:
            await ctx.send('📊 No hay mensajes registrados aún.')
            return
        
        # Ordenar por cantidad de mensajes y limitar
        top = sorted(message_activity, key=lambda x: x['count'], reverse=True)[:limit]
        
        embed = discord.Embed(
            title=f'🏆 Top {len(top)} Usuarios Más Activos en Chat',
            color=discord.Color.teal()
        )
        
        lines = []
        for i, user in enumerate(top, 1):
            medal = ['🥇', '🥈', '🥉'][i-1] if i <= 3 else f'{i}.'
            avg_chars = user['characters'] // user['count'] if user['count'] > 0 else 0
            estimated_words = user['characters'] // 5
            lines.append(
                f'{medal} **{user["username"]}**: {user["count"]:,} mensajes\n'
                f'   💬 ~{estimated_words:,} palabras | {avg_chars} chars/msg promedio'
            )
        
        embed.description = '\n'.join(lines)
        await ctx.send(embed=embed)

    @bot.command(name='topreactions')
    async def top_reactions(ctx, limit: int = 5):
        """Muestra los usuarios que más reaccionan
        
        Ejemplo: !topreactions o !topreactions 10
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx, ctx.bot):
            return
        
        # Recopilar reacciones por usuario
        reaction_activity = []
        for user_id, user_data in stats['users'].items():
            reactions_data = user_data.get('reactions', {})
            total_reactions = reactions_data.get('total', 0)
            
            if total_reactions > 0:
                by_emoji = reactions_data.get('by_emoji', {})
                # Emoji favorito
                favorite_emoji = max(by_emoji.items(), key=lambda x: x[1]) if by_emoji else (None, 0)
                
                reaction_activity.append({
                    'username': user_data.get('username', 'Usuario Desconocido'),
                    'total': total_reactions,
                    'favorite_emoji': favorite_emoji[0],
                    'favorite_count': favorite_emoji[1]
                })
        
        if not reaction_activity:
            await ctx.send('📊 No hay reacciones registradas aún.')
            return
        
        # Ordenar por total de reacciones
        top = sorted(reaction_activity, key=lambda x: x['total'], reverse=True)[:limit]
        
        embed = discord.Embed(
            title=f'🏆 Top {len(top)} Usuarios Más Reactivos',
            color=discord.Color.purple()
        )
        
        lines = []
        for i, user in enumerate(top, 1):
            medal = ['🥇', '🥈', '🥉'][i-1] if i <= 3 else f'{i}.'
            fav_emoji = user['favorite_emoji'] if user['favorite_emoji'] else '❓'
            lines.append(
                f'{medal} **{user["username"]}**: {user["total"]:,} reacciones\n'
                f'   👍 Favorito: {fav_emoji} ({user["favorite_count"]} veces)'
            )
        
        embed.description = '\n'.join(lines)
        await ctx.send(embed=embed)

    @bot.command(name='topemojis')
    async def top_emojis(ctx, limit: int = 10):
        """Muestra los emojis más usados globalmente
        
        Ejemplo: !topemojis o !topemojis 15
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx, ctx.bot):
            return
        
        # Recopilar todos los emojis de todos los usuarios
        emoji_counts = {}
        for user_data in stats['users'].values():
            reactions_data = user_data.get('reactions', {})
            by_emoji = reactions_data.get('by_emoji', {})
            
            for emoji, count in by_emoji.items():
                if emoji not in emoji_counts:
                    emoji_counts[emoji] = 0
                emoji_counts[emoji] += count
        
        if not emoji_counts:
            await ctx.send('📊 No hay emojis registrados aún.')
            return
        
        # Ordenar y limitar
        top = sorted(emoji_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        embed = discord.Embed(
            title=f'🏆 Top {len(top)} Emojis Más Usados',
            color=discord.Color.gold()
        )
        
        lines = []
        for i, (emoji, count) in enumerate(top, 1):
            medal = ['🥇', '🥈', '🥉'][i-1] if i <= 3 else f'{i}.'
            lines.append(f'{medal} {emoji}: **{count:,}** veces')
        
        embed.description = '\n'.join(lines)
        
        # Total
        total_reactions = sum(emoji_counts.values())
        embed.add_field(
            name='📊 Total',
            value=f'**{total_reactions:,}** reacciones totales\n**{len(emoji_counts)}** emojis únicos',
            inline=False
        )
        
        await ctx.send(embed=embed)

    @bot.command(name='topstickers')
    async def top_stickers(ctx, limit: int = 10):
        """Muestra los stickers más usados
        
        Ejemplo: !topstickers o !topstickers 15
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx, ctx.bot):
            return
        
        # Recopilar todos los stickers de todos los usuarios
        sticker_counts = {}
        for user_data in stats['users'].values():
            stickers_data = user_data.get('stickers', {})
            by_name = stickers_data.get('by_name', {})
            
            for sticker, count in by_name.items():
                if sticker not in sticker_counts:
                    sticker_counts[sticker] = 0
                sticker_counts[sticker] += count
        
        if not sticker_counts:
            await ctx.send('📊 No hay stickers registrados aún.')
            return
        
        # Ordenar y limitar
        top = sorted(sticker_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        embed = discord.Embed(
            title=f'🏆 Top {len(top)} Stickers Más Usados',
            color=discord.Color.magenta()
        )
        
        lines = []
        for i, (sticker, count) in enumerate(top, 1):
            medal = ['🥇', '🥈', '🥉'][i-1] if i <= 3 else f'{i}.'
            lines.append(f'{medal} **{sticker}**: {count:,} veces')
        
        embed.description = '\n'.join(lines)
        
        # Total
        total_stickers = sum(sticker_counts.values())
        embed.add_field(
            name='📊 Total',
            value=f'**{total_stickers:,}** stickers enviados\n**{len(sticker_counts)}** stickers únicos',
            inline=False
        )
        
        await ctx.send(embed=embed)

    @bot.command(name='topusers')
    async def top_users(ctx, limit: int = 5):
        """Muestra los usuarios más activos (ordenado por TIEMPO TOTAL)
        
        Ejemplo: !topusers o !topusers 10
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx, ctx.bot):
            return
        
        # Calcular actividad total por usuario CON TIEMPO
        user_activity = []
        for user_id, user_data in stats['users'].items():
            games_count = sum(game['count'] for game in user_data.get('games', {}).values())
            voice_count = user_data.get('voice', {}).get('count', 0)
            
            # Tiempo total = juegos + voz
            game_minutes = sum(g.get('total_minutes', 0) for g in user_data.get('games', {}).values())
            voice_minutes = user_data.get('voice', {}).get('total_minutes', 0)
            total_minutes = game_minutes + voice_minutes
            total_sessions = games_count + voice_count
            
            if total_sessions > 0:
                user_activity.append({
                    'username': user_data.get('username', 'Usuario Desconocido'),
                    'games': games_count,
                    'voice': voice_count,
                    'minutes': total_minutes,
                    'total': total_sessions
                })
        
        if not user_activity:
            await ctx.send('📊 No hay actividad registrada aún.')
            return
        
        # Ordenar por TIEMPO TOTAL y limitar
        top = sorted(user_activity, key=lambda x: x['minutes'], reverse=True)[:limit]
        
        embed = discord.Embed(
            title=f'🏆 Top {len(top)} Usuarios Más Activos',
            color=discord.Color.gold()
        )
        
        lines = []
        for i, user in enumerate(top, 1):
            medal = ['🥇', '🥈', '🥉'][i-1] if i <= 3 else f'{i}.'
            lines.append(
                f'{medal} **{user["username"]}**: ⏱️ {format_time(user["minutes"])}\n'
                f'   🎮 {user["games"]} juegos | 🔊 {user["voice"]} voz | {user["total"]} sesiones totales'
            )
        
        embed.description = '\n'.join(lines)
        await ctx.send(embed=embed)

