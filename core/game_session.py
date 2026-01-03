"""
Sistema de gestión de sesiones de juegos
Maneja tracking, notificaciones y verificación de duración mínima
Incluye supresión de notificaciones cuando hay party activa
"""

import asyncio
import logging
from typing import Optional, Dict, TYPE_CHECKING
from datetime import datetime
import discord

from core.base_session import BaseSession, BaseSessionManager
from core.session_dto import (
    save_game_time, increment_game_count,
    set_game_session_start, clear_game_session
)
from core.cooldown import check_cooldown, is_cooldown_passed
from core.helpers import send_notification, get_activity_verb

if TYPE_CHECKING:
    from core.party_session import PartySessionManager

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
    
    def __init__(self, bot, party_manager: Optional['PartySessionManager'] = None):
        super().__init__(bot, min_duration_seconds=10)
        self.party_manager = party_manager
    
    def set_party_manager(self, party_manager: 'PartySessionManager'):
        """Establece referencia al PartySessionManager (llamado después de inicialización)"""
        self.party_manager = party_manager
    
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
        
        # Si ya hay una sesión activa para este juego, actualizar actividad
        if user_id in self.active_sessions and self.active_sessions[user_id].game_name == game_name:
            self._update_activity(self.active_sessions[user_id])
            return
        
        # Si ya hay una sesión activa para OTRO juego, cancelarla primero
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
        
        logger.debug(f'🔍 handle_game_end llamado: {member.display_name} - {game_name}')
        
        if user_id not in self.active_sessions:
            # Si no hay sesión en manager, limpiar tracking directamente (ej. bot reinició)
            logger.debug(f'⚠️  No hay sesión activa para {member.display_name} - {game_name}')
            clear_game_session(user_id, game_name)
            return
        
        session = self.active_sessions[user_id]
        
        # Verificar que es el juego correcto
        if not isinstance(session, GameSession) or session.game_name != game_name:
            logger.debug(f'⚠️  Sesión de {member.display_name} no coincide con juego terminado (esperado: {session.game_name}, recibido: {game_name})')
            return
        
        # Log de estado de sesión antes de procesarla
        time_since_start = (datetime.now() - session.start_time).total_seconds()
        time_since_activity = (datetime.now() - session.last_activity_update).total_seconds()
        logger.debug(f'📊 Estado sesión: {member.display_name} - {game_name} | Inicio: {int(time_since_start)}s atrás | Última actividad: {int(time_since_activity)}s atrás | Confirmada: {session.is_confirmed}')
        
        # Buffer de gracia: Verificar si Discord dejó de reportar hace poco
        if self._is_in_grace_period(session):
            logger.info(f'⏳ Sesión de juego en gracia: {member.display_name} - {game_name} (última actividad hace {int((datetime.now() - session.last_activity_update).total_seconds())}s)')
            
            # IMPORTANTE: Si la sesión lleva MÁS de 5 minutos en gracia y NO se confirmó,
            # finalizarla silenciosamente (Discord dejó de enviar eventos)
            time_in_grace = (datetime.now() - session.last_activity_update).total_seconds()
            if time_in_grace > 300 and not session.is_confirmed:  # 5 minutos
                logger.warning(f'⚠️  Sesión en gracia demasiado tiempo ({int(time_in_grace)}s): Finalizando {member.display_name} - {game_name}')
                # NO retornar, continuar con finalización
            else:
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
            logger.info(f'⏭️  Sesión NO válida para guardar: {member.display_name} - {game_name} ({duration_seconds:.1f}s) - Confirmada: {session.is_confirmed}')
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
            
            # Notificar salida SOLO si:
            # 1. La sesión fue CONFIRMADA (pasó los 10s completos)
            # 2. Está habilitado en config
            # 3. Si hubo notificación de entrada: verificar cooldown de salida normalmente
            # 4. Si NO hubo notificación de entrada: solo notificar si el cooldown de entrada ya pasó (10 min)
            if config.get('notify_game_end', False) and session_is_confirmed:
                # Si hubo notificación de entrada, verificar cooldown de salida normalmente
                if session.entry_notification_sent:
                    if check_cooldown(user_id, f'game_end:{game_name}', cooldown_seconds=300):
                        messages_config = config.get('messages', {})
                        message_template = messages_config.get('game_end', "🎮 **{user}** dejó de jugar **{game}**")
                        message = message_template.format(
                            user=member.display_name,
                            game=game_name
                        )
                        await send_notification(message, self.bot)
                        logger.info(f'🎮 Notificación de salida enviada: {member.display_name} dejó {game_name}')
                    else:
                        logger.debug(f'⏭️  Notificación de salida no enviada: {member.display_name} - {game_name} (cooldown activo)')
                else:
                    # No hubo notificación de entrada: solo notificar si el cooldown de entrada ya pasó (30 minutos)
                    cooldown_key = f'game:{game_name}'
                    entry_cooldown_passed = is_cooldown_passed(user_id, cooldown_key, cooldown_seconds=1800)
                    if entry_cooldown_passed:
                        if check_cooldown(user_id, f'game_end:{game_name}', cooldown_seconds=300):
                            messages_config = config.get('messages', {})
                            message_template = messages_config.get('game_end', "🎮 **{user}** dejó de jugar **{game}**")
                            message = message_template.format(
                                user=member.display_name,
                                game=game_name
                            )
                            await send_notification(message, self.bot)
                            logger.info(f'🎮 Notificación de salida enviada: {member.display_name} dejó {game_name} (sin entrada previa, cooldown de entrada pasó)')
                        else:
                            logger.debug(f'⏭️  Notificación de salida no enviada: {member.display_name} - {game_name} (cooldown de salida activo)')
                    else:
                        logger.debug(f'⏭️  Notificación de salida no enviada: {member.display_name} - {game_name} (no hubo entrada y cooldown de entrada aún activo)')
            else:
                if not config.get('notify_game_end', False):
                    logger.debug(f'⏭️  Notificación de salida no enviada: {member.display_name} - {game_name} (notify_game_end deshabilitado)')
                elif not session_is_confirmed:
                    logger.debug(f'⏭️  Notificación de salida no enviada: {member.display_name} - {game_name} (sesión no confirmada)')
        
        # Limpiar sesión
        clear_game_session(user_id, game_name)
        
        # Eliminar sesión activa (verificación defensiva para evitar KeyError)
        if user_id in self.active_sessions:
            del self.active_sessions[user_id]
            logger.debug(f'🗑️  Sesión de juego finalizada y limpiada para {member.display_name}')
        else:
            logger.debug(f'⚠️  Sesión ya fue eliminada (probablemente por _cancel_session): {member.display_name}')
    
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
                is_active = current_type == session.activity_type
                
                # Si está activo, actualizar timestamp de actividad
                if is_active:
                    self._update_activity(session)
                
                return is_active
        
        return False
    
    async def _on_session_confirmed_phase1(self, session: BaseSession, member: discord.Member, config: dict):
        """Callback cuando la sesión es confirmada después de 3s"""
        if not isinstance(session, GameSession):
            return
        
        # Iniciar tracking de sesión
        set_game_session_start(session.user_id, session.username, session.game_name)
        
        # 🎮 Verificar si hay party activa para este juego
        if self.party_manager and self.party_manager.has_active_party(session.game_name):
            logger.debug(f'⏭️  Notificación de game suprimida: {session.username} - {session.game_name} (party activa)')
            session.entry_notification_sent = False  # No notificar, pero sí trackear tiempo
            return
        
        # Notificar entrada con cooldown (30 minutos por juego)
        if config.get('notify_games', True):
            cooldown_key = f'game:{session.game_name}'
            if check_cooldown(session.user_id, cooldown_key, cooldown_seconds=1800):
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
                session.entry_notification_sent = True  # Marcar que se envió notificación de entrada
                logger.info(f'🎮 Notificación enviada: {session.username} está {verb} {session.game_name}')
            else:
                logger.debug(f'⏭️  Notificación de entrada no enviada: {session.username} - {session.game_name} (cooldown activo)')
                session.entry_notification_sent = False  # No se envió por cooldown
        else:
            logger.debug(f'⏭️  Notificación de entrada deshabilitada en config')
            session.entry_notification_sent = False  # No se envió porque está deshabilitado
    
    async def _on_session_confirmed_phase2(self, session: BaseSession, member: discord.Member, config: dict):
        """Callback cuando la sesión es confirmada después de 10s"""
        # No hay acción adicional necesaria en fase 2 para juegos
        pass

