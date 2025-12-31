"""
Test simple para verificar el cooldown de party (1 hora)
"""
import json
import os

def test_party_cooldown_config():
    """Verifica que el cooldown de party esté configurado a 60 minutos"""
    
    # Leer config.json
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Verificar cooldown de party
    party_config = config.get('party_detection', {})
    cooldown_minutes = party_config.get('cooldown_minutes', 0)
    
    assert cooldown_minutes == 60, f"Cooldown debe ser 60 minutos, pero es {cooldown_minutes}"
    print(f"✅ Cooldown de party: {cooldown_minutes} minutos (1 hora)")
    
    # Verificar que es mayor al buffer de gracia (15 min = 900 seg)
    grace_period_minutes = 15
    assert cooldown_minutes > grace_period_minutes, \
        f"Cooldown ({cooldown_minutes}m) debe ser mayor al buffer de gracia ({grace_period_minutes}m)"
    
    print(f"✅ Cooldown ({cooldown_minutes}m) > Buffer de gracia ({grace_period_minutes}m)")
    print("\n✅ Configuración correcta: No habrá spam de notificaciones de party")

if __name__ == '__main__':
    test_party_cooldown_config()

