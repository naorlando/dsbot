"""
Módulo de persistencia de datos
Maneja carga y guardado de config.json y stats.json
"""

import json
import os
from pathlib import Path

# Usar /data si existe (Railway Volume), sino local
DATA_DIR = Path('/data') if Path('/data').exists() else Path('.')
CONFIG_FILE = DATA_DIR / 'config.json'
STATS_FILE = DATA_DIR / 'stats.json'

# Variables globales compartidas
config = None
stats = None

def load_config():
    """Carga la configuración desde config.json"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Configuración por defecto
        default_config = {
            "channel_id": None,
            "stats_channel_id": None,
            "notify_games": True,
            "notify_game_end": False,
            "notify_voice": True,
            "notify_voice_leave": False,
            "notify_voice_move": True,
            "notify_member_join": False,
            "notify_member_leave": False,
            "ignore_bots": True,
            "game_activity_types": ["playing", "streaming", "watching", "listening"],
            "game_min_duration_seconds": 10,
            "blacklisted_app_ids": [],
            "game_session": {
                "grace_period_seconds": 900
            },
            "messages": {
                "game_start": "🎮 **{user}** está {verb} **{activity}**",
                "game_end": "🎮 **{user}** dejó de jugar **{game}**",
                "voice_join": "🔊 **{user}** entró al canal de voz **{channel}**",
                "voice_leave": "🔇 **{user}** salió del canal de voz **{channel}**",
                "voice_move": "🔄 **{user}** cambió de **{old_channel}** a **{new_channel}**",
                "member_join": "👋 **{user}** se unió al servidor",
                "member_leave": "👋 **{user}** dejó el servidor"
            },
            "rate_limiting": {
                "max_retries": 5,
                "initial_delay": 30,
                "max_delay": 300,
                "exponential_base": 2
            },
            "party_detection": {
                "enabled": True,
                "min_players": 2,
                "grace_period_seconds": 1800,
                "notify_on_formed": True,
                "notify_on_join": True,
                "cooldown_minutes": 60,
                "reactivation_window_minutes": 45,
                "suppress_join_notifications_for_games": [
                    "League of Legends"
                ],
                "notification_key_aliases": {
                    "league-of-legends": [
                        "League of Legends",
                        "LoL"
                    ]
                },
                "use_here_mention": True,
                "blacklisted_games": [
                    "Spotify",
                    "YouTube",
                    "Chrome",
                    "Visual Studio Code"
                ],
                "message_template_formed": "🎮 {mention}¡Party de **{game}** formada! {players} están jugando juntos",
                "message_template_join": "🎮 {mention}{players} {verb} a la party de **{game}** ({total} jugadores)"
            }
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config

def load_stats():
    """Carga las estadísticas desde stats.json"""
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            'users': {},
            'cooldowns': {}
        }

def save_stats():
    """Guarda las estadísticas en disco"""
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

def save_config():
    """Guarda la configuración en disco"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def get_channel_id():
    """Obtiene el channel_id con prioridad: ENV > config.json"""
    # Prioridad 1: Variable de entorno (nunca se pierde)
    env_channel = os.getenv('DISCORD_CHANNEL_ID')
    if env_channel:
        return int(env_channel)
    
    # Prioridad 2: config.json persistente
    return config.get('channel_id')

def get_stats_channel_id():
    """Obtiene el stats_channel_id con prioridad: ENV > config.json"""
    # Prioridad 1: Variable de entorno
    env_channel = os.getenv('DISCORD_STATS_CHANNEL_ID')
    if env_channel:
        return int(env_channel)
    
    # Prioridad 2: config.json persistente
    return config.get('stats_channel_id')

# Inicializar al importar
config = load_config()
stats = load_stats()

