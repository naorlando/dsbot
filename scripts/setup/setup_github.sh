#!/bin/bash

# Script para configurar GitHub personal para este proyecto
# No afecta la configuración global empresarial

echo "🚀 Configurando GitHub Personal para este proyecto..."
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "bot.py" ]; then
    echo "❌ Error: Este script debe ejecutarse en la carpeta del proyecto"
    exit 1
fi

# Inicializar git si no está inicializado
if [ ! -d ".git" ]; then
    echo "📦 Inicializando repositorio git..."
    git init
fi

# Verificar configuración actual
echo "📋 Configuración actual:"
echo "   Global (empresarial):"
git config --global user.name 2>/dev/null && echo "   - Nombre: $(git config --global user.name)"
git config --global user.email 2>/dev/null && echo "   - Email: $(git config --global user.email)"
echo ""
echo "   Local (este proyecto):"
git config --local user.name 2>/dev/null && echo "   - Nombre: $(git config --local user.name)" || echo "   - No configurado"
git config --local user.email 2>/dev/null && echo "   - Email: $(git config --local user.email)" || echo "   - No configurado"
echo ""

# Solicitar información personal
echo "📝 Configuración de credenciales PERSONALES para este proyecto:"
read -p "Tu nombre personal: " PERSONAL_NAME
read -p "Tu email personal (GitHub): " PERSONAL_EMAIL
read -p "Tu usuario de GitHub personal: " GITHUB_USER

# Configurar git local
echo ""
echo "⚙️  Configurando git local..."
git config user.name "$PERSONAL_NAME"
git config user.email "$PERSONAL_EMAIL"

echo "✅ Configuración local completada:"
echo "   - Nombre: $(git config user.name)"
echo "   - Email: $(git config user.email)"
echo ""

# Verificar GitHub CLI
if command -v gh &> /dev/null; then
    echo "✅ GitHub CLI encontrado"
    echo ""
    echo "🔐 Verificando autenticación..."
    if gh auth status &> /dev/null; then
        echo "✅ Ya estás autenticado con GitHub CLI"
        gh auth status
    else
        echo "⚠️  No estás autenticado con GitHub CLI"
        echo ""
        read -p "¿Quieres autenticarte ahora? (y/n): " AUTH_NOW
        if [ "$AUTH_NOW" = "y" ] || [ "$AUTH_NOW" = "Y" ]; then
            gh auth login
        fi
    fi
else
    echo "⚠️  GitHub CLI no está instalado"
    echo "   Instálalo con: brew install gh"
    echo "   O usa un Personal Access Token manualmente"
fi

echo ""
echo "📦 Preparando archivos para commit..."

# Agregar archivos
git add .

# Verificar si hay cambios
if git diff --staged --quiet; then
    echo "⚠️  No hay cambios para commitear"
else
    echo "✅ Archivos listos para commit"
    echo ""
    read -p "¿Quieres hacer commit ahora? (y/n): " DO_COMMIT
    if [ "$DO_COMMIT" = "y" ] || [ "$DO_COMMIT" = "Y" ]; then
        git commit -m "Initial commit: Bot de Discord para notificaciones"
        echo "✅ Commit realizado"
    fi
fi

echo ""
echo "🌐 Configuración de repositorio remoto:"
echo ""
read -p "¿Quieres crear el repositorio en GitHub ahora? (y/n): " CREATE_REPO

if [ "$CREATE_REPO" = "y" ] || [ "$CREATE_REPO" = "Y" ]; then
    if command -v gh &> /dev/null; then
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
        echo "🚀 Creando repositorio en GitHub..."
        gh repo create "$REPO_NAME" $VISIBILITY --source=. --remote=origin --push
        
        if [ $? -eq 0 ]; then
            echo ""
            echo "✅ ¡Repositorio creado y código subido exitosamente!"
            echo ""
            echo "🔗 URL del repositorio:"
            gh repo view --web
        else
            echo "❌ Error al crear el repositorio"
            echo "   Puedes crearlo manualmente en: https://github.com/new"
        fi
    else
        echo "⚠️  GitHub CLI no está instalado"
        echo ""
        echo "📝 Pasos manuales:"
        echo "1. Ve a https://github.com/new"
        echo "2. Crea un repositorio llamado: dsbot"
        echo "3. NO inicialices con README"
        echo "4. Luego ejecuta:"
        echo "   git remote add origin https://github.com/$GITHUB_USER/dsbot.git"
        echo "   git push -u origin main"
    fi
else
    echo ""
    echo "📝 Para crear el repositorio manualmente:"
    echo "1. Ve a https://github.com/new"
    echo "2. Crea un repositorio"
    echo "3. Luego ejecuta:"
    echo "   git remote add origin https://github.com/$GITHUB_USER/REPO_NAME.git"
    echo "   git push -u origin main"
fi

echo ""
echo "✅ Configuración completada!"
echo ""
echo "📋 Resumen:"
echo "   - Git configurado localmente con credenciales personales"
echo "   - Configuración global empresarial NO afectada"
echo "   - Listo para trabajar con tu cuenta personal de GitHub"
echo ""
echo "🔍 Verificar configuración:"
echo "   git config --local --list"

