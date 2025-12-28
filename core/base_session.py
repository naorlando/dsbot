"""
Template genérico para gestión de sesiones
Proporciona clases base para VoiceSession y GameSession
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict
import discord

logger = logging.getLogger('dsbot')


class BaseSession:
    """Template para cualquier tipo de sesión"""
    
    def __init__(self, user_id: str, username: str, guild_id: int):
        self.user_id = user_id
        self.username = username
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


class BaseSessionManager(ABC):
    """Template para gestionar sesiones de cualquier tipo"""
    
    def __init__(self, bot, min_duration_seconds: int = 10):
        self.bot = bot
        self.min_duration_seconds = min_duration_seconds
        self.active_sessions: Dict[str, BaseSession] = {}
    
    @abstractmethod
    async def handle_start(self, member: discord.Member, config: dict):
        """Maneja el inicio de una sesión. Debe ser implementado por subclases."""
        pass
    
    @abstractmethod
    async def handle_end(self, member: discord.Member, config: dict):
        """Maneja el fin de una sesión. Debe ser implementado por subclases."""
        pass
    
    async def _verify_session(self, session: BaseSession, member: discord.Member, config: dict):
        """
        Verifica la sesión en background después de un delay (template method)
        
        Fase 1 (3s): Verifica que sigue activo
        Fase 2 (7s): Verifica nuevamente y confirma sesión
        """
        try:
            # Fase 1: Delay inicial de 3s
            await asyncio.sleep(3)
            
            # Verificar que sigue activo (método abstracto)
            if not await self._is_still_active(session, member):
                await self._cancel_session(session.user_id, reason="salió antes de 3s")
                return
            
            # Usuario confirmado después de 3s → Iniciar tracking y notificar
            await self._on_session_confirmed_phase1(session, member, config)
            
            # Fase 2: Verificación adicional de 7s (total 10s)
            await asyncio.sleep(7)
            
            # Verificar una vez más
            if not await self._is_still_active(session, member):
                # Se fue entre 3s y 10s: Borrar notificación
                if session.notification_message:
                    try:
                        await session.notification_message.delete()
                        logger.info(f'🗑️  Notificación borrada: {session.username} estuvo < {self.min_duration_seconds}s')
                    except discord.errors.NotFound:
                        logger.debug(f'⚠️  Mensaje ya fue borrado: {session.username}')
                    except Exception as e:
                        logger.error(f'❌ Error borrando notificación: {e}')
                await self._cancel_session(session.user_id, reason="salió entre 3s y 10s")
                return
            
            # Sesión confirmada: Usuario sigue después de 10s
            session.is_confirmed = True
            await self._on_session_confirmed_phase2(session, member, config)
            logger.debug(f'✅ Sesión confirmada: {session.username} > {self.min_duration_seconds}s')
        
        except asyncio.CancelledError:
            logger.debug(f'Task de verificación cancelada para {session.username}')
            if session.notification_message:
                try:
                    await session.notification_message.delete()
                    logger.info(f'🗑️  Notificación borrada por cancelación: {session.username}')
                except discord.errors.NotFound:
                    logger.debug(f'⚠️  Mensaje ya fue borrado por cancelación: {session.username}')
                except Exception as e:
                    logger.error(f'❌ Error borrando notificación por cancelación: {e}')
        except Exception as e:
            logger.error(f'❌ Error en _verify_session para {session.username}: {e}')
        finally:
            # Asegurarse de que la sesión se limpie si la task termina por cualquier razón
            if session.user_id in self.active_sessions and self.active_sessions[session.user_id] == session:
                if not session.is_confirmed:
                    del self.active_sessions[session.user_id]
                    logger.debug(f'🗑️  Sesión limpiada (no confirmada) para {session.username}')
    
    @abstractmethod
    async def _is_still_active(self, session: BaseSession, member: discord.Member) -> bool:
        """Verifica si la sesión sigue activa. Debe ser implementado por subclases."""
        pass
    
    @abstractmethod
    async def _on_session_confirmed_phase1(self, session: BaseSession, member: discord.Member, config: dict):
        """Callback cuando la sesión es confirmada después de 3s. Debe ser implementado por subclases."""
        pass
    
    @abstractmethod
    async def _on_session_confirmed_phase2(self, session: BaseSession, member: discord.Member, config: dict):
        """Callback cuando la sesión es confirmada después de 10s. Debe ser implementado por subclases."""
        pass
    
    async def _cancel_session(self, user_id: str, reason: str = "desconocida"):
        """Cancela y limpia una sesión activa"""
        session = self.active_sessions.pop(user_id, None)
        if session:
            if session.verification_task and not session.verification_task.done():
                session.verification_task.cancel()
            if session.notification_message:
                try:
                    await session.notification_message.delete()
                    logger.info(f'🗑️  Notificación borrada por cancelación ({reason}): {session.username}')
                except discord.errors.NotFound:
                    logger.debug(f'⚠️  Mensaje ya fue borrado por cancelación ({reason}): {session.username}')
                except Exception as e:
                    logger.error(f'❌ Error borrando notificación por cancelación ({reason}): {e}')
            logger.debug(f'🗑️  Sesión cancelada y limpiada para {session.username} (razón: {reason})')

