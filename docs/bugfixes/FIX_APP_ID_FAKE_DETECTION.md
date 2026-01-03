# 🛡️ Fix: Detección y Bloqueo de App IDs Fake

**Fecha:** 03 de enero de 2026  
**Problema:** Usuarios pueden usar app_ids fake para infiltrarse en parties y generar notificaciones falsas  
**Solución:** Sistema multi-capa de detección de outliers y tracking automático

---

## 🚨 **PROBLEMA IDENTIFICADO**

### **Caso Real:**

```
00:49:09 → agu + Pino juegan LoL (app_id: 401518684763586560) ✅ Real
00:49:12 → Notifica PARTY de LoL
00:49:12 → Notifica GAME de Pino ❌ Redundante
00:49:35 → Zeta juega LoL (app_id: 1402418696126992445) ❌ Fake
00:49:35 → Notifica "Zeta se unió a la party" ❌
00:49:38 → Notifica GAME de Zeta ❌
```

**Problemas:**
1. **App IDs fake:** Discord permite actividades custom con mismo nombre pero diferente app_id
2. **Spam de notificaciones:** Party + Games individuales (redundante)
3. **Infiltración en parties:** Fake puede entrar a party real

---

## ✅ **SOLUCIÓN IMPLEMENTADA**

### **1️⃣ Sistema de Tracking de App IDs**

**Archivo:** `core/app_id_tracker.py` (nuevo)

**Funcionalidad:**
- Registra cada app_id por juego con contador de apariciones
- Identifica el app_id "más común" para cada juego
- Detecta app_ids sospechosos (vistos < threshold veces)
- Persistencia en `app_id_tracker.json`

**Métodos principales:**
```python
track_app_id(game_name, app_id) → int  # Retorna count
is_suspicious_app_id(game_name, app_id, threshold=3) → bool
get_most_common_app_id(game_name) → (app_id, count)
```

**Lógica de detección:**
```python
# Primer app_id de un juego → NO sospechoso
if most_common is None:
    return False

# Si es el más común → NO sospechoso (aunque count < threshold)
if app_id == most_common[0]:
    return False

# Si visto < threshold veces → SOSPECHOSO
if count < threshold:
    return True
```

---

### **2️⃣ Outlier Detection en Parties**

**Archivo:** `core/party_session.py`

**Método:** `_filter_players_by_app_id()`

**Estrategia:**
```
┌─────────────────────────────────────────────┐
│ 1. Extraer app_ids de todos los jugadores  │
│ 2. Contar frecuencia de cada app_id        │
│ 3. Si todos tienen mismo app_id → aceptar  │
│ 4. Si hay múltiples:                       │
│    → Usar el MAYORITARIO                   │
│    → Rechazar outliers                     │
└─────────────────────────────────────────────┘
```

**Ejemplo:**
```python
# 2 jugadores con app_id real vs 1 fake
agu:  401518684763586560 ✅
Pino: 401518684763586560 ✅
Zeta: 1402418696126992445 ❌ Rechazado (outlier)

# Resultado: Party con agu + Pino, Zeta queda fuera
```

**Logging:**
```
🔍 Múltiples app_ids detectados para League of Legends:
   - 401518684763586560: 2 jugador(es)
   - 1402418696126992445: 1 jugador(es)
✅ App ID mayoritario: 401518684763586560 (2 jugadores)
🚫 Jugador rechazado (app_id outlier): Zeta - League of Legends
```

---

### **3️⃣ Supresión de Notificaciones de Games**

**Archivo:** `core/game_session.py`

**Modificaciones en `_on_session_confirmed_phase1()`:**

```python
# 1. Trackear app_id
count = track_app_id(session.game_name, session.app_id)

# 2. Verificar si es sospechoso
if is_suspicious_app_id(session.game_name, session.app_id, threshold=3):
    logger.warning(f'⚠️  App ID poco común: {game_name} ({app_id}) - visto {count} veces')
    return  # NO notificar

# 3. Verificar si hay party activa
if self.party_manager.has_active_party(session.game_name):
    logger.debug(f'⏭️  Notificación suprimida: {username} (party activa)')
    return  # NO notificar, pero SÍ trackear tiempo

# 4. Notificar solo si pasó todas las verificaciones
```

**Nuevo método en PartySessionManager:**
```python
def has_active_party(self, game_name: str) -> bool:
    """Retorna True si hay party activa y confirmada para ese juego"""
    if game_name not in self.active_sessions:
        return False
    
    session = self.active_sessions[game_name]
    return session.is_confirmed and session.state == 'active'
```

---

## 📊 **FLUJO CORREGIDO**

### **Antes:**
```
00:49:09 → agu + Pino juegan LoL
00:49:12 → Notifica PARTY ✅
00:49:12 → Notifica GAME de Pino ❌ Redundante
00:49:35 → Zeta (fake) se une a party ❌
00:49:38 → Notifica GAME de Zeta ❌
```

### **Después:**
```
00:49:09 → agu + Pino juegan LoL (app_id: 401518...)
           → Trackea app_id (count: 1)
00:49:12 → Notifica PARTY ✅
00:49:12 → NO notifica GAME de Pino ✅ (party activa)
00:49:35 → Zeta intenta unirse (app_id: 140241...)
           → Rechazado por outlier detection ✅
           → NO se une a party ✅
00:49:38 → Zeta intenta notificar game
           → App ID sospechoso (visto 1 vez vs 2 del real) ✅
           → NO notifica ✅
```

---

## 🧪 **TESTS IMPLEMENTADOS**

### **1. `test_app_id_tracking.py`** (10 tests)
- ✅ Trackeo básico de app_ids
- ✅ Contador incrementa correctamente
- ✅ Múltiples app_ids por juego
- ✅ Detección de app_id más común
- ✅ Primer app_id NO es sospechoso
- ✅ Outlier ES sospechoso
- ✅ Threshold personalizado funciona
- ✅ Estadísticas por juego
- ✅ App_id None es sospechoso

### **2. `test_party_outlier_detection.py`** (7 tests)
- ✅ Todos mismo app_id → aceptar todos
- ✅ 2 vs 1 → rechazar minoritario
- ✅ 3 vs 2 → aceptar mayoritario
- ✅ Jugadores sin actividad rechazados
- ✅ Lista vacía maneja correctamente
- ✅ Empate maneja correctamente
- ✅ Integration: handle_start rechaza si < min_players

### **3. `test_game_party_suppression.py`** (7 tests)
- ✅ has_active_party() funciona
- ✅ Party confirmada detectada
- ✅ Party inactive NO detectada
- ✅ Notificación suprimida con party activa
- ✅ Notificación enviada sin party
- ✅ App_id sospechoso suprime notificación
- ✅ Primer app_id NO es sospechoso

**Total:** 24 tests nuevos, todos pasando ✅

---

## 📁 **ARCHIVOS MODIFICADOS**

### **Nuevos:**
- `core/app_id_tracker.py` - Sistema de tracking
- `test_app_id_tracking.py` - Tests del tracker
- `test_party_outlier_detection.py` - Tests de outliers
- `test_game_party_suppression.py` - Tests de supresión

### **Modificados:**
- `core/party_session.py`
  - Agregado `_filter_players_by_app_id()`
  - Agregado `has_active_party()`
  - Modificado `handle_start()` para filtrar outliers

- `core/game_session.py`
  - Agregado tracking de app_ids
  - Agregado detección de sospechosos
  - Agregado supresión si hay party activa
  - Constructor ahora recibe `party_manager`

- `cogs/events.py`
  - Actualizado orden de inicialización:
    ```python
    self.party_manager = PartySessionManager(bot)
    self.game_manager = GameSessionManager(bot, party_manager=self.party_manager)
    ```

---

## 🎯 **VENTAJAS**

1. **Automático:** No requiere mantenimiento manual de whitelists
2. **Adaptable:** Se "entrena" con el uso real
3. **Ligero:** Solo contador por app_id
4. **Robusto:** Funciona para cualquier juego
5. **No invasivo:** Trackea tiempo normalmente, solo suprime notificaciones

---

## ⚠️ **LIMITACIONES**

1. **Edge case: Fakes first**
   - Si 2 fakes entran antes que el real, el real queda fuera
   - **Probabilidad:** Muy baja (requiere coordinación)
   - **Mitigación:** Después de unos días, el tracker aprende el app_id real

2. **Primer juego sin historial**
   - Primera vez que se juega un juego, no hay historial
   - **Mitigación:** Primer app_id no es sospechoso (beneficio de la duda)

3. **Discord reporta app_id diferente**
   - Raro, pero posible que Discord reporte diferentes app_ids para el mismo juego
   - **Mitigación:** El más común eventualmente domina

---

## 📈 **PRÓXIMOS PASOS**

- [ ] Monitorear logs para casos edge
- [ ] Analizar `app_id_tracker.json` después de 1 semana
- [ ] Considerar whitelist manual para juegos muy populares (opcional)
- [ ] Dashboard para ver app_ids trackeados (futuro)

---

## 🔗 **REFERENCIAS**

- Issue original: Logs del 03/01/2026 00:49
- Tests: 24 tests nuevos, 100% pasando
- Documentos relacionados:
  - `docs/ESTADO_ACTUAL_SESIONES.md`
  - `docs/analisis/ANALISIS_SESIONES_COORDINACION.md`

