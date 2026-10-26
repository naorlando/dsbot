# Asistente ligero: diseño, alternativas y activación

Investigación: 1 de octubre de 2026. Precios en USD, sin impuestos. Es una primera
versión opcional; sin claves y sin `AI_ENABLED=true` el bot conserva su comportamiento.

## Qué hace

- `!boton ¿Quién jugó más esta semana?`: conversación breve; Botón elige una herramienta permitida.
- `!boton ¿Cuánto tiempo jugué hoy?`: datos de quien pregunta, sin identificadores enviados al modelo.
- `!boton ¿Qué comando muestra el ranking de voz esta semana?`: consulta la ayuda pública incluida en el deploy.
- `!boton ¿Qué novedades tenés?`: consulta las novedades del bot.
- `!boton ¿Cómo salió Boca contra River el 27 de septiembre de 2026?`: web con fuentes verificadas, sin comando aparte.
- `!boton ¿Cuánto está el dólar blue hoy en Argentina?`: búsqueda, no recomendación financiera.

No escucha audio y no responde a cada mensaje. Invocación por comando de texto. La única
lectura de conversaciones es la nueva herramienta `search_channel_history`: páginas el
historial reciente de **sólo el canal habilitado** con ventana fija (últimos 500 mensajes,
14 días), palabras de la pregunta del usuario, sin IDs, sin adjuntos y sobre todo texto ya
público en ese canal. No hay SQL libre, ejecución de código, escritura de estadísticas,
archivos, compras, mensajes privados ni navegación libre.
Las futuras herramientas deben ser funciones permitidas con argumentos validados.

## Opciones investigadas

| Opción | Entrada / salida por millón de tokens | Para este bot |
| --- | --- | --- |
| [OpenRouter free](https://openrouter.ai/docs/guides/routing/routers/free-router) | $0 / $0 | Recomendado para el piloto sin costo. Modelos variables; selecciona compatibles con herramientas. No garantiza disponibilidad/calidad uniforme. |
| [Qwen 3.7 Flash, Singapore International, ≤32K](https://www.alibabacloud.com/help/en/model-studio/model-pricing) | $0.030 / $0.130 | Alternativa barata más predecible. Snapshot `qwen3.7-flash-2026-07-15`; sin thinking. Cuota inicial promocional de 1M tokens válida 90 días, no gratis para siempre. |
| [DeepSeek Flash](https://api-docs.deepseek.com/quick_start/pricing/) | $0.15–0.30 / $0.60–1.20, entrada sin caché | API paga; precios off-peak/peak. `deepseek-flash`; thinking apagado explícitamente. Más capacidad de la necesaria para un piloto. |
| [Kimi K2.6](https://platform.kimi.ai/docs/guide/kimi-k2-6-quickstart) | Ver [tarifa vigente](https://platform.kimi.ai/docs/pricing/chat) | Admite herramientas y modo sin thinking. No elegido: su documentación advierte que su búsqueda incorporada está en actualización y no la recomienda por ahora. No pude verificar los números de su tabla dinámica, por eso no los estimo. |

[OpenRouter](https://openrouter.ai/docs/api_reference/limits) ofrece 50 llamadas/día
y 20/minuto para modelos gratuitos sin compras previas; una pregunta con herramientas
usa 2–3 llamadas, no necesariamente una. El bot limita a 120 llamadas/día compartidas
por todo el servidor (también cuenta los intentos fallidos). No hace fallback a modelos pagos.
Un modelo Qwen/Kimi `:free` específico sólo debe fijarse después de confirmar que sigue
disponible y soporta herramientas; el catálogo gratuito cambia.

### Búsqueda web separada

[Tavily](https://docs.tavily.com/documentation/api-credits) ofrece 1.000 créditos/mes
sin tarjeta; búsqueda basic = 1 crédito. El bot pide hasta 5 candidatos y acepta hasta
3 fuentes; excluye resultados sociales ruidosos y filtra versiones/fechas requeridas.
Puede hacer una extracción basic de hasta 2 URLs ya aceptadas, con 5 fragmentos por fuente;
no permite URLs elegidas por el modelo. Ambas llamadas consumen una unidad local de
presupuesto antes de enviarse. Tope local: 20 llamadas web/día y 600/mes (hasta 10
preguntas/día si todas requieren extracción). Sin respuesta generada por Tavily ni
parámetros automáticos que cambien el costo. No habilitar
pay-as-you-go ni recarga automática en el proveedor para un piloto gratis.

La búsqueda ocurre con un enrutador determinista para consultas que
necesitan evidencia, o cuando Botón elige `search_web` desde `!boton`.
Tres respuestas no dependen del modelo (los modelos free chicos fallan ahí):

- **Dólar**: el parser lee compra/venta del texto de las páginas y responde sin
  llamadas de modelo (`stage=evidence route=official_dollar` en logs).
- **Historial**: preguntas tipo "por sus mensajes, ¿dónde está X?" o "¿cuándo
  hablamos de Y?" escanean el channel determinísticamente; el modelo redacta con
  las filas dadas y las lleva injectadas como datos (log `stage=history forced=true`).
  Si aun así suelta un eco de instrucciones, la respuesta es el resumen
  determinista de filas (`stage=model finish=echo_fallback`).
- **Evidencia**: un `insufficient` perezoso con fuentes en la mesa recibe hasta 2
  re-reads forzados (`stage=evidence status=insufficient_retry`).
- **Partidos**: las respuestas de "¿cómo salió X?" conservan sólo la cita del
  partido más fresco (año, luego jornada/fecha; `stage=evidence status=freshest_filter`).
  Un modelo chico que citaba tres partidos distintos como una sola respuesta.
- **Calidad web en partidos** (portaba la Serie C italiana de sportytrader para
  "¿cómo salió Boca?"): la búsqueda futbolística usa modo `topic=news` de Tavily
  con ventana de una semana y profundidad avanzada; además las fuentes deben
  nombrar al equipo (`required`) y toda cita publicada debe contener marcador
  (`2-1`, "ganó/perdió/empató/penales"; `status=score_filter`). Sin marcador →
  `insufficient` y re-lectura, nunca prosa de ambiente.
- **"Cuánto salió Boca"** es web-pregunta, no aclaración: `cuanto salio` + equipo
  de fútbol entra directo al modo partido de arriba, con default del último
  partido y sin ofrecer `ask_clarification` (el modelo preguntaba en tres pasos).
- **Herramientas gratis sin clave** (`core/assistant_tools.py`): `calc`
  (aritmética exacta con evaluador propio, sin `eval`), `wiki_summary`
  (búsqueda + resumen de Wikipedia ES, endpoints públicos) y `weather_check`
  (Open-Meteo: geocoding + pronóstico de 3 días). No gastan presupuesto de
  Tavily; HTTP acotado (timeout, techo de bytes, fail-closed). Se ofrecen según
  intent detectado (quién es / clima / cuentas), no de menú en cada turno.
- **Scaffolds generativos**: itinerarios, recetas y recomendaciones entran con
  la estructura de respuesta pre-construida en el system prompt (ruta por días,
  ingredientes/pasos, 3-5 opciones con por qué), así el modelo chico no niega
  pedidos creativos ni contesta con meta del servidor.
- **Jodedera** ("sos un hdp man" / "destruite" / "matate" / "blowjob" / "t garch"):
  respuesta determinista cero modelo; la tool de aclaración sólo se ofrece si el
  mensaje es una pregunta real (`¿?` o palabra interrogativa), porque los modelos
  chicos la usaban para preguntar al voleo. Emojis o símbolos solos (sin texto)
  tampoco gastan modelo: se pide texto de vuelta con plantilla.
- **Anti-"soy un bot"**: el system prompt aclara que la sólo-lectura es de datos,
  no de conversar; preguntas generales (viajes, recetas, juegos, consejos) se
  responden directamente con conocimiento propio, sin herramientas. La lista de
  capacidades se inyecta sólo cuando el pedido es de ayuda; en otra consulta el
  modelo la recitaba como respuesta (bug del itinerario de Japón en producción).
- **Intents forzados**: "que dice X?" / "mensajes de X" van sí o sí al historial
  del canal (ganan incluso ante "busca..."); "pasame/investigá/receta" activan web.
- **Guardas de salida**: frases canned repetidas en una misma respuesta se
  colapsan a la primera (`collapse_repeat`), y si el modelo recita la nota interna
  de memoria (eco del mask) se publica "Se me trabó la lengua" en su lugar.
- Cada model call queda en logs con `stage=model finish=... calls=... preview=...`
  (primeros 150 caracteres) para auditar la conducta del proveedor free.
El harness normaliza sólo la consulta actual, quitando muletillas y preservando entidades,
versiones y fechas. El modelo no puede reescribirla.
No se permite que el modelo genere consultas que filtren datos del servidor;
en una búsqueda no se exponen herramientas de métricas. Los resultados de web son
datos no confiables; el prompt no les concede autoridad. Las respuestas web son JSON
estructurado con IDs de fuentes y citas; el harness comprueba que cada cita existe
literalmente en la evidencia y publica sólo esas citas, sin paráfrasis libres del modelo.
Los enlaces los agrega el harness sólo para las fuentes usadas. Eso impide publicar
citas inventadas, pero no garantiza que una página externa sea verdadera o pertinente.
Para pasaportes argentinos se lee la sección PASAPORTE de una URL oficial fija de
RENAPER: lectura HTML acotada, sin redirects ni URL configurable. El tarifario se
presenta directamente, sin llamar al modelo ni hardcodear importes. Es una excepción
deliberadamente pequeña a la extracción de Tavily, que omitía los precios de esa página.
Para partidos/cotizaciones que no tengan evidencia suficiente debe pedir precisión
o decir que no pudo confirmarlo. Conviene agregar APIs especializadas más adelante.

### Estimación de costo (no una promesa ni un presupuesto de facturación)

Con Qwen 3.7 Flash y suponiendo 3.000 tokens de entrada + 400 de salida por llamada:
`(3000 × 0.030 + 400 × 0.130) / 1.000.000 = $0.000142` por llamada.
1.000 preguntas con 1–3 llamadas serían aproximadamente **$0.14–0.43** sólo de modelo.
El tamaño real del prompt/herramientas cambia el cálculo. Si se sale del cupo gratis
de búsqueda, Tavily pay-as-you-go cuesta $0.008/crédito: eso dominaría el costo.
Establecer además un límite de gasto en la cuenta/API key del proveedor.

## Recursos y límites

La inferencia ocurre fuera de Railway. No se descargan pesos ni se agregan frameworks
de agentes, base vectorial, navegador, SDK de modelos ni nuevo proceso.
Se reutiliza `aiohttp` (ya es dependencia de discord.py).
Sólo se persisten `assistant_usage.json` y `assistant_ambient.json` (comentarista y
resumen diario), unos pocos cientos de bytes; no crecen con chats. El historial de
conversación para la herramienta `search_channel_history` NO se persiste: se pagea el
historial ya guardado por Discord, cero bytes propios.
La RAM adicional no se midió en producción, pero se limita el tamaño de respuestas
HTTP a 256 KiB y las preguntas a 800 caracteres. Cada fuente tiene hasta 4.501 caracteres
(extracción + snippet); la sección oficial hasta 5.000. Los resultados se serializan
como JSON completo, sin cortarlos a mitad de estructura.
Los 500 MB del volumen son almacenamiento, no RAM ni presupuesto de API.

Una consulta a la vez, sin cola; protección anti-spam compartida de 3 segundos por usuario entre
todos los alias. Máximo 4 llamadas de modelo, 3 herramientas en total y 1 búsqueda por
pregunta; 600 tokens de salida para conversación y 1000 para seleccionar evidencia web,
18 segundos de espera de API, 8 segundos para la página oficial y 60 segundos totales.
Hasta una reparación de formato/evidencia, dentro del máximo de 3 llamadas de modelo;
sin reintentos de red ni de HTTP 429. Hay además un máximo de 20 llamadas de modelo
en una ventana móvil de 60 segundos. Los errores no consumen un cooldown adicional.
Memoria conversacional: últimos 10 mensajes (usuario y Botón juntos), por persona,
servidor y canal, en RAM. Vence tras 30 minutos sin uso, máximo 64 conversaciones y
800 caracteres por mensaje. Reiniciar/deployar la borra. Los resultados privados
de métricas se reemplazan por una nota sin cifras/nombres. No persiste llamadas de
herramientas ni claves. Las búsquedas nuevas no reciben historial y sus respuestas no
se conservan como hechos: cada consulta web requiere evidencia nueva. `!olvidar` borra
la memoria propia sin gastar API.
Las aclaraciones pendientes de fecha/tipo de dólar/país se guardan aparte en RAM,
máximo 64, por la misma persona/canal y durante 30 minutos. Sólo continuaciones
acotadas retoman la pregunta del usuario; nunca usan una respuesta del modelo como
consulta. Cambiar de tema o `!olvidar` descarta esa aclaración.
Los contadores se guardan atómicamente antes de enviar cada llamada. Si el archivo
está corrupto o no se puede guardar, se bloquean nuevas llamadas. Sólo una réplica:
el presupuesto no es un contador distribuido para varias instancias.

## Privacidad y alcance de métricas

Las preguntas viajan al proveedor elegido. Una búsqueda envía la consulta actual normalizada a Tavily.
Con `AI_SHARE_METRICS=true`, el modelo recibe resúmenes de actividad, nombres visibles
y rankings de hasta cinco miembros; nunca mensajes, tokens, IDs o datos crudos del JSON.
Avisar a los miembros y revisar las políticas de datos del proveedor antes de habilitarlo.
Por defecto no se comparten métricas; hay que aceptarlo explícitamente.

La persistencia actual acumula métricas globales por usuario, **no por servidor**.
Por eso esta versión requiere `AI_GUILD_ID` y `AI_CHANNEL_ID`, rechaza DMs y se niega
a funcionar si el bot está en más de un servidor. Sólo usa miembros actuales en caché.
Datos históricos que provinieran de otros servidores no pueden separarse retroactivamente.
Antes de habilitar en un bot multi-servidor hay que migrar el almacenamiento.
Tiempo semanal/mensual se calcula desde `daily_minutes`, no desde totales históricos.
Mensajes sólo tienen contador histórico; no se presentan como mensajes de la semana.
Las sesiones aún abiertas pueden no estar contabilizadas; nombres de juegos/usuarios
se tratan como datos, no instrucciones. La salida no puede generar menciones masivas.
No se guardan preguntas/respuestas en logs del asistente (los proveedores tienen sus propias políticas).

## Activación en Railway

Necesita Python 3.12 recomendado y el Message Content Intent ya utilizado por el bot.
Crear las claves en las cuentas de los proveedores y cargarlas como **Variables** de
Railway. No pegarlas en Discord, en el chat ni en archivos del repositorio.

```env
AI_ENABLED=true
AI_PROVIDER=openrouter
AI_MODEL=openrouter/free
AI_API_KEY=clave_del_proveedor
AI_ALLOW_PAID=false
AI_GUILD_ID=id_del_unico_servidor
AI_CHANNEL_ID=id_del_canal_habilitado
AI_SHARE_METRICS=true
# Opcional: modelo :free de repuesto. Si OpenRouter devuelve 429 del modelo principal,
# reintenta UNA vez con este. No hay fallback a modelos pagos.
AI_FALLBACK_MODEL=google/gemma-4-31b-it:free
# Opcional: sin esta clave, Botón no tiene búsqueda web
TAVILY_API_KEY=clave_de_tavily
```

```env
AI_ENABLED=true
AI_PROVIDER=openrouter
AI_MODEL=openrouter/free
AI_API_KEY=clave_del_proveedor
AI_ALLOW_PAID=false
AI_GUILD_ID=id_del_unico_servidor
AI_CHANNEL_ID=id_del_canal_habilitado
AI_SHARE_METRICS=true
# Opcional: modelo :free de repuesto. Si OpenRouter devuelve 429 del modelo principal,
# reintenta UNA vez con este. No hay fallback a modelos pagos.
AI_FALLBACK_MODEL=google/gemma-4-31b-it:free
# Opcional: sin esta clave, Botón no tiene búsqueda web
TAVILY_API_KEY=clave_de_tavily
```

Sin `AI_MODEL` el código ya no usa `openrouter/free` (ID inexistente en el catálogo actual
de OpenRouter): el default es `cohere/north-mini-code:free`, probado con API real.

### Modelo más capaz, mismo cero pesos

Los modelos free chicos de OpenRouter (north-mini) se quedan cortos citando
literal y llamando tools. El upgrade $0 real es **Google AI Studio** (free tier, sin
tarjeta): cargar `GOOGLE_API_KEY` o `GEMINI_API_KEY` en Railway basta — el chain
toma Google como principal (`AI_PROVIDER=google` o por default de claves) y OpenRouter
queda de repuesto. La intensidad del modelo tampoco muda el presupuesto del bot.

### Mini-juez de herramientas (opcional): `AI_ROUTER_PROVIDER`

Los modelos free chicos no se dan cuenta de que deben llamar una herramienta.
Opcionalmente se delega la DECISIÓN a un mini-modelo llave en mano y el principal
sólo redacta: una llamada forzada de ~10 tokens, mismo presupuesto `llm` (cuenta
como su llamada), y si el juez falla se usa el proveedor principal igual (fail-open).

| `AI_ROUTER_PROVIDER` | Modelo del juez | Clave requerida |
| --- | --- | --- |
| `groq` (recomendado) | el modelo fijo del chain de Groq | `GROQ_API_KEY` |
| `cerebras` | el modelo fijo del chain de Cerebras | `CEREBRAS_API_KEY` |
| `google` | el modelo fijo del chain de Google | `GOOGLE_API_KEY` |
| `openrouter` | el que indique `AI_ROUTER_MODEL` (debe ser `:free`) | `AI_API_KEY` |

Sin la variable, el comportamiento queda como siempre (el principal decide las
tools, con el blindaje determinista de arriba cubriendo los casos conocidos).

### Chain de proveedores free (verificado contra sus docs el 25/10/2026)

Además del principal, el asistente rota ante 429 entre proveedores **que tengan clave
configurada**; la rotación arranca en el siguiente proveedor por pregunta (round-robin)
y el fallback `AI_FALLBACK_MODEL` de OpenRouter queda como último intento. Endpoints
fijos en código:

| Variable | Proveedor | Endpoint en código | Modelo fijo |
| --- | --- | --- | --- |
| `GOOGLE_API_KEY` (o `GEMINI_API_KEY`) | Google AI Studio | `generativelanguage.googleapis.com/v1beta/openai/chat/completions` | `gemini-3.5-flash-lite` |
| `GROQ_API_KEY` | Groq | `api.groq.com/openai/v1/chat/completions` | `openai/gpt-oss-120b` |
| `CEREBRAS_API_KEY` | Cerebras | `api.cerebras.ai/v1/chat/completions` | `gpt-oss-120b` |
| `AI_API_KEY` | OpenRouter | `openrouter.ai/api/v1/chat/completions` | el que indique `AI_MODEL` |

Reglas del chain: es un failover acotado (máximo 1 request por proveedor y por pregunta,
presupuesto `llm` cobrado UNA vez), no hay fallback a modelos pagos y los endpoints no
son configurables. `AI_PROVIDER=google`, `groq` o `cerebras` fijan el proveedor
principal con modelo fijo del código (`AI_MODEL` se rechaza en ellos; para otro
endpoint/modelo existe `AI_PROVIDER=custom` con URL OpenAI-compatible propia, que exige
`AI_ENDPOINT` + `AI_MODEL`, https (o http sólo con `AI_INSECURE_ENDPOINT=true` para
red interna) y `AI_ALLOW_PAID=true`). Sin `AI_PROVIDER` y sin `AI_API_KEY`, el bot elige
el primero de google → groq → cerebras con clave cargada.

### Mensajes automáticos (ambient) y resumen diario

`AI_SHARE_METRICS` no influye aquí. El comentarista usa su propio presupuesto
`assistant_ambient.json` (default 240/día, variable `AI_AMBIENT_LIMIT`); siempre cae a
plantilla determinista si el proveedor o el presupuesto no dan, así ninguna notificación
se marea. Se usa en milestones de reconexión (10/25/25… conexiones), party armada y el
resumen diario nocturno del canal del asistente, a las
`AI_DIGEST_HOUR_UTC` (default 21:00 UTC). Para apagar el historial como herramienta:
`AI_HISTORY=false`.

Cambiar a Qwen, sólo si se acepta el costo:

```env
AI_PROVIDER=qwen
AI_MODEL=qwen3.7-flash-2026-07-15
AI_ALLOW_PAID=true
AI_API_KEY=clave_model_studio_singapore
```

También se admite `AI_PROVIDER=deepseek` y `AI_MODEL=deepseek-flash`, con opt-in pago.
Los endpoints están fijados en el código; no hay URL arbitraria configurable.
Para apagar sin afectar el bot: `AI_ENABLED=false` y aplicar las variables.

## Prueba de aceptación después de cargar las claves

1. Confirmar en logs que carga `cogs.assistant`, sin imprimir claves.
2. Probar `!boton hola` en el canal permitido y comprobar que no busca web.
3. Probar `!boton cuánto jugué hoy` y contrastar con datos diarios/comandos existentes.
4. Probar `!boton dólar blue hoy en Argentina`; verificar fuente y fecha en el enlace.
5. Confirmar rechazo en DMs/otro canal y que dos `!boton` seguidos tienen cooldown.
6. Observar Activity/Usage en el proveedor: sin fallback pago, sin saldo utilizado
   en el modo gratuito. Configurar tope externo si se elige modelo pago.

Además de las pruebas automáticas con proveedores simulados, se probaron las tres
herramientas contra las APIs reales el 1 de octubre de 2026: ayuda, métricas ficticias
y búsqueda con enlaces. OpenRouter reportó costo cero; Tavily utilizó búsqueda basic.
El router gratuito puede elegir modelos diferentes y fallar por disponibilidad.
En este servidor se fija `cohere/north-mini-code:free`: las pruebas reales de métricas,
web y memoria respondieron dentro del límite. Sigue siendo gratuito y sin fallback;
ningún proveedor gratis garantiza disponibilidad. El valor por defecto del código
sigue siendo `openrouter/free` para instalaciones nuevas.

Para repetir sin datos reales: exportar claves sólo al entorno del proceso y ejecutar
`python -m scripts.test_assistant_live help`, `metrics` o `web`. No imprime ni guarda claves.

## Harness de Botón

`cogs/assistant.py` aplica canal/servidor permitidos, cooldown, concurrencia y límite
total de tiempo. `core/assistant.py` mantiene el bucle pequeño de decisión → herramienta
validada → respuesta. Las herramientas son `get_metrics`, `query_stats` (exploración de
juegos, miembros y días del registro propio, nombres visibles, sin IDs), `get_bot_help`,
`search_channel_history` (el historial reciente del canal habilitado, ventana fija de
500 mensajes y 14 días, keywords tomadas de la pregunta, fecha/autor/snippet, sin IDs;
no se pagina con args del modelo y ni mezcla resultados con métricas ni web), `search_web`
y `ask_clarification`; esta última pregunta al usuario y termina el turno
sin consultar otra herramienta. No hay shell, SQL, escritura ni rutas elegidas por el modelo. La ayuda
sale de `docs/COMANDOS.md` y `docs/UPDATES.md`, no de una lectura arbitraria de GitHub.
Después de consultar métricas se bloquea web, y viceversa, incluso si el modelo
intenta pedirla. Los logs correlacionan cada ejecución mediante `trace`: ruta, pasos,
presupuestos, herramienta y argumentos enumerados, dominio/índice de fuentes,
extracción, tokens, costo reportado, tiempos, terminación y validación. No registran
preguntas, respuestas, claves, nombres de miembros, métricas ni historial. Para
debug de APIs reales, `scripts.test_assistant_live --debug` muestra evidencia y
salidas del modelo sólo en escenarios públicos fijos, nunca una conversación real.
`!botonestado` permite verificar herramientas habilitadas y límites sin costo de API.
La tarea manual `Boton manual metrics configuration` de GitHub Actions permite
activar/desactivar sólo `AI_SHARE_METRICS` usando el token existente de Railway, sin
mostrar secretos ni iniciar un deploy. No se ejecuta por cron ni por cada push.

## Patrones investigados con Context7

Se consultó el CLI oficial de [Context7](https://github.com/upstash/context7) para
`/huggingface/smolagents`. No se instaló un framework en el bot ni se ejecutaron
templates de terceros. Se adoptaron patrones, no capacidades de ejecución:

- [smolagents ToolCallingAgent](https://huggingface.co/docs/smolagents/reference/agents):
  herramientas JSON explícitas, pasos máximos, callbacks de observación y validación
  de respuesta final. No se usa CodeAgent ni ejecución Python.
- [Pydantic AI: validación de salidas](https://pydantic.dev/docs/ai/core-concepts/output/)
  y [herramientas](https://pydantic.dev/docs/ai/tools-toolsets/tools-advanced/): contrato
  de datos, herramientas habilitadas por etapa y reparación acotada. La implementación
  usa dataclasses/JSON estándar, sin sumar SDK ni dependencia.
- [mini-SWE-agent](https://github.com/SWE-agent/mini-swe-agent): útil como referencia
  de bucle pequeño; descartado como template para Discord porque está orientado a
  agentes de programación con shell. Botón nunca tiene una herramienta de comandos.
- La búsqueda de “dots agents” no permitió verificar un template adecuado: el repo
  encontrado redirigía a un proyecto distinto. No se importó ni ejecutó código de allí.

## Regresiones de búsqueda (1 de octubre de 2026)

Pruebas reales: la pregunta del 9/12/2018 devolvió la final River–Boca con cita verificable;
pasaporte devolvió los importes de RENAPER mediante lectura oficial sin modelo.
La recuperación de MU 99b preserva esa versión; sus fuentes recuperadas no bastan
por sí solas para prometer una guía completa. Pruebas simuladas bloquean precios,
campeonatos y películas inventadas, citas inexistentes, fuentes falsas, JSON cortado
y contaminación del tema anterior. OpenRouter devolvió HTTP 429 durante la ronda:
no se habilitaron pagos ni fallback; no se declara validación real de todos los casos.
