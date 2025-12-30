# ⏱️ Cambio de Buffer de Gracia: 5 min → 15 min

## 📋 **Resumen del Cambio**

Se aumentó el **buffer de gracia de 5 a 15 minutos** para todas las sesiones (Voice, Games, Parties).

---

## 🔢 **Cambios Específicos:**

```python
# ANTES:
grace_period_seconds = 300  # 5 minutos

# DESPUÉS:
grace_period_seconds = 900  # 15 minutos
```

---

## 🎯 **¿Por qué 15 minutos?**

### **Casos que ahora SÍ cubre (antes NO):**

```
1. Pausa para café/baño (10 min)
   ✅ ANTES: 2 sesiones separadas
   ✅ AHORA: 1 sesión continua

2. Lobby de juegos lentos (8-12 min)
   ✅ ANTES: 2 sesiones separadas
   ✅ AHORA: 1 sesión continua

3. Reinicio rápido de juego (5-10 min)
   ✅ ANTES: 2 sesiones separadas
   ✅ AHORA: 1 sesión continua

4. Lag/desconexión prolongada (7-10 min)
   ✅ ANTES: Sesión cerrada
   ✅ AHORA: Sesión continúa
```

### **Casos que todavía NO cubre (correcto):**

```
1. Almuerzo/cena (30-60 min)
   ✅ 2 sesiones separadas (correcto)

2. Jugar de noche, volver al mediodía (9 horas)
   ✅ 2 sesiones separadas (correcto)

3. Pausa para ver serie (1-2 horas)
   ✅ 2 sesiones separadas (correcto)
```

---

## 📊 **Comparación:**

| Escenario | Buffer 5 min | Buffer 15 min |
|-----------|--------------|---------------|
| Lobby LoL (3 min) | ✅ Continúa | ✅ Continúa |
| Búsqueda Valorant (2 min) | ✅ Continúa | ✅ Continúa |
| Pausa café (10 min) | ❌ Cierra | ✅ Continúa |
| Reinicio juego (8 min) | ❌ Cierra | ✅ Continúa |
| Almuerzo (30 min) | ❌ Cierra | ❌ Cierra |
| Noche → Mediodía (9h) | ❌ Cierra | ❌ Cierra |

---

## 🔧 **Archivos Modificados:**

| Archivo | Cambio |
|---------|--------|
| `core/base_session.py` | `grace_period_seconds: 300 → 900` |
| `test_buffer_simple.py` | Tests actualizados con 15 min |
| `BUFFER_GRACIA_UNIFICADO.md` | Documentación actualizada |

---

## ✅ **Tests (5/5 Pasando):**

```bash
test_buffer_simple.py::TestBufferGraciLogic::test_actualizar_actividad PASSED
test_buffer_simple.py::TestBufferGraciLogic::test_escenario_lobby_lol PASSED
test_buffer_simple.py::TestBufferGraciLogic::test_session_inicializa_con_timestamp PASSED
test_buffer_simple.py::TestBufferGraciLogic::test_verificar_gracia_dentro_del_limite PASSED (10 min)
test_buffer_simple.py::TestBufferGraciLogic::test_verificar_gracia_fuera_del_limite PASSED (20 min)
```

---

## 💡 **Ejemplo Práctico:**

### **Usuario jugando con pausas:**

```
20:00 ━━━━━━ Partida LoL #1 (30 min)
20:30 ━━ Lobby (3 min)
20:33 ━━━━━━ Partida LoL #2 (35 min)
21:08 ⏸️  Pausa café (10 min) ← NUEVO: Ya NO cierra sesión
21:18 ━━━━━━ Partida LoL #3 (25 min)
21:43 🛑 Deja de jugar
21:58 🔒 Sesión cerrada (15 min después)

Resultado: 1 sesión de 1h 43min ✅ (antes serían 3 sesiones)
```

---

## 🎯 **Ventajas del Buffer de 15 min:**

✅ **Más tolerante** con pausas naturales (café, baño, snack)
✅ **Reduce fragmentación** de sesiones largas
✅ **Mantiene contexto** de sesiones de gaming
✅ **Trackea mejor** el tiempo real jugado
✅ **Menos spam** de notificaciones para pausas cortas

---

## ⚠️ **Trade-off:**

- **Pro:** Sesiones más continuas, mejor tracking
- **Contra:** Pausas de 10-15 min se consideran parte de la misma sesión
  - Esto es **aceptable** ya que son pausas típicas durante gaming

---

## 📈 **Impacto Esperado:**

| Métrica | Antes | Después |
|---------|-------|---------|
| **Sesiones/día** | 8-10 | 4-6 (más consolidadas) |
| **Spam notificaciones** | Alto (pausas cortas) | Bajo (solo pausas largas) |
| **Tracking precisión** | Media (fragmentado) | Alta (sesiones completas) |
| **UX** | Molesto (muchas notifs) | Mejor (menos ruido) |

---

## 🚀 **Estado Final:**

✅ Buffer aumentado de 5 a 15 minutos
✅ Tests actualizados y pasando
✅ Documentación actualizada
✅ Listo para deploy

