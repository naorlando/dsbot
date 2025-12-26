# 🚀 Deploy Rápido - Bot de Discord Gratis

## ¿Qué está pasando ahora?

**El bot está corriendo LOCALMENTE en tu computadora:**
- Se conecta directamente a los servidores de Discord (vía WebSocket)
- NO necesita un servidor web propio
- Solo necesita estar "despierto" 24/7 para funcionar

**Problema:** Si apagas tu computadora, el bot se desconecta.

**Solución:** Deployarlo en un servicio gratuito que lo mantenga activo 24/7.

---

## 🎯 Opción 1: Railway.app (RECOMENDADO - Más fácil)

### Ventajas:
- ✅ 500 horas/mes GRATIS (suficiente para 24/7)
- ✅ Siempre activo
- ✅ Despliegue automático desde GitHub
- ✅ Muy fácil de usar

### Pasos:

#### 1. Crear repositorio en GitHub

```bash
cd /Users/naorlando/Documents/my/dsbot

# Configurar git (si no lo hiciste)
./config_git.sh

# Inicializar git y hacer commit
git init
git add .
git commit -m "Initial commit: Bot de Discord"

# Crear repositorio en GitHub (necesitas estar logueado)
gh repo create dsbot --public --source=. --remote=origin --push
```

**O manualmente:**
1. Ve a https://github.com/new
2. Crea repositorio: `dsbot`
3. NO marques "Initialize with README"
4. Luego ejecuta:
```bash
git remote add origin https://github.com/naorlando/dsbot.git
git add .
git commit -m "Initial commit"
git push -u origin main
```

#### 2. Desplegar en Railway

1. Ve a https://railway.app
2. Haz clic en "Login" → Usa GitHub
3. Haz clic en "New Project"
4. Selecciona "Deploy from GitHub repo"
5. Elige tu repositorio `dsbot`
6. Railway detectará automáticamente que es Python
7. Ve a "Variables" y agrega:
   - Nombre: `DISCORD_BOT_TOKEN`
   - Valor: `tu_token_de_discord_aqui`
8. El bot se desplegará automáticamente
9. Espera 1-2 minutos y verifica en Discord que el bot esté en línea

**¡Listo! El bot estará activo 24/7**

---

## 🎯 Opción 2: Render.com (Alternativa - 100% gratis)

### Ventajas:
- ✅ 100% GRATIS (sin tarjeta de crédito)
- ✅ Se reactiva automáticamente si se duerme
- ✅ Muy fácil

### Pasos:

#### 1. Crear repositorio en GitHub (igual que arriba)

#### 2. Desplegar en Render

1. Ve a https://render.com
2. Crea cuenta (puedes usar GitHub)
3. Haz clic en "New" → "Web Service"
4. Conecta tu repositorio de GitHub
5. Selecciona `dsbot`
6. Configura:
   - **Name:** `discord-bot`
   - **Region:** Elige el más cercano
   - **Branch:** `main`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
7. En "Environment Variables", agrega:
   - Key: `DISCORD_BOT_TOKEN`
   - Value: `tu_token_de_discord_aqui`
8. Haz clic en "Create Web Service"
9. Espera 2-3 minutos mientras Render construye y despliega
10. Verifica en Discord que el bot esté en línea

**¡Listo! El bot estará activo 24/7**

---

## 📋 Checklist Pre-Deploy

Antes de deployar, asegúrate de:

- [ ] El bot funciona localmente (`python bot.py`)
- [ ] El archivo `.env` NO está en git (verifica con `git status`)
- [ ] `requirements.txt` tiene todas las dependencias
- [ ] Los Intents están habilitados en Discord Developer Portal
- [ ] El bot tiene permisos en tu servidor de Discord

---

## 🔍 Verificar que el Deploy Funcionó

1. Ve a tu servidor de Discord
2. Verifica que el bot esté **en línea** (punto verde)
3. Escribe `!test` en un canal
4. Si responde, ¡todo está funcionando!

---

## 🆘 Problemas Comunes

### "El bot no se conecta después del deploy"
- Verifica que la variable `DISCORD_BOT_TOKEN` esté configurada correctamente
- Revisa los logs del servicio (Railway/Render tienen sección de logs)
- Verifica que los Intents estén habilitados

### "Error: Module not found"
- Verifica que `requirements.txt` tenga todas las dependencias
- Revisa los logs del build

### "El bot se desconecta frecuentemente"
- Railway: Verifica que no hayas excedido las 500 horas/mes
- Render: Es normal que se "duerma" después de 15 min de inactividad, pero se reactiva automáticamente

---

## 💡 Recomendación

**Usa Railway** - Es la opción más fácil y confiable para empezar.

---

**¿Listo para deployar?** Sigue los pasos de Railway arriba y en 5 minutos tendrás tu bot funcionando 24/7! 🚀

