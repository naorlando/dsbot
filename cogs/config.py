"""
Cog de Configuration - Comandos de configuración del bot
"""

import discord
from discord.ext import commands
import logging

from core.persistence import config, save_config, get_channel_id, get_stats_channel_id
from core.helpers import send_notification
from core.checks import is_owner

logger = logging.getLogger('dsbot')


class ToggleView(discord.ui.View):
    """Vista con botones para toggle de notificaciones"""
    def __init__(self):
        super().__init__(timeout=300)
    
    def create_toggle_button(self, label, key, emoji):
        button = ToggleButton(label, key, emoji)
        self.add_item(button)
        return button


class ToggleButton(discord.ui.Button):
    """Botón para activar/desactivar notificaciones"""
    def __init__(self, label, key, emoji):
        current_value = config.get(key, False)
        style = discord.ButtonStyle.success if current_value else discord.ButtonStyle.secondary
        super().__init__(label=label, emoji=emoji, style=style)
        self.key = key
        self.label_text = label
        self.emoji_text = emoji
    
    async def callback(self, interaction):
        current_value = config.get(self.key, False)
        config[self.key] = not current_value
        new_status = 'activado' if config[self.key] else 'desactivado'
        
        # Guardar configuración
        save_config()
        
        # Actualizar el botón
        self.style = discord.ButtonStyle.success if config[self.key] else discord.ButtonStyle.secondary
        
        await interaction.response.send_message(
            f'{self.emoji_text} **{self.label_text}** {new_status.capitalize()}',
            ephemeral=True
        )
        await interaction.message.edit(view=self.view)


class ConfigCog(commands.Cog, name='Configuration'):
    """Comandos de configuración del bot"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='setchannel')
    async def set_channel(self, ctx, channel: discord.TextChannel = None):
        """Configura el canal donde se enviarán las notificaciones (solo owner)
        
        Ejemplo: !setchannel o !setchannel #canal
        """
        # Verificar que solo el owner pueda usar este comando
        if not is_owner(ctx):
            await ctx.send('❌ Solo el owner del bot puede usar este comando.')
            return
        
        if channel is None:
            channel = ctx.channel
        
        # Verificar que el bot tenga permisos
        bot_member = channel.guild.get_member(self.bot.user.id)
        if bot_member:
            permissions = channel.permissions_for(bot_member)
            if not permissions.send_messages:
                try:
                    await ctx.send(f'❌ El bot no tiene permisos para enviar mensajes en {channel.mention}.')
                except:
                    logger.error(f'⚠️  Bot sin permisos en canal {channel.name} (ID: {channel.id})')
                return
        
        config['channel_id'] = channel.id
        save_config()
        
        await ctx.send(f'✅ Canal de notificaciones configurado: {channel.mention}\n💡 **Recomendación:** Configura `DISCORD_CHANNEL_ID={channel.id}` en Railway para que nunca se pierda.')
        logger.info(f'Canal configurado: {channel.name} (ID: {channel.id})')
    
    @commands.command(name='unsetchannel', aliases=['removechannel', 'clearchannel'])
    async def unset_channel(self, ctx):
        """Desconfigura el canal de notificaciones (solo owner)
        
        Ejemplo: !unsetchannel
        """
        # Verificar que solo el owner pueda usar este comando
        if not is_owner(ctx):
            await ctx.send('❌ Solo el owner del bot puede usar este comando.')
            return
        
        channel_id = get_channel_id()
        if not channel_id:
            await ctx.send('ℹ️ No hay canal configurado.')
            return
        
        old_channel = self.bot.get_channel(channel_id)
        channel_name = old_channel.name if old_channel else f'ID: {channel_id}'
        
        config['channel_id'] = None
        save_config()
        
        await ctx.send(f'✅ Canal desconfigurado: `#{channel_name}`')
        logger.info(f'Canal desconfigurado: {channel_name}')
    
    @commands.command(name='setstatschannel', aliases=['statscanal'])
    async def set_stats_channel(self, ctx, channel: discord.TextChannel = None):
        """Configura el canal donde se enviarán las respuestas de comandos de estadísticas (solo owner)
        
        Ejemplo: !setstatschannel o !setstatschannel #stats
        """
        # Verificar que solo el owner pueda usar este comando
        if not is_owner(ctx):
            await ctx.send('❌ Solo el owner del bot puede usar este comando.')
            return
        
        if channel is None:
            channel = ctx.channel
        
        # Verificar que el bot tenga permisos
        bot_member = channel.guild.get_member(self.bot.user.id)
        if bot_member:
            permissions = channel.permissions_for(bot_member)
            if not permissions.send_messages:
                try:
                    await ctx.send(f'❌ El bot no tiene permisos para enviar mensajes en {channel.mention}.')
                except:
                    logger.error(f'⚠️  Bot sin permisos en canal de stats {channel.name} (ID: {channel.id})')
                return
        
        config['stats_channel_id'] = channel.id
        save_config()
        
        await ctx.send(
            f'📊 Canal de estadísticas configurado: {channel.mention}\n'
            '💡 Los comandos protegidos con canal stats (`!bothelp`, `!party`, `!export`, '
            '`!statsmenu`, `!topconnections`, etc.) solo responderán en este canal.\n'
            f'💡 **Recomendación:** Configura `DISCORD_STATS_CHANNEL_ID={channel.id}` en Railway para que nunca se pierda.'
        )
        logger.info(f'Canal de stats configurado: {channel.name} (ID: {channel.id})')
    
    @commands.command(name='unsetstatschannel', aliases=['removestatschannel', 'clearstatschannel'])
    async def unset_stats_channel(self, ctx):
        """Desconfigura el canal de estadísticas (solo owner)
        
        Ejemplo: !unsetstatschannel
        """
        # Verificar que solo el owner pueda usar este comando
        if not is_owner(ctx):
            await ctx.send('❌ Solo el owner del bot puede usar este comando.')
            return
        
        stats_channel_id = get_stats_channel_id()
        if not stats_channel_id:
            await ctx.send('ℹ️ No hay canal de estadísticas configurado.')
            return
        
        old_channel = self.bot.get_channel(stats_channel_id)
        channel_name = old_channel.name if old_channel else f'ID: {stats_channel_id}'
        
        config['stats_channel_id'] = None
        save_config()
        
        await ctx.send(f'✅ Canal de estadísticas desconfigurado: `#{channel_name}`\nAhora los comandos de stats funcionarán en cualquier canal.')
        logger.info(f'Canal de stats desconfigurado: {channel_name}')
    
    @commands.command(name='channels', aliases=['canales', 'showchannels'])
    async def show_channels(self, ctx):
        """Muestra la configuración actual de canales
        
        Ejemplo: !channels
        """
        embed = discord.Embed(
            title='📺 Canales Configurados',
            description='› Configuración actual de los canales del bot',
            color=discord.Color.dark_embed()
        )
        
        embed.add_field(name='', value='', inline=False)
        
        # Canal de notificaciones
        channel_id = get_channel_id()
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                embed.add_field(
                    name='🔔 **Notificaciones**',
                    value=f'› {channel.mention}\n› `{channel_id}`',
                    inline=True
                )
            else:
                embed.add_field(
                    name='🔔 **Notificaciones**',
                    value=f'› ⚠️ Canal no encontrado\n› `{channel_id}`',
                    inline=True
                )
        else:
            embed.add_field(
                name='🔔 **Notificaciones**',
                value='› ❌ Sin configurar\n› Usa `!setchannel`',
                inline=True
            )
        
        # Canal de estadísticas
        stats_channel_id = get_stats_channel_id()
        if stats_channel_id:
            stats_channel = self.bot.get_channel(stats_channel_id)
            if stats_channel:
                embed.add_field(
                    name='📊 **Estadísticas**',
                    value=f'› {stats_channel.mention}\n› `{stats_channel_id}`',
                    inline=True
                )
            else:
                embed.add_field(
                    name='📊 **Estadísticas**',
                    value=f'› ⚠️ Canal no encontrado\n› `{stats_channel_id}`',
                    inline=True
                )
        else:
            embed.add_field(
                name='📊 **Estadísticas**',
                value='› ℹ️ Sin configurar\n› (funcionan en cualquier canal)',
                inline=True
            )
        
        embed.add_field(name='', value='', inline=False)
        embed.set_footer(text='🔒 Solo owners pueden cambiar estos canales')
        
        await ctx.send(embed=embed)
    
    @commands.command(name='toggle')
    async def toggle_notification(self, ctx, notification_type: str = None):
        """Activa o desactiva tipos de notificaciones usando botones interactivos
        
        Ejemplos:
        - !toggle - Abre el menú interactivo
        - !toggle games - Activa/desactiva juegos directamente
        """
        if notification_type is None:
            # Crear embed con botones
            embed = discord.Embed(
                title='🔔 Notificaciones',
                description='› Activa o desactiva los tipos de notificaciones',
                color=discord.Color.dark_embed()
            )
            
            embed.add_field(name='', value='', inline=False)
            
            # Mostrar estado actual
            status_text = (
                f'› 🎮 Juegos: {"✅" if config.get("notify_games") else "⬜"}\n'
                f'› 🔊 Entrada a Voz: {"✅" if config.get("notify_voice") else "⬜"}\n'
                f'› 🔇 Salida de Voz: {"✅" if config.get("notify_voice_leave") else "⬜"}\n'
                f'› 🔄 Cambio de Canal: {"✅" if config.get("notify_voice_move", True) else "⬜"}\n'
                f'› 👋 Miembro se Une: {"✅" if config.get("notify_member_join") else "⬜"}\n'
                f'› 👋 Miembro se Va: {"✅" if config.get("notify_member_leave") else "⬜"}\n'
                f'› 🤖 Ignorar Bots: {"✅" if config.get("ignore_bots") else "⬜"}'
            )
            
            embed.add_field(name='📋 **Estado Actual**', value=status_text, inline=False)
            embed.add_field(name='', value='', inline=False)
            
            # Crear vista con botones
            view = ToggleView()
            view.create_toggle_button('Juegos', 'notify_games', '🎮')
            view.create_toggle_button('Entrada Voz', 'notify_voice', '🔊')
            view.create_toggle_button('Salida Voz', 'notify_voice_leave', '🔇')
            view.create_toggle_button('Cambio Canal', 'notify_voice_move', '🔄')
            view.create_toggle_button('Miembro Une', 'notify_member_join', '👋')
            view.create_toggle_button('Miembro Va', 'notify_member_leave', '👋')
            view.create_toggle_button('Ignorar Bots', 'ignore_bots', '🤖')
            
            await ctx.send(embed=embed, view=view)
            return
        
        # Método tradicional
        notification_type = notification_type.lower()
        
        toggle_map = {
            'games': 'notify_games',
            'voice': 'notify_voice',
            'voiceleave': 'notify_voice_leave',
            'voicemove': 'notify_voice_move',
            'memberjoin': 'notify_member_join',
            'memberleave': 'notify_member_leave'
        }
        
        if notification_type not in toggle_map:
            await ctx.send('❌ Tipo no válido. Usa: `games`, `voice`, `voiceleave`, `voicemove`, `memberjoin`, `memberleave`')
            return
        
        config_key = toggle_map[notification_type]
        config[config_key] = not config.get(config_key, False)
        status = 'activadas' if config[config_key] else 'desactivadas'
        
        save_config()
        
        await ctx.send(f'✅ Notificaciones de {notification_type} {status}')
    
    @commands.command(name='config')
    async def show_config(self, ctx):
        """Muestra la configuración actual del bot"""
        channel_id = get_channel_id()
        channel_mention = 'No configurado'
        
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                channel_mention = channel.mention
        
        embed = discord.Embed(
            title='⚙️ Configuración Actual',
            description='› Resumen de la configuración del bot',
            color=discord.Color.dark_embed()
        )
        
        embed.add_field(name='', value='', inline=False)
        
        embed.add_field(
            name='📺 **Canal de Notificaciones**',
            value=f'› {channel_mention}',
            inline=False
        )
        
        embed.add_field(name='', value='', inline=False)
        
        # Notificaciones en columnas
        embed.add_field(
            name='🎮 Juegos',
            value='✅' if config.get('notify_games') else '⬜',
            inline=True
        )
        embed.add_field(
            name='🔊 Entrada Voz',
            value='✅' if config.get('notify_voice') else '⬜',
            inline=True
        )
        embed.add_field(
            name='🔇 Salida Voz',
            value='✅' if config.get('notify_voice_leave') else '⬜',
            inline=True
        )
        embed.add_field(
            name='🔄 Cambio Canal',
            value='✅' if config.get('notify_voice_move', True) else '⬜',
            inline=True
        )
        embed.add_field(
            name='👋 Usuario Entra',
            value='✅' if config.get('notify_member_join', False) else '⬜',
            inline=True
        )
        embed.add_field(
            name='👋 Usuario Sale',
            value='✅' if config.get('notify_member_leave', False) else '⬜',
            inline=True
        )
        
        embed.set_footer(text='💡 Usa !toggle para cambiar notificaciones')
        
        await ctx.send(embed=embed)
    
    @commands.command(name='test')
    async def test_notification(self, ctx):
        """Envía un mensaje de prueba al canal configurado
        
        Ejemplo: !test
        """
        channel_id = get_channel_id()
        if not channel_id:
            await ctx.send('⚠️ No hay canal configurado. Usa `!setchannel` primero.')
            return
        
        # Solo enviar al canal configurado
        await send_notification('🧪 **Mensaje de prueba** - El bot funciona correctamente!', self.bot)
        
        # Si el comando se ejecutó en otro canal, confirmar ahí
        if ctx.channel.id != channel_id:
            try:
                await ctx.send(f'✅ Mensaje de prueba enviado a <#{channel_id}>')
            except discord.errors.Forbidden:
                logger.error(f'⚠️ No se pudo enviar confirmación en el canal {ctx.channel.name}')


async def setup(bot):
    """Función requerida para cargar el cog"""
    await bot.add_cog(ConfigCog(bot))

