"""
Tests para Soft Close de Party Detection
Verifica todos los casos de uso de la Opción A
"""

import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from core.party_session import PartySession, PartySessionManager


class TestPartySoftClose(unittest.TestCase):
    """Tests para la funcionalidad de Soft Close en parties"""
    
    def setUp(self):
        """Setup común para todos los tests"""
        self.bot = MagicMock()
        self.manager = PartySessionManager(self.bot)
        self.test_config = {
            'party_detection': {
                'enabled': True,
                'min_players': 2,
                'notify_on_formed': True,
                'notify_on_join': True,
                'cooldown_minutes': 60,
                'reactivation_window_minutes': 30,
                'use_here_mention': True,
                'blacklisted_games': []
            }
        }
        self.guild_id = 123456789
    
    def test_party_session_initial_state(self):
        """Test 1: PartySession se crea con estado 'active'"""
        session = PartySession(
            game_name="League of Legends",
            player_ids={'user1', 'user2'},
            player_names=['Player1', 'Player2'],
            guild_id=self.guild_id
        )
        
        self.assertEqual(session.state, 'active')
        self.assertIsNone(session.inactive_since)
        self.assertEqual(session.reactivation_window, 30 * 60)  # 30 min por defecto
    
    def test_state_transitions(self):
        """Test 2: Transiciones de estado correctas (active → inactive → closed)"""
        session = PartySession(
            game_name="VALORANT",
            player_ids={'user1', 'user2'},
            player_names=['Player1', 'Player2'],
            guild_id=self.guild_id
        )
        
        # Estado inicial
        self.assertEqual(session.state, 'active')
        
        # Marcar como inactive
        session.state = 'inactive'
        session.inactive_since = datetime.now()
        self.assertEqual(session.state, 'inactive')
        self.assertIsNotNone(session.inactive_since)
        
        # Marcar como closed
        session.state = 'closed'
        self.assertEqual(session.state, 'closed')
    
    @patch('core.party_session.send_notification', new_callable=AsyncMock)
    async def test_lobby_corto_reactivacion(self, mock_notify):
        """Test 3: Lobby corto (< 30 min) → reactivación sin spam"""
        current_players = [
            {'user_id': 'user1', 'username': 'Player1', 'activity': 'LoL'},
            {'user_id': 'user2', 'username': 'Player2', 'activity': 'LoL'}
        ]
        
        # 17:00 - Party formada
        await self.manager.handle_start('League of Legends', current_players, self.guild_id, self.test_config)
        
        # Verificar que se creó la sesión
        self.assertIn('League of Legends', self.manager.active_sessions)
        session = self.manager.active_sessions['League of Legends']
        self.assertEqual(session.state, 'active')
        
        # 17:15 - Entran en lobby (simulate grace period expired)
        session.last_activity_update = datetime.now() - timedelta(minutes=20)
        await self.manager.handle_end('League of Legends', self.test_config)
        
        # Verificar que pasó a inactive (no closed)
        self.assertEqual(session.state, 'inactive')
        self.assertIsNotNone(session.inactive_since)
        self.assertIn('League of Legends', self.manager.active_sessions)  # Todavía en memoria
        
        # 17:25 - Salen del lobby (< 30 min)
        await self.manager.handle_start('League of Legends', current_players, self.guild_id, self.test_config)
        
        # Verificar que se reactivó
        self.assertEqual(session.state, 'active')
        self.assertIsNone(session.inactive_since)
        
        # ✅ Verificar que NO se envió notificación de reactivación
        # Solo debe haber 1 notificación (la inicial)
        self.assertEqual(mock_notify.call_count, 1)  # Solo la formación inicial
    
    @patch('core.party_session.send_notification', new_callable=AsyncMock)
    @patch('core.party_session.check_cooldown')
    async def test_lobby_largo_nueva_party(self, mock_cooldown, mock_notify):
        """Test 4: Lobby largo (> 30 min) → nueva party sin spam (cooldown)"""
        # Simular que el cooldown NO ha pasado (previene spam)
        mock_cooldown.return_value = False
        
        current_players = [
            {'user_id': 'user1', 'username': 'Player1', 'activity': 'LoL'},
            {'user_id': 'user2', 'username': 'Player2', 'activity': 'LoL'}
        ]
        
        # 17:00 - Party formada
        await self.manager.handle_start('League of Legends', current_players, self.guild_id, self.test_config)
        
        session = self.manager.active_sessions['League of Legends']
        
        # 17:15 - Entran en lobby
        session.last_activity_update = datetime.now() - timedelta(minutes=20)
        await self.manager.handle_end('League of Legends', self.test_config)
        self.assertEqual(session.state, 'inactive')
        
        # 17:50 - Simular que pasaron 35 min (ventana expirada)
        session.inactive_since = datetime.now() - timedelta(minutes=35)
        await self.manager.handle_end('League of Legends', self.test_config)
        
        # Verificar que se cerró definitivamente
        self.assertNotIn('League of Legends', self.manager.active_sessions)
        
        # 17:52 - Nueva party formada
        await self.manager.handle_start('League of Legends', current_players, self.guild_id, self.test_config)
        
        # Verificar que se creó nueva sesión
        self.assertIn('League of Legends', self.manager.active_sessions)
        new_session = self.manager.active_sessions['League of Legends']
        self.assertEqual(new_session.state, 'active')
        
        # ✅ Cooldown de 60 min previene spam (mock_cooldown.return_value = False)
        # No se debe enviar notificación en la nueva party
    
    async def test_usuario_sale_vuelve_mantiene_party(self):
        """Test 5: Usuario sale temporalmente, party sigue activa"""
        current_players = [
            {'user_id': 'user1', 'username': 'Player1', 'activity': 'LoL'},
            {'user_id': 'user2', 'username': 'Player2', 'activity': 'LoL'},
            {'user_id': 'user3', 'username': 'Player3', 'activity': 'LoL'}
        ]
        
        # Party con 3 jugadores
        await self.manager.handle_start('League of Legends', current_players, self.guild_id, self.test_config)
        
        session = self.manager.active_sessions['League of Legends']
        self.assertEqual(len(session.player_ids), 3)
        
        # Usuario 3 se va (quedan 2 jugadores)
        current_players_2 = [
            {'user_id': 'user1', 'username': 'Player1', 'activity': 'LoL'},
            {'user_id': 'user2', 'username': 'Player2', 'activity': 'LoL'}
        ]
        await self.manager.handle_start('League of Legends', current_players_2, self.guild_id, self.test_config)
        
        # Verificar que la party sigue activa (≥ min_players)
        self.assertEqual(session.state, 'active')
        self.assertEqual(len(session.player_ids), 2)
        
        # Usuario 3 vuelve
        await self.manager.handle_start('League of Legends', current_players, self.guild_id, self.test_config)
        
        # Verificar que la party sigue activa
        self.assertEqual(session.state, 'active')
        self.assertEqual(len(session.player_ids), 3)
    
    async def test_todos_salen_ventana_activa(self):
        """Test 6: Todos se van, quedan < 2 jugadores → reactivación posible"""
        current_players = [
            {'user_id': 'user1', 'username': 'Player1', 'activity': 'LoL'},
            {'user_id': 'user2', 'username': 'Player2', 'activity': 'LoL'}
        ]
        
        # Party formada
        await self.manager.handle_start('League of Legends', current_players, self.guild_id, self.test_config)
        
        session = self.manager.active_sessions['League of Legends']
        
        # Ambos se van (< min_players)
        current_players_empty = []
        session.last_activity_update = datetime.now() - timedelta(minutes=20)
        await self.manager.handle_end('League of Legends', self.test_config)
        
        # Verificar que pasó a inactive
        self.assertEqual(session.state, 'inactive')
        
        # Ambos vuelven (dentro de 30 min)
        await self.manager.handle_start('League of Legends', current_players, self.guild_id, self.test_config)
        
        # Verificar que se reactivó
        self.assertEqual(session.state, 'active')
    
    async def test_limpieza_sesiones_expiradas(self):
        """Test 7: Cleanup elimina sesiones inactivas expiradas"""
        current_players = [
            {'user_id': 'user1', 'username': 'Player1', 'activity': 'LoL'},
            {'user_id': 'user2', 'username': 'Player2', 'activity': 'LoL'}
        ]
        
        # Crear party
        await self.manager.handle_start('League of Legends', current_players, self.guild_id, self.test_config)
        
        session = self.manager.active_sessions['League of Legends']
        
        # Marcar como inactive y expirar ventana
        session.state = 'inactive'
        session.inactive_since = datetime.now() - timedelta(minutes=35)
        session.reactivation_window = 30 * 60
        
        # Ejecutar limpieza
        self.manager._cleanup_expired_inactive_sessions()
        
        # Verificar que se eliminó
        self.assertNotIn('League of Legends', self.manager.active_sessions)
    
    async def test_limpieza_no_toca_sesiones_activas(self):
        """Test 8: Cleanup NO elimina sesiones activas o en ventana válida"""
        current_players = [
            {'user_id': 'user1', 'username': 'Player1', 'activity': 'LoL'},
            {'user_id': 'user2', 'username': 'Player2', 'activity': 'LoL'}
        ]
        
        # Crear party activa
        await self.manager.handle_start('League of Legends', current_players, self.guild_id, self.test_config)
        
        # Crear party inactiva pero en ventana válida
        current_players_valorant = [
            {'user_id': 'user3', 'username': 'Player3', 'activity': 'VALORANT'},
            {'user_id': 'user4', 'username': 'Player4', 'activity': 'VALORANT'}
        ]
        await self.manager.handle_start('VALORANT', current_players_valorant, self.guild_id, self.test_config)
        
        valorant_session = self.manager.active_sessions['VALORANT']
        valorant_session.state = 'inactive'
        valorant_session.inactive_since = datetime.now() - timedelta(minutes=10)  # Todavía válida
        
        # Ejecutar limpieza
        self.manager._cleanup_expired_inactive_sessions()
        
        # Verificar que ambas siguen en memoria
        self.assertIn('League of Legends', self.manager.active_sessions)
        self.assertIn('VALORANT', self.manager.active_sessions)
    
    async def test_reactivation_window_configurable(self):
        """Test 9: Ventana de reactivación lee del config correctamente"""
        # Config con ventana de 15 min
        custom_config = {
            'party_detection': {
                'enabled': True,
                'min_players': 2,
                'reactivation_window_minutes': 15,
                'blacklisted_games': []
            }
        }
        
        current_players = [
            {'user_id': 'user1', 'username': 'Player1', 'activity': 'LoL'},
            {'user_id': 'user2', 'username': 'Player2', 'activity': 'LoL'}
        ]
        
        # Crear party con config custom
        await self.manager.handle_start('League of Legends', current_players, self.guild_id, custom_config)
        
        session = self.manager.active_sessions['League of Legends']
        
        # Verificar que leyó la ventana del config
        self.assertEqual(session.reactivation_window, 15 * 60)
    
    async def test_multiples_lobbies_misma_sesion(self):
        """Test 10: Múltiples lobbies en misma sesión no rompen tracking"""
        current_players = [
            {'user_id': 'user1', 'username': 'Player1', 'activity': 'LoL'},
            {'user_id': 'user2', 'username': 'Player2', 'activity': 'LoL'}
        ]
        
        # 17:00 - Party formada
        await self.manager.handle_start('League of Legends', current_players, self.guild_id, self.test_config)
        
        session = self.manager.active_sessions['League of Legends']
        start_time = session.start_time
        
        # 17:15 - Lobby 1 (10 min)
        session.last_activity_update = datetime.now() - timedelta(minutes=20)
        await self.manager.handle_end('League of Legends', self.test_config)
        self.assertEqual(session.state, 'inactive')
        
        # 17:25 - Vuelven a jugar
        await self.manager.handle_start('League of Legends', current_players, self.guild_id, self.test_config)
        self.assertEqual(session.state, 'active')
        
        # 17:45 - Lobby 2 (5 min)
        session.last_activity_update = datetime.now() - timedelta(minutes=20)
        await self.manager.handle_end('League of Legends', self.test_config)
        self.assertEqual(session.state, 'inactive')
        
        # 17:50 - Vuelven a jugar
        await self.manager.handle_start('League of Legends', current_players, self.guild_id, self.test_config)
        self.assertEqual(session.state, 'active')
        
        # Verificar que es la MISMA sesión (mismo start_time)
        self.assertEqual(session.start_time, start_time)


def run_async_test(coro):
    """Helper para ejecutar tests asíncronos"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


if __name__ == '__main__':
    # Ejecutar tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPartySoftClose)
    
    # Adaptar tests asíncronos
    for test in suite:
        if asyncio.iscoroutinefunction(getattr(test, test._testMethodName)):
            original_method = getattr(test, test._testMethodName)
            setattr(test, test._testMethodName, lambda self, m=original_method: run_async_test(m(self)))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit con código apropiado
    exit(0 if result.wasSuccessful() else 1)

