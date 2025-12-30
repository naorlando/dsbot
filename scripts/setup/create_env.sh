#!/bin/bash

# Script para crear el archivo .env con el token
# Ejecuta: ./create_env.sh

TOKEN="tu_token_de_discord_aqui"

echo "🔐 Creando archivo .env..."
echo "DISCORD_BOT_TOKEN=$TOKEN" > .env

if [ -f ".env" ]; then
    echo "✅ Archivo .env creado correctamente"
    echo ""
    echo "⚠️  IMPORTANTE:"
    echo "   - El archivo .env está en .gitignore (no se subirá a git)"
    echo "   - NUNCA compartas este token públicamente"
    echo "   - Si el token se compromete, regenera uno nuevo en Discord Developer Portal"
else
    echo "❌ Error al crear el archivo .env"
    exit 1
fi

