"""
Módulo de Gráficos ASCII Mejorados
Visualizaciones más atractivas para estadísticas del bot
"""

from typing import List, Tuple, Dict


def create_bar_chart(
    data: List[Tuple[str, int]], 
    max_width: int = 25, 
    title: str = "",
    show_percentage: bool = True,
    style: str = "gradient"
) -> str:
    """
    Crea un gráfico de barras ASCII mejorado
    
    Args:
        data: Lista de tuplas (label, value)
        max_width: Ancho máximo de la barra más grande
        title: Título del gráfico
        show_percentage: Mostrar porcentaje al lado del valor
        style: Estilo de barra ('gradient', 'solid', 'blocks')
    
    Returns:
        String con el gráfico formateado
    """
    if not data:
        return "📊 No hay datos disponibles"
    
    # Encontrar el valor máximo para normalizar
    max_value = max(value for _, value in data)
    total_value = sum(value for _, value in data)
    
    if max_value == 0:
        return "📊 No hay datos disponibles"
    
    # Estilos de barras
    bar_styles = {
        "gradient": ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"],
        "solid": ["█"],
        "blocks": ["░", "▒", "▓", "█"],
        "fancy": ["▰", "▱", "━"],
        "dots": ["⣀", "⣄", "⣤", "⣦", "⣶", "⣷", "⣿"]
    }
    
    bar_chars = bar_styles.get(style, bar_styles["gradient"])
    
    lines = []
    if title:
        lines.append(f"\n╔{'═' * (max_width + 35)}╗")
        lines.append(f"║ {title.center(max_width + 33)} ║")
        lines.append(f"╠{'═' * (max_width + 35)}╣")
    
    for i, (label, value) in enumerate(data):
        # Calcular la longitud de la barra
        bar_length = int((value / max_value) * max_width)
        
        # Crear barra con estilo
        if style == "gradient" and bar_length > 0:
            # Usar caracteres graduales
            full_blocks = bar_length
            bar = bar_chars[-1] * full_blocks
        elif style == "fancy":
            bar = bar_chars[0] * bar_length
        else:
            bar = bar_chars[-1] * bar_length
        
        # Medallas para top 3
        medals = ['🥇', '🥈', '🥉']
        prefix = medals[i] if i < 3 else f'{i+1}.'
        prefix = prefix.ljust(3)
        
        # Truncar label si es muy largo
        display_label = label[:18] + "..." if len(label) > 18 else label
        display_label = display_label.ljust(22)
        
        # Calcular porcentaje
        percentage = f"({value / total_value * 100:.1f}%)" if show_percentage and total_value > 0 else ""
        percentage = percentage.rjust(8)
        
        # Formato del valor
        value_str = f"{value:,}".rjust(6)
        
        line = f"║ {prefix} {display_label} {bar.ljust(max_width)} {value_str} {percentage} ║"
        lines.append(line)
    
    if title:
        lines.append(f"╚{'═' * (max_width + 35)}╝")
    
    return "\n".join(lines)


def create_box_chart(
    categories: List[Tuple[str, int, int]], 
    title: str = "",
    labels: Tuple[str, str] = ("Categoría 1", "Categoría 2")
) -> str:
    """
    Crea un gráfico de cajas comparativo
    
    Args:
        categories: Lista de tuplas (label, value1, value2)
        title: Título del gráfico
        labels: Nombres de las dos categorías a comparar
    
    Returns:
        String con el gráfico formateado
    """
    if not categories:
        return "📊 No hay datos disponibles"
    
    max_val1 = max(v1 for _, v1, _ in categories)
    max_val2 = max(v2 for _, _, v2 in categories)
    max_value = max(max_val1, max_val2)
    
    if max_value == 0:
        return "📊 No hay datos disponibles"
    
    max_width = 20
    lines = []
    
    if title:
        lines.append(f"\n╔{'═' * 60}╗")
        lines.append(f"║ {title.center(58)} ║")
        lines.append(f"╠{'═' * 60}╣")
        lines.append(f"║ 🟦 {labels[0].ljust(20)} | 🟩 {labels[1].ljust(20)} ║")
        lines.append(f"╠{'═' * 60}╣")
    
    for label, val1, val2 in categories:
        # Barras
        bar1_len = int((val1 / max_value) * max_width)
        bar2_len = int((val2 / max_value) * max_width)
        
        bar1 = "█" * bar1_len
        bar2 = "█" * bar2_len
        
        # Label
        display_label = label[:15] + "..." if len(label) > 15 else label
        display_label = display_label.ljust(18)
        
        lines.append(f"║ {display_label}                                  ║")
        lines.append(f"║   🟦 {bar1.ljust(max_width)} {val1:>6,}           ║")
        lines.append(f"║   🟩 {bar2.ljust(max_width)} {val2:>6,}           ║")
        lines.append(f"╠{'─' * 60}╣")
    
    lines.append(f"╚{'═' * 60}╝")
    
    return "\n".join(lines)


def create_mini_chart(value: int, max_value: int, width: int = 10) -> str:
    """
    Crea una mini barra de progreso
    
    Args:
        value: Valor actual
        max_value: Valor máximo
        width: Ancho de la barra
    
    Returns:
        String con la mini barra
    """
    if max_value == 0:
        return "▱" * width
    
    filled = int((value / max_value) * width)
    empty = width - filled
    
    return "▰" * filled + "▱" * empty


def create_timeline_chart(
    daily_data: Dict[str, int], 
    days: int = 7,
    style: str = "bars"
) -> str:
    """
    Crea un gráfico de línea de tiempo con actividad por día
    
    Args:
        daily_data: Dict con fecha (YYYY-MM-DD) -> count
        days: Número de días a mostrar
        style: 'bars' o 'sparkline'
    
    Returns:
        String con el gráfico de timeline
    """
    from datetime import datetime, timedelta
    
    # Generar los últimos N días
    end_date = datetime.now()
    dates = []
    for i in range(days - 1, -1, -1):
        date = end_date - timedelta(days=i)
        dates.append(date.strftime("%Y-%m-%d"))
    
    # Preparar datos
    data = []
    day_names = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
    
    for date_str in dates:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_name = day_names[date_obj.weekday()]
        count = daily_data.get(date_str, 0)
        # Formato: "Lun 26/12"
        label = f"{day_name} {date_obj.strftime('%d/%m')}"
        data.append((label, count))
    
    if style == "sparkline":
        return create_sparkline_chart(data, f"📈 Actividad ({days} días)")
    else:
        return create_bar_chart(data, max_width=20, title=f"📈 Actividad Últimos {days} Días", show_percentage=False)


def create_sparkline_chart(data: List[Tuple[str, int]], title: str = "") -> str:
    """
    Crea un sparkline (mini gráfico de línea)
    
    Args:
        data: Lista de tuplas (label, value)
        title: Título del gráfico
    
    Returns:
        String con el sparkline
    """
    if not data:
        return "📊 No hay datos disponibles"
    
    values = [v for _, v in data]
    max_value = max(values) if values else 1
    
    # Caracteres para sparkline (8 niveles)
    spark_chars = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']
    
    # Normalizar valores
    normalized = []
    for value in values:
        if max_value == 0:
            normalized.append(0)
        else:
            index = int((value / max_value) * 7)
            normalized.append(index)
    
    sparkline = ''.join(spark_chars[i] for i in normalized)
    
    lines = []
    if title:
        lines.append(f"\n{title}")
        lines.append("━" * 50)
    
    lines.append(f"  {sparkline}")
    lines.append("")
    
    # Mostrar labels
    for label, value in data:
        lines.append(f"  {label[:10].ljust(10)}: {value}")
    
    return "\n".join(lines)


def create_comparison_bars(
    user1_data: Dict, 
    user2_data: Dict, 
    user1_name: str, 
    user2_name: str
) -> str:
    """
    Crea barras comparativas mejoradas entre dos usuarios
    
    Args:
        user1_data: Datos del usuario 1
        user2_data: Datos del usuario 2
        user1_name: Nombre del usuario 1
        user2_name: Nombre del usuario 2
    
    Returns:
        String con la comparación formateada
    """
    lines = []
    lines.append(f"\n╔{'═' * 58}╗")
    lines.append(f"║ 🆚 {user1_name} vs {user2_name}".ljust(59) + " ║")
    lines.append(f"╚{'═' * 58}╝")
    
    # Preparar datos
    # Juegos
    games1_time = sum(g.get('total_minutes', 0) for g in user1_data.get('games', {}).values())
    games2_time = sum(g.get('total_minutes', 0) for g in user2_data.get('games', {}).values())
    
    # Voz
    voice1_time = user1_data.get('voice', {}).get('total_minutes', 0)
    voice2_time = user2_data.get('voice', {}).get('total_minutes', 0)
    
    # Mensajes
    msg1 = user1_data.get('messages', {}).get('count', 0)
    msg2 = user2_data.get('messages', {}).get('count', 0)
    
    categories = [
        ("🎮 Gaming", games1_time, games2_time),
        ("🔊 Voz", voice1_time, voice2_time),
        ("💬 Mensajes", msg1, msg2)
    ]
    
    return create_box_chart(categories, "", (user1_name, user2_name))


def create_ranking_visual(
    data: List[Tuple[str, int, str]], 
    title: str,
    max_display: int = 10
) -> str:
    """
    Crea un ranking visual con barras y estadísticas
    
    Args:
        data: Lista de tuplas (name, value, extra_info)
        title: Título del ranking
        max_display: Máximo número de entradas a mostrar
    
    Returns:
        String con el ranking formateado
    """
    if not data:
        return "📊 No hay datos disponibles"
    
    lines = []
    lines.append(f"\n╔{'═' * 70}╗")
    lines.append(f"║ {title.center(68)} ║")
    lines.append(f"╚{'═' * 70}╝")
    
    max_value = max(v for _, v, _ in data[:max_display])
    
    for i, (name, value, extra) in enumerate(data[:max_display], 1):
        # Medalla
        medals = ['🥇', '🥈', '🥉']
        prefix = medals[i-1] if i <= 3 else f'{i}.'
        prefix = prefix.ljust(3)
        
        # Barra
        bar_length = int((value / max_value) * 30) if max_value > 0 else 0
        bar = "█" * bar_length
        
        # Formato
        name_display = name[:20].ljust(20)
        value_display = f"{value:,}".rjust(8)
        extra_display = extra[:25].ljust(25)
        
        lines.append(f"{prefix} {name_display} {bar.ljust(30)} {value_display}")
        if extra:
            lines.append(f"    └─ {extra_display}")
    
    return "\n".join(lines)

