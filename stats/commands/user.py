"""
Comandos de Usuario
!stats, !mystats, !compare
"""

import discord
from discord.ext import commands
import json

from core.persistence import STATS_FILE
from ..visualization import (
    create_bar_chart,
    create_comparison_bars,
    format_time,
    format_time_ago,
    format_large_number,
    format_stat_line
)


def setup_user_commands(bot):
    """Registra los comandos de usuario"""
    
    @bot.command(name='stats', aliases=['estadisticas'])
    async def stats_command(ctx, user: discord.Member = None):
        """
        📊 Estadísticas completas de un usuario
        
        Uso: !stats [@usuario]
        
        Sin mencionar a nadie: muestra tus estadísticas
        Con mención: muestra las estadísticas del usuario mencionado
        """
        # Determinar el usuario
        target_user = user if user else ctx.author
        await ctx.send(f"⏳ Cargando estadísticas de **{target_user.display_name}**...")
        
        # Cargar stats
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
        except Exception as e:
            await ctx.send(f"❌ Error al cargar estadísticas: {e}")
            return
        
        # Buscar datos del usuario
        user_id = str(target_user.id)
        users = stats_data.get('users', {})
        
        if user_id not in users:
            await ctx.send(f"❌ **{target_user.display_name}** no tiene estadísticas registradas.")
            return
        
        user_data = users[user_id]
        
        # Crear embed principal
        embed = discord.Embed(
            title=f'📊 Estadísticas de {target_user.display_name}',
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        # 🎮 JUEGOS
        games = user_data.get('games', {})
        if games:
            total_game_time = sum(g.get('total_minutes', 0) for g in games.values())
            total_sessions = sum(g.get('count', 0) for g in games.values())
            unique_games = len(games)
            
            # Top 3 juegos
            sorted_games = sorted(
                games.items(),
                key=lambda x: x[1].get('total_minutes', 0),
                reverse=True
            )[:3]
            
            top_games_text = "\n".join([
                f"**{i+1}.** {name} - {format_time(data.get('total_minutes', 0))}"
                for i, (name, data) in enumerate(sorted_games)
            ])
            
            games_summary = (
                f"⏱️ **Tiempo Total:** {format_time(total_game_time)}\n"
                f"🎯 **Sesiones:** {total_sessions:,}\n"
                f"🎮 **Juegos Únicos:** {unique_games}\n\n"
                f"**Top 3 Juegos:**\n{top_games_text}"
            )
            
            embed.add_field(
                name="🎮 Gaming",
                value=games_summary,
                inline=False
            )
        else:
            embed.add_field(
                name="🎮 Gaming",
                value="*Sin actividad de gaming*",
                inline=False
            )
        
        # 🔊 VOZ
        voice = user_data.get('voice', {})
        if voice.get('total_minutes', 0) > 0 or voice.get('count', 0) > 0:
            voice_time = voice.get('total_minutes', 0)
            voice_count = voice.get('count', 0)
            last_join = voice.get('last_join')
            
            voice_text = (
                f"⏱️ **Tiempo Total:** {format_time(voice_time)}\n"
                f"🔊 **Conexiones:** {voice_count:,}\n"
            )
            
            if last_join:
                voice_text += f"📅 **Última vez:** {format_time_ago(last_join)}"
            
            embed.add_field(
                name="🔊 Voz",
                value=voice_text,
                inline=False
            )
        else:
            embed.add_field(
                name="🔊 Voz",
                value="*Sin actividad de voz*",
                inline=False
            )
        
        # 💬 MENSAJES
        messages = user_data.get('messages', {})
        if messages.get('count', 0) > 0:
            msg_count = messages.get('count', 0)
            msg_chars = messages.get('characters', 0)
            avg_chars = int(msg_chars / msg_count) if msg_count > 0 else 0
            
            messages_text = (
                f"💬 **Mensajes:** {format_large_number(msg_count)}\n"
                f"📝 **Promedio:** {avg_chars} caracteres/msg"
            )
            
            embed.add_field(
                name="💬 Chat",
                value=messages_text,
                inline=True
            )
        
        # 😄 REACCIONES
        reactions = user_data.get('reactions', {})
        if reactions.get('count', 0) > 0:
            react_count = reactions.get('count', 0)
            reactions_text = f"😄 **Reacciones:** {format_large_number(react_count)}"
            
            embed.add_field(
                name="😄 Reacciones",
                value=reactions_text,
                inline=True
            )
        
        # Footer con comandos relacionados
        embed.set_footer(text="💡 Usa !mygames para ver tu top de juegos | !compare @usuario para comparar")
        
        await ctx.send(embed=embed)
    
    
    @bot.command(name='mystats', aliases=['yo'])
    async def mystats_command(ctx):
        """
        📊 Tus estadísticas (atajo)
        
        Uso: !mystats
        
        Es lo mismo que !stats pero más rápido
        """
        await stats_command(ctx, None)
    
    
    @bot.command(name='compare', aliases=['vs', 'comparar'])
    async def compare_command(ctx, user: discord.Member):
        """
        🆚 Compara tus stats con otro usuario
        
        Uso: !compare @usuario
        
        Muestra una comparación lado a lado de:
        - Tiempo de juego
        - Tiempo en voz
        - Mensajes enviados
        """
        if not user:
            await ctx.send("❌ Debes mencionar un usuario para comparar.\nEjemplo: `!compare @Pino`")
            return
        
        if user.id == ctx.author.id:
            await ctx.send("❌ No puedes compararte contigo mismo!")
            return
        
        await ctx.send(f"⏳ Comparando **{ctx.author.display_name}** vs **{user.display_name}**...")
        
        # Cargar stats
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
        except Exception as e:
            await ctx.send(f"❌ Error al cargar estadísticas: {e}")
            return
        
        users = stats_data.get('users', {})
        
        user1_id = str(ctx.author.id)
        user2_id = str(user.id)
        
        if user1_id not in users:
            await ctx.send(f"❌ **{ctx.author.display_name}** no tiene estadísticas.")
            return
        
        if user2_id not in users:
            await ctx.send(f"❌ **{user.display_name}** no tiene estadísticas.")
            return
        
        user1_data = users[user1_id]
        user2_data = users[user2_id]
        
        # Crear comparación visual
        chart = create_comparison_bars(
            user1_data,
            user2_data,
            ctx.author.display_name,
            user.display_name
        )
        
        try:
            await ctx.send(f"```{chart}```")
        except discord.HTTPException:
            # Fallback
            # Calcular totales
            games1 = sum(g.get('total_minutes', 0) for g in user1_data.get('games', {}).values())
            games2 = sum(g.get('total_minutes', 0) for g in user2_data.get('games', {}).values())
            
            voice1 = user1_data.get('voice', {}).get('total_minutes', 0)
            voice2 = user2_data.get('voice', {}).get('total_minutes', 0)
            
            msg1 = user1_data.get('messages', {}).get('count', 0)
            msg2 = user2_data.get('messages', {}).get('count', 0)
            
            embed = discord.Embed(
                title=f"🆚 {ctx.author.display_name} vs {user.display_name}",
                color=discord.Color.purple()
            )
            
            embed.add_field(
                name="🎮 Gaming",
                value=f"{ctx.author.display_name}: {format_time(games1)}\n{user.display_name}: {format_time(games2)}",
                inline=False
            )
            
            embed.add_field(
                name="🔊 Voz",
                value=f"{ctx.author.display_name}: {format_time(voice1)}\n{user.display_name}: {format_time(voice2)}",
                inline=False
            )
            
            embed.add_field(
                name="💬 Mensajes",
                value=f"{ctx.author.display_name}: {format_large_number(msg1)}\n{user.display_name}: {format_large_number(msg2)}",
                inline=False
            )
            
            await ctx.send(embed=embed)

