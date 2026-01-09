#!/usr/bin/env python3
"""
Script para limpiar parties duplicadas en stats.json

PROBLEMA: Se guardaron múltiples entries de la MISMA party
CRITERIO: Mismo game + start + players
SOLUCIÓN: Quedarse con la de MAYOR duration_minutes
"""

import json
import sys
from datetime import datetime
from collections import defaultdict

def cleanup_duplicate_parties(stats_file='data/stats.json'):
    """Limpia parties duplicadas del historial"""
    
    print("🔍 Cargando stats.json...")
    with open(stats_file, 'r', encoding='utf-8') as f:
        stats = json.load(f)
    
    history = stats.get('parties', {}).get('history', [])
    print(f"📊 Total parties en historial: {len(history)}")
    
    # Agrupar por (game, start, players_tuple)
    groups = defaultdict(list)
    
    for idx, party in enumerate(history):
        # Crear key única
        game = party.get('game', '')
        start = party.get('start', '')
        players = tuple(sorted(party.get('players', [])))
        
        key = (game, start, players)
        groups[key].append((idx, party))
    
    # Identificar duplicados
    duplicates_found = 0
    duplicates_removed = 0
    indices_to_keep = set()
    
    for key, group in groups.items():
        if len(group) > 1:
            duplicates_found += 1
            game, start, _ = key
            
            # Encontrar la party con MAYOR duration
            max_duration_party = max(group, key=lambda x: x[1].get('duration_minutes', 0))
            max_duration = max_duration_party[1].get('duration_minutes', 0)
            
            print(f"\n🔄 DUPLICADO ENCONTRADO:")
            print(f"   Game: {game}")
            print(f"   Start: {start}")
            print(f"   Entries: {len(group)}")
            print(f"   Duraciones: {[p[1].get('duration_minutes', 0) for p in group[:10]]}{'...' if len(group) > 10 else ''}")
            print(f"   ✅ Manteniendo: {max_duration} min")
            
            # Quedarnos con la de mayor duración
            indices_to_keep.add(max_duration_party[0])
            duplicates_removed += len(group) - 1
        else:
            # No es duplicado, mantener
            indices_to_keep.add(group[0][0])
    
    # Crear nuevo historial sin duplicados
    new_history = [party for idx, party in enumerate(history) if idx in indices_to_keep]
    
    print(f"\n📈 RESUMEN:")
    print(f"   Total parties: {len(history)}")
    print(f"   Grupos de duplicados encontrados: {duplicates_found}")
    print(f"   Duplicados removidos: {duplicates_removed}")
    print(f"   Parties después de limpieza: {len(new_history)}")
    
    # Recalcular stats_by_game
    print(f"\n🔧 Recalculando stats_by_game...")
    new_stats_by_game = {}
    
    for party in new_history:
        game = party.get('game', '')
        duration = party.get('duration_minutes', 0)
        max_players = party.get('max_players', 0)
        players = party.get('players', [])
        
        if game not in new_stats_by_game:
            new_stats_by_game[game] = {
                'total_parties': 0,
                'total_duration_minutes': 0,
                'max_players_ever': 0,
                'total_unique_players': set()
            }
        
        game_stats = new_stats_by_game[game]
        game_stats['total_parties'] += 1
        game_stats['total_duration_minutes'] += duration
        game_stats['max_players_ever'] = max(game_stats['max_players_ever'], max_players)
        game_stats['total_unique_players'].update(players)
    
    # Convertir sets a listas para JSON
    for game_stats in new_stats_by_game.values():
        game_stats['total_unique_players'] = list(game_stats['total_unique_players'])
    
    # Comparar antes/después
    old_stats = stats.get('parties', {}).get('stats_by_game', {})
    print(f"\n📊 STATS ANTES/DESPUÉS:")
    for game, new_stats in new_stats_by_game.items():
        old = old_stats.get(game, {})
        old_parties = old.get('total_parties', 0)
        old_duration = old.get('total_duration_minutes', 0)
        
        new_parties = new_stats['total_parties']
        new_duration = new_stats['total_duration_minutes']
        
        if old_parties != new_parties or old_duration != new_duration:
            print(f"\n   {game}:")
            print(f"      Parties: {old_parties} → {new_parties}")
            print(f"      Duración: {old_duration} min ({old_duration/60:.1f}h) → {new_duration} min ({new_duration/60:.1f}h)")
    
    # Guardar backup
    backup_file = stats_file.replace('.json', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    print(f"\n💾 Creando backup: {backup_file}")
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    # Actualizar stats
    stats['parties']['history'] = new_history
    stats['parties']['stats_by_game'] = new_stats_by_game
    
    # Guardar
    print(f"💾 Guardando stats.json limpio...")
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ LIMPIEZA COMPLETADA!")
    return duplicates_removed

if __name__ == '__main__':
    stats_file = sys.argv[1] if len(sys.argv) > 1 else 'data/stats.json'
    cleanup_duplicate_parties(stats_file)

