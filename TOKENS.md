# 🔑 Guía de Tokens Necesarios

## Tokens Requeridos

### 1. Token de Discord Bot (OBLIGATORIO)

**Dónde obtenerlo:**
1. Ve a [Discord Developer Portal](https://discord.com/developers/applications)
2. Inicia sesión con tu cuenta de Discord
3. Si no tienes una aplicación, haz clic en "New Application"
4. Dale un nombre (ej: "Activity Bot")
5. Ve a la sección **"Bot"** en el menú lateral
6. Haz clic en **"Add Bot"** y confirma
7. **IMPORTANTE:** En "Privileged Gateway Intents", habilita:
   - ✅ **Presence Intent** (necesario para detectar juegos)
   - ✅ **Server Members Intent** (necesario para detectar miembros)
8. Haz clic en **"Reset Token"** o **"Copy"** para obtener el token
9. **⚠️ IMPORTANTE:** Copia el token inmediatamente, solo se muestra una vez

**Cómo usarlo:**
Crea un archivo `.env` en esta carpeta:
```bash
echo "DISCORD_BOT_TOKEN=tu_token_aqui" > .env
```

O edítalo manualmente:
```
DISCORD_BOT_TOKEN=tu_token_de_discord_aqui
```

---

### 2. Token de GitHub (OPCIONAL - Solo si usas GitHub CLI)

**Cuándo lo necesitas:**
- Si quieres usar `gh repo create` para crear repositorios automáticamente
- Si prefieres autenticarte con GitHub CLI en lugar de HTTPS

**Dónde obtenerlo:**
1. Ve a [GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)](https://github.com/settings/tokens)
2. Haz clic en **"Generate new token (classic)"**
3. Configura:
   - **Note:** `dsbot-personal` (o el nombre que prefieras)
   - **Expiration:** Elige una fecha (90 días recomendado)
   - **Scopes:** Marca `repo` (todos los permisos de repositorio)
4. Haz clic en **"Generate token"**
5. **⚠️ IMPORTANTE:** Copia el token inmediatamente, solo se muestra una vez

**Cómo usarlo:**
```bash
# Opción 1: GitHub CLI (recomendado)
gh auth login
# Cuando te pida el token, pégalo

# Opción 2: Manualmente en git
# Git te pedirá usuario y contraseña
# Usuario: naorlando
# Contraseña: el token (NO tu contraseña de GitHub)
```

---

## ✅ Checklist

- [ ] Token de Discord obtenido y guardado en `.env`
- [ ] Token de GitHub obtenido (si vas a usar GitHub CLI)
- [ ] Archivo `.env` creado en esta carpeta
- [ ] `.env` NO está siendo rastreado por git (verificado con `git status`)

---

## 🔒 Seguridad

**NUNCA:**
- ❌ Subas el archivo `.env` a GitHub
- ❌ Compartas tus tokens públicamente
- ❌ Hardcodees tokens en el código
- ❌ Compartas tokens por chat/email

**SIEMPRE:**
- ✅ Usa variables de entorno (`.env`)
- ✅ Mantén `.env` en `.gitignore`
- ✅ Regenera tokens si crees que fueron comprometidos
- ✅ Usa tokens con permisos mínimos necesarios

---

## 🆘 Problemas Comunes

**"No se encontró DISCORD_BOT_TOKEN"**
- Verifica que el archivo `.env` existe en esta carpeta
- Verifica que tiene el formato correcto: `DISCORD_BOT_TOKEN=token_aqui`
- No debe tener espacios alrededor del `=`

**"Authentication failed" en GitHub**
- Si usas HTTPS, asegúrate de usar el token como contraseña (no tu contraseña real)
- Si usas GitHub CLI, ejecuta `gh auth login` nuevamente
- Verifica que el token tenga los permisos correctos (`repo`)

