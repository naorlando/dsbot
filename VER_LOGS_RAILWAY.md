# 📊 Cómo Ver los Logs del Bot en Railway

## 🔍 Dónde están los Logs

### Paso 1: Acceder a Railway
1. Ve a **https://railway.app/dashboard**
2. Inicia sesión con tu cuenta de GitHub

### Paso 2: Abrir tu Proyecto
1. Haz clic en tu proyecto **"dsbot"**

### Paso 3: Ver los Logs
1. Haz clic en tu **servicio** (el que está corriendo)
2. En el menú lateral izquierdo, haz clic en **"Logs"** o **"Deploy Logs"**
3. Ahí verás todos los mensajes del bot en tiempo real

## 📝 Qué Verás en los Logs

### Cuando el bot se conecta:
```
BotName#1234 se ha conectado a Discord!
Bot ID: 123456789012345678
Canal de notificaciones: #nombre-del-canal
```

### Cuando detecta un juego (con el nuevo logging):
```
🔍 DEBUG: on_presence_update - Usuario: TuNombre, Bot: False
   Before activity: None (type: None)
   After activity: Activity(name='Nombre del Juego', type=ActivityType.playing)
   ✅ Actividad detectada: playing - Nombre del Juego
   ✅ Tipo de actividad está en la lista permitida
🎮 Detectado: TuNombre está jugando Nombre del Juego
✅ Notificación enviada: 🎮 **TuNombre** está jugando **Nombre del Juego**...
```

### Si no detecta el juego, verás por qué:
- `⚠️  Notificaciones de juegos DESACTIVADAS` - Las notificaciones están desactivadas
- `⚠️  Ignorando porque es un bot` - Está ignorando bots
- `⚠️  Actividad no cambió (mismo juego)` - Ya estaba jugando ese juego
- `⚠️  Tipo de actividad NO está en la lista permitida` - El tipo de actividad no está configurado
- `⚠️  No hay canal configurado` - No hay canal de notificaciones configurado

## 🔄 Actualizar los Logs

Los logs se actualizan automáticamente en tiempo real. Si no ves nada nuevo:

1. **Refresca la página** (F5 o Cmd+R)
2. **Espera unos segundos** - Los logs pueden tardar un poco en aparecer
3. **Verifica que el bot esté corriendo** - Debe decir "Active" en el estado del servicio

## 🆘 Si No Ves Nada en los Logs

1. **Verifica que el servicio esté activo:**
   - Debe decir "Active" (verde) en la pestaña "Deployments"

2. **Verifica que el bot esté conectado:**
   - En Discord, el bot debe tener un punto verde (en línea)

3. **Haz un redeploy:**
   - Ve a "Deployments" → 3 puntos → "Redeploy"

4. **Verifica la configuración:**
   - Variables → `DISCORD_BOT_TOKEN` debe estar configurado
   - El bot debe tener los Intents habilitados en Discord Developer Portal

## 📱 Logs en Móvil

Railway también tiene una app móvil donde puedes ver los logs:
- Descarga la app de Railway
- Inicia sesión
- Selecciona tu proyecto y servicio
- Ve a "Logs"

---

**Con el nuevo logging detallado, podrás ver exactamente qué está pasando cuando alguien empieza a jugar.** 🎮

