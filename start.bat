@echo off
REM Script para iniciar el bot de Discord en Windows
REM Uso: start.bat

echo 🚀 Iniciando bot de Discord...

REM Verificar si existe el archivo .env
if not exist .env (
    echo ❌ Error: No se encontró el archivo .env
    echo Por favor, crea un archivo .env con tu DISCORD_BOT_TOKEN
    pause
    exit /b 1
)

REM Verificar si existe el entorno virtual
if exist venv\Scripts\activate.bat (
    echo 📦 Activando entorno virtual...
    call venv\Scripts\activate.bat
)

REM Verificar si las dependencias están instaladas
python -c "import discord" 2>nul
if errorlevel 1 (
    echo 📥 Instalando dependencias...
    pip install -r requirements.txt
)

REM Iniciar el bot
echo ✅ Iniciando bot...
python bot.py

pause

