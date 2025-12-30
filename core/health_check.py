"""
Health Check System para Sesiones
Validación periódica y auto-reparación de sesiones activas
Recuperación de notificaciones perdidas en reinicios
"""

import logging
from discord.ext import tasks
from typing import Dict, Set
from core.pending_notifications import (
    get_pending_voice_notifications,
    get_pending_game_notifications,
    remove_voice_notification,
    remove_game_notification
)
from core.helpers import send_notification

logger = logging.getLogger('dsbot')


class SessionHealthCheck:
    """
    Sistema de validación periódica de sesiones (sin persistencia)
    
    Características:
    - Se activa solo cuando hay sesiones activas (0% overhead sin usuarios)
    - Validación cada 30 minutos
    - Detecta y corrige sesiones huérfanas
    - No requiere persistencia en disco
    """
    
    def __init__(self, bot, voice_manager, game_manager, party_manager):
        """
        Args:
            bot: Instancia del bot de Discord
            voice_manager: VoiceSessionManager
            game_manager: GameSessionManager
            party_manager: PartySessionManager
        """
        self.bot = bot
        self.voice_manager = voice_manager
        self.game_manager = game_manager
        self.party_manager = party_manager
        self._task_running = False
        self._initial_recovery_done = False
        
        logger.info('🏥 Health check inicializado (modo: dinámico con recuperación)')
    
    def _has_active_sessions(self) -> bool:
        """Verifica si hay sesiones activas en cualquier manager"""
        return (
            len(self.voice_manager.active_sessions) > 0 or
            len(self.game_manager.active_sessions) > 0 or
            len(self.party_manager.active_sessions) > 0
        )
    
    def start_if_needed(self):
        """Inicia el health check solo si hay sesiones activas"""
        if self._has_active_sessions() and not self._task_running:
            try:
                self.health_check_task.start()
                self._task_running = True
                logger.info('🏥 Health check activado (hay sesiones activas)')
            except RuntimeError:
                # Task ya está corriendo
                self._task_running = True
    
    def stop_if_empty(self):
        """Detiene el health check si no hay sesiones activas"""
        if not self._has_active_sessions() and self._task_running:
            self.health_check_task.cancel()
            self._task_running = False
            logger.info('🏥 Health check desactivado (no hay sesiones activas)')
    
    @tasks.loop(minutes=30)
    async def health_check_task(self):
        """
        Ejecuta validación cada 30 minutos.
        Solo corre cuando hay sesiones activas.
        """
        try:
            logger.info('🏥 Iniciando health check de sesiones...')
            
            # Primera ejecución después de reinicio: recuperar notificaciones perdidas
            if not self._initial_recovery_done:
                await self._recover_lost_notifications()
                self._initial_recovery_done = True
            
            fixed_voice = await self._check_voice_sessions()
            fixed_games = await self._check_game_sessions()
            fixed_parties = await self._check_party_sessions()
            
            total_fixed = fixed_voice + fixed_games + fixed_parties
            
            if total_fixed > 0:
                logger.warning(
                    f'🔧 Health check completado: '
                    f'{fixed_voice} voice, {fixed_games} games, {fixed_parties} parties arregladas'
                )
            else:
                logger.info('✅ Health check completado: Todo OK')
            
            # Detener si no quedan sesiones activas
            self.stop_if_empty()
                
        except Exception as e:
            logger.error(f'❌ Error en health check: {e}', exc_info=True)
    
    @health_check_task.before_loop
    async def before_health_check(self):
        """Espera a que el bot esté listo antes de iniciar"""
        await self.bot.wait_until_ready()
        logger.debug('🏥 Health check task listo para ejecutarse')
    
    async def _recover_lost_notifications(self):
        """
        Maneja sesiones activas después de reinicio del bot.
        
        Compara pending_notifications.json con el estado actual de Discord:
        - Si el usuario SIGUE activo: Recrear sesión silenciosa + activar cooldown
        - Si el usuario NO está activo: Limpiar pending_notifications.json
        
        NO envía notificaciones retroactivas para evitar spam.
        """
        try:
            logger.info('🔄 Recuperando estado después de reinicio...')
            
            from core.cooldown import check_cooldown
            
            restored_voice = 0
            restored_games = 0
            cleaned_voice = 0
            cleaned_games = 0
            
            # Recuperar notificaciones de voz
            pending_voice = get_pending_voice_notifications()
            for user_id, data in pending_voice.items():
                try:
                    # Verificar si el usuario sigue en voz
                    is_in_voice = False
                    member_obj = None
                    voice_channel = None
                    
                    for guild in self.bot.guilds:
                        member = guild.get_member(int(user_id))
                        if member and member.voice:
                            is_in_voice = True
                            member_obj = member
                            voice_channel = member.voice.channel
                            break
                    
                    if is_in_voice and member_obj:
                        # Usuario SIGUE en voz: Recrear sesión silenciosa + activar cooldown
                        from core.voice_session import VoiceSession
                        
                        session = VoiceSession(
                            user_id=user_id,
                            username=data['username'],
                            channel_name=voice_channel.name,
                            channel_id=voice_channel.id,
                            guild_id=member_obj.guild.id
                        )
                        session.is_confirmed = True  # Ya está confirmada (lleva tiempo activa)
                        session.entry_notification_sent = True  # Ya se notificó antes del reinicio
                        
                        self.voice_manager.active_sessions[user_id] = session
                        
                        # Activar cooldown para evitar re-notificar (20 minutos)
                        check_cooldown(user_id, 'voice', cooldown_seconds=1200)
                        
                        restored_voice += 1
                        logger.info(f'♻️  Sesión de voz restaurada: {data["username"]} en {voice_channel.name}')
                    else:
                        # Usuario NO está en voz: Solo limpiar (sin notificar)
                        remove_voice_notification(user_id)
                        cleaned_voice += 1
                        logger.debug(f'🧹 Sesión de voz limpiada: {data["username"]}')
                
                except Exception as e:
                    logger.error(f'Error recuperando sesión de voz {user_id}: {e}')
            
            # Recuperar notificaciones de juegos
            pending_games = get_pending_game_notifications()
            for key, data in pending_games.items():
                try:
                    user_id = data['user_id']
                    game_name = data['game_name']
                    
                    # Verificar si el usuario sigue jugando
                    is_playing = False
                    member_obj = None
                    activity_obj = None
                    
                    for guild in self.bot.guilds:
                        member = guild.get_member(int(user_id))
                        if member:
                            for activity in member.activities:
                                if hasattr(activity, 'name') and activity.name == game_name:
                                    is_playing = True
                                    member_obj = member
                                    activity_obj = activity
                                    break
                        if is_playing:
                            break
                    
                    if is_playing and member_obj and activity_obj:
                        # Usuario SIGUE jugando: Recrear sesión silenciosa + activar cooldown
                        from core.game_session import GameSession
                        
                        app_id = getattr(activity_obj, 'application_id', None)
                        activity_type = str(activity_obj.type).split('.')[-1]
                        
                        session = GameSession(
                            user_id=user_id,
                            username=data['username'],
                            game_name=game_name,
                            app_id=app_id,
                            activity_type=activity_type,
                            guild_id=member_obj.guild.id
                        )
                        session.is_confirmed = True  # Ya está confirmada (lleva tiempo activa)
                        session.entry_notification_sent = True  # Ya se notificó antes del reinicio
                        
                        self.game_manager.active_sessions[user_id] = session
                        
                        # Activar cooldown para evitar re-notificar (30 minutos por juego)
                        check_cooldown(user_id, f'game:{game_name}', cooldown_seconds=1800)
                        
                        restored_games += 1
                        logger.info(f'♻️  Sesión de juego restaurada: {data["username"]} jugando {game_name}')
                    else:
                        # Usuario NO está jugando: Solo limpiar (sin notificar)
                        remove_game_notification(user_id, game_name)
                        cleaned_games += 1
                        logger.debug(f'🧹 Sesión de juego limpiada: {data["username"]} - {game_name}')
                
                except Exception as e:
                    logger.error(f'Error recuperando sesión de juego {key}: {e}')
            
            # Resumen
            if restored_voice > 0 or restored_games > 0:
                logger.info(
                    f'♻️  Sesiones restauradas después de reinicio: '
                    f'{restored_voice} voz, {restored_games} juegos '
                    f'(limpiadas: {cleaned_voice} voz, {cleaned_games} juegos)'
                )
            else:
                logger.info('✅ No hay sesiones pendientes para restaurar')
        
        except Exception as e:
            logger.error(f'❌ Error en recuperación de sesiones: {e}', exc_info=True)
    
    async def _check_voice_sessions(self) -> int:
        """
        Valida sesiones de voz activas.
        
        Detecta:
        - Usuarios que ya no están en el canal de voz
        - Usuarios que cambiaron de canal sin notificación
        
        Returns:
            Cantidad de sesiones arregladas
        """
        fixed = 0
        sessions_to_end = []
        
        for user_id, session in list(self.voice_manager.active_sessions.items()):
            try:
                # Obtener guild
                guild = self.bot.get_guild(session.guild_id)
                if not guild:
                    logger.warning(f'⚠️  Guild no encontrado para sesión: {session.username}')
                    sessions_to_end.append(user_id)
                    fixed += 1
                    continue
                
                # Obtener member
                member = guild.get_member(int(user_id))
                
                # Caso 1: Usuario no existe o no está en voz
                if not member or not member.voice:
                    logger.warning(f'🔧 Sesión huérfana detectada: {session.username} (ya no en voz)')
                    sessions_to_end.append(user_id)
                    fixed += 1
                    continue
                
                # Caso 2: Usuario cambió de canal
                if member.voice.channel.id != session.channel_id:
                    logger.warning(
                        f'🔧 Usuario cambió de canal sin evento: {session.username} '
                        f'({session.channel_name} → {member.voice.channel.name})'
                    )
                    sessions_to_end.append(user_id)
                    fixed += 1
                    continue
            
            except Exception as e:
                logger.error(f'❌ Error validando sesión de voz {user_id}: {e}')
        
        # Finalizar sesiones huérfanas (sin notificaciones)
        for user_id in sessions_to_end:
            if user_id in self.voice_manager.active_sessions:
                session = self.voice_manager.active_sessions[user_id]
                
                # Guardar tiempo si la sesión estaba confirmada
                if session.is_confirmed:
                    from core.session_dto import save_voice_time, clear_voice_session
                    duration_seconds = session.duration_seconds()
                    minutes = int(duration_seconds / 60)
                    
                    if minutes > 0:
                        save_voice_time(user_id, session.username, minutes)
                        logger.info(f'💾 Tiempo guardado (health check): {session.username} - {minutes} min')
                    
                    clear_voice_session(user_id)
                
                # Cancelar task de verificación si existe
                if session.verification_task and not session.verification_task.done():
                    session.verification_task.cancel()
                
                # Eliminar sesión
                del self.voice_manager.active_sessions[user_id]
        
        return fixed
    
    async def _check_game_sessions(self) -> int:
        """
        Valida sesiones de juegos activas.
        
        Detecta:
        - Usuarios que ya no están jugando ese juego
        
        Returns:
            Cantidad de sesiones arregladas
        """
        fixed = 0
        sessions_to_end = []
        
        for user_id, session in list(self.game_manager.active_sessions.items()):
            try:
                # Obtener guild
                guild = self.bot.get_guild(session.guild_id)
                if not guild:
                    logger.warning(f'⚠️  Guild no encontrado para sesión de juego: {session.username}')
                    sessions_to_end.append(user_id)
                    fixed += 1
                    continue
                
                # Obtener member
                member = guild.get_member(int(user_id))
                
                # Usuario no existe
                if not member:
                    logger.warning(f'🔧 Sesión de juego huérfana: {session.username} ({session.game_name})')
                    sessions_to_end.append(user_id)
                    fixed += 1
                    continue
                
                # Verificar si sigue jugando el mismo juego
                is_playing = False
                for activity in member.activities:
                    if hasattr(activity, 'name') and activity.name == session.game_name:
                        is_playing = True
                        break
                
                if not is_playing:
                    logger.warning(f'🔧 Usuario ya no juega: {session.username} ({session.game_name})')
                    sessions_to_end.append(user_id)
                    fixed += 1
            
            except Exception as e:
                logger.error(f'❌ Error validando sesión de juego {user_id}: {e}')
        
        # Finalizar sesiones huérfanas
        for user_id in sessions_to_end:
            if user_id in self.game_manager.active_sessions:
                session = self.game_manager.active_sessions[user_id]
                
                # Guardar tiempo si la sesión estaba confirmada
                if session.is_confirmed:
                    from core.session_dto import save_game_time, increment_game_count, clear_game_session
                    duration_seconds = session.duration_seconds()
                    minutes = int(duration_seconds / 60)
                    
                    if minutes > 0:
                        save_game_time(user_id, session.username, session.game_name, minutes)
                        increment_game_count(user_id, session.username, session.game_name)
                        logger.info(f'💾 Tiempo guardado (health check): {session.username} - {session.game_name} - {minutes} min')
                    
                    clear_game_session(user_id, session.game_name)
                
                # Cancelar task de verificación si existe
                if session.verification_task and not session.verification_task.done():
                    session.verification_task.cancel()
                
                # Eliminar sesión
                del self.game_manager.active_sessions[user_id]
        
        return fixed
    
    async def _check_party_sessions(self) -> int:
        """
        Valida sesiones de parties activas.
        
        Detecta:
        - Parties donde ya no hay suficientes jugadores (< 2)
        - Parties donde los jugadores dejaron de jugar
        
        Returns:
            Cantidad de sesiones arregladas
        """
        fixed = 0
        sessions_to_end = []
        
        for game_name, session in list(self.party_manager.active_sessions.items()):
            try:
                # Obtener guild
                guild = self.bot.get_guild(session.guild_id)
                if not guild:
                    logger.warning(f'⚠️  Guild no encontrado para party: {game_name}')
                    sessions_to_end.append(game_name)
                    fixed += 1
                    continue
                
                # Contar cuántos jugadores siguen activos en ese juego
                active_count = 0
                for player_id in session.player_ids:
                    member = guild.get_member(int(player_id))
                    if member:
                        for activity in member.activities:
                            if hasattr(activity, 'name') and activity.name == game_name:
                                active_count += 1
                                break
                
                # Si hay menos de 2 jugadores, ya no es party
                if active_count < 2:
                    logger.warning(
                        f'🔧 Party ya no cumple requisitos: {game_name} '
                        f'({active_count}/2 jugadores activos)'
                    )
                    sessions_to_end.append(game_name)
                    fixed += 1
            
            except Exception as e:
                logger.error(f'❌ Error validando party {game_name}: {e}')
        
        # Finalizar parties huérfanas
        for game_name in sessions_to_end:
            if game_name in self.party_manager.active_sessions:
                # Usar el método handle_end del party_manager
                # Pasamos un config vacío ya que no vamos a notificar
                try:
                    await self.party_manager.handle_end(game_name, {})
                except Exception as e:
                    logger.error(f'❌ Error finalizando party {game_name}: {e}')
        
        return fixed
    
    def cleanup(self):
        """Limpia recursos al destruir el health check"""
        if self._task_running:
            self.health_check_task.cancel()
            self._task_running = False
            logger.info('🏥 Health check limpiado')

