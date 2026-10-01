"""Explicit invocation only. Disabled unless owner configures provider and scope."""

import asyncio
import logging
import os

import aiohttp
import discord
from discord.ext import commands

from core.assistant import Assistant, AssistantError, Settings, UsageBudget, metrics
from core.persistence import DATA_DIR, stats

logger = logging.getLogger("dsbot")


class AssistantCog(commands.Cog, name="Asistente"):
    def __init__(self, bot):
        self.bot = bot
        self.settings = Settings.from_env()
        self.guild_id = int(os.environ["AI_GUILD_ID"])
        self.channel_id = int(os.environ["AI_CHANNEL_ID"])
        self.lock = asyncio.Lock()
        self.cooldowns = commands.CooldownMapping.from_cooldown(1, 45, commands.BucketType.user)
        self.session = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        self.agent = Assistant(self.settings, UsageBudget(DATA_DIR / "assistant_usage.json"), self.session)

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    async def respond(self, ctx, question, web=False):
        if ctx.author.bot or not ctx.guild or ctx.guild.id != self.guild_id or ctx.channel.id != self.channel_id:
            return
        # Existing stats are global by user, not guild-scoped. Refuse multi-server
        # installations until the persistence model can guarantee isolation.
        if len(self.bot.guilds) != 1:
            await ctx.send("El asistente requiere un bot en un único servidor para proteger las métricas.")
            return
        if self.lock.locked():
            await ctx.send("Estoy respondiendo otra consulta; probá en unos segundos.")
            return
        retry_after = self.cooldowns.get_bucket(ctx.message).update_rate_limit()
        if retry_after:
            await ctx.send(f"Esperá {retry_after:.0f} segundos antes de otra consulta.")
            return
        async with self.lock:
            members = {str(m.id): m.display_name for m in ctx.guild.members if not m.bot}
            def get_metrics(view, period):
                return metrics(stats, members, ctx.author.id, view, period)
            try:
                async with ctx.typing():
                    result = await asyncio.wait_for(self.agent.answer(question, get_metrics, web), timeout=60)
                await ctx.send(result, allowed_mentions=discord.AllowedMentions.none())
            except AssistantError as exc:
                await ctx.send(str(exc), allowed_mentions=discord.AllowedMentions.none())
            except asyncio.TimeoutError:
                await ctx.send("La consulta tardó demasiado; la corté para no seguir consumiendo.")
            except Exception as exc:
                # No questions, response text, credentials or HTTP payloads in logs.
                logger.warning("Assistant failed (%s)", type(exc).__name__)
                await ctx.send("No pude responder. Las estadísticas y el resto del bot siguen funcionando.")

    @commands.command(name="ask", aliases=["pregunta"])
    async def ask(self, ctx, *, question: str = ""):
        """!ask ¿Quién jugó más esta semana? No realiza búsquedas web."""
        await self.respond(ctx, question)

    @commands.command(name="buscar")
    async def search(self, ctx, *, question: str = ""):
        """!buscar ¿Cuánto está el dólar blue hoy? Una búsqueda explícita con fuentes."""
        await self.respond(ctx, question, web=True)

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Esperá {error.retry_after:.0f} segundos antes de otra consulta.")


async def setup(bot):
    await bot.add_cog(AssistantCog(bot))
