"""
Cog de Utilidades - Comandos de ayuda y soporte
"""

import discord
from discord.ext import commands
import logging

from core.checks import stats_channel_only

logger = logging.getLogger('dsbot')


class UtilityCog(commands.Cog, name='Utilidades'):
    """Comandos de utilidad y ayuda"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='bothelp', aliases=['help', 'ayuda', 'comandos'])
    @stats_channel_only()
    async def show_help(self, ctx, categoria: str = None):
        """
        Muestra la lista de comandos disponibles (solo en canal de stats)
        
        Categorías disponibles: config, stats, voice, all
        
        Ejemplos:
        - !help
        - !help config
        - !help stats
        - !help all
        """
        
        # Si no hay categoría o es 'all', mostrar todas
        if categoria is None:
            categoria = 'general'
        
        categoria = categoria.lower()
        
        if categoria == 'general':
            # Vista general resumida
            embed = discord.Embed(
                title='📚 Centro de Ayuda',
                description='› Explora las categorías para descubrir todos los comandos disponibles',
                color=discord.Color.dark_embed()
            )
            
            embed.add_field(
                name='',
                value='',
                inline=False
            )
            
            embed.add_field(
                name='📂 **Categorías**',
                value=(
                    '› `!help config` • Configuración (owner)\n'
                    '› `!help stats` • Estadísticas\n'
                    '› `!help voice` • Comandos de voz\n'
                    '› `!help all` • Ver todo'
                ),
                inline=True
            )
            
            embed.add_field(
                name='⚡ **Destacados**',
                value=(
                    '› `!statsmenu` • Menú interactivo\n'
                    '› `!stats` • Tus estadísticas\n'
                    '› `!topgames` • Top juegos\n'
                    '› `!voicetime` • Tiempo en voz'
                ),
                inline=True
            )
            
            embed.set_footer(text='💡 Tip: Usa !help [categoría] para ver comandos específicos')
            await ctx.send(embed=embed)
        
        elif categoria == 'config':
            # Comandos de configuración (solo owner)
            embed = discord.Embed(
                title='⚙️ Configuración',
                description='› Comandos para administrar el bot',
                color=discord.Color.dark_gold()
            )
            
            embed.add_field(
                name='',
                value='',
                inline=False
            )
            
            embed.add_field(
                name='🔒 **Solo Owner**',
                value=(
                    '› `!setchannel` • Configurar notificaciones\n'
                    '› `!unsetchannel` • Quitar notificaciones\n'
                    '› `!setstatschannel` • Configurar stats\n'
                    '› `!unsetstatschannel` • Quitar stats'
                ),
                inline=True
            )
            
            embed.add_field(
                name='🌐 **Público**',
                value=(
                    '› `!channels` • Ver canales\n'
                    '› `!toggle` • Activar/desactivar\n'
                    '› `!config` • Ver config\n'
                    '› `!test` • Mensaje de prueba'
                ),
                inline=True
            )
            
            embed.set_footer(text='🔐 Los comandos de owner requieren DISCORD_OWNER_ID configurado')
            await ctx.send(embed=embed)
        
        elif categoria == 'stats':
            # Comandos de estadísticas
            embed = discord.Embed(
                title='📊 Estadísticas',
                description='› Consulta y visualiza datos del servidor',
                color=discord.Color.dark_teal()
            )
            
            embed.add_field(
                name='',
                value='',
                inline=False
            )
            
            embed.add_field(
                name='📈 **Básicos**',
                value=(
                    '› `!stats` • Ver tu perfil\n'
                    '› `!topgames` • Top juegos\n'
                    '› `!topmessages` • Top mensajes\n'
                    '› `!topreactions` • Top reacciones\n'
                    '› `!topemojis` • Top emojis\n'
                    '› `!topstickers` • Top stickers\n'
                    '› `!topusers` • Top usuarios'
                ),
                inline=True
            )
            
            embed.add_field(
                name='✨ **Avanzados**',
                value=(
                    '› `!statsmenu` • Menú interactivo\n'
                    '› `!statsgames` • Ranking juegos\n'
                    '› `!statsvoice` • Ranking voz\n'
                    '› `!statsuser` • Perfil detallado\n'
                    '› `!timeline` • Línea de tiempo\n'
                    '› `!compare` • Comparar users\n'
                    '› `!export` • Exportar datos'
                ),
                inline=True
            )
            
            embed.set_footer(text='📅 Períodos disponibles: today, week, month, all')
            await ctx.send(embed=embed)
        
        elif categoria == 'voice':
            # Comandos de voz
            embed = discord.Embed(
                title='🎙️ Comandos de Voz',
                description='› Estadísticas de tiempo en canales de voz',
                color=discord.Color.dark_purple()
            )
            
            embed.add_field(
                name='',
                value='',
                inline=False
            )
            
            embed.add_field(
                name='⏱️ **Comandos**',
                value=(
                    '› `!voicetime` • Ver tu tiempo\n'
                    '› `!voicetop` • Ranking global'
                ),
                inline=True
            )
            
            embed.add_field(
                name='📅 **Períodos**',
                value=(
                    '› `today` • Hoy\n'
                    '› `week` • Semana\n'
                    '› `month` • Mes\n'
                    '› `all` • Todo'
                ),
                inline=True
            )
            
            embed.add_field(
                name='',
                value='',
                inline=False
            )
            
            embed.add_field(
                name='💡 **Ejemplos**',
                value=(
                    '```\n'
                    '!voicetime\n'
                    '!voicetime @Juan week\n'
                    '!voicetop month\n'
                    '```'
                ),
                inline=False
            )
            
            await ctx.send(embed=embed)
        
        elif categoria == 'all':
            # Mostrar TODOS los comandos (vista completa)
            embed1 = discord.Embed(
                title='📖 Todos los Comandos · Parte 1/3',
                description='› Configuración del bot',
                color=discord.Color.greyple()
            )
            
            embed1.add_field(
                name='⚙️ **Configuración**',
                value=(
                    '› `!setchannel` 🔒 • Configurar notificaciones\n'
                    '› `!setstatschannel` 🔒 • Configurar stats\n'
                    '› `!channels` • Ver canales\n'
                    '› `!toggle` • Activar/desactivar\n'
                    '› `!config` • Ver configuración\n'
                    '› `!test` • Mensaje de prueba'
                ),
                inline=False
            )
            
            await ctx.send(embed=embed1)
            
            # Embed 2: Stats
            embed2 = discord.Embed(
                title='📖 Todos los Comandos · Parte 2/3',
                description='› Estadísticas del servidor',
                color=discord.Color.greyple()
            )
            
            embed2.add_field(
                name='📈 **Básicos**',
                value=(
                    '› `!stats` • Perfil de usuario\n'
                    '› `!topgames` • Top juegos\n'
                    '› `!topmessages` • Top mensajes\n'
                    '› `!topreactions` • Top reacciones\n'
                    '› `!topemojis` • Top emojis\n'
                    '› `!topstickers` • Top stickers\n'
                    '› `!topusers` • Top usuarios'
                ),
                inline=True
            )
            
            embed2.add_field(
                name='✨ **Avanzados**',
                value=(
                    '› `!statsmenu` • Menú interactivo\n'
                    '› `!statsgames` • Ranking juegos\n'
                    '› `!statsvoice` • Ranking voz\n'
                    '› `!statsuser` • Perfil detallado\n'
                    '› `!timeline` • Línea de tiempo\n'
                    '› `!compare` • Comparar users\n'
                    '› `!export` • Exportar datos'
                ),
                inline=True
            )
            
            await ctx.send(embed=embed2)
            
            # Embed 3: Voice + Help
            embed3 = discord.Embed(
                title='📖 Todos los Comandos · Parte 3/3',
                description='› Voz y utilidades',
                color=discord.Color.greyple()
            )
            
            embed3.add_field(
                name='🎙️ **Voz**',
                value=(
                    '› `!voicetime` • Tu tiempo en voz\n'
                    '› `!voicetop` • Ranking por tiempo'
                ),
                inline=True
            )
            
            embed3.add_field(
                name='🛠️ **Utilidades**',
                value=(
                    '› `!bothelp` • Ver ayuda\n'
                    '› `!channels` • Ver canales'
                ),
                inline=True
            )
            
            embed3.add_field(
                name='',
                value='',
                inline=False
            )
            
            embed3.set_footer(text='📚 Para más detalles usa: !help [config|stats|voice]')
            await ctx.send(embed=embed3)
        
        else:
            await ctx.send(
                f'❌ Categoría `{categoria}` no encontrada.\n'
                f'Usa: `!help` (general), `!help config`, `!help stats`, `!help voice`, o `!help all`'
            )


async def setup(bot):
    """Función requerida por discord.py para cargar el cog"""
    await bot.add_cog(UtilityCog(bot))

