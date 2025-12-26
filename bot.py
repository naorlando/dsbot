import discord
from discord.ext import commands
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Cargar configuración
def load_config():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        # Configuración por defecto
        default_config = {
            "channel_id": None,
            "notify_games": True,
            "notify_voice": True,
            "notify_voice_leave": False,
            "ignore_bots": True,
            "game_activity_types": ["playing", "streaming", "watching", "listening"]
        }
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config

config = load_config()

# Configurar intents necesarios
intents = discord.Intents.default()
intents.presences = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Diccionario para rastrear estados anteriores
previous_presences = {}
previous_voice_states = {}

@bot.event
async def on_ready():
    print(f'{bot.user} se ha conectado a Discord!')
    print(f'Bot ID: {bot.user.id}')
    
    # Verificar que el canal de notificaciones esté configurado
    if config.get('channel_id'):
        try:
            channel = bot.get_channel(config['channel_id'])
            if channel:
                print(f'Canal de notificaciones: #{channel.name}')
            else:
                print('⚠️  ADVERTENCIA: No se encontró el canal configurado. Usa !setchannel para configurarlo.')
        except:
            print('⚠️  ADVERTENCIA: Error al acceder al canal configurado.')

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
                await send_notification(
                    f"🎮 **{after.display_name}** está {get_activity_verb(activity_type_name)} **{after_activity.name}**"
                )

@bot.event
async def on_voice_state_update(member, before, after):
    """Detecta cuando alguien entra o sale de un canal de voz"""
    if config.get('ignore_bots', True) and member.bot:
        return
    
    # Entrada a canal de voz
    if not before.channel and after.channel:
        if config.get('notify_voice', True):
            await send_notification(
                f"🔊 **{member.display_name}** entró al canal de voz **{after.channel.name}**"
            )
    
    # Salida de canal de voz
    elif before.channel and not after.channel:
        if config.get('notify_voice_leave', False):
            await send_notification(
                f"🔇 **{member.display_name}** salió del canal de voz **{before.channel.name}**"
            )
    
    # Cambio de canal de voz
    elif before.channel and after.channel and before.channel != after.channel:
        if config.get('notify_voice', True):
            await send_notification(
                f"🔄 **{member.display_name}** cambió de **{before.channel.name}** a **{after.channel.name}**"
            )

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
    """Envía un mensaje al canal configurado"""
    channel_id = config.get('channel_id')
    if not channel_id:
        return
    
    try:
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(message)
        else:
            print(f'⚠️  No se encontró el canal con ID {channel_id}')
    except Exception as e:
        print(f'❌ Error al enviar notificación: {e}')

@bot.command(name='setchannel')
@commands.has_permissions(administrator=True)
async def set_channel(ctx, channel: discord.TextChannel = None):
    """Configura el canal donde se enviarán las notificaciones"""
    if channel is None:
        channel = ctx.channel
    
    config['channel_id'] = channel.id
    
    # Guardar configuración
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    await ctx.send(f'✅ Canal de notificaciones configurado: {channel.mention}')

@bot.command(name='toggle')
@commands.has_permissions(administrator=True)
async def toggle_notification(ctx, notification_type: str):
    """Activa o desactiva tipos de notificaciones
    
    Tipos disponibles:
    - games: Notificaciones de juegos
    - voice: Notificaciones de entrada a voz
    - voiceleave: Notificaciones de salida de voz
    """
    notification_type = notification_type.lower()
    
    if notification_type == 'games':
        config['notify_games'] = not config.get('notify_games', True)
        status = 'activadas' if config['notify_games'] else 'desactivadas'
        await ctx.send(f'✅ Notificaciones de juegos {status}')
    
    elif notification_type == 'voice':
        config['notify_voice'] = not config.get('notify_voice', True)
        status = 'activadas' if config['notify_voice'] else 'desactivadas'
        await ctx.send(f'✅ Notificaciones de entrada a voz {status}')
    
    elif notification_type == 'voiceleave':
        config['notify_voice_leave'] = not config.get('notify_voice_leave', False)
        status = 'activadas' if config['notify_voice_leave'] else 'desactivadas'
        await ctx.send(f'✅ Notificaciones de salida de voz {status}')
    
    else:
        await ctx.send('❌ Tipo de notificación no válido. Usa: `games`, `voice`, o `voiceleave`')
        return
    
    # Guardar configuración
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

@bot.command(name='config')
@commands.has_permissions(administrator=True)
async def show_config(ctx):
    """Muestra la configuración actual del bot"""
    channel_id = config.get('channel_id')
    channel_mention = 'No configurado'
    
    if channel_id:
        channel = bot.get_channel(channel_id)
        if channel:
            channel_mention = channel.mention
    
    embed = discord.Embed(title='⚙️ Configuración del Bot', color=discord.Color.blue())
    embed.add_field(name='Canal de notificaciones', value=channel_mention, inline=False)
    embed.add_field(name='Notificaciones de juegos', value='✅ Activadas' if config.get('notify_games') else '❌ Desactivadas', inline=True)
    embed.add_field(name='Notificaciones de entrada a voz', value='✅ Activadas' if config.get('notify_voice') else '❌ Desactivadas', inline=True)
    embed.add_field(name='Notificaciones de salida de voz', value='✅ Activadas' if config.get('notify_voice_leave') else '❌ Desactivadas', inline=True)
    embed.add_field(name='Ignorar bots', value='✅ Sí' if config.get('ignore_bots') else '❌ No', inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='test')
@commands.has_permissions(administrator=True)
async def test_notification(ctx):
    """Envía un mensaje de prueba al canal configurado"""
    await send_notification('🧪 **Mensaje de prueba** - El bot está funcionando correctamente!')
    await ctx.send('✅ Mensaje de prueba enviado!')

# Ejecutar el bot
if __name__ == '__main__':
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print('❌ ERROR: No se encontró DISCORD_BOT_TOKEN en las variables de entorno')
        print('Por favor, crea un archivo .env con: DISCORD_BOT_TOKEN=tu_token_aqui')
        exit(1)
    
    bot.run(token)

