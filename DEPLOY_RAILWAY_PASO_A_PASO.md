# 🚀 Deploy en Railway - Paso a Paso

## ✅ Código ya está en GitHub
- Repositorio: https://github.com/naorlando/dsbot
- Todo listo para deploy

## 📋 Pasos para Deploy en Railway

### Paso 1: Crear cuenta y proyecto

1. Ve a **https://railway.app**
2. Haz clic en **"Login"** o **"Start a New Project"**
3. Selecciona **"Login with GitHub"**
4. Autoriza Railway para acceder a tus repositorios

### Paso 2: Crear nuevo proyecto

1. En el dashboard de Railway, haz clic en **"New Project"**
2. Selecciona **"Deploy from GitHub repo"**
3. Si es la primera vez, autoriza Railway para acceder a GitHub
4. Busca y selecciona: **naorlando/dsbot**
5. Haz clic en **"Deploy Now"**

### Paso 3: Configurar variables de entorno

1. Una vez que Railway comience a construir, haz clic en tu servicio (debería llamarse "dsbot" o similar)
2. Ve a la pestaña **"Variables"** (en el menú lateral)
3. Haz clic en **"New Variable"** o **"Raw Editor"**
4. Agrega esta variable:
   - **Name:** `DISCORD_BOT_TOKEN`
   - **Value:** `tu_token_de_discord_aqui`
5. Haz clic en **"Add"** o guarda

**⚠️ IMPORTANTE:** Railway reiniciará automáticamente el servicio cuando agregues la variable.

### Paso 4: Verificar el deploy

1. Ve a la pestaña **"Deployments"** para ver el progreso
2. Espera a que el estado sea **"Active"** (verde)
3. Ve a la pestaña **"Logs"** para ver los mensajes del bot
4. Deberías ver algo como:
   ```
   BotName#1234 se ha conectado a Discord!
   Bot ID: 123456789012345678
   ```

### Paso 5: Verificar en Discord

1. Abre Discord
2. Ve a tu servidor
3. Verifica que el bot esté **en línea** (punto verde junto al nombre)
4. Escribe `!test` en cualquier canal donde el bot tenga permisos
5. Si responde, ¡todo funciona perfectamente!

## 🔍 Troubleshooting

### El bot no se conecta
- Verifica en **Logs** de Railway si hay errores
- Verifica que la variable `DISCORD_BOT_TOKEN` esté configurada correctamente
- Verifica que los **Intents** estén habilitados en Discord Developer Portal:
  - Presence Intent ✅
  - Server Members Intent ✅

### Error: "Module not found"
- Railway debería instalar automáticamente las dependencias
- Si hay problemas, verifica que `requirements.txt` tenga todas las dependencias

### El bot se desconecta
- Revisa los logs en Railway
- Verifica que no hayas excedido las 500 horas/mes del plan gratuito

## 📊 Monitoreo

- **Logs:** Ve a la pestaña "Logs" para ver la salida del bot en tiempo real
- **Metrics:** Ve a "Metrics" para ver uso de CPU/memoria
- **Deployments:** Ve el historial de deployments

## ✅ Checklist Final

- [ ] Proyecto creado en Railway
- [ ] Repositorio conectado: naorlando/dsbot
- [ ] Variable `DISCORD_BOT_TOKEN` configurada
- [ ] Deploy completado (estado "Active")
- [ ] Bot en línea en Discord
- [ ] Comando `!test` funciona

---

**¡Tu bot estará funcionando 24/7 en Railway!** 🎉

