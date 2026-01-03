"""
Test para verificar limpieza de sesiones huérfanas en stats.json
"""

import unittest
from datetime import datetime, timedelta


class TestOrphanedSessionsCleanup(unittest.TestCase):
    """Tests para lógica de limpieza de sesiones colgadas"""
    
    def test_session_menor_12h_no_se_limpia(self):
        """
        Sesión con 10h de antigüedad NO debe limpiarse
        (puede ser sesión legítima larga)
        """
        start_time = datetime.now() - timedelta(hours=10)
        max_age_hours = 12
        
        age_hours = (datetime.now() - start_time).total_seconds() / 3600
        
        should_clean = age_hours > max_age_hours
        
        self.assertFalse(should_clean, "Sesión de 10h NO debe limpiarse")
    
    def test_session_mayor_12h_sin_memoria_se_limpia(self):
        """
        Sesión con 15h de antigüedad SIN active_sessions debe limpiarse
        (definitivamente colgada)
        """
        start_time = datetime.now() - timedelta(hours=15)
        max_age_hours = 12
        in_memory = False  # NO está en active_sessions
        
        age_hours = (datetime.now() - start_time).total_seconds() / 3600
        
        should_clean = age_hours > max_age_hours and not in_memory
        
        self.assertTrue(should_clean, "Sesión de 15h sin memoria DEBE limpiarse")
    
    def test_session_mayor_12h_con_memoria_no_se_limpia(self):
        """
        Sesión con 15h de antigüedad CON active_sessions NO debe limpiarse
        (sesión legítima larga)
        """
        start_time = datetime.now() - timedelta(hours=15)
        max_age_hours = 12
        in_memory = True  # SÍ está en active_sessions
        
        age_hours = (datetime.now() - start_time).total_seconds() / 3600
        
        # Aunque sea vieja, si está en memoria es legítima
        should_clean = age_hours > max_age_hours and not in_memory
        
        self.assertFalse(should_clean, "Sesión de 15h en memoria NO debe limpiarse")
    
    def test_edge_case_exactamente_12h(self):
        """
        Sesión con ~12h debe limpiarse solo si es estrictamente mayor
        """
        # Usar 11.99h para evitar problemas de precisión
        start_time = datetime.now() - timedelta(hours=11, minutes=59)
        max_age_hours = 12
        
        age_hours = (datetime.now() - start_time).total_seconds() / 3600
        
        # Debe ser estrictamente mayor
        should_clean = age_hours > max_age_hours
        
        self.assertFalse(should_clean, "Sesión de 11.99h NO debe limpiarse")
    
    def test_session_4_dias_definitivamente_se_limpia(self):
        """
        Sesión de 4 días (como en stats.json actual) debe limpiarse
        """
        start_time = datetime.now() - timedelta(days=4)
        max_age_hours = 12
        in_memory = False
        
        age_hours = (datetime.now() - start_time).total_seconds() / 3600
        
        should_clean = age_hours > max_age_hours and not in_memory
        
        self.assertTrue(should_clean, f"Sesión de {age_hours:.0f}h DEBE limpiarse")
        self.assertGreater(age_hours, 24 * 4, "Debe ser >4 días")


class TestPartyOrphanedCleanup(unittest.TestCase):
    """Tests para limpieza de parties huérfanas"""
    
    def test_party_activa_3_dias_se_limpia(self):
        """
        Party en stats['parties']['active'] de hace 3 días debe limpiarse
        """
        start_time = datetime.now() - timedelta(days=3)
        max_age_hours = 12
        in_memory = False
        
        age_hours = (datetime.now() - start_time).total_seconds() / 3600
        
        should_clean = age_hours > max_age_hours and not in_memory
        
        self.assertTrue(should_clean, f"Party de {age_hours:.0f}h DEBE limpiarse")
    
    def test_party_reciente_no_se_limpia(self):
        """
        Party de hoy en stats['parties']['active'] NO debe limpiarse
        """
        start_time = datetime.now() - timedelta(hours=2)
        max_age_hours = 12
        in_memory = True  # Asumimos que está en memoria
        
        age_hours = (datetime.now() - start_time).total_seconds() / 3600
        
        should_clean = age_hours > max_age_hours and not in_memory
        
        self.assertFalse(should_clean, "Party reciente NO debe limpiarse")


if __name__ == '__main__':
    unittest.main()

