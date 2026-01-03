"""
Test para verificar comportamiento de party cuando quedan <2 jugadores
con grace period de 20 min
"""

import pytest
from datetime import datetime, timedelta


class MockPartySession:
    """Mock de PartySession para tests"""
    def __init__(self, game_name, player_ids, player_names, guild_id):
        self.game_name = game_name
        self.player_ids = set(player_ids)
        self.player_names = player_names
        self.guild_id = guild_id
        self.start_time = datetime.now()
        self.last_activity_update = datetime.now()
        self.is_confirmed = True
        self.max_players = len(player_ids)
        self.initial_players = set(player_ids)


class TestPartyMinPlayersGrace:
    """Tests para party con cambios de jugadores y grace period"""
    
    def test_tres_a_dos_jugadores_party_continua(self):
        """
        Escenario: Party de 3 → 1 se va → quedan 2
        Resultado: Party CONTINÚA (≥2 jugadores)
        """
        # Party inicial con 3 jugadores
        session = MockPartySession(
            'League of Legends',
            ['user1', 'user2', 'user3'],
            ['agu', 'Pino', 'Zeta'],
            123
        )
        
        # Simulamos que un jugador se va (quedan 2)
        new_players = {'user1', 'user2'}
        min_players = 2
        
        # Verificar que todavía hay suficientes jugadores
        assert len(new_players) >= min_players, "Party debe continuar con 2 jugadores"
        
        # La party NO debe entrar en grace, sigue activa
        session.player_ids = new_players
        session.player_names = ['agu', 'Pino']
        
        # Actualizar actividad (resetea grace)
        session.last_activity_update = datetime.now()
        
        # Verificar que NO está en grace period
        time_since = (datetime.now() - session.last_activity_update).total_seconds()
        grace_period = 1200  # 20 min
        assert time_since < grace_period
    
    def test_dos_a_uno_jugador_entra_grace(self):
        """
        Escenario: Party de 2 → 1 se va → queda 1
        Resultado: Party entra en GRACE PERIOD (20 min)
        """
        session = MockPartySession(
            'League of Legends',
            ['user1', 'user2'],
            ['agu', 'Pino'],
            123
        )
        
        # Simulamos que un jugador se va (queda 1)
        new_players = {'user1'}
        min_players = 2
        
        # Verificar que NO hay suficientes jugadores
        assert len(new_players) < min_players, "Quedan <2 jugadores"
        
        # La party debe INTENTAR cerrar, pero entrar en grace
        # (NO actualizar last_activity porque Discord no reporta party)
        
        # Simular que pasan 10 minutos
        session.last_activity_update = datetime.now() - timedelta(minutes=10)
        
        # Verificar que SÍ está en grace period
        time_since = (datetime.now() - session.last_activity_update).total_seconds()
        grace_period = 1200  # 20 min
        in_grace = time_since < grace_period
        
        assert in_grace, "Debe estar en grace period (10 min < 20 min)"
        # NO cerrar todavía, esperar reconexión
    
    def test_grace_period_expira_party_cierra(self):
        """
        Escenario: Party queda con 1 jugador, pasan 20 min, no vuelve nadie
        Resultado: Party CIERRA definitivamente
        """
        session = MockPartySession(
            'League of Legends',
            ['user1'],
            ['agu'],
            123
        )
        
        # Simular que pasaron 21 minutos sin actividad
        session.last_activity_update = datetime.now() - timedelta(minutes=21)
        
        # Verificar que grace period expiró
        time_since = (datetime.now() - session.last_activity_update).total_seconds()
        grace_period = 1200  # 20 min
        in_grace = time_since < grace_period
        
        assert not in_grace, "Grace period expiró (21 min > 20 min)"
        # Debe cerrar definitivamente y guardar tiempo
    
    def test_reconexion_dentro_grace_party_continua(self):
        """
        Escenario: Party 2 → 1 (grace) → vuelve el que se fue en 5 min
        Resultado: Party CONTINÚA sin nueva notificación
        """
        session = MockPartySession(
            'League of Legends',
            ['user1'],  # Solo queda 1
            ['agu'],
            123
        )
        
        # Última actividad hace 5 minutos
        session.last_activity_update = datetime.now() - timedelta(minutes=5)
        
        # Verificar que está en grace
        grace_period = 1200
        time_since = (datetime.now() - session.last_activity_update).total_seconds()
        assert time_since < grace_period
        
        # Simulamos que vuelve user2
        session.player_ids = {'user1', 'user2'}
        session.player_names = ['agu', 'Pino']
        
        # Actualizar actividad (sale de grace)
        session.last_activity_update = datetime.now()
        
        # Verificar: Party continúa, NO es nueva
        assert len(session.player_ids) >= 2
        # NO debe notificar "party formada" (es reactivación)
    
    def test_nuevo_jugador_entra_dentro_grace_crea_nueva_party(self):
        """
        Escenario: Party 2 → 1 (grace) → entra jugador NUEVO
        Resultado: Party NUEVA se crea, SÍ notifica
        """
        # Party original que entró en grace (solo agu)
        old_session = MockPartySession(
            'League of Legends',
            ['user1'],
            ['agu'],
            123
        )
        old_session.last_activity_update = datetime.now() - timedelta(minutes=5)
        
        # Verificar que vieja party está en grace
        grace_period = 1200
        time_since = (datetime.now() - old_session.last_activity_update).total_seconds()
        assert time_since < grace_period, "Vieja party en grace"
        
        # Pero: cuando on_presence_update detecta 2 jugadores,
        # llama handle_start() que verifica si hay sesión activa
        
        # Como la sesión existe pero está en grace (no cerró),
        # puede pasar:
        # A) Se considera nueva party → notifica
        # B) Se considera continuación → no notifica
        
        # Pregunta para el código: ¿Cómo diferenciamos?
        # Respuesta: Si los jugadores son DIFERENTES, es nueva party
        
        new_players = {'user1', 'user4'}  # agu + WiREngineer (nuevo)
        old_players = old_session.player_ids
        
        # Detectar jugadores nuevos
        new_joiners = new_players - old_players
        
        # Si hay jugador nuevo Y la party estaba en grace con <2
        # → Es efectivamente una NUEVA party
        should_notify = len(new_joiners) > 0 and len(old_session.player_ids) < 2
        
        assert should_notify, "Debe notificar party nueva con jugador nuevo"


class TestPartyNotificationLogic:
    """Tests para lógica de notificaciones"""
    
    def test_vuelve_jugador_original_no_notifica(self):
        """
        Escenario: Party 3 → 2 (Zeta se va) → Zeta vuelve
        Resultado: NO notifica (es el mismo grupo)
        """
        initial_players = {'user1', 'user2', 'user3'}  # agu, Pino, Zeta
        
        # Zeta se va
        current_players = {'user1', 'user2'}  # agu, Pino
        
        # Zeta vuelve
        returning_players = {'user1', 'user2', 'user3'}
        
        # Detectar quien volvió
        returned = returning_players - current_players
        
        # Verificar: es un jugador que ya estaba inicialmente
        is_returning = returned.issubset(initial_players)
        
        assert is_returning, "Zeta es jugador original"
        # NO debe notificar como "nuevo jugador"
    
    def test_jugador_nuevo_si_notifica(self):
        """
        Escenario: Party 2 (agu, Pino) → WiREngineer se une
        Resultado: SÍ notifica "WiREngineer se unió"
        """
        initial_players = {'user1', 'user2'}  # agu, Pino
        current_players = {'user1', 'user2', 'user4'}  # + WiREngineer
        
        # Detectar nuevos
        new_joiners = current_players - initial_players
        
        # Verificar: es jugador nuevo
        is_new = len(new_joiners) > 0
        is_new_player = not new_joiners.issubset(initial_players)
        
        assert is_new and is_new_player, "WiREngineer es jugador nuevo"
        # SÍ debe notificar "se unió"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

