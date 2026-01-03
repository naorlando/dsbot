"""
Tests para el sistema de tracking de app_ids con verificación por contador
Verifica detección de app_ids FAKE usando threshold de 3 usos
"""

import unittest
from core.app_id_tracker import (
    track_app_id, get_real_app_id, is_app_id_fake,
    get_fake_game_name, get_game_stats, clear_tracker,
    VERIFICATION_THRESHOLD
)


class TestAppIdTrackingV2(unittest.TestCase):
    """Tests para el tracker de app_ids con sistema de verificación"""
    
    def setUp(self):
        """Limpiar tracker antes de cada test"""
        clear_tracker()
    
    def tearDown(self):
        """Limpiar tracker después de cada test"""
        clear_tracker()
    
    def test_track_first_app_id(self):
        """Test 1: Primer app_id se trackea como pendiente"""
        result = track_app_id("League of Legends", 401518684763586560)
        self.assertTrue(result)
        
        # Todavía no está verificado (solo 1 uso)
        verified = get_real_app_id("League of Legends")
        self.assertIsNone(verified)
    
    def test_track_reaches_verification(self):
        """Test 2: Al llegar a 3 usos, se verifica"""
        # Uso 1
        track_app_id("VALORANT", 700)
        self.assertIsNone(get_real_app_id("VALORANT"))
        
        # Uso 2
        track_app_id("VALORANT", 700)
        self.assertIsNone(get_real_app_id("VALORANT"))
        
        # Uso 3 → VERIFICADO
        track_app_id("VALORANT", 700)
        self.assertEqual(get_real_app_id("VALORANT"), "700")
    
    def test_fake_rejected_after_verification(self):
        """Test 3: Después de verificar, fakes son rechazados"""
        # Verificar app_id real (3 usos)
        for _ in range(3):
            track_app_id("Dota 2", 570)
        
        self.assertEqual(get_real_app_id("Dota 2"), "570")
        
        # Intentar fake → rechazado
        result = track_app_id("Dota 2", 999)
        self.assertFalse(result)
    
    def test_multiple_app_ids_before_verification(self):
        """Test 4: Antes de verificar, múltiples app_ids son aceptados"""
        # 2 personas con app_id A
        track_app_id("New Game", 12345)
        track_app_id("New Game", 12345)
        
        # 1 persona con app_id B (fake)
        result = track_app_id("New Game", 99999)
        self.assertTrue(result)  # Aceptado (aún no verificado)
        
        # App_id A llega a 3 → se verifica
        track_app_id("New Game", 12345)
        self.assertEqual(get_real_app_id("New Game"), "12345")
        
        # Ahora el fake B es rechazado
        result_fake = track_app_id("New Game", 99999)
        self.assertFalse(result_fake)
    
    def test_is_app_id_fake_before_verification(self):
        """Test 5: Antes de verificar, nada es fake"""
        track_app_id("CS2", 730)
        
        # No está verificado, así que no es fake
        self.assertFalse(is_app_id_fake("CS2", 730))
        self.assertFalse(is_app_id_fake("CS2", 999))
    
    def test_is_app_id_fake_after_verification(self):
        """Test 6: Después de verificar, detecta fakes"""
        # Verificar
        for _ in range(3):
            track_app_id("Fortnite", 432980)
        
        # Real NO es fake
        self.assertFalse(is_app_id_fake("Fortnite", 432980))
        
        # Fake SÍ es fake
        self.assertTrue(is_app_id_fake("Fortnite", 999))
    
    def test_is_app_id_fake_no_app_id(self):
        """Test 7: Sin app_id siempre es fake"""
        self.assertTrue(is_app_id_fake("Any Game", None))
    
    def test_get_fake_game_name(self):
        """Test 8: get_fake_game_name agrega sufijo"""
        fake_name = get_fake_game_name("Minecraft")
        self.assertEqual(fake_name, "Minecraft (Fake)")
    
    def test_get_game_stats_shows_counts(self):
        """Test 9: get_game_stats muestra contadores"""
        track_app_id("Apex", 1172470)
        track_app_id("Apex", 1172470)
        track_app_id("Apex", 999)
        
        stats = get_game_stats("Apex")
        
        self.assertIn("counts", stats)
        self.assertEqual(stats["counts"]["1172470"], 2)
        self.assertEqual(stats["counts"]["999"], 1)
        self.assertFalse(stats["is_verified"])
        self.assertIsNone(stats["verified"])
    
    def test_get_game_stats_after_verification(self):
        """Test 10: get_game_stats después de verificación"""
        for _ in range(3):
            track_app_id("GTA V", 271590)
        
        stats = get_game_stats("GTA V")
        
        self.assertTrue(stats["is_verified"])
        self.assertEqual(stats["verified"], "271590")
        self.assertEqual(stats["counts"]["271590"], 3)
    
    def test_verification_threshold_is_3(self):
        """Test 11: Threshold es 3"""
        self.assertEqual(VERIFICATION_THRESHOLD, 3)
    
    def test_race_condition_scenario(self):
        """Test 12: Escenario de race condition con fake y real"""
        # Fake aparece 2 veces primero
        track_app_id("LOL", 999)
        track_app_id("LOL", 999)
        
        # Real aparece 3 veces → gana
        track_app_id("LOL", 401518684763586560)
        track_app_id("LOL", 401518684763586560)
        track_app_id("LOL", 401518684763586560)
        
        # El real se verificó
        self.assertEqual(get_real_app_id("LOL"), "401518684763586560")
        
        # El fake ahora es rechazado
        result = track_app_id("LOL", 999)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
