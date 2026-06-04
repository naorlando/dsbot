# Plan de mejoras (métricas, tracking, gráficos, comandos)

Contexto: ~51 MB de `stats.json` en ~4 meses, **500 MB** de volumen disponible. El crecimiento es manejable si no se añaden series por usuario con cardinalidad infinita (ej. un contador por mensaje-ID).

## 1. Comandos: redundancias y huecos

### Solapamientos (aceptables)

- **`topgames` vs `topgamers`**: uno agrupa por **juego**, otro por **jugador** — audiencias distintas.
- **`topvoice` vs `stats`**: ranking global vs perfil individual.
- **`party*` en `stats/commands` vs `!party` en utility**: rankings/historial vs vista rápida de parties activas.

### Posible consolidación futura (opcional)

- Unificar aliases bajo un `!leaderboard <tipo>` con subcomandos (breaking change; solo si molesta el menú de ayuda).

### Huecos resueltos en esta versión

- **Ranking de conexiones diarias**: expuesto por `!topconnections`.
- **Menú interactivo** (`StatsView`): expuesto por `!statsmenu`.

---

## 2. Alcance: stats vs canal general

Comportamiento actual: `stats_channel_only()` — si hay `stats_channel_id`, **solo ese canal**; si no hay, **todos los canales**.

### Recomendación práctica

| Tipo | Dónde tiene sentido |
|------|---------------------|
| **General** (cualquier canal o DM si aplica) | `channels`, `config`, `test`, `toggle` — información del bot sin volcar tablas. |
| **Canal stats** | Rankings, export, wrapped, compare, ayuda larga (`bothelp`). |
| **Owner** | `setchannel`, `setstatschannel`, etc. |

### Mejora opcional

- Decorador **`@stats_channel_only(allow_dm=True)`** o lista de comandos “ligeros” permitidos en general (`!stats` solo resumen 5 líneas) — solo si el servidor pide menos fricción.

---

## 3. Tracking: qué agregar sin explotar el JSON

### Bajo costo (estructura actual)

| Métrica | Idea | Notas |
|---------|------|--------|
| Mensajes solo embed | Contar `len(content)==0` y `len(embeds)>0` como categoría aparte o sumar a `messages` | 1–2 enteros por usuario |
| Reacciones quitadas | `on_reaction_remove` con decremento (o contador neto) | Cuidado con negativos |
| Hilos | Tratar como mensajes en el mismo canal o flag `thread_root` | Opcional |
| Comandos usados | Contador por `command name` por usuario | Poco volumen |

### Medio costo

- **Agregados diarios precomputados** ya existen para voz/juegos (`daily_minutes`); extender patrón a “mensajes por día” si hace falta para gráficos sin escanear todo el historial.

### Evitar sin diseño previo

- Guardar **cada mensaje-ID** o texto — dispara tamaño y privacidad.

---

## 4. Gráficos y vistas

- Reutilizar `stats_viz.py` / `stats/visualization/charts.py` para nuevos comandos tipo `!trend` (envolver funciones existentes).
- **Timeline**: ya hay `create_timeline_chart`; se usa desde el menú interactivo.
- **Conexiones**: `create_connections_ranking_embed` está conectado a `!topconnections`.

---

## 5. League of Legends / lobby (implementado en código)

Problema: entre partidas Discord deja de mostrar a 2+ jugadores en “Playing”, la party caía por gracia corta y al volver a cola se reenviaban alertas.

### Cambios aplicados

- **`party_detection.grace_period_seconds`** (default **1800** = 30 min): la party no se cierra por un hueco corto de presencia.
- **`game_session.grace_period_seconds`** (default **900** = 15 min): sesión de juego no se corta al instante en lobbie.
- **`reactivation_window_minutes`** (default **45** en `config.json`): si una party del mismo juego “vuelve a formarse” dentro de la ventana, **no se reenvía** la notificación “party formada” (sí se actualiza stats internos).
- **`notification_key_aliases`**: agrupa variantes de nombre de LoL bajo `league-of-legends` para compartir cooldown/reactivación.
- **`suppress_join_notifications_for_games`**: silencia avisos de “se unió a la party” para LoL, evitando spam de lobby/cola sin apagar el tracking.

Ajustar según el equipo (subir gracia o ventana si aún hay spam).

---

## 6. Mantenimiento de datos

- **Snapshot anual** del JSON (copia `stats_YYYY.json`) encaja con tu estrategia de espacio; automatizar con script cron/Railway job.
- **Límite de historial de parties** ya existe (1000); revisar si conviene el mismo patrón para otras listas.

---

## 7. Tests y calidad

- Tests que apunten a `stats/commands_basic.py` deben migrarse a módulos reales.
- Tests que requieran `discord` deben ejecutarse en entorno con dependencias instaladas.
