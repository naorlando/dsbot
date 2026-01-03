"""
Tests para supresión de notificaciones de games cuando hay party activa
Verifica que games no notifican si ya hay party del mismo juego
"""

import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from core.game_session import GameSessionManager, GameSession
from core.party_session import PartySessionManager, PartySession
from core.app_id_tracker import clear_tracker


class MockMember:
    """Mock de un miembro de Discord"""
    def __init__(self, user_id, username, guild_id=123456789):
        self.id = int(user_id) if isinstance(user_id, str) else user_id
        self.display_name = username
        self.guild = MagicMock()
        self.guild.id = guild_id


class MockActivity:
    """Mock de una actividad de Discord"""
    def __init__(self, name, app_id):
        self.name = name
        self.application_id = app_id


class TestGamePartySuppression(unittest.TestCase):
    """Tests para supresión de notificaciones de games"""
    
    def setUp(self):
        """Setup común para todos los tests"""
        self.bot = MagicMock()
        self.party_manager = PartySessionManager(self.bot)
        self.game_manager = GameSessionManager(self.bot, party_manager=self.party_manager)
        
        self.test_config = {
            'notify_games': True,
            'game_activity_types': ['playing'],
            'messages': {
                'game_start': '🎮 **{user}** está {verb} **{activity}**'
            }
        }
        clear_tracker()
    
    def tearDown(self):
        """Cleanup"""
        clear_tracker()
    
    def test_has_active_party_false(self):
        """Test 1: has_active_party retorna False cuando no hay party"""
        has_party = self.party_manager.has_active_party('League of Legends')
        self.assertFalse(has_party)
    
    def test_has_active_party_true(self):
        """Test 2: has_active_party retorna True cuando hay party confirmada"""
        # Crear party confirmada
        session = PartySession(
            game_name='VALORANT',
            player_ids={'user1', 'user2'},
            player_names=['Player1', 'Player2'],
            guild_id=123456789
        )
        session.is_confirmed = True
        session.state = 'active'
        
        self.party_manager.active_sessions['VALORANT'] = session
        
        has_party = self.party_manager.has_active_party('VALORANT')
        self.assertTrue(has_party)
    
    def test_has_active_party_inactive(self):
        """Test 3: has_active_party retorna False si party está inactive"""
        session = PartySession(
            game_name='Dota 2',
            player_ids={'user1', 'user2'},
            player_names=['Player1', 'Player2'],
            guild_id=123456789
        )
        session.is_confirmed = True
        session.state = 'inactive'  # ← Inactiva
        
        self.party_manager.active_sessions['Dota 2'] = session
        
        has_party = self.party_manager.has_active_party('Dota 2')
        self.assertFalse(has_party)
    
    def test_game_notification_suppressed_with_party(self):
        """Test 4: Notificación de game suprimida cuando hay party activa"""
        async def run_test():
            # Crear party activa confirmada
            party_session = PartySession(
                game_name='League of Legends',
                player_ids={'user1', 'user2'},
                player_names=['agu', 'Pino'],
                guild_id=123456789
            )
            party_session.is_confirmed = True
            party_session.state = 'active'
            self.party_manager.active_sessions['League of Legends'] = party_session
            
            # Crear game session
            member = MockMember('user3', 'Zeta')
            game_session = GameSession(
                user_id='user3',
                username='Zeta',
                game_name='League of Legends',
                app_id=401518684763586560,
                activity_type='playing',
                guild_id=123456789
            )
            game_session.is_confirmed = False
            
            # Mock de send_notification
            with patch('core.game_session.send_notification', new_callable=AsyncMock) as mock_notify:
                # Llamar a _on_session_confirmed_phase1
                await self.game_manager._on_session_confirmed_phase1(game_session, member, self.test_config)
                
                # Verificar que NO se llamó a send_notification
                mock_notify.assert_not_called()
                
                # Verificar que entry_notification_sent es False
                self.assertFalse(game_session.entry_notification_sent)
        
        asyncio.run(run_test())
    
    def test_game_notification_sent_without_party(self):
        """Test 5: Notificación de game enviada cuando NO hay party activa"""
        async def run_test():
            # NO crear party (o crear una inactiva)
            
            # Crear game session
            member = MockMember('user1', 'Player1')
            game_session = GameSession(
                user_id='user1',
                username='Player1',
                game_name='Counter-Strike 2',
                app_id=730,
                activity_type='playing',
                guild_id=123456789
            )
            
            # Trackear app_id para que NO sea sospechoso
            from core.app_id_tracker import track_app_id
            for _ in range(5):
                track_app_id('Counter-Strike 2', 730)
            
            # Mock de cooldown y send_notification
            with patch('core.game_session.check_cooldown', return_value=True):
                with patch('core.game_session.send_notification', new_callable=AsyncMock) as mock_notify:
                    mock_notify.return_value = MagicMock()  # Mock del mensaje retornado
                    
                    # Llamar a _on_session_confirmed_phase1
                    await self.game_manager._on_session_confirmed_phase1(game_session, member, self.test_config)
                    
                    # Verificar que SÍ se llamó a send_notification
                    mock_notify.assert_called_once()
                    
                    # Verificar que entry_notification_sent es True
                    self.assertTrue(game_session.entry_notification_sent)
        
        asyncio.run(run_test())
    
    def test_suspicious_app_id_suppressed(self):
        """Test 6: Notificación suprimida para app_id sospechoso"""
        async def run_test():
            # Trackear un app_id "real" muchas veces
            from core.app_id_tracker import track_app_id
            for _ in range(10):
                track_app_id('Fortnite', 100)
            
            # Intentar con app_id fake (solo 1 vez)
            member = MockMember('user1', 'FakePlayer')
            game_session = GameSession(
                user_id='user1',
                username='FakePlayer',
                game_name='Fortnite',
                app_id=999,  # Fake
                activity_type='playing',
                guild_id=123456789
            )
            
            with patch('core.game_session.send_notification', new_callable=AsyncMock) as mock_notify:
                await self.game_manager._on_session_confirmed_phase1(game_session, member, self.test_config)
                
                # NO debería notificar (app_id sospechoso)
                mock_notify.assert_not_called()
                self.assertFalse(game_session.entry_notification_sent)
        
        asyncio.run(run_test())
    
    def test_first_app_id_not_suspicious(self):
        """Test 7: Primer app_id de un juego NO es sospechoso"""
        async def run_test():
            # Primer app_id que vemos para este juego
            member = MockMember('user1', 'FirstPlayer')
            game_session = GameSession(
                user_id='user1',
                username='FirstPlayer',
                game_name='New Game',
                app_id=12345,
                activity_type='playing',
                guild_id=123456789
            )
            
            # Mock de cooldown y send_notification
            with patch('core.game_session.check_cooldown', return_value=True):
                with patch('core.game_session.send_notification', new_callable=AsyncMock) as mock_notify:
                    mock_notify.return_value = MagicMock()
                    
                    await self.game_manager._on_session_confirmed_phase1(game_session, member, self.test_config)
                    
                    # Debería notificar (primer app_id no es sospechoso)
                    mock_notify.assert_called_once()
                    self.assertTrue(game_session.entry_notification_sent)
        
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()

