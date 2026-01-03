"""
Sistema de tracking de application_ids por juego
Detecta app_ids sospechosos basándose en historial de uso
Solo trackea app_ids reales (no fakes)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger('dsbot')

# Archivo de persistencia
APP_ID_TRACKER_FILE = Path('app_id_tracker.json')

# Threshold para considerar un app_id como "verificado" (real)
VERIFICATION_THRESHOLD = 3

# Estructura: {game_name: {counts: {app_id: count}, verified: app_id|None}}
# Ejemplo: {"LoL": {"counts": {"401518...": 5, "140241...": 1}, "verified": "401518..."}}
app_id_stats: Dict[str, Dict] = {}


def load_app_id_tracker():
    """Carga el tracker de app_ids desde disco"""
    global app_id_stats
    
    if not APP_ID_TRACKER_FILE.exists():
        app_id_stats = {}
        return
    
    try:
        with open(APP_ID_TRACKER_FILE, 'r', encoding='utf-8') as f:
            app_id_stats = json.load(f)
        logger.info(f'📊 App ID tracker cargado: {len(app_id_stats)} juegos')
    except Exception as e:
        logger.error(f'Error cargando app_id_tracker.json: {e}')
        app_id_stats = {}


def save_app_id_tracker():
    """Guarda el tracker de app_ids a disco"""
    try:
        with open(APP_ID_TRACKER_FILE, 'w', encoding='utf-8') as f:
            json.dump(app_id_stats, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f'Error guardando app_id_tracker.json: {e}')


def track_app_id(game_name: str, app_id: Optional[int]) -> bool:
    """
    Registra un app_id para un juego con sistema de contadores.
    
    Sistema de verificación:
    - Trackea TODOS los app_ids con contador
    - Cuando uno llega a VERIFICATION_THRESHOLD (3) → se marca como VERIFICADO
    - Una vez verificado, solo ese app_id es válido
    - Antes de verificar, todos son aceptados (pendientes)
    
    Args:
        game_name: Nombre del juego
        app_id: Application ID de Discord
    
    Returns:
        True si se aceptó (real o pendiente), False si es fake (después de verificación)
    """
    if not app_id:
        return False
    
    app_id_str = str(app_id)
    
    # Inicializar estructura si no existe
    if game_name not in app_id_stats:
        app_id_stats[game_name] = {
            'counts': {},
            'verified': None
        }
    
    game_data = app_id_stats[game_name]
    
    # Si ya hay un app_id VERIFICADO y este NO es el verificado → FAKE
    if game_data['verified'] and game_data['verified'] != app_id_str:
        logger.warning(f'🚫 App ID fake detectado: {game_name} (verificado: {game_data["verified"]}, fake: {app_id_str})')
        return False
    
    # Incrementar contador para este app_id
    if app_id_str not in game_data['counts']:
        game_data['counts'][app_id_str] = 0
    
    game_data['counts'][app_id_str] += 1
    count = game_data['counts'][app_id_str]
    
    # Si llegó al threshold, marcarlo como VERIFICADO
    if count >= VERIFICATION_THRESHOLD and not game_data['verified']:
        game_data['verified'] = app_id_str
        save_app_id_tracker()
        logger.info(f'✅ App ID verificado: {game_name} ({app_id_str}) - {count} usos')
        return True
    
    # Si ya es el verificado, solo incrementar
    if game_data['verified'] == app_id_str:
        if count % 10 == 0:  # Guardar cada 10 usos
            save_app_id_tracker()
        return True
    
    # Si NO hay verificado todavía, aceptar como pendiente
    logger.debug(f'📊 App ID pendiente: {game_name} ({app_id_str}) - {count}/{VERIFICATION_THRESHOLD} usos')
    if count % 5 == 0:  # Guardar cada 5 usos
        save_app_id_tracker()
    return True


def get_real_app_id(game_name: str) -> Optional[str]:
    """
    Retorna el app_id verificado para un juego (si existe).
    
    Args:
        game_name: Nombre del juego
    
    Returns:
        App ID verificado o None si no está verificado
    """
    if game_name not in app_id_stats:
        return None
    return app_id_stats[game_name].get('verified')


def is_app_id_fake(game_name: str, app_id: Optional[int]) -> bool:
    """
    Determina si un app_id es FAKE para un juego.
    
    Lógica con sistema de verificación:
    1. Si no hay app_id → FAKE
    2. Si el juego NO tiene app_id verificado → NO es fake (pendiente)
    3. Si el juego tiene app_id verificado y coincide → NO es fake
    4. Si el juego tiene app_id verificado y NO coincide → FAKE
    
    Args:
        game_name: Nombre del juego
        app_id: Application ID a verificar
    
    Returns:
        True si es FAKE, False si es real o pendiente
    """
    if not app_id:
        return True  # Sin app_id es fake
    
    verified_app_id = get_real_app_id(game_name)
    
    # Si no hay app_id verificado, no es fake (aún en proceso de verificación)
    if verified_app_id is None:
        return False
    
    # Si el app_id NO coincide con el verificado → FAKE
    return str(app_id) != verified_app_id


def get_fake_game_name(game_name: str) -> str:
    """
    Retorna el nombre a usar para juegos fake.
    
    Args:
        game_name: Nombre original del juego
    
    Returns:
        Nombre modificado para fake (ej: "League of Legends (Fake)")
    """
    return f"{game_name} (Fake)"


def get_game_stats(game_name: str) -> Dict:
    """
    Retorna estadísticas de tracking para un juego.
    
    Args:
        game_name: Nombre del juego
    
    Returns:
        Dict con contadores y app_id verificado si existe
    """
    if game_name not in app_id_stats:
        return {}
    
    game_data = app_id_stats[game_name]
    return {
        'counts': game_data.get('counts', {}),
        'verified': game_data.get('verified'),
        'is_verified': game_data.get('verified') is not None
    }


def clear_tracker():
    """Limpia todo el tracker (útil para tests)"""
    global app_id_stats
    app_id_stats = {}
    if APP_ID_TRACKER_FILE.exists():
        APP_ID_TRACKER_FILE.unlink()


# Cargar al importar el módulo
load_app_id_tracker()

