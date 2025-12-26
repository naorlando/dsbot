# 🔄 Redeploy en Railway (Si es Necesario)

## ¿Necesito hacer redeploy?

**Generalmente NO** - Railway debería reconectar automáticamente cuando habilitas los Privileged Intents en Discord Developer Portal.

**PERO** si después de 1-2 minutos el bot sigue sin conectarse, puedes hacer un redeploy manual.

## 🔄 Cómo hacer Redeploy Manual

### Opción 1: Desde la Interfaz Web (Recomendado)

1. Ve a tu proyecto en Railway: https://railway.app/dashboard
2. Selecciona tu proyecto "dsbot"
3. Haz clic en tu servicio
4. Ve a la pestaña **"Deployments"**
5. Haz clic en los **3 puntos** (⋯) del último deployment
6. Selecciona **"Redeploy"**
7. Espera 1-2 minutos

### Opción 2: Hacer un cambio pequeño y push

Si prefieres, puedes hacer un cambio pequeño en el código y hacer push:

```bash
cd /Users/naorlando/Documents/my/dsbot
# Hacer un cambio pequeño (agregar un comentario, etc.)
git commit --allow-empty -m "Trigger redeploy"
git push
```

Railway detectará el cambio y hará un nuevo deploy automáticamente.

## ✅ Verificar que Funcionó

Después del redeploy:

1. Ve a **"Logs"** en Railway
2. Deberías ver:
   ```
   BotName#1234 se ha conectado a Discord!
   Bot ID: 123456789012345678
   ```
3. En Discord, verifica que el bot esté **en línea** (punto verde)

## 🆘 Si Sigue Sin Funcionar

1. **Verifica los Intents:**
   - Ve a https://discord.com/developers/applications
   - Bot → Privileged Gateway Intents
   - ✅ PRESENCE INTENT debe estar habilitado
   - ✅ SERVER MEMBERS INTENT debe estar habilitado

2. **Verifica la variable de entorno:**
   - Railway → Variables
   - Debe existir: `DISCORD_BOT_TOKEN`
   - Debe tener el valor correcto

3. **Revisa los logs:**
   - Railway → Logs
   - Busca mensajes de error específicos

---

**En la mayoría de los casos, solo necesitas habilitar los Intents y esperar 1-2 minutos. Railway reconectará automáticamente.** ⏱️

