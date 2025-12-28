# 🔍 Análisis de Cooldowns y Arquitectura de Sesiones

## Problemas Identificados

### 1. ❌ Salida de Voz - Sin Cooldown
**Ubicación:** `core/voice_session.py:118-125`

```python
# PROBLEMA: No hay check_cooldown aquí
if config.get('notify_voice_leave', False):
    await send_notification(message, self.bot)
```

**Impacto:** Usuario puede entrar/salir 10 veces y spamear 10 notificaciones de salida.

**Solución:** Agregar `check_cooldown(user_id, 'voice_leave', cooldown_seconds=300)`

---

### 2. ❌ Cambio de Canal - Sin Cooldown
**Ubicación:** `core/voice_session.py:133-149`

```python
async def handle_voice_move(...):
    await self.handle_voice_leave(member, before, config)  # Sin cooldown
    await self.handle_voice_join(member, after, config)   # Con cooldown
```

**Impacto:** Cambios rápidos de canal pueden spamear notificaciones.

**Solución:** Agregar `check_cooldown(user_id, 'voice_move', cooldown_seconds=300)` antes de notificar.

---

### 3. ⚠️ Juegos - Sin Sistema de Sesiones Robusto
**Estado Actual:**
- ✅ Entrada: Tiene cooldown (`check_cooldown(user_id, f'game:{game_name}')`)
- ❌ Salida: No notifica, solo guarda tiempo
- ❌ Sin verificación de duración mínima (como voz tiene 10s)
- ❌ Sin sistema de sesiones con verificación en background

**Comparación:**

| Feature | Voz | Juegos |
|---------|-----|--------|
| Cooldown entrada | ✅ | ✅ |
| Cooldown salida | ❌ | N/A (no notifica) |
| Verificación 3s+7s | ✅ | ❌ |
| Borrar notificación si sale rápido | ✅ | N/A |
| SessionManager dedicado | ✅ | ❌ |

---

### 4. 🏗️ Arquitectura - Duplicación de Responsabilidades

**Estado Actual:**

```
tracking.py:
  - start_game_session()     → Guarda datos + lógica básica
  - end_game_session()        → Calcula tiempo + guarda
  - start_voice_session()     → Guarda datos
  - end_voice_session()       → Calcula tiempo + guarda
  - record_*_event()          → Incrementa contadores

voice_session.py:
  - VoiceSessionManager        → Lógica de negocio completa
    - Verificación 3s+7s
    - Notificaciones
    - Cooldowns
    - Borrado de mensajes
```

**Problema:** `tracking.py` mezcla persistencia con lógica de negocio.

---

## Propuesta de Solución

### Opción A: Quick Fix (Solo Cooldowns)
✅ Agregar cooldowns faltantes
- `voice_leave`: 5 min
- `voice_move`: 5 min

**Pros:** Rápido, resuelve spam inmediato
**Contras:** No resuelve arquitectura, juegos siguen sin verificación

---

### Opción B: Refactor Completo (Recomendado)

#### 1. Crear `BaseSessionManager` (Template Genérico)

```python
# core/base_session.py
class BaseSession:
    """Template para cualquier tipo de sesión"""
    user_id: str
    username: str
    start_time: datetime
    notification_message: Optional[Message]
    verification_task: Optional[Task]
    is_confirmed: bool

class BaseSessionManager:
    """Template para gestionar sesiones de cualquier tipo"""
    async def handle_start(...):  # Template method
    async def handle_end(...):     # Template method
    async def _verify_session(...): # Template method
```

#### 2. Refactorizar a Clases Específicas

```python
# core/voice_session.py
class VoiceSession(BaseSession):
    channel_id: int
    channel_name: str

class VoiceSessionManager(BaseSessionManager):
    # Implementa métodos específicos de voz
```

```python
# core/game_session.py (NUEVO)
class GameSession(BaseSession):
    game_name: str
    app_id: Optional[int]

class GameSessionManager(BaseSessionManager):
    # Implementa métodos específicos de juegos
    # - Verificación 3s+7s
    # - Notificación de salida opcional
    # - Cooldown en salida
```

#### 3. Refactorizar `tracking.py`

**Nuevo propósito:** Solo persistencia de datos

```python
# tracking.py - SOLO guarda datos
def save_game_time(user_id, game_name, minutes):
    """Solo guarda tiempo, sin lógica de negocio"""
    
def save_voice_time(user_id, minutes):
    """Solo guarda tiempo, sin lógica de negocio"""
    
def increment_counter(user_id, event_type):
    """Solo incrementa contadores"""
```

**Lógica de negocio → SessionManagers**

---

### Opción C: Híbrida (Pragmática)

1. ✅ Agregar cooldowns faltantes (Quick Fix)
2. ✅ Crear `GameSessionManager` similar a `VoiceSessionManager`
3. ⏸️ Dejar `tracking.py` como está (refactor después)

**Pros:** Resuelve problemas inmediatos + mejora juegos
**Contras:** Mantiene duplicación temporalmente

---

## Recomendación

**Opción C (Híbrida)** porque:
1. Resuelve spam inmediato (cooldowns)
2. Mejora experiencia de juegos (verificación)
3. No requiere refactor masivo ahora
4. Podemos refactorizar a template después

---

## Plan de Implementación (Opción C)

### Fase 1: Cooldowns (15 min)
- [ ] Agregar cooldown a `handle_voice_leave`
- [ ] Agregar cooldown a `handle_voice_move`
- [ ] Testear spam prevention

### Fase 2: GameSessionManager (1-2 horas)
- [ ] Crear `core/game_session.py`
- [ ] Implementar `GameSession` y `GameSessionManager`
- [ ] Mover lógica de `on_presence_update` a `GameSessionManager`
- [ ] Agregar verificación 3s+7s para juegos
- [ ] Agregar notificación opcional de salida de juego
- [ ] Testear

### Fase 3: Refactor tracking.py (Futuro)
- [ ] Separar persistencia de lógica de negocio
- [ ] Crear `BaseSessionManager` template
- [ ] Migrar `VoiceSessionManager` y `GameSessionManager` a template

---

## Preguntas para Decidir

1. ¿Queremos notificaciones de "dejó de jugar X"?
2. ¿Queremos verificación 3s+7s para juegos? (evitar spam de juegos rápidos)
3. ¿Refactor completo ahora o híbrido?

