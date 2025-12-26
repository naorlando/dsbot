# Bot de Discord - Notificaciones de Actividad

Un bot de Discord que notifica en el canal general cuando los miembros:
- 🎮 Empiezan a jugar un juego
- 🔊 Entran a un canal de voz
- 🔄 Cambian de canal de voz

## Características

- ✅ Notificaciones configurables
- ✅ Soporte para diferentes tipos de actividades (juegos, streaming, música, etc.)
- ✅ Comandos de administración para personalizar el comportamiento
- ✅ Ignora bots por defecto (configurable)

## Instalación Local

### Paso 1: Requisitos previos

- Python 3.8 o superior
- pip (gestor de paquetes de Python)
- Una aplicación de bot en Discord

**Verificar Python:**
```bash
python --version
# o
python3 --version
```

### Paso 2: Crear el bot en Discord

1. Ve a [Discord Developer Portal](https://discord.com/developers/applications)
2. Haz clic en "New Application" y dale un nombre
3. Ve a la sección **"Bot"** en el menú lateral
4. Haz clic en **"Add Bot"** y confirma
5. **IMPORTANTE:** En la sección "Privileged Gateway Intents", habilita:
   - ✅ **Presence Intent** (necesario para detectar juegos)
   - ✅ **Server Members Intent** (necesario para detectar miembros)
6. Copia el **Token** del bot (haz clic en "Reset Token" si es necesario)
7. Ve a la sección **"OAuth2"** > **"URL Generator"**
8. Selecciona los scopes:
   - ✅ `bot`
   - ✅ `applications.commands`
9. Selecciona los permisos necesarios:
   - ✅ `Read Messages/View Channels`
   - ✅ `Send Messages`
   - ✅ `Read Message History`
   - ✅ `Connect` (para detectar voice channels)
   - ✅ `View Channels` (para detectar presences)
10. Copia la URL generada y ábrela en tu navegador para invitar el bot a tu servidor

### Paso 3: Clonar/Descargar el proyecto

Si tienes el código en un repositorio:
```bash
git clone <url-del-repositorio>
cd dsbot
```

O simplemente navega a la carpeta del proyecto si ya lo tienes.

### Paso 4: Crear entorno virtual (Recomendado)

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En macOS/Linux:
source venv/bin/activate
# En Windows:
venv\Scripts\activate
```

### Paso 5: Instalar dependencias

```bash
pip install -r requirements.txt
```

### Paso 6: Configurar el token

Crea un archivo `.env` en la raíz del proyecto:

**En macOS/Linux:**
```bash
touch .env
```

**En Windows:**
```bash
type nul > .env
```

Edita el archivo `.env` y agrega tu token:
```
DISCORD_BOT_TOKEN=tu_token_aqui_pega_aqui_el_token
```

**⚠️ IMPORTANTE:** Nunca compartas tu token. El archivo `.env` está en `.gitignore` para protegerlo.

### Paso 7: Ejecutar el bot

```bash
python bot.py
```

Si todo está bien, verás:
```
BotName#1234 se ha conectado a Discord!
Bot ID: 123456789012345678
```

### Paso 8: Configurar el canal de notificaciones

En cualquier canal de tu servidor de Discord, escribe:
```
!setchannel
```

Esto configurará ese canal para recibir las notificaciones.

## Configuración

El bot creará automáticamente un archivo `config.json` con la configuración por defecto. Puedes editarlo manualmente o usar los comandos del bot.

### Configuración inicial

1. Ejecuta el bot
2. En el canal donde quieres recibir las notificaciones, escribe:
   ```
   !setchannel
   ```
   O menciona otro canal:
   ```
   !setchannel #nombre-del-canal
   ```

## Comandos

### `!setchannel [canal]`
Configura el canal donde se enviarán las notificaciones.
- Si no especificas un canal, usa el canal actual
- Requiere permisos de administrador

**Ejemplo:**
```
!setchannel
!setchannel #general
```

### `!toggle <tipo>`
Activa o desactiva tipos de notificaciones.
- `games`: Notificaciones de juegos
- `voice`: Notificaciones de entrada a voz
- `voiceleave`: Notificaciones de salida de voz

**Ejemplo:**
```
!toggle games
!toggle voice
!toggle voiceleave
```

### `!config`
Muestra la configuración actual del bot.

### `!test`
Envía un mensaje de prueba al canal configurado.

## Configuración avanzada

Puedes editar el archivo `config.json` manualmente:

```json
{
    "channel_id": 123456789012345678,
    "notify_games": true,
    "notify_voice": true,
    "notify_voice_leave": false,
    "ignore_bots": true,
    "game_activity_types": [
        "playing",
        "streaming",
        "watching",
        "listening"
    ]
}
```

### Opciones:

- `channel_id`: ID del canal donde se enviarán las notificaciones (null = no configurado)
- `notify_games`: Activar/desactivar notificaciones de juegos
- `notify_voice`: Activar/desactivar notificaciones de entrada a voz
- `notify_voice_leave`: Activar/desactivar notificaciones de salida de voz
- `ignore_bots`: Ignorar actividad de bots
- `game_activity_types`: Tipos de actividades a notificar (playing, streaming, watching, listening)

## Solución de problemas

### El bot no detecta actividades

1. Asegúrate de que el bot tenga los permisos necesarios
2. Verifica que los "Privileged Gateway Intents" estén habilitados en el Developer Portal:
   - Presence Intent
   - Server Members Intent
3. Reinicia el bot después de habilitar los intents

### El bot no responde

1. Verifica que el token sea correcto
2. Asegúrate de que el bot esté en línea
3. Revisa los logs del bot para ver errores

## 🚀 Hosting/Publicación del Bot

**📖 Para una guía completa y detallada de hosting gratuito, consulta [HOSTING.md](HOSTING.md)**

### Opciones Recomendadas (Gratis):

1. **Railway.app** ⭐ (Recomendado)
   - 500 horas/mes gratis
   - Siempre activo
   - Despliegue automático desde GitHub

2. **Render.com** ⭐ (Alternativa excelente)
   - 100% gratis
   - Se reactiva automáticamente
   - Muy fácil de usar

3. **Replit.com**
   - Gratis pero requiere mantener activo
   - Bueno para desarrollo y pruebas

## Hosting/Publicación del Bot (Detalles)

Para que el bot esté siempre en línea, necesitas hostearlo en un servidor. Aquí tienes varias opciones:

### Opción 1: Hosting Gratuito (Recomendado para empezar)

#### Replit
1. Crea una cuenta en [Replit](https://replit.com)
2. Crea un nuevo proyecto Python
3. Sube los archivos del bot
4. Configura la variable de entorno `DISCORD_BOT_TOKEN` en Secrets
5. Ejecuta el bot (se mantendrá activo mientras la pestaña esté abierta)
6. Para mantenerlo siempre activo, considera usar [UptimeRobot](https://uptimerobot.com) para hacer ping cada 5 minutos

#### Railway
1. Crea una cuenta en [Railway](https://railway.app)
2. Conecta tu repositorio de GitHub o sube los archivos
3. Configura la variable de entorno `DISCORD_BOT_TOKEN`
4. Railway mantendrá el bot activo automáticamente
5. Plan gratuito incluye 500 horas/mes

#### Render
1. Crea una cuenta en [Render](https://render.com)
2. Crea un nuevo "Web Service"
3. Conecta tu repositorio o sube los archivos
4. Configura:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
5. Agrega la variable de entorno `DISCORD_BOT_TOKEN`
6. Plan gratuito mantiene el servicio activo (se duerme después de 15 min de inactividad, pero se reactiva automáticamente)

### Opción 2: VPS (Servidor Virtual Privado)

#### DigitalOcean, AWS, Google Cloud, etc.
1. Crea una cuenta y un servidor (Ubuntu recomendado)
2. Conéctate por SSH
3. Instala Python y git:
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip git
   ```
4. Clona tu repositorio o sube los archivos
5. Instala dependencias:
   ```bash
   pip3 install -r requirements.txt
   ```
6. Crea el archivo `.env` con tu token
7. Ejecuta el bot en segundo plano usando `screen` o `tmux`:
   ```bash
   # Instalar screen
   sudo apt install screen
   
   # Crear sesión
   screen -S discordbot
   
   # Ejecutar bot
   python3 bot.py
   
   # Desconectar: Ctrl+A luego D
   # Reconectar: screen -r discordbot
   ```

#### Usando systemd (Para mantener el bot siempre activo)
Crea un archivo `/etc/systemd/system/discordbot.service`:
```ini
[Unit]
Description=Discord Bot
After=network.target

[Service]
Type=simple
User=tu_usuario
WorkingDirectory=/ruta/a/dsbot
Environment="DISCORD_BOT_TOKEN=tu_token"
ExecStart=/usr/bin/python3 /ruta/a/dsbot/bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Luego:
```bash
sudo systemctl daemon-reload
sudo systemctl enable discordbot
sudo systemctl start discordbot
sudo systemctl status discordbot  # Ver estado
```

### Opción 3: Docker (Avanzado)

Crea un `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
```

Y un `docker-compose.yml`:
```yaml
version: '3.8'

services:
  bot:
    build: .
    env_file:
      - .env
    restart: unless-stopped
```

Ejecuta:
```bash
docker-compose up -d
```

### Recomendaciones

- **Para empezar:** Usa Railway o Render (gratis y fácil)
- **Para producción:** Usa un VPS con systemd o Docker
- **Siempre:** Mantén tu token seguro y nunca lo compartas
- **Monitoreo:** Considera agregar logs para ver el estado del bot

## Solución de problemas de hosting

### El bot se desconecta después de un tiempo
- Usa un servicio que mantenga el proceso activo (Railway, VPS con systemd)
- O configura un servicio de ping para mantenerlo despierto

### Error de permisos
- Asegúrate de que el bot tenga los permisos necesarios en el servidor
- Verifica que los Intents estén habilitados en Discord Developer Portal

### El bot no responde después del despliegue
- Verifica los logs del servicio
- Asegúrate de que la variable de entorno `DISCORD_BOT_TOKEN` esté configurada correctamente
- Verifica que el bot esté en línea en tu servidor de Discord

## 📦 Publicar como Open Source

Si quieres publicar este bot como proyecto open source en GitHub:

1. **Prepara el código:** Elimina tokens y información sensible
2. **Crea repositorio:** En GitHub, crea un nuevo repositorio público
3. **Sube el código:** Usa git para subir tus archivos
4. **Agrega LICENSE:** Elige una licencia (MIT recomendada)
5. **Mejora README:** Asegúrate de que esté completo

📖 **Guía completa:** Consulta [OPEN_SOURCE.md](OPEN_SOURCE.md) para instrucciones detalladas.

## Licencia

Este proyecto es de código abierto y está disponible para uso personal y comercial.

Puedes usar, modificar y distribuir este código libremente. Si lo usas en tu proyecto, considera dar crédito al autor original.

