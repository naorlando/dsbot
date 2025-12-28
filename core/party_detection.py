"""
Sistema de detección de parties (2+ jugadores en el mismo juego)
Maneja notificaciones y tracking de analytics
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
import discord

from core.persistence import stats, save_stats
from core.cooldown import check_cooldown

logger = logging.getLogger('dsbot')


class PartyDetector:
    """Detecta y gestiona parties (grupos de jugadores en el mismo juego)"""
    
    def __init__(self):
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
    
    def get_active_players_by_game(self, guild) -> Dict[str, List[Dict]]:
        """
        Obtiene jugadores activos agrupados por juego.
        
        Returns:
            Dict con formato: {game_name: [{user_id, username, activity}, ...]}
        """
        players_by_game = defaultdict(list)
        
        for member in guild.members:
            if member.bot:
                continue
            
            # Obtener actividades de juego (mismo filtro que en events.py)
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
        
        return dict(players_by_game)
    
    def detect_party_changes(self, game_name: str, current_players: List[Dict], 
                            config: dict) -> Tuple[Optional[str], Optional[str]]:
        """
        Detecta cambios en una party y retorna mensajes de notificación.
        
        Returns:
            Tuple (party_formed_msg, player_joined_msg)
            - party_formed_msg: Mensaje si se formó una party (1 → 2+)
            - player_joined_msg: Mensaje si alguien se unió a party existente
        """
        party_config = config.get('party_detection', {})
        
        # Verificar si está habilitado
        if not party_config.get('enabled', True):
            return None, None
        
        # Verificar número mínimo de jugadores
        min_players = party_config.get('min_players', 2)
        if len(current_players) < min_players:
            # Si había una party activa, finalizarla
            if game_name in stats['parties']['active']:
                self._finalize_party(game_name)
            return None, None
        
        # Verificar si el juego está en blacklist
        blacklist = party_config.get('blacklisted_games', [])
        if game_name in blacklist:
            return None, None
        
        current_player_ids = {p['user_id'] for p in current_players}
        party_formed_msg = None
        player_joined_msg = None
        
        # Caso 1: No había party activa → se formó una nueva
        if game_name not in stats['parties']['active']:
            if party_config.get('notify_on_formed', True):
                party_formed_msg = self._create_party_formed_message(
                    game_name, current_players, party_config
                )
            
            # Crear party activa
            self._create_active_party(game_name, current_players)
            logger.info(f'🎮 Party formada: {game_name} ({len(current_players)} jugadores)')
        
        # Caso 2: Ya había party → alguien se unió o salió
        else:
            active_party = stats['parties']['active'][game_name]
            previous_player_ids = set(active_party['players'])
            
            # Detectar nuevos jugadores
            new_players = current_player_ids - previous_player_ids
            
            if new_players and party_config.get('notify_on_join', True):
                # Verificar cooldown para este juego
                cooldown_minutes = party_config.get('cooldown_minutes', 30)
                cooldown_key = f'party:{game_name}'
                
                if check_cooldown('global', cooldown_key, cooldown_seconds=cooldown_minutes * 60):
                    new_player_data = [p for p in current_players if p['user_id'] in new_players]
                    player_joined_msg = self._create_player_joined_message(
                        game_name, new_player_data, len(current_players), party_config
                    )
                    logger.info(f'🎮 Jugador(es) se unieron a party: {game_name} ({len(current_players)} jugadores)')
            
            # Actualizar party activa
            self._update_active_party(game_name, current_players)
        
        return party_formed_msg, player_joined_msg
    
    def _create_party_formed_message(self, game_name: str, players: List[Dict], 
                                    config: dict) -> str:
        """Crea mensaje de party formada"""
        mention = '@here ' if config.get('use_here_mention', True) else ''
        player_names = [p['username'] for p in players]
        
        if len(players) == 2:
            players_str = f"**{player_names[0]}** y **{player_names[1]}**"
        elif len(players) == 3:
            players_str = f"**{player_names[0]}**, **{player_names[1]}** y **{player_names[2]}**"
        else:
            players_str = ', '.join([f"**{name}**" for name in player_names[:-1]]) + f" y **{player_names[-1]}**"
        
        template = config.get('message_template_formed', 
                            "🎮 {mention}¡Party de **{game}** formada! {players} están jugando juntos")
        
        return template.format(
            mention=mention,
            game=game_name,
            players=players_str
        )
    
    def _create_player_joined_message(self, game_name: str, new_players: List[Dict], 
                                     total_players: int, config: dict) -> str:
        """Crea mensaje de jugador uniéndose a party"""
        mention = '@here ' if config.get('use_here_mention', True) else ''
        new_player_names = [p['username'] for p in new_players]
        
        if len(new_players) == 1:
            players_str = f"**{new_player_names[0]}**"
            verb = "se unió"
        else:
            players_str = ' y '.join([f"**{name}**" for name in new_player_names])
            verb = "se unieron"
        
        template = config.get('message_template_join',
                            "🎮 {mention}{players} {verb} a la party de **{game}** ({total} jugadores)")
        
        return template.format(
            mention=mention,
            players=players_str,
            verb=verb,
            game=game_name,
            total=total_players
        )
    
    def _create_active_party(self, game_name: str, players: List[Dict]):
        """Crea una party activa"""
        stats['parties']['active'][game_name] = {
            'players': [p['user_id'] for p in players],
            'player_names': [p['username'] for p in players],
            'start': datetime.now().isoformat(),
            'notified_at_count': len(players),
            'last_notification': datetime.now().isoformat(),
            'max_players': len(players)
        }
        save_stats()
    
    def _update_active_party(self, game_name: str, players: List[Dict]):
        """Actualiza una party activa existente"""
        active_party = stats['parties']['active'][game_name]
        active_party['players'] = [p['user_id'] for p in players]
        active_party['player_names'] = [p['username'] for p in players]
        
        # Actualizar máximo de jugadores si es necesario
        if len(players) > active_party.get('max_players', 0):
            active_party['max_players'] = len(players)
        
        save_stats()
    
    def _finalize_party(self, game_name: str):
        """Finaliza una party y la guarda en historial"""
        if game_name not in stats['parties']['active']:
            return
        
        active_party = stats['parties']['active'][game_name]
        
        # Calcular duración
        start_time = datetime.fromisoformat(active_party['start'])
        duration_minutes = int((datetime.now() - start_time).total_seconds() / 60)
        
        # Guardar en historial (mantener últimas 100 parties)
        party_record = {
            'game': game_name,
            'players': active_party['players'],
            'player_names': active_party['player_names'],
            'start': active_party['start'],
            'end': datetime.now().isoformat(),
            'duration_minutes': duration_minutes,
            'max_players': active_party.get('max_players', len(active_party['players']))
        }
        
        stats['parties']['history'].insert(0, party_record)
        stats['parties']['history'] = stats['parties']['history'][:100]
        
        # Actualizar stats del juego
        self._update_game_stats(game_name, party_record)
        
        # Eliminar party activa
        del stats['parties']['active'][game_name]
        
        save_stats()
        logger.info(f'🎮 Party finalizada: {game_name} ({duration_minutes} min, max {party_record["max_players"]} jugadores)')
    
    def _update_game_stats(self, game_name: str, party_record: Dict):
        """Actualiza estadísticas agregadas del juego"""
        if game_name not in stats['parties']['stats_by_game']:
            stats['parties']['stats_by_game'][game_name] = {
                'total_parties': 0,
                'total_duration_minutes': 0,
                'max_players_record': 0,
                'total_players_sum': 0,  # Para calcular promedio
                'most_frequent_pairs': {}
            }
        
        game_stats = stats['parties']['stats_by_game'][game_name]
        game_stats['total_parties'] += 1
        game_stats['total_duration_minutes'] += party_record['duration_minutes']
        game_stats['total_players_sum'] += party_record['max_players']
        
        if party_record['max_players'] > game_stats['max_players_record']:
            game_stats['max_players_record'] = party_record['max_players']
        
        # Actualizar duplas más frecuentes
        players = sorted(party_record['player_names'])
        for i in range(len(players)):
            for j in range(i + 1, len(players)):
                pair_key = f"{players[i]}-{players[j]}"
                game_stats['most_frequent_pairs'][pair_key] = game_stats['most_frequent_pairs'].get(pair_key, 0) + 1
        
        save_stats()
    
    def get_active_parties(self) -> Dict[str, Dict]:
        """Retorna todas las parties activas"""
        return stats['parties'].get('active', {})
    
    def get_party_history(self, timeframe: str = 'all', limit: int = 50) -> List[Dict]:
        """
        Retorna historial de parties filtrado por timeframe.
        
        Args:
            timeframe: 'today', 'week', 'month', 'all'
            limit: Número máximo de parties a retornar
        """
        history = stats['parties'].get('history', [])
        
        if timeframe == 'all':
            return history[:limit]
        
        from datetime import timedelta
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
        """
        Retorna estadísticas de parties por juego.
        
        Args:
            game_name: Juego específico o None para todos
        """
        all_stats = stats['parties'].get('stats_by_game', {})
        
        if game_name:
            return all_stats.get(game_name, {})
        
        return all_stats

