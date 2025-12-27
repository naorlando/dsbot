"""
Módulo de Comandos de Voz
Comandos específicos para estadísticas de tiempo en voz: voicetime, voicetop
"""

import discord
from discord.ext import commands
from datetime import datetime, timedelta
from core.persistence import stats
from core.checks import check_stats_channel
from stats_viz import create_bar_chart


async def setup_voice_commands(bot: commands.Bot):
    """Registra los comandos de voz"""
    
    @bot.command(name='voicetime')
    async def voice_time_cmd(ctx, member: discord.Member = None, period: str = 'all'):
        """
        Muestra el tiempo total en canales de voz
        
        Ejemplos:
        - !voicetime
        - !voicetime @usuario
        - !voicetime @usuario week
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx):
            return
        
        if member is None:
            member = ctx.author
        
        user_id = str(member.id)
        user_data = stats.get('users', {}).get(user_id, {})
        
        if not user_data:
            await ctx.send(f'📊 {member.display_name} no tiene estadísticas registradas.')
            return
        
        voice = user_data.get('voice', {})
        total_minutes = voice.get('total_minutes', 0)
        daily_minutes = voice.get('daily_minutes', {})
        
        # Filtrar por período
        if period == 'today':
            today = datetime.now().strftime('%Y-%m-%d')
            minutes = daily_minutes.get(today, 0)
            period_label = 'Hoy'
        elif period == 'week':
            week_ago = datetime.now() - timedelta(days=7)
            minutes = sum(
                mins for date, mins in daily_minutes.items()
                if datetime.strptime(date, '%Y-%m-%d') >= week_ago
            )
            period_label = 'Esta Semana'
        elif period == 'month':
            month_ago = datetime.now() - timedelta(days=30)
            minutes = sum(
                mins for date, mins in daily_minutes.items()
                if datetime.strptime(date, '%Y-%m-%d') >= month_ago
            )
            period_label = 'Este Mes'
        else:
            minutes = total_minutes
            period_label = 'Total'
        
        # Formatear tiempo
        if minutes < 60:
            time_str = f'{minutes} min'
        elif minutes < 1440:  # < 24 horas
            hours = minutes // 60
            mins = minutes % 60
            time_str = f'{hours}h {mins}m'
        else:
            days = minutes // 1440
            hours = (minutes % 1440) // 60
            time_str = f'{days}d {hours}h'
        
        embed = discord.Embed(
            title=f'🕐 Tiempo en Voz - {member.display_name}',
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name=f'⏱️ {period_label}',
            value=f'**{time_str}** ({minutes} minutos)',
            inline=False
        )
        
        if period == 'all' and len(daily_minutes) > 0:
            # Mostrar últimos 7 días
            recent_days = sorted(daily_minutes.items(), reverse=True)[:7]
            days_text = []
            for date, mins in recent_days:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                day_label = date_obj.strftime('%d/%m')
                if mins < 60:
                    time_label = f'{mins}m'
                else:
                    hours = mins // 60
                    time_label = f'{hours}h {mins % 60}m'
                days_text.append(f'`{day_label}` - {time_label}')
            
            embed.add_field(
                name='📅 Últimos 7 Días',
                value='\n'.join(days_text) if days_text else 'Sin datos',
                inline=False
            )
        
        await ctx.send(embed=embed)

    @bot.command(name='voicetop')
    async def voice_top_time_cmd(ctx, period: str = 'all'):
        """
        Ranking de usuarios por tiempo en voz
        
        Ejemplos:
        - !voicetop
        - !voicetop week
        - !voicetop month
        """
        # Verificar canal de stats
        if not await check_stats_channel(ctx):
            return
        
        # Calcular tiempo por usuario según período
        user_times = []
        
        for user_id, user_data in stats.get('users', {}).items():
            voice = user_data.get('voice', {})
            daily_minutes = voice.get('daily_minutes', {})
            username = user_data.get('username', 'Unknown')
            
            if period == 'today':
                today = datetime.now().strftime('%Y-%m-%d')
                minutes = daily_minutes.get(today, 0)
            elif period == 'week':
                week_ago = datetime.now() - timedelta(days=7)
                minutes = sum(
                    mins for date, mins in daily_minutes.items()
                    if datetime.strptime(date, '%Y-%m-%d') >= week_ago
                )
            elif period == 'month':
                month_ago = datetime.now() - timedelta(days=30)
                minutes = sum(
                    mins for date, mins in daily_minutes.items()
                    if datetime.strptime(date, '%Y-%m-%d') >= month_ago
                )
            else:
                minutes = voice.get('total_minutes', 0)
            
            if minutes > 0:
                user_times.append((username, minutes))
        
        if not user_times:
            await ctx.send(f'📊 No hay tiempo registrado en voz para {period}.')
            return
        
        # Ordenar por tiempo
        top_users = sorted(user_times, key=lambda x: x[1], reverse=True)[:10]
        
        # Crear gráfico
        chart = create_bar_chart(top_users, max_width=15, title='')
        
        period_labels = {
            'today': 'Hoy',
            'week': 'Esta Semana',
            'month': 'Este Mes',
            'all': 'Histórico'
        }
        
        embed = discord.Embed(
            title=f'🏆 Top Tiempo en Voz - {period_labels.get(period, "Histórico")}',
            description=f'```\n{chart}\n```',
            color=discord.Color.gold()
        )
        
        # Total
        total_minutes = sum(m for _, m in top_users)
        if total_minutes < 60:
            total_str = f'{total_minutes} min'
        elif total_minutes < 1440:
            hours = total_minutes // 60
            total_str = f'{hours}h {total_minutes % 60}m'
        else:
            days = total_minutes // 1440
            hours = (total_minutes % 1440) // 60
            total_str = f'{days}d {hours}h'
        
        embed.add_field(
            name='⏱️ Total Combinado',
            value=total_str,
            inline=False
        )
        
        await ctx.send(embed=embed)

