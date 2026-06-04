# LoL / lobby: huecos de presencia y notificaciones

## Qué pasa

En juegos como **League of Legends**, Discord suele mostrar “Playing” desde **buscar partida** hasta **fin de partida**. En **post-partida / lobby**, la presencia puede desaparecer o no listar a todos los jugadores a la vez.

El bot infiere **parties** cuando hay **≥ `min_players`** con la misma actividad de juego. Si en un momento solo aparece 1 jugador (o 0), el flujo intentaba **cerrar la party**; tras unos minutos en cola de nuevo, se volvía a crear y **“party formada”** podía repetirse.

## Qué hace el bot ahora

Parámetros en `config.json` (ver también `docs/PLAN_MEJORAS.md`):

| Clave | Rol |
|-------|-----|
| `party_detection.grace_period_seconds` | No cerrar la party en cuanto baja el conteo; esperar un hueco más largo (default 30 min). |
| `game_session.grace_period_seconds` | No dar por terminada la sesión de juego ante un parpadeo de presencia (default 15 min). |
| `party_detection.reactivation_window_minutes` | Tras cerrar una party, si vuelve a “formarse” el mismo juego dentro de la ventana, **no** reenviar la notificación de party formada (stats internos sí). |
| `party_detection.notification_key_aliases` | Agrupa variantes de nombre para cooldown/reactivación; `League of Legends` y `LoL` comparten `league-of-legends`. |
| `party_detection.suppress_join_notifications_for_games` | Silencia avisos de “se unió a la party” en juegos ruidosos como LoL; el tracking y las stats siguen activos. |

## Anti-spam específico de LoL

Para LoL, el bot ahora usa una clave canónica (`league-of-legends`) para decidir cooldown/reactivación de “party formada”. Así, si Discord alterna entre nombres parecidos, no se trata como una party nueva a efectos de notificación.

Además, los avisos de nuevos jugadores uniéndose a una party de LoL quedan silenciados por default, porque el lobby/cola suele hacer aparecer y desaparecer jugadores y eso genera spam. La party sigue activa y guardando estadísticas.

## Notificaciones individuales “está jugando”

Siguen sujetas al cooldown de entrada (`game:{nombre}`, típicamente 30 min en código). Si el hueco entre partidas es **mayor** que ese cooldown, puede volver a avisar; es esperable. Subir cooldown solo si querés menos avisos a costa de menos sensibilidad.

## Pruebas

No hay reproducción determinística sin Discord real; los cambios se validan en producción ajustando tiempos. Para tests unitarios futuros: mockear `send_notification` y simular timestamps en `PartySessionManager._last_party_end_by_game`.
