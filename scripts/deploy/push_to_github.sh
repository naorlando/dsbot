#!/bin/bash
# Script para conectar y subir a GitHub
# Ejecuta después de crear el repositorio en https://github.com/new

echo "🔗 Conectando con GitHub..."
git remote add origin https://github.com/naorlando/dsbot.git 2>/dev/null || git remote set-url origin https://github.com/naorlando/dsbot.git

echo "📤 Subiendo código..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ ¡Código subido exitosamente!"
    echo "🔗 Repositorio: https://github.com/naorlando/dsbot"
else
    echo ""
    echo "❌ Error al subir. Verifica:"
    echo "   1. Que el repositorio existe en GitHub"
    echo "   2. Que tienes permisos"
    echo "   3. Que usas un Personal Access Token como contraseña"
fi
