import discord
from discord.ext import commands
import json
import os
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('dsbot')

# Usar /data si existe (Railway Volume), sino local
DATA_DIR = Path('/data') if Path('/data').exists() else Path('.')
CONFIG_FILE = DATA_DIR / 'config.json'
STATS_FILE = DATA_DIR / 'stats.json'

# Cargar configuración
def load_config():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Configuración por defecto
        default_config = {
            "channel_id": None,
            "notify_games": True,
            "notify_voice": True,
            "notify_voice_leave": False,
            "notify_voice_move": True,
            "notify_member_join": False,
            "notify_member_leave": False,
            "ignore_bots": True,
            "game_activity_types": ["playing", "streaming", "watching", "listening"],
            "messages": {
                "game_start": "🎮 **{user}** está {verb} **{activity}**",
                "voice_join": "🔊 **{user}** entró al canal de voz **{channel}**",
                "voice_leave": "🔇 **{user}** salió del canal de voz **{channel}**",
                "voice_move": "🔄 **{user}** cambió de **{old_channel}** a **{new_channel}**",
                "member_join": "👋 **{user}** se unió al servidor",
                "member_leave": "👋 **{user}** dejó el servidor"
            }
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config

config = load_config()

# Cargar estadísticas
def load_stats():
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            'users': {},
            'cooldowns': {}
        }

stats = load_stats()

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

def check_cooldown(user_id, event_key):
    """
    Verifica si pasaron 10 minutos desde el último evento similar.
    Retorna True si puede registrar el evento, False si está en cooldown.
    """
    cooldown_key = f"{user_id}:{event_key}"
    last_time_str = stats['cooldowns'].get(cooldown_key)
    
    if last_time_str:
        try:
            last_time = datetime.fromisoformat(last_time_str)
            if datetime.now() - last_time < timedelta(minutes=10):
                logger.debug(f'Cooldown activo para {cooldown_key}')
                return False
        except ValueError:
            pass
    
    # Actualizar cooldown
    stats['cooldowns'][cooldown_key] = datetime.now().isoformat()
    save_stats()
    return True

def record_game_event(user_id, username, game_name):
    """Registra un evento de juego en las estadísticas"""
    if user_id not in stats['users']:
        stats['users'][user_id] = {
            'username': username,
            'games': {},
            'voice': {'count': 0, 'last_join': None}
        }
    
    if game_name not in stats['users'][user_id]['games']:
        stats['users'][user_id]['games'][game_name] = {
            'count': 0,
            'first_played': datetime.now().isoformat(),
            'last_played': None
        }
    
    # Asegurar que tiene todos los campos nuevos
    game_data = stats['users'][user_id]['games'][game_name]
    if 'total_minutes' not in game_data:
        game_data['total_minutes'] = 0
    if 'daily_minutes' not in game_data:
        game_data['daily_minutes'] = {}
    if 'current_session' not in game_data:
        game_data['current_session'] = None
    
    stats['users'][user_id]['games'][game_name]['count'] += 1
    stats['users'][user_id]['games'][game_name]['last_played'] = datetime.now().isoformat()
    stats['users'][user_id]['username'] = username
    save_stats()
    
    logger.info(f'📊 Stats: {username} jugó {game_name} ({stats["users"][user_id]["games"][game_name]["count"]} veces)')

def is_link_spam(message_content):
    """Detecta si un mensaje es principalmente links/URLs
    
    Args:
        message_content: Contenido del mensaje
        
    Returns:
        True si el mensaje es spam de links, False si es contenido válido
    """
    import re
    
    if not message_content or len(message_content) == 0:
        return True
    
    # Regex para detectar URLs
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, message_content, re.IGNORECASE)
    
    # Si no hay URLs, no es spam
    if not urls:
        return False
    
    # Calcular longitud total de URLs
    url_length = sum(len(url) for url in urls)
    
    # Si las URLs ocupan más del 70% del mensaje, considerarlo spam
    if url_length / len(message_content) > 0.7:
        return True
    
    # Si el mensaje tiene solo 1-2 palabras además del link, considerarlo spam
    content_without_urls = message_content
    for url in urls:
        content_without_urls = content_without_urls.replace(url, '')
    
    # Contar palabras reales (sin URLs)
    words = [w for w in content_without_urls.split() if len(w) > 0]
    if len(words) <= 2:
        return True
    
    return False

def record_message_event(user_id, username, message_length):
    """Registra un mensaje en las estadísticas"""
    if user_id not in stats['users']:
        stats['users'][user_id] = {
            'username': username,
            'games': {},
            'voice': {'count': 0, 'last_join': None, 'total_minutes': 0, 'daily_minutes': {}},
            'messages': {'count': 0, 'characters': 0, 'last_message': None}
        }
    
    # Asegurar que existe la estructura de mensajes
    if 'messages' not in stats['users'][user_id]:
        stats['users'][user_id]['messages'] = {'count': 0, 'characters': 0, 'last_message': None}
    
    stats['users'][user_id]['messages']['count'] += 1
    stats['users'][user_id]['messages']['characters'] += message_length
    stats['users'][user_id]['messages']['last_message'] = datetime.now().isoformat()
    stats['users'][user_id]['username'] = username
    
    save_stats()
    
    # Log solo cada 10 mensajes para no spamear logs
    if stats['users'][user_id]['messages']['count'] % 10 == 0:
        logger.debug(f'📊 Stats: {username} - {stats["users"][user_id]["messages"]["count"]} mensajes, {stats["users"][user_id]["messages"]["characters"]} chars')

def start_game_session(user_id, username, game_name):
    """Inicia una sesión de juego para tracking de tiempo"""
    if user_id not in stats['users']:
        stats['users'][user_id] = {
            'username': username,
            'games': {},
            'voice': {'count': 0, 'last_join': None}
        }
    
    if game_name not in stats['users'][user_id]['games']:
        stats['users'][user_id]['games'][game_name] = {
            'count': 0,
            'first_played': datetime.now().isoformat(),
            'last_played': None,
            'total_minutes': 0,
            'daily_minutes': {},
            'current_session': None
        }
    
    # Guardar sesión actual
    stats['users'][user_id]['games'][game_name]['current_session'] = {
        'start': datetime.now().isoformat()
    }
    stats['users'][user_id]['username'] = username
    
    save_stats()
    logger.debug(f'🕐 Sesión de juego iniciada: {username} - {game_name}')

def end_game_session(user_id, username, game_name):
    """Finaliza una sesión de juego y calcula el tiempo"""
    if user_id not in stats['users']:
        return
    
    if game_name not in stats['users'][user_id]['games']:
        return
    
    game_data = stats['users'][user_id]['games'][game_name]
    current_session = game_data.get('current_session')
    
    if not current_session:
        return
    
    try:
        start_time = datetime.fromisoformat(current_session['start'])
        end_time = datetime.now()
        duration = end_time - start_time
        minutes = int(duration.total_seconds() / 60)
        
        # Solo contar si jugó más de 1 minuto
        if minutes >= 1:
            # Actualizar total
            game_data['total_minutes'] = game_data.get('total_minutes', 0) + minutes
            
            # Actualizar daily
            today = datetime.now().strftime('%Y-%m-%d')
            if 'daily_minutes' not in game_data:
                game_data['daily_minutes'] = {}
            game_data['daily_minutes'][today] = game_data['daily_minutes'].get(today, 0) + minutes
            
            logger.info(f'🕐 Sesión finalizada: {username} jugó {game_name} por {minutes} min')
        
        # Limpiar sesión actual
        game_data['current_session'] = None
        save_stats()
        
    except Exception as e:
        logger.error(f'Error al finalizar sesión de juego: {e}')
        game_data['current_session'] = None
        save_stats()

def record_voice_event(user_id, username):
    """Registra un evento de entrada a voz en las estadísticas"""
    if user_id not in stats['users']:
        stats['users'][user_id] = {
            'username': username,
            'games': {},
            'voice': {
                'count': 0,
                'last_join': None,
                'total_minutes': 0,
                'daily_minutes': {},
                'current_session': None
            }
        }
    
    # Asegurar que voice tenga todos los campos
    voice = stats['users'][user_id].get('voice', {})
    if 'total_minutes' not in voice:
        voice['total_minutes'] = 0
    if 'daily_minutes' not in voice:
        voice['daily_minutes'] = {}
    if 'current_session' not in voice:
        voice['current_session'] = None
    
    stats['users'][user_id]['voice']['count'] += 1
    stats['users'][user_id]['voice']['last_join'] = datetime.now().isoformat()
    stats['users'][user_id]['username'] = username
    save_stats()
    
    logger.info(f'📊 Stats: {username} entró a voz ({stats["users"][user_id]["voice"]["count"]} veces)')

def start_voice_session(user_id, username, channel_name):
    """Inicia una sesión de voz para tracking de tiempo"""
    if user_id not in stats['users']:
        stats['users'][user_id] = {
            'username': username,
            'games': {},
            'voice': {
                'count': 0,
                'total_minutes': 0,
                'daily_minutes': {},
                'current_session': None
            }
        }
    
    # Guardar sesión actual
    stats['users'][user_id]['voice']['current_session'] = {
        'channel': channel_name,
        'start': datetime.now().isoformat()
    }
    stats['users'][user_id]['username'] = username
    
    save_stats()
    logger.debug(f'🕐 Sesión de voz iniciada: {username} en {channel_name}')

def end_voice_session(user_id, username):
    """Finaliza una sesión de voz y calcula el tiempo"""
    if user_id not in stats['users']:
        return
    
    voice_data = stats['users'][user_id].get('voice', {})
    current_session = voice_data.get('current_session')
    
    if not current_session:
        return
    
    try:
        start_time = datetime.fromisoformat(current_session['start'])
        end_time = datetime.now()
        duration = end_time - start_time
        minutes = int(duration.total_seconds() / 60)
        
        # Solo contar si estuvo más de 1 minuto
        if minutes >= 1:
            # Actualizar total
            voice_data['total_minutes'] = voice_data.get('total_minutes', 0) + minutes
            
            # Actualizar daily
            today = datetime.now().strftime('%Y-%m-%d')
            if 'daily_minutes' not in voice_data:
                voice_data['daily_minutes'] = {}
            voice_data['daily_minutes'][today] = voice_data['daily_minutes'].get(today, 0) + minutes
            
            logger.info(f'🕐 Sesión finalizada: {username} estuvo {minutes} min en {current_session["channel"]}')
        
        # Limpiar sesión actual
        voice_data['current_session'] = None
        save_stats()
        
    except Exception as e:
        logger.error(f'Error al finalizar sesión de voz: {e}')
        voice_data['current_session'] = None
        save_stats()

# Configurar intents necesarios
intents = discord.Intents.default()
intents.presences = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

@bot.event
async def on_ready():
    logger.info(f'{bot.user} se ha conectado a Discord!')
    logger.info(f'Bot ID: {bot.user.id}')
    
    # Verificar que el canal de notificaciones esté configurado
    channel_id = get_channel_id()
    if channel_id:
        try:
            channel = bot.get_channel(channel_id)
            if channel:
                logger.info(f'Canal de notificaciones: #{channel.name} (ID: {channel_id})')
            else:
                logger.warning(f'⚠️  No se encontró el canal con ID {channel_id}')
        except Exception as e:
            logger.error(f'Error al acceder al canal: {e}')
    else:
        logger.warning('⚠️  Canal de notificaciones no configurado')
        logger.info('💡 Configura DISCORD_CHANNEL_ID en variables de entorno o usa !setchannel')

@bot.event
async def on_presence_update(before, after):
    """Detecta cuando alguien cambia su presencia (juegos, streaming, etc.)"""
    # Ignorar bots si está configurado
    if config.get('ignore_bots', True) and after.bot:
        return
    
    # TRACK CONEXIONES DIARIAS: Detectar cuando alguien se conecta (offline → online)
    if before.status == discord.Status.offline and after.status != discord.Status.offline:
        user_id = str(after.id)
        username = after.display_name
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Inicializar estructura si no existe
        if user_id not in stats['users']:
            stats['users'][user_id] = {
                'username': username,
                'games': {},
                'voice': {'count': 0},
                'messages': {'count': 0, 'characters': 0},
                'reactions': {'total': 0, 'by_emoji': {}},
                'stickers': {'total': 0, 'by_name': {}},
                'daily_connections': {}
            }
        
        # Registrar conexión del día (solo una vez por día)
        if 'daily_connections' not in stats['users'][user_id]:
            stats['users'][user_id]['daily_connections'] = {}
        
        if today not in stats['users'][user_id]['daily_connections']:
            stats['users'][user_id]['daily_connections'][today] = True
            save_stats()
            logger.debug(f'🌐 Conexión diaria: {username} ({today})')
    
    if not config.get('notify_games', True):
        return
    
    # Obtener TODAS las actividades (no solo la primera)
    # Discord puede tener: Custom Status + Juego + Spotify simultáneamente
    before_activities = before.activities
    after_activities = after.activities
    
    # Filtrar solo actividades de juegos (ignorar custom status)
    def get_game_activities(activities):
        return [
            act for act in activities 
            if act.type in [
                discord.ActivityType.playing, 
                discord.ActivityType.streaming,
                discord.ActivityType.watching,
                discord.ActivityType.listening
            ] and act.type != discord.ActivityType.custom  # Ignorar estados custom
        ]
    
    before_games = get_game_activities(before_activities)
    after_games = get_game_activities(after_activities)
    
    # Obtener nombres de juegos
    before_game_names = {act.name for act in before_games}
    after_game_names = {act.name for act in after_games}
    
    # Detectar juegos nuevos (que están en after pero no en before)
    new_games = after_game_names - before_game_names
    
    # Detectar juegos que terminaron
    ended_games = before_game_names - after_game_names
    
    # Procesar juegos nuevos
    for game_name in new_games:
        # Encontrar la actividad completa
        game_activity = next(act for act in after_games if act.name == game_name)
        activity_type_name = game_activity.type.name.lower()
        
        if activity_type_name in config.get('game_activity_types', ['playing', 'streaming', 'watching', 'listening']):
            # Verificar cooldown
            if check_cooldown(str(after.id), f'game:{game_name}'):
                logger.info(f'🎮 Detectado: {after.display_name} está {get_activity_verb(activity_type_name)} {game_name}')
                
                # Iniciar sesión de juego para tracking de tiempo
                start_game_session(str(after.id), after.display_name, game_name)
                
                # Registrar en estadísticas
                record_game_event(str(after.id), after.display_name, game_name)
                
                # Enviar notificación
                message_template = config.get('messages', {}).get('game_start', "🎮 **{user}** está {verb} **{activity}**")
                message = message_template.format(
                    user=after.display_name,
                    verb=get_activity_verb(activity_type_name),
                    activity=game_name
                )
                await send_notification(message)
    
    # Procesar juegos que terminaron (para finalizar sesiones)
    for game_name in ended_games:
        end_game_session(str(after.id), after.display_name, game_name)

@bot.event
async def on_voice_state_update(member, before, after):
    """Detecta cuando alguien entra o sale de un canal de voz"""
    if config.get('ignore_bots', True) and member.bot:
        return
    
    messages_config = config.get('messages', {})
    
    # Entrada a canal de voz
    if not before.channel and after.channel:
        # Iniciar tracking de tiempo
        start_voice_session(str(member.id), member.display_name, after.channel.name)
        
        if config.get('notify_voice', True):
            # Verificar cooldown
            if check_cooldown(str(member.id), 'voice'):
                logger.info(f'🔊 Detectado: {member.display_name} entró al canal de voz {after.channel.name}')
                
                # Registrar en estadísticas
                record_voice_event(str(member.id), member.display_name)
                
                # Enviar notificación
                message_template = messages_config.get('voice_join', "🔊 **{user}** entró al canal de voz **{channel}**")
                message = message_template.format(
                    user=member.display_name,
                    channel=after.channel.name
                )
                await send_notification(message)
    
    # Salida de canal de voz
    elif before.channel and not after.channel:
        # Finalizar tracking de tiempo
        end_voice_session(str(member.id), member.display_name)
        
        if config.get('notify_voice_leave', False):
            logger.info(f'🔇 Detectado: {member.display_name} salió del canal de voz {before.channel.name}')
            message_template = messages_config.get('voice_leave', "🔇 **{user}** salió del canal de voz **{channel}**")
            message = message_template.format(
                user=member.display_name,
                channel=before.channel.name
            )
            await send_notification(message)
    
    # Cambio de canal de voz
    elif before.channel and after.channel and before.channel != after.channel:
        if config.get('notify_voice_move', True):
            # Verificar cooldown para evitar spam de cambios de canal
            if check_cooldown(str(member.id), 'voice_move'):
                logger.info(f'🔄 Detectado: {member.display_name} cambió de {before.channel.name} a {after.channel.name}')
                message_template = messages_config.get('voice_move', "🔄 **{user}** cambió de **{old_channel}** a **{new_channel}**")
                message = message_template.format(
                    user=member.display_name,
                    old_channel=before.channel.name,
                    new_channel=after.channel.name
                )
                await send_notification(message)

@bot.event
async def on_message(message):
    """Detecta mensajes para tracking de estadísticas"""
    # Ignorar mensajes del bot mismo
    if message.author == bot.user:
        return
    
    # Ignorar bots si está configurado
    if config.get('ignore_bots', True) and message.author.bot:
        return
    
    # Trackear mensaje (sin notificar, solo stats)
    user_id = str(message.author.id)
    username = message.author.display_name
    message_content = message.content
    message_length = len(message_content)
    
    # Trackear stickers si el mensaje los tiene
    if message.stickers:
        # Inicializar estructura si no existe
        if user_id not in stats['users']:
            stats['users'][user_id] = {
                'username': username,
                'games': {},
                'voice': {'count': 0},
                'messages': {'count': 0, 'characters': 0},
                'reactions': {'total': 0, 'by_emoji': {}},
                'stickers': {'total': 0, 'by_name': {}},
                'daily_connections': {}
            }
        
        # Asegurar que existe la estructura de stickers
        if 'stickers' not in stats['users'][user_id]:
            stats['users'][user_id]['stickers'] = {'total': 0, 'by_name': {}}
        
        for sticker in message.stickers:
            sticker_name = sticker.name
            
            stats['users'][user_id]['stickers']['total'] += 1
            
            if sticker_name not in stats['users'][user_id]['stickers']['by_name']:
                stats['users'][user_id]['stickers']['by_name'][sticker_name] = 0
            
            stats['users'][user_id]['stickers']['by_name'][sticker_name] += 1
        
        stats['users'][user_id]['username'] = username
        save_stats()
        
        # Log solo cada 10 stickers
        if stats['users'][user_id]['stickers']['total'] % 10 == 0:
            logger.debug(f'🎨 Stats: {username} - {stats["users"][user_id]["stickers"]["total"]} stickers')
    
    # Solo trackear mensajes si tiene contenido Y no es spam de links
    if message_length > 0 and not is_link_spam(message_content):
        record_message_event(user_id, username, message_length)
    
    # Procesar comandos
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    """Detecta cuando alguien agrega una reacción"""
    # Ignorar reacciones del bot mismo
    if user == bot.user:
        return
    
    # Ignorar bots si está configurado
    if config.get('ignore_bots', True) and user.bot:
        return
    
    user_id = str(user.id)
    username = user.display_name
    
    # Obtener el emoji (puede ser unicode o custom)
    if reaction.is_custom_emoji():
        emoji_name = reaction.emoji.name  # Custom emoji del servidor
    else:
        emoji_name = str(reaction.emoji)  # Unicode emoji (👍, ❤️, etc)
    
    # Inicializar estructura si no existe
    if user_id not in stats['users']:
        stats['users'][user_id] = {
            'username': username,
            'games': {},
            'voice': {'count': 0},
            'messages': {'count': 0, 'characters': 0},
            'reactions': {'total': 0, 'by_emoji': {}},
            'stickers': {'total': 0, 'by_name': {}},
            'daily_connections': {}
        }
    
    # Asegurar que existe la estructura de reacciones
    if 'reactions' not in stats['users'][user_id]:
        stats['users'][user_id]['reactions'] = {'total': 0, 'by_emoji': {}}
    
    # Registrar reacción
    stats['users'][user_id]['reactions']['total'] += 1
    
    if emoji_name not in stats['users'][user_id]['reactions']['by_emoji']:
        stats['users'][user_id]['reactions']['by_emoji'][emoji_name] = 0
    
    stats['users'][user_id]['reactions']['by_emoji'][emoji_name] += 1
    stats['users'][user_id]['username'] = username
    
    save_stats()
    
    # Log solo cada 20 reacciones para no spamear
    if stats['users'][user_id]['reactions']['total'] % 20 == 0:
        logger.debug(f'👍 Stats: {username} - {stats["users"][user_id]["reactions"]["total"]} reacciones')

@bot.event
async def on_member_join(member):
    """Detecta cuando un miembro se une al servidor"""
    if config.get('ignore_bots', True) and member.bot:
        return
    
    if config.get('notify_member_join', False):
        logger.info(f'👋 Detectado: {member.display_name} se unió al servidor')
        message_template = config.get('messages', {}).get('member_join', "👋 **{user}** se unió al servidor")
        message = message_template.format(user=member.display_name)
        await send_notification(message)

@bot.event
async def on_member_remove(member):
    """Detecta cuando un miembro deja el servidor"""
    if config.get('ignore_bots', True) and member.bot:
        return
    
    if config.get('notify_member_leave', False):
        logger.info(f'👋 Detectado: {member.display_name} dejó el servidor')
        message_template = config.get('messages', {}).get('member_leave', "👋 **{user}** dejó el servidor")
        message = message_template.format(user=member.display_name)
        await send_notification(message)

def get_activity_verb(activity_type):
    """Traduce el tipo de actividad al español"""
    verbs = {
        'playing': 'jugando',
        'streaming': 'transmitiendo',
        'watching': 'viendo',
        'listening': 'escuchando'
    }
    return verbs.get(activity_type, activity_type)

async def send_notification(message):
    """Envía un mensaje al canal configurado con manejo de errores robusto"""
    channel_id = get_channel_id()
    if not channel_id:
        logger.warning('⚠️  No hay canal configurado. Configura DISCORD_CHANNEL_ID o usa !setchannel')
        return
    
    try:
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(message)
            logger.info(f'✅ Notificación enviada: {message[:50]}...')
        else:
            logger.error(f'⚠️  No se encontró el canal con ID {channel_id}')
    except discord.errors.HTTPException as e:
        if e.status == 429:  # Rate limited
            retry_after = e.retry_after if hasattr(e, 'retry_after') else 1.0
            logger.warning(f'⚠️  Rate limited. Esperando {retry_after}s...')
            await asyncio.sleep(retry_after)
            try:
                await channel.send(message)
            except Exception as retry_error:
                logger.error(f'❌ Error al reintentar: {retry_error}')
        else:
            logger.error(f'❌ Error HTTP: {e}')
    except discord.errors.Forbidden:
        logger.error(f'⚠️  Sin permisos para enviar mensajes al canal {channel_id}')
    except Exception as e:
        logger.error(f'❌ Error al enviar notificación: {e}')

@bot.command(name='setchannel')
async def set_channel(ctx, channel: discord.TextChannel = None):
    """Configura el canal donde se enviarán las notificaciones
    
    Ejemplo: !setchannel o !setchannel #canal
    """
    if channel is None:
        channel = ctx.channel
    
    # Verificar que el bot tenga permisos
    bot_member = channel.guild.get_member(bot.user.id)
    if bot_member:
        permissions = channel.permissions_for(bot_member)
        if not permissions.send_messages:
            try:
                await ctx.send(f'❌ El bot no tiene permisos para enviar mensajes en {channel.mention}.')
            except:
                logger.error(f'⚠️  Bot sin permisos en canal {channel.name} (ID: {channel.id})')
            return
    
    config['channel_id'] = channel.id
    save_config()
    
    await ctx.send(f'✅ Canal de notificaciones configurado: {channel.mention}\n💡 **Recomendación:** Configura `DISCORD_CHANNEL_ID={channel.id}` en Railway para que nunca se pierda.')
    logger.info(f'Canal configurado: {channel.name} (ID: {channel.id})')

@bot.command(name='unsetchannel', aliases=['removechannel', 'clearchannel'])
async def unset_channel(ctx):
    """Desconfigura el canal de notificaciones
    
    Ejemplo: !unsetchannel
    """
    channel_id = get_channel_id()
    if not channel_id:
        await ctx.send('ℹ️ No hay canal configurado.')
        return
    
    old_channel = bot.get_channel(channel_id)
    channel_name = old_channel.name if old_channel else f'ID: {channel_id}'
    
    config['channel_id'] = None
    save_config()
    
    await ctx.send(f'✅ Canal desconfigurado: `#{channel_name}`')
    logger.info(f'Canal desconfigurado: {channel_name}')

@bot.command(name='stats', aliases=['mystats'])
async def show_stats(ctx, member: discord.Member = None):
    """Muestra estadísticas de un usuario
    
    Ejemplos:
    - !stats - Tus estadísticas
    - !stats @usuario - Estadísticas de otro usuario
    """
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

# Clase para los botones de toggle
class ToggleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
    
    def create_toggle_button(self, label, key, emoji):
        button = ToggleButton(label, key, emoji)
        self.add_item(button)
        return button

class ToggleButton(discord.ui.Button):
    def __init__(self, label, key, emoji):
        current_value = config.get(key, False)
        style = discord.ButtonStyle.success if current_value else discord.ButtonStyle.secondary
        super().__init__(label=label, emoji=emoji, style=style)
        self.key = key
        self.label_text = label
        self.emoji_text = emoji
    
    async def callback(self, interaction):
        current_value = config.get(self.key, False)
        config[self.key] = not current_value
        new_status = 'activado' if config[self.key] else 'desactivado'
        
        # Guardar configuración
        save_config()
        
        # Actualizar el botón
        self.style = discord.ButtonStyle.success if config[self.key] else discord.ButtonStyle.secondary
        
        await interaction.response.send_message(
            f'{self.emoji_text} **{self.label_text}** {new_status.capitalize()}',
            ephemeral=True
        )

@bot.command(name='toggle')
async def toggle_notification(ctx, notification_type: str = None):
    """Activa o desactiva tipos de notificaciones usando botones interactivos
    
    Ejemplos:
    - !toggle - Abre el menú interactivo
    - !toggle games - Activa/desactiva juegos directamente
    """
    if notification_type is None:
        # Crear embed con botones
        embed = discord.Embed(
            title='⚙️ Configurar Notificaciones',
            description='Haz clic en los botones para activar/desactivar:',
            color=discord.Color.blue()
        )
        
        # Mostrar estado actual
        status_text = (
            f'🎮 Juegos: {"✅" if config.get("notify_games") else "❌"}\n'
            f'🔊 Entrada a Voz: {"✅" if config.get("notify_voice") else "❌"}\n'
            f'🔇 Salida de Voz: {"✅" if config.get("notify_voice_leave") else "❌"}\n'
            f'🔄 Cambio de Canal: {"✅" if config.get("notify_voice_move", True) else "❌"}\n'
            f'👋 Miembro se Une: {"✅" if config.get("notify_member_join") else "❌"}\n'
            f'👋 Miembro se Va: {"✅" if config.get("notify_member_leave") else "❌"}\n'
            f'🤖 Ignorar Bots: {"✅" if config.get("ignore_bots") else "❌"}'
        )
        
        embed.add_field(name='Estado Actual', value=status_text, inline=False)
        
        # Crear vista con botones
        view = ToggleView()
        view.create_toggle_button('Juegos', 'notify_games', '🎮')
        view.create_toggle_button('Entrada Voz', 'notify_voice', '🔊')
        view.create_toggle_button('Salida Voz', 'notify_voice_leave', '🔇')
        view.create_toggle_button('Cambio Canal', 'notify_voice_move', '🔄')
        view.create_toggle_button('Miembro Une', 'notify_member_join', '👋')
        view.create_toggle_button('Miembro Va', 'notify_member_leave', '👋')
        view.create_toggle_button('Ignorar Bots', 'ignore_bots', '🤖')
        
        await ctx.send(embed=embed, view=view)
        return
    
    # Método tradicional
    notification_type = notification_type.lower()
    
    toggle_map = {
        'games': 'notify_games',
        'voice': 'notify_voice',
        'voiceleave': 'notify_voice_leave',
        'voicemove': 'notify_voice_move',
        'memberjoin': 'notify_member_join',
        'memberleave': 'notify_member_leave'
    }
    
    if notification_type not in toggle_map:
        await ctx.send('❌ Tipo no válido. Usa: `games`, `voice`, `voiceleave`, `voicemove`, `memberjoin`, `memberleave`')
        return
    
    config_key = toggle_map[notification_type]
    config[config_key] = not config.get(config_key, False)
    status = 'activadas' if config[config_key] else 'desactivadas'
    
    save_config()
    
    await ctx.send(f'✅ Notificaciones de {notification_type} {status}')

@bot.command(name='config')
async def show_config(ctx):
    """Muestra la configuración actual del bot"""
    channel_id = get_channel_id()
    channel_mention = 'No configurado'
    
    if channel_id:
        channel = bot.get_channel(channel_id)
        if channel:
            channel_mention = channel.mention
    
    embed = discord.Embed(title='⚙️ Configuración del Bot', color=discord.Color.blue())
    embed.add_field(name='Canal de notificaciones', value=channel_mention, inline=False)
    embed.add_field(name='Notificaciones de juegos', value='✅' if config.get('notify_games') else '❌', inline=True)
    embed.add_field(name='Entrada a voz', value='✅' if config.get('notify_voice') else '❌', inline=True)
    embed.add_field(name='Salida de voz', value='✅' if config.get('notify_voice_leave') else '❌', inline=True)
    embed.add_field(name='Cambio de voz', value='✅' if config.get('notify_voice_move', True) else '❌', inline=True)
    embed.add_field(name='Miembros (join)', value='✅' if config.get('notify_member_join', False) else '❌', inline=True)
    embed.add_field(name='Miembros (leave)', value='✅' if config.get('notify_member_leave', False) else '❌', inline=True)
    embed.add_field(name='Ignorar bots', value='✅' if config.get('ignore_bots') else '❌', inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='test')
async def test_notification(ctx):
    """Envía un mensaje de prueba al canal configurado
    
    Ejemplo: !test
    """
    channel_id = get_channel_id()
    if not channel_id:
        await ctx.send('⚠️ No hay canal configurado. Usa `!setchannel` primero.')
        return
    
    # Solo enviar al canal configurado
    await send_notification('🧪 **Mensaje de prueba** - El bot funciona correctamente!')
    
    # Si el comando se ejecutó en otro canal, confirmar ahí
    if ctx.channel.id != channel_id:
        try:
            await ctx.send(f'✅ Mensaje de prueba enviado a <#{channel_id}>')
        except discord.errors.Forbidden:
            logger.error(f'⚠️ No se pudo enviar confirmación en el canal {ctx.channel.name}')

# Importar funciones de visualización
from stats_viz import (
    create_bar_chart, create_timeline_chart, create_comparison_chart,
    create_user_detail_view, filter_by_period, get_period_label,
    calculate_daily_activity, format_time
)

# ============================================================================
# SISTEMA DE VISUALIZACIÓN INTERACTIVO
# ============================================================================

class StatsView(discord.ui.View):
    """Vista interactiva para seleccionar diferentes visualizaciones de stats"""
    
    def __init__(self, period='all'):
        super().__init__(timeout=300)
        self.period = period
        self.add_item(StatsSelect(period))
        self.add_item(PeriodSelect())
    
    async def on_timeout(self):
        """Desactiva los componentes cuando expira el timeout"""
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass

class StatsSelect(discord.ui.Select):
    """Select menu para elegir el tipo de visualización"""
    
    def __init__(self, period='all'):
        self.period = period
        
        options = [
            discord.SelectOption(
                label='Vista General',
                description='Resumen completo de estadísticas',
                emoji='📊',
                value='overview'
            ),
            discord.SelectOption(
                label='Ranking Juegos',
                description='Juegos más jugados (gráfico)',
                emoji='🎮',
                value='games'
            ),
            discord.SelectOption(
                label='Ranking Voz',
                description='Usuarios más activos en voz',
                emoji='🔊',
                value='voice'
            ),
            discord.SelectOption(
                label='Ranking Mensajes',
                description='Usuarios más activos en chat',
                emoji='💬',
                value='messages'
            ),
            discord.SelectOption(
                label='Ranking Usuarios',
                description='Actividad total por usuario',
                emoji='👥',
                value='users'
            ),
            discord.SelectOption(
                label='Línea de Tiempo',
                description='Actividad de los últimos 7 días',
                emoji='📈',
                value='timeline'
            ),
        ]
        
        super().__init__(
            placeholder='Selecciona una visualización...',
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        view_type = self.values[0]
        
        # Filtrar datos por período
        filtered_stats = filter_by_period(stats, self.period)
        period_label = get_period_label(self.period)
        
        if view_type == 'overview':
            embed = await create_overview_embed(filtered_stats, period_label)
            await interaction.response.edit_message(embed=embed, view=self.view)
        
        elif view_type == 'games':
            embed = await create_games_ranking_embed(filtered_stats, period_label)
            await interaction.response.edit_message(embed=embed, view=self.view)
        
        elif view_type == 'voice':
            embed = await create_voice_ranking_embed(filtered_stats, period_label)
            await interaction.response.edit_message(embed=embed, view=self.view)
        
        elif view_type == 'messages':
            embed = await create_messages_ranking_embed(filtered_stats, period_label)
            await interaction.response.edit_message(embed=embed, view=self.view)
        
        elif view_type == 'users':
            embed = await create_users_ranking_embed(filtered_stats, period_label)
            await interaction.response.edit_message(embed=embed, view=self.view)
        
        elif view_type == 'timeline':
            embed = await create_timeline_embed(stats, period_label)
            await interaction.response.edit_message(embed=embed, view=self.view)

class PeriodSelect(discord.ui.Select):
    """Select menu para elegir el período de tiempo"""
    
    def __init__(self):
        options = [
            discord.SelectOption(label='Hoy', emoji='📅', value='today'),
            discord.SelectOption(label='Última Semana', emoji='📆', value='week'),
            discord.SelectOption(label='Último Mes', emoji='🗓️', value='month'),
            discord.SelectOption(label='Histórico', emoji='📚', value='all'),
        ]
        
        super().__init__(
            placeholder='Período: Histórico',
            min_values=1,
            max_values=1,
            options=options,
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        period = self.values[0]
        
        # Actualizar el placeholder
        self.placeholder = f'Período: {get_period_label(period)}'
        
        # Crear nueva vista con el período actualizado
        new_view = StatsView(period=period)
        new_view.message = self.view.message
        
        # Mostrar vista general con el nuevo período
        filtered_stats = filter_by_period(stats, period)
        period_label = get_period_label(period)
        embed = await create_overview_embed(filtered_stats, period_label)
        
        await interaction.response.edit_message(embed=embed, view=new_view)

# ============================================================================
# FUNCIONES DE CREACIÓN DE EMBEDS
# ============================================================================

async def create_overview_embed(filtered_stats: Dict, period_label: str) -> discord.Embed:
    """Crea embed con vista general de estadísticas"""
    embed = discord.Embed(
        title=f'📊 Vista General - {period_label}',
        color=discord.Color.blue()
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
        title=f'🎮 Ranking de Juegos - {period_label}',
        color=discord.Color.gold()
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
        title=f'🔊 Ranking de Actividad de Voz - {period_label}',
        color=discord.Color.purple()
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
        title=f'👥 Ranking de Usuarios - {period_label}',
        color=discord.Color.green()
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
        title=f'💬 Ranking de Mensajes - {period_label}',
        color=discord.Color.teal()
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
        title=f'📈 Línea de Tiempo de Actividad',
        color=discord.Color.orange()
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

# ============================================================================
# COMANDOS DE ESTADÍSTICAS
# ============================================================================

@bot.command(name='statsmenu', aliases=['statsinteractive'])
async def stats_menu(ctx):
    """
    Abre el menú interactivo de estadísticas
    
    Ejemplo: !statsmenu
    """
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

@bot.command(name='voicetime')
async def voice_time_cmd(ctx, member: discord.Member = None, period: str = 'all'):
    """
    Muestra el tiempo total en canales de voz
    
    Ejemplos:
    - !voicetime
    - !voicetime @usuario
    - !voicetime @usuario week
    """
    if member is None:
        member = ctx.author
    
    user_id = str(member.id)
    user_data = stats.get('users', {}).get(user_id, {})
    
    if not user_data:
        await ctx.send(f'📊 {member.display_name} no tiene estadísticas registradas.')
        return
    
    voice = user_data.get('voice', {})
    total_minutes = voice.get('total_minutes', 0)
    daily_minutes = voice.get('daily_minutes', {})
    
    # Filtrar por período
    if period == 'today':
        today = datetime.now().strftime('%Y-%m-%d')
        minutes = daily_minutes.get(today, 0)
        period_label = 'Hoy'
    elif period == 'week':
        week_ago = datetime.now() - timedelta(days=7)
        minutes = sum(
            mins for date, mins in daily_minutes.items()
            if datetime.strptime(date, '%Y-%m-%d') >= week_ago
        )
        period_label = 'Esta Semana'
    elif period == 'month':
        month_ago = datetime.now() - timedelta(days=30)
        minutes = sum(
            mins for date, mins in daily_minutes.items()
            if datetime.strptime(date, '%Y-%m-%d') >= month_ago
        )
        period_label = 'Este Mes'
    else:
        minutes = total_minutes
        period_label = 'Total'
    
    # Formatear tiempo
    if minutes < 60:
        time_str = f'{minutes} min'
    elif minutes < 1440:  # < 24 horas
        hours = minutes // 60
        mins = minutes % 60
        time_str = f'{hours}h {mins}m'
    else:
        days = minutes // 1440
        hours = (minutes % 1440) // 60
        time_str = f'{days}d {hours}h'
    
    embed = discord.Embed(
        title=f'🕐 Tiempo en Voz - {member.display_name}',
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name=f'⏱️ {period_label}',
        value=f'**{time_str}** ({minutes} minutos)',
        inline=False
    )
    
    if period == 'all' and len(daily_minutes) > 0:
        # Mostrar últimos 7 días
        recent_days = sorted(daily_minutes.items(), reverse=True)[:7]
        days_text = []
        for date, mins in recent_days:
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            day_label = date_obj.strftime('%d/%m')
            if mins < 60:
                time_label = f'{mins}m'
            else:
                hours = mins // 60
                time_label = f'{hours}h {mins % 60}m'
            days_text.append(f'`{day_label}` - {time_label}')
        
        embed.add_field(
            name='📅 Últimos 7 Días',
            value='\n'.join(days_text) if days_text else 'Sin datos',
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='voicetop')
async def voice_top_time_cmd(ctx, period: str = 'all'):
    """
    Ranking de usuarios por tiempo en voz
    
    Ejemplos:
    - !voicetop
    - !voicetop week
    - !voicetop month
    """
    # Calcular tiempo por usuario según período
    user_times = []
    
    for user_id, user_data in stats.get('users', {}).items():
        voice = user_data.get('voice', {})
        daily_minutes = voice.get('daily_minutes', {})
        username = user_data.get('username', 'Unknown')
        
        if period == 'today':
            today = datetime.now().strftime('%Y-%m-%d')
            minutes = daily_minutes.get(today, 0)
        elif period == 'week':
            week_ago = datetime.now() - timedelta(days=7)
            minutes = sum(
                mins for date, mins in daily_minutes.items()
                if datetime.strptime(date, '%Y-%m-%d') >= week_ago
            )
        elif period == 'month':
            month_ago = datetime.now() - timedelta(days=30)
            minutes = sum(
                mins for date, mins in daily_minutes.items()
                if datetime.strptime(date, '%Y-%m-%d') >= month_ago
            )
        else:
            minutes = voice.get('total_minutes', 0)
        
        if minutes > 0:
            user_times.append((username, minutes))
    
    if not user_times:
        await ctx.send(f'📊 No hay tiempo registrado en voz para {period}.')
        return
    
    # Ordenar por tiempo
    top_users = sorted(user_times, key=lambda x: x[1], reverse=True)[:10]
    
    # Crear gráfico
    from stats_viz import create_bar_chart
    chart = create_bar_chart(top_users, max_width=15, title='')
    
    period_labels = {
        'today': 'Hoy',
        'week': 'Esta Semana',
        'month': 'Este Mes',
        'all': 'Histórico'
    }
    
    embed = discord.Embed(
        title=f'🏆 Top Tiempo en Voz - {period_labels.get(period, "Histórico")}',
        description=f'```\n{chart}\n```',
        color=discord.Color.gold()
    )
    
    # Total
    total_minutes = sum(m for _, m in top_users)
    if total_minutes < 60:
        total_str = f'{total_minutes} min'
    elif total_minutes < 1440:
        hours = total_minutes // 60
        total_str = f'{hours}h {total_minutes % 60}m'
    else:
        days = total_minutes // 1440
        hours = (total_minutes % 1440) // 60
        total_str = f'{days}d {hours}h'
    
    embed.add_field(
        name='⏱️ Total Combinado',
        value=total_str,
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='bothelp', aliases=['help', 'ayuda', 'comandos'])
async def show_help(ctx, comando: str = None):
    """
    Muestra la lista de comandos disponibles
    
    Ejemplos:
    - !help
    - !help stats
    - !help export
    """
    if comando:
        # Ayuda específica de un comando
        comando = comando.lower()
        help_texts = {
            'setchannel': '**!setchannel [#canal]**\nConfigura el canal donde se enviarán las notificaciones.\nSi no especificas canal, usa el canal actual.\n\nEjemplo: `!setchannel #general`',
            'unsetchannel': '**!unsetchannel**\nDesconfigura el canal de notificaciones.\nEl bot dejará de enviar mensajes.',
            'toggle': '**!toggle [tipo]**\nActiva/desactiva tipos de notificaciones.\nSin argumentos abre menú interactivo.\n\nTipos: `games`, `voice`, `voiceleave`, `voicemove`\nEjemplo: `!toggle games`',
            'config': '**!config**\nMuestra la configuración actual del bot.',
            'test': '**!test**\nEnvía un mensaje de prueba al canal configurado.',
            'stats': '**!stats [@usuario]**\nMuestra estadísticas de un usuario.\nSin argumento muestra las tuyas.\n\nEjemplo: `!stats @Juan`',
            'topgames': '**!topgames [límite]**\nMuestra los juegos más jugados.\nLímite por defecto: 5\n\nEjemplo: `!topgames 10`',
            'topusers': '**!topusers [límite]**\nMuestra los usuarios más activos.\nLímite por defecto: 5',
            'statsmenu': '**!statsmenu**\nAbre el menú interactivo de estadísticas.\nIncluye múltiples visualizaciones y filtros.',
            'statsgames': '**!statsgames [período]**\nRanking de juegos con gráfico ASCII.\nPeríodos: `today`, `week`, `month`, `all`\n\nEjemplo: `!statsgames week`',
            'statsvoice': '**!statsvoice [período]**\nRanking de actividad de voz con gráfico.\nPeríodos: `today`, `week`, `month`, `all`',
            'statsuser': '**!statsuser [@usuario]**\nEstadísticas detalladas de un usuario.\nMás completo que !stats',
            'timeline': '**!timeline [días]**\nLínea de tiempo de actividad.\nDías: 1-30 (default: 7)\n\nEjemplo: `!timeline 14`',
            'compare': '**!compare @user1 @user2**\nCompara estadísticas entre dos usuarios.\n\nEjemplo: `!compare @Juan @María`',
            'export': '**!export [formato]**\nExporta estadísticas a archivo.\nFormatos: `json`, `csv`\n\nEjemplo: `!export csv`',
        }
        
        help_text = help_texts.get(comando)
        if help_text:
            embed = discord.Embed(
                title=f'📖 Ayuda: {comando}',
                description=help_text,
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f'❌ Comando `{comando}` no encontrado. Usa `!help` para ver todos los comandos.')
        return
    
    # Ayuda general
    embed = discord.Embed(
        title='📖 Comandos del Bot',
        description='Lista completa de comandos disponibles',
        color=discord.Color.blue()
    )
    
    # Configuración
    embed.add_field(
        name='🔧 Configuración',
        value=(
            '`!setchannel [#canal]` - Configurar canal de notificaciones\n'
            '`!unsetchannel` - Desconfigurar canal\n'
            '`!toggle [tipo]` - Activar/desactivar notificaciones\n'
            '`!config` - Ver configuración actual\n'
            '`!test` - Enviar mensaje de prueba'
        ),
        inline=False
    )
    
    # Estadísticas Básicas
    embed.add_field(
        name='📊 Estadísticas Básicas',
        value=(
            '`!stats [@usuario]` - Estadísticas de un usuario\n'
            '`!topgames [límite]` - Top juegos más jugados\n'
            '`!topusers [límite]` - Top usuarios más activos'
        ),
        inline=False
    )
    
    # Estadísticas Avanzadas
    embed.add_field(
        name='📈 Estadísticas Avanzadas',
        value=(
            '`!statsmenu` - Menú interactivo completo\n'
            '`!statsgames [período]` - Ranking de juegos con gráfico\n'
            '`!statsvoice [período]` - Ranking de voz con gráfico\n'
            '`!statsuser [@usuario]` - Stats detalladas de usuario\n'
            '`!timeline [días]` - Línea de tiempo de actividad\n'
            '`!compare @user1 @user2` - Comparar dos usuarios'
        ),
        inline=False
    )
    
    # Utilidades
    embed.add_field(
        name='🛠️ Utilidades',
        value=(
            '`!export [formato]` - Exportar stats (json/csv)\n'
            '`!voicetime [@usuario] [período]` - Tiempo en voz\n'
            '`!voicetop [período]` - Ranking por tiempo en voz\n'
            '`!bothelp [comando]` - Ver ayuda detallada'
        ),
        inline=False
    )
    
    # Footer con tips
    embed.set_footer(text='💡 Tip: Usa !bothelp [comando] para más detalles. Ejemplo: !bothelp stats')
    
    await ctx.send(embed=embed)

# Ejecutar el bot
if __name__ == '__main__':
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error('❌ ERROR: No se encontró DISCORD_BOT_TOKEN')
        logger.error('Configura la variable de entorno DISCORD_BOT_TOKEN')
        exit(1)
    
    # Verificar configuración del canal
    channel_id = get_channel_id()
    if channel_id:
        logger.info(f'✅ Canal configurado: {channel_id}')
    else:
        logger.warning('⚠️  Canal no configurado')
        logger.warning('💡 Configura DISCORD_CHANNEL_ID en Railway o usa !setchannel')
    
    logger.info(f'📁 Directorio de datos: {DATA_DIR}')
    logger.info(f'📊 Usuarios registrados: {len(stats.get("users", {}))}')
    
    try:
        bot.run(token, reconnect=True, log_handler=None)
    except KeyboardInterrupt:
        logger.info('🛑 Bot detenido')
    except discord.errors.LoginFailure:
        logger.error('❌ ERROR: Token inválido')
        exit(1)
    except discord.errors.PrivilegedIntentsRequired:
        logger.error('❌ ERROR: Privileged Intents no habilitados')
        logger.error('Ve a: https://discord.com/developers/applications')
        logger.error('Bot → Privileged Gateway Intents → Activa PRESENCE y SERVER MEMBERS')
        exit(1)
    except Exception as e:
        logger.exception(f'❌ Error fatal: {e}')
        exit(1)
