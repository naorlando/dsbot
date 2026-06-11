# Lista de comandos (fuente de verdad)

Prefijo: `!` · Si `DISCORD_STATS_CHANNEL_ID` / `!setstatschannel` está configurado, solo los comandos marcados **stats** quedan restringidos a ese canal.

## Leyenda

| Alcance | Significado |
|--------|-------------|
| **stats** | Requiere canal de estadísticas si está configurado (`@stats_channel_only`) |
| **general** | Va en `cogs/config` o `cogs/utility` sin restricción de stats (salvo que indiquemos lo contrario) |
| **owner** | Requiere `DISCORD_OWNER_ID` |

---

## Configuración (`cogs/config.py`)

| Comando | Aliases | Alcance |
|---------|---------|--------|
| `setchannel` | — | owner |
| `unsetchannel` | removechannel, clearchannel | owner |
| `setstatschannel` | statscanal | owner |
| `unsetstatschannel` | removestatschannel, clearstatschannel | owner |
| `channels` | canales, showchannels | **general** |
| `toggle` | — | **general** |
| `config` | — | **general** |
| `test` | — | **general** |

---

## Estadísticas (`stats/commands/*` + `cogs/stats.py`)

Los comandos de rankings/juegos/usuario/parties/wrapped no tienen restricción de canal en esta versión, salvo que se indique lo contrario.

### Rankings (`rankings.py`)

| Comando | Aliases |
|---------|---------|
| `topgamers` | topgaming, gamers |
| `topvoice` | topvoz, voice |
| `topchat` | topmessages, chatters |
| `topusers` | — |

### Juegos (`games.py`)

| Comando | Aliases |
|---------|---------|
| `topgames` | populargames, games |
| `topgame` | gamestats, gameinfo |
| `mygames` | misjuegos |

### Parties (`parties.py`)

| Comando | Aliases |
|---------|---------|
| `partymaster` | topparties, partyking |
| `partywith` | partywho |
| `partygames` | toppartygames |

### Usuario (`user.py`)

| Comando | Aliases |
|---------|---------|
| `stats` | estadisticas |
| `mystats` | yo |
| `compare` | vs, comparar |

### Social (`social.py`)

| Comando | Aliases | Alcance |
|---------|---------|--------|
| `topreactions` | reactions | general |
| `topstickers` | stickers | general |
| `topconnections` | conexiones | stats |

### Utilidades stats (`utils.py`)

| Comando | Aliases | Alcance | Notas |
|---------|---------|--------|-------|
| `statsmenu` | menu_stats, statspanel | stats | Menú interactivo (`StatsView`) |
| `export` | — | stats | json / csv |
| `checkstats` | — | stats | Debug del archivo de datos |

### Wrapped (`wrapped.py`)

| Comando | Notas |
|---------|--------|
| `wrapped` | Resumen anual |

Los comandos sin columna de alcance en esta sección son **general** en el código actual.

---

## Utilidades (`cogs/utility.py`)

| Comando | Aliases | Alcance |
|---------|---------|--------|
| `bothelp` | help, ayuda, comandos | stats |
| `updates` | update, novedades, changelog | stats |
| `party` | parties | stats |
| `partyhistory` | partyhist | stats |
| `partystats` | — | stats |

---

## Cargas opcionales (`bot.py`)

| Variable de entorno | Efecto |
|---------------------|--------|
| `ENABLE_WRAPPED_SCHEDULER=true` | Carga `cogs.wrapped_event` (envío automático del wrapped el 31/12 si aplica). |
| `BOT_VERSION=vX.Y.Z` | Etiqueta visible en la notificación de deploy activo. |
| `NOTIFY_DEPLOY=false` | Desactiva la notificación automática al iniciar el bot. |

---

## Comandos no implementados como tales en este repo

- `statsgames`, `statsvoice`, `statsuser` — no hay comandos con esos nombres; parte del menú `!statsmenu` cubre vistas similares.
- `voicetime`, `voicetop` — usar `!stats` / `!topvoice`.
- `topemojis` — no hay comando dedicado (sí hay reacciones en `!topreactions`).

---

## Períodos

Donde aplique: `today`, `week`, `month`, `all` (según comando; p. ej. `!topconnections [periodo]`).

---

*Última revisión: alineada con el árbol de código del repo.*
