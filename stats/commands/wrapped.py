"""
Comando !wrapped - Resumen anual del usuario
Versión Básica - Solo usa datos actuales
"""
import discord
from discord.ext import commands
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from core.persistence import STATS_FILE

import logging
logger = logging.getLogger('dsbot')


@commands.command(name='wrapped')
async def wrapped(ctx, usuario: discord.Member = None, año: int = None):
    """
    🎁 Tu año en Discord (Wrapped)
    
    Uso:
        !wrapped              → Tu wrapped del año actual
        !wrapped @usuario     → Wrapped de otro usuario
        !wrapped @usuario 2025 → Wrapped de un año específico
    
    Ejemplo: !wrapped @Pino 2025
    """
    # Determinar usuario (si no se especifica, usar quien ejecuta el comando)
    target_user = usuario if usuario else ctx.author
    
    # Determinar año (si no se especifica, usar año actual)
    target_year = año if año else datetime.now().year
    
    # Cargar datos
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            stats_data = json.load(f)
    except Exception as e:
        await ctx.send(f"❌ Error cargando estadísticas: {e}")
        return
    
    user_id = str(target_user.id)
    
    # Verificar que el usuario tenga datos
    if user_id not in stats_data.get('users', {}):
        await ctx.send(f"❌ {target_user.display_name} no tiene estadísticas registradas.")
        return
    
    # Generar wrapped
    try:
        wrapped_embed = generate_wrapped_embed(stats_data, user_id, target_user.display_name, target_year)
        await ctx.send(embed=wrapped_embed)
        logger.info(f'🎁 Wrapped generado para {target_user.display_name} ({target_year})')
    except Exception as e:
        logger.error(f'Error generando wrapped: {e}', exc_info=True)
        await ctx.send(f"❌ Error generando wrapped: {e}")


def generate_wrapped_embed(stats_data: Dict, user_id: str, username: str, year: int) -> discord.Embed:
    """
    Genera el embed del wrapped completo
    """
    user_data = stats_data['users'][user_id]
    
    # Crear embed principal
    embed = discord.Embed(
        title=f"🎁 {username} en {year}",
        description="Tu año en Discord resumido",
        color=0x9b59b6,  # Púrpura
        timestamp=datetime.now()
    )
    
    # === GAMING ===
    gaming_stats = _calculate_gaming_stats(user_data, year)
    if gaming_stats:
        gaming_text = (
            f"🎮 **{gaming_stats['total_hours']}h** jugadas\n"
            f"🏆 Tu juego: **{gaming_stats['top_game']}** ({gaming_stats['top_game_hours']}h)\n"
            f"📊 {gaming_stats['unique_games']} juegos diferentes\n"
            f"🔥 Racha: **{gaming_stats['longest_streak']} días** seguidos\n"
            f"📅 Día más gamer: {gaming_stats['best_day']}"
        )
        embed.add_field(name="🎮 GAMING", value=gaming_text, inline=False)
    
    # === VOICE ===
    voice_stats = _calculate_voice_stats(user_data, year)
    if voice_stats:
        voice_text = (
            f"🔊 **{voice_stats['total_hours']}h** en voice\n"
            f"📊 {voice_stats['sessions']} sesiones\n"
            f"⏱️ Promedio: {voice_stats['avg_session']}h por sesión\n"
            f"🏆 Maratón: **{voice_stats['longest_session']}h**"
        )
        embed.add_field(name="🔊 VOICE", value=voice_text, inline=False)
    
    # === PARTIES ===
    party_stats = _calculate_party_stats(stats_data, user_id, year)
    if party_stats:
        party_text = (
            f"🎉 **{party_stats['total_parties']}** parties jugadas\n"
            f"🏆 Juego más social: **{party_stats['top_game']}**\n"
            f"⏱️ Party más larga: **{party_stats['longest_party']}h**\n"
            f"👥 Tu squad: {party_stats['best_partner']}"
        )
        embed.add_field(name="🎉 PARTIES", value=party_text, inline=False)
    
    # === SOCIAL ===
    social_stats = _calculate_social_stats(user_data)
    if social_stats and social_stats['messages'] > 0:
        social_text = (
            f"💬 **{social_stats['messages']:,}** mensajes\n"
            f"❤️ {social_stats['reactions']} reacciones\n"
            f"🎨 {social_stats['stickers']} stickers\n"
            f"😊 Tu emoji: {social_stats['top_emoji']}"
        )
        embed.add_field(name="💬 SOCIAL", value=social_text, inline=False)
    
    # === PERSONALIDAD ===
    personality = _detect_personality(user_data, gaming_stats, party_stats)
    if personality:
        personality_text = "\n".join([f"{icon} {trait}" for icon, trait in personality])
        embed.add_field(name="🎨 TU PERSONALIDAD", value=personality_text, inline=False)
    
    # === RANKINGS ===
    rankings = _calculate_rankings(stats_data, user_id)
    if rankings:
        rankings_text = (
            f"🏆 #{rankings['gaming']} en Gaming\n"
            f"💬 #{rankings['social']} en Social\n"
            f"🎉 #{rankings['parties']} en Parties"
        )
        embed.add_field(name="🏆 TU POSICIÓN", value=rankings_text, inline=False)
    
    embed.set_footer(text=f"Wrapped 2025 • Generado el {datetime.now().strftime('%d/%m/%Y')}")
    
    return embed


def _calculate_gaming_stats(user_data: Dict, year: int) -> Optional[Dict]:
    """Calcula estadísticas de gaming para el wrapped"""
    games = user_data.get('games', {})
    if not games:
        return None
    
    # Filtrar por año (usando daily_minutes)
    year_str = str(year)
    total_minutes = 0
    games_filtered = {}
    
    for game_name, game_data in games.items():
        daily_minutes = game_data.get('daily_minutes', {})
        year_minutes = sum(
            minutes for date, minutes in daily_minutes.items()
            if date.startswith(year_str)
        )
        if year_minutes > 0:
            games_filtered[game_name] = {
                'minutes': year_minutes,
                'count': game_data.get('count', 0),
                'daily_minutes': {k: v for k, v in daily_minutes.items() if k.startswith(year_str)}
            }
            total_minutes += year_minutes
    
    if not games_filtered:
        return None
    
    # Top juego
    top_game = max(games_filtered.items(), key=lambda x: x[1]['minutes'])
    
    # Racha más larga (días consecutivos)
    longest_streak = _calculate_longest_streak(games_filtered)
    
    # Día más gamer
    all_daily = {}
    for game_data in games_filtered.values():
        for date, minutes in game_data.get('daily_minutes', {}).items():
            all_daily[date] = all_daily.get(date, 0) + minutes
    
    best_day = max(all_daily.items(), key=lambda x: x[1]) if all_daily else ("N/A", 0)
    
    return {
        'total_hours': round(total_minutes / 60, 1),
        'total_minutes': total_minutes,
        'top_game': top_game[0],
        'top_game_hours': round(top_game[1]['minutes'] / 60, 1),
        'unique_games': len(games_filtered),
        'longest_streak': longest_streak,
        'best_day': f"{best_day[0]} ({round(best_day[1] / 60, 1)}h)" if best_day[0] != "N/A" else "N/A",
        'avg_session': round((total_minutes / sum(g['count'] for g in games_filtered.values())) / 60, 1) if games_filtered else 0
    }


def _calculate_longest_streak(games_filtered: Dict) -> int:
    """Calcula la racha más larga de días consecutivos jugando"""
    from datetime import datetime, timedelta
    
    # Obtener todas las fechas únicas
    all_dates = set()
    for game_data in games_filtered.values():
        all_dates.update(game_data.get('daily_minutes', {}).keys())
    
    if not all_dates:
        return 0
    
    # Convertir a datetime y ordenar
    dates = sorted([datetime.fromisoformat(d) for d in all_dates])
    
    # Calcular racha más larga
    max_streak = 1
    current_streak = 1
    
    for i in range(1, len(dates)):
        if (dates[i] - dates[i-1]).days == 1:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 1
    
    return max_streak


def _calculate_voice_stats(user_data: Dict, year: int) -> Optional[Dict]:
    """Calcula estadísticas de voice para el wrapped"""
    voice = user_data.get('voice', {})
    if not voice or voice.get('total_minutes', 0) == 0:
        return None
    
    # Filtrar por año
    year_str = str(year)
    daily_minutes = voice.get('daily_minutes', {})
    year_minutes = sum(
        minutes for date, minutes in daily_minutes.items()
        if date.startswith(year_str)
    )
    
    if year_minutes == 0:
        return None
    
    # Sesiones en el año (estimado)
    sessions = voice.get('count', 0)
    
    # Maratón más larga (día con más minutos)
    year_daily = {k: v for k, v in daily_minutes.items() if k.startswith(year_str)}
    longest_day = max(year_daily.values()) if year_daily else 0
    
    return {
        'total_hours': round(year_minutes / 60, 1),
        'sessions': sessions,
        'avg_session': round((year_minutes / sessions) / 60, 1) if sessions > 0 else 0,
        'longest_session': round(longest_day / 60, 1)
    }


def _calculate_party_stats(stats_data: Dict, user_id: str, year: int) -> Optional[Dict]:
    """Calcula estadísticas de parties para el wrapped"""
    parties = stats_data.get('parties', {})
    history = parties.get('history', [])
    
    if not history:
        return None
    
    # Filtrar parties donde el usuario participó en el año
    year_str = str(year)
    user_parties = [
        p for p in history
        if user_id in p.get('players', []) and p.get('start', '').startswith(year_str)
    ]
    
    if not user_parties:
        return None
    
    # Juego más jugado en party
    game_counts = {}
    for party in user_parties:
        game = party.get('game', 'Unknown')
        game_counts[game] = game_counts.get(game, 0) + 1
    
    top_game = max(game_counts.items(), key=lambda x: x[1])[0] if game_counts else "N/A"
    
    # Party más larga
    longest = max(user_parties, key=lambda x: x.get('duration', 0))
    longest_hours = round(longest.get('duration', 0) / 60, 1)
    
    # Mejor compañero (con quien jugó más)
    partner_counts = {}
    for party in user_parties:
        for player in party.get('players', []):
            if player != user_id:
                partner_counts[player] = partner_counts.get(player, 0) + 1
    
    if partner_counts:
        best_partner_id = max(partner_counts.items(), key=lambda x: x[1])[0]
        # Buscar username
        best_partner_name = stats_data['users'].get(best_partner_id, {}).get('username', 'Unknown')
        best_partner = f"{best_partner_name} ({partner_counts[best_partner_id]} parties)"
    else:
        best_partner = "Solo"
    
    return {
        'total_parties': len(user_parties),
        'top_game': top_game,
        'longest_party': longest_hours,
        'best_partner': best_partner
    }


def _calculate_social_stats(user_data: Dict) -> Optional[Dict]:
    """Calcula estadísticas sociales para el wrapped"""
    messages = user_data.get('messages', {})
    reactions = user_data.get('reactions', {})
    stickers = user_data.get('stickers', {})
    
    if not messages and not reactions:
        return None
    
    # Top emoji
    by_emoji = reactions.get('by_emoji', {})
    top_emoji = max(by_emoji.items(), key=lambda x: x[1]) if by_emoji else ("❓", 0)
    
    return {
        'messages': messages.get('count', 0),
        'reactions': reactions.get('total', 0),
        'stickers': stickers.get('total', 0),
        'top_emoji': f"{top_emoji[0]} ({top_emoji[1]}x)" if by_emoji else "N/A"
    }


def _detect_personality(user_data: Dict, gaming_stats: Optional[Dict], party_stats: Optional[Dict]) -> List[Tuple[str, str]]:
    """Detecta la personalidad del usuario basado en sus stats"""
    personality = []
    
    if not gaming_stats:
        return [("🤷", "Sin datos suficientes")]
    
    # Maratonero vs Casual
    avg_session = gaming_stats.get('avg_session', 0)
    if avg_session >= 3:
        personality.append(("🏃", "Maratonero"))
    elif avg_session < 1 and avg_session > 0:
        personality.append(("🎲", "Casual"))
    
    # Social vs Loner
    if party_stats:
        total_parties = party_stats.get('total_parties', 0)
        if total_parties > 30:
            personality.append(("👥", "Social Butterfly"))
        elif total_parties < 5 and total_parties > 0:
            personality.append(("🦅", "Loner"))
    
    # Fidelidad vs Explorer
    unique_games = gaming_stats.get('unique_games', 0)
    if unique_games >= 10:
        personality.append(("🗺️", "Explorer"))
    elif unique_games <= 3 and unique_games > 0:
        personality.append(("💎", "Fiel a sus juegos"))
    
    # Racha
    longest_streak = gaming_stats.get('longest_streak', 0)
    if longest_streak >= 14:
        personality.append(("🔥", "Constante"))
    
    return personality if personality else [("🎮", "Gamer")]


def _calculate_rankings(stats_data: Dict, user_id: str) -> Optional[Dict]:
    """Calcula rankings del usuario en el servidor"""
    users = stats_data.get('users', {})
    
    # Gaming ranking (por total_minutes)
    gaming_scores = []
    for uid, udata in users.items():
        total = sum(
            game.get('total_minutes', 0)
            for game in udata.get('games', {}).values()
        )
        gaming_scores.append((uid, total))
    
    gaming_scores.sort(key=lambda x: x[1], reverse=True)
    gaming_rank = next((i+1 for i, (uid, _) in enumerate(gaming_scores) if uid == user_id), 0)
    
    # Social ranking (mensajes + reacciones)
    social_scores = []
    for uid, udata in users.items():
        score = (
            udata.get('messages', {}).get('count', 0) +
            udata.get('reactions', {}).get('total', 0)
        )
        social_scores.append((uid, score))
    
    social_scores.sort(key=lambda x: x[1], reverse=True)
    social_rank = next((i+1 for i, (uid, _) in enumerate(social_scores) if uid == user_id), 0)
    
    # Party ranking (contar parties)
    party_scores = []
    parties_history = stats_data.get('parties', {}).get('history', [])
    for uid in users.keys():
        count = sum(1 for p in parties_history if uid in p.get('players', []))
        party_scores.append((uid, count))
    
    party_scores.sort(key=lambda x: x[1], reverse=True)
    party_rank = next((i+1 for i, (uid, _) in enumerate(party_scores) if uid == user_id), 0)
    
    return {
        'gaming': gaming_rank,
        'social': social_rank,
        'parties': party_rank
    }


def setup_wrapped_commands(bot):
    """Registra el comando de wrapped"""
    bot.add_command(wrapped)
    logger.info("✅ Comando !wrapped registrado")

