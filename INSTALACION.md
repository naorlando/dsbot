# Guía Rápida de Instalación

## Instalación Local (Tu Computadora)

### 1. Instalar Python
- Descarga Python 3.8+ desde [python.org](https://www.python.org/downloads/)
- Durante la instalación, marca la opción "Add Python to PATH"

### 2. Descargar el proyecto
```bash
# Si tienes git:
git clone <url-del-repositorio>
cd dsbot

# O descarga el ZIP y extráelo
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Crear archivo .env
Crea un archivo llamado `.env` en la carpeta del proyecto con:
```
DISCORD_BOT_TOKEN=tu_token_aqui
```

### 5. Ejecutar
```bash
# Opción 1: Usar el script
./start.sh        # macOS/Linux
start.bat         # Windows

# Opción 2: Ejecutar directamente
python bot.py
```

## Instalación en Servidor (Hosting)

### Railway (Recomendado - Gratis)

1. Ve a [railway.app](https://railway.app) y crea cuenta
2. Haz clic en "New Project" > "Deploy from GitHub repo"
3. Conecta tu repositorio o sube los archivos manualmente
4. Ve a "Variables" y agrega:
   - Nombre: `DISCORD_BOT_TOKEN`
   - Valor: `tu_token`
5. El bot se desplegará automáticamente

### Render (Gratis)

1. Ve a [render.com](https://render.com) y crea cuenta
2. Haz clic en "New" > "Web Service"
3. Conecta tu repositorio o sube archivos
4. Configura:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
5. En "Environment Variables", agrega:
   - `DISCORD_BOT_TOKEN` = `tu_token`
6. Haz clic en "Create Web Service"

### Replit (Gratis pero requiere mantener abierto)

1. Ve a [replit.com](https://replit.com) y crea cuenta
2. Crea nuevo proyecto Python
3. Sube los archivos del bot
4. En "Secrets", agrega:
   - `DISCORD_BOT_TOKEN` = `tu_token`
5. Ejecuta el bot
6. Para mantenerlo activo, usa [UptimeRobot](https://uptimerobot.com) para hacer ping cada 5 minutos

## Verificación

Una vez ejecutado, deberías ver:
```
BotName#1234 se ha conectado a Discord!
Bot ID: 123456789012345678
```

Luego en Discord, escribe `!setchannel` en el canal donde quieres las notificaciones.

## Problemas Comunes

**Error: "No module named 'discord'"**
- Ejecuta: `pip install -r requirements.txt`

**Error: "No se encontró DISCORD_BOT_TOKEN"**
- Verifica que el archivo `.env` existe y tiene el token correcto

**El bot no detecta actividades**
- Ve a [Discord Developer Portal](https://discord.com/developers/applications)
- Selecciona tu aplicación > Bot
- Habilita "Presence Intent" y "Server Members Intent"
- Reinicia el bot

