"""Explicit invocation only. Disabled unless owner configures provider and scope."""

import asyncio
import logging
import os
from types import SimpleNamespace

from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands, tasks

from core.assistant import Assistant, AssistantError, Settings, UsageBudget, metrics, bot_help
from core.channel_dialogue import ChannelDialogue
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
        # Shared channel dialogue includes summons and our own replies. RAM only;
        # curated durable notes remain a separate, opt-in subsystem.
        self.dialogue = ChannelDialogue(self.guild_id, self.channel_id)
        self.warm_started = False
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
        logger.info("Boton ready tools=%s metrics=%s web=%s dialogue_messages=100",
                    ",".join(bot_help(self.settings, "capabilities")["tools"]),
                    self.settings.share_metrics, bool(self.settings.search_key))

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
        """Capture scoped dialogue; a direct mention/reply is also an invocation."""
        try:
            if (message.guild is None
                    or message.guild.id != self.guild_id or len(self.bot.guilds) != 1
                    or message.channel.id != self.channel_id):
                return
            self._sync_dialogue_bot()
            accepted = self.dialogue.observe(message) if self.settings.history_enabled else False
            if accepted and not message.author.bot and self.curator is not None:
                # A statement inside !boton is still something a human said.
                # Do not exclude the entire conversation just because it invoked us.
                source = message
                if message.content.lstrip().startswith("!"):
                    parts = message.content.split(maxsplit=1)
                    source = SimpleNamespace(author=message.author, created_at=message.created_at,
                                             content=parts[1] if len(parts) > 1 else "")
                row = _row_from(source)
                if row:
                    self.curator.observe(row)
            if message.author.bot or message.content.lstrip().startswith("!"):
                return
            bot_id = self.dialogue.bot_id
            mentions = getattr(message, "mentions", [])
            mentioned = bot_id is not None and any(getattr(who, "id", None) == bot_id for who in mentions)
            # Use one resolver for invocation and rendering, including deleted-parent tombstones.
            replied = self.dialogue.reply_is_own(message)
            if mentioned or replied:
                text = message.content.replace(f"<@{bot_id}>", "").replace(f"<@!{bot_id}>", "").strip()
                ctx = await self.bot.get_context(message)
                await self.respond(ctx, text)
        except (AttributeError, TypeError):
            return

    def _sync_dialogue_bot(self):
        bot_id = getattr(getattr(self.bot, "user", None), "id", None)
        if isinstance(bot_id, int) and not isinstance(bot_id, bool):
            self.dialogue.bot_id = bot_id

    def _invocation_message(self, ctx, question):
        """Use the actual Discord message; tolerate minimal command test contexts."""
        message = ctx.message
        if getattr(message, "guild", None) is not None and getattr(message, "channel", None) is not None:
            return message
        return SimpleNamespace(id=getattr(message, "id", None), guild=ctx.guild, channel=ctx.channel,
            author=ctx.author, created_at=datetime.now(timezone.utc), content="!boton " + question,
            mentions=getattr(message, "mentions", []), reference=getattr(message, "reference", None))

    async def _reply(self, ctx, text):
        """Link outputs to the actual request and immediately capture our answer."""
        reply = getattr(ctx, "reply", None)
        if callable(reply):
            sent = await reply(text, mention_author=False, allowed_mentions=discord.AllowedMentions.none())
        else:
            sent = await ctx.send(text, allowed_mentions=discord.AllowedMentions.none())
        self._sync_dialogue_bot()
        if self.settings.history_enabled:
            self.dialogue.observe(sent)
        return sent

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if getattr(message.channel, "id", None) == self.channel_id:
            self.dialogue.remove(message.id)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if self.settings.history_enabled and getattr(after.channel, "id", None) == self.channel_id:
            self._sync_dialogue_bot()
            self.dialogue.observe(after)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        if (self.settings.history_enabled and payload.guild_id == self.guild_id
                and payload.channel_id == self.channel_id):
            self.dialogue.remove(payload.message_id)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload):
        if (self.settings.history_enabled and payload.guild_id == self.guild_id
                and payload.channel_id == self.channel_id):
            for message_id in payload.message_ids:
                self.dialogue.remove(message_id)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        if (self.settings.history_enabled and payload.guild_id == self.guild_id
                and payload.channel_id == self.channel_id
                and isinstance(payload.data, dict) and isinstance(payload.data.get('content'), str)):
            self.dialogue.edit(payload.message_id, payload.data['content'], payload.data.get('mentions', ()))

    async def _warm_start(self, channel):
        """One bounded warm start; failure never blocks a question or triggers retries."""
        if self.warm_started or not self.settings.history_enabled:
            return
        self.warm_started = True
        if not callable(getattr(channel, "history", None)):
            return
        try:
            async def collect():
                return [row async for row in channel.history(limit=100, oldest_first=False)]
            rows = await asyncio.wait_for(collect(), timeout=3)
            self._sync_dialogue_bot()
            for row in reversed(rows):
                self.dialogue.observe(row, historical=True)
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
                    await self._warm_start(ctx.channel)
                    self._sync_dialogue_bot()
                    message = self._invocation_message(ctx, question)
                    # The current invocation is separate, not duplicated as old chat.
                    if self.settings.history_enabled:
                        self.dialogue.observe(message)
                    channel_context = self.dialogue.render(current_message=message) \
                        if self.settings.history_enabled and not web else ""
                    invocation = self.dialogue.invocation(message, question) if not web else None
                    notes = self.curator.digest() if self.curator is not None and not web else ""
                    result = await asyncio.wait_for(self.agent.answer(question, get_metrics, web,
                        conversation_key=(ctx.guild.id, ctx.channel.id),
                        query_data=query_data,
                        history_search=history_lookup if self.settings.history_enabled else None,
                        ambient_digest=notes, dialogue_context=channel_context, invocation=invocation),
                        timeout=self.answer_timeout)
                await self._reply(ctx, result)
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
        """Compatibility notice: there are no individual Discord chat sessions."""
        if self.in_scope(ctx):
            await ctx.send("Ahora la conversación es compartida por canal, no un chat por usuario. "
                           "Este comando antiguo no borra el diálogo ni los recuerdos del grupo.",
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
                "Diálogo compartido: hasta 100 mensajes, con autores, nuestras respuestas y replies. "
                "Prioridad a los últimos 24 turnos de la última hora.\n"
                "No hay sesiones separadas por usuario: todos comparten el contexto de este canal.\n"
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
