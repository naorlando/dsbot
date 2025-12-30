#!/bin/bash

# Script para configurar git SOLO en este directorio
# Ejecuta: ./config_git.sh

echo "🔧 Configurando Git para este proyecto..."
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "bot.py" ]; then
    echo "❌ Error: Ejecuta este script desde la carpeta del proyecto"
    exit 1
fi

# Inicializar git si no está inicializado
if [ ! -d ".git" ]; then
    echo "📦 Inicializando repositorio git..."
    git init
fi

# Configurar credenciales LOCALES (solo este proyecto)
echo "⚙️  Configurando credenciales personales..."
git config user.name "naorlando"
git config user.email "naorlando@frba.utn.edu.ar"

# Verificar configuración
echo ""
echo "✅ Configuración completada:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Configuración LOCAL (solo este proyecto):"
git config --local user.name
git config --local user.email
echo ""
echo "Configuración GLOBAL (no afectada):"
git config --global user.name 2>/dev/null || echo "No configurado"
git config --global user.email 2>/dev/null || echo "No configurado"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ Git configurado correctamente para este proyecto"
echo "   Tu configuración global empresarial NO fue afectada"

