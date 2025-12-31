"""
Tests para el Health Check Periódico
Verifica que sesiones con grace period expirado se finalicen correctamente
"""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
import asyncio


class TestHealthCheckPeriodic(unittest.TestCase):
    """Tests para el health check periódico"""
    
    def setUp(self):
        """Setup común para todos los tests"""
        # Mock del bot
        self.bot = MagicMock()
        self.bot.guilds = []
        
        # Mock de config
        self.config = {
            'notify_games': True,
            'game_min_duration_seconds': 10
        }
    
    @patch('core.health_check.GameSessionManager')
    @patch('core.health_check.VoiceSessionManager')
    @patch('core.health_check.PartySessionManager')
    def test_health_check_initialization(self, mock_party, mock_voice, mock_game):
        """Test inicialización del health check con managers"""
        from core.health_check import SessionHealthCheck
        
        voice_manager = mock_voice.return_value
        game_manager = mock_game.return_value
        party_manager = mock_party.return_value
        
        health_check = SessionHealthCheck(
            bot=self.bot,
            voice_manager=voice_manager,
            game_manager=game_manager,
            party_manager=party_manager,
            config=self.config
        )
        
        self.assertIsNotNone(health_check)
        self.assertEqual(health_check.bot, self.bot)
        self.assertEqual(health_check.game_manager, game_manager)
        self.assertEqual(health_check.party_manager, party_manager)
    
    def test_expired_session_detection(self):
        """Test detección de sesiones expiradas"""
        from core.base_session import BaseSession
        
        # Crear sesión con actividad hace 20 minutos (> 15 min grace period)
        session = BaseSession(
            user_id="123",
            username="TestUser",
            guild_id=456
        )
        session.last_activity_update = datetime.now() - timedelta(minutes=20)
        
        # Calcular tiempo desde última actividad
        time_since_activity = (datetime.now() - session.last_activity_update).total_seconds()
        
        # Debería estar expirada (> 900 segundos = 15 min)
        self.assertGreater(time_since_activity, 900)
    
    def test_non_expired_session_detection(self):
        """Test que sesiones recientes NO se detecten como expiradas"""
        from core.base_session import BaseSession
        
        # Crear sesión con actividad hace 5 minutos (< 15 min grace period)
        session = BaseSession(
            user_id="123",
            username="TestUser",
            guild_id=456
        )
        session.last_activity_update = datetime.now() - timedelta(minutes=5)
        
        # Calcular tiempo desde última actividad
        time_since_activity = (datetime.now() - session.last_activity_update).total_seconds()
        
        # NO debería estar expirada (< 900 segundos = 15 min)
        self.assertLess(time_since_activity, 900)
    
    @patch('core.health_check.logger')
    async def async_test_check_game_sessions(self, mock_logger):
        """Test revisión de sesiones de juego expiradas"""
        from core.health_check import SessionHealthCheck
        from core.game_session import GameSession, GameSessionManager
        
        # Mock managers
        voice_manager = MagicMock()
        game_manager = MagicMock(spec=GameSessionManager)
        party_manager = MagicMock()
        
        # Crear sesión expirada
        old_session = GameSession(
            user_id="123",
            username="TestUser",
            game_name="TestGame",
            app_id=None,
            activity_type="playing",
            guild_id=456
        )
        old_session.last_activity_update = datetime.now() - timedelta(minutes=20)
        old_session.is_confirmed = True
        
        # Agregar al manager
        game_manager.active_sessions = {"123": old_session}
        game_manager.handle_game_end = AsyncMock()
        
        # Mock de guild y member
        mock_guild = MagicMock()
        mock_member = MagicMock()
        mock_member.id = 123
        mock_guild.get_member.return_value = mock_member
        self.bot.get_guild.return_value = mock_guild
        
        # Crear health check
        health_check = SessionHealthCheck(
            bot=self.bot,
            voice_manager=voice_manager,
            game_manager=game_manager,
            party_manager=party_manager,
            config=self.config
        )
        
        # Ejecutar check
        finalized = await health_check._check_game_sessions()
        
        # Verificar que finalizó la sesión
        self.assertEqual(finalized, 1)
        game_manager.handle_game_end.assert_called_once()
    
    def test_check_game_sessions(self):
        """Wrapper síncrono para test asíncrono"""
        asyncio.run(self.async_test_check_game_sessions())
    
    @patch('core.health_check.logger')
    async def async_test_check_party_sessions(self, mock_logger):
        """Test revisión de party sessions expiradas"""
        from core.health_check import SessionHealthCheck
        from core.party_session import PartySession, PartySessionManager
        
        # Mock managers
        voice_manager = MagicMock()
        game_manager = MagicMock()
        party_manager = MagicMock(spec=PartySessionManager)
        
        # Crear party expirada
        old_party = PartySession(
            game_name="TestGame",
            player_ids={"123", "456"},
            player_names=["User1", "User2"],
            guild_id=789
        )
        old_party.last_activity_update = datetime.now() - timedelta(minutes=20)
        old_party.state = 'active'
        old_party.is_confirmed = True
        
        # Agregar al manager
        party_manager.active_sessions = {"TestGame": old_party}
        party_manager.handle_end = AsyncMock()
        
        # Crear health check
        health_check = SessionHealthCheck(
            bot=self.bot,
            voice_manager=voice_manager,
            game_manager=game_manager,
            party_manager=party_manager,
            config=self.config
        )
        
        # Ejecutar check
        finalized = await health_check._check_party_sessions()
        
        # Verificar que marcó como inactiva
        self.assertEqual(finalized, 1)
        party_manager.handle_end.assert_called_once()
    
    def test_check_party_sessions(self):
        """Wrapper síncrono para test asíncrono"""
        asyncio.run(self.async_test_check_party_sessions())
    
    def test_grace_period_threshold(self):
        """Test del threshold del grace period (15 minutos = 900 segundos)"""
        grace_period_seconds = 900
        
        # Justo en el límite (14:59)
        time_at_limit = 899
        self.assertLess(time_at_limit, grace_period_seconds)
        
        # Apenas excedido (15:01)
        time_exceeded = 901
        self.assertGreater(time_exceeded, grace_period_seconds)
        
        # Muy excedido (20 minutos)
        time_way_exceeded = 1200
        self.assertGreater(time_way_exceeded, grace_period_seconds)


class TestHealthCheckRecovery(unittest.TestCase):
    """Tests para la recuperación en on_ready"""
    
    @patch('core.health_check.logger')
    async def async_test_recovery_only_once(self, mock_logger):
        """Test que recovery solo se ejecuta una vez"""
        from core.health_check import SessionHealthCheck
        
        bot = MagicMock()
        voice_manager = MagicMock()
        game_manager = MagicMock()
        party_manager = MagicMock()
        config = {}
        
        health_check = SessionHealthCheck(
            bot=bot,
            voice_manager=voice_manager,
            game_manager=game_manager,
            party_manager=party_manager,
            config=config
        )
        
        # Mock del método de recovery
        health_check._recover_voice_sessions = AsyncMock()
        
        # Ejecutar recovery dos veces
        await health_check.recover_on_startup()
        await health_check.recover_on_startup()
        
        # Verificar que solo se ejecutó una vez
        self.assertEqual(health_check._recover_voice_sessions.call_count, 1)
        self.assertTrue(health_check._recovery_done)
    
    def test_recovery_only_once(self):
        """Wrapper síncrono"""
        asyncio.run(self.async_test_recovery_only_once())


if __name__ == '__main__':
    # Ejecutar tests
    unittest.main(verbosity=2)

