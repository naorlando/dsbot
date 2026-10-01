# Asistente ligero: diseño, alternativas y activación

Investigación: 1 de octubre de 2026. Precios en USD, sin impuestos. Es una primera
versión opcional; sin claves y sin `AI_ENABLED=true` el bot conserva su comportamiento.

## Qué hace

- `!boton ¿Quién jugó más esta semana?` / `!ask ...` / `!pregunta ...`: conversación breve; Botón elige una herramienta permitida.
- `!ask ¿Cuánto tiempo jugué hoy?`: datos de quien pregunta, sin identificadores enviados al modelo.
- `!boton ¿Qué comando muestra el ranking de voz esta semana?`: consulta la ayuda pública incluida en el deploy.
- `!boton ¿Qué novedades tenés?`: consulta las novedades del bot.
- `!buscar ¿Cómo salió Boca contra River el 27 de septiembre de 2026?`: una búsqueda web explícita con fuentes.
- `!buscar ¿Cuánto está el dólar blue hoy en Argentina?`: búsqueda, no recomendación financiera.

No escucha conversaciones, no lee el historial del canal, no recibe audio y no responde a cada
mensaje. Invocación por comando de texto. No hay SQL libre, ejecución de código,
escritura de estadísticas, archivos, compras, mensajes privados ni navegación libre.
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
usa 2–3 llamadas, no necesariamente una. El bot limita a 40 llamadas/día compartidas
por todo el servidor (también cuenta los intentos fallidos). No hace fallback a modelos pagos.
Un modelo Qwen/Kimi `:free` específico sólo debe fijarse después de confirmar que sigue
disponible y soporta herramientas; el catálogo gratuito cambia.

### Búsqueda web separada

[Tavily](https://docs.tavily.com/documentation/api-credits) ofrece 1.000 créditos/mes
sin tarjeta; búsqueda basic = 1 crédito. El bot usa sólo basic, máximo 3 extractos,
sin páginas completas, sin respuesta generada por Tavily y sin parámetros automáticos
que puedan cambiar el costo. Tope local: 20 búsquedas/día y 600/mes. No habilitar
pay-as-you-go ni recarga automática en el proveedor para un piloto gratis.

La búsqueda ocurre con `!buscar` o cuando Botón elige `search_web` desde `!boton`,
`!ask` o `!pregunta`. Siempre usa el texto original que escribió el usuario.
No se permite que el modelo genere consultas que filtren datos del servidor;
en una búsqueda no se exponen herramientas de métricas. Los resultados de web son
datos no confiables; el prompt no les concede autoridad. El bot agrega los enlaces
reales retornados por Tavily, pero no garantiza que un extracto sea actual o correcto.
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
Sólo se persiste `assistant_usage.json`, unos pocos cientos de bytes; no crece con chats.
La RAM adicional no se midió en producción, pero se limita el tamaño de respuestas
HTTP a 256 KiB, las preguntas a 800 caracteres y los resultados de herramientas a 4.000.
Los 500 MB del volumen son almacenamiento, no RAM ni presupuesto de API.

Una consulta a la vez, sin cola; cooldown compartido de 45 segundos por usuario entre
todos los alias. Máximo 3 llamadas de modelo, 2 herramientas en total y 1 búsqueda por
pregunta; 400 tokens máximos de salida por llamada, 18 segundos de espera de red y
60 segundos de tiempo total. Sin reintentos automáticos.
Memoria conversacional: últimos 5 mensajes (usuario y Botón juntos), por persona,
servidor y canal, en RAM. Vence tras 30 minutos sin uso, máximo 64 conversaciones y
800 caracteres por mensaje. Reiniciar/deployar la borra. Los resultados privados
de métricas se reemplazan por una nota sin cifras/nombres. No persiste llamadas de
herramientas ni claves. `!olvidar` borra la memoria propia sin gastar API.
Los contadores se guardan atómicamente antes de enviar cada llamada. Si el archivo
está corrupto o no se puede guardar, se bloquean nuevas llamadas. Sólo una réplica:
el presupuesto no es un contador distribuido para varias instancias.

## Privacidad y alcance de métricas

Las preguntas viajan al proveedor elegido. Una búsqueda envía el texto original también a Tavily.
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
# Opcional: sin esta clave, Botón no tiene búsqueda web
TAVILY_API_KEY=clave_de_tavily
```

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
2. Probar `!ask hola` en el canal permitido y comprobar que no busca web.
3. Probar `!ask cuánto jugué hoy` y contrastar con datos diarios/comandos existentes.
4. Probar `!buscar dólar blue hoy en Argentina`; verificar fuente y fecha en el enlace.
5. Confirmar rechazo en DMs/otro canal y que `!ask` seguido de `!buscar` tiene cooldown.
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
validada → respuesta. Las únicas herramientas son `get_metrics`, `get_bot_help`,
`search_web` y `ask_clarification`; esta última pregunta al usuario y termina el turno
sin consultar otra herramienta. No hay shell, SQL, escritura ni rutas elegidas por el modelo. La ayuda
sale de `docs/COMANDOS.md` y `docs/UPDATES.md`, no de una lectura arbitraria de GitHub.
Después de consultar métricas se bloquea web, y viceversa, incluso si el modelo
intenta pedirla. Los logs sólo registran modelo, costo y nombre de herramienta, no chats.
`!botonestado` permite verificar herramientas habilitadas y límites sin costo de API.
La tarea manual `Boton manual metrics configuration` de GitHub Actions permite
activar/desactivar sólo `AI_SHARE_METRICS` usando el token existente de Railway, sin
mostrar secretos ni iniciar un deploy. No se ejecuta por cron ni por cada push.
