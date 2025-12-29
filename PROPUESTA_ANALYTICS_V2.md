# 📊 Propuesta de Mejora de Analytics - V2
## (Revisada y Enfocada)

---

## 🎯 Objetivos Principales

1. **Separar rankings por contexto** → Gamers ≠ Voice ≠ Chat
2. **Rankings por juego específico** → ¿Quién jugó más a Hades?
3. **Integrar parties en analytics** → Nuevo universo de datos
4. **Preparar wrapped** → Infraestructura para resumen anual
5. **Refactorizar y limpiar** → Código más mantenible

---

## ✅ Lo que NO vamos a cambiar

### **!stats se queda como está** (con mejoras menores opcionales)

El comando actual está bien, solo pequeñas mejoras:

```markdown
ACTUAL (está bien):
📊 Estadísticas de Pino
🎮 Juegos: Hades 2h 30m, Minecraft 1h 15m
🔊 Voz: 15h 20m en 42 sesiones
💬 Mensajes: 1,245

OPCIONAL (simplificar SI quieres):
- Eliminar "promedio chars/mensaje" → No aporta valor
- Simplificar "última conexión" → Poner solo si fue hoy
- Mantener top 3 emojis → Está bien, es divertido
```

**Decisión: Mantener como está, solo eliminar "promedio chars/mensaje"**

---

## 🔥 Lo que SÍ vamos a implementar

### **1. Rankings Separados por Contexto** ⭐ PRIORIDAD 1

```python
# ELIMINAR: !topusers (mezcla todo sin contexto)

# CREAR NUEVOS:
!topgamers [periodo]    # Ranking por TIEMPO de juego
!topvoice [periodo]     # Ranking por TIEMPO en voz  
!topchat [periodo]      # Ranking por mensajes

# MANTENER:
!topgames [periodo]     # Ya existe, pero mejorar formato
!topmessages           # Ya existe (alias de !topchat)
!topreactions          # Ya existe
!topemojis             # Ya existe
!topstickers           # Ya existe
!topconnections        # Ya existe
```

**Cambios en !topgames:**
- ✅ Ya ordena por tiempo (línea 227 de commands_basic.py)
- ⚠️ Mejorar formato para incluir # de jugadores y parties

### **2. Rankings por Juego Específico** ⭐ PRIORIDAD 2

```python
!topgame <juego>        # Quien jugó más a X juego
!rankings <juego>       # Stats completas del juego (alias)
```

**Ejemplo de salida:**

```markdown
🎮 Estadísticas de Hades

━━━ 🏆 TOP JUGADORES ━━━
1. 👑 Pino - 85h (22% del total)
2. 🥈 Zeta - 62h (16%)
3. 🥉 WiR - 48h (13%)

━━━ 📊 STATS GENERALES ━━━
⏱️ Tiempo total: 380h jugadas
👥 Jugadores: 12 únicos
🎉 Parties: 45 (promedio 3.2 jugadores)
📅 Más jugado en: Diciembre 2025

━━━ 🎉 PARTY STATS ━━━
🔥 Party más larga: 6h (@Pino, @Zeta, @Gamma)
👥 Party más grande: 5 jugadores
🤝 Mejor dúo: @Pino + @Zeta (15 parties)
```

### **3. Stats de Parties** ⭐ PRIORIDAD 3

```python
# MEJORAR COMANDOS EXISTENTES:
!party                  # Mostrar parties activas ahora
!partyhistory          # Historial de parties
!partystats            # Stats globales de parties

# CREAR NUEVOS:
!partymaster [periodo]  # Quien creó más parties
!partygames [periodo]   # Juegos con más parties  
!partywith @user        # Con quién jugaste más
```

### **4. Comparaciones** ⭐ PRIORIDAD 4

```python
!compare @user1 @user2  # Ya existe pero mejorar formato
```

**Nuevo formato:**

```markdown
🆚 Pino vs Zeta

━━━ 🎮 Gaming ━━━
Pino: 25h | Zeta: 18h
Juego favorito: Ambos Hades
Partys juntos: 5

━━━ 🔊 Voz ━━━
Pino: 15h | Zeta: 22h
Zeta gana por +7h

━━━ 💬 Chat ━━━
Pino: 1,245 msgs | Zeta: 2,341 msgs
Emoji favorito común: 🔥

━━━ 👥 Social ━━━
Juegos juntos: 5 (Hades, Minecraft...)
Mejor party: 8h en Valheim
```

### **5. Wrapped (Resumen Anual)** ⭐ PRIORIDAD 5 (LARGO PLAZO)

```python
!wrapped                # Tu año en Discord
!serverwrapped         # Stats del servidor
```

**NO implementar ahora, pero preparar infraestructura:**
- Agregar campos `by_month` en stats.json
- Agregar `yearly_totals` para comparar año a año
- Agregar tracking de `consecutive_days` (rachas)

---

## 🗂️ Plan de Refactorización

### **Estructura Actual:**
```
stats/
├── commands_basic.py       # 606 líneas - MUCHOS comandos mezclados
├── commands_advanced.py    # 250 líneas - OK
├── embeds.py              # ?
├── ui_components.py       # ?
└── __init__.py
```

### **Nueva Estructura Propuesta:**

```
stats/
├── __init__.py
│
├── commands/
│   ├── __init__.py
│   ├── rankings.py         # !topgamers, !topvoice, !topchat
│   ├── games.py            # !topgames, !topgame, !rankings
│   ├── parties.py          # !party, !partymaster, !partywith
│   ├── social.py           # !topmessages, !topreactions, !topemojis
│   ├── compare.py          # !compare
│   ├── user.py             # !stats, !statsuser
│   └── wrapped.py          # !wrapped, !serverwrapped (futuro)
│
├── visualization/
│   ├── __init__.py
│   ├── formatters.py       # format_time, etc
│   ├── charts.py           # ASCII charts
│   └── embeds.py           # Discord embeds
│
├── data/
│   ├── __init__.py
│   ├── aggregators.py      # Funciones para agregar datos
│   └── filters.py          # filter_by_period, etc
│
└── utils/
    ├── __init__.py
    └── helpers.py          # Utilidades comunes
```

### **Beneficios:**
- ✅ Cada archivo tiene una responsabilidad clara
- ✅ Más fácil encontrar y modificar comandos
- ✅ Módulos reutilizables
- ✅ Preparado para crecer (wrapped, más comandos)

---

## 💾 Nuevos Datos a Guardar

### **Para Wrapped (futuro):**

```json
{
  "users": {
    "user_id": {
      "games": {
        "Hades": {
          "total_minutes": 5100,
          "count": 85,
          
          // AGREGAR:
          "by_month": {
            "2025-01": 450,
            "2025-02": 380
          },
          "consecutive_days": 15,
          "days_played": 62
        }
      },
      
      "voice": {
        "total_minutes": 10800,
        
        // AGREGAR:
        "by_month": {
          "2025-01": 950,
          "2025-02": 880
        },
        "by_hour": {
          "20": 450,
          "21": 520,
          "22": 380
        },
        "consecutive_days": 12
      },
      
      // AGREGAR: Stats de parties por usuario
      "parties": {
        "total_parties": 45,
        "total_minutes": 1140,
        "by_game": {
          "Minecraft": {"count": 25, "minutes": 680}
        },
        "partners": {
          "other_user_id": 25
        },
        "longest_party_minutes": 480
      },
      
      // AGREGAR: Para comparar año a año
      "yearly_totals": {
        "2025": {
          "games_minutes": 25000,
          "voice_minutes": 15000,
          "messages": 8542
        }
      }
    }
  },
  
  // AGREGAR: Stats globales del servidor
  "server": {
    "yearly_totals": {
      "2025": {
        "total_game_minutes": 150000,
        "total_voice_minutes": 108000,
        "total_parties": 234
      }
    },
    "records": {
      "longest_party": {"game": "Minecraft", "minutes": 480},
      "largest_party": {"game": "Minecraft", "players": 8}
    }
  }
}
```

**⚠️ Importante:** Estos datos NO son necesarios ahora. Solo los guardamos cuando implementemos wrapped.

---

## 📋 Plan de Implementación

### **Fase 1: Refactor (1 semana)** ✅ HACER YA

1. ✅ Reorganizar estructura de carpetas
2. ✅ Separar comandos en módulos lógicos
3. ✅ Mover formatters/helpers a su lugar
4. ✅ Actualizar imports en todos lados
5. ✅ Testear que todo sigue funcionando

### **Fase 2: Rankings Separados (3 días)** ⭐

1. ✅ Crear `!topgamers` (ranking por tiempo de juego)
2. ✅ Crear `!topvoice` (ranking por tiempo en voz)
3. ✅ Deprecar `!topusers` → redireccionar a nuevo menú
4. ✅ Mejorar formato de `!topgames` con parties

### **Fase 3: Rankings por Juego (3 días)** ⭐

1. ✅ Crear `!topgame <juego>` → top jugadores de ese juego
2. ✅ Agregar stats de parties por juego
3. ✅ Agregar "mejor dúo" y "party más larga"

### **Fase 4: Mejorar Parties (3 días)** ⭐

1. ✅ Crear `!partymaster` → quien creó más parties
2. ✅ Crear `!partygames` → juegos con más parties
3. ✅ Crear `!partywith @user` → stats de parties con alguien
4. ✅ Mejorar `!partystats` con más info

### **Fase 5: Comparaciones (2 días)**

1. ✅ Mejorar formato de `!compare`
2. ✅ Agregar stats de parties a la comparación
3. ✅ Agregar juegos/emojis en común

### **Fase 6: Preparar Wrapped (2 semanas)** 🔮 FUTURO

1. 🔮 Agregar tracking de `by_month`
2. 🔮 Agregar `yearly_totals`
3. 🔮 Agregar `consecutive_days`
4. 🔮 Implementar `!wrapped`
5. 🔮 Implementar `!serverwrapped`

**Total: ~2-3 semanas** (sin contar wrapped)

---

## 🚀 Quick Wins (Hacer HOY)

1. **Mejorar !topgames** → Agregar # de jugadores y parties
2. **Eliminar "promedio chars" de !stats** → Ruido innecesario
3. **Crear !topgamers** → Código casi idéntico a !topusers
4. **Crear !topvoice** → Código similar a !topgamers
5. **Deprecar !topusers** → Mostrar mensaje: "Usa !topgamers o !topvoice"

---

## 🎯 Resumen Ejecutivo

### **Lo que vamos a hacer:**

✅ **Mantener !stats** como está (solo quitar "promedio chars")
✅ **Separar rankings** → !topgamers, !topvoice, !topchat
✅ **Rankings por juego** → !topgame Hades
✅ **Mejorar parties** → !partymaster, !partywith
✅ **Refactorizar** → Estructura modular clara
✅ **Preparar wrapped** → Infraestructura de datos (sin implementar aún)

### **Lo que NO vamos a hacer (ahora):**

❌ Reescribir !stats completamente
❌ Implementar wrapped completo (solo preparar datos)
❌ Cambios grandes en visualización
❌ Sistema de logros/achievements

### **Impacto esperado:**

📈 Rankings más claros y útiles
🎮 Mejor comprensión de stats por juego
🤝 Más engagement con parties
🛠️ Código más fácil de mantener
🚀 Base lista para wrapped cuando lo necesitemos

---

## 🤔 Decisiones Pendientes

### **¿Qué hacemos con !topusers?**

**Opción A:** Eliminar y mostrar error
```
❌ !topusers ya no existe
✅ Usa !topgamers o !topvoice en su lugar
```

**Opción B:** Redireccionar automáticamente
```python
@bot.command(name='topusers')
async def topusers_deprecated(ctx):
    await ctx.send(
        '⚠️ `!topusers` fue reemplazado:\n'
        '• `!topgamers` → Top jugadores por tiempo\n'
        '• `!topvoice` → Top usuarios en voz\n'
        '• `!topchat` → Top usuarios en chat'
    )
```

**Opción C:** Mostrar menú para elegir
```python
# Botones: "Ver Gamers" | "Ver Voice" | "Ver Chat"
```

**👉 Tu decides cuál prefieres**

---

## 📊 Antes vs Después

### **ANTES:**
```
!topusers → Mezcla juegos + voz (confuso)
!stats → Muestra "promedio chars" (ruido)
No hay !topgame Hades
Parties sin analytics detalladas
```

### **DESPUÉS:**
```
!topgamers → Solo juegos, por tiempo
!topvoice → Solo voz, por tiempo
!topchat → Solo chat, por mensajes
!stats → Limpio, sin ruido
!topgame Hades → Stats del juego + parties
!partymaster → Quien hace más parties
!partywith @user → Stats de parties juntos
```

---

## ✅ Siguiente Paso

**¿Empezamos con el refactor y los Quick Wins?**

1. Refactorizar estructura de carpetas
2. Eliminar "promedio chars" de !stats
3. Crear !topgamers
4. Crear !topvoice
5. Deprecar !topusers

**¿O preferís otro orden?**

