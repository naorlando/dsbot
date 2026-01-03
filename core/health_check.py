"""
Session Recovery System + Periodic Health Check
Recuperación de sesiones de voice después de reinicio del bot
+ Validación periódica de sesiones con grace period expirado
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
        Solo para voice (games no necesita recovery).
        """
        if self._recovery_done:
            logger.debug('Recovery ya ejecutado, omitiendo')
            return
        
        try:
            logger.info('🔄 Recuperando sesiones de voice después de reinicio...')
            await self._recover_voice_sessions()
            self._recovery_done = True
            logger.info('✅ Recovery completado')
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
            else:
                logger.info('✅ No hay sesiones pendientes para restaurar')
        
        except Exception as e:
            logger.error(f'❌ Error en recuperación de voice: {e}', exc_info=True)
    
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
            party_sessions = len([s for s in self.party_manager.active_sessions.values() if s.state == 'active'])
            
            logger.info(f'🏥 Health check iniciado (games: {game_sessions}, parties: {party_sessions})')
            
            finalized = 0
            
            # Revisar game sessions
            finalized += await self._check_game_sessions()
            
            # Revisar party sessions
            finalized += await self._check_party_sessions()
            
            if finalized > 0:
                logger.info(f'✅ Health check: {finalized} sesiones finalizadas')
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
