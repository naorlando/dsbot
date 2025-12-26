# Guía: Configurar GitHub Personal para este Proyecto

## 🎯 Objetivo

Configurar este proyecto para usar tu cuenta personal de GitHub **sin afectar** tu configuración empresarial.

## 📋 Opción 1: Configuración Local (Recomendada)

Esta opción configura git **solo para este proyecto**, dejando intacta tu configuración global empresarial.

### Paso 1: Inicializar el repositorio

```bash
# En la carpeta del proyecto
cd /Users/naorlando/Documents/my/dsbot

# Inicializar git (si no está inicializado)
git init
```

### Paso 2: Configurar credenciales LOCALES (solo este proyecto)

```bash
# Configurar nombre y email PERSONAL (solo para este repo)
git config user.name "Tu Nombre Personal"
git config user.email "tu-email-personal@gmail.com"

# Verificar que se configuró correctamente
git config user.name
git config user.email
```

### Paso 3: Configurar autenticación

Tienes 3 opciones para autenticarte:

#### Opción A: GitHub CLI (Más fácil) ⭐

```bash
# Instalar GitHub CLI (si no lo tienes)
brew install gh

# Autenticarte con tu cuenta PERSONAL
gh auth login
# Selecciona:
# - GitHub.com
# - HTTPS
# - Login with a web browser
# - Acepta los permisos

# Verificar que estás logueado con la cuenta correcta
gh auth status
```

#### Opción B: Personal Access Token (PAT)

1. Ve a [GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)](https://github.com/settings/tokens)
2. Haz clic en "Generate new token (classic)"
3. Configura:
   - **Note:** `dsbot-personal`
   - **Expiration:** Elige una fecha
   - **Scopes:** Marca `repo` (todos los permisos de repositorio)
4. Copia el token (solo se muestra una vez)
5. Cuando git te pida credenciales, usa:
   - **Username:** Tu usuario de GitHub personal
   - **Password:** El token que copiaste

#### Opción C: SSH Key (Más seguro, recomendado para largo plazo)

```bash
# Generar nueva SSH key para GitHub personal
ssh-keygen -t ed25519 -C "tu-email-personal@gmail.com" -f ~/.ssh/id_ed25519_personal

# Agregar al ssh-agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519_personal

# Copiar la clave pública
cat ~/.ssh/id_ed25519_personal.pub
# Copia todo el contenido

# Agregar a GitHub:
# 1. Ve a https://github.com/settings/keys
# 2. New SSH key
# 3. Pega la clave pública
# 4. Dale un título: "Mac Personal"

# Configurar git para usar SSH en este proyecto
git remote set-url origin git@github.com:TU_USUARIO/dsbot.git
```

### Paso 4: Crear repositorio en GitHub

#### Método 1: Usando GitHub CLI (Más fácil)

```bash
# Crear repositorio y conectarlo automáticamente
gh repo create dsbot --public --source=. --remote=origin --push

# Esto:
# - Crea el repo en GitHub
# - Lo conecta como 'origin'
# - Sube el código
```

#### Método 2: Manualmente en GitHub

1. Ve a [github.com](https://github.com) y asegúrate de estar logueado con tu cuenta **personal**
2. Haz clic en "New repository"
3. Configura:
   - **Name:** `dsbot`
   - **Description:** "Bot de Discord para notificar actividad de miembros"
   - **Visibility:** Public (o Private si prefieres)
   - ❌ **NO marques** "Initialize with README" (ya tenemos uno)
4. Haz clic en "Create repository"
5. Copia la URL que te da (será algo como: `https://github.com/TU_USUARIO/dsbot.git`)

Luego en tu terminal:

```bash
# Agregar el repositorio remoto
git remote add origin https://github.com/TU_USUARIO/dsbot.git

# O si usas SSH:
git remote add origin git@github.com:TU_USUARIO/dsbot.git

# Verificar
git remote -v
```

### Paso 5: Subir el código

```bash
# Agregar todos los archivos
git add .

# Hacer commit
git commit -m "Initial commit: Bot de Discord para notificaciones"

# Subir a GitHub
git push -u origin main

# Si tienes problemas con la rama, usa:
git branch -M main
git push -u origin main
```

## 🔐 Verificar Configuración

Para asegurarte de que todo está bien:

```bash
# Ver configuración LOCAL (solo este proyecto)
git config --local --list

# Ver configuración GLOBAL (no debería cambiar)
git config --global --list

# Verificar remoto
git remote -v

# Verificar autenticación GitHub CLI
gh auth status
```

## 🛠️ Solución de Problemas

### Error: "Permission denied" o "Authentication failed"

**Si usas HTTPS:**
```bash
# Limpiar credenciales guardadas
git credential-osxkeychain erase
host=github.com
protocol=https

# O usar GitHub CLI
gh auth login
```

**Si usas SSH:**
```bash
# Verificar que la clave está agregada
ssh-add -l

# Probar conexión
ssh -T git@github.com
```

### Error: "Repository not found"

- Verifica que estás logueado con la cuenta correcta
- Verifica que el repositorio existe en tu cuenta personal
- Verifica la URL del remoto: `git remote -v`

### Quiero cambiar entre cuentas

**Para este proyecto (personal):**
```bash
cd /Users/naorlando/Documents/my/dsbot
gh auth status  # Debe mostrar tu cuenta personal
```

**Para proyectos empresariales:**
```bash
cd /ruta/a/proyecto/empresarial
gh auth login  # Loguea con cuenta empresarial
```

## 📝 Resumen de Comandos Rápidos

```bash
# 1. Configurar git local
git config user.name "Tu Nombre"
git config user.email "tu-email-personal@gmail.com"

# 2. Autenticarse con GitHub CLI
gh auth login

# 3. Crear y conectar repositorio
gh repo create dsbot --public --source=. --remote=origin --push

# ¡Listo! Tu código está en GitHub
```

## ✅ Checklist Final

- [ ] Git configurado localmente con credenciales personales
- [ ] Autenticado con GitHub CLI o token personal
- [ ] Repositorio creado en GitHub (cuenta personal)
- [ ] Código subido exitosamente
- [ ] Configuración global empresarial intacta

---

**¿Necesitas ayuda?** Ejecuta los comandos de verificación arriba y comparte el output si hay problemas.

