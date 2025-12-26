"""
Módulo de visualización de estadísticas
Genera gráficos ASCII y resúmenes para el bot de Discord
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# Import discord solo si está disponible (para tests)
try:
    import discord
except ImportError:
    discord = None


def create_bar_chart(data: List[Tuple[str, int]], max_width: int = 20, title: str = "") -> str:
    """
    Crea un gráfico de barras ASCII
    
    Args:
        data: Lista de tuplas (label, value)
        max_width: Ancho máximo de la barra más grande
        title: Título del gráfico
    
    Returns:
        String con el gráfico formateado
    """
    if not data:
        return "📊 No hay datos disponibles"
    
    # Encontrar el valor máximo para normalizar
    max_value = max(value for _, value in data)
    if max_value == 0:
        return "📊 No hay datos disponibles"
    
    lines = []
    if title:
        lines.append(f"**{title}**")
        lines.append("━" * 40)
    
    for label, value in data:
        # Calcular la longitud de la barra
        bar_length = int((value / max_value) * max_width)
        bar = "█" * bar_length
        
        # Truncar label si es muy largo
        display_label = label[:15] + "..." if len(label) > 15 else label
        display_label = display_label.ljust(18)
        
        lines.append(f"{display_label} {bar} {value}")
    
    return "\n".join(lines)


def create_timeline_chart(daily_data: Dict[str, int], days: int = 7) -> str:
    """
    Crea un gráfico de línea de tiempo con actividad por día
    
    Args:
        daily_data: Dict con fecha (YYYY-MM-DD) -> count
        days: Número de días a mostrar
    
    Returns:
        String con el gráfico de timeline
    """
    # Generar los últimos N días
    end_date = datetime.now()
    dates = []
    for i in range(days - 1, -1, -1):
        date = end_date - timedelta(days=i)
        dates.append(date.strftime("%Y-%m-%d"))
    
    # Preparar datos
    data = []
    day_names = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    
    for date_str in dates:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = day_names[date_obj.weekday()]
        count = daily_data.get(date_str, 0)
        # Formato: "Lun 26/12"
        label = f"{day_name} {date_obj.strftime('%d/%m')}"
        data.append((label, count))
    
    return create_bar_chart(data, max_width=20, title=f"📈 Actividad ({days} días)")


def create_comparison_chart(user1_data: Dict, user2_data: Dict, user1_name: str, user2_name: str) -> str:
    """
    Crea un gráfico comparativo entre dos usuarios
    
    Args:
        user1_data: Datos del usuario 1
        user2_data: Datos del usuario 2
        user1_name: Nombre del usuario 1
        user2_name: Nombre del usuario 2
    
    Returns:
        String con la comparación formateada
    """
    lines = []
    lines.append(f"**📊 Comparación: {user1_name} vs {user2_name}**")
    lines.append("━" * 40)
    
    # Comparar juegos
    games1 = sum(game['count'] for game in user1_data.get('games', {}).values())
    games2 = sum(game['count'] for game in user2_data.get('games', {}).values())
    
    lines.append(f"\n🎮 **Sesiones de Juego:**")
    lines.append(f"{user1_name}: {games1}")
    lines.append(f"{user2_name}: {games2}")
    winner_games = user1_name if games1 > games2 else user2_name if games2 > games1 else "Empate"
    lines.append(f"👑 Ganador: **{winner_games}**")
    
    # Comparar voz
    voice1 = user1_data.get('voice', {}).get('count', 0)
    voice2 = user2_data.get('voice', {}).get('count', 0)
    
    lines.append(f"\n🔊 **Entradas a Voz:**")
    lines.append(f"{user1_name}: {voice1}")
    lines.append(f"{user2_name}: {voice2}")
    winner_voice = user1_name if voice1 > voice2 else user2_name if voice2 > voice1 else "Empate"
    lines.append(f"👑 Ganador: **{winner_voice}**")
    
    # Total
    total1 = games1 + voice1
    total2 = games2 + voice2
    
    lines.append(f"\n🏆 **Actividad Total:**")
    lines.append(f"{user1_name}: {total1}")
    lines.append(f"{user2_name}: {total2}")
    winner_total = user1_name if total1 > total2 else user2_name if total2 > total1 else "Empate"
    lines.append(f"👑 **Ganador General: {winner_total}**")
    
    return "\n".join(lines)


def create_user_detail_view(user_data: Dict, username: str):
    """
    Crea un embed detallado con las estadísticas de un usuario
    
    Args:
        user_data: Datos del usuario
        username: Nombre del usuario
    
    Returns:
        discord.Embed con los datos formateados (o None si discord no está disponible)
    """
    if discord is None:
        return None
    
    embed = discord.Embed(
        title=f'📊 Estadísticas Detalladas: {username}',
        color=discord.Color.blue()
    )
    
    # Juegos
    games = user_data.get('games', {})
    if games:
        total_games = sum(game['count'] for game in games.values())
        game_list = sorted(games.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
        
        game_lines = []
        for game_name, game_data in game_list:
            count = game_data['count']
            first_played = datetime.fromisoformat(game_data['first_played']).strftime('%d/%m/%Y')
            game_lines.append(f"• **{game_name}**: {count} veces (desde {first_played})")
        
        embed.add_field(
            name=f'🎮 Juegos (Total: {total_games} sesiones)',
            value='\n'.join(game_lines) + f'\n\n**Juegos únicos:** {len(games)}',
            inline=False
        )
    
    # Voz
    voice = user_data.get('voice', {})
    if voice.get('count', 0) > 0:
        count = voice['count']
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
        
        embed.add_field(
            name='🔊 Actividad de Voz',
            value=f'**Entradas:** {count} veces\n**Última vez:** {time_str}',
            inline=False
        )
    
    return embed


def filter_by_period(stats_data: Dict, period: str = 'all') -> Dict:
    """
    Filtra estadísticas por período de tiempo
    
    Args:
        stats_data: Datos completos de stats
        period: 'today', 'week', 'month', 'all'
    
    Returns:
        Dict filtrado con solo los datos del período
    """
    now = datetime.now()
    
    if period == 'all':
        return stats_data
    
    # Calcular fecha límite
    if period == 'today':
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        cutoff = now - timedelta(days=7)
    elif period == 'month':
        cutoff = now - timedelta(days=30)
    else:
        return stats_data
    
    # Filtrar datos
    filtered = {'users': {}}
    
    for user_id, user_data in stats_data.get('users', {}).items():
        filtered_user = {
            'username': user_data.get('username', 'Unknown'),
            'games': {},
            'voice': {'count': 0, 'last_join': None}
        }
        
        # Filtrar juegos
        for game_name, game_data in user_data.get('games', {}).items():
            try:
                last_played = datetime.fromisoformat(game_data.get('last_played', ''))
                if last_played >= cutoff:
                    filtered_user['games'][game_name] = game_data
            except:
                pass
        
        # Filtrar voz
        voice = user_data.get('voice', {})
        if voice.get('last_join'):
            try:
                last_join = datetime.fromisoformat(voice['last_join'])
                if last_join >= cutoff:
                    filtered_user['voice'] = voice
            except:
                pass
        
        # Solo agregar si tiene datos en el período
        if filtered_user['games'] or filtered_user['voice'].get('count', 0) > 0:
            filtered['users'][user_id] = filtered_user
    
    return filtered


def get_period_label(period: str) -> str:
    """Retorna el label legible para un período"""
    labels = {
        'today': 'Hoy',
        'week': 'Última Semana',
        'month': 'Último Mes',
        'all': 'Histórico'
    }
    return labels.get(period, period)


def calculate_daily_activity(stats_data: Dict, days: int = 7) -> Dict[str, int]:
    """
    Calcula la actividad diaria para los últimos N días
    
    Args:
        stats_data: Datos de stats
        days: Número de días a calcular
    
    Returns:
        Dict con fecha (YYYY-MM-DD) -> count
    """
    daily = {}
    
    # Inicializar los últimos N días con 0
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        daily[date] = 0
    
    # Contar actividad por día
    for user_data in stats_data.get('users', {}).values():
        # Contar juegos
        for game_data in user_data.get('games', {}).values():
            try:
                last_played = datetime.fromisoformat(game_data.get('last_played', ''))
                date_key = last_played.strftime("%Y-%m-%d")
                if date_key in daily:
                    daily[date_key] += game_data.get('count', 0)
            except:
                pass
        
        # Contar voz
        voice = user_data.get('voice', {})
        if voice.get('last_join'):
            try:
                last_join = datetime.fromisoformat(voice['last_join'])
                date_key = last_join.strftime("%Y-%m-%d")
                if date_key in daily:
                    daily[date_key] += voice.get('count', 0)
            except:
                pass
    
    return daily

