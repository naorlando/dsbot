# 🎮 Propuesta: Rediseño Completo del Sistema de Parties

## 📋 Estado Actual: ¿Cómo funciona ahora?

### **Respuestas a tus preguntas:**

```
Entra 1 y 2 → ✅ Se forma party (key: "League of Legends")
Entra 3 → ✅ Se suma a la MISMA party (actualiza jugadores)
Entra 4 → ✅ Se suma a la MISMA party (actualiza jugadores)

Se sale 3 → ⚠️ Se actualiza la party (quita jugador 3)
           → Si quedan < 2 → Party se FINALIZA

Entra 3 de nuevo → ❓ DEPENDE:
                   - Si la party sigue activa (≥2 jugadores) → Se suma a la MISMA
                   - Si la party ya finalizó (< 2 jugadores) → NUEVA party
```

### **Key de identificación:**
```python
# La party se identifica SOLO por el nombre del juego
active_sessions[game_name] = PartySession(...)

# NO por grupo de jugadores
# NO por "quién entró primero"
# SOLO por juego
```

---

## 🔴 Problemas Identificados

### **1. Buffer de Gracia vs Lobbies Largos**
```
17:23 - Party inicia (2 jugadores)
17:38 - Lobby/búsqueda (Discord deja de reportar actividad)
17:39 - Buffer expira (15 min) → Party FINALIZADA
17:39 - Salen del lobby → Party NUEVA → SPAM ❌
```

**Problema:** Lobbies largos (>15 min) cierran la party y crean spam.

---

### **2. No hay concepto de "Sesión de Juego Continua"**
```
Party 1: 17:23-17:39 (15 min)
Party 2: 17:39-18:30 (51 min)

Para el usuario: 1 sesión de juego de 66 minutos
Para el sistema: 2 parties separadas
```

**Problema:** División artificial de sesiones continuas.

---

### **3. Party por Juego, no por Grupo**
```
Jugadores A+B jugando LoL → Party 1
Jugadores C+D jugando LoL → ❌ MISMA Party (sobrescribe)
```

**Problema:** Solo puede haber 1 party por juego en todo el servidor.

---

### **4. Re-join después de < 2 jugadores**
```
A+B jugando → Party activa
B se va → Party FINALIZADA (< 2)
B vuelve 2 min después → Party NUEVA → SPAM ❌
```

**Problema:** Salidas temporales crean spam de notificaciones.

---

## 🎯 Propuesta de Solución: Sistema de "Sesiones de Juego Persistentes"

### **Concepto Central: "Gaming Session"**

```
Gaming Session = Período continuo donde ≥2 jugadores están en el mismo juego
                 (tolerando pausas/lobbies de hasta X minutos)
```

### **Características:**

1. **Tolerancia a Lobbies Largos:** 30-45 minutos (no 15)
2. **Identificación Híbrida:** Juego + primer grupo de jugadores
3. **Notificaciones Inteligentes:** 1 sola por sesión continua
4. **Tracking Unificado:** 1 registro para toda la sesión

---

## 🏗️ Arquitectura Propuesta

### **Opción A: "Soft Close" (Recomendada) ⭐**

**Concepto:** Party NO se cierra al instante, se marca como "inactiva" y puede reactivarse.

```python
class PartySession:
    def __init__(self, ...):
        self.state = 'active'  # active, inactive, closed
        self.inactive_since = None
        self.reactivation_window = 30 * 60  # 30 minutos
```

#### **Flujo:**

```
1. Party inicia (A+B jugando)
   → state = 'active'
   → Notifica ✅

2. Discord deja de reportar (lobby)
   → state = 'inactive'
   → inactive_since = now()
   → NO notifica, NO cierra

3. Dentro de 30 min:
   a) Vuelven a jugar → state = 'active' → NO notifica ✅
   b) Pasan 30 min → state = 'closed' → Finalizar y guardar

4. Después de cerrada:
   → Si vuelven a jugar → NUEVA party → Notifica (pero cooldown 60 min aplica)
```

#### **Ventajas:**
- ✅ **Simple:** Solo agrega un estado intermedio
- ✅ **Efectivo:** Elimina spam en lobbies
- ✅ **Flexible:** Ventana configurable
- ✅ **Backward compatible:** Tracking sigue funcionando

#### **Desventajas:**
- ⚠️ Parties "inactivas" en memoria por 30 min

---

### **Opción B: "Smart Cooldown con Historial"**

**Concepto:** Cooldown inteligente que mira historial reciente.

```python
def should_notify_party(game_name, current_players):
    # Cooldown estándar de 60 min
    if not check_cooldown(game_name, f'party_formed_{game_name}', 60*60):
        return False
    
    # Verificar si hay una party reciente (últimas 2 horas) con los mismos jugadores
    recent_parties = get_recent_parties(game_name, hours=2)
    for party in recent_parties:
        if set(party['players']) == set(current_players):
            # Mismos jugadores en las últimas 2 horas → NO notificar
            return False
    
    return True
```

#### **Ventajas:**
- ✅ **Cero overhead:** No mantiene estado en memoria
- ✅ **Histórico:** Usa datos ya guardados
- ✅ **Robusto:** Funciona incluso con restarts del bot

#### **Desventajas:**
- ⚠️ Más complejo
- ⚠️ Queries a stats.json

---

### **Opción C: "Party ID única"**

**Concepto:** Identificar party por grupo inicial de jugadores + juego.

```python
def get_party_id(game_name, player_ids):
    # Ordenar para tener siempre el mismo ID
    sorted_ids = sorted(player_ids)
    return f"{game_name}_{hash(tuple(sorted_ids))}"

# Ejemplo:
# A+B en LoL → "lol_abc123"
# C+D en LoL → "lol_def456"  (¡DIFERENTE!)
```

#### **Ventajas:**
- ✅ **Múltiples parties:** Varios grupos pueden jugar el mismo juego
- ✅ **Identificación clara:** Cada grupo tiene su party

#### **Desventajas:**
- ⚠️ **Complejo:** Qué pasa si C se une a A+B?
- ⚠️ **Fragmentación:** Muchas parties pequeñas

---

## 🎯 Recomendación Final: Opción A + Tweaks

### **Implementación:**

```python
class PartySession(BaseSession):
    def __init__(self, ...):
        super().__init__(...)
        self.state = 'active'  # active, inactive, closed
        self.inactive_since = None
        self.reactivation_window = 30 * 60  # 30 minutos
        self.notification_sent = False  # Para evitar spam

class PartySessionManager:
    async def handle_start(self, game_name, current_players, guild_id, config):
        # Caso 1: No hay sesión
        if game_name not in self.active_sessions:
            session = PartySession(...)
            session.state = 'active'
            # Notificar solo si cooldown permite
            if check_cooldown(..., 60*60):
                notify(...)
                session.notification_sent = True
        
        # Caso 2: Sesión inactiva → REACTIVAR
        elif self.active_sessions[game_name].state == 'inactive':
            session = self.active_sessions[game_name]
            session.state = 'active'
            session.inactive_since = None
            # NO notificar, es la misma sesión ✅
        
        # Caso 3: Sesión activa → actualizar
        else:
            session = self.active_sessions[game_name]
            # Detectar nuevos jugadores y notificar si aplica
            ...
    
    async def handle_end(self, game_name, config):
        if game_name not in self.active_sessions:
            return
        
        session = self.active_sessions[game_name]
        
        # NO cerrar inmediatamente, marcar como inactiva
        if session.state == 'active':
            session.state = 'inactive'
            session.inactive_since = datetime.now()
            logger.info(f'⏸️  Party inactiva: {game_name} (ventana: 30 min)')
            return  # NO finalizar todavía
        
        # Si ya estaba inactiva, verificar ventana
        if session.state == 'inactive':
            time_inactive = (datetime.now() - session.inactive_since).total_seconds()
            if time_inactive < session.reactivation_window:
                logger.info(f'⏳ Party sigue en ventana: {game_name} ({int(time_inactive/60)} min)')
                return  # Todavía puede reactivarse
            
            # Ventana expirada → cerrar definitivamente
            session.state = 'closed'
            self._finalize_party_in_stats(game_name, session)
            del self.active_sessions[game_name]
            logger.info(f'🎮 Party cerrada definitivamente: {game_name}')
```

---

## 📊 Comparación de Opciones

| Criterio | Opción A (Soft Close) | Opción B (Smart Cooldown) | Opción C (Party ID) |
|----------|----------------------|---------------------------|---------------------|
| **Simplicidad** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Efectividad** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Overhead** | ⭐⭐⭐ (memoria) | ⭐⭐⭐⭐ (cero) | ⭐⭐ (complejo) |
| **Robustez** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **UX** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## 🔧 Configuración Propuesta

```json
{
  "party_detection": {
    "enabled": true,
    "min_players": 2,
    "notify_on_formed": true,
    "notify_on_join": true,
    "cooldown_minutes": 60,
    "reactivation_window_minutes": 30,  // NUEVO
    "use_here_mention": true,
    "blacklisted_games": [...]
  }
}
```

---

## 🧪 Casos de Prueba

### **Caso 1: Lobby largo**
```
17:00 - A+B → Party inicia → Notifica ✅
17:15 - Lobby (>15 min) → state = 'inactive'
17:45 - Salen del lobby → state = 'active' → NO notifica ✅
18:00 - Terminan de jugar → Party finalizada (60 min total)
```

### **Caso 2: Salida temporal**
```
17:00 - A+B → Party inicia → Notifica ✅
17:20 - B se va → state = 'inactive'
17:25 - B vuelve → state = 'active' → NO notifica ✅
```

### **Caso 3: Ventana expirada**
```
17:00 - A+B → Party inicia → Notifica ✅
17:15 - Ambos se van → state = 'inactive'
17:50 - Pasa ventana (30 min) → state = 'closed', party guardada
18:00 - Vuelven a jugar → NUEVA party → Cooldown 60 min previene spam ✅
```

### **Caso 4: Jugadores nuevos**
```
17:00 - A+B → Party inicia → Notifica ✅
17:10 - C se une → Notifica "C se unió" (cooldown individual)
17:20 - D se une → Notifica "D se unió" (cooldown individual)
```

---

## ✅ Beneficios de la Opción A

1. **Elimina spam de lobbies**: Ventana de 30 min tolera búsquedas/lobbies
2. **Tracking unificado**: 1 party = 1 sesión continua de juego
3. **Simple de implementar**: Solo agregar estados y lógica de ventana
4. **Configurable**: Ventana ajustable según necesidad
5. **Backward compatible**: No rompe tracking existente
6. **UX mejorada**: Usuario ve 1 notificación por sesión real

---

## 🚀 Plan de Implementación

### **Fase 1: Agregar estados**
- Modificar `PartySession` con `state`, `inactive_since`, `reactivation_window`
- Modificar `handle_end` para marcar como inactive en vez de cerrar

### **Fase 2: Lógica de reactivación**
- Modificar `handle_start` para detectar sesiones inactivas
- Reactivar en vez de crear nueva

### **Fase 3: Limpieza de inactivas**
- Background task que cierra definitivamente las inactivas expiradas
- O hacerlo en cada `handle_start`/`handle_end`

### **Fase 4: Tests**
- Test de lobby largo
- Test de salida temporal
- Test de ventana expirada
- Test de jugadores nuevos

### **Fase 5: Ajuste fino**
- Ajustar `reactivation_window` según feedback (30-45 min)
- Ajustar cooldowns si es necesario

---

## 💡 Alternativa Híbrida (Opción A + B)

Combinar lo mejor de ambas:

1. **Opción A** para sesiones activas (estado en memoria)
2. **Opción B** como fallback (si bot reinicia durante inactividad)

```python
async def handle_start(self, game_name, current_players, guild_id, config):
    # Primero, verificar memoria (Opción A)
    if game_name in self.active_sessions:
        # Lógica de reactivación...
        return
    
    # Si no está en memoria, verificar historial reciente (Opción B)
    if not check_cooldown(..., 60*60):
        return  # Cooldown activo
    
    recent_parties = get_recent_parties(game_name, minutes=120)
    for party in recent_parties:
        if set(party['players']) == set(current_player_ids):
            logger.info(f'🔄 Sesión reciente encontrada, no notificar')
            # Crear sesión sin notificar
            session = PartySession(...)
            session.notification_sent = True  # Ya se notificó antes
            self.active_sessions[game_name] = session
            return
    
    # Nueva sesión legítima
    session = PartySession(...)
    notify(...)
```

**Ventaja:** Robustez total, funciona incluso con restarts.

---

## 🎯 Recomendación Final

**Implementar Opción A (Soft Close) con estos parámetros:**

- `reactivation_window`: **30 minutos**
- `cooldown_minutes`: **60 minutos**
- `grace_period_seconds`: **900 segundos (15 min)** (actual)

**Resultado esperado:**
- ✅ No más spam de lobbies
- ✅ Tracking preciso de sesiones continuas
- ✅ UX mejorada
- ✅ Simple de mantener

---

**¿Quieres que implemente la Opción A?**

