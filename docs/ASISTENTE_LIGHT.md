# Botón: diseño y operación

Botón es un participante del canal, no una mesa de ayuda. Se suma cuando lo llaman
con `!boton` / `!botón`, una mención o un reply a uno de sus mensajes. Una llamada
vacía sigue el hilo reciente; un cambio explícito de tema lo reemplaza.
No escucha audio ni interviene espontáneamente en la charla.

## Arquitectura y límites

Un LLM elige herramientas en un bucle acotado: no hay rutas por palabras ni recetas
especiales para precios, deportes o documentos. Usa `aiohttp`, JSON y biblioteca
estándar: sin SDK de modelos, frameworks, navegador, SQL ni ejecución de código.
El SYSTEM fija identidad, veracidad, herramientas y privacidad en hasta 2400 caracteres.
La fecha se agrega aparte: UTC y hora de Argentina (`America/Argentina/Buenos_Aires`,
con fallback UTC−03:00 si faltan datos de zona horaria).

| Recurso | Límite actual |
| --- | --- |
| Pregunta | 4000 caracteres |
| Generaciones por pregunta | Hasta 6 llamadas de modelo, incluidas reparaciones y mini-juez |
| Herramientas | Hasta 4 herramientas por pregunta; una por turno |
| Web | 1 investigación por pregunta; 20 búsquedas/día y 600/mes |
| Presupuesto interactivo | 400 llamadas/día, compartidas por el servidor |
| Avisos automáticos | 240/día por defecto, bolsa separada (`AI_AMBIENT_LIMIT`) |
| Curador | 24 intentos/día, bolsa separada de las preguntas |
| Justicia de uso | 40 invocaciones por usuario/día, además del pozo global |
| Ritmo | Anti-spam de 3 segundos por usuario; 20 llamadas de modelo por minuto |
| Concurrencia | Una pregunta a la vez, sin cola |
| Tiempo | 25 s por intento de modelo; 10 s mini-juez; 28 s grounding; 60 s por respuesta |
| Salida | 600 tokens de charla; 1000 para seleccionar evidencia web |

Las generaciones cobran presupuesto antes de la red, incluidos fallos. Cada generación
puede probar una vez cada proveedor configurado y un modelo gratuito de respaldo:
el tope de 6 generaciones **no** equivale a seis requests HTTP físicos.
Un 429 abre un enfriamiento por proveedor/modelo; errores reiterados de herramientas
también lo apartan temporalmente. No se habilitan pagos ni se espera indefinidamente.
Google grounding admite un reintento acotado ante 429/503, dentro de la cerca global.

Los contadores y cuotas se escriben atómicamente y fallan cerrado si no se pueden
verificar o guardar. Relojes hacia atrás no reinician las bolsas. Requiere una sola
réplica: los JSON no son contadores distribuidos. Las cuotas guardan identificadores
seudonimizados, nunca nombres ni preguntas; no se exportan esos identificadores.
La clave HMAC viene sólo del entorno (`AI_QUOTA_KEY`, o la clave ya disponible de
Discord/proveedor); el archivo guarda un salt público, no la clave. Si rota la clave
sin fijar `AI_QUOTA_KEY`, no se concede otra cuota ese día: se reanuda al próximo
cambio de día UTC. Las credenciales nunca se escriben en el archivo de cuotas.

## Conversación y alcance

Un diálogo compartido en RAM: hasta 100 mensajes de humanos y Botón, con autor, hora,
replies y nombre del hilo público. Últimos 24 turnos de la última hora prioritarios;
lo anterior es antecedente, hasta 3 días. El render tiene hasta 7000 caracteres.
No hay chat por usuario. Se precargan hasta 100 mensajes por canal/hilo visitado,
con timeout de 3 segundos y un número acotado de hilos. Reiniciar pierde esa RAM.

Sólo el servidor y canal configurados y sus hilos **públicos**. Hilos privados,
otros canales y DMs quedan fuera. Las referencias se validan contra el canal real
del mensaje: no se inventan replies entre hilos. No se recorren todos los hilos
ni se hacen fetches para resolver referencias desconocidas.

`search_channel_history` consulta hasta 1000 mensajes / 30 días y devuelve hasta
12 coincidencias del canal o hilo donde se lo llamó. El modelo puede reformular
keywords; no hay embeddings ni búsqueda exhaustiva del servidor. Una repetición
exacta dentro del mismo turno reutiliza su resultado.

## Herramientas

- `get_metrics`, `query_stats`: agregados y exploración del registro propio, sólo lectura,
  con `AI_SHARE_METRICS=true`. Las sesiones abiertas pueden faltar; mensajes sólo histórico.
- `get_bot_help`: ayuda pública y novedades incluidas en el deploy, no archivos arbitrarios.
- `search_channel_history`: historial del canal/hilo autorizado, sólo lectura.
- `search_web`: investigación pública aislada del contexto del canal.
- `calc`: aritmética con evaluador acotado propio, sin `eval`.
- `weather_check`: geocoding y pronóstico de Open-Meteo, gratis y sin clave.
- `ask_clarification`: pregunta un dato necesario y termina el turno; sólo al inicio.
- `banter_ledger`: chanzas/apuestas explícitas y acotadas, sólo con memoria opt-in.

Nunca modifica estadísticas, ejecuta comandos, compra, contacta personas ni navega
libremente. Métricas, historial y ledger pueden combinarse entre sí; después de una
lectura privada se cierra web para ese turno. El diálogo por sí solo no bloquea web:
si el modelo elige buscar, se descarta **todo** el contexto privado antes de hacerlo.

## Fuentes web y privacidad

Google Search grounding es primario (`GOOGLE_API_KEY` o `GEMINI_API_KEY`). Tavily
(`TAVILY_API_KEY`, búsqueda basic) es respaldo cuando Google falta o falla.
Sin ninguno, la conversación y las otras herramientas siguen funcionando.
Una investigación consume una unidad de búsqueda, no una por cada backend.

Google sólo publica una respuesta con segmentos respaldados por metadatos válidos y
fuentes publicables. La comprobación valida procedencia y cobertura, **no** demuestra
que una fuente diga la verdad. Si falla, se intenta Tavily. Tavily sólo publica
citas literales seleccionadas por IDs y validadas contra los fragmentos recibidos.
Ambos caminos incluyen enlaces, fecha de consulta y tipo de respuesta. Si no alcanza
la evidencia, no se rellenan huecos: se informa el límite y se ofrecen enlaces reales.
No se hace extracción libre ni se guardan respuestas web para usarlas como prueba.

Se retiró `knowledge.json` del camino activo: se escribía pero no se consultaba.
Los archivos históricos no se borran ni se importan automáticamente. La utilidad
legada `core/knowledge.py` no se instancia en el bot desplegado.

Las preguntas y el contexto habilitado viajan al proveedor de inferencia; avisar a
los miembros y revisar las políticas del proveedor antes de activarlo. El buscador
recibe sólo la consulta pública actual, nunca una reformulación con mensajes privados.
No se buscan ni agregan datos personales. Secretos, emails, teléfonos y datos de
identificación/domicilio explícitos se filtran antes del contexto o la memoria;
el filtro conservador no detecta todas las formas de información sensible.
Religión, etnia, género, salud y sexualidad no se convierten en perfiles.

## Memoria opt-in y borrado preciso

`AI_CHANNEL_MEMORY=true`, junto con historial habilitado, activa curador y ledger.
Ver [MEMORIA_CANAL.md](MEMORIA_CANAL.md). Se observan hasta 100 filas pendientes en RAM;
cada 40 mensajes, o 2 horas con 10 pendientes, puede correr el curador. Separación
mínima 15 minutos, reintento tras fallo 30 minutos, máximo 24 intentos/día.
Conserva hasta 30 bullets por 14 días, con evidencia literal; chanzas vencen a los 30 días.

Los IDs de mensaje/canal de la evidencia son metadatos locales: no se mandan al LLM.
Editar o borrar la fuente invalida sus resúmenes y las curaciones en curso.
El owner puede revocar una fuente con `!botonborrar ID_MENSAJE [ID_CANAL]`.
No es borrado por nombre ni borra mensajes de Discord o chanzas sin procedencia.
`!olvidar` / `!resetboton` sólo explica que la conversación es compartida; no borra nada.

## Operación y activación

Variables secretas sólo en Railway o entorno, nunca en Discord/chat/Git:

```env
AI_ENABLED=true
AI_GUILD_ID=id_del_unico_servidor
AI_CHANNEL_ID=id_del_canal_habilitado
AI_ALLOW_PAID=false
GOOGLE_API_KEY=clave_de_google
# Opcionales: fallbacks gratuitos y búsqueda de respaldo
GROQ_API_KEY=clave_de_groq
CEREBRAS_API_KEY=clave_de_cerebras
AI_API_KEY=clave_de_openrouter
TAVILY_API_KEY=clave_de_tavily
# Datos privados y memoria: consentimiento separado, por defecto apagados
AI_SHARE_METRICS=false
AI_CHANNEL_MEMORY=false
```

Sin `AI_PROVIDER` ni `AI_API_KEY`, elige el primer proveedor con clave de
google → groq → cerebras. OpenRouter usa por defecto `cohere/north-mini-code:free`;
su catálogo cambia. Los modelos/URLs están fijados en el código. El mini-juez
opcional (`AI_ROUTER_PROVIDER`) usa elección `auto` y **sí** consume una generación
y presupuesto; si falla, el principal decide dentro de los mismos límites.
Las opciones legacy pagas no son necesarias ni se activan en esta configuración.
Los topes locales no sustituyen desactivar facturación y controlar cuotas externas.

Las métricas históricas siguen siendo globales por usuario, no por servidor:
el asistente se niega a funcionar si el bot está en más de un servidor.
Para apagarlo: `AI_ENABLED=false`. Para desactivar diálogo/historial: `AI_HISTORY=false`.
Volumen persistente necesario para conservar JSON entre redeploys.

`!botonestado` muestra límites; `!botonmemoria`, recuerdos y uso del curador, sin modelo.
`!botonmetricas` es sólo para `DISCORD_OWNER_ID`: bolsas, latencias p50/p95, errores,
429 y última curación, sin preguntas, respuestas, nombres ni IDs de usuarios.
La telemetría es acotada y desde el último reinicio, no un historial durable.
Los avisos automáticos son mensajes de servicio (milestones, party, resumen diario),
no participación en la charla; conservan plantillas si falla el proveedor.
Resumen diario a `AI_DIGEST_HOUR_UTC` (por defecto 21:00 UTC).

## Verificación sin costo

```text
python -m pytest tests -q
python -m scripts.eval_boton
```

El replay usa conversaciones sintéticas y proveedores simulados: valida el harness,
no demuestra comprensión ni calidad de un modelo real. Los tests anti-drift comparan
límites activos y docs. CI corre estas verificaciones sin claves; Railway sólo espera
su resultado si se habilita **Wait for CI** en la integración GitHub. Sin ese ajuste,
push y CI pueden desplegar/correr en paralelo. La verificación no usa claves de modelos
ni tokens de deploy; el reconciliador existente conserva su token de Railway.
El reconciliador nocturno existente también exige el último CI exitoso para el SHA
exacto antes de pedir un deploy; no toma un verde viejo o de otro commit como prueba.

Tras deploy: probar llamado vacío en medio del hilo, mención, reply, cambio de tema,
pregunta de métricas, una web con fuentes y fecha, hilo público y rechazo en privado.
No hay validación live de este cambio sin claves/logs de Railway. Rotar cualquier
token que se haya pegado en una conversación antes de volver a usarlo.
