# 🔴 URGENTE: Habilitar Privileged Intents

## ❌ Error Actual
```
PrivilegedIntentsRequired: Shard ID None is requesting privileged intents that have not been explicitly enabled in the developer portal.
```

**Esto significa que los Intents NO están habilitados en Discord Developer Portal.**

## ✅ SOLUCIÓN PASO A PASO

### Paso 1: Ir a Discord Developer Portal

1. Ve a: **https://discord.com/developers/applications**
2. **Inicia sesión** con tu cuenta de Discord
3. Selecciona tu aplicación (la que creaste para el bot)

### Paso 2: Ir a la Sección Bot

1. En el menú lateral izquierdo, haz clic en **"Bot"**
2. Desplázate hacia abajo hasta encontrar la sección **"Privileged Gateway Intents"**

### Paso 3: Habilitar los Intents (OBLIGATORIO)

En la sección **"Privileged Gateway Intents"**, verás dos opciones:

1. ✅ **PRESENCE INTENT**
   - **Márcalo/Actívalo** (debe estar en verde/activado)
   - Necesario para detectar cuando alguien juega un juego

2. ✅ **SERVER MEMBERS INTENT**
   - **Márcalo/Actívalo** (debe estar en verde/activado)
   - Necesario para detectar miembros y sus actividades

### Paso 4: Guardar

- Los cambios se guardan **automáticamente** cuando activas los switches
- No necesitas hacer clic en ningún botón "Save"

### Paso 5: Esperar y Verificar

1. Espera **30-60 segundos** después de habilitar los intents
2. Ve a Railway y revisa los **Logs**
3. Deberías ver:
   ```
   BotName#1234 se ha conectado a Discord!
   Bot ID: 123456789012345678
   ```

## 📸 Ubicación Visual

```
Discord Developer Portal
├── Applications
│   └── Tu Aplicación
│       ├── General Information
│       ├── Bot ← AQUÍ
│       │   ├── Token
│       │   ├── Username
│       │   ├── ...
│       │   └── Privileged Gateway Intents ← AQUÍ
│       │       ├── ✅ PRESENCE INTENT
│       │       └── ✅ SERVER MEMBERS INTENT
│       ├── OAuth2
│       └── ...
```

## ⚠️ IMPORTANTE

- **AMBOS intents deben estar ACTIVADOS** (verde/on)
- Si solo activas uno, el bot seguirá fallando
- Los cambios se guardan automáticamente
- Puede tardar unos segundos en aplicarse

## 🔍 Verificar que Están Habilitados

Después de activarlos, deberías ver:

```
Privileged Gateway Intents
├── ✅ PRESENCE INTENT (ON/Verde)
└── ✅ SERVER MEMBERS INTENT (ON/Verde)
```

## 🆘 Si Sigue Sin Funcionar

1. **Verifica que ambos intents estén activados:**
   - Ve a Bot → Privileged Gateway Intents
   - Ambos deben estar en verde/activados

2. **Espera 1-2 minutos** después de activarlos

3. **Haz un redeploy en Railway:**
   - Deployments → 3 puntos → Redeploy

4. **Verifica el token:**
   - Railway → Variables
   - Debe existir `DISCORD_BOT_TOKEN`
   - Debe tener el valor correcto

---

**⚠️ SIN ESTOS INTENTS HABILITADOS, EL BOT NO FUNCIONARÁ. ES OBLIGATORIO HABILITARLOS.** 🔴

