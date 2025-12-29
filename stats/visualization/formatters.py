"""
Módulo de Formateadores
Funciones para formatear datos de estadísticas
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple


def format_time(minutes: int) -> str:
    """
    Formatea minutos a formato legible (horas/días)
    
    Args:
        minutes: Tiempo en minutos
        
    Returns:
        String formateado (ej: '2h 30m', '1d 3h', '45m')
    """
    if minutes < 60:
        return f'{minutes}m'
    elif minutes < 1440:  # Menos de 24 horas
        hours = minutes // 60
        mins = minutes % 60
        if mins > 0:
            return f'{hours}h {mins}m'
        return f'{hours}h'
    else:  # Días
        days = minutes // 1440
        hours = (minutes % 1440) // 60
        if hours > 0:
            return f'{days}d {hours}h'
        return f'{days}d'


def format_duration_detailed(minutes: int) -> str:
    """
    Formatea minutos con más detalle
    
    Args:
        minutes: Tiempo en minutos
        
    Returns:
        String formateado con palabras completas
    """
    if minutes < 1:
        return "menos de 1 minuto"
    elif minutes < 60:
        return f"{minutes} minuto{'s' if minutes != 1 else ''}"
    elif minutes < 1440:
        hours = minutes // 60
        mins = minutes % 60
        result = f"{hours} hora{'s' if hours != 1 else ''}"
        if mins > 0:
            result += f" y {mins} minuto{'s' if mins != 1 else ''}"
        return result
    else:
        days = minutes // 1440
        hours = (minutes % 1440) // 60
        result = f"{days} día{'s' if days != 1 else ''}"
        if hours > 0:
            result += f" y {hours} hora{'s' if hours != 1 else ''}"
        return result


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Formatea un porcentaje
    
    Args:
        value: Valor entre 0 y 100
        decimals: Número de decimales
        
    Returns:
        String formateado (ej: '25.5%')
    """
    return f"{value:.{decimals}f}%"


def format_large_number(num: int) -> str:
    """
    Formatea números grandes con sufijos (K, M)
    
    Args:
        num: Número a formatear
        
    Returns:
        String formateado (ej: '1.2K', '5.4M')
    """
    if num < 1000:
        return str(num)
    elif num < 1_000_000:
        return f"{num / 1000:.1f}K"
    else:
        return f"{num / 1_000_000:.1f}M"


def format_time_ago(iso_date: str) -> str:
    """
    Formatea una fecha ISO a tiempo relativo (hace X tiempo)
    
    Args:
        iso_date: Fecha en formato ISO
        
    Returns:
        String con tiempo relativo (ej: 'hace 2 horas')
    """
    try:
        date = datetime.fromisoformat(iso_date)
        now = datetime.now()
        
        # Si tiene timezone, convertir ambos a aware
        if date.tzinfo is not None:
            from datetime import timezone
            now = now.replace(tzinfo=timezone.utc)
        
        diff = now - date
        
        if diff.days > 365:
            years = diff.days // 365
            return f"hace {years} año{'s' if years != 1 else ''}"
        elif diff.days > 30:
            months = diff.days // 30
            return f"hace {months} mes{'es' if months != 1 else ''}"
        elif diff.days > 0:
            return f"hace {diff.days} día{'s' if diff.days != 1 else ''}"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"hace {hours} hora{'s' if hours != 1 else ''}"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"hace {minutes} minuto{'s' if minutes != 1 else ''}"
        else:
            return "hace unos segundos"
    except:
        return "Desconocido"


def format_date(iso_date: str, format_str: str = "%d/%m/%Y") -> str:
    """
    Formatea una fecha ISO a un formato específico
    
    Args:
        iso_date: Fecha en formato ISO
        format_str: Formato deseado (default: DD/MM/YYYY)
        
    Returns:
        String con fecha formateada
    """
    try:
        date = datetime.fromisoformat(iso_date)
        return date.strftime(format_str)
    except:
        return "Fecha desconocida"


def format_ranking_position(position: int) -> str:
    """
    Formatea una posición de ranking con medalla
    
    Args:
        position: Posición (1, 2, 3, etc.)
        
    Returns:
        String con emoji o número
    """
    medals = {1: '🥇', 2: '🥈', 3: '🥉'}
    return medals.get(position, f'{position}.')


def format_list_with_commas(items: List[str], max_items: int = 3) -> str:
    """
    Formatea una lista en texto con comas
    
    Args:
        items: Lista de strings
        max_items: Máximo de items a mostrar
        
    Returns:
        String formateado (ej: 'item1, item2, item3')
    """
    if not items:
        return "Ninguno"
    
    if len(items) <= max_items:
        if len(items) == 1:
            return items[0]
        elif len(items) == 2:
            return f"{items[0]} y {items[1]}"
        else:
            return ", ".join(items[:-1]) + f" y {items[-1]}"
    else:
        shown = items[:max_items]
        remaining = len(items) - max_items
        return ", ".join(shown) + f" y {remaining} más"


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Trunca texto si excede el largo máximo
    
    Args:
        text: Texto a truncar
        max_length: Largo máximo
        suffix: Sufijo a agregar si se trunca
        
    Returns:
        Texto truncado
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_progress_bar(current: int, total: int, width: int = 20, filled_char: str = "█", empty_char: str = "░") -> str:
    """
    Crea una barra de progreso
    
    Args:
        current: Valor actual
        total: Valor total
        width: Ancho de la barra
        filled_char: Caracter para la parte llena
        empty_char: Caracter para la parte vacía
        
    Returns:
        String con la barra de progreso
    """
    if total == 0:
        return empty_char * width
    
    filled = int((current / total) * width)
    empty = width - filled
    
    return filled_char * filled + empty_char * empty


def format_comparison(value1: int, value2: int, format_func=None) -> Tuple[str, str, str]:
    """
    Formatea una comparación entre dos valores
    
    Args:
        value1: Primer valor
        value2: Segundo valor
        format_func: Función opcional para formatear los valores
        
    Returns:
        Tupla (formatted_val1, formatted_val2, winner_indicator)
    """
    if format_func:
        val1_str = format_func(value1)
        val2_str = format_func(value2)
    else:
        val1_str = str(value1)
        val2_str = str(value2)
    
    if value1 > value2:
        winner = "👑 ⬅"
    elif value2 > value1:
        winner = "➡ 👑"
    else:
        winner = "🤝"
    
    return val1_str, val2_str, winner


def format_stat_line(label: str, value: str, emoji: str = "", width: int = 30) -> str:
    """
    Formatea una línea de estadística
    
    Args:
        label: Etiqueta
        value: Valor
        emoji: Emoji opcional
        width: Ancho de la línea
        
    Returns:
        String formateado
    """
    prefix = f"{emoji} " if emoji else ""
    label_part = f"{prefix}{label}".ljust(width)
    return f"{label_part} {value}"


def get_period_label(period: str) -> str:
    """
    Retorna el label legible para un período
    
    Args:
        period: 'today', 'week', 'month', 'all'
        
    Returns:
        Label legible
    """
    labels = {
        'today': 'Hoy',
        'week': 'Última Semana',
        'month': 'Último Mes',
        'year': 'Último Año',
        'all': 'Histórico'
    }
    return labels.get(period, period.title())

