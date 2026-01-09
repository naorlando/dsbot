"""
Gestión de sesiones de parties (grupos de jugadores en el mismo juego)
Implementa verificación de 3s+7s y tracking automático
Cierra party cuando quedan <2 jugadores
Tracking individual de tiempo por jugador (entrada/salida dinámica)
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
import discord

from core.base_session import BaseSession, BaseSessionManager
from core.persistence import stats, save_stats
from core.session_dto import save_game_time
from core.cooldown import check_cooldown
from core.helpers import send_notification

logger = logging.getLogger('dsbot')


@dataclass
class PlayerInParty:
    """Tracking individual de un jugador en una party"""
    user_id: str
    username: str
    joined_at: datetime
    left_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    time_saved: bool = False  # Flag para evitar guardar múltiples veces


class PartySession(BaseSession):
    """
    Sesión de party (grupo de jugadores en el mismo juego) con tracking individual.
    
    Cada jugador tiene su propio tracking de tiempo (joined_at, left_at) para manejar:
    - Jugadores que entran/salen en diferentes momentos
    - Grace period individual (vuelven dentro de 20 min)
    - Tiempo preciso por jugador
    """
    
    def __init__(self, game_name: str, player_ids: Set[str], player_names: List[str], guild_id: int):
        # Usar game_name como "user_id" para aprovechar la estructura de BaseSession
        super().__init__(game_name, game_name, guild_id)
        self.game_name = game_name
        self.player_ids = player_ids.copy()
        self.player_names = player_names.copy()
        self.max_players = len(player_ids)
        self.initial_players = player_ids.copy()  # Para detectar quién se unió después
        
        # 🆕 TRACKING INDIVIDUAL POR JUGADOR
        self.players: Dict[str, PlayerInParty] = {}
        now = datetime.now()
        for user_id, username in zip(player_ids, player_names):
            self.players[user_id] = PlayerInParty(
                user_id=user_id,
                username=username,
                joined_at=now,
                last_activity=now,
                time_saved=False
            )
        
        logger.debug(f'🎮 Party iniciada con tracking individual: {game_name} ({len(self.players)} jugadores)')
    
    def mark_player_left(self, user_id: str):
        """Marca que un jugador salió de la party (entra en grace period)"""
        if user_id in self.players:
            self.players[user_id].left_at = datetime.now()
            logger.debug(f'⏳ {self.players[user_id].username} salió de party (grace 20 min): {self.game_name}')
    
    def mark_player_rejoined(self, user_id: str):
        """Marca que un jugador volvió dentro del grace period"""
        if user_id in self.players:
            self.players[user_id].left_at = None  # Cancelar salida
            self.players[user_id].last_activity = datetime.now()
            logger.debug(f'✅ {self.players[user_id].username} volvió a party (grace cancelado): {self.game_name}')
    
    def add_player(self, user_id: str, username: str):
        """Agrega un nuevo jugador a la party en curso"""
        if user_id not in self.players:
            self.players[user_id] = PlayerInParty(
                user_id=user_id,
                username=username,
                joined_at=datetime.now(),
                last_activity=datetime.now(),
                time_saved=False
            )
            logger.debug(f'➕ {username} se unió a party: {self.game_name}')
    
    def save_player_time(self, user_id: str, game_name: str) -> bool:
        """
        Guarda el tiempo de un jugador que salió (grace expirado).
        
        Returns:
            True si se guardó el tiempo, False si no
        """
        if user_id not in self.players:
            return False
        
        player = self.players[user_id]
        
        if player.time_saved:
            return False  # Ya guardado
        
        # Calcular duración desde joined_at hasta left_at (o ahora si no salió)
        end_time = player.left_at or datetime.now()
        duration_seconds = (end_time - player.joined_at).total_seconds()
        duration_minutes = int(duration_seconds / 60)
        
        if duration_minutes >= 1:
            save_game_time(user_id, player.username, game_name, duration_minutes)
            player.time_saved = True
            logger.info(f'💾 {player.username} salió de party: {duration_minutes} min guardados ({game_name})')
            return True
        
        return False
    
    def get_active_players_count(self) -> int:
        """Retorna el número de jugadores activos (no salidos o dentro de grace)"""
        now = datetime.now()
        grace_seconds = 1200  # 20 minutos
        
        active_count = 0
        for player in self.players.values():
            if player.left_at is None:
                active_count += 1  # Activo
            else:
                # En grace period?
                time_since_left = (now - player.left_at).total_seconds()
                if time_since_left <= grace_seconds:
                    active_count += 1  # Aún en grace
        
        return active_count


class PartySessionManager(BaseSessionManager):
    """Gestiona sesiones de parties con verificación automática"""
    
    def __init__(self, bot):
        super().__init__(bot, min_duration_seconds=10)
        self._ensure_party_structure()
        self._finalize_locks = {}  # Lock por game_name para prevenir finalize múltiple
    
    def _ensure_party_structure(self):
        """Asegura que existe la estructura de parties en stats"""
        if 'parties' not in stats:
            stats['parties'] = {
                'active': {},
                'history': [],
                'stats_by_game': {}
            }
            save_stats()
    
    def check_player_grace_periods(self, game_name: str) -> int:
        """
        Verifica y guarda tiempo de jugadores que expiraron su grace period individual.
        
        Retorna el número de jugadores que salieron definitivamente.
        """
        if game_name not in self.active_sessions:
            return 0
        
        session = self.active_sessions[game_name]
        now = datetime.now()
        grace_seconds = 1200  # 20 minutos
        players_removed = 0
        
        # Revisar cada jugador
        for user_id in list(session.players.keys()):
            player = session.players[user_id]
            
            # Si el jugador salió y su grace expiró
            if player.left_at:
                time_since_left = (now - player.left_at).total_seconds()
                
                if time_since_left > grace_seconds:
                    # Grace expirado → Guardar tiempo y remover
                    session.save_player_time(user_id, game_name)
                    del session.players[user_id]
                    session.player_ids.discard(user_id)
                    players_removed += 1
                    logger.info(f'⏱️  {player.username} salió definitivamente de party (grace expirado): {game_name}')
        
        return players_removed
    
    async def handle_start(self, game_name: str, current_players: List[Dict], guild_id: int, config: dict):
        """
        Maneja el inicio o actualización de una party.
        Cierra party si quedan <2 jugadores (con grace period de 20 min).
        
        Args:
            game_name: Nombre del juego
            current_players: Lista de jugadores [{user_id, username, activity}]
            guild_id: ID del servidor
            config: Configuración del bot
        """
        party_config = config.get('party_detection', {})
        
        # Verificar si está habilitado
        if not party_config.get('enabled', True):
            return
        
        # Verificar número mínimo de jugadores
        min_players = party_config.get('min_players', 2)
        if len(current_players) < min_players:
            # Si había una party activa, cerrarla (con grace period)
            if game_name in self.active_sessions:
                await self.handle_end(game_name, config)
            return
        
        # Verificar si el juego está en blacklist
        blacklist = party_config.get('blacklisted_games', [])
        if game_name in blacklist:
            if game_name in self.active_sessions:
                await self.handle_end(game_name, config)
            return
        
        current_player_ids = {p['user_id'] for p in current_players}
        current_player_names = [p['username'] for p in current_players]
        
        # Caso 1: No hay sesión → crear nueva party
        if game_name not in self.active_sessions:
            session = PartySession(game_name, current_player_ids, current_player_names, guild_id)
            self.active_sessions[game_name] = session
            
            # Iniciar verificación en background
            session.verification_task = asyncio.create_task(
                self._verify_session(session, None, config)
            )
            
            logger.info(f'🎮 Nueva party iniciada: {game_name} con {len(current_players)} jugadores')
            logger.debug(f'   Jugadores: {", ".join(current_player_names)}')
        
        # Caso 2: Sesión ACTIVA → actualizar jugadores con tracking individual
        else:
            session = self.active_sessions[game_name]
            
            # Actualizar actividad (resetea grace period de la party)
            self._update_activity(session)
            
            # 🆕 TRACKING INDIVIDUAL: Detectar cambios de jugadores
            old_player_ids = session.player_ids.copy()
            
            # Jugadores que salieron (estaban antes pero ya no están)
            players_left = old_player_ids - current_player_ids
            for user_id in players_left:
                session.mark_player_left(user_id)
            
            # Jugadores que volvieron (estaban marcados como left pero volvieron)
            players_returned = []
            for player_id in current_player_ids:
                if player_id in session.players and session.players[player_id].left_at:
                    session.mark_player_rejoined(player_id)
                    players_returned.append(player_id)
            
            # Jugadores completamente nuevos (nunca estuvieron en la party)
            players_new = current_player_ids - set(session.players.keys())
            for p in current_players:
                if p['user_id'] in players_new:
                    session.add_player(p['user_id'], p['username'])
            
            # Actualizar listas principales
            session.player_ids = current_player_ids.copy()
            session.player_names = current_player_names.copy()
            
            # Actualizar máximo si es necesario
            if len(current_player_ids) > session.max_players:
                session.max_players = len(current_player_ids)
            
            # Si la sesión está confirmada, notificar solo jugadores NUEVOS (no returnedos)
            if session.is_confirmed:
                if players_new and party_config.get('notify_on_join', True):
                    # Obtener nombres de los nuevos jugadores
                    new_player_names = [p['username'] for p in current_players if p['user_id'] in players_new]
                    
                    # Verificar cooldown POR JUGADOR (no por juego)
                    cooldown_minutes = party_config.get('cooldown_minutes', 60)
                    for player_id in list(players_new):
                        # Cooldown por jugador individual (consistente con game sessions)
                        if not check_cooldown(player_id, f'game:{game_name}', cooldown_seconds=cooldown_minutes * 60):
                            # Este jugador específico está en cooldown, removerlo de la lista
                            players_new.discard(player_id)
                            new_player_names = [p['username'] for p in current_players if p['user_id'] in players_new]
                    
                    # Notificar solo si quedan jugadores después del filtro de cooldown
                    if new_player_names:
                        message = self._create_player_joined_message(game_name, new_player_names, current_player_names, party_config)
                        if message:
                            await send_notification(message, self.bot)
                            logger.info(f'🎮 Notificación de jugador unido a party: {game_name}')
                
                # Actualizar en stats si está confirmada
                self._update_active_party_in_stats(game_name, session)
            
            logger.debug(f'🎮 Party actualizada: {game_name} con {len(current_players)} jugadores (tracking individual activo)')
    
    async def handle_end(self, game_name: str, config: dict):
        """
        Maneja el fin de una party con lock para prevenir finalizaciones múltiples.
        Usa grace period de 20 min para reconexiones.
        
        Args:
            game_name: Nombre del juego
            config: Configuración del bot
        """
        # Adquirir lock para este game_name
        if game_name not in self._finalize_locks:
            self._finalize_locks[game_name] = asyncio.Lock()
        
        async with self._finalize_locks[game_name]:
            if game_name not in self.active_sessions:
                return  # Ya fue finalizada en otro call
            
            session = self.active_sessions[game_name]
            
            # Buffer de gracia: Verificar si realmente terminó o es lag/reconexión
            if self._is_in_grace_period(session):
                logger.debug(f'⏳ Party en gracia: {game_name}')
                return
            
            # ✅ CERRAR DEFINITIVAMENTE
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
            
            # Si la sesión fue confirmada, finalizarla en stats y guardar tiempo individual
            if session.is_confirmed:
                self._finalize_party_in_stats(game_name, session)
                logger.info(f'🎮 Party finalizada: {game_name} (duración: {session.duration_seconds():.1f}s)')
            else:
                logger.debug(f'🎮 Party cancelada: {game_name} (no confirmada)')
            
            # Eliminar sesión activa
            if game_name in self.active_sessions:
                del self.active_sessions[game_name]
            
            # Limpiar lock
            if game_name in self._finalize_locks:
                del self._finalize_locks[game_name]
    
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
        """Finaliza una party y la guarda en historial + tiempo individual"""
        
        if game_name not in stats['parties']['active']:
            # Puede no estar en active si no llegó a confirmarse en fase 1
            logger.debug(f'⚠️  Party no estaba en active: {game_name}')
            return
        
        active_party = stats['parties']['active'][game_name]
        
        # Calcular duración total de la party (para historial)
        end_time = datetime.now()
        start_time = datetime.fromisoformat(active_party['start'])
        duration_seconds = (end_time - start_time).total_seconds()
        duration_minutes = int(duration_seconds / 60)
        
        # 💾 Guardar tiempo INDIVIDUAL para cada jugador que NO fue guardado
        # (jugadores que salieron antes ya tienen su tiempo guardado)
        players_saved = 0
        for user_id in session.players:
            player = session.players[user_id]
            
            if not player.time_saved:
                # Calcular tiempo individual (desde joined_at hasta ahora)
                player_duration_seconds = (end_time - player.joined_at).total_seconds()
                player_duration_minutes = int(player_duration_seconds / 60)
                
                if player_duration_minutes >= 1:
                    save_game_time(user_id, player.username, game_name, player_duration_minutes)
                    player.time_saved = True
                    players_saved += 1
                    logger.info(f'💾 Tiempo guardado: {player.username} jugó {game_name} por {player_duration_minutes} min (individual)')
        
        logger.debug(f'💾 Party finalizada: {game_name} | {players_saved} jugadores guardaron tiempo | Duración total: {duration_minutes} min')
        
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
    
    def has_active_party(self, game_name: str, user_id: Optional[str] = None) -> bool:
        """
        Verifica si hay una party activa o formándose para un juego (opcionalmente para un usuario específico).
        
        Args:
            game_name: Nombre del juego
            user_id: ID del usuario (opcional). Si se proporciona, verifica que esté en la party.
        
        Returns:
            True si hay una party (confirmada o formándose) para ese juego (y el usuario está en ella si se especificó)
        """
        if game_name not in self.active_sessions:
            return False
        
        session = self.active_sessions[game_name]
        
        # Si no se especificó user_id, party existe (confirmada o no)
        if user_id is None:
            return True  # Hay party (confirmada o formándose)
        
        # Si se especificó user_id, verificar que esté en la party (confirmada o formándose)
        return user_id in session.player_ids
    
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

