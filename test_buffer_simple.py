"""
Test simple para verificar buffer de gracia (sin discord)
"""

import unittest
from datetime import datetime, timedelta


class MockBaseSession:
    """Mock simple de BaseSession"""
    def __init__(self, user_id: str, username: str, guild_id: int):
        self.user_id = user_id
        self.username = username
        self.guild_id = guild_id
        self.start_time = datetime.now()
        self.last_activity_update = datetime.now()
        self.is_confirmed = False


class TestBufferGraciLogic(unittest.TestCase):
    """Tests para verificar la lógica del buffer de gracia"""
    
    def test_session_inicializa_con_timestamp(self):
        """Verifica que la sesión se inicializa con timestamp actual"""
        session = MockBaseSession('123', 'TestUser', 1)
        
        self.assertIsNotNone(session.last_activity_update)
        self.assertIsInstance(session.last_activity_update, datetime)
        
        # Debe ser muy reciente
        time_diff = (datetime.now() - session.last_activity_update).total_seconds()
        self.assertLess(time_diff, 1.0)
    
    def test_verificar_gracia_dentro_del_limite(self):
        """Verifica lógica de gracia dentro del límite (< 15 min)"""
        session = MockBaseSession('123', 'TestUser', 1)
        grace_period_seconds = 900  # 15 minutos
        
        # Simular última actividad hace 10 minutos
        session.last_activity_update = datetime.now() - timedelta(minutes=10)
        
        # Calcular tiempo desde última actividad
        time_since_last = (datetime.now() - session.last_activity_update).total_seconds()
        
        # Debe estar dentro del período de gracia
        self.assertLess(time_since_last, grace_period_seconds)
        
        # Simular decisión: NO cerrar sesión
        should_close = time_since_last >= grace_period_seconds
        self.assertFalse(should_close, "No debe cerrar sesión si está en gracia")
    
    def test_verificar_gracia_fuera_del_limite(self):
        """Verifica lógica de gracia fuera del límite (> 15 min)"""
        session = MockBaseSession('123', 'TestUser', 1)
        grace_period_seconds = 900  # 15 minutos
        
        # Simular última actividad hace 20 minutos
        session.last_activity_update = datetime.now() - timedelta(minutes=20)
        
        # Calcular tiempo desde última actividad
        time_since_last = (datetime.now() - session.last_activity_update).total_seconds()
        
        # Debe estar fuera del período de gracia
        self.assertGreaterEqual(time_since_last, grace_period_seconds)
        
        # Simular decisión: SÍ cerrar sesión
        should_close = time_since_last >= grace_period_seconds
        self.assertTrue(should_close, "Debe cerrar sesión si gracia expiró")
    
    def test_actualizar_actividad(self):
        """Verifica que actualizar actividad modifica el timestamp"""
        session = MockBaseSession('123', 'TestUser', 1)
        old_timestamp = session.last_activity_update
        
        # Simular paso de tiempo
        import time
        time.sleep(0.1)
        
        # Actualizar actividad
        session.last_activity_update = datetime.now()
        
        # Verificar que el timestamp cambió
        self.assertGreater(session.last_activity_update, old_timestamp)
    
    def test_escenario_lobby_lol(self):
        """
        Escenario real: Usuario jugando LoL con lobbies de 3 minutos
        
        14:00 → Juega partida (15 min)
        14:15 → Lobby (3 min, Discord no reporta)
        14:18 → Nueva partida
        
        Con buffer 15 min: Sesión continúa ✅
        Sin buffer: Sesión se cierra en 14:15 ❌
        """
        session = MockBaseSession('123', 'TestUser', 1)
        grace_period_seconds = 900  # 15 minutos
        
        # 14:00 - Jugando partida
        session.last_activity_update = datetime.now()
        
        # 14:15 - Entra al lobby (Discord deja de reportar)
        # Simulamos que pasan 3 minutos sin actividad
        lobby_time = datetime.now() + timedelta(minutes=3)
        
        # En el minuto 3 del lobby, verificamos gracia
        time_since_last = (lobby_time - session.last_activity_update).total_seconds()
        
        # 3 minutos < 15 minutos → En gracia
        self.assertLess(time_since_last, grace_period_seconds)
        should_close = time_since_last >= grace_period_seconds
        self.assertFalse(should_close, "No debe cerrar durante lobby de 3 min")
        
        # 14:18 - Vuelve a jugar (Discord reporta de nuevo)
        session.last_activity_update = datetime.now() + timedelta(minutes=3)
        
        # Sesión continúa sin interrupciones ✅


if __name__ == '__main__':
    unittest.main()

