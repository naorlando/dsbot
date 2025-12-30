"""
Comandos de utilidades para estadísticas
Incluye: export, backup, etc.
"""

import discord
from discord.ext import commands
import json
import csv
import logging
from datetime import datetime
from pathlib import Path
from io import StringIO

from core.persistence import stats, STATS_FILE, DATA_DIR
from stats.decorators import stats_channel_only

logger = logging.getLogger('dsbot')


def setup_utils_commands(bot: commands.Bot):
    """Configura los comandos de utilidades"""
    
    @bot.command(name='export')
    @stats_channel_only()
    async def export_stats(ctx, format: str = 'json'):
        """
        Exporta las estadísticas a un archivo
        
        Formatos disponibles: json, csv
        
        Ejemplos:
        - !export
        - !export json
        - !export csv
        """
        
        if format not in ['json', 'csv']:
            await ctx.send('❌ Formato inválido. Usa: `json` o `csv`')
            return
        
        try:
            if format == 'json':
                # Exportar como JSON
                filename = f'stats_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                filepath = Path(DATA_DIR) / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(stats, f, indent=2, ensure_ascii=False)
                
                # Enviar archivo
                await ctx.send(
                    f'📊 Exportación de estadísticas en formato JSON:',
                    file=discord.File(filepath, filename=filename)
                )
                
                # Limpiar archivo temporal
                filepath.unlink()
                
                logger.info(f'Estadísticas exportadas en formato JSON por {ctx.author.display_name}')
            
            elif format == 'csv':
                # Exportar como CSV (usuarios y sus estadísticas principales)
                csv_buffer = StringIO()
                writer = csv.writer(csv_buffer)
                
                # Headers
                writer.writerow([
                    'Usuario',
                    'Total Juegos',
                    'Tiempo Total Juegos (min)',
                    'Total Voz',
                    'Tiempo Total Voz (min)',
                    'Mensajes',
                    'Reacciones',
                    'Stickers'
                ])
                
                # Datos
                for user_id, user_data in stats.get('users', {}).items():
                    username = user_data.get('username', 'Unknown')
                    
                    # Sumar tiempo de todos los juegos
                    total_game_time = sum(
                        game.get('total_minutes', 0)
                        for game in user_data.get('games', {}).values()
                    )
                    
                    # Contar número de juegos únicos
                    total_games = len(user_data.get('games', {}))
                    
                    # Voz
                    voice_data = user_data.get('voice', {})
                    voice_count = voice_data.get('count', 0)
                    voice_time = voice_data.get('total_minutes', 0)
                    
                    # Mensajes
                    messages = user_data.get('messages', {}).get('count', 0)
                    
                    # Reacciones
                    reactions = user_data.get('reactions', {}).get('total', 0)
                    
                    # Stickers
                    stickers = user_data.get('stickers', {}).get('total', 0)
                    
                    writer.writerow([
                        username,
                        total_games,
                        total_game_time,
                        voice_count,
                        voice_time,
                        messages,
                        reactions,
                        stickers
                    ])
                
                # Enviar como archivo
                csv_content = csv_buffer.getvalue()
                csv_buffer.close()
                
                filename = f'stats_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                
                await ctx.send(
                    f'📊 Exportación de estadísticas en formato CSV:',
                    file=discord.File(
                        StringIO(csv_content),
                        filename=filename
                    )
                )
                
                logger.info(f'Estadísticas exportadas en formato CSV por {ctx.author.display_name}')
        
        except Exception as e:
            logger.error(f'Error exportando estadísticas: {e}', exc_info=True)
            await ctx.send(f'❌ Error al exportar estadísticas: {str(e)}')
    
    @bot.command(name='checkstats')
    async def check_stats_file(ctx):
        """
        Verifica si stats.json existe y muestra información básica
        
        Útil para debugging
        """
        try:
            import os
            
            if not os.path.exists(STATS_FILE):
                await ctx.send(f'❌ El archivo `stats.json` no existe en: `{STATS_FILE}`')
                return
            
            # Obtener tamaño del archivo
            file_size = os.path.getsize(STATS_FILE)
            file_size_kb = file_size / 1024
            
            # Contar usuarios
            total_users = len(stats.get('users', {}))
            
            # Información
            info_lines = [
                "📊 **Estado de stats.json:**",
                f"• Ubicación: `{STATS_FILE}`",
                f"• Tamaño: {file_size_kb:.2f} KB",
                f"• Usuarios registrados: {total_users}",
                ""
            ]
            
            # Mostrar algunos usuarios de ejemplo
            if total_users > 0:
                info_lines.append("**Usuarios registrados:**")
                for i, (user_id, user_data) in enumerate(list(stats['users'].items())[:5]):
                    username = user_data.get('username', 'Unknown')
                    games_count = len(user_data.get('games', {}))
                    info_lines.append(f"• {username}: {games_count} juegos")
                    if i >= 4:
                        break
                
                if total_users > 5:
                    info_lines.append(f"• ... y {total_users - 5} más")
            
            await ctx.send('\n'.join(info_lines))
            
        except Exception as e:
            logger.error(f'Error verificando stats.json: {e}', exc_info=True)
            await ctx.send(f'❌ Error: {str(e)}')

