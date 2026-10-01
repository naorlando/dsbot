# Updates del bot

## 2026-10-01 · Botón, agente con herramientas

- `!boton` / `!botón`, `!ask` y `!pregunta` llaman a Botón: elige entre métricas de sólo lectura, ayuda pública y web según las herramientas habilitadas.
- `!buscar` fuerza una búsqueda; con Tavily conectado, también puede elegir buscar desde una pregunta normal y responder con enlaces reales de las fuentes.
- Consulta comandos, capacidades y novedades de la versión desplegada. No tiene acceso libre al código, archivos privados ni terminal.
- Nunca mezcla métricas y web en una misma consulta. El buscador recibe sólo la pregunta original, no consultas inventadas por el modelo.
- Pide aclaraciones cuando falta información. Mantiene hasta 5 mensajes por persona/canal en RAM, con vencimiento de 30 minutos, sin guardar resultados privados de métricas; `!olvidar` los borra.
- `!botonestado` muestra capacidades reales sin consumir el modelo. Harness con argumentos validados, tres llamadas de modelo y dos herramientas por pedido, sin fallback pago.

## 2026-10-01 · Deploy inteligente y asistente opcional

- La automatización nocturna compara versiones: no redespliega el mismo commit si ya está activo o dormido, ni duplica un despliegue en curso.
- Se agregó un asistente ligero con `!ask` / `!pregunta` para conversación y métricas de sólo lectura, y `!buscar` para web con fuentes; sigue desactivado hasta configurar las claves y el canal permitido.
- Usa OpenRouter gratis por defecto, sin fallback pago, con límites de consumo y sin guardar historial de chat.
- La búsqueda web es explícita y opcional; necesita una clave de Tavily.
- El asistente requiere un único servidor y compartir métricas con el proveedor debe habilitarse expresamente.

## 2026-09-19 · Despliegue fuera de hora pico

- Se agregó una tarea de GitHub Actions para desplegar fuera de la ventana restringida de Railway Free.
- El build pasó a Railpack y los errores fatales de arranque ahora se reportan como fallos del proceso.
- La comparación de versiones del 1 de octubre reemplaza el redeploy diario incondicional.

## 2026-06-10 · Emuladores detectados

- El bot ahora detecta emuladores que Discord muestra como actividad sin `application_id`.
- Se agregó una allowlist configurable en `allowed_no_app_id_games`.
- Incluye RetroArch, Dolphin, PCSX2, RPCS3, Ryujinx, Citra, PPSSPP y otros.
- También se agregó `Ship of Harkinian (DirectX 11)` con el nombre exacto visto en Discord.
- Las actividades desconocidas sin app ID siguen bloqueadas para evitar falsos positivos.

## 2026-06-04 · Menos spam en parties de LoL

- Las parties de League of Legends comparten una clave canónica para cooldown y reactivación.
- Si Discord alterna entre `League of Legends` y `LoL`, se trata como el mismo juego para notificaciones.
- Se silenciaron por default los avisos de “se unió a la party” en LoL.
- El tracking y las estadísticas de parties siguen activos.

## 2026-06-04 · Tracking y comandos de parties

- Se corrigió el cierre de sesiones de voz al cambiar de canal.
- El health check respeta la gracia configurada para juegos y parties.
- `!party`, `!partyhistory` y `!partystats` ahora usan el manager real de sesiones activas.
- `!partymaster`, `!partywith` y `!partygames` muestran datos reales del historial.

## 2026-06-04 · Estadísticas y ayuda

- Se agregó `!topconnections` para ranking de conexiones.
- Se reactivó `!statsmenu` como menú interactivo.
- `!topreactions` y `!topstickers` leen el schema actual de stats.
- `!help` y `docs/COMANDOS.md` quedaron alineados con los comandos reales.

## 2026-06-04 · Deploy activo

- El bot avisa cuando un deploy queda online.
- Usa `BOT_VERSION` si está configurado o el commit corto de Railway como etiqueta.
- Se puede desactivar con `NOTIFY_DEPLOY=false`.
