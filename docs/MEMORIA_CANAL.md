# Contexto y memoria de Botón

Cambios locales pendientes de aprobación para deploy. No se importa el export de
Discord a producción ni se entrena ningún modelo con él.

## Tres capas distintas

1. **Conversación reciente:** buffer en RAM de hasta 100 mensajes del canal
   autorizado; incluye charla humana sin menciones a Botón. Se precarga una vez
   desde Discord, con timeout de 3 segundos. El prompt recibe una cola compacta
   de hasta 6000 caracteres, no necesariamente los 100 textos completos. Los
   mensajes de más de 3 días no entran en este contexto inmediato.
2. **Búsqueda histórica:** herramienta elegida por el modelo, hasta 1000 mensajes
   o 30 días, con un máximo de 12 coincidencias. Permite reformular las palabras
   clave. Repetir exactamente la misma consulta reutiliza su resultado en ese
   turno; cambiarla realiza una búsqueda distinta. No hay embeddings ni una
   búsqueda semántica exhaustiva del servidor.
3. **Memoria duradera opt-in:** `AI_CHANNEL_MEMORY=true`. El curador destila
   tópicos/acuerdos con respaldo en mensajes; el ledger conserva apuestas o
   chistes explícitos que el modelo decide anotar. No son perfiles de personas
   ni una métrica objetiva de "cómo es" alguien. No se infieren religión, etnia,
   salud o sexualidad para guardar etiquetas personales.

Los resúmenes del canal siguen siendo privados aunque no sean mensajes completos.
Se tratan como **datos no confiables**, nunca como instrucciones del sistema.
Los archivos quedan bajo el directorio de datos; requieren volumen persistente
en Railway para sobrevivir redeploys. Un JSON local no garantiza persistencia
si el filesystem del contenedor es efímero.

El cog separa archivos por servidor/canal en
`/data/channel_memory/<servidor>_<canal>/` (o `data/` en local). Cambiar el canal
autorizado no reutiliza los recuerdos del canal anterior.

### Curación y control

Con `AI_CHANNEL_MEMORY=true` y el historial habilitado:

- Se observa la charla humana nueva, sin comandos ni bots. La cola cruda vive
  sólo en RAM (hasta 100 filas); no es un archivo completo de cada mensaje.
- Cada **40 mensajes nuevos**, o **2 horas con al menos 10 pendientes**, el
  curador puede hacer una llamada en background. Chequea elegibilidad cada 5 min.
- Separación mínima de 15 min; máximo **24 intentos diarios**, fallidos incluidos.
  Tras un fallo espera 30 min antes de reintentar.
  Consume además el presupuesto LLM normal de Botón, no una bolsa ilimitada.
- Hasta 30 bullets con TTL de 14 días. Se exige evidencia literal que exista en
  el snapshot enviado; esto valida procedencia, no prueba que la interpretación
  del resumen sea perfecta. Apuestas/chistes del ledger vencen a los 30 días.
- `!botonmemoria` muestra resúmenes, chanzas, intentos diarios y mensajes pendientes
  sin llamar al modelo. El comando heredado `!olvidar` sólo reinicia la memoria
  corta en RAM por ID; no elimina contexto compartido ni recuerdos por nombre.
  No hay borrado persistente de autoservicio hasta contar con procedencia e IDs
  estables. Los métodos de borrado por nombre de los stores son internos, no se
  exponen como herramientas del modelo ni como borrado automático para usuarios.

La cadencia inicial se eligió con el análisis local de actividad reciente, y se
aumentó a pedido del administrador para monitorearla, no suponiendo
que todo el histórico exportado corresponde a la vida de Botón. No se genera
ningún perfil de identidad ni se transforma un chiste en un hecho comprobado.

## Separación con la web

El contexto ambiente no impide que el modelo elija `search_web`. Si lo elige,
se descartan el ambiente, el ledger y la conversación privada antes de sintetizar
la respuesta web. El buscador recibe únicamente la pregunta actual original,
nunca una consulta elaborada con mensajes del canal.

Una lectura explícita de métricas, historial o ledger sí cierra la búsqueda web
para ese turno. Las respuestas privadas no se guardan en la memoria corta.

`knowledge.json` es otra cosa: una caché opcional de respuestas web verificadas,
con fuentes, TTL y límites. No guarda la charla del canal y no sustituye una
búsqueda nueva para datos actuales.

## Operación y validación

- Preguntas de hasta 4000 caracteres; error visible por encima de ese límite.
- Hasta 6 pasos del modelo por pregunta; no se aumenta la bolsa diaria existente.
- Proveedor: timeout por intento 25 s; router 10 s; respuesta completa 60 s.
- El límite global cancela la tarea y libera el lock. Es contención del fallo,
  **no** ejecución durable ni garantía de finalizar consultas de varios minutos.
  La precarga inicial del contexto tiene su propio límite de 3 s anterior al de
  la respuesta. Las escrituras síncronas o código que no cede al event loop no
  pueden ser interrumpidos instantáneamente por `asyncio.wait_for`.
- `!olvidar` no queda esperando detrás de una respuesta lenta.
- Las pruebas con `AsyncMock` comprueban protocolo, privacidad, límites y errores.
  **No demuestran** que un modelo real elija siempre la herramienta correcta.
- Export y análisis locales están ignorados por Git. No publicar nombres ni
  citas privadas del export en documentación o fixtures versionados.
