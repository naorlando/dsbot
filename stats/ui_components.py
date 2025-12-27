"""
Módulo de Componentes UI para Estadísticas
Views, Selects y Buttons para la interfaz interactiva de Discord
"""

import discord
from core.persistence import stats
from stats_viz import filter_by_period, get_period_label
from stats.embeds import (
    create_overview_embed,
    create_games_ranking_embed,
    create_voice_ranking_embed,
    create_messages_ranking_embed,
    create_users_ranking_embed,
    create_timeline_embed
)


class StatsView(discord.ui.View):
    """Vista interactiva para seleccionar diferentes visualizaciones de stats"""
    
    def __init__(self, period='all'):
        super().__init__(timeout=300)
        self.period = period
        self.add_item(StatsSelect(period))
        self.add_item(PeriodSelect())
    
    async def on_timeout(self):
        """Desactiva los componentes cuando expira el timeout"""
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass


class StatsSelect(discord.ui.Select):
    """Select menu para elegir el tipo de visualización"""
    
    def __init__(self, period='all'):
        self.period = period
        
        options = [
            discord.SelectOption(
                label='Vista General',
                description='Resumen completo de estadísticas',
                emoji='📊',
                value='overview'
            ),
            discord.SelectOption(
                label='Ranking Juegos',
                description='Juegos más jugados (gráfico)',
                emoji='🎮',
                value='games'
            ),
            discord.SelectOption(
                label='Ranking Voz',
                description='Usuarios más activos en voz',
                emoji='🔊',
                value='voice'
            ),
            discord.SelectOption(
                label='Ranking Mensajes',
                description='Usuarios más activos en chat',
                emoji='💬',
                value='messages'
            ),
            discord.SelectOption(
                label='Ranking Usuarios',
                description='Actividad total por usuario',
                emoji='👥',
                value='users'
            ),
            discord.SelectOption(
                label='Línea de Tiempo',
                description='Actividad de los últimos 7 días',
                emoji='📈',
                value='timeline'
            ),
        ]
        
        super().__init__(
            placeholder='Selecciona una visualización...',
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        view_type = self.values[0]
        
        # Filtrar datos por período
        filtered_stats = filter_by_period(stats, self.period)
        period_label = get_period_label(self.period)
        
        if view_type == 'overview':
            embed = await create_overview_embed(filtered_stats, period_label)
            await interaction.response.edit_message(embed=embed, view=self.view)
        
        elif view_type == 'games':
            embed = await create_games_ranking_embed(filtered_stats, period_label)
            await interaction.response.edit_message(embed=embed, view=self.view)
        
        elif view_type == 'voice':
            embed = await create_voice_ranking_embed(filtered_stats, period_label)
            await interaction.response.edit_message(embed=embed, view=self.view)
        
        elif view_type == 'messages':
            embed = await create_messages_ranking_embed(filtered_stats, period_label)
            await interaction.response.edit_message(embed=embed, view=self.view)
        
        elif view_type == 'users':
            embed = await create_users_ranking_embed(filtered_stats, period_label)
            await interaction.response.edit_message(embed=embed, view=self.view)
        
        elif view_type == 'timeline':
            embed = await create_timeline_embed(stats, period_label)
            await interaction.response.edit_message(embed=embed, view=self.view)


class PeriodSelect(discord.ui.Select):
    """Select menu para elegir el período de tiempo"""
    
    def __init__(self):
        options = [
            discord.SelectOption(label='Hoy', emoji='📅', value='today'),
            discord.SelectOption(label='Última Semana', emoji='📆', value='week'),
            discord.SelectOption(label='Último Mes', emoji='🗓️', value='month'),
            discord.SelectOption(label='Histórico', emoji='📚', value='all'),
        ]
        
        super().__init__(
            placeholder='Período: Histórico',
            min_values=1,
            max_values=1,
            options=options,
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        period = self.values[0]
        
        # Actualizar el placeholder
        self.placeholder = f'Período: {get_period_label(period)}'
        
        # Crear nueva vista con el período actualizado
        new_view = StatsView(period=period)
        new_view.message = self.view.message
        
        # Mostrar vista general con el nuevo período
        filtered_stats = filter_by_period(stats, period)
        period_label = get_period_label(period)
        embed = await create_overview_embed(filtered_stats, period_label)
        
        await interaction.response.edit_message(embed=embed, view=new_view)

