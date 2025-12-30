# 🤖 Discord Activity Bot

Bot de Discord que notifica actividad en tiempo real con estadísticas avanzadas y tracking de tiempo en voz.

## ✨ Características

- 🎮 **Notificaciones de juegos** - Detecta cuando alguien empieza a jugar
- 🔊 **Activity en voz** - Entrada, salida y cambios de canal
- 📊 **Estadísticas completas** - Rankings, gráficos ASCII, comparaciones
- ⏱️ **Tracking de tiempo** - Cuánto tiempo pasan en voz por usuario
- 🛡️ **Anti-spam** - Cooldown de 10 min para evitar notificaciones duplicadas
- 💾 **Datos persistentes** - Stats nunca se pierden (Railway Volume)
- 🎨 **Menú interactivo** - Visualizaciones con select menus y botones
- 📺 **Sistema dual de canales** - Separa notificaciones de comandos de stats

## 🚀 Quick Start

### 1. Requisitos

- Python 3.8+
- Bot de Discord ([crear aquí](https://discord.com/developers/applications))
- Habilitar **Privileged Gateway Intents** (Presence + Server Members)

### 2. Instalación

```bash
git clone https://github.com/naorlando/dsbot.git
cd dsbot
pip install -r requirements.txt
```

### 3. Configurar Variables de Entorno

Crea `.env` (ver [ENV_TEMPLATE.md](ENV_TEMPLATE.md) para detalles):
```env
# REQUERIDAS
DISCORD_BOT_TOKEN=tu_token_aqui
DISCORD_OWNER_ID=tu_user_id            # Para comandos protegidos
# DISCORD_OWNER_ID=id1,id2,id3         # Múltiples owners (separados por comas)

# OPCIONALES
DISCORD_CHANNEL_ID=id_del_canal        # Canal de notificaciones
DISCORD_STATS_CHANNEL_ID=id_del_canal  # Canal de comandos stats
```

**¿Cómo obtener tu User ID?**
1. Habilita "Modo Desarrollador" en Discord (Settings > Advanced)
2. Clic derecho en tu perfil > "Copiar ID de usuario"

**💡 Tip:** Puedes agregar múltiples owners separándolos por comas

### 4. Ejecutar

```bash
python bot.py
```

### 5. Configurar en Discord

```
!setchannel         # Configura el canal de notificaciones (avisos)
!setstatschannel    # (Opcional) Canal exclusivo para comandos de stats
!bothelp            # Ver todos los comandos
```

### 📺 Sistema Dual de Canales

**Modo recomendado:** Separar notificaciones de comandos
- **Canal de notificaciones** (`!setchannel #general`) - Para avisos de juegos/voz
- **Canal de estadísticas** (`!setstatschannel #stats`) - Solo comandos de stats

Si configuras un canal de stats, los comandos (`!stats`, `!topgames`, etc.) **solo funcionarán ahí**.  
Esto mantiene tu canal general limpio y organizado. 🎯

```
!channels  # Ver configuración actual de ambos canales
```

## 📋 Comandos

### 🔧 Configuración
```
# Solo Owner 🔒
!setchannel         - Configurar canal de notificaciones
!setstatschannel    - Configurar canal de estadísticas
!unsetchannel       - Desconfigurar canal de notificaciones
!unsetstatschannel  - Desconfigurar canal de stats

# Públicos
!channels           - Ver configuración de canales
!toggle             - Activar/desactivar notificaciones (menú)
!config             - Ver configuración actual
!test               - Mensaje de prueba
```

**Nota:** Los comandos de owner (🔒) requieren `DISCORD_OWNER_ID` configurado.

### 📊 Estadísticas
```
!statsmenu               - Menú interactivo completo
!stats [@user]           - Stats de un usuario
!topgames [período]      - Ranking de juegos
!topusers                - Usuarios más activos
!topconnections [período] - Ranking de conexiones diarias
!topmessages [límite]    - Top usuarios por mensajes
!topreactions [límite]   - Top reacciones más usadas
!topemojis [límite]      - Top emojis favoritos
!topstickers [límite]    - Top stickers más enviados
```

### 📈 Avanzadas
```
!statsgames [período]  - Ranking con gráfico ASCII
!statsvoice [período]  - Ranking actividad voz
!timeline [días]       - Línea de tiempo (1-30 días)
!compare @user1 @user2 - Comparar dos usuarios
```

### 🕐 Tiempo en Voz
```
!voicetime [@user] [período]  - Ver tiempo en voz
!voicetop [período]           - Ranking por tiempo
```

### 🛠️ Utilidades
```
!export [json|csv]  - Exportar estadísticas
!bothelp [comando]  - Ayuda detallada
```

**Períodos:** `today`, `week`, `month`, `all`

## 🌐 Deploy (Railway)

### Setup Rápido

1. Fork este repo
2. Crea cuenta en [Railway](https://railway.app)
3. **New Project** → **Deploy from GitHub**
4. Configura variables:
   ```
   DISCORD_BOT_TOKEN=tu_token
   DISCORD_CHANNEL_ID=id_canal        # Opcional (notificaciones)
   DISCORD_STATS_CHANNEL_ID=id_canal  # Opcional (comandos stats)
   ```
5. Deploy automático ✅

Railway detectará `railway.toml` y creará un volume de 500MB para datos persistentes.

## 📊 Visualizaciones

```
🎮 Ranking de Juegos - Esta Semana
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Valorant          ████████████████ 45
League            ████████████ 32
Minecraft         ████████ 21
```

```
🕐 Tiempo en Voz - Usuario1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ Esta Semana: 12h 30m

📅 Últimos 7 Días
26/12 - 2h 15m
25/12 - 3h 45m
24/12 - 1h 30m
```

## 🧪 Tests

```bash
python test_bot.py
```

**Cobertura:** 63/63 tests ✅
- Gráficos ASCII
- Tracking de tiempo
- Filtros por período
- Comandos y estructura
- Message tracking
- Link filtering
- Reactions y stickers
- Conexiones diarias
- Notificaciones de milestones

## 🛡️ Seguridad

- ✅ Token en `.env` (nunca en código)
- ✅ `.gitignore` configurado
- ✅ No permisos de admin requeridos (el servidor maneja permisos)

## 📦 Estructura

```
dsbot/
├── bot.py           # Bot principal (27 comandos)
├── stats_viz.py     # Visualizaciones y gráficos
├── test_bot.py      # Suite de tests
├── config.json      # Configuración del bot
├── railway.toml     # Config de Railway Volume
└── requirements.txt # Dependencias
```

## 💡 Features Destacados

- **Verificación de voz:** Sistema de 2 fases (3s + 7s) para filtrar entradas rápidas
- **Juegos verificados:** Filtro multicapa que solo trackea actividades legítimas
  - Whitelist de clases: `Game`, `Streaming`, `Activity`, `Spotify`
  - Blacklist configurable de app IDs
  - Filtro de nombres sospechosos
- **Cooldown inteligente:** 10 min para juegos/voz, 5 min para conexiones
- **Session tracking:** Detecta cuánto tiempo están en voz (>1 min) y jugando
- **Conexiones diarias:** Trackea cuántas veces se conecta cada usuario con milestones
- **Visualizaciones ASCII:** Gráficos que funcionan en Discord
- **Menú interactivo:** Select menus con filtros de período
- **Export:** JSON y CSV para análisis externos
- **Persistencia:** Railway Volume mantiene datos entre deploys

## 📚 Documentación

La documentación del proyecto está organizada en carpetas temáticas:

- **[docs/analisis/](docs/analisis/)** - Análisis técnicos y estudios de mejoras
- **[docs/propuestas/](docs/propuestas/)** - Propuestas de nuevas features
- **[docs/refactors/](docs/refactors/)** - Documentación de refactors completados
- **[ARQUITECTURA.md](ARQUITECTURA.md)** - Arquitectura del sistema y diseño
- **[BUENAS_PRACTICAS.md](BUENAS_PRACTICAS.md)** - Guía de buenas prácticas

---

## 📝 Licencia

MIT - Uso libre personal y comercial

---

**⭐ Si te gusta el proyecto, dale una estrella!**

📖 Más info: `!bothelp` en Discord
