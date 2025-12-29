"""
Comandos de Parties
!partymaster, !partywith, !partygames
"""

import discord
from discord.ext import commands
import json

from ..visualization import (
    create_ranking_visual,
    format_time,
    format_list_with_commas
)


def setup_party_commands(bot):
    """Registra los comandos de parties"""
    
    @bot.command(name='partymaster', aliases=['topparties', 'partyking'])
    async def partymaster_command(ctx):
        """
        👥 Top usuarios por parties formadas
        
        Uso: !partymaster
        
        Muestra quién ha jugado más en party
        """
        # TODO: Implementar cuando tengamos stats de parties en JSON
        embed = discord.Embed(
            title="🚧 Próximamente",
            description=(
                "Este comando estará disponible pronto!\n\n"
                "**Mostrará:**\n"
                "• Top usuarios por parties formadas\n"
                "• Tiempo total en party\n"
                "• Juegos favoritos para party\n\n"
                "Mientras tanto, usa `!party` para ver parties activas."
            ),
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
    
    
    @bot.command(name='partywith', aliases=['partywho'])
    async def partywith_command(ctx, *, username: str = None):
        """
        👥 Con quién has jugado más en party
        
        Uso: !partywith [usuario]
        
        Sin usuario: muestra tu top companions
        Con usuario: muestra stats de parties con ese usuario
        """
        # TODO: Implementar cuando tengamos stats de parties en JSON
        embed = discord.Embed(
            title="🚧 Próximamente",
            description=(
                "Este comando estará disponible pronto!\n\n"
                "**Mostrará:**\n"
                "• Tus compañeros de party más frecuentes\n"
                "• Juegos que jugaron juntos\n"
                "• Tiempo total en party\n"
                "• Última party juntos\n"
            ),
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)
    
    
    @bot.command(name='partygames', aliases=['toppartygames'])
    async def partygames_command(ctx):
        """
        🎮 Juegos más jugados en party
        
        Uso: !partygames
        
        Muestra qué juegos son más populares para parties
        """
        # TODO: Implementar cuando tengamos stats de parties en JSON
        embed = discord.Embed(
            title="🚧 Próximamente",
            description=(
                "Este comando estará disponible pronto!\n\n"
                "**Mostrará:**\n"
                "• Juegos con más parties formadas\n"
                "• Promedio de jugadores por party\n"
                "• Tiempo total en party por juego\n"
            ),
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

