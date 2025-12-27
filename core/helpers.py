"""
Módulo de funciones auxiliares
Funciones helper para el bot
"""

import re
import discord
import asyncio
import logging
from core.persistence import get_channel_id

logger = logging.getLogger('dsbot')


def is_link_spam(message_content):
    """Detecta si un mensaje es principalmente links/URLs
    
    Args:
        message_content: Contenido del mensaje
        
    Returns:
        True si el mensaje es spam de links, False si es contenido válido
    """
    if not message_content or len(message_content) == 0:
        return True
    
    # Regex para detectar URLs
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    urls = re.findall(url_pattern, message_content, re.IGNORECASE)
    
    # Si no hay URLs, no es spam
    if not urls:
        return False
    
    # Calcular longitud total de URLs
    url_length = sum(len(url) for url in urls)
    
    # Si las URLs ocupan más del 70% del mensaje, considerarlo spam
    if url_length / len(message_content) > 0.7:
        return True
    
    # Si el mensaje tiene solo 1-2 palabras además del link, considerarlo spam
    content_without_urls = message_content
    for url in urls:
        content_without_urls = content_without_urls.replace(url, '')
    
    # Contar palabras reales (sin URLs)
    words = [w for w in content_without_urls.split() if len(w) > 0]
    if len(words) <= 2:
        return True
    
    return False


def get_activity_verb(activity_type):
    """Traduce el tipo de actividad al español"""
    verbs = {
        'playing': 'jugando',
        'streaming': 'transmitiendo',
        'watching': 'viendo',
        'listening': 'escuchando'
    }
    return verbs.get(activity_type, activity_type)


async def send_notification(message, bot):
    """Envía un mensaje al canal configurado con manejo de errores robusto"""
    channel_id = get_channel_id()
    if not channel_id:
        logger.warning('⚠️  No hay canal configurado. Configura DISCORD_CHANNEL_ID o usa !setchannel')
        return
    
    try:
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(message)
            logger.info(f'✅ Notificación enviada: {message[:50]}...')
        else:
            logger.error(f'⚠️  No se encontró el canal con ID {channel_id}')
    except discord.errors.HTTPException as e:
        if e.status == 429:  # Rate limited
            retry_after = e.retry_after if hasattr(e, 'retry_after') else 1.0
            logger.warning(f'⚠️  Rate limited. Esperando {retry_after}s...')
            await asyncio.sleep(retry_after)
            try:
                await channel.send(message)
            except Exception as retry_error:
                logger.error(f'❌ Error al reintentar: {retry_error}')
        else:
            logger.error(f'❌ Error HTTP: {e}')
    except discord.errors.Forbidden:
        logger.error(f'⚠️  Sin permisos para enviar mensajes al canal {channel_id}')
    except Exception as e:
        logger.error(f'❌ Error al enviar notificación: {e}')

