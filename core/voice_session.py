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
from core.cooldown import check_cooldown
from core.helpers import send_notification

logger = logging.getLogger('dsbot')


class VoiceSession(BaseSession):
    """Representa una sesión de voz activa"""
    
    def __init__(self, user_id: str, username: str, channel_id: int, channel_name: str, guild_id: int):
        super().__init__(user_id, username, guild_id)
        self.channel_id = channel_id
        self.channel_name = channel_name


class VoiceSessionManager(BaseSessionManager):
    """Gestiona todas las sesiones de voz activas"""
    
    def __init__(self, bot):
        super().__init__(bot, min_duration_seconds=10)
    
    async def handle_start(self, member: discord.Member, channel: discord.VoiceChannel, config: dict):
        """
        Maneja la entrada de un usuario a un canal de voz
        
        Args:
            member: Miembro que entró
            channel: Canal de voz
            config: Configuración del bot
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
            guild_id=member.guild.id
        )
        
        self.active_sessions[user_id] = session
        
        # Iniciar task de verificación en background (no bloquea)
        session.verification_task = asyncio.create_task(
            self._verify_session(session, member, config)
        )
    
    async def handle_end(self, member: discord.Member, channel: discord.VoiceChannel, config: dict):
        """
        Maneja la salida de un usuario de un canal de voz
        
        Args:
            member: Miembro que salió
            channel: Canal de voz (el que dejó)
            config: Configuración del bot
        """
        user_id = str(member.id)
        
        if user_id not in self.active_sessions:
            # Si no hay sesión en manager, finalizar tracking directamente (ej. bot reinició)
            clear_voice_session(user_id)
            return
        
        session = self.active_sessions[user_id]
        
        # Verificar que es el canal correcto
        if session.channel_id != channel.id:
            logger.debug(f'⚠️  Sesión de {member.display_name} no coincide con canal de salida')
            return
        
        # Cancelar task de verificación si aún está corriendo
        if session.verification_task and not session.verification_task.done():
            session.verification_task.cancel()
        
        # Calcular tiempo de sesión
        duration_seconds = session.duration_seconds()
        minutes = int(duration_seconds / 60)
        
        # Verificar si la sesión fue válida:
        # - Debe haber durado al menos min_duration_seconds (10s)
        # - O debe estar confirmada (pasó la verificación completa)
        session_is_valid = duration_seconds >= self.min_duration_seconds or session.is_confirmed
        
        # Si la sesión NO fue válida, borrar notificación y no guardar/notificar
        if not session_is_valid:
            if session.notification_message:
                try:
                    await session.notification_message.delete()
                    logger.info(f'🗑️  Notificación borrada: {member.display_name} estuvo < {self.min_duration_seconds}s o no fue confirmada')
                except discord.errors.NotFound:
                    logger.debug(f'⚠️  Mensaje ya fue borrado: {member.display_name}')
                except Exception as e:
                    logger.error(f'Error borrando notificación: {e}')
            # No guardar tiempo ni notificar salida si la sesión no fue válida
        else:
            # Sesión válida (confirmada y > 10s): guardar tiempo y notificar salida si está habilitado
            if minutes >= 1:  # Solo guardar si duró más de 1 minuto
                save_voice_time(user_id, member.display_name, minutes, session.channel_name)
            
            # Notificar salida con cooldown (solo si la sesión fue confirmada)
            if config.get('notify_voice_leave', False):
                if check_cooldown(user_id, 'voice_leave', cooldown_seconds=300):
                    messages_config = config.get('messages', {})
                    message_template = messages_config.get('voice_leave', "🔇 **{user}** salió del canal de voz **{channel}**")
                    message = message_template.format(
                        user=member.display_name,
                        channel=channel.name
                    )
                    await send_notification(message, self.bot)
                    logger.info(f'🔇 Notificación de salida enviada: {member.display_name} de {channel.name}')
        
        # Limpiar sesión
        clear_voice_session(user_id)
        del self.active_sessions[user_id]
        logger.debug(f'🗑️  Sesión de voz finalizada y limpiada para {member.display_name}')
    
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
        
        # Tratar como salida del canal anterior
        await self.handle_end(member, before, config)
        
        # Tratar como entrada al canal nuevo
        await self.handle_start(member, after, config)
        
        # Notificar cambio de canal con cooldown
        if config.get('notify_voice_move', True):
            if check_cooldown(user_id, 'voice_move', cooldown_seconds=300):
                messages_config = config.get('messages', {})
                message_template = messages_config.get('voice_move', "🔄 **{user}** cambió de **{old_channel}** a **{new_channel}**")
                message = message_template.format(
                    user=member.display_name,
                    old_channel=before.name,
                    new_channel=after.name
                )
                await send_notification(message, self.bot)
                logger.info(f'🔄 Notificación de cambio de canal enviada: {member.display_name} de {before.name} a {after.name}')
    
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
        
        return member_now.voice.channel.id == session.channel_id
    
    async def _on_session_confirmed_phase1(self, session: BaseSession, member: discord.Member, config: dict):
        """Callback cuando la sesión es confirmada después de 3s"""
        if not isinstance(session, VoiceSession):
            return
        
        # Iniciar tracking de sesión
        set_voice_session_start(session.user_id, session.username, session.channel_name)
        
        # Notificar entrada con cooldown
        if config.get('notify_voice', True):
            if check_cooldown(session.user_id, 'voice'):
                increment_voice_count(session.user_id, session.username)
                
                messages_config = config.get('messages', {})
                message_template = messages_config.get('voice_join', "🔊 **{user}** entró al canal de voz **{channel}**")
                message = message_template.format(
                    user=session.username,
                    channel=session.channel_name
                )
                session.notification_message = await send_notification(message, self.bot, return_message=True)
                logger.info(f'🔊 Notificación enviada: {session.username} en {session.channel_name}')
    
    async def _on_session_confirmed_phase2(self, session: BaseSession, member: discord.Member, config: dict):
        """Callback cuando la sesión es confirmada después de 10s"""
        # No hay acción adicional necesaria en fase 2 para voz
        pass
    
    # Métodos de compatibilidad (mantener por si acaso)
    
    async def handle_voice_join(self, member: discord.Member, channel: discord.VoiceChannel, config: dict):
        """Alias para handle_start (compatibilidad)"""
        await self.handle_start(member, channel, config)
    
    async def handle_voice_leave(self, member: discord.Member, channel: discord.VoiceChannel, config: dict):
        """Alias para handle_end (compatibilidad)"""
        await self.handle_end(member, channel, config)
