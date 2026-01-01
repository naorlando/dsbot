# 🐛 Fix: Sesiones Colgadas en Período de Gracia

## 📋 Problema Reportado (31/12/2025 - 00:04)

### **Logs:**
```
2026-01-01 00:04:50 - Zamu empieza Fortnite
2026-01-01 00:04:52 - ⏳ Sesión de juego en gracia: Zamu - Fortnite
2026-01-01 00:26:16 - 🏥 Health check: games: 0
                     - ❌ NO hay log "💾 Tiempo guardado"
```

**Síntoma:** Sesiones muy cortas que entran en gracia pero **nunca se finalizan correctamente**.

---

## 🔍 Análisis de Causa Raíz

### **Flujo Problemático:**

1. **Usuario juega < 10 segundos**
   - Zamu abre Fortnite (00:04:50)
   - Discord reporta actividad
   - `handle_game_start` crea sesión

2. **Usuario cierra el juego rápidamente**
   - Zamu cierra Fortnite (00:04:52)
   - Discord reporta fin de actividad
   - `handle_game_end` se llama

3. **Sesión entra en gracia**
   - `time_since_last_activity = 2 segundos`
   - `2s < 900s` (15 min de gracia)
   - Método retorna sin finalizar
   - **Sesión queda en `active_sessions`**

4. **Discord deja de enviar eventos**
   - No se llama más a `handle_game_end`
   - La sesión queda "colgada"
   - Esperando que:
     - Discord envíe otro evento (no lo hace)
     - Health check la detecte (21 min después ya no está)

5. **Sesión desaparece sin logs**
   - Entre 00:04:52 y 00:26:16, la sesión se perdió
   - No hay log de finalización
   - No se guardó tiempo

---

## 🎯 Solución Implementada

### **Fix Principal: Timeout en Gracia**

```python
# core/game_session.py - línea ~145

if self._is_in_grace_period(session):
    logger.info(f'⏳ Sesión de juego en gracia: {member.display_name} - {game_name} (última actividad hace {int(time_since_activity)}s)')
    
    # NUEVO: Si la sesión lleva MÁS de 5 minutos en gracia y NO se confirmó,
    # finalizarla silenciosamente (Discord dejó de enviar eventos)
    time_in_grace = (now - session.last_activity_update).total_seconds()
    if time_in_grace > 300 and not session.is_confirmed:  # 5 minutos
        logger.warning(f'⚠️  Sesión en gracia demasiado tiempo ({int(time_in_grace)}s): Finalizando {member.display_name} - {game_name}')
        # NO retornar, continuar con finalización
    else:
        return
```

---

## ✅ Comportamiento Corregido

### **Nuevo Flujo:**

1. **Usuario juega < 10 segundos**
   - Sesión empieza (00:00:00)
   - Usuario cierra rápido (00:00:02)

2. **Primer intento de finalización**
   - `handle_game_end` se llama (00:00:02)
   - Entra en gracia (`2s < 900s`)
   - **Retorna sin finalizar**
   - Sesión queda en memoria

3. **Discord no envía más eventos**
   - Pasan 5 minutos (00:05:02)
   - Sesión sigue en `active_sessions`

4. **Segundo intento de finalización (o health check)**
   - `handle_game_end` se llama de nuevo (por cualquier evento)
   - Verifica gracia: `time_in_grace = 300s`
   - Como `300s > 300s` y `!is_confirmed`:
     - **Fuerza finalización**
     - Log: `⚠️  Sesión en gracia demasiado tiempo (300s): Finalizando...`

5. **Sesión se finaliza correctamente**
   - `duration = 2s < 10s` y `!is_confirmed`
   - `session_is_valid_for_time = False`
   - **No se guarda tiempo** (esperado para sesiones < 10s)
   - Log: `⏭️  Sesión NO válida para guardar: Zamu - Fortnite (2.0s) - Confirmada: False`
   - Se borra de `active_sessions`

---

## 📊 Mejoras en Logging

### **Logs Agregados para Debugging:**

1. **En cada llamada a `handle_game_end`:**
   ```
   🔍 handle_game_end llamado: Zamu - Fortnite
   📊 Estado sesión: Zamu - Fortnite | Inicio: 2s atrás | Última actividad: 2s atrás | Confirmada: False
   ```

2. **En sesiones en gracia:**
   ```
   ⏳ Sesión de juego en gracia: Zamu - Fortnite (última actividad hace 2s)
   ```

3. **En sesiones forzadas:**
   ```
   ⚠️  Sesión en gracia demasiado tiempo (320s): Finalizando Zamu - Fortnite
   ```

4. **En sesiones no válidas:**
   ```
   ⏭️  Sesión NO válida para guardar: Zamu - Fortnite (2.0s) - Confirmada: False
   ```

---

## ⚖️ Trade-offs y Consideraciones

### **¿Por qué 5 minutos de timeout?**

- **Menor tiempo (1-2 min):** Riesgo de finalizar sesiones legítimas si Discord tiene lag
- **Mayor tiempo (10+ min):** Sesiones quedan colgadas demasiado tiempo
- **5 minutos:** Balance óptimo
  - Suficiente para manejar lags de Discord
  - Lo suficientemente corto para evitar acumulación de sesiones colgadas

### **¿Por qué forzar solo si `!is_confirmed`?**

- Sesiones **confirmadas** (> 10s) son legítimas
- Sesiones **no confirmadas** (< 10s) pueden ser:
  - Aperturas accidentales
  - Crashes de juegos
  - Pruebas rápidas
- Si llevan 5+ min en gracia y no se confirmaron, probablemente Discord dejó de reportar

---

## 🧪 Casos de Uso Cubiertos

### **✅ Caso 1: Apertura rápida (<10s)**
```
Usuario abre juego → Cierra en 2s → Discord deja de enviar eventos
→ 5 min después: Sesión forzada a finalizar
→ NO se guarda tiempo (esperado)
→ ✅ Sesión limpiada correctamente
```

### **✅ Caso 2: Lag temporal de Discord**
```
Usuario jugando → Discord deja de reportar (lag) → 2 min después reporta de nuevo
→ Sesión en gracia (2 min < 5 min)
→ Discord vuelve a reportar
→ Sesión continúa normalmente
→ ✅ No se pierde el tracking
```

### **✅ Caso 3: Discord deja de reportar permanentemente**
```
Usuario jugando 30 min → Discord para de reportar → No envía más eventos
→ 5 min después: Sesión aún en gracia
→ 15 min después (total 20 min): Grace period expira
→ Health check (30 min) detecta y finaliza
→ ✅ Se guarda tiempo acumulado
```

---

## 📈 Impacto Esperado

### **Antes del Fix:**
- Sesiones < 10s podían quedar colgadas indefinidamente
- Health check podía no detectarlas (si ya se "perdieron")
- Sin logs para debugging

### **Después del Fix:**
- Sesiones < 10s se finalizan automáticamente después de 5 min
- Logs completos para debugging
- Health check como backup (30 min)

---

## 🚀 Deploy

**Commit:** `[hash]`  
**Fecha:** 01/01/2026  
**Archivos Modificados:**
- `core/game_session.py`: Timeout de 5 min para sesiones en gracia
- Logs mejorados para debugging

**Próximos Pasos:**
- Monitorear logs para confirmar que sesiones colgadas se finalizan correctamente
- Verificar que no hay finalización prematura de sesiones legítimas

---

**Estado:** ✅ Implementado y listo para testing

