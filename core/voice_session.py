"""
Sistema de gestión de sesiones de voz
Maneja tracking, notificaciones y verificación de duración mínima
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict
import discord

from core.persistence import stats, save_stats
from core.tracking import start_voice_session, end_voice_session, record_voice_event
from core.cooldown import check_cooldown
from core.helpers import send_notification

logger = logging.getLogger('dsbot')


class VoiceSession:
    """Representa una sesión de voz activa"""
    
    def __init__(self, user_id: str, username: str, channel_id: int, channel_name: str, guild_id: int):
        self.user_id = user_id
        self.username = username
        self.channel_id = channel_id
        self.channel_name = channel_name
        self.guild_id = guild_id
        self.start_time = datetime.now()
        self.notification_message: Optional[discord.Message] = None
        self.verification_task: Optional[asyncio.Task] = None
        self.is_confirmed = False  # True si pasó el threshold mínimo
    
    def duration_seconds(self) -> float:
        """Retorna la duración de la sesión en segundos"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def is_short(self, threshold: int = 10) -> bool:
        """Verifica si la sesión es corta (< threshold segundos)"""
        return self.duration_seconds() < threshold


class VoiceSessionManager:
    """Gestiona todas las sesiones de voz activas"""
    
    def __init__(self, bot):
        self.bot = bot
        # {user_id: VoiceSession}
        self.active_sessions: Dict[str, VoiceSession] = {}
        self.min_duration_seconds = 10  # Threshold mínimo para considerar sesión válida
    
    async def handle_voice_join(self, member: discord.Member, channel: discord.VoiceChannel, config: dict):
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
            self._verify_session(session, member, channel, config)
        )
    
    async def handle_voice_leave(self, member: discord.Member, channel: discord.VoiceChannel, config: dict):
        """
        Maneja la salida de un usuario de un canal de voz
        
        Args:
            member: Miembro que salió
            channel: Canal de voz (el que dejó)
            config: Configuración del bot
        """
        user_id = str(member.id)
        
        if user_id not in self.active_sessions:
            return
        
        session = self.active_sessions[user_id]
        
        # Verificar que es el canal correcto
        if session.channel_id != channel.id:
            logger.debug(f'⚠️  Sesión de {member.display_name} no coincide con canal de salida')
            return
        
        # Cancelar task de verificación si aún está corriendo
        if session.verification_task and not session.verification_task.done():
            session.verification_task.cancel()
        
        # Si la sesión fue corta, borrar notificación
        if session.is_short(self.min_duration_seconds):
            if session.notification_message:
                try:
                    await session.notification_message.delete()
                    logger.info(f'🗑️  Notificación borrada: {member.display_name} estuvo < {self.min_duration_seconds}s')
                except Exception as e:
                    logger.error(f'Error borrando notificación: {e}')
        else:
            # Sesión válida: notificar salida si está habilitado
            if config.get('notify_voice_leave', False):
                messages_config = config.get('messages', {})
                message_template = messages_config.get('voice_leave', "🔇 **{user}** salió del canal de voz **{channel}**")
                message = message_template.format(
                    user=member.display_name,
                    channel=channel.name
                )
                await send_notification(message, self.bot)
        
        # Finalizar tracking
        end_voice_session(user_id, member.display_name)
        
        # Limpiar sesión
        del self.active_sessions[user_id]
    
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
        await self.handle_voice_leave(member, before, config)
        
        # Tratar como entrada al canal nuevo
        await self.handle_voice_join(member, after, config)
    
    async def _verify_session(self, session: VoiceSession, member: discord.Member, channel: discord.VoiceChannel, config: dict):
        """
        Verifica la sesión en background después de un delay
        
        Fase 1 (3s): Verifica que sigue en el canal
        Fase 2 (7s): Verifica nuevamente y confirma sesión
        """
        try:
            # Fase 1: Delay inicial de 3s
            await asyncio.sleep(3)
            
            # Verificar que sigue en el canal
            guild = self.bot.get_guild(session.guild_id)
            if not guild:
                await self._cancel_session(session.user_id, reason="guild no encontrado")
                return
            
            member_now = guild.get_member(member.id)
            if not member_now or not member_now.voice or not member_now.voice.channel:
                await self._cancel_session(session.user_id, reason="salió antes de 3s")
                return
            
            if member_now.voice.channel.id != session.channel_id:
                await self._cancel_session(session.user_id, reason="cambió de canal antes de 3s")
                return
            
            # Usuario confirmado después de 3s → Iniciar tracking y notificar
            start_voice_session(session.user_id, session.username, session.channel_name)
            
            if config.get('notify_voice', True):
                if check_cooldown(session.user_id, 'voice'):
                    record_voice_event(session.user_id, session.username)
                    
                    messages_config = config.get('messages', {})
                    message_template = messages_config.get('voice_join', "🔊 **{user}** entró al canal de voz **{channel}**")
                    message = message_template.format(
                        user=session.username,
                        channel=session.channel_name
                    )
                    session.notification_message = await send_notification(message, self.bot, return_message=True)
                    logger.info(f'🔊 Notificación enviada: {session.username} en {session.channel_name}')
            
            # Fase 2: Verificación adicional de 7s (total 10s)
            await asyncio.sleep(7)
            
            # Verificar una vez más
            guild = self.bot.get_guild(session.guild_id)
            if not guild:
                return
            
            member_now = guild.get_member(member.id)
            if member_now and member_now.voice and member_now.voice.channel:
                if member_now.voice.channel.id == session.channel_id:
                    # Sesión confirmada: Usuario sigue después de 10s
                    session.is_confirmed = True
                    logger.debug(f'✅ Sesión confirmada: {session.username} > {self.min_duration_seconds}s')
                else:
                    # Cambió de canal: borrar notificación
                    if session.notification_message:
                        try:
                            await session.notification_message.delete()
                            logger.info(f'🗑️  Notificación borrada: {session.username} cambió de canal')
                        except Exception as e:
                            logger.error(f'Error borrando notificación: {e}')
            else:
                # Salió: borrar notificación
                if session.notification_message:
                    try:
                        await session.notification_message.delete()
                        logger.info(f'🗑️  Notificación borrada: {session.username} salió antes de confirmar')
                    except Exception as e:
                        logger.error(f'Error borrando notificación: {e}')
        
        except asyncio.CancelledError:
            # Task cancelada (usuario salió antes de completar verificación)
            logger.debug(f'⏭️  Verificación cancelada: {session.username}')
        except Exception as e:
            logger.error(f'Error en verificación de sesión: {e}')
    
    async def _cancel_session(self, user_id: str, reason: str = ""):
        """Cancela una sesión sin finalizar tracking"""
        if user_id not in self.active_sessions:
            return
        
        session = self.active_sessions[user_id]
        
        # Cancelar task de verificación
        if session.verification_task and not session.verification_task.done():
            session.verification_task.cancel()
        
        # Borrar notificación si existe
        if session.notification_message:
            try:
                await session.notification_message.delete()
            except Exception:
                pass
        
        logger.debug(f'⏭️  Sesión cancelada: {session.username} ({reason})')
        del self.active_sessions[user_id]

