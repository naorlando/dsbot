"""Explicit invocation only. Disabled unless owner configures provider and scope."""

import asyncio
import json
import logging
import os
from types import SimpleNamespace

from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands, tasks

from core.assistant import Assistant, AssistantError, Settings, UsageBudget, metrics, bot_help
from core.channel_dialogue import ChannelDialogue
from core.assistant_scope import channel_in_scope, public_thread
from core.assistant_quota import UserDailyQuota, QuotaError
from core.assistant_operations import operations, provider_health
from core.assistant_data import day_digest, query_stats as query_stats_data
from core.assistant_history import scan_history, _row_from
from core.banter_ledger import BanterLedger
from core.channel_curator import ChannelCurator
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
        self.warm_channels = set()
        self.thread_ids = set()
        self.user_quota = None  # Created only on cog_load, never during pure tests.
        self.curator_budget = None
        self.last_curator_attempt = None
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
                               if self.channel_memory_enabled and self.settings.history_enabled else None)
        self.user_quota = UserDailyQuota(DATA_DIR / "assistant_users.json")
        self.curator_budget = UsageBudget(DATA_DIR / "assistant_curator_usage.json", llm_limit=24)
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
                    or not self._channel_allowed(message.channel)):
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
                    # Internal provenance only. The curator strips these IDs from
                    # its LLM snapshot and reattaches them after literal matching.
                    row.update(message_id=str(message.id), channel_id=str(message.channel.id))
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

    def _channel_allowed(self, channel):
        if not channel_in_scope(channel, self.channel_id):
            return False
        if public_thread(channel, self.channel_id):
            if len(self.thread_ids) >= 128 and channel.id not in self.thread_ids:
                return False
            self.thread_ids.add(channel.id)
        return True

    def _raw_in_scope(self, payload):
        if getattr(payload, "guild_id", None) != self.guild_id:
            return False
        channel_id = getattr(payload, "channel_id", None)
        if channel_id == self.channel_id or channel_id in self.thread_ids:
            return True
        lookup = getattr(self.bot, "get_channel", None)
        channel = lookup(channel_id) if callable(lookup) else None
        return channel is not None and self._channel_allowed(channel)

    def _invalidate_source(self, message_id, channel_id):
        if self.curator is not None:
            # Cold-cache deletes from a previously visited public thread still
            # revoke stored evidence. Unrelated channels must not continually
            # invalidate snapshots or trigger privacy-marker disk writes.
            known = channel_id == self.channel_id or channel_id in self.thread_ids
            if not known:
                metadata = getattr(self.curator, 'metadata', None)
                known = callable(metadata) and any(
                    str(source.get('message_id')) == str(message_id)
                    and str(source.get('channel_id')) == str(channel_id)
                    for bullet in metadata() for source in bullet['sources'])
            if not known:
                return
            self.curator.invalidate_message(message_id, channel_id)

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
        if (self.settings.history_enabled and getattr(message.guild, "id", None) == self.guild_id
                and self._channel_allowed(message.channel)):
            self.dialogue.remove(message.id)
            self._invalidate_source(message.id, message.channel.id)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if (self.settings.history_enabled and getattr(after.guild, "id", None) == self.guild_id
                and self._channel_allowed(after.channel)):
            self._invalidate_source(after.id, after.channel.id)
            self._sync_dialogue_bot()
            self.dialogue.observe(after)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        if self.settings.history_enabled and payload.guild_id == self.guild_id:
            self._invalidate_source(payload.message_id, payload.channel_id)
        if self.settings.history_enabled and self._raw_in_scope(payload):
            self.dialogue.remove(payload.message_id)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload):
        if self.settings.history_enabled and payload.guild_id == self.guild_id:
            for message_id in payload.message_ids:
                self._invalidate_source(message_id, payload.channel_id)
        if self.settings.history_enabled and self._raw_in_scope(payload):
            for message_id in payload.message_ids:
                self.dialogue.remove(message_id)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        if (self.settings.history_enabled and payload.guild_id == self.guild_id
                and isinstance(payload.data, dict) and isinstance(payload.data.get('content'), str)):
            self._invalidate_source(payload.message_id, payload.channel_id)
        if (self.settings.history_enabled and self._raw_in_scope(payload)
                and isinstance(payload.data, dict) and isinstance(payload.data.get('content'), str)):
            self.dialogue.edit(payload.message_id, payload.data['content'], payload.data.get('mentions', ()))

    async def _warm_start(self, channel):
        """One bounded warm start; failure never blocks a question or triggers retries."""
        channel_id = getattr(channel, "id", self.channel_id)
        if (channel_id in self.warm_channels or not self.settings.history_enabled
                or len(self.warm_channels) >= 129):
            return
        self.warm_channels.add(channel_id)
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
        """Background only, with its own persisted 24-call daily budget."""
        if (self.curator is None or self.lock.locked() or len(self.bot.guilds) != 1
                or not self.curator.due()):
            return
        try:
            async def summarize(messages, tools):
                self.last_curator_attempt = datetime.now(timezone.utc).isoformat()
                return await self.agent.completion(messages, tools, total=18, max_tokens=1600,
                                                   usage_budget=self.curator_budget)
            await self.curator.curate(summarize)
        except Exception as exc:
            logger.info("Curator skipped (%s)", type(exc).__name__)

    async def respond(self, ctx, question, web=False):
        if not self.in_scope(ctx):
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
                if self.user_quota is not None:
                    self.user_quota.consume(ctx.author.id)
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
            except (AssistantError, QuotaError) as exc:
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
                and self._channel_allowed(ctx.channel))

    def _is_owner(self, ctx):
        owner = os.getenv("DISCORD_OWNER_ID", "")
        return bool(owner and str(ctx.author.id) == owner and self.in_scope(ctx))

    @commands.command(name="botonmetricas")
    async def operational_status(self, ctx):
        """Owner-only aggregates: no questions, answers, names or user identifiers."""
        if not self._is_owner(ctx):
            return
        try:
            counters = self.agent.budget.snapshot()
            ambient = getattr(self.bot, "commentator", None)
            ambient_counters = ambient.budget.snapshot() if ambient is not None else None
            report = {"preguntas": counters, "avisos": ambient_counters,
                      "curador": self.curator_budget.snapshot() if self.curator_budget is not None else None,
                      "cuota_usuarios": self.user_quota.snapshot() if self.user_quota is not None else None,
                      "ultimo_intento_curador_utc_desde_reinicio": self.last_curator_attempt,
                      "operacion_desde_reinicio": operations.snapshot(),
                      "proveedores": provider_health.snapshot()}
        except (AssistantError, QuotaError):
            await ctx.send("No puedo verificar los contadores; las llamadas se bloquean por seguridad.")
            return
        # Snapshots contain only bounded operational counters. Keep payloads out
        # of trace logs, and split Discord output without cutting JSON strings.
        for section, values in report.items():
            text = section + ": " + json.dumps(values, ensure_ascii=False, separators=(",", ":"))
            for start in range(0, len(text), 1900):
                await ctx.send(text[start:start + 1900], allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="botonborrar")
    async def remove_source(self, ctx, message_id: str, channel_id: str = ""):
        """Revoke curated evidence by source ID, not a mutable display name."""
        if not self._is_owner(ctx):
            return
        source_channel = channel_id or str(ctx.channel.id)
        if not (message_id.isdecimal() and source_channel.isdecimal()
                and 0 < int(message_id) < 2**64 and 0 < int(source_channel) < 2**64):
            await ctx.send("Usá !botonborrar ID_MENSAJE [ID_CANAL], con IDs válidos.")
            return
        if self.curator is None:
            await ctx.send("La memoria curada está desactivada.")
            return
        try:
            result = self.curator.invalidate_message(message_id, source_channel)
        except OSError:
            await ctx.send("Quité los recuerdos de RAM, pero no pude asegurar el borrado en disco. "
                           "La memoria quedó bloqueada: revisá el almacenamiento antes de reiniciar.")
            return
        self.dialogue.remove(message_id)
        status = self.curator.status()
        if not status['persisted']:
            await ctx.send("La fuente quedó revocada en RAM y la memoria bloqueada por seguridad; "
                           "no pude completar la escritura en disco. Revisá el almacenamiento.")
            return
        await ctx.send(f"Revocación de esa fuente aplicada a la memoria curada ({result}). "
                       "No borra mensajes de Discord ni usa nombres para borrar chanzas.",
                       allowed_mentions=discord.AllowedMentions.none())

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
                "400 llamadas/día para preguntas + 240/día por defecto para avisos + 24/día del curador; "
                "40 invocaciones por usuario/día; web 20/día y 600/mes. "
                "Sin ejecutar código ni cambiar estadísticas; con memoria opt-in anota chanzas o apuestas "
                "explícitas en un ledger acotado. Incluye hilos públicos del canal; privados no.\n"
                f"Resumen del día automático a las {self.digest_hour:02d}:00 UTC.",
                allowed_mentions=discord.AllowedMentions.none())

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"Esperá {error.retry_after:.0f} segundos antes de otra consulta.")


async def setup(bot):
    await bot.add_cog(AssistantCog(bot))
