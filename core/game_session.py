"""
Sistema de gestión de sesiones de juegos
Maneja tracking, notificaciones y verificación de duración mínima
"""

import asyncio
import logging
from typing import Optional, Dict
import discord

from core.base_session import BaseSession, BaseSessionManager
from core.session_dto import (
    save_game_time, increment_game_count,
    set_game_session_start, clear_game_session
)
from core.cooldown import check_cooldown
from core.helpers import send_notification, get_activity_verb

logger = logging.getLogger('dsbot')


class GameSession(BaseSession):
    """Representa una sesión de juego activa"""
    
    def __init__(self, user_id: str, username: str, game_name: str, app_id: Optional[int], 
                 activity_type: str, guild_id: int):
        super().__init__(user_id, username, guild_id)
        self.game_name = game_name
        self.app_id = app_id
        self.activity_type = activity_type


class GameSessionManager(BaseSessionManager):
    """Gestiona todas las sesiones de juego activas"""
    
    def __init__(self, bot):
        super().__init__(bot, min_duration_seconds=10)
    
    # Métodos abstractos requeridos por BaseSessionManager
    async def handle_start(self, member: discord.Member, config: dict, *args, **kwargs):
        """
        Implementa handle_start abstracto.
        Para juegos, requiere game_activity y activity_type en kwargs.
        """
        game_activity = kwargs.get('game_activity')
        activity_type = kwargs.get('activity_type')
        if game_activity is None or activity_type is None:
            logger.error("GameSessionManager.handle_start requiere game_activity y activity_type en kwargs")
            return
        await self.handle_game_start(member, game_activity, activity_type, config)
    
    async def handle_end(self, member: discord.Member, config: dict, *args, **kwargs):
        """
        Implementa handle_end abstracto.
        Para juegos, requiere game_name en kwargs.
        """
        game_name = kwargs.get('game_name')
        if game_name is None:
            logger.error("GameSessionManager.handle_end requiere game_name en kwargs")
            return
        await self.handle_game_end(member, game_name, config)
    
    async def handle_game_start(self, member: discord.Member, game_activity: discord.Activity, 
                               activity_type: str, config: dict):
        """
        Maneja el inicio de un juego
        
        Args:
            member: Miembro que empezó a jugar
            game_activity: Actividad de Discord
            activity_type: Tipo de actividad ('playing', 'streaming', etc.)
            config: Configuración del bot
        """
        user_id = str(member.id)
        game_name = game_activity.name
        app_id = getattr(game_activity, 'application_id', None)
        
        # Si ya hay una sesión activa para este juego, cancelarla primero
        if user_id in self.active_sessions:
            existing_session = self.active_sessions[user_id]
            if isinstance(existing_session, GameSession) and existing_session.game_name == game_name:
                # Mismo juego, mantener sesión
                return
            else:
                # Diferente juego, cancelar anterior
                await self._cancel_session(user_id, reason="cambio de juego")
        
        # Crear nueva sesión
        session = GameSession(
            user_id=user_id,
            username=member.display_name,
            game_name=game_name,
            app_id=app_id,
            activity_type=activity_type,
            guild_id=member.guild.id
        )
        
        self.active_sessions[user_id] = session
        
        # Iniciar task de verificación en background (no bloquea)
        session.verification_task = asyncio.create_task(
            self._verify_session(session, member, config)
        )
    
    async def handle_game_end(self, member: discord.Member, game_name: str, config: dict):
        """
        Maneja el fin de un juego
        
        Args:
            member: Miembro que dejó de jugar
            game_name: Nombre del juego
            config: Configuración del bot
        """
        user_id = str(member.id)
        
        if user_id not in self.active_sessions:
            # Si no hay sesión en manager, limpiar tracking directamente (ej. bot reinició)
            clear_game_session(user_id, game_name)
            return
        
        session = self.active_sessions[user_id]
        
        # Verificar que es el juego correcto
        if not isinstance(session, GameSession) or session.game_name != game_name:
            logger.debug(f'⚠️  Sesión de {member.display_name} no coincide con juego terminado')
            return
        
        # Cancelar task de verificación si aún está corriendo
        if session.verification_task and not session.verification_task.done():
            session.verification_task.cancel()
        
        # Calcular tiempo de sesión
        duration_seconds = session.duration_seconds()
        minutes = int(duration_seconds / 60)
        
        # Verificar si la sesión fue válida para guardar tiempo:
        # - Debe haber durado al menos min_duration_seconds (10s)
        # - O debe estar confirmada (pasó la verificación completa)
        session_is_valid_for_time = duration_seconds >= self.min_duration_seconds or session.is_confirmed
        
        # Para notificación de salida: SOLO si fue confirmada (pasó los 10s completos)
        session_is_confirmed = session.is_confirmed
        
        logger.debug(f'🎮 Sesión terminada: {member.display_name} - {game_name} - Duración: {duration_seconds:.1f}s ({minutes} min) - Confirmada: {session.is_confirmed} - Válida para tiempo: {session_is_valid_for_time}')
        
        # Si la sesión NO fue válida, borrar notificación y no guardar/notificar
        if not session_is_valid_for_time:
            if session.notification_message:
                try:
                    await session.notification_message.delete()
                    logger.info(f'🗑️  Notificación borrada: {member.display_name} jugó < {self.min_duration_seconds}s o no fue confirmada')
                except discord.errors.NotFound:
                    logger.debug(f'⚠️  Mensaje ya fue borrado: {member.display_name}')
                except Exception as e:
                    logger.error(f'Error borrando notificación: {e}')
            # No guardar tiempo ni notificar salida si la sesión no fue válida
        else:
            # Sesión válida: guardar tiempo si duró al menos 1 minuto
            if minutes >= 1:
                save_game_time(user_id, member.display_name, game_name, minutes)
                logger.info(f'💾 Tiempo guardado: {member.display_name} jugó {game_name} por {minutes} min ({duration_seconds:.1f}s)')
            else:
                logger.debug(f'⏭️  Tiempo no guardado: {member.display_name} jugó {game_name} por {duration_seconds:.1f}s (< 1 minuto)')
            
            # Notificar salida con cooldown (SOLO si la sesión fue CONFIRMADA, no solo válida)
            if config.get('notify_game_end', False) and session_is_confirmed:
                if check_cooldown(user_id, f'game_end:{game_name}', cooldown_seconds=300):
                    messages_config = config.get('messages', {})
                    message_template = messages_config.get('game_end', "🎮 **{user}** dejó de jugar **{game}**")
                    message = message_template.format(
                        user=member.display_name,
                        game=game_name
                    )
                    await send_notification(message, self.bot)
                    logger.info(f'🎮 Notificación de salida enviada: {member.display_name} dejó {game_name}')
        
        # Limpiar sesión
        clear_game_session(user_id, game_name)
        del self.active_sessions[user_id]
        logger.debug(f'🗑️  Sesión de juego finalizada y limpiada para {member.display_name}')
    
    # Métodos abstractos requeridos por BaseSessionManager
    
    async def _is_still_active(self, session: BaseSession, member: discord.Member) -> bool:
        """Verifica si la sesión de juego sigue activa"""
        if not isinstance(session, GameSession):
            return False
        
        # Obtener el miembro actualizado del guild
        guild = self.bot.get_guild(session.guild_id)
        if not guild:
            return False
        
        member_now = guild.get_member(member.id)
        if not member_now:
            return False
        
        # Verificar que el miembro sigue teniendo esta actividad
        if not member_now.activities:
            return False
        
        # Buscar la actividad en la lista de actividades del miembro
        for activity in member_now.activities:
            if activity.name == session.game_name:
                # Verificar que el tipo coincide
                activity_type_map = {
                    discord.ActivityType.playing: 'playing',
                    discord.ActivityType.streaming: 'streaming',
                    discord.ActivityType.watching: 'watching',
                    discord.ActivityType.listening: 'listening',
                }
                current_type = activity_type_map.get(activity.type, 'playing')
                return current_type == session.activity_type
        
        return False
    
    async def _on_session_confirmed_phase1(self, session: BaseSession, member: discord.Member, config: dict):
        """Callback cuando la sesión es confirmada después de 3s"""
        if not isinstance(session, GameSession):
            return
        
        # Iniciar tracking de sesión
        set_game_session_start(session.user_id, session.username, session.game_name)
        
        # Notificar entrada con cooldown
        if config.get('notify_games', True):
            cooldown_key = f'game:{session.game_name}'
            if check_cooldown(session.user_id, cooldown_key):
                increment_game_count(session.user_id, session.username, session.game_name)
                
                messages_config = config.get('messages', {})
                message_template = messages_config.get('game_start', "🎮 **{user}** está {verb} **{activity}**")
                verb = get_activity_verb(session.activity_type)
                message = message_template.format(
                    user=session.username,
                    verb=verb,
                    activity=session.game_name
                )
                session.notification_message = await send_notification(message, self.bot, return_message=True)
                logger.info(f'🎮 Notificación enviada: {session.username} está {verb} {session.game_name}')
            else:
                logger.debug(f'⏭️  Notificación de entrada no enviada: {session.username} - {session.game_name} (cooldown activo)')
        else:
            logger.debug(f'⏭️  Notificación de entrada deshabilitada en config')
    
    async def _on_session_confirmed_phase2(self, session: BaseSession, member: discord.Member, config: dict):
        """Callback cuando la sesión es confirmada después de 10s"""
        # No hay acción adicional necesaria en fase 2 para juegos
        pass

