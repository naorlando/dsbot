# 🗺️ Estado Actual: Sistema de Sesiones Completo

**Fecha:** 01 de enero de 2026  
**Versión:** Post-Simplificación Agresiva + Wrapped + Fixes

---

## 📊 ARQUITECTURA GENERAL

### **Base: Sistema Unificado de Sesiones**

```
BaseSession (base_session.py)
    ├─ Atributos comunes:
    │  ├─ user_id, username, guild_id
    │  ├─ start_time
    │  ├─ last_activity_update (para grace period)
    │  ├─ is_confirmed (verificado > min_duration)
    │  ├─ entry_notification_sent (flag para cooldowns)
    │  └─ notification_message (referencia al mensaje de Discord)
    │
    ├─ VoiceSession (voice_session.py)
    │  └─ channel_name
    │
    ├─ GameSession (game_session.py)
    │  ├─ game_name
    │  ├─ app_id
    │  ├─ activity_type
    │  └─ verification_task
    │
    └─ PartySession (party_session.py)
       ├─ game_name
       ├─ players (lista de user_ids)
       ├─ state (active, inactive, closed)
       ├─ inactive_since (datetime)
       └─ reactivation_window (segundos)

BaseSessionManager (base_session.py)
    ├─ Métodos comunes:
    │  ├─ _update_activity(session)
    │  ├─ _is_in_grace_period(session)
    │  ├─ handle_start() [abstracto]
    │  └─ handle_end() [abstracto]
    │
    ├─ VoiceSessionManager (voice_session.py)
    ├─ GameSessionManager (game_session.py)
    └─ PartySessionManager (party_session.py)
```

---

## 🎮 GAME SESSIONS

### **Flujo Completo:**

```
1. Discord reporta actividad
   ↓
2. on_presence_update detecta nuevo juego
   ↓
3. Verificación multicapa (6 capas):
   - ¿Es custom status? → Ignorar
   - ¿Es Activity legítimo? → Validar clase
   - ¿Tiene app_id? → Preferir con app_id
   - ¿Está en blacklist? → Ignorar
   - ¿Es streaming genérico? → Ignorar
   - ¿Pasa filtros? → Continuar
   ↓
4. GameSessionManager.handle_game_start()
   - Crear GameSession
   - Iniciar verification_task (10s)
   ↓
5. Después de 10s:
   - Si aún está jugando → Confirmar (is_confirmed = True)
   - Enviar notificación (cooldown: 30 min)
   - save_game_session() para tracking
   ↓
6. Discord deja de reportar:
   ↓
7. on_presence_update detecta juego terminado
   ↓
8. GameSessionManager.handle_game_end()
   ├─ Verificar grace period (15 min)
   │  ├─ Si < 15 min desde última actividad → Retornar (esperar)
   │  └─ Si > 5 min en gracia y NO confirmada → FORZAR FINALIZACIÓN (FIX)
   ├─ Si >= 15 min sin actividad → Finalizar
   ├─ Calcular duración
   ├─ Si >= 1 min → save_game_time()
   ├─ Notificar salida (si config habilitado)
   └─ Limpiar sesión
```

### **Características Actuales:**

✅ **Grace Period:** 15 minutos unificado  
✅ **Cooldown:** 30 minutos (resetea en cada intento)  
✅ **Verificación:** 10 segundos antes de confirmar  
✅ **Timeout en gracia:** 5 min para sesiones no confirmadas (NUEVO)  
✅ **Tracking:** Guarda tiempo si duró >= 1 minuto  
❌ **Persistencia:** Solo en memoria (se pierde al reiniciar)  

### **Logs Clave:**
- `🎮 Notificación enviada: X está jugando Y`
- `⏳ Sesión de juego en gracia: X - Y (última actividad hace Zs)`
- `⚠️ Sesión en gracia demasiado tiempo (Zs): Finalizando X - Y` (NUEVO)
- `💾 Tiempo guardado: X jugó Y por Z min`

---

## 🔊 VOICE SESSIONS

### **Flujo Completo:**

```
1. Usuario entra a canal
   ↓
2. on_voice_state_update detecta
   ↓
3. VoiceSessionManager.handle_start()
   - Crear VoiceSession
   - Iniciar verification_task (3s)
   ↓
4. Después de 3s:
   - Si aún está en voice → Confirmar
   - Enviar notificación (cooldown: 20 min)
   - save_voice_notification() para recovery
   ↓
5. Usuario sale de canal:
   ↓
6. VoiceSessionManager.handle_end()
   ├─ Verificar grace period (15 min)
   ├─ Calcular duración
   ├─ Si >= 1 min → save_voice_time()
   ├─ Verificar si hubo entrada + cooldown pasó → Notificar salida
   ├─ remove_voice_notification()
   └─ Limpiar sesión
```

### **Características Actuales:**

✅ **Grace Period:** 15 minutos unificado  
✅ **Cooldown:** 20 minutos (unificado para entrada/salida/movimiento)  
✅ **Verificación:** 3 segundos antes de confirmar  
✅ **Persistencia:** `pending_notifications.json` (recupera en reinicio)  
✅ **Recovery:** Restaura sesiones después de reinicio  

### **Logs Clave:**
- `🔊 Notificación enviada: X en Y`
- `♻️ Sesión de voz restaurada: X en Y`
- `💾 Tiempo guardado: X estuvo en Y por Z min`
- `🔇 Notificación de salida enviada: X de Y`

---

## 🎉 PARTY SESSIONS (Soft Close)

### **Flujo Completo:**

```
1. Discord reporta actividades de múltiples usuarios
   ↓
2. on_presence_update detecta
   ↓
3. PartySessionManager agrupa por juego
   ↓
4. Si >= 2 usuarios en mismo juego:
   ↓
5. PartySessionManager.handle_start()
   - Si NO existe sesión → Crear PartySession (state: active)
   - Si existe y state = active → _update_activity()
   - Si existe y state = inactive → Verificar reactivation_window
     ├─ Si dentro de ventana (30 min) → Reactivar (state: active)
     └─ Si fuera de ventana → Crear nueva party
   - Iniciar verification_task (10s)
   ↓
6. Después de 10s:
   - Si aún están >= 2 jugadores → Confirmar
   - Enviar notificación "Party formada" (cooldown: 20 min)
   - Actualizar stats de party
   ↓
7. Usuarios juegan partida, salen a lobby:
   ↓
8. Discord reporta < 2 usuarios en juego
   ↓
9. PartySessionManager.handle_end()
   ├─ Verificar grace period (15 min)
   │  └─ Si < 15 min → state = 'inactive', inactive_since = now
   ├─ Si >= 15 min sin actividad:
   │  └─ Si confirmada → _finalize_party_in_stats()
   │  └─ state = 'closed', eliminar de active_sessions
   └─ _cleanup_expired_inactive_sessions() (cada handle_start)
```

### **Estados de Party:**

```
active → Jugadores activos en el juego
   ↓
inactive → En lobby/búsqueda (< 30 min)
   ↓ (si vuelven a jugar < 30 min)
active → Reactivada (sin nueva notificación)
   ↓ (si pasan > 30 min)
closed → Finalizada definitivamente
```

### **Características Actuales:**

✅ **Grace Period:** 15 minutos unificado  
✅ **Cooldown:** 20 minutos (por party formada)  
✅ **Cooldown Join:** Individual por jugador que se une  
✅ **Verificación:** 10 segundos antes de confirmar  
✅ **Reactivation Window:** 30 minutos  
✅ **Soft Close:** Permite lobbies sin spam  
✅ **Stats:** Guarda en `stats.json` history  
❌ **Persistencia:** Solo en memoria (se pierde al reiniciar)  

### **Logs Clave:**
- `🎮 Nueva party iniciada: X con Y jugadores`
- `@here 🎮 Party formada en X! Jugadores: A, B, C`
- `⏸️ Party inactiva: X (ventana: 30 min)`
- `🔄 Party reactivada: X (sin nueva notificación)`
- `🎮 Party finalizada: X (duración: Y min)`

---

## 🏥 HEALTH CHECK

### **Sistema Actual:**

```
SessionHealthCheck (health_check.py)
    ├─ Startup Recovery:
    │  └─ initial_recovery() (solo voice)
    │     └─ Lee pending_notifications.json
    │     └─ Restaura sesiones de voice activas
    │
    └─ Periodic Check:
       └─ @tasks.loop(minutes=30)
       └─ periodic_check()
          ├─ _check_game_sessions()
          │  └─ Finaliza si last_activity > grace_period
          └─ _check_party_sessions()
             └─ Finaliza si last_activity > grace_period
```

### **Qué Recupera:**

✅ **Voice:** Restaura sesiones después de reinicio  
❌ **Games:** Se pierden al reiniciar (trade-off aceptado)  
❌ **Parties:** Se pierden al reiniciar (trade-off aceptado)  

### **Qué Detecta:**

✅ **Sesiones colgadas:** Discord dejó de reportar  
✅ **Sesiones expiradas:** Grace period vencido  
✅ **Parties inactivas:** Reactivation window vencido  

### **Logs Clave:**
- `🏥 Health check iniciado (games: X, parties: Y)`
- `✅ Health check: Todo OK`
- `✅ Health check: X sesiones finalizadas`

---

## ⏱️ COOLDOWNS (Sistema Unificado)

### **Configuración Actual:**

| Tipo | Duración | Resetea |
|------|----------|---------|
| **Voice (entrada)** | 20 min | ✅ En cada intento |
| **Voice (salida/movimiento)** | 20 min | ✅ Unificado |
| **Games (entrada)** | 30 min | ✅ En cada intento |
| **Parties (formada)** | 20 min | ✅ En cada intento |
| **Parties (join)** | 20 min | ✅ Individual por jugador |
| **Conexiones diarias** | 10 min | ✅ En cada intento |

### **Comportamiento "Resetea en cada intento":**

```python
# Antes (contador desde última notificación exitosa):
Usuario intenta → Cooldown activo → NO notifica → NO actualiza timestamp
Usuario intenta → Cooldown activo → NO notifica → NO actualiza timestamp
Usuario intenta → Cooldown pasó → SÍ notifica → Actualiza timestamp

# Ahora (contador desde último intento):
Usuario intenta → Cooldown activo → NO notifica → SÍ actualiza timestamp ← NUEVO
Usuario intenta → Cooldown activo → NO notifica → SÍ actualiza timestamp ← NUEVO
Usuario intenta → Cooldown pasó → SÍ notifica → Actualiza timestamp
```

**Resultado:** Previene spam incluso con reconexiones rápidas.

---

## 🎯 GRACE PERIOD (Unificado - 15 minutos)

### **¿Qué Es?**

Un "buffer" que previene finalización prematura de sesiones debido a:
- Lags de Discord
- Reconexiones rápidas
- Cambios de estado temporales

### **Aplicado a:**

✅ **Voice:** 15 min (si Discord no reporta, espera 15 min antes de finalizar)  
✅ **Games:** 15 min (igual)  
✅ **Parties:** 15 min (igual)  

### **Timeout en Gracia (NUEVO - Games/Parties):**

- Si una sesión **NO confirmada** (< 10s) lleva **> 5 min en gracia**
- Se **fuerza la finalización** (Discord dejó de enviar eventos)
- **NO se guarda tiempo** (era < 10s)

---

## 📦 PERSISTENCIA

### **¿Qué se guarda en disco?**

| Archivo | Qué contiene | Uso |
|---------|--------------|-----|
| **stats.json** | Todo el histórico | Analytics, wrapped, rankings |
| **pending_notifications.json** | Sesiones de voice activas | Recovery después de reinicio |
| **config.json** | Configuración del bot | Cooldowns, settings |

### **¿Qué se guarda en memoria?**

| Manager | Qué contiene | Persiste reinicio |
|---------|--------------|-------------------|
| **VoiceSessionManager** | active_sessions (dict) | ✅ SÍ (via pending_notifications.json) |
| **GameSessionManager** | active_sessions (dict) | ❌ NO |
| **PartySessionManager** | active_sessions (dict) | ❌ NO |

---

## 🎁 WRAPPED 2025

### **Sistema Nuevo:**

```
stats/commands/wrapped.py
    └─ !wrapped [usuario] [año]
       ├─ Gaming: horas, top juego, racha, días
       ├─ Voice: sesiones, promedio, maratones
       ├─ Parties: total, juego social, squad
       ├─ Social: mensajes, reacciones, emoji
       └─ Rankings: posición en gaming/social/parties

cogs/wrapped_event.py
    └─ Cron automático para 31/12/2025 a las 12:00
       └─ Envía wrapped a todos los usuarios con datos
       └─ Se ejecuta SOLO UNA VEZ
```

---

## 🐛 FIXES RECIENTES

### **Fix 1: Sesiones Colgadas en Gracia (01/01/2026)**

**Problema:** Sesiones < 10s entran en gracia pero quedan colgadas sin finalizar  
**Solución:** Timeout de 5 min para sesiones no confirmadas en gracia  
**Archivos:** `core/game_session.py`  

---

## 📊 STATS GUARDADOS

### **Estructura `stats.json`:**

```json
{
  "users": {
    "user_id": {
      "username": "Pino",
      "games": {
        "League of Legends": {
          "count": 50,
          "total_minutes": 3000,
          "daily_minutes": {
            "2025-12-31": 120,
            "2026-01-01": 90
          }
        }
      },
      "voice": {
        "count": 25,
        "total_minutes": 1500,
        "daily_minutes": { ... }
      },
      "messages": { "count": 500 },
      "reactions": { "total": 150 },
      "connections": { "count": 10 }
    }
  },
  "parties": {
    "history": [
      {
        "game": "League of Legends",
        "start": "2025-12-31T20:00:00",
        "end": "2025-12-31T22:00:00",
        "duration": 120,
        "players": ["user_id_1", "user_id_2"]
      }
    ],
    "games": {
      "League of Legends": {
        "max_players_ever": 5,
        "total_parties": 20,
        "total_duration_minutes": 500
      }
    }
  },
  "cooldowns": {
    "user_id:voice": "2025-12-31T23:00:00",
    "user_id:game:League of Legends": "2025-12-31T22:00:00"
  }
}
```

---

## 🚀 RESUMEN EJECUTIVO

### **Lo que SÍ funciona perfectamente:**

✅ Voice sessions con recovery  
✅ Game sessions con verificación multicapa  
✅ Party sessions con Soft Close  
✅ Grace period unificado (15 min)  
✅ Cooldowns que resetean en cada intento  
✅ Health check periódico (30 min)  
✅ Wrapped 2025 automático  
✅ Timeout para sesiones colgadas (5 min)  

### **Trade-offs aceptados:**

⚖️ Games/Parties se pierden al reiniciar (~1% de sesiones)  
⚖️ Reinicios durante grace period pueden perder tracking  
⚖️ Health check tiene delay de hasta 30 min  

### **Lo que está deployeado HOY:**

🎁 **Wrapped 2025:** Se ejecutará a las 12:00 (1 hora)  
🐛 **Fix sesiones colgadas:** Activo en producción  
📊 **Logs mejorados:** Debugging completo  

---

**Estado:** ✅ Sistema robusto, probado en producción, listo para 2026

