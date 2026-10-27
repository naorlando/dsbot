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
usa 2–3 llamadas, no necesariamente una. El bot limita a 400 llamadas/día compartidas
por todo el servidor (también cuenta los intentos fallidos). No hace fallback a modelos pagos.
Un modelo Qwen/Kimi `:free` específico sólo debe fijarse después de confirmar que sigue
disponible y soporta herramientas; el catálogo gratuito cambia.

### Búsqueda web (agéntica)

La web se resuelve en dos capas, y el **modelo** decide cuándo buscar eligiendo
`search_web` del menú (o el `!boton` explícito entra directo):

1. **Google Search grounding** (primario, `GOOGLE_API_KEY`): llamada nativa a
   `:generateContent` con el tool de servidor `google_search`; el índice real de
   Google devuelve la respuesta ya anclada y las URLs de origen
   (`groundingChunks`). La respuesta aterrizada se publica tal cual, con pie
   "Fuentes consultadas" si el texto no trajo citas. Cero llamadas de modelo.
2. **Tavily** (respaldo): sólo si no hay clave de Google o el grounding falla
   (429/5xx/respuesta vacía). Búsqueda `basic`, hasta 5 candidatos, acepta hasta
   3 fuentes; excluye redes ruidosas y valida que cada cita exista literalmente
   antes de publicar (`render_evidence`). Sin extracción de URLs ni respuesta
   generada por Tavily ni parámetros automáticos.

Tope local: 20 búsquedas/día y 600/mes; una investigación completa (grounding o
Tavily) consume **una** unidad, cobrada antes de enviarse. Sin Tavily ni Google
el bot responde que el buscador no está conectado y el resto sigue funcionando.

Ya no hay rutas deterministas: dólar, pasaporte, Wikipedia, partidos, scaffolds,
banter y ecos de historial **no tienen código aparte** — el agente resuelve todo
con su menú de tools y su system prompt. Lo único que queda fuera del modelo es
seguridad y límites: validación de argumentos, presupuesto, guardas de secretos/enlaces,
`collapse_repeat` y los re-reads de evidencia (un `insufficient` perezoso con
fuentes en la mesa recibe hasta 2 reintentos; un JSON inválido tras el segundo
intento falla cerrado, nunca publica citas inventadas).

- **Herramientas gratis sin clave** (`core/assistant_tools.py`): `calc`
  (aritmética exacta con evaluador propio, sin `eval`) y `weather_check`
  (Open-Meteo: geocoding + pronóstico de 3 días). HTTP acotado (timeout, techo
  de bytes, fail-closed). El menú completo se ofrece en cada turno sin datos
  aún: el modelo elige; `ask_clarification` sólo en el turno 0.
- **Jodedera / emojis / preguntas generales**: sin filtro previo — llegan al
  modelo y se resuelven con su propio criterio (charla, viaje, receta, etc.).
- **Anti-"soy un bot"**: el system prompt fijá que si es creativo o general se
  responde completo con conocimiento propio, sin tools ni meta de capacidades.
- **Guardas de salida**: frases canned repetidas se colapsan (`collapse_repeat`),
  y si el modelo recita la nota interna de memoria se publica "Se me trabó la
  lengua" en su lugar.
- Cada model call queda en logs con `stage=model finish=... calls=... preview=...`
  (primeros 150 caracteres) para auditar la conducta del proveedor free.
El harness normaliza la consulta actual (quita muletillas, preserva entidades y
fechas); el modelo no puede reescribirla al buscar. No se permite que consultas
web filtren datos del servidor; métricas e historial no se mezclan con web en la
misma respuesta — pero sí se mezclan entre sí: tras leer el servidor, el modelo
puede seguir perforando con `get_metrics` → `query_stats` → `search_channel_history`
(sólo `search_web` sale del menú). Las llamadas de herramienta inválidas, múltiples
o fuera de turno no matan la pregunta: se reencaminan con un nudge y el modelo
corrije en el mismo turno; al segundo error sale un error humano ("Se me cruzaron
los cables con las herramientas; preguntame de vuelta. 😅"), nunca tool-speak.
Los resultados de web son datos no confiables; el path Tavily sólo publica citas
literales de fuentes existentes.
Para partidos/cotizaciones sin evidencia suficiente el modelo debe pedir precisión
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
Las aclaraciones pendientes no se guardan aparte: `ask_clarification` es una tool
más en el menú (sólo turno 0) y la continuidad queda en la memoria conversacional
normal, que vence tras 30 minutos. La protección doxxing (dateas/IP/DNI/domicilio)
es la única decisión del harness: rechaza en frío sin gastar modelo ni guardar nada.
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
# Opcional: sin Tavily ni Google, Botón no tiene búsqueda web
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
# Opcional: sin Tavily ni Google, Botón no tiene búsqueda web
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
sólo redacta: una llamada forzada de ~10 tokens que **no** consume el presupuesto
`llm` (es lo más barato de todo el flujo), y si el juez falla se usa el proveedor
principal igual (fail-open).

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
