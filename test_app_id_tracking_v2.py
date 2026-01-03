"""
Tests para el sistema de tracking de app_ids (versión simplificada)
Verifica detección de app_ids FAKE y tracking de reales
Solo guarda UN app_id por juego (el real)
"""

import unittest
from core.app_id_tracker import (
    track_app_id, get_real_app_id, is_app_id_fake,
    get_fake_game_name, get_game_stats, clear_tracker,
    is_game_in_whitelist, KNOWN_GAMES
)


class TestAppIdTrackingV2(unittest.TestCase):
    """Tests para el tracker de app_ids (versión simplificada)"""
    
    def setUp(self):
        """Limpiar tracker antes de cada test"""
        clear_tracker()
    
    def tearDown(self):
        """Limpiar tracker después de cada test"""
        clear_tracker()
    
    def test_track_first_app_id(self):
        """Test 1: Primer app_id para un juego se guarda como real"""
        result = track_app_id("League of Legends", 401518684763586560)
        self.assertTrue(result)
        
        real_app_id = get_real_app_id("League of Legends")
        self.assertEqual(real_app_id, "401518684763586560")
    
    def test_track_same_app_id_twice(self):
        """Test 2: Trackear el mismo app_id dos veces funciona"""
        track_app_id("VALORANT", 700)
        result = track_app_id("VALORANT", 700)
        
        self.assertTrue(result)
        self.assertEqual(get_real_app_id("VALORANT"), "700")
    
    def test_track_different_app_id_is_fake(self):
        """Test 3: Segundo app_id diferente es rechazado (fake)"""
        # Trackear app_id real
        track_app_id("League of Legends", 401518684763586560)
        
        # Intentar trackear app_id fake
        result = track_app_id("League of Legends", 1402418696126992445)
        
        self.assertFalse(result)  # No se trackea
        self.assertEqual(get_real_app_id("League of Legends"), "401518684763586560")  # Sigue siendo el real
    
    def test_is_app_id_fake_when_different(self):
        """Test 4: is_app_id_fake detecta fakes correctamente"""
        # Trackear real
        track_app_id("Dota 2", 570)
        
        # Verificar que el real NO es fake
        self.assertFalse(is_app_id_fake("Dota 2", 570))
        
        # Verificar que otro app_id SÍ es fake
        self.assertTrue(is_app_id_fake("Dota 2", 999))
    
    def test_is_app_id_fake_no_tracker(self):
        """Test 5: Si no hay tracker, no es fake (beneficio de la duda)"""
        is_fake = is_app_id_fake("New Game", 12345)
        self.assertFalse(is_fake)
    
    def test_is_app_id_fake_no_app_id(self):
        """Test 6: Sin app_id siempre es fake"""
        self.assertTrue(is_app_id_fake("Any Game", None))
    
    def test_get_fake_game_name(self):
        """Test 7: get_fake_game_name agrega sufijo"""
        fake_name = get_fake_game_name("Fortnite")
        self.assertEqual(fake_name, "Fortnite (Fake)")
    
    def test_whitelist_verification(self):
        """Test 8: Whitelist funciona correctamente"""
        # LoL está en whitelist
        self.assertTrue(is_game_in_whitelist("League of Legends", 401518684763586560))
        
        # LoL con app_id incorrecto NO está en whitelist
        self.assertFalse(is_game_in_whitelist("League of Legends", 999))
        
        # Juego no en whitelist
        self.assertFalse(is_game_in_whitelist("Unknown Game", 123))
    
    def test_whitelist_games_loaded(self):
        """Test 9: Whitelist tiene juegos populares"""
        self.assertIn("League of Legends", KNOWN_GAMES)
        self.assertIn("Counter-Strike 2", KNOWN_GAMES)
        self.assertIn("Dota 2", KNOWN_GAMES)
        self.assertGreater(len(KNOWN_GAMES), 10)
    
    def test_track_game_in_whitelist(self):
        """Test 10: Juego en whitelist se trackea y logea correctamente"""
        result = track_app_id("Counter-Strike 2", 730)
        self.assertTrue(result)
        self.assertEqual(get_real_app_id("Counter-Strike 2"), "730")
    
    def test_get_game_stats(self):
        """Test 11: get_game_stats retorna app_id trackeado"""
        track_app_id("Apex Legends", 1172470)
        stats = get_game_stats("Apex Legends")
        
        self.assertIn("app_id", stats)
        self.assertEqual(stats["app_id"], "1172470")
    
    def test_get_game_stats_no_data(self):
        """Test 12: get_game_stats retorna dict vacío si no hay datos"""
        stats = get_game_stats("Non Existent Game")
        self.assertEqual(stats, {})


if __name__ == '__main__':
    unittest.main()

