"""
Comandos de Parties
!partymaster, !partywith, !partygames
"""

import discord
from discord.ext import commands
import json

from core.persistence import STATS_FILE
from ..data.aggregators import aggregate_party_stats
from ..visualization import format_time


def setup_party_commands(bot):
    """Registra los comandos de parties"""

    @bot.command(name='partymaster', aliases=['topparties', 'partyking'])
    async def partymaster_command(ctx):
        """
        👥 Usuarios con más participaciones en parties (historial)
        """
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
        except Exception as e:
            await ctx.send(f"❌ Error al cargar estadísticas: {e}")
            return

        ap = aggregate_party_stats(stats_data)
        by_user = ap.get('by_user') or {}
        if not by_user:
            await ctx.send("📊 Aún no hay parties registradas en el historial.")
            return

        users = stats_data.get('users', {})
        ranked = sorted(by_user.items(), key=lambda x: x[1], reverse=True)[:15]
        lines = []
        for i, (uid, count) in enumerate(ranked, 1):
            name = users.get(uid, {}).get('username', f'ID {uid}')
            lines.append(f"{i}. **{name}** — {count} parties")

        embed = discord.Embed(
            title='👑 Partymaster',
            description='Top por veces que apareciste en una party (historial).',
            color=discord.Color.gold(),
        )
        embed.add_field(name='Ranking', value='\n'.join(lines[:10]), inline=False)
        if len(lines) > 10:
            embed.add_field(name='…', value='\n'.join(lines[10:]), inline=False)
        embed.set_footer(text=f"Total parties en historial: {ap.get('total_parties', 0)}")
        await ctx.send(embed=embed)

    @bot.command(name='partywith', aliases=['partywho'])
    async def partywith_command(ctx, member: discord.Member = None):
        """
        👥 Con quién compartiste más parties (mismo historial)
        """
        target = member or ctx.author
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
        except Exception as e:
            await ctx.send(f"❌ Error al cargar estadísticas: {e}")
            return

        uid = str(target.id)
        ap = aggregate_party_stats(stats_data)
        pairs = ap.get('companion_pairs') or {}
        users_map = stats_data.get('users', {})

        # Parejas donde participó uid
        companions = []
        for (a, b), cnt in pairs.items():
            other = None
            if a == uid:
                other = b
            elif b == uid:
                other = a
            if other is not None:
                oname = users_map.get(other, {}).get('username', f'ID {other}')
                companions.append((oname, cnt))

        companions.sort(key=lambda x: x[1], reverse=True)
        if not companions:
            await ctx.send(
                f"📊 No hay datos de companions en parties para **{target.display_name}**."
            )
            return

        lines = [f"{i}. **{name}** — {c} parties" for i, (name, c) in enumerate(companions[:12], 1)]
        embed = discord.Embed(
            title=f'🤝 Party companions — {target.display_name}',
            description='Basado en historial de parties.',
            color=discord.Color.purple(),
        )
        embed.add_field(name='Top', value='\n'.join(lines), inline=False)
        await ctx.send(embed=embed)

    @bot.command(name='partygames', aliases=['toppartygames'])
    async def partygames_command(ctx):
        """
        🎮 Juegos con más parties formadas (stats_by_game)
        """
        try:
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                stats_data = json.load(f)
        except Exception as e:
            await ctx.send(f"❌ Error al cargar estadísticas: {e}")
            return

        ap = aggregate_party_stats(stats_data)
        sorted_g = ap.get('by_game_sorted') or []
        if not sorted_g:
            await ctx.send("📊 No hay estadísticas de parties por juego todavía.")
            return

        rows = []
        for game_name, data in sorted_g[:12]:
            if not isinstance(data, dict):
                continue
            tp = data.get('total_parties', 0)
            dm = data.get('total_duration_minutes', 0)
            mx = data.get('max_players_ever', 0)
            rows.append((game_name, tp, dm, mx))

        lines = [
            f"**{g}** — {tp} parties · {format_time(dm)} · récord {mx} jug."
            for g, tp, dm, mx in rows
        ]
        embed = discord.Embed(
            title='🎮 Juegos con más parties',
            description='\n'.join(lines),
            color=discord.Color.blue(),
        )
        await ctx.send(embed=embed)
