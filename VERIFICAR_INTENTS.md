# 🔴 VERIFICAR INTENTS - Guía Paso a Paso

## ❌ Error Actual
```
PrivilegedIntentsRequired: Shard ID None is requesting privileged intents that have not been explicitly enabled
```

## ✅ SOLUCIÓN DEFINITIVA

### Paso 1: Ir a Discord Developer Portal
1. Abre: **https://discord.com/developers/applications**
2. **Inicia sesión** con tu cuenta de Discord
3. Selecciona tu aplicación (la que creaste para el bot)

### Paso 2: Verificar Sección Bot
1. En el menú lateral izquierdo, haz clic en **"Bot"**
2. Desplázate hacia abajo hasta encontrar **"Privileged Gateway Intents"**

### Paso 3: VERIFICAR que Ambos Estén ACTIVADOS

Debes ver exactamente esto:

```
┌─────────────────────────────────────────┐
│ Privileged Gateway Intents              │
├─────────────────────────────────────────┤
│ ✅ PRESENCE INTENT          [ON/Verde]  │
│ ✅ SERVER MEMBERS INTENT    [ON/Verde]  │
│ ⚪ MESSAGE CONTENT INTENT   [OFF/Gris]  │
└─────────────────────────────────────────┘
```

**⚠️ CRÍTICO:**
- ✅ **PRESENCE INTENT** debe estar **VERDE/ON** (activado)
- ✅ **SERVER MEMBERS INTENT** debe estar **VERDE/ON** (activado)
- ⚪ **MESSAGE CONTENT INTENT** puede estar OFF (no es necesario para este bot)

### Paso 4: Si NO Están Activados

1. Haz clic en el **switch** de "PRESENCE INTENT" hasta que esté **VERDE/ON**
2. Haz clic en el **switch** de "SERVER MEMBERS INTENT" hasta que esté **VERDE/ON**
3. Los cambios se guardan **automáticamente** (no hay botón "Save")
4. Espera **30-60 segundos**

### Paso 5: Verificar en Railway

1. Ve a Railway → Logs
2. Deberías ver:
   ```
   BotName#1234 se ha conectado a Discord!
   Bot ID: 123456789012345678
   ```
3. Si aún ves el error, verifica:
   - ¿Ambos switches están VERDE/ON?
   - ¿Esperaste 30-60 segundos?
   - ¿Recargaste la página de Discord Developer Portal?

## 🔍 Troubleshooting

### "Los switches están activados pero sigue fallando"
1. **Recarga la página** de Discord Developer Portal
2. **Verifica nuevamente** que ambos estén activados
3. Espera **1-2 minutos** (puede tardar en propagarse)
4. Haz un **redeploy** en Railway:
   - Deployments → 3 puntos → Redeploy

### "No veo la sección Privileged Gateway Intents"
1. Asegúrate de estar en la sección **"Bot"** (no "OAuth2" u otra)
2. Desplázate hacia abajo (está al final de la página)
3. Si aún no la ves, tu bot puede estar en un servidor con 100+ miembros
   - En ese caso, necesitas verificación de Discord

### "Solo veo un intent activado"
- **AMBOS deben estar activados**
- Si solo uno está activado, el bot seguirá fallando
- Activa el que falta y espera 30-60 segundos

## 📸 Ubicación Visual

```
Discord Developer Portal
│
├── Applications
│   └── Tu Aplicación
│       │
│       ├── General Information
│       ├── Bot ← AQUÍ
│       │   │
│       │   ├── Token
│       │   ├── Username
│       │   ├── ...
│       │   │
│       │   └── Privileged Gateway Intents ← AQUÍ (al final)
│       │       │
│       │       ├── ✅ PRESENCE INTENT [ON]
│       │       ├── ✅ SERVER MEMBERS INTENT [ON]
│       │       └── ⚪ MESSAGE CONTENT INTENT [OFF]
│       │
│       ├── OAuth2
│       └── ...
```

## ✅ Checklist Final

Antes de verificar Railway, asegúrate de:

- [ ] Estás en https://discord.com/developers/applications
- [ ] Seleccionaste tu aplicación correcta
- [ ] Estás en la sección "Bot"
- [ ] PRESENCE INTENT está VERDE/ON
- [ ] SERVER MEMBERS INTENT está VERDE/ON
- [ ] Esperaste 30-60 segundos después de activarlos
- [ ] Recargaste la página para verificar

---

**Una vez que ambos intents estén VERDE/ON, el bot debería conectarse automáticamente en Railway.** 🚀

