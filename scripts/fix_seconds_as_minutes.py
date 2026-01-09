#!/usr/bin/env python3
"""
Script para detectar y corregir datos guardados como SEGUNDOS en vez de MINUTOS

PROBLEMA: Si guardamos segundos (e.g., 3600) como minutos, aparece como 60 horas en vez de 1 hora
DETECCIÓN: total_minutes o daily_minutes > 3000 (50 horas) es sospechoso
SOLUCIÓN: Dividir por 60 si es claramente anormal
"""

import json
import sys
from datetime import datetime

def is_suspicious_value(minutes: int, threshold: int = 3000) -> bool:
    """Detecta valores sospechosos (probablemente segundos guardados como minutos)"""
    return minutes > threshold

def fix_seconds_as_minutes(stats_file='data/stats.json', threshold=3000, dry_run=False):
    """
    Detecta y corrige valores anormalmente altos en stats.json
    
    Args:
        stats_file: Path al archivo stats.json
        threshold: Umbral para detectar valores sospechosos (default 3000 min = 50h)
        dry_run: Si True, solo muestra lo que haría sin modificar
    """
    
    print(f"🔍 Analizando {stats_file}...")
    print(f"   Threshold: {threshold} min ({threshold/60:.1f} horas)")
    print(f"   Modo: {'🔬 DRY RUN (solo análisis)' if dry_run else '✍️  ESCRITURA (aplicará cambios)'}")
    
    with open(stats_file, 'r', encoding='utf-8') as f:
        stats = json.load(f)
    
    corrections = []
    
    # Revisar games de cada usuario
    for user_id, user_data in stats.get('users', {}).items():
        username = user_data.get('username', 'Unknown')
        games = user_data.get('games', {})
        
        for game_name, game_data in games.items():
            # Revisar total_minutes
            total_minutes = game_data.get('total_minutes', 0)
            if is_suspicious_value(total_minutes, threshold):
                old_value = total_minutes
                new_value = int(total_minutes / 60)
                corrections.append({
                    'type': 'game_total',
                    'user': username,
                    'game': game_name,
                    'old': old_value,
                    'new': new_value
                })
                
                if not dry_run:
                    game_data['total_minutes'] = new_value
            
            # Revisar daily_minutes
            daily_minutes = game_data.get('daily_minutes', {})
            for date, minutes in daily_minutes.items():
                if is_suspicious_value(minutes, threshold):
                    old_value = minutes
                    new_value = int(minutes / 60)
                    corrections.append({
                        'type': 'game_daily',
                        'user': username,
                        'game': game_name,
                        'date': date,
                        'old': old_value,
                        'new': new_value
                    })
                    
                    if not dry_run:
                        daily_minutes[date] = new_value
        
        # Revisar voice
        voice = user_data.get('voice', {})
        total_voice = voice.get('total_minutes', 0)
        if is_suspicious_value(total_voice, threshold):
            old_value = total_voice
            new_value = int(total_voice / 60)
            corrections.append({
                'type': 'voice_total',
                'user': username,
                'old': old_value,
                'new': new_value
            })
            
            if not dry_run:
                voice['total_minutes'] = new_value
        
        # Revisar voice daily
        voice_daily = voice.get('daily_minutes', {})
        for date, minutes in voice_daily.items():
            if is_suspicious_value(minutes, threshold):
                old_value = minutes
                new_value = int(minutes / 60)
                corrections.append({
                    'type': 'voice_daily',
                    'user': username,
                    'date': date,
                    'old': old_value,
                    'new': new_value
                })
                
                if not dry_run:
                    voice_daily[date] = new_value
    
    # Mostrar resultados
    print(f"\n📊 ANÁLISIS COMPLETADO:")
    print(f"   Correcciones necesarias: {len(corrections)}")
    
    if corrections:
        print(f"\n🔧 CORRECCIONES DETECTADAS:\n")
        for i, correction in enumerate(corrections, 1):
            print(f"{i}. {correction['type'].upper()}")
            print(f"   Usuario: {correction['user']}")
            if 'game' in correction:
                print(f"   Game: {correction['game']}")
            if 'date' in correction:
                print(f"   Fecha: {correction['date']}")
            print(f"   Valor: {correction['old']} min ({correction['old']/60:.1f}h) → {correction['new']} min ({correction['new']/60:.1f}h)")
            print()
    else:
        print(f"\n✅ NO se encontraron valores sospechosos > {threshold} min")
        print(f"   Los datos parecen estar correctos.")
    
    if not dry_run and corrections:
        # Guardar backup
        backup_file = stats_file.replace('.json', f'_backup_fix_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        print(f"💾 Creando backup: {backup_file}")
        
        with open(stats_file, 'r', encoding='utf-8') as f:
            original = f.read()
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(original)
        
        # Guardar corregido
        print(f"💾 Guardando correcciones en {stats_file}...")
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ CORRECCIONES APLICADAS!")
    elif dry_run and corrections:
        print(f"ℹ️  Ejecuta sin --dry-run para aplicar las correcciones")
    
    return len(corrections)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Detectar y corregir segundos guardados como minutos')
    parser.add_argument('stats_file', nargs='?', default='data/stats.json', help='Path al stats.json')
    parser.add_argument('--threshold', type=int, default=3000, help='Umbral de detección en minutos (default: 3000)')
    parser.add_argument('--dry-run', action='store_true', help='Solo análisis, sin modificar')
    
    args = parser.parse_args()
    
    fix_seconds_as_minutes(args.stats_file, args.threshold, args.dry_run)

