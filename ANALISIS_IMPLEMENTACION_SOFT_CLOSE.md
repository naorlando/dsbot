# 📋 Análisis de Implementación: Soft Close para Parties

## 🎯 Objetivo

Implementar Opción A (Soft Close) para eliminar spam de notificaciones en lobbies largos.

---

## 📁 Archivos a Modificar

### 1. `core/party_session.py` ⭐ (Principal)

#### **Clase `PartySession`:**

**Agregar atributos:**
```python
class PartySession(BaseSession):
    def __init__(self, game_name: str, player_ids: Set[str], player_names: List[str], guild_id: int):
        super().__init__(game_name, game_name, guild_id)
        # ... código existente ...
        
        # ✨ NUEVO: Estados para soft close
        self.state = 'active'  # active, inactive, closed
        self.inactive_since = None  # Timestamp cuando pasó a inactive
        self.reactivation_window = 30 * 60  # 30 minutos (de config)
```

#### **Clase `PartySessionManager`:**

**Modificar `__init__`:**
```python
def __init__(self, bot):
    super().__init__(bot, min_duration_seconds=10)
    self._ensure_party_structure()
    # ✨ NUEVO: Leer ventana de reactivación del config
    # Se hará en handle_start para tener acceso a config
```

**Modificar `handle_start`:** (Línea 50)

**Estado actual:**
```python
# Caso 1: No hay sesión activa → crear nueva party
if game_name not in self.active_sessions:
    session = PartySession(...)
    self.active_sessions[game_name] = session
    # ... iniciar verificación ...
    logger.info(f'🎮 Nueva party iniciada: {game_name}')

# Caso 2: Sesión existente → actualizar jugadores
else:
    session = self.active_sessions[game_name]
    # ... actualizar jugadores ...
```

**Cambios necesarios:**
```python
# ✨ NUEVO Caso 1: No hay sesión
if game_name not in self.active_sessions:
    # Lógica existente (crear nueva)
    ...

# ✨ NUEVO Caso 2: Sesión INACTIVA → REACTIVAR
elif self.active_sessions[game_name].state == 'inactive':
    session = self.active_sessions[game_name]
    
    # Reactivar sesión
    session.state = 'active'
    session.inactive_since = None
    self._update_activity(session)  # Actualizar timestamp
    
    # Actualizar jugadores
    session.player_ids = current_player_ids.copy()
    session.player_names = current_player_names.copy()
    if len(current_player_ids) > session.max_players:
        session.max_players = len(current_player_ids)
    
    # Actualizar en stats si ya estaba confirmada
    if session.is_confirmed:
        self._update_active_party_in_stats(game_name, session)
    
    logger.info(f'🔄 Party reactivada: {game_name} con {len(current_players)} jugadores')
    # ❌ NO notificar (es la misma sesión)

# ✨ MODIFICADO Caso 3: Sesión ACTIVA → actualizar (lógica existente)
else:
    session = self.active_sessions[game_name]
    # ... lógica existente de actualización ...
```

**Modificar `handle_end`:** (Línea 139)

**Estado actual:**
```python
async def handle_end(self, game_name: str, config: dict):
    if game_name not in self.active_sessions:
        return
    
    session = self.active_sessions[game_name]
    
    # Buffer de gracia
    if self._is_in_grace_period(session):
        logger.info(f'⏳ Party en gracia: {game_name}')
        return
    
    # Cancelar tarea de verificación
    # Borrar mensaje si no confirmada
    # Finalizar en stats si confirmada
    
    # Eliminar sesión activa
    del self.active_sessions[game_name]
```

**Cambios necesarios:**
```python
async def handle_end(self, game_name: str, config: dict):
    if game_name not in self.active_sessions:
        return
    
    session = self.active_sessions[game_name]
    
    # ✅ MANTENER: Buffer de gracia (15 min)
    if self._is_in_grace_period(session):
        logger.info(f'⏳ Party en gracia: {game_name}')
        return
    
    # ✨ NUEVO: En vez de cerrar, marcar como inactive
    if session.state == 'active':
        session.state = 'inactive'
        session.inactive_since = datetime.now()
        
        # Leer ventana de config
        party_config = config.get('party_detection', {})
        reactivation_minutes = party_config.get('reactivation_window_minutes', 30)
        session.reactivation_window = reactivation_minutes * 60
        
        logger.info(f'⏸️  Party inactiva: {game_name} (ventana: {reactivation_minutes} min)')
        return  # ❌ NO finalizar todavía
    
    # ✨ NUEVO: Si ya estaba inactive, verificar ventana
    if session.state == 'inactive':
        time_inactive = (datetime.now() - session.inactive_since).total_seconds()
        if time_inactive < session.reactivation_window:
            logger.info(f'⏳ Party en ventana de reactivación: {game_name} ({int(time_inactive/60)} min)')
            return  # Todavía puede reactivarse
        
        # ✨ NUEVO: Ventana expirada → cerrar definitivamente
        logger.info(f'⌛ Ventana expirada: {game_name}, cerrando definitivamente')
    
    # ✅ MANTENER: Lógica existente de finalización
    # (Cancelar tarea, borrar mensaje, finalizar en stats, eliminar de memoria)
    session.state = 'closed'
    
    # ... resto del código existente ...
```

**Agregar nuevo método:**
```python
def _cleanup_expired_inactive_sessions(self):
    """
    Limpia sesiones inactivas cuya ventana de reactivación expiró.
    Se llama periódicamente o en cada handle_start/handle_end.
    """
    to_remove = []
    for game_name, session in self.active_sessions.items():
        if session.state == 'inactive' and session.inactive_since:
            time_inactive = (datetime.now() - session.inactive_since).total_seconds()
            if time_inactive >= session.reactivation_window:
                to_remove.append(game_name)
    
    for game_name in to_remove:
        session = self.active_sessions[game_name]
        logger.info(f'🧹 Limpiando party inactiva expirada: {game_name}')
        
        # Finalizar si estaba confirmada
        if session.is_confirmed:
            self._finalize_party_in_stats(game_name, session)
        
        # Eliminar de memoria
        del self.active_sessions[game_name]
```

**Llamar limpieza en lugares estratégicos:**
```python
# En handle_start (al inicio):
async def handle_start(self, ...):
    # Limpiar expiradas antes de procesar
    self._cleanup_expired_inactive_sessions()
    
    # ... resto del código ...

# También podría llamarse en handle_end, pero con handle_start es suficiente
```

---

### 2. `config.json`

**Agregar nuevo campo:**
```json
{
  "party_detection": {
    "enabled": true,
    "min_players": 2,
    "notify_on_formed": true,
    "notify_on_join": true,
    "cooldown_minutes": 60,
    "reactivation_window_minutes": 30,  // ✨ NUEVO
    "use_here_mention": true,
    "blacklisted_games": [...]
  }
}
```

---

### 3. `cogs/events.py`

**Verificar:** `on_presence_update` llama a `party_manager.handle_start()`

**NO requiere cambios** - Solo pasa los parámetros, la lógica está en `PartySessionManager`.

---

### 4. Crear `test_party_soft_close.py`

**Tests necesarios:**

1. ✅ `test_lobby_corto_reactivacion` - Lobby < 30 min, reactivación exitosa
2. ✅ `test_lobby_largo_nueva_party` - Lobby > 30 min, nueva party sin spam
3. ✅ `test_usuario_sale_vuelve` - Usuario sale temporalmente
4. ✅ `test_todos_salen_ventana_activa` - < 2 jugadores, reactivación en ventana
5. ✅ `test_todos_salen_ventana_expira` - < 2 jugadores, ventana expira
6. ✅ `test_multiples_lobbies` - Varios lobbies en misma sesión
7. ✅ `test_limpieza_sesiones_expiradas` - Cleanup funciona correctamente
8. ✅ `test_estado_transitions` - Transiciones active → inactive → closed
9. ✅ `test_reactivation_window_configurable` - Lee del config correctamente
10. ✅ `test_cooldown_previene_spam` - Cooldown 60 min funciona

---

## 🔍 Lógica Vieja a Verificar/Eliminar

### ✅ NO eliminar:

1. **Buffer de gracia (15 min):** Sigue siendo útil para lag de Discord
2. **Cooldown de 60 min:** Previene spam en caso de nueva party
3. **Verificación de 3s + 10s:** Confirmación de party sigue igual
4. **Tracking en stats.json:** No cambia, solo cuándo se finaliza
5. **Notificaciones de join:** Siguen funcionando igual

### ⚠️ Verificar que no haya conflictos:

1. **`_is_in_grace_period()`:** Debe ejecutarse ANTES de marcar inactive
2. **`_finalize_party_in_stats()`:** Solo se llama cuando state = 'closed'
3. **`_update_active_party_in_stats()`:** Se llama en reactivación si ya confirmada

---

## 🧪 Plan de Testing

### Fase 1: Tests Unitarios
```bash
python test_party_soft_close.py
```

### Fase 2: Tests de Integración
```bash
pytest test_bot.py -k party
```

### Fase 3: Tests Manuales (Importante)
1. Crear party con 2+ jugadores
2. Entrar en lobby por 5 min → Verificar reactivación
3. Entrar en lobby por 35 min → Verificar nueva party (sin spam)
4. Usuario sale/vuelve en < 30 min → Verificar no spam
5. Bot restart durante party → Verificar cooldown previene spam

---

## 📊 Checklist de Implementación

### PartySession:
- [ ] Agregar atributo `state`
- [ ] Agregar atributo `inactive_since`
- [ ] Agregar atributo `reactivation_window`

### PartySessionManager:
- [ ] Modificar `handle_start` - Caso reactivación
- [ ] Modificar `handle_end` - Marcar inactive
- [ ] Modificar `handle_end` - Verificar ventana
- [ ] Agregar `_cleanup_expired_inactive_sessions()`
- [ ] Llamar cleanup en `handle_start`
- [ ] Agregar logs informativos

### Config:
- [ ] Agregar `reactivation_window_minutes: 30`

### Tests:
- [ ] Crear `test_party_soft_close.py`
- [ ] 10 tests de casos de uso
- [ ] Tests de edge cases
- [ ] Tests de configuración

### Verificación:
- [ ] NO hay lógica duplicada
- [ ] NO hay conflictos con buffer de gracia
- [ ] Logs son claros y útiles
- [ ] Estados bien definidos (active/inactive/closed)
- [ ] Cleanup funciona correctamente

### Documentación:
- [ ] Agregar docstrings a nuevos métodos
- [ ] Comentarios en código complejo
- [ ] Actualizar PROPUESTA_PARTY_REDESIGN.md con status

---

## ⚡ Orden de Implementación

1. **Modificar `PartySession.__init__`** (agregar atributos)
2. **Agregar `_cleanup_expired_inactive_sessions()`**
3. **Modificar `handle_end`** (inactive logic)
4. **Modificar `handle_start`** (reactivation logic)
5. **Actualizar `config.json`**
6. **Crear tests**
7. **Ejecutar tests**
8. **Verificar integración**
9. **Test manual** (si es posible)

---

## 🎯 Resultado Esperado

**Antes:**
```
17:00 - Party → Notifica ✅
17:15 - Lobby 20 min
17:35 - Buffer expira → Party cerrada
17:36 - Salen de lobby → Nueva party → Notifica ❌ SPAM
```

**Después:**
```
17:00 - Party → state=active → Notifica ✅
17:15 - Lobby 20 min → state=inactive
17:36 - Salen de lobby → state=active (reactivada) → ❌ NO notifica ✅
18:00 - Terminan → state=inactive → ... → closed
```

**Win:** ✅ 1 sola notificación, sesión continua, tracking correcto

---

## 🚨 Riesgos y Mitigaciones

### Riesgo 1: Sesiones inactivas acumulándose en memoria
**Mitigación:** `_cleanup_expired_inactive_sessions()` limpia periódicamente

### Riesgo 2: Conflicto entre grace period (15 min) y inactive window (30 min)
**Mitigación:** Grace period se verifica PRIMERO, luego inactive logic

### Riesgo 3: Bot restart pierde sesiones inactivas
**Mitigación:** Cooldown de 60 min previene spam al recrear

### Riesgo 4: Configuración incorrecta de ventana
**Mitigación:** Valor por defecto de 30 min si falta en config

---

**Listo para implementar! ✅**

