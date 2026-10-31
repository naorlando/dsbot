# Contexto y memoria de Botón

Cambios locales pendientes de aprobación para deploy. No se importa el export de
Discord a producción ni se entrena ningún modelo con él.

## Tres capas distintas

1. **Diálogo compartido del canal:** un solo timeline en RAM por servidor/canal con
   hasta 100 mensajes: charla humana, invocaciones `!boton` y las respuestas de
   Botón, con autor, hora, hilo público y referencia al mensaje respondido. No hay un chat por
   usuario: si alguien habla de un tema y después otra persona llama a Botón, el
   bot ve ambos turnos. Incluye hilos públicos del canal padre autorizado, nunca
   hilos privados. Se precarga una vez por canal/hilo visitado, con timeout de 3
   segundos. El prompt recibe hasta 7000 caracteres: primero los antecedentes
   (máximo 25% del espacio) y al final los últimos 24 turnos de la última hora.
   Un canal tranquilo no convierte el tema de ayer en "actual": queda como
   antecedente. Los mensajes de más de 3 días no entran.
2. **Búsqueda histórica:** herramienta elegida por el modelo, hasta 1000 mensajes
   o 30 días, con un máximo de 12 coincidencias. Permite reformular las palabras
   clave. Repetir exactamente la misma consulta reutiliza su resultado en ese
   turno; cambiarla realiza una búsqueda distinta. No hay embeddings ni una
   búsqueda semántica exhaustiva del servidor.
3. **Memoria duradera opt-in:** `AI_CHANNEL_MEMORY=true`. El curador destila
   tópicos/acuerdos con respaldo en mensajes; el ledger conserva apuestas o
   chistes explícitos que el modelo decide anotar. No son perfiles de personas
   ni una métrica objetiva de "cómo es" alguien. No se infieren religión, etnia,
   género, salud o sexualidad para guardar etiquetas personales.

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

- Se observa la charla humana nueva y el texto que acompaña a `!boton`; no se
  observan otros comandos ni bots. La cola cruda vive sólo en RAM (hasta 100
  filas); no es un archivo completo de cada mensaje.
- Cada **40 mensajes nuevos**, o **2 horas con al menos 10 pendientes**, el
  curador puede hacer una llamada en background. Chequea elegibilidad cada 5 min.
- Separación mínima de 15 min; máximo **24 intentos diarios**, fallidos incluidos.
  Tras un fallo espera 30 min antes de reintentar.
   Consume su propia bolsa persistida de 24 llamadas/día; no consume las 400
   generaciones diarias reservadas a preguntas.
- Hasta 30 bullets con TTL de 14 días. Se exige evidencia literal que exista en
  el snapshot enviado; esto valida procedencia, no prueba que la interpretación
  del resumen sea perfecta. Apuestas/chistes del ledger vencen a los 30 días.
- `!botonmemoria` muestra resúmenes, chanzas, intentos diarios y mensajes pendientes
  sin llamar al modelo. El comando heredado `!olvidar` ya no borra nada: avisa que
   la conversación es compartida por canal. No hay borrado de autoservicio por nombre.
   El owner (`DISCORD_OWNER_ID`) puede revocar evidencia con
   `!botonborrar ID_MENSAJE [ID_CANAL]`, sin borrar el mensaje en Discord ni chanzas
   sin vínculo de procedencia. Los métodos por nombre de los stores siguen siendo
   internos, no herramientas del modelo ni borrado automático para usuarios.

### Procedencia y datos sensibles

El curador conserva IDs locales de mensaje y canal junto a la evidencia literal.
El snapshot del LLM sigue usando fecha/autor/texto: **los IDs no salen al proveedor**.
Los eventos recibidos de edición y borrado invalidan los bullets completos que dependan
de esa fuente y evitan que una curación en vuelo los restaure. Las notas heredadas
sin IDs no tienen revocación precisa por mensaje. No hay reconciliación exhaustiva de
ediciones/borrados ocurridos mientras el bot estaba desconectado.

Antes del diálogo y de la memoria se filtran secretos, emails, teléfonos y datos
explícitos de identificación/domicilio. Curador y ledger rechazan esos datos también
al cargar archivos. Es una barrera conservadora, no una prueba de anonimato ni un
detector exhaustivo de datos sensibles. Los nombres visibles siguen siendo necesarios
para atribuir turnos; no se crean perfiles de personas.

La cadencia inicial se eligió con el análisis local de actividad reciente, y se
aumentó a pedido del administrador para monitorearla, no suponiendo
que todo el histórico exportado corresponde a la vida de Botón. No se genera
ningún perfil de identidad ni se transforma un chiste en un hecho comprobado.

## Separación con la web

El diálogo no impide que el modelo elija `search_web`. Si lo elige, se descartan
el diálogo, el ledger y los recuerdos antes de buscar y sintetizar. El buscador
recibe únicamente la pregunta actual original, nunca una consulta elaborada con
mensajes del canal, y tampoco se reenvía al selector de fuentes ninguna llamada
generada con contexto privado.

Una lectura explícita de métricas, historial o ledger sí cierra la búsqueda web
para ese turno. Las respuestas de Botón quedan en el diálogo porque ya son
mensajes públicos del canal; no se usan como prueba de hechos.

`knowledge.json` ya no se usa en el camino activo: se escribía sin consultarse.
No se guardan nuevas respuestas web. Archivos anteriores no se importan ni se borran
automáticamente; `core/knowledge.py` queda como utilidad legada, fuera del runtime.

## Operación y validación

- Preguntas de hasta 4000 caracteres; error visible por encima de ese límite.
- Hasta 6 pasos del modelo por pregunta; no se aumenta la bolsa diaria existente.
- Hasta 4 herramientas; 400 llamadas/día interactivas, 240/día ambientales por
  defecto y 24/día del curador. Además, 40 invocaciones por usuario/día, con cuotas
  seudonimizadas; no son chats por usuario ni se envían esos IDs al LLM.
- Proveedor: timeout por intento 25 s; router 10 s; respuesta completa 60 s.
- El límite global cancela la tarea y libera el lock. Es contención del fallo,
  **no** ejecución durable ni garantía de finalizar consultas de varios minutos.
  La precarga inicial del contexto tiene su propio límite de 3 s anterior al de
  la respuesta. Las escrituras síncronas o código que no cede al event loop no
  pueden ser interrumpidos instantáneamente por `asyncio.wait_for`.
- `!olvidar` responde al instante: no toma el lock ni espera una respuesta lenta.
- Las pruebas con `AsyncMock` comprueban protocolo, privacidad, límites y errores.
  **No demuestran** que un modelo real elija siempre la herramienta correcta.
- Export y análisis locales están ignorados por Git. No publicar nombres ni
  citas privadas del export en documentación o fixtures versionados.
