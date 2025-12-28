# 🏗️ Arquitectura del Bot de Discord - Recorrido Completo

## 📋 Tabla de Contenidos

1. [Visión General](#visión-general)
2. [Arquitectura](#arquitectura)
3. [Estructura de Directorios](#estructura-de-directorios)
4. [Clases Principales](#clases-principales)
5. [Módulos Core](#módulos-core)
6. [Sistema de Cogs](#sistema-de-cogs)
7. [Algoritmos y Lógicas](#algoritmos-y-lógicas)
8. [Flujos de Datos](#flujos-de-datos)
9. [Patrones de Diseño](#patrones-de-diseño)
10. [Persistencia de Datos](#persistencia-de-datos)

---

## 🎯 Visión General

**Bot de Discord para tracking de actividad** que registra:
- 🎮 Juegos jugados (con tiempo)
- 🔊 Tiempo en canales de voz
- 💬 Mensajes enviados
- 👍 Reacciones y emojis
- 📎 Stickers y attachments
- 📱 Conexiones diarias
- 🔥 Rachas de actividad

**Stack Tecnológico:**
- **Framework:** discord.py (async/await)
- **Arquitectura:** Modular con Cogs
- **Persistencia:** JSON (Railway Volume)
- **Deploy:** Railway.app
- **Tests:** pytest + unittest

---

## 🏛️ Arquitectura

### **Patrón: Modular con Extensiones (Cogs)**

```
┌─────────────────────────────────────────┐
│           bot.py (Entry Point)          │
│  - Inicialización                        │
│  - Carga de extensiones                  │
│  - Manejo de errores                     │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
┌──────▼──────┐  ┌─────▼──────┐
│   Cogs/     │  │   Core/     │
│  (Features) │  │  (Base)     │
└─────────────┘  └─────────────┘
```

### **Separación de Responsabilidades:**

```
┌─────────────────────────────────────────────────────────┐
│                    CAPA DE PRESENTACIÓN                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Commands   │  │    Embeds    │  │   UI Views   │ │
│  │  (Discord)   │  │  (Visual)    │  │ (Interactive)│ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                    CAPA DE LÓGICA                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Tracking    │  │  Cooldown    │  │  Helpers     │ │
│  │  (Events)    │  │  (Anti-spam) │  │  (Utils)     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└───────────────────────▼─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                    CAPA DE DATOS                          │
│  ┌──────────────┐  ┌──────────────┐                      │
│  │ Persistence  │  │  stats.json │                      │
│  │  (I/O)       │  │  config.json │                      │
│  └──────────────┘  └──────────────┘                      │
└───────────────────────────────────────────────────────────┘
```

---

## 📁 Estructura de Directorios

```
dsbot/
├── bot.py                    # 🚀 Entry point - Inicialización del bot
│
├── core/                     # 🔧 Módulos base (sin dependencias de Discord)
│   ├── persistence.py       # 💾 Carga/guarda JSON (stats.json, config.json)
│   ├── tracking.py          # 📊 Funciones de registro de eventos
│   ├── cooldown.py          # ⏱️ Sistema anti-spam (10 min default)
│   ├── checks.py            # ✅ Validaciones (owner, canal de stats)
│   ├── helpers.py           # 🛠️ Utilidades (spam detection, notificaciones)
│   └── voice_session.py     # 🔊 Gestión de sesiones de voz (nuevo sistema)
│
├── cogs/                     # 🎭 Extensiones modulares (features)
│   ├── events.py            # 👂 Event listeners (presence, voice, messages)
│   ├── config.py            # ⚙️ Comandos de configuración (owner-only)
│   ├── stats.py             # 📊 Loader de comandos de estadísticas
│   └── utility.py           # 🛠️ Comandos de utilidad (!bothelp)
│
├── stats/                     # 📈 Sistema de comandos de estadísticas
│   ├── commands_basic.py    # 📋 Comandos básicos (!stats, !topgames, etc)
│   ├── commands_advanced.py # 🎨 Comandos avanzados (!statsmenu, !timeline)
│   ├── commands_voice.py    # 🔊 Comandos de voz (!voicetime, !voicetop)
│   ├── embeds.py            # 🎨 Generación de embeds visuales
│   └── ui_components.py     # 🖱️ Componentes interactivos (Views, Selects)
│
├── stats_viz.py              # 📊 Visualizaciones ASCII (gráficos, charts)
├── test_bot.py              # 🧪 Suite de tests (65 tests)
│
└── data/                     # 💾 Datos persistentes (Railway Volume)
    ├── stats.json           # 📊 Estadísticas de usuarios
    └── config.json          # ⚙️ Configuración del bot
```

---

## 🏛️ Clases Principales

### **1. VoiceSession** (`core/voice_session.py`)
**Propósito:** Representa una sesión de voz activa

```python
class VoiceSession:
    - user_id: str
    - username: str
    - channel_id: int
    - channel_name: str
    - guild_id: int
    - start_time: datetime
    - notification_message: Optional[Message]
    - verification_task: Optional[Task]
    - is_confirmed: bool
    
    Métodos:
    - duration_seconds() → float
    - is_short(threshold) → bool
```

**Algoritmo:**
- Encapsula estado de sesión
- Calcula duración dinámicamente
- Verifica si es "corta" (< threshold)

---

### **2. VoiceSessionManager** (`core/voice_session.py`)
**Propósito:** Gestiona todas las sesiones de voz activas

```python
class VoiceSessionManager:
    - bot: Bot
    - active_sessions: Dict[str, VoiceSession]
    - min_duration_seconds: int = 10
    
    Métodos:
    - handle_voice_join() → Crea sesión + task de verificación
    - handle_voice_leave() → Finaliza sesión + borra notificación si < 10s
    - handle_voice_move() → Maneja cambio de canal
    - _verify_session() → Task en background (3s + 7s)
    - _cancel_session() → Limpieza
```

**Algoritmo de Verificación:**
```
1. Usuario entra → Crear VoiceSession
2. Crear task en background (no bloquea)
3. [3s delay] → ¿Sigue en canal?
   - NO → Cancelar sesión
   - SÍ → Iniciar tracking + Notificar
4. [7s delay] → ¿Sigue en canal?
   - NO → Borrar notificación
   - SÍ → Confirmar sesión (> 10s)
```

**Ventajas:**
- ✅ No bloquea event handler
- ✅ Limpieza automática de tasks
- ✅ Estado centralizado
- ✅ Sin memory leaks

---

### **3. EventsCog** (`cogs/events.py`)
**Propósito:** Maneja todos los event listeners de Discord

```python
class EventsCog(commands.Cog):
    - bot: Bot
    - voice_manager: VoiceSessionManager
    
    Listeners:
    - on_ready() → Inicialización
    - on_presence_update() → Juegos + Conexiones
    - on_voice_state_update() → Delegado a VoiceSessionManager
    - on_message() → Tracking de mensajes
    - on_reaction_add() → Tracking de reacciones
    - on_member_join/remove() → Notificaciones
```

**Flujo de Eventos:**
```
Discord Event → EventsCog → Core Module → Persistence
```

---

### **4. StatsCog** (`cogs/stats.py`)
**Propósito:** Loader de comandos de estadísticas

```python
class StatsCog(commands.Cog):
    - bot: Bot
    
    Métodos:
    - cog_load() → Carga comandos básicos/avanzados/voz
```

**Patrón:** Facade - Simplifica carga de múltiples módulos

---

### **5. ConfigCog** (`cogs/config.py`)
**Propósito:** Comandos de configuración (owner-only)

```python
class ConfigCog(commands.Cog):
    - bot: Bot
    
    Comandos:
    - !setchannel / !unsetchannel
    - !setstatschannel / !unsetstatschannel
    - !channels
    - !toggle
    - !config
    - !test
    
    UI Components:
    - ToggleView (View con botones)
    - ToggleButton (Botón interactivo)
```

---

### **6. UtilityCog** (`cogs/utility.py`)
**Propósito:** Comandos de utilidad

```python
class UtilityCog(commands.Cog):
    - bot: Bot
    
    Comandos:
    - !bothelp [categoria] → Ayuda categorizada
```

---

### **7. UI Components** (`stats/ui_components.py`)

```python
class StatsView(discord.ui.View):
    - period: str
    - timeout: 300s
    - StatsSelect (menú de selección)
    - PeriodSelect (filtro de período)

class StatsSelect(discord.ui.Select):
    - Opciones: overview, games, voice, messages, users, timeline

class PeriodSelect(discord.ui.Select):
    - Opciones: today, week, month, all
```

**Patrón:** Strategy - Diferentes visualizaciones según selección

---

## 🔧 Módulos Core

### **1. persistence.py** 💾
**Responsabilidad:** I/O de archivos JSON

```python
Funciones:
- load_config() → Dict
- load_stats() → Dict
- save_stats() → None
- save_config() → None
- get_channel_id() → Optional[int]
- get_stats_channel_id() → Optional[int]
```

**Algoritmo:**
- Detecta `/data` (Railway) o `.` (local)
- Carga JSON con valores por defecto si no existe
- Guarda con manejo de errores

**Variables Globales:**
- `config: Dict` (singleton)
- `stats: Dict` (singleton)

---

### **2. tracking.py** 📊
**Responsabilidad:** Registro de eventos en stats

```python
Funciones de Eventos:
- record_game_event() → Incrementa count, actualiza last_played
- record_message_event() → Incrementa count + characters
- record_voice_event() → Incrementa count, actualiza last_join
- record_connection_event() → Incrementa conexiones diarias + récord

Funciones de Sesiones:
- start_game_session() → Guarda current_session con timestamp
- end_game_session() → Calcula minutos, actualiza total_minutes
- start_voice_session() → Guarda current_session
- end_voice_session() → Calcula minutos, actualiza total_minutes
```

**Algoritmo de Sesiones:**
```
1. start_session() → Guarda timestamp en current_session
2. [Usuario sale/termina]
3. end_session() → Calcula diferencia
4. Si duration >= 1 minuto → Guarda en total_minutes
5. Limpia current_session
```

**Estructura de Datos:**
```json
{
  "users": {
    "user_id": {
      "games": {
        "game_name": {
          "count": 10,
          "total_minutes": 120,
          "current_session": {"start": "2025-12-28T..."}
        }
      },
      "voice": {
        "count": 5,
        "total_minutes": 60,
        "current_session": {"start": "2025-12-28T...", "channel": "General"}
      }
    }
  }
}
```

---

### **3. cooldown.py** ⏱️
**Responsabilidad:** Sistema anti-spam

```python
def check_cooldown(user_id, event_key, cooldown_seconds=600):
    """
    Algoritmo:
    1. Generar clave: "{user_id}:{event_key}"
    2. Buscar último timestamp en stats['cooldowns']
    3. Si existe y < cooldown_seconds → Retornar False
    4. Si no existe o >= cooldown_seconds → Actualizar timestamp, retornar True
    """
```

**Estructura:**
```json
{
  "cooldowns": {
    "user_id:game:Fortnite": "2025-12-28T15:30:00",
    "user_id:voice": "2025-12-28T15:25:00",
    "user_id:daily_connection": "2025-12-28T15:20:00"
  }
}
```

**Cooldowns Configurados:**
- `game:{game_name}` → 600s (10 min)
- `voice` → 600s (10 min)
- `voice_move` → 600s (10 min)
- `daily_connection` → 300s (5 min)

---

### **4. checks.py** ✅
**Responsabilidad:** Validaciones y decoradores

```python
def is_owner(ctx) → bool:
    """
    Algoritmo:
    1. Leer DISCORD_OWNER_ID (puede ser múltiple, separado por comas)
    2. Comparar ctx.author.id con lista de owners
    3. Retornar True/False
    """

@stats_channel_only() → Decorator:
    """
    Algoritmo:
    1. Obtener stats_channel_id de config
    2. Si no configurado → Permitir en cualquier canal
    3. Si ctx.channel.id == stats_channel_id → Permitir
    4. Si no → Enviar mensaje de redirección + Retornar False
    """
```

**Patrón:** Decorator Pattern

---

### **5. helpers.py** 🛠️
**Responsabilidad:** Utilidades generales

```python
def is_link_spam(message_content) → bool:
    """
    Algoritmo:
    1. Buscar URLs con regex
    2. Calcular % de contenido que son URLs
    3. Si > 70% → Spam
    4. Si solo 1-2 palabras además de URLs → Spam
    5. Retornar True/False
    """

def get_activity_verb(activity_type) → str:
    """Traduce tipo de actividad al español"""

async def send_notification(message, bot, return_message=False) → Optional[Message]:
    """
    Algoritmo:
    1. Obtener channel_id de config
    2. Buscar canal con bot.get_channel()
    3. Enviar mensaje
    4. Manejar rate limits (429) con retry
    5. Retornar mensaje si return_message=True
    """
```

---

### **6. voice_session.py** 🔊
**Responsabilidad:** Gestión centralizada de sesiones de voz

**Clases:**
- `VoiceSession` (datos)
- `VoiceSessionManager` (lógica)

**Algoritmo Principal:**
```
ENTRADA:
1. handle_voice_join() → Crear VoiceSession
2. Crear task: _verify_session() (background)
3. Task espera 3s → Verifica que sigue
4. Si sigue → start_voice_session() + Notificar
5. Task espera 7s → Verifica nuevamente
6. Si sigue → Confirmar (> 10s)
7. Si se fue → Borrar notificación

SALIDA:
1. handle_voice_leave() → Buscar sesión
2. Cancelar task si está corriendo
3. Calcular duración
4. Si < 10s → Borrar notificación
5. Si > 10s → Notificar salida (opcional)
6. end_voice_session() → Guardar tiempo
7. Limpiar sesión

CAMBIO DE CANAL:
1. handle_voice_move() → Salida del anterior + Entrada al nuevo
```

**Ventajas del Sistema:**
- ✅ No bloquea event handler
- ✅ Tasks canceladas automáticamente
- ✅ Estado centralizado
- ✅ Limpieza automática

---

## 🎭 Sistema de Cogs

### **Carga de Extensiones:**

```python
# bot.py
async def load_extensions():
    cogs = [
        'cogs.events',      # Event listeners
        'cogs.config',      # Configuración
        'cogs.stats',       # Loader de stats
        'cogs.utility',     # Utilidades
    ]
    for cog in cogs:
        await bot.load_extension(cog)
```

### **Cada Cog tiene:**

```python
async def setup(bot):
    """Función requerida para cargar el cog"""
    await bot.add_cog(CogClass(bot))
```

---

## 🧮 Algoritmos y Lógicas

### **1. Filtrado de Juegos Falsos** (`cogs/events.py`)

**Problema:** Usuarios crean Custom Rich Presence falsos

**Solución: 6 Capas de Verificación**

```python
1. Tipo de actividad != 'custom'
2. Clase en whitelist: ['Game', 'Streaming', 'Activity', 'Spotify']
3. Tiene application_id (excepto Spotify)
4. No está en blacklist (config.json)
5. Nombre no es sospechoso: ['test', 'fake', 'custom', etc]
6. Logging detallado
```

**Algoritmo:**
```
for actividad in nuevas_actividades:
    if not pasa_capa_1: continue
    if not pasa_capa_2: continue
    if not pasa_capa_3: continue
    if not pasa_capa_4: continue
    if not pasa_capa_5: continue
    # Si llegó aquí → Juego legítimo
    trackear_juego()
```

---

### **2. Tracking de Conexiones Diarias** (`core/tracking.py`)

**Algoritmo:**
```python
def record_connection_event():
    1. Obtener fecha actual (YYYY-MM-DD)
    2. Incrementar total
    3. Incrementar by_date[today]
    4. Obtener count_today
    5. Comparar con personal_record['count']
    6. Si count_today > record → Actualizar récord
    7. Retornar (count_today, broke_record)
```

**Notificaciones:**
- Milestones: 10, 25, 50 conexiones
- Récord personal: Solo si anterior >= 10

---

### **3. Visualizaciones ASCII** (`stats_viz.py`)

**create_bar_chart():**
```python
Algoritmo:
1. Encontrar valor máximo
2. Calcular escala: max_width / max_value
3. Para cada item:
   - Calcular ancho: value * escala
   - Generar barra con caracteres: '█' * ancho
   - Formatear label + barra + valor
4. Retornar string multilinea
```

**create_timeline_chart():**
```python
Algoritmo:
1. Agrupar datos por día
2. Crear matriz de caracteres (días × altura)
3. Calcular altura máxima
4. Para cada día:
   - Calcular altura proporcional
   - Dibujar columna con '█'
5. Agregar ejes y labels
```

---

### **4. Filtrado por Período** (`stats_viz.py`)

```python
def filter_by_period(stats_data, period):
    """
    Algoritmo:
    1. Calcular fecha de corte según período:
       - 'today' → Hoy
       - 'week' → 7 días atrás
       - 'month' → 30 días atrás
       - 'all' → Sin filtro
    2. Para cada usuario:
       - Filtrar daily_minutes por fecha
       - Filtrar daily_connections.by_date
    3. Retornar stats filtrados
    """
```

---

### **5. Sistema de Cooldown** (`core/cooldown.py`)

**Algoritmo:**
```python
def check_cooldown(user_id, event_key, cooldown_seconds=600):
    clave = f"{user_id}:{event_key}"
    
    if clave in stats['cooldowns']:
        ultimo_timestamp = parse(stats['cooldowns'][clave])
        tiempo_transcurrido = now() - ultimo_timestamp
        
        if tiempo_transcurrido < cooldown_seconds:
            return False  # En cooldown
    
    # Actualizar cooldown
    stats['cooldowns'][clave] = now().isoformat()
    save_stats()
    return True  # Puede ejecutar
```

**Complejidad:** O(1) - Lookup en dict

---

## 🔄 Flujos de Datos

### **Flujo 1: Usuario Entra a Voz**

```
on_voice_state_update()
    ↓
EventsCog.on_voice_state_update()
    ↓
VoiceSessionManager.handle_voice_join()
    ↓
Crear VoiceSession
    ↓
asyncio.create_task(_verify_session())
    ↓
[3s delay] → Verificar que sigue
    ↓
start_voice_session() → Guardar en stats.json
    ↓
check_cooldown() → Verificar anti-spam
    ↓
send_notification() → Enviar mensaje
    ↓
[7s delay] → Verificar nuevamente
    ↓
Si sigue → Confirmar (> 10s)
Si se fue → Borrar notificación
```

---

### **Flujo 2: Usuario Juega un Juego**

```
on_presence_update()
    ↓
EventsCog.on_presence_update()
    ↓
Detectar nuevas actividades
    ↓
Filtro multicapa (6 capas)
    ↓
Si pasa filtros:
    start_game_session() → Guardar timestamp
    record_game_event() → Incrementar count
    check_cooldown() → Verificar anti-spam
    send_notification() → Notificar
    
Cuando sale:
    end_game_session() → Calcular minutos
    Si >= 1 min → Guardar en total_minutes
```

---

### **Flujo 3: Usuario Envía Mensaje**

```
on_message()
    ↓
EventsCog.on_message()
    ↓
is_link_spam() → Verificar spam
    ↓
Si no es spam:
    record_message_event() → Incrementar count + characters
    save_stats() → Persistir
```

---

### **Flujo 4: Comando !stats**

```
Usuario: !stats
    ↓
@stats_channel_only() → Verificar canal
    ↓
stats/commands_basic.py:show_stats()
    ↓
Leer stats['users'][user_id]
    ↓
stats/embeds.py:create_overview_embed()
    ↓
Calcular totales y promedios
    ↓
Crear discord.Embed
    ↓
ctx.send(embed) → Enviar respuesta
```

---

### **Flujo 5: Comando !statsmenu (Interactivo)**

```
Usuario: !statsmenu
    ↓
@stats_channel_only() → Verificar canal
    ↓
stats/commands_advanced.py:stats_menu()
    ↓
Crear StatsView (con StatsSelect + PeriodSelect)
    ↓
Crear embed inicial
    ↓
ctx.send(embed, view=StatsView)
    ↓
Usuario selecciona opción
    ↓
StatsSelect.callback()
    ↓
Filtrar stats por período
    ↓
Crear embed correspondiente
    ↓
Actualizar mensaje con nuevo embed
```

---

## 🎨 Patrones de Diseño

### **1. Singleton Pattern**
**Uso:** `config` y `stats` en `persistence.py`
- Variables globales compartidas
- Cargadas una vez al inicio
- Accesibles desde cualquier módulo

---

### **2. Factory Pattern**
**Uso:** `setup_*_commands()` en `stats/`
- Funciones que crean y registran comandos
- Permite carga dinámica
- Evita registro duplicado

---

### **3. Strategy Pattern**
**Uso:** `StatsSelect` en `ui_components.py`
- Diferentes visualizaciones según selección
- Cada opción ejecuta estrategia diferente

---

### **4. Decorator Pattern**
**Uso:** `@stats_channel_only()` en `checks.py`
- Envuelve comandos con validación
- Reutilizable en múltiples comandos
- Separa concerns (validación vs lógica)

---

### **5. Observer Pattern**
**Uso:** Event listeners en `EventsCog`
- Bot observa eventos de Discord
- Reacciona automáticamente
- Desacoplado del framework

---

### **6. Facade Pattern**
**Uso:** `StatsCog` como loader
- Simplifica carga de múltiples módulos
- Interfaz única para comandos de stats

---

### **7. State Pattern**
**Uso:** `VoiceSession` con estados
- `is_confirmed` indica estado
- Transiciones claras (pending → confirmed → ended)

---

## 💾 Persistencia de Datos

### **Estructura de stats.json:**

```json
{
  "users": {
    "user_id": {
      "username": "Nombre",
      "games": {
        "game_name": {
          "count": 10,
          "total_minutes": 120,
          "daily_minutes": {"2025-12-28": 30},
          "current_session": {"start": "..."}
        }
      },
      "voice": {
        "count": 5,
        "total_minutes": 60,
        "daily_minutes": {"2025-12-28": 20},
        "current_session": {"start": "...", "channel": "General"}
      },
      "messages": {
        "count": 100,
        "characters": 5000
      },
      "reactions": {
        "total": 50,
        "by_emoji": {"👍": 20, "❤️": 30}
      },
      "stickers": {
        "total": 10,
        "by_name": {"sticker_name": 5}
      },
      "daily_connections": {
        "total": 25,
        "by_date": {"2025-12-28": 3},
        "personal_record": {"count": 5, "date": "2025-12-27"}
      }
    }
  },
  "cooldowns": {
    "user_id:game:Fortnite": "2025-12-28T15:30:00",
    "user_id:voice": "2025-12-28T15:25:00"
  }
}
```

### **Estructura de config.json:**

```json
{
  "channel_id": 123456789,
  "stats_channel_id": 987654321,
  "notify_games": true,
  "notify_voice": true,
  "notify_voice_leave": false,
  "notify_voice_move": true,
  "ignore_bots": true,
  "game_activity_types": ["playing", "streaming", "watching", "listening"],
  "blacklisted_app_ids": ["1435707463935594496"],
  "messages": {
    "game_start": "🎮 **{user}** está {verb} **{activity}**",
    "voice_join": "🔊 **{user}** entró al canal de voz **{channel}**"
  }
}
```

### **Algoritmo de Persistencia:**

```python
1. load_stats() → Cargar JSON o crear estructura vacía
2. [Evento ocurre]
3. Modificar stats dict en memoria
4. save_stats() → Escribir JSON completo
5. Manejo de errores (backup, retry)
```

**Optimizaciones:**
- Guarda solo cuando hay cambios
- Manejo de errores robusto
- Backup automático en Railway

---

## 🔍 Algoritmos Clave Detallados

### **1. Cálculo de Tiempo de Sesión**

```python
def end_voice_session():
    start_time = parse(current_session['start'])
    end_time = now()
    duration = end_time - start_time
    minutes = int(duration.total_seconds() / 60)
    
    if minutes >= 1:  # Threshold mínimo
        total_minutes += minutes
        daily_minutes[today] += minutes
```

**Complejidad:** O(1)

---

### **2. Ranking de Usuarios**

```python
def calcular_ranking():
    user_scores = []
    for user_id, user_data in stats['users'].items():
        score = calcular_score(user_data)  # Suma de métricas
        user_scores.append((username, score))
    
    user_scores.sort(key=lambda x: x[1], reverse=True)
    return user_scores[:limit]
```

**Complejidad:** O(n log n) - Sorting

---

### **3. Filtrado Temporal**

```python
def filter_by_period(stats, period):
    cutoff_date = calcular_fecha_corte(period)
    
    filtered_stats = {
        'users': {}
    }
    
    for user_id, user_data in stats['users'].items():
        filtered_user = {}
        
        # Filtrar daily_minutes
        filtered_user['voice'] = {
            'daily_minutes': {
                date: minutes 
                for date, minutes in user_data['voice']['daily_minutes'].items()
                if date >= cutoff_date
            }
        }
        
        filtered_stats['users'][user_id] = filtered_user
    
    return filtered_stats
```

**Complejidad:** O(n × m) donde n=usuarios, m=días

---

## 📊 Métricas y Estadísticas

### **Cálculos Realizados:**

1. **Totales:**
   - Total de juegos jugados
   - Total de tiempo en voz
   - Total de mensajes
   - Total de reacciones/stickers

2. **Promedios:**
   - Promedio de caracteres por mensaje
   - Promedio de tiempo por sesión

3. **Rankings:**
   - Top juegos (por tiempo)
   - Top usuarios (por actividad total)
   - Top emojis/stickers

4. **Tendencias:**
   - Actividad diaria (últimos 7 días)
   - Línea de tiempo
   - Comparación entre usuarios

---

## 🚀 Optimizaciones Implementadas

### **1. Cooldown System**
- Evita spam de notificaciones
- Reduce carga en Discord API
- Mejora UX

### **2. Tasks en Background**
- No bloquea event handler
- Permite múltiples verificaciones simultáneas
- Mejor performance

### **3. Lazy Loading**
- Comandos cargados bajo demanda
- Evita registro duplicado
- Menor uso de memoria

### **4. Caching de Embeds**
- Embeds reutilizables en UI
- Menos procesamiento

### **5. Threshold Mínimo**
- Sesiones < 1 minuto no se guardan
- Reduce ruido en datos
- Mejor calidad de estadísticas

---

## 🔐 Seguridad y Validaciones

### **1. Owner-Only Commands**
- `is_owner()` verifica múltiples owners
- Comandos críticos protegidos

### **2. Canal de Stats**
- `@stats_channel_only()` restringe comandos
- Evita spam en canales generales

### **3. Filtrado de Spam**
- `is_link_spam()` detecta mensajes spam
- No se trackean mensajes spam

### **4. Validación de Actividades**
- 6 capas de verificación para juegos
- Blacklist configurable
- Previene tracking de falsos

---

## 📈 Escalabilidad

### **Actual:**
- ~8 usuarios activos
- ~2.85MB de datos (con 365 días)
- Performance: Excelente

### **Límites Teóricos:**
- **Usuarios:** ~1000 usuarios (Railway free tier)
- **Datos:** ~350MB (1000 usuarios × 365 días)
- **Performance:** JSON parsing ~100ms para 350MB

### **Optimizaciones Futuras:**
- Migrar a SQLite si > 500 usuarios
- Paginación en comandos de ranking
- Caché de cálculos frecuentes

---

## 🧪 Testing

### **Cobertura:**
- 65 tests totales
- Tests unitarios para funciones core
- Tests de integración para workflows
- Tests de estructura de datos

### **Categorías:**
- FormatTime (3 tests)
- BarChart (5 tests)
- TimelineChart (3 tests)
- ComparisonChart (3 tests)
- PeriodFiltering (4 tests)
- DailyActivity (2 tests)
- VoiceTimeTracking (7 tests)
- VoiceFiltering (3 tests)
- VoiceRanking (3 tests)
- LinkFiltering (4 tests)
- MessageTracking (4 tests)
- NewTracking (4 tests)
- CommandCoverage (5 tests)
- CommandProcessing (2 tests)
- ConnectionTracking (7 tests)
- VoiceMessageTracking (2 tests)

---

## 🎯 Puntos Clave de la Arquitectura

### **Fortalezas:**
1. ✅ **Modularidad:** Separación clara de responsabilidades
2. ✅ **Escalabilidad:** Fácil agregar nuevos comandos/features
3. ✅ **Mantenibilidad:** Código organizado y documentado
4. ✅ **Performance:** Tasks en background, no bloquea
5. ✅ **Robustez:** Manejo de errores en todos los niveles
6. ✅ **Testeable:** Funciones puras, fácil de testear

### **Áreas de Mejora Potencial:**
1. 🔄 Migrar a base de datos si crece mucho (>500 usuarios)
2. 🔄 Implementar caché para cálculos frecuentes
3. 🔄 Agregar más tests de integración
4. 🔄 Documentación de API más detallada

---

## 📚 Resumen Ejecutivo

**Arquitectura:** Modular con Cogs (discord.py)
**Persistencia:** JSON (Railway Volume)
**Patrones:** Singleton, Factory, Strategy, Decorator, Observer, Facade, State
**Algoritmos:** O(1) para lookups, O(n log n) para rankings
**Performance:** Excelente para escala actual
**Escalabilidad:** Buena hasta ~500 usuarios

---

**Última actualización:** 2025-12-28
**Versión:** 2.0 (Sistema de sesiones de voz refactorizado)

