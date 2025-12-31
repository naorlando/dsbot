# 🔧 Implementación Técnica: Wrapped Completo

## 📋 Resumen Ejecutivo

### **Archivos a Modificar/Crear:**
- ✏️ Modificar: 3 archivos existentes
- ✨ Crear: 4 archivos nuevos
- 📊 Migración: 1 script de datos históricos

### **Esfuerzo Estimado:**
- **Básico (70% métricas):** 2-3 días
- **Premium (100% métricas):** 5-7 días
- **Total con tests y polish:** 10 días

---

## 🎯 FASE 1: WRAPPED BÁSICO (Solo con datos actuales)

### **Archivos a CREAR:**

#### **1. `stats/commands/wrapped.py` (NUEVO)**
```python
"""
Comando !wrapped - Resumen anual del usuario
"""
import discord
from discord.ext import commands
from datetime import datetime
from typing import Dict, List, Tuple
from core.persistence import stats, STATS_FILE
from stats.visualization.formatters import format_time
from stats.data.aggregators import (
    aggregate_user_game_time,
    aggregate_user_voice_time
)

@commands.command(name='wrapped')
async def wrapped(ctx, usuario: discord.Member = None, año: int = None):
    """
    🎁 Tu año en Discord (Wrapped)
    
    Uso:
        !wrapped              → Tu wrapped del año actual
        !wrapped @usuario     → Wrapped de otro usuario
        !wrapped @usuario 2024 → Wrapped de un año específico
    
    Ejemplo: !wrapped @Pino 2025
    """
    # Determinar usuario (si no se especifica, usar quien ejecuta el comando)
    target_user = usuario if usuario else ctx.author
    
    # Determinar año (si no se especifica, usar año actual)
    target_year = año if año else datetime.now().year
    
    # Cargar datos
    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        stats_data = json.load(f)
    
    user_id = str(target_user.id)
    
    # Verificar que el usuario tenga datos
    if user_id not in stats_data.get('users', {}):
        await ctx.send(f"❌ {target_user.display_name} no tiene estadísticas registradas.")
        return
    
    # Generar wrapped
    wrapped_embed = generate_wrapped_embed(stats_data, user_id, target_user.display_name, target_year)
    
    await ctx.send(embed=wrapped_embed)


def generate_wrapped_embed(stats_data: Dict, user_id: str, username: str, year: int) -> discord.Embed:
    """
    Genera el embed del wrapped completo
    """
    user_data = stats_data['users'][user_id]
    
    # Crear embed principal
    embed = discord.Embed(
        title=f"🎁 {username} en Discord {year}",
        description="Tu año resumido",
        color=0x9b59b6  # Púrpura
    )
    
    # === GAMING ===
    gaming_stats = _calculate_gaming_stats(user_data, year)
    if gaming_stats:
        gaming_text = (
            f"🎮 **{gaming_stats['total_hours']}h** jugadas\n"
            f"🏆 Tu juego: **{gaming_stats['top_game']}** ({gaming_stats['top_game_hours']}h)\n"
            f"📊 {gaming_stats['unique_games']} juegos diferentes\n"
            f"🔥 Racha: {gaming_stats['longest_streak']} días\n"
            f"📅 Día más gamer: {gaming_stats['best_day']}"
        )
        embed.add_field(name="🎮 GAMING", value=gaming_text, inline=False)
    
    # === VOICE ===
    voice_stats = _calculate_voice_stats(user_data, year)
    if voice_stats:
        voice_text = (
            f"🔊 **{voice_stats['total_hours']}h** en voice\n"
            f"📊 {voice_stats['sessions']} sesiones\n"
            f"⏱️ Promedio: {voice_stats['avg_session']}h/sesión\n"
            f"🏆 Maratón: {voice_stats['longest_session']}h"
        )
        embed.add_field(name="🔊 VOICE", value=voice_text, inline=False)
    
    # === PARTIES ===
    party_stats = _calculate_party_stats(stats_data, user_id, year)
    if party_stats:
        party_text = (
            f"🎉 **{party_stats['total_parties']}** parties jugadas\n"
            f"🏆 Juego más social: **{party_stats['top_game']}**\n"
            f"⏱️ Party más larga: {party_stats['longest_party']}h\n"
            f"👥 Tu squad: {party_stats['best_partner']}"
        )
        embed.add_field(name="🎉 PARTIES", value=party_text, inline=False)
    
    # === SOCIAL ===
    social_stats = _calculate_social_stats(user_data)
    if social_stats:
        social_text = (
            f"💬 **{social_stats['messages']:,}** mensajes\n"
            f"❤️ {social_stats['reactions']} reacciones\n"
            f"🎨 {social_stats['stickers']} stickers\n"
            f"😊 Tu emoji: {social_stats['top_emoji']}"
        )
        embed.add_field(name="💬 SOCIAL", value=social_text, inline=False)
    
    # === PERSONALIDAD ===
    personality = _detect_personality(user_data, gaming_stats, party_stats)
    personality_text = "\n".join([f"{icon} {trait}" for icon, trait in personality])
    embed.add_field(name="🎨 TU PERSONALIDAD", value=personality_text, inline=False)
    
    # === RANKINGS ===
    rankings = _calculate_rankings(stats_data, user_id)
    rankings_text = (
        f"🏆 #{rankings['gaming']} en Gaming\n"
        f"💬 #{rankings['social']} en Social\n"
        f"🎉 #{rankings['parties']} en Parties"
    )
    embed.add_field(name="🏆 RANKINGS", value=rankings_text, inline=False)
    
    embed.set_footer(text=f"Wrapped generado el {datetime.now().strftime('%d/%m/%Y')}")
    
    return embed


def _calculate_gaming_stats(user_data: Dict, year: int) -> Dict:
    """
    Calcula estadísticas de gaming para el wrapped
    """
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
        'best_day': f"{best_day[0]} ({round(best_day[1] / 60, 1)}h)",
        'avg_session': round((total_minutes / sum(g['count'] for g in games_filtered.values())) / 60, 1) if games_filtered else 0
    }


def _calculate_longest_streak(games_filtered: Dict) -> int:
    """
    Calcula la racha más larga de días consecutivos jugando (cualquier juego)
    """
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


def _calculate_voice_stats(user_data: Dict, year: int) -> Dict:
    """
    Calcula estadísticas de voice para el wrapped
    """
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


def _calculate_party_stats(stats_data: Dict, user_id: str, year: int) -> Dict:
    """
    Calcula estadísticas de parties para el wrapped
    """
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
        best_partner = "Jugaste solo"
    
    return {
        'total_parties': len(user_parties),
        'top_game': top_game,
        'longest_party': longest_hours,
        'best_partner': best_partner
    }


def _calculate_social_stats(user_data: Dict) -> Dict:
    """
    Calcula estadísticas sociales para el wrapped
    """
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
        'top_emoji': f"{top_emoji[0]} ({top_emoji[1]} veces)"
    }


def _detect_personality(user_data: Dict, gaming_stats: Dict, party_stats: Dict) -> List[Tuple[str, str]]:
    """
    Detecta la personalidad del usuario basado en sus stats
    """
    personality = []
    
    if not gaming_stats:
        return [("🤷", "Sin datos suficientes")]
    
    # Maratonero vs Casual
    avg_session = gaming_stats.get('avg_session', 0)
    if avg_session >= 3:
        personality.append(("🏃", "Maratonero"))
    elif avg_session < 1:
        personality.append(("🎲", "Casual"))
    
    # Social vs Loner
    if party_stats:
        total_parties = party_stats.get('total_parties', 0)
        if total_parties > 30:
            personality.append(("👥", "Social Butterfly"))
        elif total_parties < 5:
            personality.append(("🦅", "Loner"))
    
    # Fidelidad vs Explorer
    unique_games = gaming_stats.get('unique_games', 0)
    if unique_games >= 10:
        personality.append(("🗺️", "Explorer"))
    elif unique_games <= 3:
        personality.append(("💎", "Fiel a sus juegos"))
    
    # Racha
    longest_streak = gaming_stats.get('longest_streak', 0)
    if longest_streak >= 14:
        personality.append(("🔥", "Constante"))
    
    return personality if personality else [("🎮", "Gamer")]


def _calculate_rankings(stats_data: Dict, user_id: str) -> Dict:
    """
    Calcula rankings del usuario en el servidor
    """
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
```

**Tamaño:** ~400 líneas  
**Esfuerzo:** 1 día (con tests)

---

#### **2. `stats/__init__.py` (MODIFICAR)**

Agregar línea:
```python
from stats.commands.wrapped import setup_wrapped_commands

# En el init del paquete
__all__ = [
    'setup_rankings_commands',
    'setup_games_commands',
    'setup_parties_commands',
    'setup_user_commands',
    'setup_social_commands',
    'setup_utils_commands',
    'setup_wrapped_commands',  # ← NUEVO
]
```

---

#### **3. `cogs/stats.py` (MODIFICAR)**

Agregar en `__init__`:
```python
from stats import (
    # ... imports existentes ...
    setup_wrapped_commands,  # ← NUEVO
)

class StatsCog(commands.Cog):
    def __init__(self, bot):
        # ... código existente ...
        setup_wrapped_commands(bot)  # ← NUEVO
        logger.info("✓ Wrapped cargado")
```

---

#### **4. `test_wrapped.py` (NUEVO)**

```python
"""
Tests para el comando !wrapped
"""
import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
from datetime import datetime
from stats.commands.wrapped import (
    _calculate_gaming_stats,
    _calculate_voice_stats,
    _calculate_party_stats,
    _calculate_social_stats,
    _detect_personality,
    _calculate_longest_streak,
    _calculate_rankings
)

class TestWrappedCalculations(unittest.TestCase):
    def setUp(self):
        self.mock_user_data = {
            'games': {
                'League of Legends': {
                    'count': 50,
                    'total_minutes': 3000,
                    'daily_minutes': {
                        '2025-01-15': 120,
                        '2025-01-16': 180,
                        '2025-01-17': 90
                    }
                },
                'Valorant': {
                    'count': 30,
                    'total_minutes': 1800,
                    'daily_minutes': {
                        '2025-02-10': 60,
                        '2025-02-11': 90
                    }
                }
            },
            'voice': {
                'count': 25,
                'total_minutes': 1500,
                'daily_minutes': {
                    '2025-03-01': 60,
                    '2025-03-02': 90
                }
            },
            'messages': {'count': 1000, 'characters': 25000},
            'reactions': {'total': 250, 'by_emoji': {'👍': 100, '❤️': 80}},
            'stickers': {'total': 50}
        }
    
    def test_calculate_gaming_stats(self):
        """Test cálculo de stats de gaming"""
        stats = _calculate_gaming_stats(self.mock_user_data, 2025)
        
        self.assertIsNotNone(stats)
        self.assertIn('total_hours', stats)
        self.assertIn('top_game', stats)
        self.assertEqual(stats['top_game'], 'League of Legends')
    
    def test_calculate_longest_streak(self):
        """Test cálculo de racha más larga"""
        games_filtered = {
            'LoL': {
                'daily_minutes': {
                    '2025-01-15': 120,
                    '2025-01-16': 180,
                    '2025-01-17': 90
                }
            }
        }
        streak = _calculate_longest_streak(games_filtered)
        self.assertEqual(streak, 3)
    
    def test_detect_personality_maratonero(self):
        """Test detector de personalidad: Maratonero"""
        gaming_stats = {'avg_session': 3.5, 'unique_games': 5, 'longest_streak': 15}
        party_stats = {'total_parties': 40}
        
        personality = _detect_personality(self.mock_user_data, gaming_stats, party_stats)
        
        self.assertTrue(any("Maratonero" in trait for _, trait in personality))
    
    # ... más tests ...

if __name__ == '__main__':
    unittest.main()
```

**Esfuerzo:** 0.5 día

---

### **TOTAL FASE 1: 2-3 días** ✅

**Resultado:** Wrapped funcional con 70% de métricas

---

## ⭐ FASE 2: WRAPPED PREMIUM (Agregar datos faltantes)

### **Nuevos campos en stats.json:**

```json
{
  "users": {
    "user_id": {
      "games": {
        "League of Legends": {
          // ✅ Existentes
          "count": 150,
          "total_minutes": 7800,
          "daily_minutes": {...},
          
          // ✨ NUEVOS
          "by_month": {
            "2025-01": 450,
            "2025-02": 380,
            "2025-12": 620
          },
          "by_hour": {
            "20": 450,
            "21": 520,
            "22": 380
          },
          "consecutive_days_record": 15,
          "days_played": 62
        }
      },
      
      "voice": {
        // ✅ Existentes
        "count": 85,
        "total_minutes": 3600,
        "daily_minutes": {...},
        
        // ✨ NUEVOS
        "by_month": {
          "2025-01": 950,
          "2025-12": 880
        },
        "by_hour": {
          "20": 450,
          "21": 520
        },
        "consecutive_days_record": 12
      },
      
      // ✨ NUEVO: Stats de parties POR USUARIO
      "parties": {
        "total_parties": 45,
        "total_minutes": 1140,
        "by_game": {
          "League of Legends": {
            "count": 25,
            "minutes": 680
          }
        },
        "partners": {
          "other_user_id": 25,
          "another_user_id": 18
        },
        "longest_party_minutes": 480,
        "largest_party_players": 5
      },
      
      // ✨ NUEVO: Totales anuales
      "yearly_totals": {
        "2025": {
          "games_minutes": 25000,
          "voice_minutes": 15000,
          "messages": 8542,
          "parties": 45
        },
        "2024": {
          "games_minutes": 18000,
          "voice_minutes": 12000,
          "messages": 6200,
          "parties": 32
        }
      }
    }
  },
  
  // ✨ NUEVO: Stats globales del servidor
  "server": {
    "yearly_totals": {
      "2025": {
        "total_game_minutes": 150000,
        "total_voice_minutes": 108000,
        "total_messages": 52000,
        "total_parties": 234
      }
    },
    "records": {
      "longest_party": {
        "game": "Minecraft",
        "minutes": 480,
        "players": ["user1", "user2"],
        "date": "2025-08-15"
      },
      "largest_party": {
        "game": "Valorant",
        "players": 8,
        "date": "2025-07-20"
      },
      "most_active_day": {
        "date": "2025-07-20",
        "total_minutes": 1850
      }
    }
  }
}
```

---

### **Archivos a MODIFICAR:**

#### **1. `core/session_dto.py` (MODIFICAR)**

**Agregar funciones:**

```python
from datetime import datetime

def _get_month_key(timestamp: datetime = None) -> str:
    """Helper para obtener clave de mes (YYYY-MM)"""
    dt = timestamp if timestamp else datetime.now()
    return dt.strftime('%Y-%m')

def _get_hour_key(timestamp: datetime = None) -> int:
    """Helper para obtener hora (0-23)"""
    dt = timestamp if timestamp else datetime.now()
    return dt.hour


# Modificar save_game_time para agregar by_month y by_hour
def save_game_time(user_id: str, username: str, game_name: str, minutes: int, timestamp: datetime = None):
    """
    Guarda tiempo jugado (MODIFICADO para agregar by_month y by_hour)
    
    Args:
        user_id: ID del usuario
        username: Nombre del usuario
        game_name: Nombre del juego
        minutes: Minutos jugados
        timestamp: Timestamp de la sesión (para calcular month/hour)
    """
    _ensure_user_exists(user_id, username)
    
    # Asegurar estructura del juego
    if game_name not in stats['users'][user_id]['games']:
        stats['users'][user_id]['games'][game_name] = {
            'count': 0,
            'total_minutes': 0,
            'daily_minutes': {},
            'by_month': {},        # ← NUEVO
            'by_hour': {},          # ← NUEVO
            'last_played': None,
            'sessions': []
        }
    
    game_data = stats['users'][user_id]['games'][game_name]
    
    # Actualizar totales
    game_data['total_minutes'] += minutes
    
    # Actualizar por día
    today = datetime.now().strftime('%Y-%m-%d')
    game_data['daily_minutes'][today] = game_data['daily_minutes'].get(today, 0) + minutes
    
    # ✨ NUEVO: Actualizar por mes
    month_key = _get_month_key(timestamp)
    game_data['by_month'][month_key] = game_data['by_month'].get(month_key, 0) + minutes
    
    # ✨ NUEVO: Actualizar por hora (distribuir proporcionalmente)
    if timestamp:
        # Registrar en la hora de inicio de la sesión
        hour_key = str(_get_hour_key(timestamp))
        game_data['by_hour'][hour_key] = game_data['by_hour'].get(hour_key, 0) + minutes
    
    # Actualizar fecha de última sesión
    game_data['last_played'] = datetime.now().isoformat()
    
    save_stats()
    logger.debug(f'💾 Tiempo guardado: {username} jugó {game_name} por {minutes} min')


# Modificar save_voice_time para agregar by_month y by_hour
def save_voice_time(user_id: str, username: str, minutes: int, channel_name: str, timestamp: datetime = None):
    """
    Guarda tiempo en voice (MODIFICADO para agregar by_month y by_hour)
    """
    _ensure_user_exists(user_id, username)
    
    voice_data = stats['users'][user_id]['voice']
    
    # Actualizar totales
    voice_data['total_minutes'] = voice_data.get('total_minutes', 0) + minutes
    
    # Actualizar por día
    today = datetime.now().strftime('%Y-%m-%d')
    voice_data['daily_minutes'][today] = voice_data['daily_minutes'].get(today, 0) + minutes
    
    # ✨ NUEVO: Actualizar por mes
    month_key = _get_month_key(timestamp)
    if 'by_month' not in voice_data:
        voice_data['by_month'] = {}
    voice_data['by_month'][month_key] = voice_data['by_month'].get(month_key, 0) + minutes
    
    # ✨ NUEVO: Actualizar por hora
    if timestamp:
        if 'by_hour' not in voice_data:
            voice_data['by_hour'] = {}
        hour_key = str(_get_hour_key(timestamp))
        voice_data['by_hour'][hour_key] = voice_data['by_hour'].get(hour_key, 0) + minutes
    
    save_stats()
    logger.debug(f'💾 Tiempo de voz guardado: {username} - {minutes} min en {channel_name}')


# ✨ NUEVO: Función para actualizar stats de parties por usuario
def update_user_party_stats(user_id: str, username: str, game_name: str, party_minutes: int, 
                            other_players: List[str], max_players: int):
    """
    Actualiza las estadísticas de parties para un usuario específico
    
    Args:
        user_id: ID del usuario
        username: Nombre del usuario
        game_name: Nombre del juego
        party_minutes: Duración de la party en minutos
        other_players: Lista de IDs de otros jugadores
        max_players: Número máximo de jugadores en la party
    """
    _ensure_user_exists(user_id, username)
    
    # Asegurar estructura de parties
    if 'parties' not in stats['users'][user_id]:
        stats['users'][user_id]['parties'] = {
            'total_parties': 0,
            'total_minutes': 0,
            'by_game': {},
            'partners': {},
            'longest_party_minutes': 0,
            'largest_party_players': 0
        }
    
    party_data = stats['users'][user_id]['parties']
    
    # Actualizar totales
    party_data['total_parties'] += 1
    party_data['total_minutes'] += party_minutes
    
    # Actualizar por juego
    if game_name not in party_data['by_game']:
        party_data['by_game'][game_name] = {'count': 0, 'minutes': 0}
    
    party_data['by_game'][game_name]['count'] += 1
    party_data['by_game'][game_name]['minutes'] += party_minutes
    
    # Actualizar partners
    for partner_id in other_players:
        party_data['partners'][partner_id] = party_data['partners'].get(partner_id, 0) + 1
    
    # Actualizar récords
    party_data['longest_party_minutes'] = max(party_data['longest_party_minutes'], party_minutes)
    party_data['largest_party_players'] = max(party_data['largest_party_players'], max_players)
    
    save_stats()
    logger.debug(f'💾 Party stats actualizadas: {username} - {game_name}')


# ✨ NUEVO: Función para actualizar totales anuales
def update_yearly_totals(year: int = None):
    """
    Actualiza los totales anuales para todos los usuarios
    Llamar al final de cada año o bajo demanda
    """
    target_year = year if year else datetime.now().year
    year_key = str(target_year)
    
    for user_id, user_data in stats['users'].items():
        # Asegurar estructura
        if 'yearly_totals' not in user_data:
            user_data['yearly_totals'] = {}
        
        if year_key not in user_data['yearly_totals']:
            user_data['yearly_totals'][year_key] = {
                'games_minutes': 0,
                'voice_minutes': 0,
                'messages': 0,
                'parties': 0
            }
        
        yearly = user_data['yearly_totals'][year_key]
        
        # Calcular games
        games_minutes = 0
        for game_data in user_data.get('games', {}).values():
            by_month = game_data.get('by_month', {})
            games_minutes += sum(
                minutes for month, minutes in by_month.items()
                if month.startswith(year_key)
            )
        yearly['games_minutes'] = games_minutes
        
        # Calcular voice
        voice_data = user_data.get('voice', {})
        by_month = voice_data.get('by_month', {})
        yearly['voice_minutes'] = sum(
            minutes for month, minutes in by_month.items()
            if month.startswith(year_key)
        )
        
        # Messages (ya es total acumulado, no por año)
        yearly['messages'] = user_data.get('messages', {}).get('count', 0)
        
        # Parties
        yearly['parties'] = user_data.get('parties', {}).get('total_parties', 0)
    
    save_stats()
    logger.info(f'💾 Totales anuales actualizados para {year_key}')
```

**Tamaño:** +200 líneas  
**Esfuerzo:** 1 día

---

#### **2. `core/game_session.py` (MODIFICAR)**

Pasar timestamp al `save_game_time`:

```python
async def handle_game_end(self, member: discord.Member, game_name: str, config: dict):
    # ... código existente ...
    
    if session.is_confirmed:
        # ... código existente ...
        
        # ✨ MODIFICADO: Pasar start_time como timestamp
        save_game_time(user_id, member.display_name, game_name, minutes, timestamp=session.start_time)
```

**Esfuerzo:** 0.5 hora

---

#### **3. `core/voice_session.py` (MODIFICAR)**

Pasar timestamp al `save_voice_time`:

```python
async def handle_end(self, member: discord.Member, channel: discord.VoiceChannel, config: dict):
    # ... código existente ...
    
    if session.is_confirmed:
        # ... código existente ...
        
        # ✨ MODIFICADO: Pasar start_time como timestamp
        save_voice_time(user_id, member.display_name, minutes, channel_name, timestamp=session.start_time)
```

**Esfuerzo:** 0.5 hora

---

#### **4. `core/party_session.py` (MODIFICAR)**

Actualizar stats de parties por usuario:

```python
from core.session_dto import update_user_party_stats

def _finalize_party_in_stats(self, game_name: str, session: PartySession):
    """Finaliza una party en stats"""
    # ... código existente ...
    
    # ✨ NUEVO: Actualizar stats de parties por cada usuario
    for player_id in session.player_ids:
        other_players = [pid for pid in session.player_ids if pid != player_id]
        player_name = stats['users'].get(player_id, {}).get('username', 'Unknown')
        
        update_user_party_stats(
            user_id=player_id,
            username=player_name,
            game_name=game_name,
            party_minutes=round(duration_seconds / 60),
            other_players=other_players,
            max_players=session.max_players
        )
```

**Esfuerzo:** 1 hora

---

#### **5. `scripts/migrate_historical_data.py` (NUEVO)**

Script para migrar datos históricos:

```python
"""
Script para migrar datos históricos a la nueva estructura
Calcula by_month, by_hour, yearly_totals desde daily_minutes existentes
"""

import json
from datetime import datetime
from pathlib import Path

STATS_FILE = Path('/data/stats.json') if Path('/data').exists() else Path('./stats.json')

def migrate_data():
    """Migra datos históricos a nueva estructura"""
    print("📊 Iniciando migración de datos históricos...")
    
    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        stats = json.load(f)
    
    migrated_users = 0
    
    for user_id, user_data in stats['users'].items():
        # Migrar games
        for game_name, game_data in user_data.get('games', {}).items():
            daily_minutes = game_data.get('daily_minutes', {})
            
            # Calcular by_month
            by_month = {}
            for date_str, minutes in daily_minutes.items():
                month_key = date_str[:7]  # YYYY-MM
                by_month[month_key] = by_month.get(month_key, 0) + minutes
            
            game_data['by_month'] = by_month
            
            # by_hour no se puede calcular (falta timestamp), inicializar vacío
            game_data['by_hour'] = {}
            
            print(f"  ✓ Migrado {game_name} para {user_data.get('username', user_id)}")
        
        # Migrar voice
        voice_data = user_data.get('voice', {})
        daily_minutes = voice_data.get('daily_minutes', {})
        
        by_month = {}
        for date_str, minutes in daily_minutes.items():
            month_key = date_str[:7]
            by_month[month_key] = by_month.get(month_key, 0) + minutes
        
        voice_data['by_month'] = by_month
        voice_data['by_hour'] = {}
        
        # Inicializar parties si no existe
        if 'parties' not in user_data:
            user_data['parties'] = {
                'total_parties': 0,
                'total_minutes': 0,
                'by_game': {},
                'partners': {},
                'longest_party_minutes': 0,
                'largest_party_players': 0
            }
        
        # Calcular yearly_totals
        user_data['yearly_totals'] = {}
        years = set()
        
        # Obtener años de games
        for game_data in user_data.get('games', {}).values():
            for month in game_data.get('by_month', {}).keys():
                years.add(month[:4])
        
        for year in years:
            games_minutes = sum(
                minutes
                for game_data in user_data.get('games', {}).values()
                for month, minutes in game_data.get('by_month', {}).items()
                if month.startswith(year)
            )
            
            voice_minutes = sum(
                minutes
                for month, minutes in voice_data.get('by_month', {}).items()
                if month.startswith(year)
            )
            
            user_data['yearly_totals'][year] = {
                'games_minutes': games_minutes,
                'voice_minutes': voice_minutes,
                'messages': user_data.get('messages', {}).get('count', 0),
                'parties': user_data.get('parties', {}).get('total_parties', 0)
            }
        
        migrated_users += 1
    
    # Agregar estructura de servidor si no existe
    if 'server' not in stats:
        stats['server'] = {
            'yearly_totals': {},
            'records': {}
        }
    
    # Guardar
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Migración completada: {migrated_users} usuarios migrados")

if __name__ == '__main__':
    migrate_data()
```

**Esfuerzo:** 0.5 día

---

#### **6. Actualizar `stats/commands/wrapped.py`**

Agregar métricas premium:
- Mes más gamer (from `by_month`)
- Horario pico (from `by_hour`)
- Comparación anual (from `yearly_totals`)
- % del servidor (from `server.yearly_totals`)

**Esfuerzo:** 1 día

---

### **TOTAL FASE 2: 4-5 días** ⭐

**Resultado:** Wrapped completo con 100% de métricas

---

## 📊 RESUMEN DE IMPACTO

### **Storage:**
- **Wrapped básico:** +0 KB (usa datos existentes)
- **Wrapped premium:** +50-100 KB por usuario/año

**Ejemplo para 10 usuarios activos:**
- `by_month`: ~120 bytes/juego/año
- `by_hour`: ~300 bytes/juego/año
- `parties`: ~500 bytes/usuario
- `yearly_totals`: ~150 bytes/usuario/año

**Total estimado:** +10-15 KB/usuario activo = ~150 KB para 10 usuarios

### **Performance:**
- **Wrapped básico:** ~100-200ms (cálculo on-demand)
- **Wrapped premium:** ~200-400ms (más datos a procesar)
- **Migración:** ~5-10 segundos (una sola vez)

### **Mantenimiento:**
- **Wrapped básico:** Bajo (solo usa datos existentes)
- **Wrapped premium:** Medio (nuevas agregaciones en tiempo real)

---

## 🎯 PLAN RECOMENDADO

### **Opción A: Implementar TODO de una vez**
- **Tiempo:** 10 días
- **Ventaja:** Feature completo desde el inicio
- **Desventaja:** No hay feedback intermedio

### **Opción B: Implementar por fases** ⭐ RECOMENDADO
- **Fase 1 (básico):** 3 días → Deploy y feedback
- **Fase 2 (premium):** 5 días → Deploy completo
- **Ventaja:** Feedback temprano, iteración basada en uso real
- **Desventaja:** 2 deploys

---

## ✅ RESUMEN DE ARCHIVOS

### **Crear:**
1. ✨ `stats/commands/wrapped.py` (~400 líneas)
2. ✨ `test_wrapped.py` (~200 líneas)
3. ✨ `scripts/migrate_historical_data.py` (~100 líneas)

### **Modificar:**
1. ✏️ `core/session_dto.py` (+200 líneas)
2. ✏️ `core/game_session.py` (+2 líneas)
3. ✏️ `core/voice_session.py` (+2 líneas)
4. ✏️ `core/party_session.py` (+20 líneas)
5. ✏️ `stats/__init__.py` (+2 líneas)
6. ✏️ `cogs/stats.py` (+2 líneas)

**Total:** ~1000 líneas de código nuevo/modificado

---

**¿Empezamos con la Fase 1 (básico) o querés ver más detalles de alguna parte específica?** 🚀

