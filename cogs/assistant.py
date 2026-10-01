"""Explicit invocation only. Disabled unless owner configures provider and scope."""

import asyncio
import logging
import os

import aiohttp
import discord
from discord.ext import commands

from core.assistant import Assistant, AssistantError, Settings, UsageBudget, metrics, bot_help
from core.persistence import DATA_DIR, stats

logger = logging.getLogger("dsbot")


class AssistantCog(commands.Cog, name="Asistente"):
    def __init__(self, bot):
        self.bot = bot
        self.settings = Settings.from_env()
        self.guild_id = int(os.environ["AI_GUILD_ID"])
        self.channel_id = int(os.environ["AI_CHANNEL_ID"])
        self.lock = asyncio.Lock()
        self.cooldowns = commands.CooldownMapping.from_cooldown(1, 3, commands.BucketType.user)
        self.session = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        self.agent = Assistant(self.settings, UsageBudget(DATA_DIR / "assistant_usage.json"), self.session)
        logger.info("Boton ready tools=%s metrics=%s web=%s memory_messages=5", ",".join(bot_help(self.settings, "capabilities")["tools"]), self.settings.share_metrics, bool(self.settings.search_key))

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
                    result = await asyncio.wait_for(self.agent.answer(question, get_metrics, web,
                        conversation_key=(ctx.guild.id, ctx.channel.id, ctx.author.id)), timeout=60)
                await ctx.send(result, allowed_mentions=discord.AllowedMentions.none())
            except AssistantError as exc:
                self.cooldowns.get_bucket(ctx.message).reset()
                await ctx.send(str(exc), allowed_mentions=discord.AllowedMentions.none())
            except asyncio.TimeoutError:
                self.cooldowns.get_bucket(ctx.message).reset()
                await ctx.send("La consulta tardó demasiado; la corté para no seguir consumiendo.")
            except Exception as exc:
                # No questions, response text, credentials or HTTP payloads in logs.
                logger.warning("Assistant failed (%s)", type(exc).__name__)
                await ctx.send("No pude responder. Las estadísticas y el resto del bot siguen funcionando.")

    @commands.command(name="ask", aliases=["pregunta", "boton", "botón"])
    async def ask(self, ctx, *, question: str = ""):
        """!boton pregunta: elige entre métricas, ayuda y búsqueda web habilitadas."""
        await self.respond(ctx, question)

    @commands.command(name="buscar")
    async def search(self, ctx, *, question: str = ""):
        """!buscar ¿Cuánto está el dólar blue hoy? Una búsqueda explícita con fuentes."""
        await self.respond(ctx, question, web=True)

    def in_scope(self, ctx):
        return (not ctx.author.bot and ctx.guild and ctx.guild.id == self.guild_id
                and ctx.channel.id == self.channel_id)

    @commands.command(name="olvidar", aliases=["resetboton"])
    async def forget(self, ctx):
        """Borra sólo tu memoria corta de Botón en este canal; no llama al modelo."""
        if self.in_scope(ctx):
            async with self.lock:
                self.agent.memory.forget((ctx.guild.id, ctx.channel.id, ctx.author.id))
                if hasattr(self.agent, 'pending_questions'):
                    self.agent.pending_questions.pop((ctx.guild.id, ctx.channel.id, ctx.author.id), None)
            await ctx.send("Listo, borré tu memoria corta de Botón en este canal.")

    @commands.command(name="botonestado")
    async def status(self, ctx):
        """Capacidades reales y límites, sin gastar una llamada al modelo."""
        if self.in_scope(ctx):
            flags = bot_help(self.settings, "capabilities")
            tools = ["ayuda pública", "aclaraciones"]
            if flags["metrics_enabled"]:
                tools.append("métricas (sólo lectura)")
            if flags["web_enabled"]:
                tools.append("búsqueda web con fuentes")
            await ctx.send("Botón: " + ", ".join(tools) + ".\nWeb: citas verificadas; una búsqueda nueva no arrastra respuestas anteriores.\nMemoria: últimos 5 mensajes tuyos y míos, por persona/canal; RAM, vence tras 30 min sin uso. !olvidar la borra. No guarda resultados privados.\nLímites: anti-spam 3 segundos; 3 llamadas de modelo y 2 herramientas por pregunta; 40 llamadas/día; web 20 llamadas/día y 600/mes (búsqueda y extracción cuentan por separado). Sin ejecución ni escritura de datos.")

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Esperá {error.retry_after:.0f} segundos antes de otra consulta.")


async def setup(bot):
    await bot.add_cog(AssistantCog(bot))
