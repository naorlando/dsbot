# Updates del bot

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
