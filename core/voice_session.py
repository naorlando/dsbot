"""
Sistema de gestión de sesiones de voz
Maneja tracking, notificaciones y verificación de duración mínima
"""

import asyncio
import logging
from typing import Dict
import discord

from core.base_session import BaseSession, BaseSessionManager
from core.session_dto import (
    save_voice_time, increment_voice_count,
    set_voice_session_start, clear_voice_session
)
from core.cooldown import check_cooldown, is_cooldown_passed
from core.helpers import send_notification
from core.pending_notifications import save_voice_notification, remove_voice_notification

logger = logging.getLogger('dsbot')


class VoiceSession(BaseSession):
    """Representa una sesión de voz activa"""
    
    def __init__(
        self,
        user_id: str,
        username: str,
        channel_id: int,
        channel_name: str,
        guild_id: int,
        voice_continuation: bool = False,
    ):
        super().__init__(user_id, username, guild_id)
        self.channel_id = channel_id
        self.channel_name = channel_name
        # True si el usuario viene de otro canal de voz (misma presencia continua)
        self.voice_continuation = voice_continuation
        if voice_continuation:
            # Ya estuvo en voz confirmado antes: habilita notify de salida aunque el join
            # al nuevo canal quede silenciado por cooldown (anti-spam del move).
            self.entry_notification_sent = True


class VoiceSessionManager(BaseSessionManager):
    """Gestiona todas las sesiones de voz activas"""
    
    def __init__(self, bot):
        super().__init__(bot, min_duration_seconds=10)
    
    async def handle_start(
        self,
        member: discord.Member,
        channel: discord.VoiceChannel,
        config: dict,
        *,
        continuation_from_voice_move: bool = False,
    ):
        """
        Maneja la entrada de un usuario a un canal de voz
        
        Args:
            member: Miembro que entró
            channel: Canal de voz
            config: Configuración del bot
            continuation_from_voice_move: True si viene de handle_voice_move tras sesión ya confirmada
        """
        user_id = str(member.id)
        
        # Si ya hay una sesión activa, cancelarla primero (cambio de canal)
        if user_id in self.active_sessions:
            await self._cancel_session(user_id, reason="cambio de canal")
        
        # Crear nueva sesión
        session = VoiceSession(
            user_id=user_id,
            username=member.display_name,
            channel_id=channel.id,
            channel_name=channel.name,
            guild_id=member.guild.id,
            voice_continuation=continuation_from_voice_move,
        )
        
        self.active_sessions[user_id] = session
        
        # Iniciar task de verificación en background (no bloquea)
        session.verification_task = asyncio.create_task(
            self._verify_session(session, member, config)
        )
    
    async def handle_end(
        self,
        member: discord.Member,
        channel: discord.VoiceChannel,
        config: dict,
        *,
        skip_grace: bool = False,
    ):
        """
        Maneja la salida de un usuario de un canal de voz
        
        Args:
            member: Miembro que salió
            channel: Canal de voz (el que dejó)
            config: Configuración del bot
            skip_grace: True cuando el usuario dejó el voice por completo (no es move).
                Evita dejar sesión huérfana si la gracia retrasa el cierre.
        """
        user_id = str(member.id)
        
        if user_id not in self.active_sessions:
            # Si no hay sesión en manager, finalizar tracking directamente (ej. bot reinició)
            clear_voice_session(user_id)
            return
        
        session = self.active_sessions[user_id]
        
        # Desincronización canal (reconexiones / estados raros): limpiar sin dejar huérfano
        if session.channel_id != channel.id:
            logger.warning(
                f'⚠️  Sesión/canal desincronizado ({session.channel_id} vs {channel.id}) '
                f'— forzando cierre para {member.display_name}'
            )
            await self._force_cleanup_mismatched_session(user_id, session, member, channel, config)
            return
        
        # Gracia solo para flickers; al cortar voice del todo, finalizar siempre
        if not skip_grace and self._is_in_grace_period(session):
            logger.info(f'⏳ Sesión de voz en gracia: {member.display_name} - {channel.name}')
            return
        
        # Cancelar task de verificación si aún está corriendo
        # Esto hará que la task lance CancelledError y se limpie automáticamente
        if session.verification_task and not session.verification_task.done():
            session.verification_task.cancel()
            # Esperar un poco para que la task procese la cancelación y borre el mensaje si existe
            # (solo si la sesión es corta, para evitar esperas innecesarias)
            if session.duration_seconds() < self.min_duration_seconds:
                await asyncio.sleep(0.1)  # Pequeño delay para que la task procese la cancelación
        
        # Calcular tiempo de sesión
        duration_seconds = session.duration_seconds()
        minutes = int(duration_seconds / 60)
        
        # Verificar si la sesión fue válida para guardar tiempo:
        # - Debe haber durado al menos min_duration_seconds (10s)
        # - O debe estar confirmada (pasó la verificación completa)
        session_is_valid_for_time = duration_seconds >= self.min_duration_seconds or session.is_confirmed
        
        # Para notificación de salida: SOLO si fue confirmada (pasó los 10s completos)
        session_is_confirmed = session.is_confirmed
        
        logger.debug(f'🔊 Sesión terminada: {member.display_name} - {channel.name} - Duración: {duration_seconds:.1f}s ({minutes} min) - Confirmada: {session.is_confirmed} - Válida para tiempo: {session_is_valid_for_time}')
        
        # Si la sesión NO fue válida, verificar si aún hay mensaje que borrar
        # (la task puede haberlo borrado ya, pero por si acaso lo verificamos)
        if not session_is_valid_for_time:
            if session.notification_message:
                try:
                    await session.notification_message.delete()
                    logger.info(f'🗑️  Notificación borrada: {member.display_name} estuvo < {self.min_duration_seconds}s o no fue confirmada')
                except discord.errors.NotFound:
                    logger.debug(f'⚠️  Mensaje ya fue borrado por la task de verificación: {member.display_name}')
                except Exception as e:
                    logger.error(f'Error borrando notificación: {e}')
            # No guardar tiempo ni notificar salida si la sesión no fue válida
        else:
            # Sesión válida: guardar tiempo si duró al menos 1 minuto
            if minutes >= 1:
                save_voice_time(user_id, member.display_name, minutes, session.channel_name)
                logger.info(f'💾 Tiempo guardado: {member.display_name} estuvo en {channel.name} por {minutes} min ({duration_seconds:.1f}s)')
            else:
                logger.debug(f'⏭️  Tiempo no guardado: {member.display_name} estuvo en {channel.name} por {duration_seconds:.1f}s (< 1 minuto)')
            
            # Notificar salida SOLO si:
            # 1. La sesión fue CONFIRMADA (pasó los 10s completos)
            # 2. Está habilitado en config
            # SIMPLIFICADO: notify_voice_leave usa mismo cooldown que entrada (deshabilitado por default)
            if config.get('notify_voice_leave', False) and session_is_confirmed and session.entry_notification_sent:
                if check_cooldown(user_id, 'voice', cooldown_seconds=1800):
                    messages_config = config.get('messages', {})
                    message_template = messages_config.get('voice_leave', "🔇 **{user}** salió del canal de voz **{channel}**")
                    message = message_template.format(user=member.display_name, channel=channel.name)
                    await send_notification(message, self.bot)
                    remove_voice_notification(user_id)
                    logger.info(f'🔇 Notificación de salida enviada: {member.display_name} de {channel.name}')
        
        # Limpiar sesión
        clear_voice_session(user_id)
        
        # Eliminar sesión activa (verificación defensiva para evitar KeyError)
        if user_id in self.active_sessions:
            del self.active_sessions[user_id]
            logger.debug(f'🗑️  Sesión de voz finalizada y limpiada para {member.display_name}')
        else:
            logger.debug(f'⚠️  Sesión ya fue eliminada (probablemente por _cancel_session): {member.display_name}')
    
    async def _force_cleanup_mismatched_session(
        self,
        user_id: str,
        session: VoiceSession,
        member: discord.Member,
        channel: discord.VoiceChannel,
        config: dict,
    ):
        """Canal de sesión ≠ canal del evento: evita sesión huérfana en memoria."""
        if session.verification_task and not session.verification_task.done():
            session.verification_task.cancel()
        if session.notification_message:
            try:
                await session.notification_message.delete()
            except discord.errors.NotFound:
                pass
            except Exception as e:
                logger.error(f'Error borrando notificación (mismatch): {e}')
        duration_seconds = session.duration_seconds()
        session_is_valid = duration_seconds >= self.min_duration_seconds or session.is_confirmed
        if session_is_valid and int(duration_seconds / 60) >= 1:
            save_voice_time(user_id, member.display_name, int(duration_seconds / 60), session.channel_name)
            logger.info(f'💾 Tiempo guardado (mismatch cleanup): {member.display_name} en {session.channel_name}')
        clear_voice_session(user_id)
        remove_voice_notification(user_id)
        self.active_sessions.pop(user_id, None)
        logger.debug(f'🗑️  Sesión forzada limpiada (mismatch) para {member.display_name}')

    async def handle_voice_move(self, member: discord.Member, before: discord.VoiceChannel, after: discord.VoiceChannel, config: dict):
        """
        Maneja el cambio de canal de voz
        
        Args:
            member: Miembro que cambió
            before: Canal anterior
            after: Canal nuevo
            config: Configuración del bot
        """
        user_id = str(member.id)
        
        # Capturar si la sesión anterior estaba confirmada ANTES de finalizarla
        old_session = self.active_sessions.get(user_id)
        was_confirmed = old_session.is_confirmed if old_session else False
        
        # El move cierra el tramo anterior: no aplicar gracia porque luego se crea
        # una sesión nueva y _cancel_session no guarda tiempo acumulado.
        await self.handle_end(member, before, config, skip_grace=True)
        
        # Entrada al canal nuevo: si ya llevaba voz confirmada, marcar continuidad para que
        # el join silenciado por cooldown no deje entry_notification_sent=False y rompa el leave.
        await self.handle_start(
            member, after, config, continuation_from_voice_move=was_confirmed
        )
        
        # Cooldown propio para move: no roba el bucket 'voice' del join al canal nuevo
        if config.get('notify_voice_move', True) and was_confirmed:
            if check_cooldown(user_id, 'voice_move', cooldown_seconds=1800):
                messages_config = config.get('messages', {})
                message_template = messages_config.get('voice_move', "🔄 **{user}** cambió de **{old_channel}** a **{new_channel}**")
                message = message_template.format(user=member.display_name, old_channel=before.name, new_channel=after.name)
                await send_notification(message, self.bot)
                logger.info(f'🔄 Notificación de cambio enviada: {member.display_name} de {before.name} a {after.name}')
    
    # Métodos abstractos requeridos por BaseSessionManager
    
    async def _is_still_active(self, session: BaseSession, member: discord.Member) -> bool:
        """Verifica si la sesión de voz sigue activa"""
        if not isinstance(session, VoiceSession):
            return False
        
        guild = self.bot.get_guild(session.guild_id)
        if not guild:
            return False
        
        member_now = guild.get_member(member.id)
        if not member_now or not member_now.voice or not member_now.voice.channel:
            return False
        
        is_active = member_now.voice.channel.id == session.channel_id
        
        # Si está activo, actualizar timestamp de actividad
        if is_active:
            self._update_activity(session)
        
        return is_active
    
    async def _on_session_confirmed_phase1(self, session: BaseSession, member: discord.Member, config: dict):
        """Callback cuando la sesión es confirmada después de 3s"""
        if not isinstance(session, VoiceSession):
            return
        
        # Iniciar tracking de sesión
        set_voice_session_start(session.user_id, session.username, session.channel_name)
        
        # Notificar entrada con cooldown (20 minutos)
        if config.get('notify_voice', True):
            if check_cooldown(session.user_id, 'voice', cooldown_seconds=1200):
                if not session.voice_continuation:
                    increment_voice_count(session.user_id, session.username)
                
                messages_config = config.get('messages', {})
                message_template = messages_config.get('voice_join', "🔊 **{user}** entró al canal de voz **{channel}**")
                message = message_template.format(
                    user=session.username,
                    channel=session.channel_name
                )
                session.notification_message = await send_notification(message, self.bot, return_message=True)
                session.entry_notification_sent = True  # Marcar que se envió notificación de entrada
                
                # Guardar pending notification para recuperación en reinicio
                save_voice_notification(session.user_id, session.username, session.channel_name)
                
                logger.info(f'🔊 Notificación enviada: {session.username} en {session.channel_name}')
            else:
                logger.debug(f'⏭️  Notificación de entrada no enviada: {session.username} - {session.channel_name} (cooldown activo)')
                if not session.voice_continuation:
                    session.entry_notification_sent = False
        else:
            logger.debug(f'⏭️  Notificación de entrada no enviada: {session.username} - {session.channel_name} (notify_voice deshabilitado)')
            if not session.voice_continuation:
                session.entry_notification_sent = False
    
    async def _on_session_confirmed_phase2(self, session: BaseSession, member: discord.Member, config: dict):
        """Callback cuando la sesión es confirmada después de 10s"""
        # No hay acción adicional necesaria en fase 2 para voz
        pass
    
    # Métodos de compatibilidad (mantener por si acaso)
    
    async def handle_voice_join(self, member: discord.Member, channel: discord.VoiceChannel, config: dict):
        """Alias para handle_start (compatibilidad)"""
        await self.handle_start(member, channel, config)
    
    async def handle_voice_leave(self, member: discord.Member, channel: discord.VoiceChannel, config: dict):
        """Alias para handle_end (compatibilidad) — salida total de voz."""
        await self.handle_end(member, channel, config, skip_grace=True)
