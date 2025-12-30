"""
Session Recovery System
Recuperación de sesiones de voice después de reinicio del bot
SIMPLIFICADO: Solo recovery en on_ready, sin validación periódica
"""

import logging
from core.pending_notifications import (
    get_pending_voice_notifications,
    remove_voice_notification
)
from core.cooldown import check_cooldown

logger = logging.getLogger('dsbot')


class SessionHealthCheck:
    """
    Sistema de recuperación de sesiones después de reinicio.
    
    SIMPLIFICADO:
    - Solo se ejecuta una vez en on_ready
    - Solo recupera sesiones de voice (games no necesita)
    - No hay validación periódica (buffer de 5 min + sesiones activas es suficiente)
    """
    
    def __init__(self, bot, voice_manager):
        """
        Args:
            bot: Instancia del bot de Discord
            voice_manager: VoiceSessionManager
        """
        self.bot = bot
        self.voice_manager = voice_manager
        self._recovery_done = False
        
        logger.info('🏥 Session recovery inicializado (solo on_ready)')
    
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
