# 🔍 Análisis Completo: Casos de Recovery de Sesiones

## 📋 **CASOS A ANALIZAR:**

### **Caso 1: Usuario jugando cuando bot reinicia (continúa)**
```
17:00 → Empieza Kingdom Come
        → current_session = {start: "17:00"}
        → active_sessions[Wire] = sesión

20:00 → DEPLOY
        → active_sessions = {} (memoria limpia)
        
20:00 → Recovery AGRESIVO:
        → Lee: current_session = {start: "17:00"}
        → Recrea: session.start_time = "17:00" ✅
        → active_sessions[Wire] = sesión restaurada

20:05 → Discord reporta: Wire jugando Kingdom Come
        → on_presence_update detecta actividad
        → handle_game_start() ve: active_sessions[Wire] ya existe
        → Actualiza: last_activity_update ✅
        → NO crea nueva sesión ✅

23:00 → Wire termina (6h total)
        → Guarda: 6h correctas ✅
```

**Resultado:** ✅ PERFECTO

---

### **Caso 2: Usuario terminó de jugar ANTES del reinicio**
```
17:00 → Juega LoL (1h)
18:00 → Termina de jugar
        → current_session = null (debería, pero...)

18:01 → Discord reporta que NO juega más
        → handle_game_end() se llama
        → Guarda tiempo y limpia ✅
        
20:00 → DEPLOY
        → Recovery: current_session = null
        → NO intenta recuperar ✅
```

**Resultado:** ✅ PERFECTO

---

### **Caso 3: Usuario terminó pero current_session quedó colgada**
```
17:00 → Juega LoL
18:00 → Termina
        → Discord dejó de reportar
        → handle_game_end() entra en grace
        → NO limpia current_session ❌

20:00 → DEPLOY
        → Recovery AGRESIVO:
        → current_session = {start: "17:00"}
        → Recrea sesión ✅

20:00 → Discord NO reporta LoL (terminó hace 2h)
        → on_presence_update NO detecta nada

20:20 → Grace period expira (20 min)
        → Health check cierra sesión
        → Guarda: 3h (17:00 - 20:20) ❌ INCORRECTO
        → Debería ser 1h (17:00 - 18:00)
```

**Resultado:** ❌ **GUARDA MAL** - Agrega 2h extra

---

### **Caso 4: Usuario juega, para, vuelve a jugar (varias sesiones)**
```
17:00 → Juega LoL (1h)
18:00 → Para de jugar
        → Guarda: 1h ✅
        → current_session = null ✅

19:00 → Juega LoL de nuevo (2h)
        → current_session = {start: "19:00"}

20:30 → DEPLOY
        → Recovery: current_session = {start: "19:00"}
        → Recrea sesión ✅

21:00 → Termina
        → Guarda: 2h (19:00 - 21:00) ✅

Total: 1h + 2h = 3h ✅
```

**Resultado:** ✅ PERFECTO

---

### **Caso 5: Deploy durante grace period**
```
17:00 → Juega LoL
17:30 → Discord deja de reportar (lobby)
        → Sesión en grace
        → current_session = {start: "17:00"} ✅

17:35 → DEPLOY (5 min después)
        → Recovery: current_session = {start: "17:00"}
        → Recrea sesión ✅

17:38 → Vuelve del lobby
        → Discord reporta LoL
        → on_presence_update: active_sessions ya existe
        → Actualiza activity ✅

18:00 → Termina
        → Guarda: 1h correcta ✅
```

**Resultado:** ✅ PERFECTO

---

### **Caso 6: Termina, abre otra sesión INMEDIATA**
```
17:00 → Juega LoL
18:00 → Termina
        → current_session debería = null
        → Pero Discord tarda en reportar...

18:00 → DEPLOY (justo cuando termina)
        → current_session = {start: "17:00"} (no limpió)
        → Recrea sesión ✅

18:01 → Discord reporta que NO juega
        → handle_game_end()
        → Grace 20 min
        
18:21 → No volvió
        → Health check cierra
        → Guarda: 1h 21min ❌ (+21 min extra)

18:05 → Empieza LoL DE NUEVO
        → on_presence_update detecta
        → active_sessions[user] ya existe (de recovery)
        → ¿Qué pasa? ❓
```

**Resultado:** ⚠️ **CONFLICTO POTENCIAL**

---

### **Caso 7: Recovery con sesión muy vieja (>12h)**
```
DAY 1 - 10:00 → Juega
DAY 1 - 11:00 → Bot crashea
        → current_session queda

DAY 2 - 10:00 → DEPLOY (23h después)
        → Recovery AGRESIVO: recrea sesión
        → active_sessions[user] = sesión (start: ayer)

DAY 2 - 10:30 → Health check
        → Cleanup huérfanas: >12h sin memoria
        → Pero ESTÁ en memoria ahora ❌
        → NO limpia

DAY 2 - 10:35 → Discord NO reporta (terminó ayer)
        → Grace 20 min

DAY 2 - 10:55 → Health check cierra
        → Guarda: 24h 55min ❌❌❌
```

**Resultado:** ❌ **MUY MAL** - Guarda 24h de más

---

## 🎯 **ANÁLISIS:**

### **Recovery agresivo funciona SI:**
✅ Usuario SIGUE jugando después del deploy  
✅ Sesión es reciente (<1h idealmente)  
✅ Discord reporta rápido después del deploy

### **Recovery agresivo FALLA SI:**
❌ Usuario terminó ANTES del deploy (agrega tiempo extra)  
❌ Sesión es vieja (>12h) (agrega mucho tiempo extra)  
❌ Deploy durante cambio de juego (conflictos)

---

## 💡 **SOLUCIONES POSIBLES:**

### **Opción A: Recovery con validación Discord (actual)**
```python
if current_session and discord_sigue_reportando():
    recuperar()
```
**Pro:** Solo recupera sesiones activas  
**Con:** Si está en menú, no recupera (pierde tiempo)

---

### **Opción B: Recovery agresivo + límite de edad**
```python
if current_session and age < 2h:
    recuperar()  # Sin verificar Discord
```
**Pro:** Recupera la mayoría de casos  
**Con:** Casos 3 y 7 (terminó hace rato) guardan tiempo extra

---

### **Opción C: Limpiar current_session al finalizar**
```python
# En handle_game_end, SIEMPRE:
clear_game_session(user_id, game_name)  # Limpia current_session

# Incluso si está en grace:
if in_grace:
    # Marcar para limpiar después
    pending_cleanup[user_id] = game_name
```
**Pro:** No hay sesiones colgadas  
**Con:** Más complejo

---

### **Opción D: Recovery solo para voice (trade-off)**
```python
# NO recuperar games/parties
# Aceptar pérdida en deploys (~5% de tiempo)
```
**Pro:** Simple, sin bugs  
**Con:** Pierdes tiempo en deploys

---

## 🤔 **MI RECOMENDACIÓN:**

**Opción B + C combinadas:**

1. **Recovery agresivo SOLO si sesión <1h**
2. **Limpiar current_session SIEMPRE al finalizar** (no esperar grace)

**¿Por qué 1h?**
- Deploy toma 30 seg
- Chance de deploy durante sesión <1h: ALTA
- Chance de deploy durante sesión >1h sin que termine antes: BAJA

**¿Implemento esto?**

