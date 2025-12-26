# 🔧 Configurar Variables en Railway - SOLUCIÓN

## ❌ Error Actual
```
❌ ERROR: No se encontró DISCORD_BOT_TOKEN en las variables de entorno
```

## ✅ Solución: Configurar Variable en Railway

### Método 1: Desde la Interfaz Web (Recomendado)

1. **Ve a tu proyecto en Railway**
   - https://railway.app/dashboard
   - Selecciona tu proyecto "dsbot"

2. **Haz clic en tu servicio** (el que está corriendo)

3. **Ve a la pestaña "Variables"** (en el menú lateral izquierdo)

4. **Haz clic en "New Variable"** o en **"Raw Editor"**

5. **Agrega la variable:**
   ```
   DISCORD_BOT_TOKEN=tu_token_de_discord_aqui
   ```
   
   **O usando el formulario:**
   - **Name:** `DISCORD_BOT_TOKEN`
   - **Value:** `tu_token_de_discord_aqui`

6. **Haz clic en "Add"** o **"Save"**

7. **Railway reiniciará automáticamente** el servicio con la nueva variable

8. **Espera 30-60 segundos** y verifica los logs

### Método 2: Raw Editor (Más rápido)

1. Ve a **Variables** → **Raw Editor**
2. Pega esto:
   ```
   DISCORD_BOT_TOKEN=tu_token_de_discord_aqui
   ```
3. Haz clic en **"Save"**

## 🔍 Verificar que Funcionó

1. Ve a la pestaña **"Logs"**
2. Deberías ver:
   ```
   BotName#1234 se ha conectado a Discord!
   Bot ID: 123456789012345678
   ```
3. Si aún ves el error, verifica:
   - ✅ Que la variable se llama exactamente `DISCORD_BOT_TOKEN` (sin espacios)
   - ✅ Que el valor es correcto (el token completo)
   - ✅ Que guardaste los cambios
   - ✅ Que el servicio se reinició (debería hacerlo automáticamente)

## 📸 Ubicación en Railway

```
Railway Dashboard
└── Tu Proyecto (dsbot)
    └── Tu Servicio
        ├── Variables ← AQUÍ
        ├── Deployments
        ├── Logs
        └── Settings
```

## 🆘 Si Sigue Sin Funcionar

1. **Verifica el nombre de la variable:**
   - Debe ser exactamente: `DISCORD_BOT_TOKEN`
   - Sin espacios antes o después
   - Case-sensitive (mayúsculas/minúsculas importan)

2. **Verifica el valor:**
   - Debe ser el token completo
   - Sin comillas alrededor
   - Sin espacios al inicio o final

3. **Reinicia manualmente:**
   - Ve a "Deployments"
   - Haz clic en los 3 puntos del último deployment
   - Selecciona "Redeploy"

4. **Revisa los logs:**
   - Ve a "Logs"
   - Busca mensajes de error
   - Verifica que la variable esté siendo leída

---

**Una vez configurada la variable, el bot debería conectarse automáticamente a Discord!** 🚀

