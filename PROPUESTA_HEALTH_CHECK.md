# 🏥 Propuesta: Sistema de Health Check para Sesiones

## 🎯 Objetivo

Implementar un evento periódico que valide que todas las sesiones activas en memoria coincidan con la realidad en Discord.

---

## ⏰ Frecuencia Recomendada

**10 minutos** con activación dinámica:
- ✅ Solo se ejecuta cuando HAY sesiones activas
- ✅ Se detiene automáticamente en tiempos muertos (0% overhead)
- ✅ 10 minutos es suficiente (sesiones mínimas son de 10s de todos modos)
- ✅ Balancea precisión vs eficiencia

**Activación dinámica:**
```python
if hay_sesiones_activas():
    health_check_task.start()  # Activar
else:
    health_check_task.cancel()  # Desactivar
```

---

## 🔍 Validaciones a Implementar

### 1️⃣ **Voice Sessions Health Check**

**Validación:**
```python
for session in voice_manager.active_sessions:
    usuario = guild.get_member(session.user_id)
    
    # ¿El usuario sigue en el canal de voz?
    if not usuario or not usuario.voice or usuario.voice.channel.id != session.channel_id:
        # ❌ Sesión huérfana → Finalizar y guardar
        logger.warning(f'🔧 Sesión huérfana detectada: {session.username} en voz')
        await voice_manager.handle_end(usuario, session.channel, config)
```

**Casos que detecta:**
- Bot reinició y perdió sesión
- Discord no envió evento de salida
- Usuario cambió de canal mientras bot estaba offline

---

### 2️⃣ **Game Sessions Health Check**

**Validación:**
```python
for session in game_manager.active_sessions:
    usuario = guild.get_member(session.user_id)
    
    # ¿El usuario sigue jugando ese juego?
    if not usuario or not _is_playing_game(usuario, session.game_name):
        # ❌ Sesión huérfana → Finalizar y guardar
        logger.warning(f'🔧 Sesión huérfana detectada: {session.username} jugando {session.game_name}')
        await game_manager.handle_end(usuario, None, config)
```

**Casos que detecta:**
- Bot reinició mientras usuario jugaba
- Discord no envió evento de `presence_update`
- Usuario cerró juego mientras bot estaba offline

---

### 3️⃣ **Party Sessions Health Check**

**Validación:**
```python
for game_name, session in party_manager.active_sessions.items():
    # ¿Los jugadores siguen jugando ese juego?
    current_players = party_manager.get_active_players_by_game(guild).get(game_name, [])
    
    if len(current_players) < 2:
        # ❌ Party ya no cumple requisitos → Finalizar
        logger.warning(f'🔧 Party huérfana detectada: {game_name}')
        await party_manager.handle_end(game_name, config)
```

**Casos que detecta:**
- Todos los jugadores salieron mientras bot estaba offline
- Solo queda 1 jugador (ya no es party)

---

### 4️⃣ **Recuperación de Sesiones Perdidas (Opcional)**

**Validación inversa:**
```python
# Revisar usuarios en voice channels SIN sesión activa
for voice_channel in guild.voice_channels:
    for member in voice_channel.members:
        if member.id not in voice_manager.active_sessions:
            # ⚠️ Usuario en voz SIN sesión → Crear sesión
            logger.info(f'🔧 Recuperando sesión perdida: {member.display_name} en {voice_channel.name}')
            await voice_manager.handle_start(member, voice_channel, config)

# Similar para games...
```

**Casos que detecta:**
- Bot reinició y usuario ya estaba en voz/jugando
- Recuperación proactiva de sesiones

---

## 🔧 Implementación Técnica

### ¿Es un hilo o un cron?

**Es un "task loop" de discord.py:**
- Similar a un cron job pero asíncrono
- NO es un hilo del sistema operativo
- Corre en el event loop de asyncio (sin bloqueo)
- Se puede iniciar/detener dinámicamente

**Ventajas:**
- ✅ No bloqueante (no afecta otros eventos)
- ✅ Bajo overhead (solo se ejecuta cuando es necesario)
- ✅ Integrado con el lifecycle del bot

---

## 💾 Persistencia de Sesiones Activas

### Por qué persistir?

**Problema:**
```
1. Usuario entra a voz → VoiceSession en memoria
2. Bot se reinicia (deploy) → Sesión perdida 💥
3. Bot arranca → No sabe que el usuario está en voz
4. Health check encuentra al usuario → Crea nueva sesión
5. Pero el start_time es incorrecto (recién reinició)
```

**Solución: Persistir sesiones activas**

### Ubicación

Archivo nuevo: `active_sessions.json` (en `/data/`)

```json
{
  "voice_sessions": {
    "123456789": {
      "username": "Pino",
      "channel_id": 987654321,
      "channel_name": "General",
      "start_time": "2025-12-29T22:30:00",
      "is_confirmed": true
    }
  },
  "game_sessions": {
    "123456789": {
      "username": "Pino",
      "game_name": "VALORANT",
      "app_id": 700136079562375258,
      "activity_type": "playing",
      "start_time": "2025-12-29T22:35:00",
      "is_confirmed": true
    }
  },
  "party_sessions": {
    "VALORANT": {
      "player_ids": ["123", "456", "789"],
      "player_names": ["Pino", "agu", "Zeta"],
      "start_time": "2025-12-29T22:35:00",
      "max_players": 3,
      "is_confirmed": true
    }
  }
}
```

### Cuándo Guardar?

**1. Al confirmar sesión (después de 10s):**
```python
async def _on_session_confirmed_phase2(self, session, member, config):
    # ... lógica existente ...
    
    # NUEVO: Persistir sesión confirmada
    self._persist_active_session(session)
```

**2. Al actualizar sesión (cambios importantes):**
```python
# Ej: Usuario cambia de canal de voz
session.channel_id = new_channel.id
self._persist_active_session(session)
```

**3. Al finalizar sesión:**
```python
await self.handle_end(member, channel, config):
    # ... guardar tiempo ...
    
    # NUEVO: Eliminar de sesiones activas
    self._remove_persisted_session(session)
```

---

## 📝 Implementación Completa

### Ubicación

Crear nuevo archivo: `core/health_check.py`

```python
from discord.ext import tasks
import logging
import json
import os
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger('dsbot')

# Archivo de persistencia
ACTIVE_SESSIONS_FILE = os.path.join(os.getenv('DATA_DIR', '.'), 'active_sessions.json')


class SessionHealthCheck:
    """
    Sistema de validación periódica de sesiones
    
    - Validación cada 10 minutos
    - Solo activo cuando hay sesiones
    - Persistencia en disco para sobrevivir reinicios
    """
    
    def __init__(self, bot, voice_manager, game_manager, party_manager):
        self.bot = bot
        self.voice_manager = voice_manager
        self.game_manager = game_manager
        self.party_manager = party_manager
        self._task_running = False
        
        # Restaurar sesiones al iniciar
        self._restore_sessions_on_startup()
    
    def _restore_sessions_on_startup(self):
        """Restaura sesiones persistidas después de reinicio"""
        if not os.path.exists(ACTIVE_SESSIONS_FILE):
            logger.info('🔄 No hay sesiones previas para restaurar')
            return
        
        try:
            with open(ACTIVE_SESSIONS_FILE, 'r', encoding='utf-8') as f:
                persisted = json.load(f)
            
            # Restaurar VoiceSessions
            for user_id, data in persisted.get('voice_sessions', {}).items():
                from core.voice_session import VoiceSession
                session = VoiceSession(
                    user_id=user_id,
                    username=data['username'],
                    channel_id=data['channel_id'],
                    channel_name=data['channel_name'],
                    guild_id=data.get('guild_id', 0)
                )
                session.start_time = datetime.fromisoformat(data['start_time'])
                session.is_confirmed = data.get('is_confirmed', False)
                self.voice_manager.active_sessions[user_id] = session
                logger.info(f'🔄 Sesión de voz restaurada: {data["username"]} en {data["channel_name"]}')
            
            # Restaurar GameSessions
            for user_id, data in persisted.get('game_sessions', {}).items():
                from core.game_session import GameSession
                session = GameSession(
                    user_id=user_id,
                    username=data['username'],
                    game_name=data['game_name'],
                    app_id=data.get('app_id'),
                    activity_type=data['activity_type'],
                    guild_id=data.get('guild_id', 0)
                )
                session.start_time = datetime.fromisoformat(data['start_time'])
                session.is_confirmed = data.get('is_confirmed', False)
                self.game_manager.active_sessions[user_id] = session
                logger.info(f'🔄 Sesión de juego restaurada: {data["username"]} jugando {data["game_name"]}')
            
            # Restaurar PartySessions
            for game_name, data in persisted.get('party_sessions', {}).items():
                from core.party_session import PartySession
                session = PartySession(
                    game_name=game_name,
                    player_ids=set(data['player_ids']),
                    player_names=data['player_names'],
                    guild_id=data.get('guild_id', 0)
                )
                session.start_time = datetime.fromisoformat(data['start_time'])
                session.is_confirmed = data.get('is_confirmed', False)
                session.max_players = data.get('max_players', len(data['player_ids']))
                self.party_manager.active_sessions[game_name] = session
                logger.info(f'🔄 Sesión de party restaurada: {game_name} con {len(data["player_ids"])} jugadores')
            
            logger.info(f'✅ {len(persisted.get("voice_sessions", {}))} voice, '
                       f'{len(persisted.get("game_sessions", {}))} games, '
                       f'{len(persisted.get("party_sessions", {}))} parties restauradas')
        
        except Exception as e:
            logger.error(f'❌ Error al restaurar sesiones: {e}')
    
    def persist_all_sessions(self):
        """Guarda todas las sesiones activas en disco"""
        data = {
            'voice_sessions': {},
            'game_sessions': {},
            'party_sessions': {},
            'last_updated': datetime.now().isoformat()
        }
        
        # Persistir VoiceSessions
        for user_id, session in self.voice_manager.active_sessions.items():
            if session.is_confirmed:  # Solo persistir sesiones confirmadas
                data['voice_sessions'][user_id] = {
                    'username': session.username,
                    'channel_id': session.channel_id,
                    'channel_name': session.channel_name,
                    'guild_id': session.guild_id,
                    'start_time': session.start_time.isoformat(),
                    'is_confirmed': session.is_confirmed
                }
        
        # Persistir GameSessions
        for user_id, session in self.game_manager.active_sessions.items():
            if session.is_confirmed:
                data['game_sessions'][user_id] = {
                    'username': session.username,
                    'game_name': session.game_name,
                    'app_id': session.app_id,
                    'activity_type': session.activity_type,
                    'guild_id': session.guild_id,
                    'start_time': session.start_time.isoformat(),
                    'is_confirmed': session.is_confirmed
                }
        
        # Persistir PartySessions
        for game_name, session in self.party_manager.active_sessions.items():
            if session.is_confirmed:
                data['party_sessions'][game_name] = {
                    'player_ids': list(session.player_ids),
                    'player_names': session.player_names,
                    'guild_id': session.guild_id,
                    'start_time': session.start_time.isoformat(),
                    'max_players': session.max_players,
                    'is_confirmed': session.is_confirmed
                }
        
        # Guardar a disco
        try:
            with open(ACTIVE_SESSIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            total = len(data['voice_sessions']) + len(data['game_sessions']) + len(data['party_sessions'])
            if total > 0:
                logger.debug(f'💾 {total} sesiones persistidas')
        except Exception as e:
            logger.error(f'❌ Error al persistir sesiones: {e}')
    
    def _has_active_sessions(self) -> bool:
        """Verifica si hay sesiones activas"""
        return (
            len(self.voice_manager.active_sessions) > 0 or
            len(self.game_manager.active_sessions) > 0 or
            len(self.party_manager.active_sessions) > 0
        )
    
    def start_if_needed(self):
        """Inicia el health check solo si hay sesiones activas"""
        if self._has_active_sessions() and not self._task_running:
            self.health_check_task.start()
            self._task_running = True
            logger.info('🏥 Health check activado (hay sesiones activas)')
    
    def stop_if_empty(self):
        """Detiene el health check si no hay sesiones activas"""
        if not self._has_active_sessions() and self._task_running:
            self.health_check_task.cancel()
            self._task_running = False
            logger.info('🏥 Health check desactivado (no hay sesiones activas)')
    
    @tasks.loop(minutes=10)
    async def health_check_task(self):
        """Ejecuta validación cada 10 minutos"""
        try:
            logger.info('🏥 Iniciando health check de sesiones...')
            
            fixed_voice = await self._check_voice_sessions()
            fixed_games = await self._check_game_sessions()
            fixed_parties = await self._check_party_sessions()
            
            # Persistir estado actual
            self.persist_all_sessions()
            
            if fixed_voice + fixed_games + fixed_parties > 0:
                logger.warning(f'🔧 Health check completado: {fixed_voice} voice, {fixed_games} games, {fixed_parties} parties arregladas')
            else:
                logger.info('✅ Health check completado: Todo OK')
            
            # Detener si no quedan sesiones
            self.stop_if_empty()
                
        except Exception as e:
            logger.error(f'❌ Error en health check: {e}')
    
    @health_check_task.before_loop
    async def before_health_check(self):
        """Espera a que el bot esté listo antes de iniciar"""
        await self.bot.wait_until_ready()
    
    async def _check_voice_sessions(self) -> int:
        """Valida sesiones de voz. Retorna cantidad de sesiones arregladas."""
        fixed = 0
        # TODO: Implementación
        return fixed
    
    async def _check_game_sessions(self) -> int:
        """Valida sesiones de juegos. Retorna cantidad de sesiones arregladas."""
        fixed = 0
        # TODO: Implementación
        return fixed
    
    async def _check_party_sessions(self) -> int:
        """Valida sesiones de parties. Retorna cantidad de sesiones arregladas."""
        fixed = 0
        # TODO: Implementación
        return fixed
```

### Integración en `cogs/events.py`

```python
from core.health_check import SessionHealthCheck

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_manager = VoiceSessionManager(bot)
        self.game_manager = GameSessionManager(bot)
        self.party_manager = PartySessionManager(bot)
        
        # NUEVO: Inicializar health check
        self.health_check = SessionHealthCheck(
            bot=bot,
            voice_manager=self.voice_manager,
            game_manager=self.game_manager,
            party_manager=self.party_manager
        )
    
    async def on_voice_state_update(self, member, before, after):
        # ... lógica existente ...
        
        # NUEVO: Activar health check si se creó una sesión
        if after.channel and before.channel is None:
            self.health_check.start_if_needed()
        
        # NUEVO: Persistir sesiones al finalizar
        if after.channel is None and before.channel:
            self.health_check.persist_all_sessions()
    
    async def on_presence_update(self, before, after):
        # ... lógica existente ...
        
        # NUEVO: Activar health check si se detectó un juego
        self.health_check.start_if_needed()
        
        # NUEVO: Persistir sesiones
        self.health_check.persist_all_sessions()
```

### Llamadas a `persist_all_sessions()`

**Cuándo persistir:**
1. Después de confirmar una sesión (fase 2)
2. Al finalizar una sesión (handle_end)
3. Durante el health check
4. Al detectar cambios importantes (cambio de canal, nuevo jugador en party)

**Dónde agregar:**
```python
# En BaseSessionManager._on_session_confirmed_phase2()
self.health_check.persist_all_sessions()

# En cada manager.handle_end()
self.health_check.persist_all_sessions()
```

---

## 📊 Logs de Health Check

**Formato de logs:**

**Sin problemas:**
```
2025-12-29 23:00:00 - dsbot - INFO - 🏥 Iniciando health check de sesiones...
2025-12-29 23:00:01 - dsbot - INFO - ✅ Health check completado: Todo OK
```

**Con problemas detectados:**
```
2025-12-29 23:00:00 - dsbot - INFO - 🏥 Iniciando health check de sesiones...
2025-12-29 23:00:01 - dsbot - WARNING - 🔧 Sesión huérfana detectada: Pino en voz
2025-12-29 23:00:01 - dsbot - INFO - 💾 Tiempo guardado: Pino estuvo en 👥 General por 45 min
2025-12-29 23:00:02 - dsbot - WARNING - 🔧 Party huérfana detectada: VALORANT
2025-12-29 23:00:02 - dsbot - WARNING - 🔧 Health check completado: 1 voice, 0 games, 1 parties arregladas
```

---

## 🎯 Beneficios

1. ✅ **Resiliencia:** Bot se auto-repara después de reinicios
2. ✅ **Precisión:** Stats más precisos (no se pierden sesiones)
3. ✅ **Debugging:** Logs claros de inconsistencias
4. ✅ **Confianza:** Sistema se auto-monitorea
5. ✅ **Sin intervención manual:** Todo automático

---

## ⚠️ Consideraciones

1. **Performance:** Iteración sobre todos los miembros del guild cada 5 min
   - Con <1000 miembros: negligible
   - Con >1000 miembros: considerar optimizaciones

2. **Race conditions:** El health check podría coincidir con un evento real
   - Solución: Usar locks si es necesario

3. **Notificaciones:** NO enviar notificaciones durante health check
   - Las sesiones recuperadas son "silenciosas"
   - Solo trackear tiempo, no notificar

4. **Cooldowns:** Respetar cooldowns existentes durante health check
   - No resetear cooldowns al finalizar sesiones huérfanas

---

## 🔄 Flujo Completo

```
┌─────────────────────────────────────────────────────────────┐
│ INICIO DEL BOT                                              │
├─────────────────────────────────────────────────────────────┤
│ 1. Bot arranca                                              │
│ 2. SessionHealthCheck.__init__()                            │
│ 3. _restore_sessions_on_startup()                           │
│    ├─ Lee active_sessions.json                              │
│    └─ Restaura VoiceSessions, GameSessions, PartySessions   │
│                                                             │
│ 4. Health check task queda en standby (NO se inicia)       │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ USUARIO ENTRA A VOZ / JUEGA                                 │
├─────────────────────────────────────────────────────────────┤
│ 1. on_voice_state_update() o on_presence_update()          │
│ 2. handle_start() → Crea sesión                            │
│ 3. health_check.start_if_needed()                           │
│    └─ Si es la primera sesión → health_check_task.start()  │
│                                                             │
│ Health check ACTIVO (corre cada 10 min)                    │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ CADA 10 MINUTOS (mientras hay sesiones)                    │
├─────────────────────────────────────────────────────────────┤
│ 1. health_check_task() se ejecuta                          │
│ 2. Valida todas las sesiones activas                       │
│ 3. Corrige inconsistencias (sesiones huérfanas)            │
│ 4. persist_all_sessions() → Guarda a active_sessions.json  │
│ 5. stop_if_empty() → Si no hay sesiones, se detiene        │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ TODAS LAS SESIONES TERMINAN                                 │
├─────────────────────────────────────────────────────────────┤
│ 1. Última sesión termina                                   │
│ 2. persist_all_sessions() → active_sessions.json vacío     │
│ 3. stop_if_empty() → health_check_task.cancel()            │
│                                                             │
│ Health check INACTIVO (0% CPU hasta próxima sesión)        │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Persistencia: active_sessions.json

### Cuándo se actualiza?

**1. Al confirmar sesión (10s después de iniciar):**
```
Usuario entra a voz → 3s → 7s → Sesión confirmada → persist_all_sessions()
```

**2. Durante health check (cada 10 min):**
```
Health check valida sesiones → persist_all_sessions()
```

**3. Al finalizar sesión:**
```
Usuario sale → handle_end() → persist_all_sessions()
```

**4. Cambios importantes:**
```
Usuario cambia de canal → persist_all_sessions()
Jugador se une a party → persist_all_sessions()
```

### Por qué cada 10 minutos es suficiente?

- ✅ Sesiones mínimas son de 10 segundos
- ✅ Si bot reinicia y perdió <10 min, no es crítico
- ✅ El health check recupera sesiones válidas
- ✅ Balance perfecto entre precisión y overhead

---

## 🎯 Ventajas del Sistema Completo

### 1️⃣ **Carga Dinámica**
```
Sin sesiones:      0% CPU (health check desactivado)
Con sesiones:      <0.1% CPU (check cada 10 min)
Muchos usuarios:   Mismo overhead (solo itera sesiones, no todos los miembros)
```

### 2️⃣ **Resiliencia Total**
```
Bot reinicia mientras Pino está en voz:
├─ Bot lee active_sessions.json
├─ Restaura VoiceSession con start_time original
├─ Pino sale → Guarda tiempo correcto ✅
└─ Sin pérdida de datos
```

### 3️⃣ **Auto-reparación**
```
Discord falla y no envía evento:
├─ Health check detecta inconsistencia
├─ Finaliza sesión huérfana
├─ Guarda tiempo parcial ✅
└─ Sistema se auto-repara
```

### 4️⃣ **Sin Intervención Manual**
```
Todo es automático:
├─ Se activa cuando hay usuarios
├─ Se desactiva cuando no hay nadie
├─ Persiste sesiones en disco
├─ Restaura después de reinicios
└─ Usuario no nota nada
```

---

## 📈 Próximos Pasos

1. ✅ Implementar `SessionHealthCheck` en `core/health_check.py`
2. ✅ Agregar métodos de persistencia (_restore, persist_all)
3. ✅ Implementar validaciones (_check_voice, _check_games, _check_parties)
4. ✅ Integrar start_if_needed() en eventos
5. ✅ Testear con reinicio del bot
6. ✅ Monitorear logs en Railway

---

## 🤔 Preguntas para el Usuario

1. **¿Implementar recuperación proactiva de sesiones perdidas?**
   - PRO: No se pierde tracking después de reinicios
   - CONTRA: Puede crear sesiones "sin inicio" (sin notificación)

2. **¿Incluir Spotify en el tracking?**
   - PRO: Analytics de música, wrapped musical
   - CONTRA: Puede generar mucho ruido

3. **¿Separar Streaming de GameSession?**
   - PRO: Stats específicos de streamers
   - CONTRA: Más complejidad

4. **¿Frecuencia del health check?**
   - Opción A: 5 minutos (recomendado)
   - Opción B: 10 minutos (más ligero)
   - Opción C: 3 minutos (más agresivo)

