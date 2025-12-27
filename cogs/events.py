"""
Cog de Events - Maneja todos los event listeners del bot
"""

import discord
from discord.ext import commands
import logging
from datetime import datetime

from core.persistence import config, stats, save_stats, get_channel_id
from core.tracking import (
    record_game_event, record_voice_event, record_message_event,
    start_game_session, end_game_session,
    start_voice_session, end_voice_session
)
from core.cooldown import check_cooldown
from core.helpers import is_link_spam, get_activity_verb, send_notification

logger = logging.getLogger('dsbot')


class EventsCog(commands.Cog, name='Events'):
    """Maneja todos los eventos del bot (presence, voice, messages, reactions)"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Evento cuando el bot se conecta"""
        logger.info(f'{self.bot.user} se ha conectado a Discord!')
        logger.info(f'Bot ID: {self.bot.user.id}')
        
        # Verificar que el canal de notificaciones esté configurado
        channel_id = get_channel_id()
        if channel_id:
            try:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    logger.info(f'Canal de notificaciones: #{channel.name} (ID: {channel_id})')
                else:
                    logger.warning(f'⚠️  No se encontró el canal con ID {channel_id}')
            except Exception as e:
                logger.error(f'Error al acceder al canal: {e}')
        else:
            logger.warning('⚠️  Canal de notificaciones no configurado')
            logger.info('💡 Configura DISCORD_CHANNEL_ID en variables de entorno o usa !setchannel')
    
    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
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
                    await send_notification(message, self.bot)
        
        # Procesar juegos que terminaron (para finalizar sesiones)
        for game_name in ended_games:
            end_game_session(str(after.id), after.display_name, game_name)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
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
                    await send_notification(message, self.bot)
        
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
                await send_notification(message, self.bot)
        
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
                    await send_notification(message, self.bot)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Detecta mensajes para tracking de estadísticas"""
        # Ignorar mensajes del bot mismo
        if message.author == self.bot.user:
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
        
        # NO llamar process_commands() aquí - el bot lo hace automáticamente
        # cuando se usa @commands.Cog.listener() en lugar de @bot.event
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Detecta cuando alguien agrega una reacción"""
        # Ignorar reacciones del bot mismo
        if user == self.bot.user:
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
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Detecta cuando un miembro se une al servidor"""
        if config.get('ignore_bots', True) and member.bot:
            return
        
        if config.get('notify_member_join', False):
            logger.info(f'👋 Detectado: {member.display_name} se unió al servidor')
            message_template = config.get('messages', {}).get('member_join', "👋 **{user}** se unió al servidor")
            message = message_template.format(user=member.display_name)
            await send_notification(message, self.bot)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Detecta cuando un miembro deja el servidor"""
        if config.get('ignore_bots', True) and member.bot:
            return
        
        if config.get('notify_member_leave', False):
            logger.info(f'👋 Detectado: {member.display_name} dejó el servidor')
            message_template = config.get('messages', {}).get('member_leave', "👋 **{user}** dejó el servidor")
            message = message_template.format(user=member.display_name)
            await send_notification(message, self.bot)


async def setup(bot):
    """Función requerida para cargar el cog"""
    await bot.add_cog(EventsCog(bot))

