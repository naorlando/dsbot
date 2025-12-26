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
    
    stats['users'][user_id]['games'][game_name]['count'] += 1
    stats['users'][user_id]['games'][game_name]['last_played'] = datetime.now().isoformat()
    stats['users'][user_id]['username'] = username  # Actualizar username por si cambió
    save_stats()
    
    logger.info(f'📊 Stats: {username} jugó {game_name} ({stats["users"][user_id]["games"][game_name]["count"]} veces)')

def record_voice_event(user_id, username):
    """Registra un evento de entrada a voz en las estadísticas"""
    if user_id not in stats['users']:
        stats['users'][user_id] = {
            'username': username,
            'games': {},
            'voice': {'count': 0, 'last_join': None}
        }
    
    stats['users'][user_id]['voice']['count'] += 1
    stats['users'][user_id]['voice']['last_join'] = datetime.now().isoformat()
    stats['users'][user_id]['username'] = username
    save_stats()
    
    logger.info(f'📊 Stats: {username} entró a voz ({stats["users"][user_id]["voice"]["count"]} veces)')

# Configurar intents necesarios
intents = discord.Intents.default()
intents.presences = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

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
    if not config.get('notify_games', True):
        return
    
    # Ignorar bots si está configurado
    if config.get('ignore_bots', True) and after.bot:
        return
    
    # Obtener actividades anteriores y nuevas
    before_activity = before.activity
    after_activity = after.activity
    
    # Verificar si empezó una nueva actividad
    if after_activity and after_activity.type in [discord.ActivityType.playing, 
                                                   discord.ActivityType.streaming,
                                                   discord.ActivityType.watching,
                                                   discord.ActivityType.listening]:
        # Verificar si es una actividad nueva o diferente
        activity_type_name = after_activity.type.name.lower()
        
        if activity_type_name in config.get('game_activity_types', ['playing', 'streaming', 'watching', 'listening']):
            # Si no tenía actividad antes o es diferente
            if not before_activity or before_activity.name != after_activity.name:
                # Verificar cooldown
                if check_cooldown(str(after.id), f'game:{after_activity.name}'):
                    logger.info(f'🎮 Detectado: {after.display_name} está {get_activity_verb(activity_type_name)} {after_activity.name}')
                    
                    # Registrar en estadísticas
                    record_game_event(str(after.id), after.display_name, after_activity.name)
                    
                    # Enviar notificación
                    message_template = config.get('messages', {}).get('game_start', "🎮 **{user}** está {verb} **{activity}**")
                    message = message_template.format(
                        user=after.display_name,
                        verb=get_activity_verb(activity_type_name),
                        activity=after_activity.name
                    )
                    await send_notification(message)

@bot.event
async def on_voice_state_update(member, before, after):
    """Detecta cuando alguien entra o sale de un canal de voz"""
    if config.get('ignore_bots', True) and member.bot:
        return
    
    messages_config = config.get('messages', {})
    
    # Entrada a canal de voz
    if not before.channel and after.channel:
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
    
    # Estadísticas de juegos
    games = user_stats.get('games', {})
    if games:
        game_lines = []
        for game, data in sorted(games.items(), key=lambda x: x[1]['count'], reverse=True)[:5]:
            game_lines.append(f'• {game}: **{data["count"]}** veces')
        embed.add_field(
            name='🎮 Juegos',
            value='\n'.join(game_lines) + f'\n\n**Total juegos:** {len(games)}',
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
        
        embed.add_field(
            name='🔊 Voz',
            value=f'Entradas a canal: **{voice["count"]}** veces\nÚltima vez: {time_str}',
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='topgames')
async def top_games(ctx, limit: int = 5):
    """Muestra los juegos más jugados
    
    Ejemplo: !topgames o !topgames 10
    """
    # Recopilar todos los juegos
    game_counts = {}
    for user_data in stats['users'].values():
        for game, data in user_data.get('games', {}).items():
            if game not in game_counts:
                game_counts[game] = 0
            game_counts[game] += data['count']
    
    if not game_counts:
        await ctx.send('📊 No hay juegos registrados aún.')
        return
    
    # Ordenar y limitar
    top = sorted(game_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    embed = discord.Embed(
        title=f'🏆 Top {len(top)} Juegos Más Jugados',
        color=discord.Color.gold()
    )
    
    lines = []
    for i, (game, count) in enumerate(top, 1):
        medal = ['🥇', '🥈', '🥉'][i-1] if i <= 3 else f'{i}.'
        lines.append(f'{medal} **{game}**: {count} veces')
    
    embed.description = '\n'.join(lines)
    await ctx.send(embed=embed)

@bot.command(name='topusers')
async def top_users(ctx, limit: int = 5):
    """Muestra los usuarios más activos
    
    Ejemplo: !topusers o !topusers 10
    """
    # Calcular actividad total por usuario
    user_activity = []
    for user_id, user_data in stats['users'].items():
        games_count = sum(game['count'] for game in user_data.get('games', {}).values())
        voice_count = user_data.get('voice', {}).get('count', 0)
        total = games_count + voice_count
        
        if total > 0:
            user_activity.append({
                'username': user_data.get('username', 'Usuario Desconocido'),
                'games': games_count,
                'voice': voice_count,
                'total': total
            })
    
    if not user_activity:
        await ctx.send('📊 No hay actividad registrada aún.')
        return
    
    # Ordenar y limitar
    top = sorted(user_activity, key=lambda x: x['total'], reverse=True)[:limit]
    
    embed = discord.Embed(
        title=f'🏆 Top {len(top)} Usuarios Más Activos',
        color=discord.Color.gold()
    )
    
    lines = []
    for i, user in enumerate(top, 1):
        medal = ['🥇', '🥈', '🥉'][i-1] if i <= 3 else f'{i}.'
        lines.append(
            f'{medal} **{user["username"]}**: {user["total"]} eventos\n'
            f'   🎮 {user["games"]} juegos | 🔊 {user["voice"]} voz'
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
    """Envía un mensaje de prueba"""
    try:
        await send_notification('🧪 **Mensaje de prueba** - El bot funciona correctamente!')
        try:
            await ctx.send('✅ Mensaje de prueba enviado!')
        except discord.errors.Forbidden:
            pass
    except Exception as e:
        try:
            await ctx.send(f'❌ Error: {str(e)}')
        except discord.errors.Forbidden:
            logger.error(f'⚠️  Error en !test: {e}')

# Importar funciones de visualización
from stats_viz import (
    create_bar_chart, create_timeline_chart, create_comparison_chart,
    create_user_detail_view, filter_by_period, get_period_label,
    calculate_daily_activity
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
    
    # Contar totales
    total_games = 0
    total_voice = 0
    unique_games = set()
    
    for user_data in users.values():
        for game_name, game_data in user_data.get('games', {}).items():
            total_games += game_data.get('count', 0)
            unique_games.add(game_name)
        total_voice += user_data.get('voice', {}).get('count', 0)
    
    # Resumen
    embed.add_field(
        name='📈 Resumen',
        value=(
            f'**Usuarios activos:** {total_users}\n'
            f'**Sesiones de juego:** {total_games}\n'
            f'**Juegos únicos:** {len(unique_games)}\n'
            f'**Entradas a voz:** {total_voice}\n'
            f'**Actividad total:** {total_games + total_voice}'
        ),
        inline=False
    )
    
    # Top 3 juegos
    game_counts = {}
    for user_data in users.values():
        for game, data in user_data.get('games', {}).items():
            game_counts[game] = game_counts.get(game, 0) + data['count']
    
    if game_counts:
        top_games = sorted(game_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        games_text = '\n'.join([f'{i+1}. **{game}**: {count} veces' 
                               for i, (game, count) in enumerate(top_games)])
        embed.add_field(name='🎮 Top 3 Juegos', value=games_text, inline=True)
    
    # Top 3 usuarios
    user_activity = []
    for user_id, user_data in users.items():
        games_count = sum(g['count'] for g in user_data.get('games', {}).values())
        voice_count = user_data.get('voice', {}).get('count', 0)
        total = games_count + voice_count
        if total > 0:
            user_activity.append((user_data.get('username', 'Unknown'), total))
    
    if user_activity:
        top_users = sorted(user_activity, key=lambda x: x[1], reverse=True)[:3]
        users_text = '\n'.join([f'{i+1}. **{name}**: {count} eventos' 
                               for i, (name, count) in enumerate(top_users)])
        embed.add_field(name='👥 Top 3 Usuarios', value=users_text, inline=True)
    
    return embed

async def create_games_ranking_embed(filtered_stats: Dict, period_label: str) -> discord.Embed:
    """Crea embed con ranking de juegos y gráfico"""
    embed = discord.Embed(
        title=f'🎮 Ranking de Juegos - {period_label}',
        color=discord.Color.gold()
    )
    
    # Recopilar juegos
    game_counts = {}
    for user_data in filtered_stats.get('users', {}).values():
        for game, data in user_data.get('games', {}).items():
            game_counts[game] = game_counts.get(game, 0) + data['count']
    
    if not game_counts:
        embed.description = 'No hay juegos registrados en este período.'
        return embed
    
    # Ordenar y tomar top 10
    top_games = sorted(game_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Crear gráfico ASCII
    chart = create_bar_chart(top_games, max_width=15)
    
    embed.description = f'```\n{chart}\n```'
    embed.add_field(
        name='📊 Total',
        value=f'**{len(game_counts)}** juegos únicos\n**{sum(game_counts.values())}** sesiones totales',
        inline=False
    )
    
    return embed

async def create_voice_ranking_embed(filtered_stats: Dict, period_label: str) -> discord.Embed:
    """Crea embed con ranking de actividad de voz"""
    embed = discord.Embed(
        title=f'🔊 Ranking de Actividad de Voz - {period_label}',
        color=discord.Color.purple()
    )
    
    # Recopilar actividad de voz
    voice_counts = []
    for user_data in filtered_stats.get('users', {}).values():
        username = user_data.get('username', 'Unknown')
        count = user_data.get('voice', {}).get('count', 0)
        if count > 0:
            voice_counts.append((username, count))
    
    if not voice_counts:
        embed.description = 'No hay actividad de voz registrada en este período.'
        return embed
    
    # Ordenar y tomar top 8
    top_voice = sorted(voice_counts, key=lambda x: x[1], reverse=True)[:8]
    
    # Crear gráfico ASCII
    chart = create_bar_chart(top_voice, max_width=15)
    
    embed.description = f'```\n{chart}\n```'
    embed.add_field(
        name='📊 Total',
        value=f'**{len(voice_counts)}** usuarios activos\n**{sum(c for _, c in voice_counts)}** entradas totales',
        inline=False
    )
    
    return embed

async def create_users_ranking_embed(filtered_stats: Dict, period_label: str) -> discord.Embed:
    """Crea embed con ranking de usuarios más activos"""
    embed = discord.Embed(
        title=f'👥 Ranking de Usuarios - {period_label}',
        color=discord.Color.green()
    )
    
    # Calcular actividad total por usuario
    user_activity = []
    for user_data in filtered_stats.get('users', {}).values():
        username = user_data.get('username', 'Unknown')
        games_count = sum(g['count'] for g in user_data.get('games', {}).values())
        voice_count = user_data.get('voice', {}).get('count', 0)
        total = games_count + voice_count
        
        if total > 0:
            user_activity.append((username, total, games_count, voice_count))
    
    if not user_activity:
        embed.description = 'No hay actividad registrada en este período.'
        return embed
    
    # Ordenar por total
    top_users = sorted(user_activity, key=lambda x: x[1], reverse=True)[:8]
    
    # Crear gráfico ASCII
    chart_data = [(name, total) for name, total, _, _ in top_users]
    chart = create_bar_chart(chart_data, max_width=15)
    
    embed.description = f'```\n{chart}\n```'
    
    # Detalles
    details = []
    for i, (name, total, games, voice) in enumerate(top_users[:5], 1):
        medal = ['🥇', '🥈', '🥉'][i-1] if i <= 3 else f'{i}.'
        details.append(f'{medal} **{name}**: {total} total (🎮 {games} | 🔊 {voice})')
    
    embed.add_field(name='📋 Detalle Top 5', value='\n'.join(details), inline=False)
    
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

@bot.command(name='help', aliases=['ayuda', 'comandos'])
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
            '`!help [comando]` - Ver ayuda detallada'
        ),
        inline=False
    )
    
    # Footer con tips
    embed.set_footer(text='💡 Tip: Usa !help [comando] para más detalles. Ejemplo: !help stats')
    
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
