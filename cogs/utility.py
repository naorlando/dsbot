"""
Cog de Utilidades - Comandos de ayuda y soporte
"""

import discord
from discord.ext import commands
import logging

from core.checks import stats_channel_only
from core.party_session import PartySessionManager
from core.updates import load_update_sections

logger = logging.getLogger('dsbot')


class UtilityCog(commands.Cog, name='Utilidades'):
    """Comandos de utilidad y ayuda"""
    
    def __init__(self, bot):
        self.bot = bot
        self.party_manager = PartySessionManager(bot)

    def _get_party_manager(self):
        """Usa el manager runtime de EventsCog para ver parties activas reales."""
        events_cog = self.bot.get_cog('Events')
        return getattr(events_cog, 'party_manager', self.party_manager)

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
                    '› `!updates` • Últimas novedades\n'
                    '› `!help all` • Ver todo'
                ),
                inline=True
            )
            
            embed.add_field(
                name='⚡ **Destacados**',
                value=(
                    '› `!stats` • Tus estadísticas\n'
                    '› `!wrapped` • Resumen anual\n'
                    '› `!topgames` • Top juegos\n'
                    '› `!topvoice` • Ranking tiempo en voz\n'
                    '› `!topconnections` • Ranking conexiones\n'
                    '› `!compare` • Comparar dos usuarios'
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
                name='📈 **Rankings y perfiles**',
                value=(
                    '› `!stats` / `!mystats` • Perfil\n'
                    '› `!topgamers` • Top por juegos\n'
                    '› `!topvoice` • Top por voz\n'
                    '› `!topchat` • Top mensajes (`!topmessages`)\n'
                    '› `!topusers` • Top usuarios (actividad)\n'
                    '› `!topgames` / `!topgame` / `!mygames` • Juegos\n'
                    '› `!topreactions` / `!topstickers` • Social\n'
                    '› `!topconnections` • Conexiones'
                ),
                inline=True
            )
            
            embed.add_field(
                name='✨ **Parties y más**',
                value=(
                    '› `!partymaster` • Quién más arma parties\n'
                    '› `!partywith` • Con quién jugás\n'
                    '› `!partygames` • Juegos con más parties\n'
                    '› `!party` / `!partyhistory` / `!partystats` • Activas e historial\n'
                    '› `!compare` • Comparar usuarios\n'
                    '› `!wrapped` • Resumen anual\n'
                    '› `!statsmenu` • Menú interactivo\n'
                    '› `!export` • Exportar JSON/CSV\n'
                    '› `!checkstats` • Info del archivo de datos'
                ),
                inline=True
            )
            
            embed.set_footer(text='💡 Voz: métricas en !stats; ranking global en !topvoice · Períodos: today, week, month, all')
            await ctx.send(embed=embed)
        
        elif categoria == 'voice':
            # Voz: no hay comandos dedicados tipo !voicetime; se usa stats + topvoice
            embed = discord.Embed(
                title='🎙️ Estadísticas de voz',
                description=(
                    'No hay comandos `!voicetime` / `!voicetop` en esta versión. '
                    'Usá lo siguiente:'
                ),
                color=discord.Color.dark_purple()
            )
            
            embed.add_field(
                name='📊 **Dónde ver voz**',
                value=(
                    '› `!stats` / `!mystats` • Tiempo y sesiones de voz en tu perfil\n'
                    '› `!topvoice` • Ranking por tiempo en voz (alias: `!topvoz`, `!voice`)'
                ),
                inline=False
            )
            
            embed.add_field(
                name='📅 **Períodos** (donde aplique el comando)',
                value=(
                    '› `today` · `week` · `month` · `all`'
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
                    '› `!unsetchannel` 🔒 • Quitar notificaciones\n'
                    '› `!setstatschannel` 🔒 • Configurar stats\n'
                    '› `!unsetstatschannel` 🔒 • Quitar stats\n'
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
                name='📈 **Stats · rankings**',
                value=(
                    '› `!stats` · `!mystats` · `!compare` · `!wrapped`\n'
                    '› `!topgamers` · `!topvoice` · `!topchat` · `!topusers`\n'
                    '› `!topgames` · `!topgame` · `!mygames`\n'
                    '› `!topreactions` · `!topstickers` · `!topconnections`'
                ),
                inline=False
            )
            
            embed2.add_field(
                name='🎉 **Parties**',
                value=(
                    '› `!partymaster` · `!partywith` · `!partygames`\n'
                    '› `!party` · `!partyhistory` · `!partystats`'
                ),
                inline=False
            )

            embed2.add_field(
                name='🛠️ **Utilidades stats**',
                value=(
                    '› `!statsmenu` · `!export` · `!checkstats`'
                ),
                inline=False
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
                    '› Ver tiempo en `!stats` / `!mystats`\n'
                    '› Ranking: `!topvoice`'
                ),
                inline=True
            )
            
            embed3.add_field(
                name='🛠️ **Utilidades**',
                value=(
                    '› `!bothelp` • Ver ayuda\n'
                    '› `!updates` • Últimas novedades\n'
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

    @commands.command(name='updates', aliases=['update', 'novedades', 'changelog'])
    @stats_channel_only()
    async def show_updates(self, ctx, limit: int = 3):
        """
        Muestra las últimas novedades curadas del bot.

        Uso:
        - !updates
        - !updates 5
        """
        limit = max(1, min(limit, 5))
        sections = load_update_sections(limit)

        if not sections:
            await ctx.send('ℹ️ No hay novedades documentadas todavía.')
            return

        embed = discord.Embed(
            title='🚀 Últimas novedades del bot',
            description='Cambios resumidos para usuarios del servidor.',
            color=discord.Color.dark_teal()
        )

        for title, lines in sections:
            value = '\n'.join(lines[:8])
            if len(value) > 1000:
                value = value[:997] + '...'
            embed.add_field(name=title, value=value or 'Sin detalles.', inline=False)

        embed.set_footer(text='Tip: usá !updates 5 para ver más entradas')
        await ctx.send(embed=embed)
    
    @commands.command(name='party', aliases=['parties'])
    @stats_channel_only()
    async def show_parties(self, ctx, game: str = None):
        """
        Muestra las parties activas o jugadores de un juego específico
        
        Uso:
        - !party - Muestra todas las parties activas
        - !party Valorant - Muestra quién está jugando Valorant
        """
        party_manager = self._get_party_manager()
        active_parties = party_manager.get_active_parties()
        
        if not active_parties:
            await ctx.send('🎮 No hay parties activas en este momento')
            return
        
        # Si se especificó un juego, mostrar solo ese
        if game:
            game_lower = game.lower()
            matching_game = None
            
            for game_name in active_parties.keys():
                if game_lower in game_name.lower():
                    matching_game = game_name
                    break
            
            if not matching_game:
                await ctx.send(f'🎮 No hay nadie jugando **{game}** en este momento')
                return
            
            party = active_parties[matching_game]
            players = ', '.join([f'**{name}**' for name in party['player_names']])
            
            embed = discord.Embed(
                title=f'🎮 Party de {matching_game}',
                description=f'{len(party["players"])} jugadores: {players}',
                color=discord.Color.green()
            )
            
            # Calcular duración
            from datetime import datetime
            start_time = datetime.fromisoformat(party['start'])
            duration_minutes = int((datetime.now() - start_time).total_seconds() / 60)
            
            embed.add_field(name='⏱️ Duración', value=f'{duration_minutes} minutos', inline=True)
            embed.add_field(name='👥 Máximo', value=f'{party["max_players"]} jugadores', inline=True)
            
            await ctx.send(embed=embed)
            return
        
        # Mostrar todas las parties activas
        embed = discord.Embed(
            title='🎮 Parties Activas',
            description=f'Hay {len(active_parties)} party(s) activa(s)',
            color=discord.Color.blue()
        )
        
        for game_name, party in active_parties.items():
            players = ', '.join([f'**{name}**' for name in party['player_names']])
            embed.add_field(
                name=f'{game_name} ({len(party["players"])} jugadores)',
                value=players,
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='partyhistory', aliases=['partyhist'])
    @stats_channel_only()
    async def show_party_history(self, ctx, timeframe: str = 'today'):
        """
        Muestra el historial de parties
        
        Uso:
        - !partyhistory [timeframe]
        - Timeframes: today, week, month, all
        """
        if timeframe not in ['today', 'week', 'month', 'all']:
            await ctx.send('⚠️ Timeframe inválido. Usa: today, week, month, all')
            return
        
        party_manager = self._get_party_manager()
        history = party_manager.get_party_history(timeframe, limit=10)
        
        if not history:
            await ctx.send(f'🎮 No hay historial de parties para **{timeframe}**')
            return
        
        timeframe_labels = {
            'today': 'Hoy',
            'week': 'Última Semana',
            'month': 'Último Mes',
            'all': 'Histórico'
        }
        
        embed = discord.Embed(
            title=f'🎮 Historial de Parties - {timeframe_labels[timeframe]}',
            description=f'Mostrando últimas {len(history)} parties',
            color=discord.Color.purple()
        )
        
        for party in history[:10]:
            players = ', '.join([f'**{name}**' for name in party['player_names']])
            duration = party['duration_minutes']
            max_players = party.get('max_players', len(party['players']))
            
            embed.add_field(
                name=f'{party["game"]} ({max_players} jugadores, {duration} min)',
                value=players,
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='partystats')
    @stats_channel_only()
    async def show_party_stats(self, ctx, game: str = None):
        """
        Muestra estadísticas de parties
        
        Uso:
        - !partystats - Muestra stats de todos los juegos
        - !partystats Valorant - Muestra stats de un juego específico
        """
        party_manager = self._get_party_manager()
        all_stats = party_manager.get_game_stats()
        
        if not all_stats:
            await ctx.send('🎮 No hay estadísticas de parties disponibles')
            return
        
        # Si se especificó un juego
        if game:
            game_lower = game.lower()
            matching_game = None
            
            for game_name in all_stats.keys():
                if game_lower in game_name.lower():
                    matching_game = game_name
                    break
            
            if not matching_game:
                await ctx.send(f'🎮 No hay estadísticas de parties para **{game}**')
                return
            
            stats = all_stats[matching_game]
            total_parties = stats.get('total_parties', 0)
            total_duration = stats.get('total_duration_minutes', 0)
            max_players = stats.get('max_players_ever', stats.get('max_players_record', 0))
            unique_players = len(stats.get('total_unique_players', []))
            
            embed = discord.Embed(
                title=f'🎮 Stats de Parties - {matching_game}',
                color=discord.Color.gold()
            )
            
            embed.add_field(name='🎯 Total Parties', value=str(total_parties), inline=True)
            embed.add_field(name='⏱️ Tiempo Total', value=f'{total_duration} min', inline=True)
            embed.add_field(name='👥 Récord Jugadores', value=str(max_players), inline=True)
            embed.add_field(name='👤 Jugadores Únicos', value=str(unique_players), inline=True)
            
            # Top duplas
            if stats.get('most_frequent_pairs'):
                top_pairs = sorted(stats['most_frequent_pairs'].items(), key=lambda x: x[1], reverse=True)[:5]
                pairs_text = '\n'.join([f'{pair}: {count} veces' for pair, count in top_pairs])
                embed.add_field(name='🤝 Duplas Más Frecuentes', value=pairs_text, inline=False)
            
            await ctx.send(embed=embed)
            return
        
        # Mostrar stats generales
        embed = discord.Embed(
            title='🎮 Estadísticas de Parties',
            description=f'Stats de {len(all_stats)} juego(s)',
            color=discord.Color.gold()
        )
        
        # Top juegos por número de parties
        top_games = sorted(all_stats.items(), key=lambda x: x[1].get('total_parties', 0), reverse=True)[:10]
        
        for game_name, stats in top_games:
            total_parties = stats.get('total_parties', 0)
            total_duration = stats.get('total_duration_minutes', 0)
            max_players = stats.get('max_players_ever', stats.get('max_players_record', 0))
            embed.add_field(
                name=f'{game_name}',
                value=f'🎯 {total_parties} parties | ⏱️ {total_duration} min | 👥 Récord {max_players}',
                inline=False
            )
        
        await ctx.send(embed=embed)


async def setup(bot):
    """Función requerida por discord.py para cargar el cog"""
    await bot.add_cog(UtilityCog(bot))

