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
        Maneja el inicio o actualización de una party.
        
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
        
        # Caso 1: No hay sesión activa → crear nueva party
        if game_name not in self.active_sessions:
            session = PartySession(game_name, current_player_ids, current_player_names, guild_id)
            self.active_sessions[game_name] = session
            
            # Iniciar verificación en background
            session.verification_task = asyncio.create_task(
                self._verify_session(session, None, config)
            )
            
            logger.info(f'🎮 Nueva party iniciada: {game_name} con {len(current_players)} jugadores')
            logger.debug(f'   Jugadores: {", ".join(current_player_names)}')
        
        # Caso 2: Sesión existente → actualizar jugadores
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
                    
                    # Verificar cooldown por juego
                    cooldown_minutes = party_config.get('cooldown_minutes', 10)
                    if check_cooldown(game_name, f'party_join_{game_name}', cooldown_seconds=cooldown_minutes * 60):
                        message = self._create_player_joined_message(game_name, new_player_names, current_player_names, party_config)
                        if message:
                            await send_notification(message, self.bot)
                            logger.info(f'🎮 Notificación de jugador unido a party: {game_name}')
                
                # Actualizar en stats si está confirmada
                self._update_active_party_in_stats(game_name, session)
            
            logger.debug(f'🎮 Party actualizada: {game_name} con {len(current_players)} jugadores')
    
    async def handle_end(self, game_name: str, config: dict):
        """
        Finaliza una party cuando ya no cumple los requisitos.
        
        Args:
            game_name: Nombre del juego
            config: Configuración del bot
        """
        if game_name not in self.active_sessions:
            return
        
        session = self.active_sessions[game_name]
        
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
        return current_count >= 2
    
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
            'start': active_party['start'],
            'end': end_time.isoformat(),
            'duration_minutes': duration_minutes,
            'players': active_party['players'],
            'player_names': active_party['player_names'],
            'max_players': active_party['max_players']
        }
        
        # Agregar a historial
        stats['parties']['history'].insert(0, party_record)
        
        # Limitar historial a 1000 parties
        if len(stats['parties']['history']) > 1000:
            stats['parties']['history'] = stats['parties']['history'][:1000]
        
        # Actualizar estadísticas por juego
        self._update_game_stats(game_name, party_record)
        
        # Eliminar de parties activas
        del stats['parties']['active'][game_name]
        
        save_stats()
        logger.debug(f'💾 Party guardada en historial: {game_name} ({duration_minutes} min)')
    
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
        game_stats['total_parties'] += 1
        game_stats['total_duration_minutes'] += party_record['duration_minutes']
        game_stats['max_players_ever'] = max(game_stats['max_players_ever'], party_record['max_players'])
        
        # Agregar jugadores únicos (convertir a set si no lo es)
        if not isinstance(game_stats['total_unique_players'], set):
            game_stats['total_unique_players'] = set(game_stats['total_unique_players'])
        game_stats['total_unique_players'].update(party_record['players'])
        
        # Convertir set a lista para serialización JSON
        game_stats['total_unique_players'] = list(game_stats['total_unique_players'])
    
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

