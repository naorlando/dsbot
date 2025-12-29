"""
Tests para el sistema de Health Check
"""

import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import discord

from core.health_check import SessionHealthCheck
from core.voice_session import VoiceSession, VoiceSessionManager
from core.game_session import GameSession, GameSessionManager
from core.party_session import PartySession, PartySessionManager


class TestHealthCheckActivation(unittest.TestCase):
    """Tests para activación/desactivación dinámica del health check"""
    
    def setUp(self):
        """Setup común para todos los tests"""
        self.bot = Mock()
        self.voice_manager = Mock()
        self.voice_manager.active_sessions = {}
        self.game_manager = Mock()
        self.game_manager.active_sessions = {}
        self.party_manager = Mock()
        self.party_manager.active_sessions = {}
        
        self.health_check = SessionHealthCheck(
            bot=self.bot,
            voice_manager=self.voice_manager,
            game_manager=self.game_manager,
            party_manager=self.party_manager
        )
    
    def test_health_check_initialization(self):
        """Test que el health check se inicializa correctamente"""
        self.assertIsNotNone(self.health_check)
        self.assertFalse(self.health_check._task_running)
        self.assertEqual(len(self.voice_manager.active_sessions), 0)
    
    def test_has_active_sessions_empty(self):
        """Test que detecta cuando NO hay sesiones activas"""
        self.assertFalse(self.health_check._has_active_sessions())
    
    def test_has_active_sessions_voice(self):
        """Test que detecta sesiones de voz activas"""
        self.voice_manager.active_sessions = {'123': Mock()}
        self.assertTrue(self.health_check._has_active_sessions())
    
    def test_has_active_sessions_game(self):
        """Test que detecta sesiones de juegos activas"""
        self.game_manager.active_sessions = {'456': Mock()}
        self.assertTrue(self.health_check._has_active_sessions())
    
    def test_has_active_sessions_party(self):
        """Test que detecta sesiones de parties activas"""
        self.party_manager.active_sessions = {'VALORANT': Mock()}
        self.assertTrue(self.health_check._has_active_sessions())
    
    def test_start_if_needed_with_sessions(self):
        """Test que inicia el health check cuando hay sesiones"""
        self.voice_manager.active_sessions = {'123': Mock()}
        
        # Mock del task
        self.health_check.health_check_task = Mock()
        self.health_check.health_check_task.start = Mock()
        
        self.health_check.start_if_needed()
        
        self.health_check.health_check_task.start.assert_called_once()
        self.assertTrue(self.health_check._task_running)
    
    def test_start_if_needed_without_sessions(self):
        """Test que NO inicia el health check sin sesiones"""
        # Sin sesiones activas
        self.health_check.health_check_task = Mock()
        self.health_check.health_check_task.start = Mock()
        
        self.health_check.start_if_needed()
        
        self.health_check.health_check_task.start.assert_not_called()
        self.assertFalse(self.health_check._task_running)
    
    def test_stop_if_empty_with_sessions(self):
        """Test que NO detiene el health check si hay sesiones"""
        self.voice_manager.active_sessions = {'123': Mock()}
        self.health_check._task_running = True
        self.health_check.health_check_task = Mock()
        self.health_check.health_check_task.cancel = Mock()
        
        self.health_check.stop_if_empty()
        
        self.health_check.health_check_task.cancel.assert_not_called()
        self.assertTrue(self.health_check._task_running)
    
    def test_stop_if_empty_without_sessions(self):
        """Test que detiene el health check sin sesiones"""
        # Sin sesiones activas
        self.health_check._task_running = True
        self.health_check.health_check_task = Mock()
        self.health_check.health_check_task.cancel = Mock()
        
        self.health_check.stop_if_empty()
        
        self.health_check.health_check_task.cancel.assert_called_once()
        self.assertFalse(self.health_check._task_running)


class TestHealthCheckVoiceValidation(unittest.IsolatedAsyncioTestCase):
    """Tests para validación de sesiones de voz"""
    
    async def asyncSetUp(self):
        """Setup asíncrono para tests"""
        self.bot = Mock()
        self.voice_manager = Mock()
        self.voice_manager.active_sessions = {}
        self.game_manager = Mock()
        self.game_manager.active_sessions = {}
        self.party_manager = Mock()
        self.party_manager.active_sessions = {}
        
        self.health_check = SessionHealthCheck(
            bot=self.bot,
            voice_manager=self.voice_manager,
            game_manager=self.game_manager,
            party_manager=self.party_manager
        )
    
    async def test_check_voice_sessions_no_sessions(self):
        """Test validación sin sesiones activas"""
        fixed = await self.health_check._check_voice_sessions()
        self.assertEqual(fixed, 0)
    
    async def test_check_voice_sessions_user_still_in_voice(self):
        """Test que NO corrige sesión válida"""
        # Crear sesión
        session = Mock()
        session.guild_id = 123
        session.username = "TestUser"
        session.channel_id = 456
        session.is_confirmed = True
        session.duration_seconds = Mock(return_value=120)
        
        self.voice_manager.active_sessions = {'789': session}
        
        # Mock guild y member
        guild = Mock()
        member = Mock()
        member.voice = Mock()
        member.voice.channel = Mock()
        member.voice.channel.id = 456  # Mismo canal
        
        guild.get_member = Mock(return_value=member)
        self.bot.get_guild = Mock(return_value=guild)
        
        fixed = await self.health_check._check_voice_sessions()
        
        # No debería corregir nada
        self.assertEqual(fixed, 0)
        self.assertIn('789', self.voice_manager.active_sessions)
    
    async def test_check_voice_sessions_user_left(self):
        """Test que corrige sesión cuando usuario salió"""
        # Crear sesión
        session = Mock()
        session.guild_id = 123
        session.username = "TestUser"
        session.channel_id = 456
        session.is_confirmed = True
        session.duration_seconds = Mock(return_value=120)
        session.verification_task = None
        
        self.voice_manager.active_sessions = {'789': session}
        
        # Mock guild y member sin voz
        guild = Mock()
        member = Mock()
        member.voice = None  # Usuario NO está en voz
        
        guild.get_member = Mock(return_value=member)
        self.bot.get_guild = Mock(return_value=guild)
        
        fixed = await self.health_check._check_voice_sessions()
        
        # Debería corregir 1 sesión
        self.assertEqual(fixed, 1)
        # Sesión debería ser eliminada
        self.assertNotIn('789', self.voice_manager.active_sessions)


class TestHealthCheckGameValidation(unittest.IsolatedAsyncioTestCase):
    """Tests para validación de sesiones de juegos"""
    
    async def asyncSetUp(self):
        """Setup asíncrono para tests"""
        self.bot = Mock()
        self.voice_manager = Mock()
        self.voice_manager.active_sessions = {}
        self.game_manager = Mock()
        self.game_manager.active_sessions = {}
        self.party_manager = Mock()
        self.party_manager.active_sessions = {}
        
        self.health_check = SessionHealthCheck(
            bot=self.bot,
            voice_manager=self.voice_manager,
            game_manager=self.game_manager,
            party_manager=self.party_manager
        )
    
    async def test_check_game_sessions_no_sessions(self):
        """Test validación sin sesiones de juegos"""
        fixed = await self.health_check._check_game_sessions()
        self.assertEqual(fixed, 0)
    
    async def test_check_game_sessions_user_still_playing(self):
        """Test que NO corrige sesión de juego válida"""
        # Crear sesión
        session = Mock()
        session.guild_id = 123
        session.username = "TestUser"
        session.game_name = "VALORANT"
        session.is_confirmed = True
        
        self.game_manager.active_sessions = {'789': session}
        
        # Mock guild y member con actividad
        guild = Mock()
        member = Mock()
        
        # Crear actividad con el mismo juego
        activity = Mock()
        activity.name = "VALORANT"
        member.activities = [activity]
        
        guild.get_member = Mock(return_value=member)
        self.bot.get_guild = Mock(return_value=guild)
        
        fixed = await self.health_check._check_game_sessions()
        
        # No debería corregir nada
        self.assertEqual(fixed, 0)
        self.assertIn('789', self.game_manager.active_sessions)
    
    async def test_check_game_sessions_user_stopped_playing(self):
        """Test que corrige sesión cuando usuario dejó de jugar"""
        # Crear sesión
        session = Mock()
        session.guild_id = 123
        session.username = "TestUser"
        session.game_name = "VALORANT"
        session.is_confirmed = True
        session.duration_seconds = Mock(return_value=300)
        session.verification_task = None
        
        self.game_manager.active_sessions = {'789': session}
        
        # Mock guild y member sin ese juego
        guild = Mock()
        member = Mock()
        member.activities = []  # Sin actividades
        
        guild.get_member = Mock(return_value=member)
        self.bot.get_guild = Mock(return_value=guild)
        
        fixed = await self.health_check._check_game_sessions()
        
        # Debería corregir 1 sesión
        self.assertEqual(fixed, 1)
        # Sesión debería ser eliminada
        self.assertNotIn('789', self.game_manager.active_sessions)


class TestHealthCheckPartyValidation(unittest.IsolatedAsyncioTestCase):
    """Tests para validación de sesiones de parties"""
    
    async def asyncSetUp(self):
        """Setup asíncrono para tests"""
        self.bot = Mock()
        self.voice_manager = Mock()
        self.voice_manager.active_sessions = {}
        self.game_manager = Mock()
        self.game_manager.active_sessions = {}
        self.party_manager = Mock()
        self.party_manager.active_sessions = {}
        self.party_manager.handle_end = AsyncMock()
        
        self.health_check = SessionHealthCheck(
            bot=self.bot,
            voice_manager=self.voice_manager,
            game_manager=self.game_manager,
            party_manager=self.party_manager
        )
    
    async def test_check_party_sessions_no_sessions(self):
        """Test validación sin parties activas"""
        fixed = await self.health_check._check_party_sessions()
        self.assertEqual(fixed, 0)
    
    async def test_check_party_sessions_valid_party(self):
        """Test que NO corrige party válida"""
        # Crear party session
        session = Mock()
        session.guild_id = 123
        session.player_ids = {'111', '222', '333'}
        
        self.party_manager.active_sessions = {'VALORANT': session}
        
        # Mock guild con 3 jugadores activos
        guild = Mock()
        
        # Crear 3 members jugando VALORANT
        members = []
        for player_id in ['111', '222', '333']:
            member = Mock()
            activity = Mock()
            activity.name = "VALORANT"
            member.activities = [activity]
            members.append(member)
        
        guild.get_member = Mock(side_effect=members)
        self.bot.get_guild = Mock(return_value=guild)
        
        fixed = await self.health_check._check_party_sessions()
        
        # No debería corregir nada
        self.assertEqual(fixed, 0)
        self.assertIn('VALORANT', self.party_manager.active_sessions)
    
    async def test_check_party_sessions_not_enough_players(self):
        """Test que corrige party con menos de 2 jugadores"""
        # Crear party session
        session = Mock()
        session.guild_id = 123
        session.player_ids = {'111', '222'}
        
        self.party_manager.active_sessions = {'VALORANT': session}
        
        # Mock guild con solo 1 jugador activo
        guild = Mock()
        
        # Solo 1 member jugando
        member1 = Mock()
        activity = Mock()
        activity.name = "VALORANT"
        member1.activities = [activity]
        
        member2 = Mock()
        member2.activities = []  # No está jugando
        
        guild.get_member = Mock(side_effect=[member1, member2])
        self.bot.get_guild = Mock(return_value=guild)
        
        fixed = await self.health_check._check_party_sessions()
        
        # Debería corregir 1 party
        self.assertEqual(fixed, 1)
        # handle_end debería ser llamado
        self.party_manager.handle_end.assert_called_once_with('VALORANT', {})


if __name__ == '__main__':
    unittest.main()

