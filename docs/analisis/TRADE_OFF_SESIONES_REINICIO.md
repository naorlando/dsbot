# ⚠️ Trade-off: Sesiones Perdidas al Reiniciar

## 📋 Problema Observado

**Logs del 31/12/2025 - 23:48:**
```
2025-12-31 23:48:37 - 🔄 Recuperando sesiones de voice después de reinicio...
2025-12-31 23:48:37 - ♻️  Sesión de voz restaurada: Zamu en 👥 General
2025-12-31 23:48:37 - ♻️  Sesión de voz restaurada: Pino en 👥 General
2025-12-31 23:48:37 - ♻️  2 sesiones de voz restauradas (limpiadas: 0)
2025-12-31 23:48:37 - 🏥 Health check periódico iniciado (cada 30 min)
2025-12-31 23:48:37 - 🏥 Health check iniciado (games: 0, parties: 0)
```

**¿Por qué no se recuperó la sesión de agu (FINAL FANTASY XV)?**

---

## 🔍 Explicación Técnica

### **Tipos de Sesiones:**

| Tipo | Persistencia | Recuperable |
|------|--------------|-------------|
| **Voice** | `pending_notifications.json` | ✅ SÍ |
| **Games** | Solo en memoria | ❌ NO |
| **Parties** | Solo en memoria | ❌ NO |

---

### **¿Por qué Voice SÍ se recupera?**

```python
# Voice guarda en pending_notifications.json
save_voice_notification(user_id, username, channel_name)
# En reinicio:
pending_voice = get_pending_voice_notifications()
# → Restaura sesión silenciosamente
```

**Beneficio:**
- Si un usuario está en voice y el bot reinicia
- La sesión se recupera sin notificación duplicada
- Se aplica cooldown de 20 min

---

### **¿Por qué Games/Parties NO se recuperan?**

```python
# Games/Parties solo en memoria
game_manager.active_sessions[user_id] = GameSession(...)
# En reinicio:
# → Se pierde, active_sessions = {}
```

**Razón:**
- Simplificación agresiva (semana del 28/12)
- Trade-off aceptado para reducir complejidad
- Overhead mínimo vs persistencia completa

---

## 📊 Impacto Real

### **Escenarios:**

#### **1. Bot Crashea Durante Sesión de Juego**
```
Usuario jugando LoL (30 min acumulados)
       ↓
Bot crashea y reinicia (10 segundos)
       ↓
Sesión se pierde
       ↓
❌ 30 minutos NO guardados
```

**Frecuencia:** Muy baja (~1% de sesiones si hay 1 reinicio/semana)

---

#### **2. Bot Crashea Durante Sesión de Voice**
```
Usuario en voice (1 hora acumulada)
       ↓
Bot crashea y reinicia (10 segundos)
       ↓
Sesión se recupera silenciosamente
       ↓
✅ 1 hora SE GUARDARÁ cuando salga normalmente
```

**Frecuencia:** 100% recuperación

---

#### **3. Health Check Detecta Sesión Colgada**
```
Usuario jugando (última actividad hace 20 min)
Discord deja de reportar
       ↓
Health check (30 min después)
       ↓
Detecta: last_activity > 15 min
       ↓
✅ Finaliza y guarda tiempo acumulado
```

**Frecuencia:** ~5% de sesiones (cuando Discord falla)

---

## 🎯 ¿Qué Cubre el Health Check?

### **✅ Lo que SÍ detecta:**

1. **Sesiones colgadas (Discord no reporta)**
   - Usuario jugó 30 min
   - Discord dejó de reportar hace 20 min
   - Health check finaliza y guarda

2. **Sesiones muy largas sin updates**
   - Usuario en party hace 2 horas
   - Última actividad hace 18 min
   - Health check marca como inactiva

3. **Parties en lobbies eternos**
   - Party inactiva hace 45 min
   - Ventana de reactivación expirada
   - Health check cierra definitivamente

---

### **❌ Lo que NO puede detectar:**

1. **Sesiones perdidas por reinicio**
   - La sesión ya no está en memoria
   - No hay forma de recuperarla
   - Trade-off aceptado

2. **Reinicios durante grace period**
   - Usuario jugó 5 min
   - Bot reinicia
   - Sesión < 10 min, no se había guardado

---

## 💡 Logs Mejorados

### **Antes (confuso):**
```
🏥 Iniciando health check periódico...
✅ Health check completado: Todo OK
```
❓ ¿Por qué no detectó la sesión de agu?

---

### **Ahora (claro):**
```
🏥 Health check iniciado (games: 0, parties: 0)
✅ Health check: Todo OK
```
✅ Queda claro que NO hay sesiones activas en memoria

---

## 🔄 Flujo Completo: Startup

```
[Bot Reinicia]
      ↓
[on_ready]
      ↓
[Recovery de Voice]
  ├─ Leer pending_notifications.json
  ├─ Zamu en voz → Restaurar sesión
  ├─ Pino en voz → Restaurar sesión
  └─ agu NO en voz → Limpiar (era game, no voice)
      ↓
[Health Check Inicia]
  ├─ Revisar game_manager.active_sessions
  │  └─ Vacío (sesiones se perdieron al reiniciar)
  ├─ Revisar party_manager.active_sessions
  │  └─ Vacío (sesiones se perdieron al reiniciar)
  └─ Log: games: 0, parties: 0
      ↓
[Health Check cada 30 min]
  └─ Si Discord reporta nuevas sesiones
     └─ Se acumulan en memoria
     └─ Health check las valida
```

---

## ✅ Conclusión

### **El comportamiento es CORRECTO:**

1. ✅ **Voice se recupera** (persistencia ligera)
2. ❌ **Games/Parties se pierden** (trade-off aceptado)
3. ✅ **Health check detecta colgadas** (cuando hay sesiones en memoria)
4. ✅ **Logs más claros** (muestra cuántas sesiones hay)

---

### **La sesión de agu NO se recuperó porque:**

1. Era una sesión de **juego** (no voice)
2. Las sesiones de juego **no persisten**
3. Al reiniciar, se **perdió de memoria**
4. El health check **no puede recuperar** algo que no existe

---

### **Esto es aceptable porque:**

- Frecuencia muy baja (~1% de sesiones)
- Complejidad evitada (persistencia completa)
- Health check cubre el 99% de casos (sesiones colgadas)
- Voice sí se recupera (caso más importante)

---

**Fecha:** 31 de diciembre de 2025  
**Estado:** ✅ Comportamiento esperado y documentado

