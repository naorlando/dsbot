"""
Tests para verificar los nuevos periodos configurados
"""

import unittest
from datetime import datetime, timedelta
from core.base_session import BaseSessionManager
from core.cooldown import check_cooldown, is_cooldown_passed
from core.persistence import stats, save_stats


class TestNewPeriods(unittest.TestCase):
    """Tests para los nuevos periodos del sistema"""
    
    def setUp(self):
        """Limpiar cooldowns antes de cada test"""
        stats['cooldowns'] = {}
        save_stats()
    
    def test_grace_period_5_minutes(self):
        """Verifica que el grace period sea 5 minutos (300 segundos)"""
        # Mock de BaseSessionManager
        class MockBot:
            pass
        
        manager = BaseSessionManager(MockBot())
        self.assertEqual(manager.grace_period_seconds, 300, "Grace period debe ser 300 segundos (5 min)")
    
    def test_cooldown_no_reset(self):
        """Verifica que el cooldown NO se reinicie en intentos intermedios"""
        user_id = 'test_user'
        event_key = 'game:LoL'
        
        # Primera notificación (exitosa)
        result1 = check_cooldown(user_id, event_key, cooldown_seconds=1800)  # 30 min
        self.assertTrue(result1, "Primera notificación debe pasar")
        
        # Guardar timestamp
        cooldown_key = f"{user_id}:{event_key}"
        first_timestamp = stats['cooldowns'][cooldown_key]
        
        # Intento 5 segundos después (debe fallar y NO actualizar timestamp)
        result2 = check_cooldown(user_id, event_key, cooldown_seconds=1800)
        self.assertFalse(result2, "Segunda notificación debe fallar (en cooldown)")
        
        # Verificar que el timestamp NO cambió
        second_timestamp = stats['cooldowns'][cooldown_key]
        self.assertEqual(first_timestamp, second_timestamp, "Timestamp NO debe cambiar durante cooldown")
    
    def test_cooldown_predictable(self):
        """Verifica que el cooldown sea predecible (basado en última notificación)"""
        user_id = 'test_user'
        event_key = 'game:CS2'
        
        # Primera notificación
        check_cooldown(user_id, event_key, cooldown_seconds=10)
        
        # Simular paso del tiempo modificando el timestamp manualmente
        cooldown_key = f"{user_id}:{event_key}"
        old_time = datetime.fromisoformat(stats['cooldowns'][cooldown_key])
        fake_old_time = old_time - timedelta(seconds=15)  # 15 segundos atrás
        stats['cooldowns'][cooldown_key] = fake_old_time.isoformat()
        save_stats()
        
        # Después de 15 segundos (>10s cooldown) debe permitir
        result = check_cooldown(user_id, event_key, cooldown_seconds=10)
        self.assertTrue(result, "Debe permitir notificación después de que expira cooldown")
    
    def test_is_cooldown_passed_no_update(self):
        """Verifica que is_cooldown_passed NO actualice el timestamp"""
        user_id = 'test_user'
        event_key = 'voice'
        
        # Establecer cooldown
        check_cooldown(user_id, event_key, cooldown_seconds=1800)
        cooldown_key = f"{user_id}:{event_key}"
        original_timestamp = stats['cooldowns'][cooldown_key]
        
        # Verificar estado (no debe actualizar)
        is_cooldown_passed(user_id, event_key, cooldown_seconds=1800)
        
        # Timestamp debe ser el mismo
        new_timestamp = stats['cooldowns'][cooldown_key]
        self.assertEqual(original_timestamp, new_timestamp, "is_cooldown_passed NO debe actualizar timestamp")
    
    def test_party_cooldown_per_player(self):
        """Verifica que el cooldown de party sea por jugador individual"""
        game_name = 'League of Legends'
        player1_id = 'player1'
        player2_id = 'player2'
        
        # Player1 notifica
        result1 = check_cooldown(player1_id, f'game:{game_name}', cooldown_seconds=1800)
        self.assertTrue(result1, "Player1 debe poder notificar")
        
        # Player2 notifica (diferente jugador, debe pasar)
        result2 = check_cooldown(player2_id, f'game:{game_name}', cooldown_seconds=1800)
        self.assertTrue(result2, "Player2 debe poder notificar (cooldown es por jugador)")
        
        # Player1 intenta de nuevo (debe fallar)
        result3 = check_cooldown(player1_id, f'game:{game_name}', cooldown_seconds=1800)
        self.assertFalse(result3, "Player1 debe estar en cooldown")
        
        # Player2 intenta de nuevo (debe fallar)
        result4 = check_cooldown(player2_id, f'game:{game_name}', cooldown_seconds=1800)
        self.assertFalse(result4, "Player2 debe estar en cooldown")


if __name__ == '__main__':
    unittest.main()

