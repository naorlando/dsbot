#!/bin/bash

# Script para iniciar el bot de Discord
# Uso: ./start.sh

echo "🚀 Iniciando bot de Discord..."

# Verificar si existe el archivo .env
if [ ! -f .env ]; then
    echo "❌ Error: No se encontró el archivo .env"
    echo "Por favor, crea un archivo .env con tu DISCORD_BOT_TOKEN"
    exit 1
fi

# Verificar si existe el entorno virtual
if [ -d "venv" ]; then
    echo "📦 Activando entorno virtual..."
    source venv/bin/activate
fi

# Verificar si las dependencias están instaladas
if ! python -c "import discord" 2>/dev/null; then
    echo "📥 Instalando dependencias..."
    pip install -r requirements.txt
fi

# Iniciar el bot
echo "✅ Iniciando bot..."
python bot.py

