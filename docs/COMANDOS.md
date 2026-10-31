# Lista de comandos (fuente de verdad)

Prefijo: `!` · Si `DISCORD_STATS_CHANNEL_ID` / `!setstatschannel` está configurado, solo los comandos marcados **stats** quedan restringidos a ese canal.

Uso rápido: `!topvoice week` muestra el ranking de voz semanal; `!topgamers week`, el de juegos. Períodos: `today`, `week`, `month`, `all`. `!mystats` muestra tu perfil.

## Botón (`cogs/assistant.py`)

`!boton` / `!botón` llama al agente; también se lo invoca mencionándolo o respondiendo a uno de sus mensajes. El modelo decide qué herramienta usar y cuándo, sin rutas deterministas por palabras. Sólo responde en el servidor, canal y sus hilos públicos autorizados; nunca hilos privados ni audio. Anti-spam de 3 segundos y cuota de 40 invocaciones por usuario/día. No ejecuta comandos ni modifica estadísticas. Con `AI_CHANNEL_MEMORY=true` puede anotar chistes/apuestas explícitas en un ledger acotado. Las métricas requieren `AI_SHARE_METRICS=true`. La web usa Google grounding con `GOOGLE_API_KEY` / `GEMINI_API_KEY` y Tavily como respaldo con `TAVILY_API_KEY`; no exige ambas claves. `!boton novedades` lee las novedades del deploy.

Las respuestas web incluyen fuentes, fecha de consulta y tipo de respuesta. Google requiere metadatos válidos de respaldo; Tavily sólo publica citas literales verificadas con enlaces. Esto valida procedencia, no garantiza la verdad de las fuentes. Si falta un dato esencial, Botón pregunta en vez de inventarlo. Cada búsqueda web queda aislada del contexto privado del canal y requiere evidencia nueva: no hay caché activa de respuestas. No busca ni reúne datos personales en Dateas.

Memoria: diálogo compartido del canal, hasta 100 mensajes con autores, respuestas
de Botón y referencias; sólo RAM, se pierde al reiniciar. No hay un chat separado
por usuario. Con `AI_CHANNEL_MEMORY=true` el modelo también puede guardar chistes
o apuestas explícitas en un ledger acotado; eso no modifica las estadísticas.
`!olvidar` / `!resetboton` sólo avisa que el contexto es compartido: no borra el
diálogo ni los recuerdos del grupo. `!botonestado` muestra herramientas
habilitadas y límites sin llamar al modelo.

`!botonmemoria` muestra recuerdos y uso del curador. Sólo para `DISCORD_OWNER_ID`:
`!botonmetricas` muestra consumo y salud operativa sin contenido privado;
`!botonborrar ID_MENSAJE [ID_CANAL]` revoca evidencia de la memoria curada por su
procedencia, no por nombre. No borra mensajes de Discord ni chanzas sin vínculo a esa fuente.

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
