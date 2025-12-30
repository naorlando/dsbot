# 🔄 Buffer de Gracia Unificado

## 📋 **Resumen**

Unificación del buffer de gracia de **15 minutos** para **todas las sesiones** (Voice, Games, Parties).

---

## 🎯 **¿Qué es el Buffer de Gracia?**

Un **período de tolerancia de 15 minutos** que previene el cierre prematuro de sesiones cuando:
- Discord deja de reportar actividad temporalmente (lag/inconsistencias)
- El usuario está en un lobby de juego (ej. LoL, Valorant)
- Hay una desconexión breve de voz

### **Comportamiento:**

```
Usuario activo → Discord deja de reportar → Buffer 15 min → ¿Sigue activo?
                                                │
                                                ├─ SÍ → Sesión continúa ✅
                                                └─ NO → Sesión se cierra ❌
```

---

## 🏗️ **Arquitectura: DRY (Don't Repeat Yourself)**

### **Antes (Código Duplicado):**
```python
# En GameSessionManager
time_since_last = (datetime.now() - session.last_activity_update).total_seconds()
if time_since_last < 300:  # 5 min (valor viejo)
    return

# En VoiceSessionManager (sin buffer)
# En PartySessionManager (sin buffer)
```

### **Después (Código Unificado):**
```python
# En BaseSessionManager (1 sola vez)
def _is_in_grace_period(self, session: BaseSession) -> bool:
    time_since_last = (datetime.now() - session.last_activity_update).total_seconds()
    return time_since_last < self.grace_period_seconds

# En VoiceSessionManager, GameSessionManager, PartySessionManager
if self._is_in_grace_period(session):
    return  # No cerrar sesión
```

---

## 🔧 **Cambios Implementados**

### **1. BaseSessionManager:**

#### **Constructor:**
```python
def __init__(self, bot, min_duration_seconds: int = 10, grace_period_seconds: int = 900):
    self.grace_period_seconds = grace_period_seconds  # 15 minutos
```

#### **Métodos Nuevos:**
```python
def _update_activity(self, session: BaseSession):
    """Actualiza timestamp de última actividad"""
    session.last_activity_update = datetime.now()

def _is_in_grace_period(self, session: BaseSession) -> bool:
    """Verifica si está dentro del período de gracia"""
    time_since_last = (datetime.now() - session.last_activity_update).total_seconds()
    return time_since_last < self.grace_period_seconds
```

---

### **2. VoiceSessionManager:**

#### **handle_end:**
```python
# Buffer de gracia: Verificar si realmente salió o es desconexión temporal
if self._is_in_grace_period(session):
    logger.info(f'⏳ Sesión de voz en gracia: {member.display_name} - {channel.name}')
    return
```

#### **_is_still_active:**
```python
is_active = member_now.voice.channel.id == session.channel_id

# Si está activo, actualizar timestamp
if is_active:
    self._update_activity(session)

return is_active
```

---

### **3. GameSessionManager:**

#### **handle_start (ya existía):**
```python
# Si ya hay sesión activa, actualizar actividad
if user_id in self.active_sessions:
    self._update_activity(self.active_sessions[user_id])  # ← REFACTORIZADO
    return
```

#### **handle_end:**
```python
# Buffer de gracia
if self._is_in_grace_period(session):  # ← SIMPLIFICADO
    logger.info(f'⏳ Sesión de juego en gracia: {member.display_name} - {game_name}')
    return
```

#### **_is_still_active:**
```python
is_active = current_type == session.activity_type

# Si está activo, actualizar timestamp
if is_active:
    self._update_activity(session)

return is_active
```

---

### **4. PartySessionManager:**

#### **handle_end:**
```python
# Buffer de gracia: Verificar si realmente terminó o es pausa temporal (lobby)
if self._is_in_grace_period(session):
    logger.info(f'⏳ Party en gracia: {game_name}')
    return
```

#### **_is_still_active:**
```python
is_active = current_count >= 2

# Si está activo, actualizar timestamp
if is_active:
    self._update_activity(session)

return is_active
```

---

## ✅ **Tests (5/5 Pasando)**

```
test_buffer_simple.py::TestBufferGraciLogic::test_actualizar_actividad PASSED
test_buffer_simple.py::TestBufferGraciLogic::test_escenario_lobby_lol PASSED
test_buffer_simple.py::TestBufferGraciLogic::test_session_inicializa_con_timestamp PASSED
test_buffer_simple.py::TestBufferGraciLogic::test_verificar_gracia_dentro_del_limite PASSED
test_buffer_simple.py::TestBufferGraciLogic::test_verificar_gracia_fuera_del_limite PASSED
```

### **Escenarios Cubiertos:**
- ✅ Sesión inicializa con timestamp actual
- ✅ Actualizar actividad modifica timestamp
- ✅ Verificar gracia dentro del límite (< 5 min)
- ✅ Verificar gracia fuera del límite (> 5 min)
- ✅ Escenario real: Lobby de LoL (3 min) no cierra sesión

---

## 📊 **Beneficios**

| Aspecto | Antes | Después |
|---------|-------|---------|
| **Código** | 3 implementaciones separadas | 1 implementación compartida |
| **Mantenimiento** | Cambiar en 3 lugares | Cambiar en 1 lugar |
| **Consistencia** | Buffer solo en Games | Buffer en Voice, Games, Parties |
| **Testeo** | Tests parciales | Tests unificados |
| **Spam** | Parties spamean en lobbies | Todas las sesiones toleran pausas |

---

## 🎮 **Casos de Uso Reales**

### **1. League of Legends - Lobby (3 min):**
```
14:00 → Jugando partida (15 min)
14:15 → Lobby (3 min, Discord no reporta)
14:18 → Nueva partida

CON BUFFER: Sesión continúa ✅
SIN BUFFER: Sesión se cierra y notifica spam ❌
```

### **2. Voice Channel - Desconexión Temporal (1 min):**
```
15:00 → En voz (30 min)
15:30 → Lag internet (1 min, Discord no reporta)
15:31 → Reconecta

CON BUFFER: Sesión continúa ✅
SIN BUFFER: Sesión se cierra y notifica salida ❌
```

### **3. Party de Valorant - Búsqueda de Partida (2 min):**
```
20:00 → Jugando partida (20 min)
20:20 → Buscando partida (2 min, Discord no reporta)
20:22 → Nueva partida

CON BUFFER: Party continúa ✅
SIN BUFFER: Party se cierra y notifica spam ❌
```

---

## 🔄 **Flujo de Actualización de Actividad**

```
on_presence_update → _is_still_active → _update_activity(session)
                                               ↓
                         session.last_activity_update = NOW
                                               ↓
                         handle_end → _is_in_grace_period
                                               ↓
                         (NOW - last_activity) < 15 min?
                                     ↓              ↓
                                   SÍ             NO
                                   ↓              ↓
                             return         Cerrar sesión
```

---

## 📝 **Próximos Pasos**

✅ **Completado:**
- Unificación de buffer en `BaseSessionManager`
- Refactor de `VoiceSessionManager`
- Refactor de `GameSessionManager`
- Refactor de `PartySessionManager`
- Tests de lógica de buffer
- Documentación

🎯 **Producción:**
- Deploy y monitoreo de logs
- Validar reducción de spam en lobbies
- Verificar continuidad de sesiones con lag

---

## 🎉 **Estado Final**

✅ **Código unificado**
✅ **Tests pasando (5/5)**
✅ **DRY principle aplicado**
✅ **Sin duplicación de lógica**
✅ **Consistencia en todas las sesiones**
✅ **Preparado para deploy**

