"""
Wrapped Event - Envío automático de Wrapped 2025
Se ejecuta SOLO el 31 de diciembre de 2025 a las 12:00
"""

import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime, time
import json
from core.persistence import get_channel_id, STATS_FILE
from stats.commands.wrapped import generate_wrapped_embed

logger = logging.getLogger('dsbot')


class WrappedEventCog(commands.Cog, name='WrappedEvent'):
    """Cog para envío automático del Wrapped 2025"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.wrapped_sent = False  # Flag para enviar solo una vez
        logger.info("🎁 WrappedEventCog inicializado")
    
    async def cog_load(self):
        """Se ejecuta cuando el cog se carga"""
        logger.info("🎁 Iniciando task de Wrapped 2025...")
        self.check_and_send_wrapped.start()
    
    async def cog_unload(self):
        """Se ejecuta cuando el cog se descarga"""
        self.check_and_send_wrapped.cancel()
        logger.info("🎁 WrappedEvent descargado")
    
    @tasks.loop(minutes=5)  # Revisar cada 5 minutos
    async def check_and_send_wrapped(self):
        """
        Revisa si es el momento de enviar el wrapped.
        Se ejecuta solo el 31 de diciembre de 2025 a las 12:00
        """
        try:
            # Si ya se envió, no hacer nada
            if self.wrapped_sent:
                return
            
            now = datetime.now()
            
            # Verificar que sea 31 de diciembre de 2025
            if now.year != 2025 or now.month != 12 or now.day != 31:
                logger.debug("🎁 No es 31 de diciembre de 2025, wrapped no se enviará")
                return
            
            # Verificar que sea la hora correcta (12:00 ± 5 minutos)
            target_hour = 12
            target_minute = 0
            
            # Si es entre 12:00 y 12:05, enviar
            if now.hour == target_hour and now.minute < 10:
                logger.info("🎁 ¡ES HORA! Enviando Wrapped 2025 a todos los usuarios...")
                await self.send_wrapped_to_all()
                self.wrapped_sent = True
                logger.info("✅ Wrapped 2025 enviado exitosamente")
                
                # Detener el task después de enviar
                self.check_and_send_wrapped.cancel()
        
        except Exception as e:
            logger.error(f"❌ Error en check_and_send_wrapped: {e}", exc_info=True)
    
    @check_and_send_wrapped.before_loop
    async def before_check(self):
        """Esperar a que el bot esté listo"""
        await self.bot.wait_until_ready()
        logger.info("🎁 Bot listo, esperando momento para enviar Wrapped...")
    
    async def send_wrapped_to_all(self):
        """
        Envía el wrapped a todos los usuarios con datos en stats.json
        """
        try:
            # Obtener canal de notificaciones
            channel_id = get_channel_id()
            if not channel_id:
                logger.error("❌ No hay canal de notificaciones configurado")
                return
            
            channel = self.bot.get_channel(channel_id)
            if not channel:
                logger.error(f"❌ No se encontró el canal {channel_id}")
                return
            
            # Cargar stats
            try:
                with open(STATS_FILE, 'r', encoding='utf-8') as f:
                    stats_data = json.load(f)
            except Exception as e:
                logger.error(f"❌ Error cargando stats.json: {e}")
                return
            
            users = stats_data.get('users', {})
            if not users:
                logger.warning("⚠️  No hay usuarios en stats.json")
                return
            
            # Enviar mensaje de introducción
            intro_embed = discord.Embed(
                title="🎉 WRAPPED 2025 🎉",
                description=(
                    "¡Llegó el momento de ver tu año en Discord!\n\n"
                    "📊 A continuación verás tu resumen del 2025:\n"
                    "🎮 Gaming • 🔊 Voice • 🎉 Parties • 💬 Social\n\n"
                    "¡Feliz Año Nuevo! 🎆"
                ),
                color=0xFFD700,  # Dorado
                timestamp=datetime.now()
            )
            intro_embed.set_footer(text="Wrapped 2025 • Generado automáticamente")
            
            await channel.send("@here", embed=intro_embed)
            logger.info(f"✅ Mensaje de introducción enviado")
            
            # Enviar wrapped para cada usuario
            sent_count = 0
            skipped_count = 0
            
            for user_id, user_data in users.items():
                try:
                    # Obtener member object
                    member = None
                    for guild in self.bot.guilds:
                        member = guild.get_member(int(user_id))
                        if member:
                            break
                    
                    if not member:
                        logger.debug(f"⚠️  Usuario {user_id} no encontrado en ningún servidor")
                        skipped_count += 1
                        continue
                    
                    # Verificar que tenga datos significativos
                    has_data = False
                    
                    # Verificar gaming
                    if user_data.get('games'):
                        has_data = True
                    
                    # Verificar voice
                    if user_data.get('voice', {}).get('total_minutes', 0) > 0:
                        has_data = True
                    
                    # Verificar parties
                    parties_history = stats_data.get('parties', {}).get('history', [])
                    user_parties = [p for p in parties_history if user_id in p.get('players', [])]
                    if user_parties:
                        has_data = True
                    
                    if not has_data:
                        logger.debug(f"⚠️  {member.display_name} no tiene datos suficientes")
                        skipped_count += 1
                        continue
                    
                    # Generar wrapped
                    wrapped_embed = generate_wrapped_embed(
                        stats_data=stats_data,
                        user_id=user_id,
                        username=member.display_name,
                        year=2025
                    )
                    
                    # Enviar
                    await channel.send(f"## {member.mention}", embed=wrapped_embed)
                    sent_count += 1
                    logger.info(f"✅ Wrapped enviado a {member.display_name}")
                    
                    # Pequeño delay para evitar rate limit
                    import asyncio
                    await asyncio.sleep(2)
                
                except Exception as e:
                    logger.error(f"❌ Error enviando wrapped a {user_id}: {e}")
                    skipped_count += 1
            
            # Mensaje final
            summary_embed = discord.Embed(
                title="✅ Wrapped 2025 Completado",
                description=(
                    f"📊 **Wrappeds enviados:** {sent_count}\n"
                    f"⚠️ **Omitidos:** {skipped_count}\n\n"
                    "¡Gracias por ser parte de este servidor! 🎉\n"
                    "¡Feliz Año Nuevo! 🎆"
                ),
                color=0x00FF00,  # Verde
                timestamp=datetime.now()
            )
            
            await channel.send(embed=summary_embed)
            logger.info(f"📊 Resumen: {sent_count} enviados, {skipped_count} omitidos")
        
        except Exception as e:
            logger.error(f"❌ Error en send_wrapped_to_all: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    """Función requerida por discord.py para cargar el cog"""
    await bot.add_cog(WrappedEventCog(bot))

