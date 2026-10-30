"""Explicit invocation only. Disabled unless owner configures provider and scope."""

import asyncio
import logging
import os
from collections import deque

from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands, tasks

from core.assistant import Assistant, AssistantError, Settings, UsageBudget, metrics, bot_help
from core.ambient import ambient
from core.assistant_data import day_digest, query_stats as query_stats_data
from core.assistant_history import scan_history, _row_from
from core.banter_ledger import BanterLedger
from core.channel_curator import ChannelCurator
from core.knowledge import KnowledgeStore
from core.commentator import Commentator, maybe_compose, template_digest
from core.persistence import DATA_DIR, stats

logger = logging.getLogger("dsbot")


class AssistantCog(commands.Cog, name="Asistente"):
    def __init__(self, bot):
        self.bot = bot
        self.settings = Settings.from_env()
        self.guild_id = int(os.environ["AI_GUILD_ID"])
        self.channel_id = int(os.environ["AI_CHANNEL_ID"])
        self.lock = asyncio.Lock()
        # Question fence: the wait_for cap in respond(). Coherent with the
        # per-provider hard cuts in core.assistant (PROVIDER_TIMEOUT/ROUTER_TIMEOUT);
        # both layers must fire before Discord looks dead.
        self.answer_timeout = 60.0
        # Rolling buffer of recent channel messages: the raw material for the
        # ambient digest passed to the agent each question. RAM only, never
        # persisted (same contract as the conversation memory).
        self.ambient_rows = deque(maxlen=100)
        self.ambient_loaded = False
        self.channel_memory_enabled = os.getenv("AI_CHANNEL_MEMORY", "false").lower() == "true"
        self.curator = None
        self.cooldowns = commands.CooldownMapping.from_cooldown(1, 3, commands.BucketType.user)
        self.session = None
        try:
            self.digest_hour = int(os.getenv("AI_DIGEST_HOUR_UTC", "21"))
        except ValueError:
            self.digest_hour = 21
        self.digest_hour = self.digest_hour % 24
        self.digest_last = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        channel_data = DATA_DIR / "channel_memory" / f"{self.guild_id}_{self.channel_id}"
        self.agent = Assistant(self.settings, UsageBudget(DATA_DIR / "assistant_usage.json"), self.session,
                               banter=BanterLedger(channel_data / "banter.json")
                               if self.channel_memory_enabled and self.settings.history_enabled else None,
                               knowledge=KnowledgeStore())
        if self.channel_memory_enabled and self.settings.history_enabled:
            self.curator = ChannelCurator(channel_data / "channel_curator.json", min_messages=40,
                interval_seconds=2 * 3600, temporal_min_messages=10,
                min_gap_seconds=900, retry_seconds=1800, max_daily=24)
            self.curator_loop.start()
        # Ambient commentator shares the session but has its own daily budget.
        self.bot.commentator = Commentator(
            self.session,
            UsageBudget(DATA_DIR / "assistant_ambient.json",
                        ambient_limit=int(os.getenv("AI_AMBIENT_LIMIT", "240"))),
            self.settings)
        self.digest_loop.start()
        logger.info("Boton ready tools=%s metrics=%s web=%s memory_messages=10", ",".join(bot_help(self.settings, "capabilities")["tools"]), self.settings.share_metrics, bool(self.settings.search_key))

    async def cog_unload(self):
        self.digest_loop.cancel()
        self.curator_loop.stop()
        self.curator_loop.cancel()
        if self.session:
            await self.session.close()

    @tasks.loop(minutes=30)
    async def digest_loop(self):
        now = datetime.now(timezone.utc)
        if now.hour != self.digest_hour:
            return
        key = now.strftime("%Y-%m-%d")
        if self.digest_last == key:
            return
        guild = self.bot.get_guild(self.guild_id)
        channel = self.bot.get_channel(self.channel_id)
        if not guild or not channel:
            return
        members = {str(m.id): m.display_name for m in guild.members if not m.bot}
        try:
            facts = day_digest(stats, members, now)
            if not facts:
                self.digest_last = key  # nothing tracked: no digest, no retry noise
                return
            composed = await maybe_compose(self.bot, "daily_digest", facts)
            text = composed or template_digest(facts)
            await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
            self.digest_last = key
        except Exception as exc:  # noqa: BLE001 - a nightly digest must never break the bot
            logger.warning("Digest failed (%s)", type(exc).__name__)
            self.digest_last = None  # allow a retry later within the same hour

    @commands.Cog.listener()
    async def on_message(self, message):
        """Maintain the rolling ambient buffer for the assistant channel."""
        try:
            if (not self.settings.history_enabled or message.guild is None
                    or message.guild.id != self.guild_id or len(self.bot.guilds) != 1
                    or message.author.bot or message.channel.id != self.channel_id
                    or not message.content.strip() or message.content.lstrip().startswith("!")):
                return
            self.ambient_rows.append(message)
            if self.curator is not None:
                row = _row_from(message)
                if row:
                    self.curator.observe(row)
        except (AttributeError, TypeError):
            return

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if getattr(message.channel, "id", None) == self.channel_id:
            self.ambient_rows = deque((row for row in self.ambient_rows
                                       if row.id != message.id), maxlen=100)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if getattr(after.channel, "id", None) == self.channel_id:
            self.ambient_rows = deque((after if row.id == after.id else row
                                       for row in self.ambient_rows), maxlen=100)

    async def _load_ambient(self, channel):
        """One bounded warm start; failure never blocks a question or triggers retries."""
        if self.ambient_loaded or not self.settings.history_enabled:
            return
        self.ambient_loaded = True
        if not callable(getattr(channel, "history", None)):
            return
        try:
            async def collect():
                return [row async for row in channel.history(limit=100, oldest_first=False)]
            rows = await asyncio.wait_for(collect(), timeout=3)
            # Preserve messages delivered while the REST request was in flight.
            merged = {row.id: row for row in rows + list(self.ambient_rows)}
            self.ambient_rows = deque(sorted(merged.values(), key=lambda row: row.id)[-100:], maxlen=100)
        except Exception as exc:
            logger.info("Ambient warm start skipped (%s)", type(exc).__name__)

    @tasks.loop(minutes=5)
    async def curator_loop(self):
        """Background only, sharing the normal daily LLM budget."""
        if (self.curator is None or self.lock.locked() or len(self.bot.guilds) != 1
                or not self.curator.due()):
            return
        try:
            async def summarize(messages, tools):
                return await self.agent.completion(messages, tools, total=18, max_tokens=1600)
            await self.curator.curate(summarize)
        except Exception as exc:
            logger.info("Curator skipped (%s)", type(exc).__name__)

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
            def query_data(query_args):
                return query_stats_data(stats, members, query_args)
            async def history_lookup(word):
                return await scan_history(ctx.channel, word, now=datetime.now(timezone.utc))
            try:
                async with ctx.typing():
                    await self._load_ambient(ctx.channel)
                    channel_context = ambient(list(self.ambient_rows), now=datetime.now(timezone.utc),
                                              max_chars=6000, window=100, max_age_days=3) \
                        if self.settings.history_enabled and not web else ""
                    if self.curator is not None and not web:
                        channel_context += "\n" + self.curator.digest()
                    result = await asyncio.wait_for(self.agent.answer(question, get_metrics, web,
                        conversation_key=(ctx.guild.id, ctx.channel.id, ctx.author.id),
                        query_data=query_data,
                        history_search=history_lookup if self.settings.history_enabled else None,
                        ambient_digest=channel_context),
                        timeout=self.answer_timeout)
                await ctx.send(result, allowed_mentions=discord.AllowedMentions.none())
            except AssistantError as exc:
                self.cooldowns.get_bucket(ctx.message).reset()
                await ctx.send(str(exc), allowed_mentions=discord.AllowedMentions.none())
            except asyncio.TimeoutError:
                # wait_for already cancelled the request and released the typing
                # context; never leave the user staring at a dead typing spinner.
                self.cooldowns.get_bucket(ctx.message).reset()
                logger.info("Boton answer timeout fenced after %.0fs", self.answer_timeout)
                await ctx.send("Se me fue la mano con esa consulta; mandá algo más puntual 😅",
                               allowed_mentions=discord.AllowedMentions.none())
            except Exception as exc:
                # No questions, response text, credentials or HTTP payloads in logs.
                logger.warning("Assistant failed (%s)", type(exc).__name__)
                await ctx.send("No pude responder. Las estadísticas y el resto del bot siguen funcionando.")

    @commands.command(name="boton", aliases=["botón"])
    async def ask(self, ctx, *, question: str = ""):
        """!boton pregunta: métricas, historial, web o ayuda, sin comandos extra."""
        await self.respond(ctx, question)

    def in_scope(self, ctx):
        return (not ctx.author.bot and ctx.guild and ctx.guild.id == self.guild_id
                and ctx.channel.id == self.channel_id)

    @commands.command(name="olvidar", aliases=["resetboton"])
    async def forget(self, ctx):
        """Reset opcional de RAM por ID; no borra recuerdos compartidos por nombre."""
        if self.in_scope(ctx):
            if self.lock.locked():
                # Never hang !olvidar behind an in-flight query: it just waits on
                # the same lock today, which looks like "the bot is stuck".
                await ctx.send("Tengo una consulta en curso; mandá !olvidar de nuevo en un momento.")
                return
            async with self.lock:
                self.agent.memory.forget((ctx.guild.id, ctx.channel.id, ctx.author.id))
            await ctx.send("Reinicié sólo tu conversación corta en RAM. No borré el contexto ni los recuerdos del canal.",
                           allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="botonmemoria")
    async def memory_status(self, ctx):
        """Muestra lo que quedó resumido, sin llamar al modelo."""
        if not self.in_scope(ctx):
            return
        if not self.channel_memory_enabled:
            await ctx.send("Memoria persistente del canal desactivada; sólo uso contexto reciente en RAM.")
            return
        notes = self.curator.digest(max_chars=1000) if self.curator is not None else ""
        monitor = ""
        if self.curator is not None:
            self.curator.due()  # Refresh the UTC daily counter, without consuming an attempt.
            monitor = (f"Curador: {self.curator.daily_count}/{self.curator.max_daily} intentos hoy; "
                       f"{self.curator.pending_count} mensajes pendientes.\n")
        ledger = getattr(self.agent, "banter", None)
        jokes = ledger.digest(max_chars=700) if ledger is not None else ""
        await ctx.send(monitor + ((notes + "\n" + jokes).strip() or "Todavía no hay recuerdos guardados."),
                       allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="botonestado")
    async def status(self, ctx):
        """Capacidades reales y límites, sin gastar una llamada al modelo."""
        if self.in_scope(ctx):
            flags = bot_help(self.settings, "capabilities")
            tools = ["ayuda pública", "aclaraciones"]
            if flags["metrics_enabled"]:
                tools.append("métricas y exploración de datos (sólo lectura)")
            if "search_channel_history" in flags["tools"]:
                tools.append("historial del canal (sólo lectura)")
            if flags["web_enabled"]:
                tools.append("búsqueda web con fuentes")
            persistent = "activada" if self.curator is not None else "desactivada"
            await ctx.send("Botón: " + ", ".join(tools) + ".\n"
                "Web: fuentes verificadas; no recibe el contexto privado del canal.\n"
                "Historial: hasta 1000 mensajes / 30 días, 12 coincidencias; puedo reformular la búsqueda.\n"
                "Contexto: hasta 100 mensajes recientes, compactados; no sólo menciones.\n"
                "Memoria corta: últimos 10 mensajes, por persona/canal; RAM, vence tras 30 min.\n"
                f"Memoria persistente del canal: {persistent}. !botonmemoria muestra recuerdos y uso del curador.\n"
                "Límites: anti-spam 3 segundos; hasta 6 pasos de modelo y 4 herramientas por pregunta. "
                "400 llamadas/día; web 20/día y 600/mes. Sin ejecutar código ni cambiar estadísticas.\n"
                f"Resumen del día automático a las {self.digest_hour:02d}:00 UTC.",
                allowed_mentions=discord.AllowedMentions.none())

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Esperá {error.retry_after:.0f} segundos antes de otra consulta.")


async def setup(bot):
    await bot.add_cog(AssistantCog(bot))
