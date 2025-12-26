# 🚀 Deploy Ahora - Instrucciones Rápidas

## Ejecuta el Script de Deploy

```bash
cd /Users/naorlando/Documents/my/dsbot
./deploy_completo.sh
```

El script te guiará paso a paso:
1. ✅ Configurará git localmente
2. ✅ Verificará que .env esté protegido
3. ✅ Hará commit de los archivos
4. ✅ Creará el repositorio en GitHub (o te guiará para hacerlo manualmente)
5. ✅ Subirá el código

---

## Después del Script: Deploy en Railway

Una vez que el código esté en GitHub:

### Paso 1: Railway
1. Ve a https://railway.app
2. Haz clic en **"Login"** → Usa GitHub
3. Haz clic en **"New Project"**
4. Selecciona **"Deploy from GitHub repo"**
5. Busca y selecciona: **naorlando/dsbot**
6. Railway detectará automáticamente que es Python

### Paso 2: Configurar Variables
1. En tu proyecto de Railway, haz clic en el servicio
2. Ve a la pestaña **"Variables"**
3. Haz clic en **"New Variable"**
4. Agrega:
   - **Name:** `DISCORD_BOT_TOKEN`
   - **Value:** `tu_token_de_discord_aqui`
5. Haz clic en **"Add"**

### Paso 3: Verificar Deploy
1. Railway comenzará a construir y desplegar automáticamente
2. Espera 1-2 minutos
3. Ve a la pestaña **"Deployments"** para ver el progreso
4. Cuando veas "Active" en verde, el bot está desplegado

### Paso 4: Verificar en Discord
1. Abre Discord
2. Ve a tu servidor
3. Verifica que el bot esté **en línea** (punto verde)
4. Escribe `!test` en un canal
5. Si responde, ¡todo funciona!

---

## Alternativa: Render (100% Gratis)

Si prefieres Render:

1. Ve a https://render.com
2. Login con GitHub
3. **New** → **Web Service**
4. Conecta: **naorlando/dsbot**
5. Configura:
   - **Name:** `discord-bot`
   - **Region:** Elige el más cercano
   - **Branch:** `main`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
6. En **Environment Variables**, agrega:
   - **Key:** `DISCORD_BOT_TOKEN`
   - **Value:** `tu_token_de_discord_aqui`
7. Haz clic en **Create Web Service**
8. Espera 2-3 minutos

---

## ✅ Checklist Final

- [ ] Código subido a GitHub
- [ ] Repositorio creado: naorlando/dsbot
- [ ] Deployado en Railway o Render
- [ ] Variable DISCORD_BOT_TOKEN configurada
- [ ] Bot en línea en Discord
- [ ] Comando `!test` funciona

---

**¡Ejecuta `./deploy_completo.sh` para empezar!** 🚀

