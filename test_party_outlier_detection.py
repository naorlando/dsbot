"""
Tests para detección de outliers en parties
Verifica que app_ids sospechosos son rechazados correctamente
"""

import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from core.party_session import PartySessionManager
from core.app_id_tracker import clear_tracker


class MockActivity:
    """Mock de una actividad de Discord"""
    def __init__(self, name, app_id):
        self.name = name
        self.application_id = app_id


class TestPartyOutlierDetection(unittest.TestCase):
    """Tests para detección de outliers en parties"""
    
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
        clear_tracker()
    
    def tearDown(self):
        """Cleanup después de cada test"""
        clear_tracker()
    
    def test_all_same_app_id(self):
        """Test 1: Todos los jugadores con el mismo app_id → aceptar todos"""
        players = [
            {
                'user_id': 'user1',
                'username': 'Player1',
                'activity': MockActivity('League of Legends', 401518684763586560)
            },
            {
                'user_id': 'user2',
                'username': 'Player2',
                'activity': MockActivity('League of Legends', 401518684763586560)
            },
            {
                'user_id': 'user3',
                'username': 'Player3',
                'activity': MockActivity('League of Legends', 401518684763586560)
            }
        ]
        
        filtered = self.manager._filter_players_by_app_id('League of Legends', players, self.test_config['party_detection'])
        
        self.assertEqual(len(filtered), 3)
        self.assertEqual([p['username'] for p in filtered], ['Player1', 'Player2', 'Player3'])
    
    def test_outlier_detection_2_vs_1(self):
        """Test 2: 2 jugadores con app_id real vs 1 fake → rechazar fake"""
        players = [
            {
                'user_id': 'user1',
                'username': 'agu',
                'activity': MockActivity('League of Legends', 401518684763586560)
            },
            {
                'user_id': 'user2',
                'username': 'Pino',
                'activity': MockActivity('League of Legends', 401518684763586560)
            },
            {
                'user_id': 'user3',
                'username': 'Zeta',
                'activity': MockActivity('League of Legends', 1402418696126992445)
            }
        ]
        
        filtered = self.manager._filter_players_by_app_id('League of Legends', players, self.test_config['party_detection'])
        
        # Solo agu y Pino deberían pasar
        self.assertEqual(len(filtered), 2)
        self.assertEqual([p['username'] for p in filtered], ['agu', 'Pino'])
    
    def test_outlier_detection_3_vs_2(self):
        """Test 3: 3 vs 2 → aceptar el grupo mayoritario"""
        players = [
            {
                'user_id': 'user1',
                'username': 'Player1',
                'activity': MockActivity('VALORANT', 700)
            },
            {
                'user_id': 'user2',
                'username': 'Player2',
                'activity': MockActivity('VALORANT', 700)
            },
            {
                'user_id': 'user3',
                'username': 'Player3',
                'activity': MockActivity('VALORANT', 700)
            },
            {
                'user_id': 'user4',
                'username': 'Fake1',
                'activity': MockActivity('VALORANT', 999)
            },
            {
                'user_id': 'user5',
                'username': 'Fake2',
                'activity': MockActivity('VALORANT', 999)
            }
        ]
        
        filtered = self.manager._filter_players_by_app_id('VALORANT', players, self.test_config['party_detection'])
        
        # Los 3 con app_id 700 deberían pasar
        self.assertEqual(len(filtered), 3)
        self.assertIn('Player1', [p['username'] for p in filtered])
        self.assertIn('Player2', [p['username'] for p in filtered])
        self.assertIn('Player3', [p['username'] for p in filtered])
    
    def test_no_activity(self):
        """Test 4: Jugadores sin actividad son rechazados"""
        players = [
            {
                'user_id': 'user1',
                'username': 'Player1',
                'activity': MockActivity('Dota 2', 570)
            },
            {
                'user_id': 'user2',
                'username': 'Player2',
                'activity': None  # Sin actividad
            }
        ]
        
        filtered = self.manager._filter_players_by_app_id('Dota 2', players, self.test_config['party_detection'])
        
        # Solo Player1 debería pasar
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['username'], 'Player1')
    
    def test_empty_players_list(self):
        """Test 5: Lista vacía retorna lista vacía"""
        filtered = self.manager._filter_players_by_app_id('Any Game', [], self.test_config['party_detection'])
        self.assertEqual(len(filtered), 0)
    
    def test_all_outliers_rejected(self):
        """Test 6: Si todos son outliers minoritarios, retorna vacío"""
        # Este es un edge case: solo 1 jugador por app_id
        players = [
            {
                'user_id': 'user1',
                'username': 'Player1',
                'activity': MockActivity('CS2', 730)
            },
            {
                'user_id': 'user2',
                'username': 'Player2',
                'activity': MockActivity('CS2', 999)
            }
        ]
        
        filtered = self.manager._filter_players_by_app_id('CS2', players, self.test_config['party_detection'])
        
        # En empate 1 vs 1, el primero que aparezca en Counter.most_common() gana
        # Debería retornar 1 jugador (el mayoritario)
        self.assertEqual(len(filtered), 1)
    
    def test_integration_handle_start_rejects_outliers(self):
        """Test 7: handle_start rechaza party si quedan < min_players después de filtrar"""
        async def run_test():
            players = [
                {
                    'user_id': 'user1',
                    'username': 'Real1',
                    'activity': MockActivity('Fortnite', 100)
                },
                {
                    'user_id': 'user2',
                    'username': 'Fake',
                    'activity': MockActivity('Fortnite', 999)
                }
            ]
            
            # Después de filtrar, quedará solo 1 jugador (< min_players=2)
            with patch.object(self.manager, '_verify_session', new_callable=AsyncMock):
                await self.manager.handle_start('Fortnite', players, self.guild_id, self.test_config)
            
            # No debería haber creado party
            self.assertNotIn('Fortnite', self.manager.active_sessions)
        
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()

