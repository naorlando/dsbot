#!/bin/bash

# Script para hacer deploy completo del bot
# Ejecuta: ./deploy_completo.sh

set -e  # Detener si hay errores

echo "🚀 Iniciando deploy completo..."
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "bot.py" ]; then
    echo "❌ Error: Ejecuta este script desde la carpeta del proyecto"
    exit 1
fi

# 1. Configurar git localmente
echo "1️⃣  Configurando git..."
if [ ! -d ".git" ]; then
    git init
fi

git config user.name "naorlando"
git config user.email "naorlando@frba.utn.edu.ar"

echo "✅ Git configurado"
echo ""

# 2. Verificar que .env no se va a subir
echo "2️⃣  Verificando seguridad..."
if git check-ignore .env > /dev/null 2>&1; then
    echo "✅ .env está protegido (no se subirá a git)"
else
    echo "⚠️  ADVERTENCIA: .env NO está en .gitignore"
    read -p "¿Continuar de todas formas? (y/n): " CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        exit 1
    fi
fi
echo ""

# 3. Agregar archivos y hacer commit
echo "3️⃣  Preparando archivos para commit..."
git add .
git status --short

echo ""
read -p "¿Hacer commit con estos archivos? (y/n): " DO_COMMIT
if [ "$DO_COMMIT" = "y" ] || [ "$DO_COMMIT" = "Y" ]; then
    git commit -m "Initial commit: Bot de Discord para notificaciones de actividad"
    echo "✅ Commit realizado"
else
    echo "❌ Commit cancelado"
    exit 1
fi
echo ""

# 4. Crear repositorio en GitHub
echo "4️⃣  Creando repositorio en GitHub..."
echo ""
echo "Opciones:"
echo "A) Usar GitHub CLI (gh) - Más fácil"
echo "B) Crear manualmente en GitHub"
echo ""
read -p "Elige opción (A/B): " OPTION

if [ "$OPTION" = "A" ] || [ "$OPTION" = "a" ]; then
    # Verificar si gh está instalado
    if ! command -v gh &> /dev/null; then
        echo "❌ GitHub CLI no está instalado"
        echo "   Instálalo con: brew install gh"
        echo "   O elige opción B para hacerlo manualmente"
        exit 1
    fi
    
    # Verificar autenticación
    if ! gh auth status &> /dev/null; then
        echo "⚠️  No estás autenticado con GitHub CLI"
        echo "   Ejecutando: gh auth login"
        gh auth login
    fi
    
    echo ""
    read -p "Nombre del repositorio (default: dsbot): " REPO_NAME
    REPO_NAME=${REPO_NAME:-dsbot}
    
    read -p "¿Repositorio público? (y/n, default: y): " IS_PUBLIC
    if [ "$IS_PUBLIC" = "n" ] || [ "$IS_PUBLIC" = "N" ]; then
        VISIBILITY="--private"
    else
        VISIBILITY="--public"
    fi
    
    echo ""
    echo "🚀 Creando repositorio y subiendo código..."
    gh repo create "$REPO_NAME" $VISIBILITY --source=. --remote=origin --push
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ ¡Repositorio creado y código subido exitosamente!"
        REPO_URL="https://github.com/naorlando/$REPO_NAME"
        echo "🔗 URL: $REPO_URL"
    else
        echo "❌ Error al crear el repositorio"
        exit 1
    fi
    
else
    # Opción manual
    echo ""
    echo "📝 Pasos manuales:"
    echo ""
    echo "1. Ve a https://github.com/new"
    echo "2. Crea un repositorio llamado: dsbot"
    echo "3. NO marques 'Initialize with README'"
    echo "4. Haz clic en 'Create repository'"
    echo ""
    read -p "¿Ya creaste el repositorio? (y/n): " REPO_CREATED
    
    if [ "$REPO_CREATED" = "y" ] || [ "$REPO_CREATED" = "Y" ]; then
        read -p "URL del repositorio (ej: https://github.com/naorlando/dsbot.git): " REPO_URL
        
        echo ""
        echo "🔗 Conectando con repositorio remoto..."
        git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"
        
        echo "📤 Subiendo código..."
        git branch -M main
        git push -u origin main
        
        if [ $? -eq 0 ]; then
            echo "✅ ¡Código subido exitosamente!"
        else
            echo "❌ Error al subir el código"
            exit 1
        fi
    else
        echo "❌ Crea el repositorio primero y luego ejecuta este script nuevamente"
        exit 1
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ PASO 1 COMPLETADO: Código en GitHub"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Próximos pasos para deploy:"
echo ""
echo "OPCIÓN 1: Railway (Recomendado)"
echo "1. Ve a https://railway.app"
echo "2. Login con GitHub"
echo "3. New Project → Deploy from GitHub repo"
echo "4. Selecciona: naorlando/dsbot"
echo "5. Variables → Agrega: DISCORD_BOT_TOKEN = tu_token"
echo "6. ¡Listo! El bot se desplegará automáticamente"
echo ""
echo "OPCIÓN 2: Render"
echo "1. Ve a https://render.com"
echo "2. Login con GitHub"
echo "3. New → Web Service"
echo "4. Conecta: naorlando/dsbot"
echo "5. Build: pip install -r requirements.txt"
echo "6. Start: python bot.py"
echo "7. Variables → DISCORD_BOT_TOKEN = tu_token"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

