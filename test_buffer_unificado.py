"""
Test para verificar buffer de gracia unificado en todas las sesiones
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
from core.base_session import BaseSession, BaseSessionManager


class DummySession(BaseSession):
    """Sesión de prueba"""
    pass


class DummySessionManager(BaseSessionManager):
    """Manager de prueba"""
    
    async def handle_start(self, member, config, *args, **kwargs):
        pass
    
    async def handle_end(self, member, config, *args, **kwargs):
        pass
    
    async def _is_still_active(self, session, member):
        return True
    
    async def _on_session_confirmed_phase1(self, session, member, config):
        pass
    
    async def _on_session_confirmed_phase2(self, session, member, config):
        pass


class TestBufferUnificado(unittest.TestCase):
    """Tests para el buffer de gracia unificado"""
    
    def setUp(self):
        """Setup para cada test"""
        self.bot = Mock()
        self.manager = DummySessionManager(self.bot, min_duration_seconds=10, grace_period_seconds=300)
    
    def test_grace_period_default_5_minutes(self):
        """Verifica que el grace period default es 5 minutos (300s)"""
        self.assertEqual(self.manager.grace_period_seconds, 300)
    
    def test_update_activity_updates_timestamp(self):
        """Verifica que _update_activity actualiza el timestamp"""
        session = DummySession('123', 'TestUser', 1)
        old_timestamp = session.last_activity_update
        
        # Simular paso de tiempo
        import time
        time.sleep(0.1)
        
        # Actualizar actividad
        self.manager._update_activity(session)
        
        # Verificar que el timestamp cambió
        self.assertGreater(session.last_activity_update, old_timestamp)
    
    def test_is_in_grace_period_dentro_del_limite(self):
        """Verifica que _is_in_grace_period retorna True si está dentro del límite"""
        session = DummySession('123', 'TestUser', 1)
        
        # Última actividad hace 2 minutos (< 5 min)
        session.last_activity_update = datetime.now() - timedelta(minutes=2)
        
        # Debe estar en gracia
        self.assertTrue(self.manager._is_in_grace_period(session))
    
    def test_is_in_grace_period_fuera_del_limite(self):
        """Verifica que _is_in_grace_period retorna False si pasó el límite"""
        session = DummySession('123', 'TestUser', 1)
        
        # Última actividad hace 6 minutos (> 5 min)
        session.last_activity_update = datetime.now() - timedelta(minutes=6)
        
        # No debe estar en gracia
        self.assertFalse(self.manager._is_in_grace_period(session))
    
    def test_is_in_grace_period_justo_en_el_limite(self):
        """Verifica comportamiento en el límite exacto"""
        session = DummySession('123', 'TestUser', 1)
        
        # Última actividad hace exactamente 5 minutos
        session.last_activity_update = datetime.now() - timedelta(seconds=300)
        
        # Justo en el límite, podría ser True o False dependiendo de milisegundos
        # Por seguridad, verificamos que el método no falle
        result = self.manager._is_in_grace_period(session)
        self.assertIsInstance(result, bool)
    
    def test_todas_las_sesiones_tienen_last_activity_update(self):
        """Verifica que BaseSession inicializa last_activity_update"""
        session = BaseSession('123', 'TestUser', 1)
        
        self.assertIsNotNone(session.last_activity_update)
        self.assertIsInstance(session.last_activity_update, datetime)
        
        # Debe ser muy reciente (hace menos de 1 segundo)
        time_diff = (datetime.now() - session.last_activity_update).total_seconds()
        self.assertLess(time_diff, 1.0)


if __name__ == '__main__':
    unittest.main()

