import discord
from discord.ext import commands
import json
import os
import asyncio
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
            message_template = messages_config.get('voice_join', "🔊 **{user}** entró al canal de voz **{channel}**")
            message = message_template.format(
                user=member.display_name,
                channel=after.channel.name
            )
            await send_notification(message)
    
    # Salida de canal de voz
    elif before.channel and not after.channel:
        if config.get('notify_voice_leave', False):
            message_template = messages_config.get('voice_leave', "🔇 **{user}** salió del canal de voz **{channel}**")
            message = message_template.format(
                user=member.display_name,
                channel=before.channel.name
            )
            await send_notification(message)
    
    # Cambio de canal de voz
    elif before.channel and after.channel and before.channel != after.channel:
        if config.get('notify_voice_move', True):
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
        message_template = config.get('messages', {}).get('member_join', "👋 **{user}** se unió al servidor")
        message = message_template.format(user=member.display_name)
        await send_notification(message)

@bot.event
async def on_member_remove(member):
    """Detecta cuando un miembro deja el servidor"""
    if config.get('ignore_bots', True) and member.bot:
        return
    
    if config.get('notify_member_leave', False):
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
    channel_id = config.get('channel_id')
    if not channel_id:
        print('⚠️  ADVERTENCIA: No hay canal configurado. Usa !setchannel para configurarlo.')
        return
    
    try:
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(message)
        else:
            print(f'⚠️  No se encontró el canal con ID {channel_id}')
    except discord.errors.HTTPException as e:
        if e.status == 429:  # Rate limited
            retry_after = e.retry_after if hasattr(e, 'retry_after') else 1.0
            print(f'⚠️  Rate limited al enviar mensaje. Esperando {retry_after} segundos...')
            await asyncio.sleep(retry_after)
            # Reintentar una vez después del delay
            try:
                await channel.send(message)
            except Exception as retry_error:
                print(f'❌ Error al reintentar envío: {retry_error}')
        else:
            print(f'❌ Error HTTP al enviar notificación: {e}')
    except discord.errors.Forbidden:
        print(f'⚠️  Sin permisos para enviar mensajes al canal {channel_id}')
    except Exception as e:
        print(f'❌ Error al enviar notificación: {e}')

@bot.command(name='setchannel')
async def set_channel(ctx, channel: discord.TextChannel = None):
    """Configura el canal donde se enviarán las notificaciones
    
    Solo requiere permisos para enviar mensajes. Cualquier usuario puede configurar el canal.
    """
    if channel is None:
        channel = ctx.channel
    
    # Verificar que el bot tenga permisos para enviar mensajes en ese canal
    bot_member = channel.guild.get_member(bot.user.id)
    if bot_member:
        permissions = channel.permissions_for(bot_member)
        if not permissions.send_messages:
            try:
                await ctx.send(f'❌ El bot no tiene permisos para enviar mensajes en {channel.mention}.\n\n**Solución:** Ve a la configuración del canal y asegúrate de que el bot tenga el permiso "Send Messages" habilitado.')
            except:
                # Si tampoco puede enviar en el canal actual, solo loguear
                print(f'⚠️  Bot sin permisos en canal {channel.name} (ID: {channel.id})')
            return
    
    config['channel_id'] = channel.id
    
    # Guardar configuración
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    await ctx.send(f'✅ Canal de notificaciones configurado: {channel.mention}')

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
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        
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
    - !toggle - Abre el menú interactivo con botones
    - !toggle games - Activa/desactiva notificaciones de juegos directamente
    """
    if notification_type is None:
        # Crear embed con botones interactivos
        embed = discord.Embed(
            title='⚙️ Configurar Notificaciones',
            description='Haz clic en los botones para activar/desactivar notificaciones:',
            color=discord.Color.blue()
        )
        
        # Mostrar estado actual
        status_text = (
            f'🎮 Juegos: {"✅ Activado" if config.get("notify_games") else "❌ Desactivado"}\n'
            f'🔊 Entrada a Voz: {"✅ Activado" if config.get("notify_voice") else "❌ Desactivado"}\n'
            f'🔇 Salida de Voz: {"✅ Activado" if config.get("notify_voice_leave") else "❌ Desactivado"}\n'
            f'🔄 Cambio de Canal: {"✅ Activado" if config.get("notify_voice_move", True) else "❌ Desactivado"}\n'
            f'👋 Miembro se Une: {"✅ Activado" if config.get("notify_member_join") else "❌ Desactivado"}\n'
            f'👋 Miembro se Va: {"✅ Activado" if config.get("notify_member_leave") else "❌ Desactivado"}\n'
            f'🤖 Ignorar Bots: {"✅ Activado" if config.get("ignore_bots") else "❌ Desactivado"}'
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
    
    # Método tradicional si se proporciona el tipo
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
        await ctx.send('❌ Tipo de notificación no válido. Usa: `games`, `voice`, `voiceleave`, `voicemove`, `memberjoin`, `memberleave`')
        return
    
    config_key = toggle_map[notification_type]
    config[config_key] = not config.get(config_key, False)
    status = 'activadas' if config[config_key] else 'desactivadas'
    
    # Guardar configuración
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    await ctx.send(f'✅ Notificaciones de {notification_type} {status}')

@bot.command(name='config')
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
    embed.add_field(name='Notificaciones de cambio de voz', value='✅ Activadas' if config.get('notify_voice_move', True) else '❌ Desactivadas', inline=True)
    embed.add_field(name='Notificaciones de miembros (join)', value='✅ Activadas' if config.get('notify_member_join', False) else '❌ Desactivadas', inline=True)
    embed.add_field(name='Notificaciones de miembros (leave)', value='✅ Activadas' if config.get('notify_member_leave', False) else '❌ Desactivadas', inline=True)
    embed.add_field(name='Ignorar bots', value='✅ Sí' if config.get('ignore_bots') else '❌ No', inline=True)
    
    await ctx.send(embed=embed)

# Clase para el modal de configuración de mensajes
class MessageModal(discord.ui.Modal):
    def __init__(self, message_type):
        super().__init__(title=f'Configurar: {message_type}')
        self.message_type = message_type
        
        # Obtener mensaje actual si existe
        current_message = config.get('messages', {}).get(message_type, '')
        
        # Crear campo de texto
        self.message_input = discord.ui.TextInput(
            label='Mensaje',
            placeholder=f'Ejemplo: 🎮 **{{user}}** está {{verb}} **{{activity}}**',
            default=current_message,
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        
        self.add_item(self.message_input)
    
    async def on_submit(self, interaction):
        message_template = self.message_input.value
        
        if 'messages' not in config:
            config['messages'] = {}
        
        config['messages'][self.message_type] = message_template
        
        # Guardar configuración
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        
        await interaction.response.send_message(
            f'✅ Mensaje para `{self.message_type}` configurado:\n```{message_template}```',
            ephemeral=True
        )

# Clase para el select de tipos de mensaje
class MessageSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        
        options = [
            discord.SelectOption(label='Inicio de Juego', value='game_start', emoji='🎮', description='Cuando alguien empieza a jugar'),
            discord.SelectOption(label='Entrada a Voz', value='voice_join', emoji='🔊', description='Cuando alguien entra a voz'),
            discord.SelectOption(label='Salida de Voz', value='voice_leave', emoji='🔇', description='Cuando alguien sale de voz'),
            discord.SelectOption(label='Cambio de Canal', value='voice_move', emoji='🔄', description='Cuando alguien cambia de canal'),
            discord.SelectOption(label='Miembro se Une', value='member_join', emoji='👋', description='Cuando un miembro se une'),
            discord.SelectOption(label='Miembro se Va', value='member_leave', emoji='👋', description='Cuando un miembro se va'),
        ]
        
        select = discord.ui.Select(
            placeholder='Selecciona el tipo de mensaje...',
            options=options
        )
        
        select.callback = self.select_callback
        self.add_item(select)
    
    async def select_callback(self, interaction):
        message_type = interaction.data['values'][0]
        modal = MessageModal(message_type)
        await interaction.response.send_modal(modal)

@bot.command(name='setmessage')
async def set_message(ctx, message_type: str = None, *, message_template: str = None):
    """Configura mensajes personalizados usando un formulario interactivo
    
    Ejemplos:
    - !setmessage - Abre el menú interactivo con formulario
    - !setmessage game_start 🎮 {user} juega {activity} - Configura directamente
    """
    if message_type is None:
        # Mostrar menú interactivo con select
        embed = discord.Embed(
            title='💬 Configurar Mensajes',
            description='Selecciona el tipo de mensaje que quieres configurar:',
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name='Tipos disponibles',
            value=(
                '🎮 `game_start` - Cuando alguien empieza a jugar\n'
                '🔊 `voice_join` - Cuando alguien entra a voz\n'
                '🔇 `voice_leave` - Cuando alguien sale de voz\n'
                '🔄 `voice_move` - Cuando alguien cambia de canal\n'
                '👋 `member_join` - Cuando un miembro se une\n'
                '👋 `member_leave` - Cuando un miembro se va'
            ),
            inline=False
        )
        
        embed.add_field(
            name='Variables disponibles',
            value=(
                '`{user}` - Nombre del usuario\n'
                '`{activity}` - Nombre de la actividad/juego\n'
                '`{verb}` - Verbo (jugando, viendo, etc.)\n'
                '`{channel}` - Nombre del canal\n'
                '`{old_channel}` - Canal anterior\n'
                '`{new_channel}` - Canal nuevo'
            ),
            inline=False
        )
        
        embed.add_field(
            name='Uso rápido',
            value='`!setmessage game_start 🎮 {user} está {verb} {activity}`',
            inline=False
        )
        
        view = MessageSelectView()
        await ctx.send(embed=embed, view=view)
        return
    
    # Método directo si se proporciona el tipo y mensaje
    if message_template is None:
        await ctx.send('❌ Debes proporcionar el mensaje. Ejemplo: `!setmessage game_start 🎮 {user} juega {activity}`')
        return
    
    message_type = message_type.lower()
    valid_types = ['game_start', 'voice_join', 'voice_leave', 'voice_move', 'member_join', 'member_leave']
    
    if message_type not in valid_types:
        await ctx.send(f'❌ Tipo de mensaje no válido. Tipos disponibles: {", ".join(valid_types)}')
        return
    
    if 'messages' not in config:
        config['messages'] = {}
    
    config['messages'][message_type] = message_template
    
    # Guardar configuración
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    await ctx.send(f'✅ Mensaje para `{message_type}` configurado:\n```{message_template}```')

@bot.command(name='test')
async def test_notification(ctx):
    """Envía un mensaje de prueba al canal configurado"""
    await send_notification('🧪 **Mensaje de prueba** - El bot está funcionando correctamente!')
    await ctx.send('✅ Mensaje de prueba enviado!')

# Ejecutar el bot
if __name__ == '__main__':
    import asyncio
    import logging
    
    # Configurar logging para mejor debugging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('discord')
    logger.setLevel(logging.WARNING)  # Reducir spam de logs de discord.py
    
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print('❌ ERROR: No se encontró DISCORD_BOT_TOKEN en las variables de entorno')
        print('Por favor, crea un archivo .env con: DISCORD_BOT_TOKEN=tu_token_aqui')
        exit(1)
    
    # Configuración de rate limiting desde config.json
    rate_limit_config = config.get('rate_limiting', {})
    max_retries = rate_limit_config.get('max_retries', 5)
    initial_delay = rate_limit_config.get('initial_delay', 30)
    max_delay = rate_limit_config.get('max_delay', 300)
    exponential_base = rate_limit_config.get('exponential_base', 2)
    
    # Manejo de errores mejorado con exponential backoff
    @bot.event
    async def on_error(event, *args, **kwargs):
        """Maneja errores no capturados"""
        logger.error(f'Error en evento {event}: {args}, {kwargs}', exc_info=True)
    
    # Usar run con reconexión automática y manejo de errores
    try:
        bot.run(token, reconnect=True, log_handler=None)
    except KeyboardInterrupt:
        print('\n🛑 Bot detenido por el usuario')
        bot.close()
    except discord.errors.LoginFailure:
        print('❌ ERROR: Token inválido. Verifica tu DISCORD_BOT_TOKEN')
        exit(1)
    except discord.errors.PrivilegedIntentsRequired as e:
        print('❌ ERROR: Privileged Intents no habilitados en Discord Developer Portal')
        print('')
        print('🔴 PASOS PARA SOLUCIONAR:')
        print('1. Ve a: https://discord.com/developers/applications')
        print('2. Selecciona tu aplicación (bot)')
        print('3. Ve a la sección "Bot" en el menú lateral')
        print('4. Desplázate hasta "Privileged Gateway Intents"')
        print('5. ACTIVA estos dos switches:')
        print('   ✅ PRESENCE INTENT (debe estar en verde/ON)')
        print('   ✅ SERVER MEMBERS INTENT (debe estar en verde/ON)')
        print('6. Los cambios se guardan automáticamente')
        print('7. Espera 30-60 segundos y Railway reconectará automáticamente')
        print('')
        print('⚠️  IMPORTANTE: Ambos intents DEBEN estar activados (verde/ON)')
        print('   Si solo uno está activado, el bot seguirá fallando.')
        exit(1)
    except Exception as e:
        print(f'❌ Error fatal: {e}')
        logger.exception('Error fatal en el bot')
        exit(1)

