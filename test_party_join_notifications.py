"""
Test para verificar que las notificaciones de "join party" se envían correctamente
cuando múltiples jugadores se unen a una party ya confirmada.
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import asyncio

from core.party_session import PartySessionManager


class TestPartyJoinNotifications(unittest.IsolatedAsyncioTestCase):
    """Tests para notificaciones de jugadores uniéndose a parties"""
    
    async def asyncSetUp(self):
        """Setup común para todos los tests"""
        self.bot = Mock()
        self.party_manager = PartySessionManager(self.bot)
        
        # Config mock
        self.config = {
            'party_detection': {
                'enabled': True,
                'notify_on_join': True,
                'cooldown_minutes': 10,
                'blacklisted_games': []
            }
        }
    
    async def test_multiple_players_join_confirmed_party(self):
        """
        Test que verifica que cuando múltiples jugadores se unen a una party confirmada,
        cada uno recibe su notificación (sin cooldown global por juego).
        
        Escenario:
        1. Party de 2 jugadores se forma y confirma (Pino, agu)
        2. Black Tomi se une → debe notificar
        3. Zamu se une → debe notificar
        4. Zeta se une → debe notificar
        """
        game_name = "Counter-Strike 2"
        guild_id = 123
        
        # Paso 1: Crear party inicial con 2 jugadores
        initial_players = [
            {'user_id': '111', 'username': 'Pino'},
            {'user_id': '222', 'username': 'agu'}
        ]
        
        with patch('core.party_session.send_notification', new_callable=AsyncMock) as mock_notify:
            with patch('core.party_session.check_cooldown', return_value=True):
                # Crear party
                await self.party_manager.handle_start(game_name, initial_players, guild_id, self.config)
                
                # Confirmar party manualmente
                session = self.party_manager.active_sessions[game_name]
                session.is_confirmed = True
                
                # Resetear mock para contar solo las notificaciones de "join"
                mock_notify.reset_mock()
                
                # Paso 2: Black Tomi se une (3er jugador)
                players_with_tomi = initial_players + [
                    {'user_id': '333', 'username': 'Black Tomi Returns'}
                ]
                
                await self.party_manager.handle_start(game_name, players_with_tomi, guild_id, self.config)
                
                # Verificar que se notificó
                self.assertEqual(mock_notify.call_count, 1, "Black Tomi debería generar notificación")
                first_call_message = mock_notify.call_args_list[0][0][0]
                self.assertIn('Black Tomi Returns', first_call_message)
                
                # Paso 3: Zamu se une (4to jugador)
                mock_notify.reset_mock()
                players_with_zamu = players_with_tomi + [
                    {'user_id': '444', 'username': 'Zamu'}
                ]
                
                await self.party_manager.handle_start(game_name, players_with_zamu, guild_id, self.config)
                
                # Verificar que se notificó
                self.assertEqual(mock_notify.call_count, 1, "Zamu debería generar notificación")
                second_call_message = mock_notify.call_args_list[0][0][0]
                self.assertIn('Zamu', second_call_message)
                
                # Paso 4: Zeta se une (5to jugador)
                mock_notify.reset_mock()
                players_with_zeta = players_with_zamu + [
                    {'user_id': '555', 'username': 'Zeta'}
                ]
                
                await self.party_manager.handle_start(game_name, players_with_zeta, guild_id, self.config)
                
                # Verificar que se notificó
                self.assertEqual(mock_notify.call_count, 1, "Zeta debería generar notificación")
                third_call_message = mock_notify.call_args_list[0][0][0]
                self.assertIn('Zeta', third_call_message)
                
                # Verificar que la party tiene 5 jugadores
                final_session = self.party_manager.active_sessions[game_name]
                self.assertEqual(len(final_session.player_ids), 5)
                self.assertEqual(final_session.max_players, 5)
    
    async def test_player_rejoin_respects_cooldown(self):
        """
        Test que verifica que si un jugador sale y vuelve a entrar,
        el cooldown POR JUGADOR evita spam de notificaciones.
        """
        game_name = "VALORANT"
        guild_id = 123
        
        # Party inicial
        initial_players = [
            {'user_id': '111', 'username': 'Player1'},
            {'user_id': '222', 'username': 'Player2'}
        ]
        
        with patch('core.party_session.send_notification', new_callable=AsyncMock) as mock_notify:
            with patch('core.party_session.check_cooldown', return_value=True):
                # Crear y confirmar party
                await self.party_manager.handle_start(game_name, initial_players, guild_id, self.config)
                session = self.party_manager.active_sessions[game_name]
                session.is_confirmed = True
                
                mock_notify.reset_mock()
                
                # Player3 se une por primera vez
                players_with_3 = initial_players + [
                    {'user_id': '333', 'username': 'Player3'}
                ]
                
                await self.party_manager.handle_start(game_name, players_with_3, guild_id, self.config)
                self.assertEqual(mock_notify.call_count, 1, "Primera vez debe notificar")
                
                # Player3 sale
                await self.party_manager.handle_start(game_name, initial_players, guild_id, self.config)
                
                mock_notify.reset_mock()
                
                # Player3 vuelve a entrar (dentro del cooldown)
                with patch('core.party_session.check_cooldown', return_value=False):  # Cooldown activo
                    await self.party_manager.handle_start(game_name, players_with_3, guild_id, self.config)
                    
                    # NO debería notificar porque está en cooldown
                    self.assertEqual(mock_notify.call_count, 0, "No debe notificar si está en cooldown")


if __name__ == '__main__':
    unittest.main()

