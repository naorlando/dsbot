"""
Cog de Events - Maneja todos los event listeners del bot
"""

import discord
from discord.ext import commands
import logging
import asyncio
from datetime import datetime

from core.persistence import config, stats, save_stats, get_channel_id
from core.session_dto import (
    save_message_event, save_reaction_event, save_sticker_event,
    save_connection_event
)
from core.voice_session import VoiceSessionManager
from core.game_session import GameSessionManager
from core.party_session import PartySessionManager
from core.health_check import SessionHealthCheck
from core.cooldown import check_cooldown
from core.helpers import is_link_spam, get_activity_verb, send_notification

logger = logging.getLogger('dsbot')


class EventsCog(commands.Cog, name='Events'):
    """Maneja todos los eventos del bot (presence, voice, messages, reactions)"""
    
    def __init__(self, bot):
        self.bot = bot
        self.deploy_notification_sent = False
        # Sistema centralizado de gestión de sesiones
        party_cfg = config.get('party_detection', {})
        game_cfg = config.get('game_session', {})
        party_grace = int(party_cfg.get('grace_period_seconds', 1800))
        game_grace = int(game_cfg.get('grace_period_seconds', 900))
        self.voice_manager = VoiceSessionManager(bot)
        self.party_manager = PartySessionManager(bot, grace_period_seconds=party_grace)
        self.game_manager = GameSessionManager(
            bot, party_manager=self.party_manager, grace_period_seconds=game_grace
        )
        
        # Recovery de sesiones + Health check periódico
        self.health_check = SessionHealthCheck(
            bot=bot,
            voice_manager=self.voice_manager,
            game_manager=self.game_manager,
            party_manager=self.party_manager,
            config=config
        )
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Evento cuando el bot se conecta"""
        logger.info(f'{self.bot.user} se ha conectado a Discord!')
        logger.info(f'Bot ID: {self.bot.user.id}')
        
        # Recovery de sesiones de voice después de reinicio
        await self.health_check.recover_on_startup()
        
        # 🧹 LIMPIEZA DE DATOS (ejecutar solo una vez con variable de entorno)
        import os
        from core.persistence import DATA_DIR
        
        stats_path = os.path.join(DATA_DIR, 'stats.json')
        
        if os.getenv('RUN_CLEANUP_PARTIES', 'false').lower() == 'true':
            logger.warning('🧹 EJECUTANDO LIMPIEZA DE PARTIES DUPLICADAS...')
            try:
                from scripts.cleanup_duplicate_parties import cleanup_duplicate_parties
                removed = cleanup_duplicate_parties(stats_path)
                logger.info(f'✅ Limpieza completada! Duplicados removidos: {removed}')
                logger.warning('⚠️  IMPORTANTE: Remover variable RUN_CLEANUP_PARTIES de Railway!')
            except Exception as e:
                logger.error(f'❌ Error en limpieza de datos: {e}')
        
        if os.getenv('RUN_FIX_SECONDS', 'false').lower() == 'true':
            logger.warning('🧹 EJECUTANDO CORRECCIÓN DE MINUTOS/SEGUNDOS...')
            try:
                from scripts.fix_seconds_as_minutes import fix_seconds_as_minutes
                corrections_count = fix_seconds_as_minutes(stats_path, threshold=3000, dry_run=False)
                logger.info(f'✅ Corrección completada! Entradas corregidas: {corrections_count}')
                logger.warning('⚠️  IMPORTANTE: Remover variable RUN_FIX_SECONDS de Railway!')
            except Exception as e:
                logger.error(f'❌ Error en corrección de datos: {e}')
        
        # Iniciar health check periódico (cada 30 min)
        self.health_check.start()

        await self._send_deploy_notification_once()
        
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

    async def _send_deploy_notification_once(self):
        """Notifica una vez por proceso que el deploy quedó activo."""
        if self.deploy_notification_sent:
            return

        import os

        if os.getenv('NOTIFY_DEPLOY', 'true').lower() != 'true':
            self.deploy_notification_sent = True
            return

        version = (
            os.getenv('BOT_VERSION')
            or os.getenv('RAILWAY_GIT_COMMIT_SHA', '')[:7]
            or 'nueva versión'
        )
        message = (
            f'🚀 **Deploy activo** · `{version}`\n'
            'El bot ya se encuentra online con la nueva versión.'
        )

        sent = await send_notification(message, self.bot)
        if sent is not None:
            logger.info(f'🚀 Notificación de deploy enviada: {version}')
        self.deploy_notification_sent = True
    
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
            
            # Cooldown de 10 minutos para evitar contar reconexiones rápidas
            if check_cooldown(user_id, 'daily_connection', cooldown_seconds=600):
                count_today, broke_record = save_connection_event(user_id, username)
                
                # NOTIFICACIONES DE MILESTONES (suficiente para tracking de conexiones)
                MILESTONES = [10, 25, 50]
                
                if count_today in MILESTONES:
                    # Mensajes divertidos según milestone
                    milestone_messages = {
                        10: f"🔥 ¡**{username}** se conectó **10 veces** hoy! ¿Todo bien en casa? 🏠",
                        25: f"🚨 ¡ALERTA! **{username}** ya se conectó **25 veces** hoy. Alguien deténgalo. 🛑",
                        50: f"💀 **50 CONEXIONES EN UN DÍA**. {username}, sal de tu casa. 🚪"
                    }
                    message = milestone_messages[count_today]
                    await send_notification(message, self.bot)
                    logger.info(f'🎉 Milestone alcanzado: {username} - {count_today} conexiones')
                
                # Récords personales se siguen trackeando en stats.json pero NO se notifican
                # (evita spam: cada conexión después de milestone 10 sería un "nuevo récord")
                if broke_record:
                    logger.debug(f'📊 Récord personal actualizado: {username} - {count_today} conexiones (anterior: {count_today - 1})')
        
        if not config.get('notify_games', True):
            return
        
        # Obtener TODAS las actividades (no solo la primera)
        # Discord puede tener: Custom Status + Juego + Spotify simultáneamente
        before_activities = before.activities
        after_activities = after.activities
        
        # Filtrar solo actividades de juegos (ignorar custom status y Spotify)
        def get_game_activities(activities):
            return [
                act for act in activities 
                if act.type in [
                    discord.ActivityType.playing,     # Juegos
                    discord.ActivityType.streaming,   # Streaming
                    discord.ActivityType.watching,    # Viendo
                    # ❌ NO incluir listening (Spotify) - no es un juego
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
            
            # ✅ VERIFICACIÓN MULTICAPA: Filtrar juegos falsos/custom
            
            # 1. Verificar que NO sea un custom status (type='custom')
            if activity_type_name == 'custom':
                logger.debug(f'🚫 Custom status ignorado: "{game_name}" (usuario: {after.display_name})')
                continue
            
            # 2. Obtener clase de actividad (para verificar legitimidad)
            activity_class = game_activity.__class__.__name__
            
            # 3. WHITELIST: Solo aceptar clases de actividad legítimas
            # Game: Juegos normales detectados por Discord
            # Streaming: Streaming en Twitch/YouTube
            # Activity: Rich Presence oficial (verificado por Discord)
            # Spotify: Música (aunque se maneja aparte)
            allowed_classes = ['Game', 'Streaming', 'Activity', 'Spotify']
            
            if activity_class not in allowed_classes:
                logger.debug(f'🚫 Tipo de actividad no permitido: "{game_name}" (clase: {activity_class}, usuario: {after.display_name})')
                continue
            
            # 4. Verificar application_id (usar getattr para evitar crash con Spotify)
            app_id = getattr(game_activity, 'application_id', None)
            
            # Solo Spotify puede no tener app_id (se maneja diferente)
            if not app_id and activity_class != 'Spotify':
                logger.debug(f'🚫 Actividad sin application_id ignorada: "{game_name}" (clase: {activity_class}, usuario: {after.display_name})')
                continue
            
            # 5. Verificar contra blacklist configurable
            blacklisted_apps = config.get('blacklisted_app_ids', [])
            if app_id and str(app_id) in blacklisted_apps:
                logger.debug(f'🚫 Aplicación en blacklist: "{game_name}" (app_id: {app_id}, usuario: {after.display_name})')
                continue
            
            # 6. Filtro de nombres sospechosos (última línea de defensa)
            suspicious_names = ['test', 'asdf', 'fake', 'custom', 'prueba', 'ejemplo']
            if game_name.lower() in suspicious_names:
                logger.warning(f'⚠️  Nombre sospechoso ignorado: "{game_name}" (app_id: {app_id}, clase: {activity_class}, usuario: {after.display_name})')
                continue
            
            # Si llegó aquí, la actividad pasó TODAS las verificaciones
            if activity_class == 'Spotify':
                logger.info(f'✅ Actividad verificada: "{game_name}" (tipo: Spotify, usuario: {after.display_name})')
            else:
                logger.info(f'✅ Actividad verificada: "{game_name}" (app_id: {app_id}, clase: {activity_class}, type: {activity_type_name}, usuario: {after.display_name})')
            
            if activity_type_name in config.get('game_activity_types', ['playing', 'streaming', 'watching', 'listening']):
                # Usar GameSessionManager para manejar inicio de juego
                await self.game_manager.handle_start(after, config, game_activity=game_activity, activity_type=activity_type_name)
        
        # Procesar juegos que terminaron (para finalizar sesiones)
        for game_name in ended_games:
            await self.game_manager.handle_end(after, config, game_name=game_name)
        
        # Detección de parties con sistema de sesiones (después de procesar cambios de juegos)
        try:
            # Obtener jugadores agrupados por juego
            players_by_game = self.party_manager.get_active_players_by_game(after.guild)
            
            # Obtener juegos con parties activas (COPIAR para evitar "Set changed size")
            active_party_games = set(self.party_manager.active_sessions.keys())
            current_games = set(players_by_game.keys())
            
            # Procesar cada juego con suficientes jugadores
            for game_name, players in players_by_game.items():
                await self.party_manager.handle_start(game_name, players, after.guild.id, config)
            
            # Finalizar parties de juegos que ya no tienen suficientes jugadores
            # 🚨 FIX: Convertir a lista para evitar "Set changed size during iteration"
            games_to_end = list(active_party_games - current_games)
            for game_name in games_to_end:
                await self.party_manager.handle_end(game_name, config)
            
            # Health check simplificado: no necesita activación manual
        except Exception as e:
            logger.error(f'Error en gestión de parties: {e}')
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Detecta cuando alguien entra o sale de un canal de voz"""
        if config.get('ignore_bots', True) and member.bot:
            return
        
        # Entrada a canal de voz
        if not before.channel and after.channel:
            await self.voice_manager.handle_start(member, after.channel, config)
        
        # Salida de canal de voz (corte total: no aplicar gracia que deje sesión colgada)
        elif before.channel and not after.channel:
            await self.voice_manager.handle_end(member, before.channel, config, skip_grace=True)
        
        # Cambio de canal de voz
        elif before.channel and after.channel and before.channel != after.channel:
            await self.voice_manager.handle_voice_move(member, before.channel, after.channel, config)
    
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
            for sticker in message.stickers:
                save_sticker_event(user_id, username, sticker.name)
        
        # Solo trackear mensajes si tiene contenido Y no es spam de links
        if message_length > 0 and not is_link_spam(message_content):
            save_message_event(user_id, username, message_length)
        
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
        
        # Guardar reacción usando DTO
        save_reaction_event(user_id, username, emoji_name)
    
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

