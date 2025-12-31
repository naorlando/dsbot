"""
Gestión de sesiones de parties (grupos de jugadores en el mismo juego)
Implementa verificación de 3s+7s y tracking automático
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
import discord

from core.base_session import BaseSession, BaseSessionManager
from core.persistence import stats, save_stats
from core.cooldown import check_cooldown
from core.helpers import send_notification

logger = logging.getLogger('dsbot')


class PartySession(BaseSession):
    """Sesión de party (grupo de jugadores en el mismo juego)"""
    
    def __init__(self, game_name: str, player_ids: Set[str], player_names: List[str], guild_id: int):
        # Usar game_name como "user_id" para aprovechar la estructura de BaseSession
        super().__init__(game_name, game_name, guild_id)
        self.game_name = game_name
        self.player_ids = player_ids.copy()
        self.player_names = player_names.copy()
        self.max_players = len(player_ids)
        self.initial_players = player_ids.copy()  # Para detectar quién se unió después
        
        # ✨ Soft Close: Estados para reactivación
        self.state = 'active'  # active, inactive, closed
        self.inactive_since = None  # Timestamp cuando pasó a inactive
        self.reactivation_window = 30 * 60  # 30 minutos por defecto (se actualiza de config)


class PartySessionManager(BaseSessionManager):
    """Gestiona sesiones de parties con verificación automática"""
    
    def __init__(self, bot):
        super().__init__(bot, min_duration_seconds=10)
        self._ensure_party_structure()
    
    def _ensure_party_structure(self):
        """Asegura que existe la estructura de parties en stats"""
        if 'parties' not in stats:
            stats['parties'] = {
                'active': {},
                'history': [],
                'stats_by_game': {}
            }
            save_stats()
    
    async def handle_start(self, game_name: str, current_players: List[Dict], guild_id: int, config: dict):
        """
        Maneja el inicio o actualización de una party (Soft Close).
        
        Puede crear nueva party o REACTIVAR una inactiva dentro de la ventana.
        
        Args:
            game_name: Nombre del juego
            current_players: Lista de jugadores [{user_id, username, activity}]
            guild_id: ID del servidor
            config: Configuración del bot
        """
        # ✨ SOFT CLOSE: Limpiar sesiones inactivas expiradas al inicio
        self._cleanup_expired_inactive_sessions()
        
        party_config = config.get('party_detection', {})
        
        # Verificar si está habilitado
        if not party_config.get('enabled', True):
            return
        
        # Verificar número mínimo de jugadores
        min_players = party_config.get('min_players', 2)
        if len(current_players) < min_players:
            # Si había una party activa, finalizarla
            if game_name in self.active_sessions:
                await self.handle_end(game_name, config)
            return
        
        # Verificar si el juego está en blacklist
        blacklist = party_config.get('blacklisted_games', [])
        if game_name in blacklist:
            # Si había una party activa, finalizarla
            if game_name in self.active_sessions:
                await self.handle_end(game_name, config)
            return
        
        current_player_ids = {p['user_id'] for p in current_players}
        current_player_names = [p['username'] for p in current_players]
        
        # Caso 1: No hay sesión → crear nueva party
        if game_name not in self.active_sessions:
            session = PartySession(game_name, current_player_ids, current_player_names, guild_id)
            # Leer ventana de reactivación del config
            reactivation_minutes = party_config.get('reactivation_window_minutes', 30)
            session.reactivation_window = reactivation_minutes * 60
            self.active_sessions[game_name] = session
            
            # Iniciar verificación en background
            session.verification_task = asyncio.create_task(
                self._verify_session(session, None, config)
            )
            
            logger.info(f'🎮 Nueva party iniciada: {game_name} con {len(current_players)} jugadores')
            logger.debug(f'   Jugadores: {", ".join(current_player_names)}')
        
        # ✨ SOFT CLOSE: Caso 2: Sesión INACTIVA → REACTIVAR
        elif self.active_sessions[game_name].state == 'inactive':
            session = self.active_sessions[game_name]
            
            # Reactivar sesión
            session.state = 'active'
            session.inactive_since = None
            self._update_activity(session)  # Actualizar timestamp de actividad
            
            # Actualizar jugadores
            session.player_ids = current_player_ids.copy()
            session.player_names = current_player_names.copy()
            
            # Actualizar máximo si es necesario
            if len(current_player_ids) > session.max_players:
                session.max_players = len(current_player_ids)
            
            # Actualizar en stats si ya estaba confirmada
            if session.is_confirmed:
                self._update_active_party_in_stats(game_name, session)
            
            logger.info(f'🔄 Party reactivada: {game_name} con {len(current_players)} jugadores')
            # ❌ NO notificar (es la misma sesión continua)
        
        # Caso 3: Sesión ACTIVA → actualizar jugadores (lógica existente)
        else:
            session = self.active_sessions[game_name]
            
            # Actualizar lista de jugadores
            old_player_ids = session.player_ids.copy()
            session.player_ids = current_player_ids.copy()
            session.player_names = current_player_names.copy()
            
            # Actualizar máximo si es necesario
            if len(current_player_ids) > session.max_players:
                session.max_players = len(current_player_ids)
            
            # Si la sesión está confirmada, detectar nuevos jugadores
            if session.is_confirmed:
                new_players = current_player_ids - old_player_ids
                if new_players and party_config.get('notify_on_join', True):
                    # Obtener nombres de los nuevos jugadores
                    new_player_names = [p['username'] for p in current_players if p['user_id'] in new_players]
                    
                    # Verificar cooldown POR JUGADOR (no por juego)
                    cooldown_minutes = party_config.get('cooldown_minutes', 60)
                    for player_id in new_players:
                        if not check_cooldown(game_name, f'party_join_{game_name}_{player_id}', cooldown_seconds=cooldown_minutes * 60):
                            # Este jugador específico está en cooldown, removerlo de la lista
                            new_players.discard(player_id)
                            new_player_names = [p['username'] for p in current_players if p['user_id'] in new_players]
                    
                    # Notificar solo si quedan jugadores después del filtro de cooldown
                    if new_player_names:
                        message = self._create_player_joined_message(game_name, new_player_names, current_player_names, party_config)
                        if message:
                            await send_notification(message, self.bot)
                            logger.info(f'🎮 Notificación de jugador unido a party: {game_name}')
                
                # Actualizar en stats si está confirmada
                self._update_active_party_in_stats(game_name, session)
            
            logger.debug(f'🎮 Party actualizada: {game_name} con {len(current_players)} jugadores')
    
    async def handle_end(self, game_name: str, config: dict):
        """
        Maneja el fin de una party (Soft Close).
        
        En vez de cerrar inmediatamente, marca como 'inactive' con ventana de reactivación.
        Solo cierra definitivamente cuando la ventana expira.
        
        Args:
            game_name: Nombre del juego
            config: Configuración del bot
        """
        if game_name not in self.active_sessions:
            return
        
        session = self.active_sessions[game_name]
        
        # Buffer de gracia: Verificar si realmente terminó o es lag de Discord
        if self._is_in_grace_period(session):
            logger.info(f'⏳ Party en gracia: {game_name}')
            return
        
        # ✨ SOFT CLOSE: Marcar como inactive en vez de cerrar inmediatamente
        if session.state == 'active':
            session.state = 'inactive'
            session.inactive_since = datetime.now()
            
            # Leer ventana de reactivación del config
            party_config = config.get('party_detection', {})
            reactivation_minutes = party_config.get('reactivation_window_minutes', 30)
            session.reactivation_window = reactivation_minutes * 60
            
            logger.info(f'⏸️  Party inactiva: {game_name} (ventana: {reactivation_minutes} min)')
            return  # ❌ NO finalizar todavía, puede reactivarse
        
        # ✨ SOFT CLOSE: Si ya estaba inactive, verificar ventana de reactivación
        if session.state == 'inactive':
            time_inactive = (datetime.now() - session.inactive_since).total_seconds()
            if time_inactive < session.reactivation_window:
                logger.info(f'⏳ Party en ventana de reactivación: {game_name} ({int(time_inactive/60)} min)')
                return  # Todavía puede reactivarse
            
            # Ventana expirada → cerrar definitivamente
            logger.info(f'⌛ Ventana expirada: {game_name}, cerrando definitivamente')
        
        # ✅ CERRAR DEFINITIVAMENTE (lógica existente)
        session.state = 'closed'
        
        # Cancelar tarea de verificación si existe
        if session.verification_task and not session.verification_task.done():
            session.verification_task.cancel()
            await asyncio.sleep(0.1)  # Dar tiempo a que se procese la cancelación
        
        # Borrar mensaje de notificación si existe y la sesión no fue confirmada
        if session.notification_message and not session.is_confirmed:
            try:
                await session.notification_message.delete()
                logger.info(f'🗑️  Notificación borrada: Party de {game_name} no fue confirmada')
            except discord.errors.NotFound:
                logger.debug(f'⚠️  Mensaje ya fue borrado: {game_name}')
            except Exception as e:
                logger.error(f'Error borrando notificación de party: {e}')
        
        # Si la sesión fue confirmada, finalizarla en stats
        if session.is_confirmed:
            self._finalize_party_in_stats(game_name, session)
            logger.info(f'🎮 Party finalizada: {game_name} (duración: {session.duration_seconds():.1f}s)')
        else:
            logger.debug(f'🎮 Party cancelada: {game_name} (no confirmada)')
        
        # Eliminar sesión activa (verificación defensiva para evitar KeyError)
        if game_name in self.active_sessions:
            del self.active_sessions[game_name]
        else:
            logger.debug(f'⚠️  Sesión de party ya fue eliminada: {game_name}')
    
    def _cleanup_expired_inactive_sessions(self):
        """
        Limpia sesiones inactivas cuya ventana de reactivación expiró.
        Se llama al inicio de handle_start para mantener memoria limpia.
        """
        to_remove = []
        for game_name, session in self.active_sessions.items():
            if session.state == 'inactive' and session.inactive_since:
                time_inactive = (datetime.now() - session.inactive_since).total_seconds()
                if time_inactive >= session.reactivation_window:
                    to_remove.append(game_name)
        
        for game_name in to_remove:
            session = self.active_sessions[game_name]
            logger.info(f'🧹 Limpiando party inactiva expirada: {game_name}')
            
            # Finalizar si estaba confirmada
            if session.is_confirmed:
                self._finalize_party_in_stats(game_name, session)
            
            # Eliminar de memoria
            del self.active_sessions[game_name]
    
    # Métodos abstractos requeridos por BaseSessionManager
    
    async def _is_still_active(self, session: PartySession, member: discord.Member) -> bool:
        """
        Verifica si la party sigue activa.
        
        Nota: member es None para parties, usamos guild_id de la sesión
        """
        # Buscar el guild
        guild = self.bot.get_guild(session.guild_id)
        if not guild:
            return False
        
        # Contar jugadores actuales en ese juego
        current_count = 0
        for mem in guild.members:
            if mem.bot:
                continue
            for activity in mem.activities:
                if activity.type in [
                    discord.ActivityType.playing,
                    discord.ActivityType.streaming,
                    discord.ActivityType.watching,
                    discord.ActivityType.listening
                ]:
                    if activity.name == session.game_name:
                        current_count += 1
                        break
        
        # Verificar si hay suficientes jugadores (mínimo 2)
        is_active = current_count >= 2
        
        # Si está activo, actualizar timestamp de actividad
        if is_active:
            self._update_activity(session)
        
        return is_active
    
    async def _on_session_confirmed_phase1(self, session: PartySession, member: discord.Member, config: dict):
        """
        Fase 1 de confirmación (después de 3s): notificar party formada.
        """
        party_config = config.get('party_detection', {})
        
        # Notificar party formada
        if party_config.get('notify_on_formed', True):
            cooldown_minutes = party_config.get('cooldown_minutes', 10)
            if check_cooldown(session.game_name, f'party_formed_{session.game_name}', cooldown_seconds=cooldown_minutes * 60):
                message = self._create_party_formed_message(session.game_name, session.player_names, party_config)
                if message:
                    try:
                        notification_msg = await send_notification(message, self.bot)
                        session.notification_message = notification_msg
                        session.entry_notification_sent = True
                        logger.info(f'🎮 Notificación de party formada enviada: {session.game_name}')
                    except Exception as e:
                        logger.error(f'Error enviando notificación de party: {e}')
            else:
                logger.debug(f'⏭️  Notificación de party no enviada: {session.game_name} (cooldown activo)')
        
        # Crear registro en stats
        self._create_active_party_in_stats(session.game_name, session)
    
    async def _on_session_confirmed_phase2(self, session: PartySession, member: discord.Member, config: dict):
        """
        Fase 2 de confirmación (después de 10s): marcar como confirmada.
        """
        session.is_confirmed = True
        logger.info(f'✅ Party confirmada después de 10s: {session.game_name}')
    
    # Métodos auxiliares para mensajes
    
    def _create_party_formed_message(self, game_name: str, player_names: List[str], party_config: dict) -> Optional[str]:
        """Crea mensaje de party formada"""
        template = party_config.get('message_template_formed', 
                                   '🎮 **Party formada en {game}!** Jugadores: {players}')
        
        mention = '@here' if party_config.get('use_here_mention', True) else ''
        players_str = ', '.join([f'**{name}**' for name in player_names])
        
        message = template.format(game=game_name, players=players_str)
        if mention:
            message = f'{mention} {message}'
        
        return message
    
    def _create_player_joined_message(self, game_name: str, new_player_names: List[str], 
                                     all_player_names: List[str], party_config: dict) -> Optional[str]:
        """Crea mensaje de jugador unido a party"""
        template = party_config.get('message_template_join',
                                   '🎮 **{new_players}** se unió a la party de **{game}!** ({total} jugadores)')
        
        new_players_str = ', '.join([f'**{name}**' for name in new_player_names])
        
        message = template.format(
            new_players=new_players_str,
            game=game_name,
            total=len(all_player_names)
        )
        
        return message
    
    # Métodos para persistencia en stats
    
    def _create_active_party_in_stats(self, game_name: str, session: PartySession):
        """Crea una party activa en stats"""
        stats['parties']['active'][game_name] = {
            'start': session.start_time.isoformat(),
            'players': list(session.player_ids),
            'player_names': session.player_names,
            'max_players': session.max_players
        }
        save_stats()
    
    def _update_active_party_in_stats(self, game_name: str, session: PartySession):
        """Actualiza una party activa en stats"""
        if game_name in stats['parties']['active']:
            active_party = stats['parties']['active'][game_name]
            active_party['players'] = list(session.player_ids)
            active_party['player_names'] = session.player_names
            active_party['max_players'] = session.max_players
            save_stats()
    
    def _finalize_party_in_stats(self, game_name: str, session: PartySession):
        """Finaliza una party y la guarda en historial"""
        if game_name not in stats['parties']['active']:
            # Puede no estar en active si no llegó a confirmarse en fase 1
            logger.debug(f'⚠️  Party no estaba en active: {game_name}')
            return
        
        active_party = stats['parties']['active'][game_name]
        
        # Calcular duración
        end_time = datetime.now()
        start_time = datetime.fromisoformat(active_party['start'])
        duration_seconds = (end_time - start_time).total_seconds()
        duration_minutes = int(duration_seconds / 60)
        
        # Crear registro en historial
        party_record = {
            'game': game_name,
            'start': active_party.get('start', datetime.now().isoformat()),
            'end': end_time.isoformat(),
            'duration_minutes': duration_minutes,
            'players': active_party.get('players', list(session.player_ids)),
            'player_names': active_party.get('player_names', session.player_names),
            'max_players': active_party.get('max_players', session.max_players)
        }
        
        # Buscar si ya existe una entrada con el mismo start time y game
        # (para evitar duplicados cuando handle_end se llama múltiples veces)
        existing_entry = None
        for i, entry in enumerate(stats['parties']['history']):
            if entry.get('game') == game_name and entry.get('start') == party_record['start']:
                existing_entry = i
                break
        
        if existing_entry is not None:
            # Actualizar entrada existente
            old_duration = stats['parties']['history'][existing_entry]['duration_minutes']
            stats['parties']['history'][existing_entry] = party_record
            logger.debug(f'🔄 Party actualizada en historial: {game_name} ({old_duration}→{duration_minutes} min)')
        else:
            # Agregar nueva entrada al inicio
            stats['parties']['history'].insert(0, party_record)
            logger.debug(f'💾 Party guardada en historial: {game_name} ({duration_minutes} min)')
            
            # Limitar historial a 1000 parties (solo si agregamos nueva)
            if len(stats['parties']['history']) > 1000:
                stats['parties']['history'] = stats['parties']['history'][:1000]
        
        # Actualizar estadísticas por juego (solo si es nueva o si la duración cambió significativamente)
        if existing_entry is None:
            self._update_game_stats(game_name, party_record)
        
        # Eliminar de parties activas
        del stats['parties']['active'][game_name]
        
        save_stats()
    
    def _update_game_stats(self, game_name: str, party_record: Dict):
        """Actualiza estadísticas de un juego"""
        if game_name not in stats['parties']['stats_by_game']:
            stats['parties']['stats_by_game'][game_name] = {
                'total_parties': 0,
                'total_duration_minutes': 0,
                'max_players_ever': 0,
                'total_unique_players': set()
            }
        
        game_stats = stats['parties']['stats_by_game'][game_name]
        game_stats['total_parties'] = game_stats.get('total_parties', 0) + 1
        game_stats['total_duration_minutes'] = game_stats.get('total_duration_minutes', 0) + party_record['duration_minutes']
        game_stats['max_players_ever'] = max(game_stats.get('max_players_ever', 0), party_record['max_players'])
        
        # Agregar jugadores únicos (convertir a set si no lo es)
        current_unique = game_stats.get('total_unique_players', [])
        if not isinstance(current_unique, set):
            current_unique = set(current_unique) if current_unique else set()
        current_unique.update(party_record['players'])
        
        # Convertir set a lista para serialización JSON
        game_stats['total_unique_players'] = list(current_unique)
    
    # Métodos públicos para comandos
    
    def get_active_parties(self) -> Dict[str, Dict]:
        """Retorna todas las parties activas desde sesiones"""
        active_parties = {}
        for game_name, session in self.active_sessions.items():
            if session.is_confirmed:
                active_parties[game_name] = {
                    'start': session.start_time.isoformat(),
                    'players': list(session.player_ids),
                    'player_names': session.player_names,
                    'max_players': session.max_players
                }
        return active_parties
    
    def get_party_history(self, timeframe: str = 'all', limit: int = 50) -> List[Dict]:
        """Retorna historial de parties filtrado por timeframe"""
        from datetime import timedelta
        
        history = stats['parties'].get('history', [])
        
        if timeframe == 'all':
            return history[:limit]
        
        now = datetime.now()
        timeframe_deltas = {
            'today': timedelta(days=1),
            'week': timedelta(days=7),
            'month': timedelta(days=30)
        }
        
        delta = timeframe_deltas.get(timeframe, timedelta(days=365))
        cutoff = now - delta
        
        filtered = []
        for party in history:
            try:
                party_time = datetime.fromisoformat(party['start'])
                if party_time >= cutoff:
                    filtered.append(party)
                    if len(filtered) >= limit:
                        break
            except (ValueError, KeyError):
                continue
        
        return filtered
    
    def get_game_stats(self, game_name: Optional[str] = None) -> Dict:
        """Retorna estadísticas de parties por juego"""
        all_stats = stats['parties'].get('stats_by_game', {})
        
        if game_name:
            return all_stats.get(game_name, {
                'total_parties': 0,
                'total_duration_minutes': 0,
                'max_players_ever': 0,
                'total_unique_players': []
            })
        
        return all_stats
    
    def get_active_players_by_game(self, guild) -> Dict[str, List[Dict]]:
        """
        Obtiene jugadores activos agrupados por juego.
        
        Returns:
            Dict con formato: {game_name: [{user_id, username, activity}, ...]}
        """
        from collections import defaultdict
        
        players_by_game = defaultdict(list)
        
        for member in guild.members:
            if member.bot:
                continue
            
            # Obtener actividades de juego
            for activity in member.activities:
                if activity.type in [
                    discord.ActivityType.playing,
                    discord.ActivityType.streaming,
                    discord.ActivityType.watching,
                    discord.ActivityType.listening
                ]:
                    game_name = activity.name
                    players_by_game[game_name].append({
                        'user_id': str(member.id),
                        'username': member.display_name,
                        'activity': activity
                    })
                    break  # Solo la primera actividad válida
        
        return dict(players_by_game)

