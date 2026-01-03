"""
Session Recovery System + Periodic Health Check
Recuperación de sesiones de voice después de reinicio del bot
+ Validación periódica de sesiones con grace period expirado
+ Limpieza de sesiones huérfanas en stats.json
"""

import logging
import asyncio
from datetime import datetime
from discord.ext import tasks
from core.pending_notifications import (
    get_pending_voice_notifications,
    remove_voice_notification
)
from core.cooldown import check_cooldown
from core.persistence import stats, save_stats

logger = logging.getLogger('dsbot')


class SessionHealthCheck:
    """
    Sistema de recuperación y validación de sesiones.
    
    FUNCIONALIDADES:
    1. Recovery en on_ready: Recupera sesiones de voice después de reinicio
    2. Health check periódico (cada 30 min): Finaliza sesiones con grace period expirado
    """
    
    def __init__(self, bot, voice_manager, game_manager, party_manager, config):
        """
        Args:
            bot: Instancia del bot de Discord
            voice_manager: VoiceSessionManager
            game_manager: GameSessionManager
            party_manager: PartySessionManager
            config: Configuración del bot
        """
        self.bot = bot
        self.voice_manager = voice_manager
        self.game_manager = game_manager
        self.party_manager = party_manager
        self.config = config
        self._recovery_done = False
        
        logger.info('🏥 Health check inicializado (recovery + validación periódica)')
    
    async def recover_on_startup(self):
        """
        Ejecuta recovery UNA VEZ cuando el bot inicia.
        Recupera sesiones de TODOS los tipos: voice, games, parties.
        """
        if self._recovery_done:
            logger.debug('Recovery ya ejecutado, omitiendo')
            return
        
        try:
            logger.info('🔄 Recuperando sesiones después de reinicio...')
            
            # Recuperar voice (desde pending_notifications.json)
            voice_restored = await self._recover_voice_sessions()
            
            # Recuperar games (desde stats.json)
            game_restored = await self._recover_game_sessions()
            
            # Recuperar parties (desde stats.json)
            party_restored = await self._recover_party_sessions()
            
            self._recovery_done = True
            
            total = voice_restored + game_restored + party_restored
            if total > 0:
                logger.info(f'✅ Recovery completado: {voice_restored} voice, {game_restored} games, {party_restored} parties')
            else:
                logger.info('✅ No hay sesiones pendientes para restaurar')
        except Exception as e:
            logger.error(f'❌ Error en recovery: {e}', exc_info=True)
    
    async def _recover_voice_sessions(self):
        """
        Recupera sesiones de voice después de reinicio.
        
        Si usuario SIGUE en voz: Recrear sesión silenciosa
        Si usuario NO está en voz: Limpiar pending_notifications.json
        """
        try:
            restored = 0
            cleaned = 0
            
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
                        # Usuario SIGUE en voz: Recrear sesión silenciosa
                        from core.voice_session import VoiceSession
                        
                        session = VoiceSession(
                            user_id=user_id,
                            username=data['username'],
                            channel_name=voice_channel.name,
                            channel_id=voice_channel.id,
                            guild_id=member_obj.guild.id
                        )
                        session.is_confirmed = True
                        session.entry_notification_sent = True
                        
                        self.voice_manager.active_sessions[user_id] = session
                        
                        # Activar cooldown para evitar re-notificar (20 minutos)
                        check_cooldown(user_id, 'voice', cooldown_seconds=1200)
                        
                        restored += 1
                        logger.info(f'♻️  Sesión de voz restaurada: {data["username"]} en {voice_channel.name}')
                    else:
                        # Usuario NO está en voz: Solo limpiar
                        remove_voice_notification(user_id)
                        cleaned += 1
                        logger.debug(f'🧹 Sesión de voz limpiada: {data["username"]}')
                
                except Exception as e:
                    logger.error(f'Error recuperando sesión de voz {user_id}: {e}')
            
            if restored > 0:
                logger.info(f'♻️  {restored} sesiones de voz restauradas (limpiadas: {cleaned})')
            
            return restored
        
        except Exception as e:
            logger.error(f'❌ Error en recuperación de voice: {e}', exc_info=True)
            return 0
    
    async def _recover_game_sessions(self):
        """
        Recupera sesiones de juegos desde stats.json.
        Solo recupera sesiones <1h para evitar colgadas.
        """
        try:
            restored = 0
            
            for user_id, user_data in stats.get('users', {}).items():
                for game_name, game_data in user_data.get('games', {}).items():
                    current_session = game_data.get('current_session')
                    
                    if not current_session:
                        continue
                    
                    try:
                        # Calcular antigüedad
                        start_time = datetime.fromisoformat(current_session['start'])
                        age_minutes = (datetime.now() - start_time).total_seconds() / 60
                        
                        # Solo recuperar sesiones recientes (<1h)
                        if age_minutes > 60:
                            continue
                        
                        # Buscar usuario en guilds
                        member = None
                        for guild in self.bot.guilds:
                            member = guild.get_member(int(user_id))
                            if member:
                                break
                        
                        if not member:
                            continue
                        
                        # Verificar si Discord SIGUE reportando este juego
                        game_activity = None
                        for activity in member.activities:
                            if activity.name == game_name:
                                game_activity = activity
                                break
                        
                        if not game_activity:
                            continue
                        
                        # Usuario SIGUE jugando → recrear sesión
                        from core.game_session import GameSession
                        
                        session = GameSession(
                            user_id=user_id,
                            username=user_data.get('username', member.display_name),
                            game_name=game_name,
                            app_id=getattr(game_activity, 'application_id', None),
                            activity_type=game_activity.type.name.lower(),
                            guild_id=member.guild.id
                        )
                        
                        # Usar start_time ORIGINAL del disco
                        session.start_time = start_time
                        session.is_confirmed = True
                        session.entry_notification_sent = True
                        
                        self.game_manager.active_sessions[user_id] = session
                        
                        # Activar cooldown para evitar re-notificar
                        check_cooldown(game_name, f'{user_id}:game:{game_name}', cooldown_seconds=1800)
                        
                        restored += 1
                        logger.info(f'♻️  Game session restaurada: {session.username} - {game_name} (inicio: {start_time.strftime("%H:%M")})')
                    
                    except Exception as e:
                        logger.error(f'Error recuperando game session {game_name} de {user_id}: {e}')
            
            return restored
        
        except Exception as e:
            logger.error(f'❌ Error en recuperación de games: {e}', exc_info=True)
            return 0
    
    async def _recover_party_sessions(self):
        """
        Recupera party sessions desde stats.json.
        Solo recupera parties recientes (<1h).
        """
        try:
            restored = 0
            
            for game_name, party_data in stats.get('parties', {}).get('active', {}).items():
                try:
                    # Calcular antigüedad
                    start_time = datetime.fromisoformat(party_data['start'])
                    age_minutes = (datetime.now() - start_time).total_seconds() / 60
                    
                    # Solo recuperar parties recientes (<1h)
                    if age_minutes > 60:
                        continue
                    
                    # Verificar cuántos jugadores SIGUEN jugando
                    current_players = []
                    guild_id = None
                    
                    for guild in self.bot.guilds:
                        for member in guild.members:
                            if member.bot:
                                continue
                            
                            for activity in member.activities:
                                if activity.name == game_name:
                                    current_players.append({
                                        'user_id': str(member.id),
                                        'username': member.display_name,
                                        'activity': activity
                                    })
                                    guild_id = guild.id
                                    break
                    
                    # Si hay ≥2 jugadores, recrear party
                    if len(current_players) >= 2 and guild_id:
                        from core.party_session import PartySession
                        
                        player_ids = {p['user_id'] for p in current_players}
                        player_names = [p['username'] for p in current_players]
                        
                        session = PartySession(
                            game_name=game_name,
                            player_ids=player_ids,
                            player_names=player_names,
                            guild_id=guild_id
                        )
                        
                        # Usar start_time ORIGINAL del disco
                        session.start_time = start_time
                        session.is_confirmed = True
                        session.notification_message = None
                        
                        self.party_manager.active_sessions[game_name] = session
                        
                        restored += 1
                        logger.info(f'♻️  Party restaurada: {game_name} con {len(current_players)} jugadores (inicio: {start_time.strftime("%H:%M")})')
                
                except Exception as e:
                    logger.error(f'Error recuperando party {game_name}: {e}')
            
            return restored
        
        except Exception as e:
            logger.error(f'❌ Error en recuperación de parties: {e}', exc_info=True)
            return 0
    
    # ==================== HEALTH CHECK PERIÓDICO ====================
    
    @tasks.loop(minutes=30)
    async def periodic_check(self):
        """
        Valida sesiones cada 30 minutos.
        Finaliza sesiones con grace period expirado (sesiones "colgadas").
        
        NOTA: Se ejecuta inmediatamente al iniciar para detectar sesiones
        colgadas que sobrevivieron a un reinicio rápido.
        """
        try:
            # Contar sesiones activas
            game_sessions = len(self.game_manager.active_sessions)
            party_sessions = len(self.party_manager.active_sessions)
            
            logger.info(f'🏥 Health check iniciado (games: {game_sessions}, parties: {party_sessions})')
            
            finalized = 0
            
            # Revisar game sessions en memoria
            finalized += await self._check_game_sessions()
            
            # Revisar party sessions en memoria
            finalized += await self._check_party_sessions()
            
            # Limpiar sesiones colgadas en stats.json (huérfanas del disco)
            cleaned = await self._cleanup_orphaned_sessions_in_stats()
            
            if finalized > 0 or cleaned > 0:
                logger.info(f'✅ Health check: {finalized} sesiones finalizadas, {cleaned} sesiones colgadas limpiadas')
            else:
                logger.info('✅ Health check: Todo OK')
        
        except Exception as e:
            logger.error(f'❌ Error en health check periódico: {e}', exc_info=True)
    
    @periodic_check.before_loop
    async def before_periodic_check(self):
        """Esperar a que el bot esté listo antes de iniciar el health check"""
        await self.bot.wait_until_ready()
    
    async def _check_game_sessions(self) -> int:
        """
        Revisa sesiones de juego con grace period expirado.
        
        Returns:
            Número de sesiones finalizadas
        """
        finalized = 0
        now = datetime.now()
        grace_period_seconds = 1200  # 20 minutos
        
        # Copiar lista para evitar modificación durante iteración
        sessions_to_check = list(self.game_manager.active_sessions.items())
        
        for user_id, session in sessions_to_check:
            try:
                # Calcular tiempo desde última actividad
                time_since_activity = (now - session.last_activity_update).total_seconds()
                
                # Si excedió el grace period, finalizar
                if time_since_activity > grace_period_seconds:
                    logger.info(f'🔄 Finalizando sesión expirada: {session.username} - {session.game_name} ({int(time_since_activity/60)} min sin actividad)')
                    
                    # Obtener member object
                    member = await self._get_member(int(user_id), session.guild_id)
                    if member:
                        await self.game_manager.handle_game_end(member, session.game_name, self.config)
                        finalized += 1
                    else:
                        # Si no encontramos el member, limpiar directamente
                        logger.warning(f'⚠️  No se pudo obtener member para {user_id}, limpiando sesión')
                        if user_id in self.game_manager.active_sessions:
                            del self.game_manager.active_sessions[user_id]
                        finalized += 1
            
            except Exception as e:
                logger.error(f'Error revisando sesión de juego {user_id}: {e}')
        
        return finalized
    
    async def _check_party_sessions(self) -> int:
        """
        Revisa sesiones de party con grace period expirado.
        
        Returns:
            Número de sesiones finalizadas
        """
        finalized = 0
        now = datetime.now()
        grace_period_seconds = 1200  # 20 minutos
        
        # Copiar lista para evitar modificación durante iteración
        sessions_to_check = list(self.party_manager.active_sessions.items())
        
        for game_name, session in sessions_to_check:
            try:
                # Solo revisar parties activas (no las inactivas)
                if session.state != 'active':
                    continue
                
                # Calcular tiempo desde última actividad
                time_since_activity = (now - session.last_activity_update).total_seconds()
                
                # Si excedió el grace period, marcar como inactiva
                if time_since_activity > grace_period_seconds:
                    logger.info(f'🔄 Marcando party como inactiva: {game_name} ({int(time_since_activity/60)} min sin actividad)')
                    await self.party_manager.handle_end(game_name, self.config)
                    finalized += 1
            
            except Exception as e:
                logger.error(f'Error revisando party {game_name}: {e}')
        
        return finalized
    
    async def _get_member(self, user_id: int, guild_id: int):
        """
        Obtiene un member object del bot.
        
        Args:
            user_id: ID del usuario
            guild_id: ID del servidor
        
        Returns:
            discord.Member o None si no se encuentra
        """
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return None
            
            member = guild.get_member(user_id)
            return member
        
        except Exception as e:
            logger.error(f'Error obteniendo member {user_id}: {e}')
            return None
    
    async def _cleanup_orphaned_sessions_in_stats(self) -> int:
        """
        Limpia sesiones huérfanas en stats.json (sin active_sessions en memoria).
        
        Sesiones huérfanas son aquellas que:
        1. Tienen current_session != null en stats.json
        2. NO existen en active_sessions (memoria)
        3. Tienen >12h de antigüedad
        
        Esto pasa cuando:
        - Bot reinicia y no recupera game/party sessions
        - Sesión queda colgada en disco
        
        Returns:
            Número de sesiones limpiadas
        """
        cleaned = 0
        now = datetime.now()
        max_age_hours = 12
        
        try:
            # Limpiar game sessions huérfanas
            for user_id, user_data in stats.get('users', {}).items():
                for game_name, game_data in user_data.get('games', {}).items():
                    current_session = game_data.get('current_session')
                    
                    if not current_session:
                        continue
                    
                    # Verificar si está en memoria
                    if user_id in self.game_manager.active_sessions:
                        continue  # Está activa en memoria, OK
                    
                    # Calcular antigüedad
                    try:
                        start_time = datetime.fromisoformat(current_session['start'])
                        age_hours = (now - start_time).total_seconds() / 3600
                        
                        if age_hours > max_age_hours:
                            # Sesión huérfana antigua, limpiar
                            game_data['current_session'] = None
                            username = user_data.get('username', 'Unknown')
                            logger.warning(f'🧹 Sesión colgada limpiada: {username} - {game_name} ({age_hours:.1f}h)')
                            cleaned += 1
                    except Exception as e:
                        logger.error(f'Error procesando current_session de {game_name}: {e}')
            
            # Limpiar party sessions huérfanas
            parties_to_remove = []
            for game_name, party_data in stats.get('parties', {}).get('active', {}).items():
                # Verificar si está en memoria
                if game_name in self.party_manager.active_sessions:
                    continue  # Está activa en memoria, OK
                
                # Calcular antigüedad
                try:
                    start_time = datetime.fromisoformat(party_data['start'])
                    age_hours = (now - start_time).total_seconds() / 3600
                    
                    if age_hours > max_age_hours:
                        # Party huérfana antigua, marcar para eliminar
                        parties_to_remove.append(game_name)
                        logger.warning(f'🧹 Party colgada limpiada: {game_name} ({age_hours:.1f}h)')
                        cleaned += 1
                except Exception as e:
                    logger.error(f'Error procesando party activa de {game_name}: {e}')
            
            # Eliminar parties marcadas
            for game_name in parties_to_remove:
                del stats['parties']['active'][game_name]
            
            # Guardar cambios si hubo limpieza
            if cleaned > 0:
                save_stats()
        
        except Exception as e:
            logger.error(f'Error en limpieza de sesiones huérfanas: {e}', exc_info=True)
        
        return cleaned
    
    def start(self):
        """Inicia el health check periódico"""
        if not self.periodic_check.is_running():
            self.periodic_check.start()
            logger.info('🏥 Health check periódico iniciado (cada 30 min)')
    
    def stop(self):
        """Detiene el health check periódico"""
        if self.periodic_check.is_running():
            self.periodic_check.cancel()
            logger.info('🏥 Health check periódico detenido')
