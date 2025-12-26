# 📤 Crear Repositorio en GitHub - Pasos Manuales

## ✅ Git ya está configurado

- ✅ Repositorio inicializado
- ✅ Commit realizado (26 archivos)
- ✅ Rama: `main`

## 🚀 Crear Repositorio en GitHub

### Paso 1: Crear el repositorio en GitHub

1. Ve a: **https://github.com/new**
2. Configura:
   - **Repository name:** `dsbot`
   - **Description:** `Bot de Discord para notificar actividad de miembros`
   - **Visibility:** Public (o Private si prefieres)
   - ❌ **NO marques** "Add a README file"
   - ❌ **NO marques** "Add .gitignore"
   - ❌ **NO marques** "Choose a license"
3. Haz clic en **"Create repository"**

### Paso 2: Conectar y subir código

Después de crear el repositorio, GitHub te mostrará instrucciones. Ejecuta estos comandos:

```bash
cd /Users/naorlando/Documents/my/dsbot

# Conectar con el repositorio remoto
git remote add origin https://github.com/naorlando/dsbot.git

# Subir el código
git push -u origin main
```

**Si te pide credenciales:**
- **Username:** `naorlando`
- **Password:** Usa un **Personal Access Token** (NO tu contraseña de GitHub)
  - Crea uno en: https://github.com/settings/tokens
  - Permisos: `repo` (todos los permisos de repositorio)

## ✅ Verificar

Después de hacer push, ve a:
**https://github.com/naorlando/dsbot**

Deberías ver todos tus archivos ahí.

## 🚀 Siguiente Paso: Deploy en Railway

Una vez que el código esté en GitHub:

1. Ve a **https://railway.app**
2. Login con GitHub
3. **New Project** → **Deploy from GitHub repo**
4. Selecciona: **naorlando/dsbot**
5. Ve a **Variables** y agrega:
   - **Name:** `DISCORD_BOT_TOKEN`
   - **Value:** `tu_token_de_discord_aqui`
6. ¡El bot se desplegará automáticamente!

---

**¡Ejecuta los comandos de arriba después de crear el repositorio en GitHub!** 🚀

