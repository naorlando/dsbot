# 🤖 Discord Activity Bot

Bot de Discord que notifica actividad en tiempo real con estadísticas avanzadas y tracking de tiempo en voz.

## ✨ Características

- 🎮 **Notificaciones de juegos** - Detecta cuando alguien empieza a jugar
- 🔊 **Activity en voz** - Entrada, salida y cambios de canal
- 📊 **Estadísticas completas** - Rankings, gráficos ASCII, comparaciones
- ⏱️ **Tracking de tiempo** - Cuánto tiempo pasan en voz por usuario
- 🛡️ **Anti-spam** - Cooldowns configurables para notificaciones duplicadas
- 💾 **Datos persistentes** - Stats nunca se pierden (Railway Volume)
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
!setstatschannel    # (Opcional) Canal para comandos stats restringidos
!bothelp            # Ver todos los comandos (canal stats si está configurado)
```

### 📺 Sistema Dual de Canales

**Modo recomendado:** Separar notificaciones de comandos
- **Canal de notificaciones** (`!setchannel #general`) - Para avisos de juegos/voz
- **Canal de estadísticas** (`!setstatschannel #stats`) - Comandos stats restringidos

Si configuras un canal de stats, los comandos marcados como restringidos (`!bothelp`, `!party`, `!export`, `!statsmenu`, `!topconnections`, etc.) **solo funcionarán ahí**.
Esto ayuda a mantener tu canal general limpio y organizado. 🎯

```
!channels  # Ver configuración actual de ambos canales
```

## 📋 Comandos

Lista completa y notas de alcance: **[docs/COMANDOS.md](docs/COMANDOS.md)**.

### 🔧 Configuración
```
# Solo Owner 🔒
!setchannel         - Canal de notificaciones
!setstatschannel    - Canal de estadísticas (comandos stats)
!unsetchannel       - Quitar canal de notificaciones
!unsetstatschannel  - Quitar canal de stats

# Públicos (cualquier canal si no hay stats channel exclusivo)
!channels           - Ver canales configurados
!toggle             - Activar/desactivar notificaciones
!config             - Ver configuración
!test               - Mensaje de prueba
```

### 📊 Estadísticas (canal de stats si está configurado)
```
!stats / !mystats       - Perfil
!compare @user          - Comparar con otro usuario
!wrapped [@user] [año]  - Resumen anual

!topgamers              - Top por tiempo de juego (jugadores)
!topgames / !topgame    - Rankings por juego
!mygames                - Tus juegos
!topvoice               - Top tiempo en voz
!topchat                - Top mensajes (!topmessages)
!topusers               - Top actividad
!topreactions           - Reacciones
!topstickers            - Stickers

!partymaster            - Quién más arma parties
!partywith / !partygames - Parties sociales

!export [json|csv]      - Exportar datos
!checkstats             - Debug del archivo stats
!updates                - Últimas novedades del bot
```

### 🎉 Parties (mismo alcance que stats)
```
!party [juego]          - Parties activas
!partyhistory [periodo] - Historial
!partystats [juego]     - Estadísticas de parties
```

### 🛠️ Ayuda
```
!bothelp                - Centro de ayuda (!help)
!updates                - Últimas novedades (!novedades)
```

**Períodos** (donde aplique): `today`, `week`, `month`, `all`

**Nota:** Los comandos de owner (🔒) requieren `DISCORD_OWNER_ID` configurado.

## 🌐 Deploy (Railway)

### Setup Rápido

1. Fork este repo
2. Crea cuenta en [Railway](https://railway.app)
3. **New Project** → **Deploy from GitHub**
4. Configura variables:
   ```
   DISCORD_BOT_TOKEN=tu_token
   DISCORD_OWNER_ID=tu_user_id      # Requerido para comandos owner
   DISCORD_CHANNEL_ID=id_canal        # Opcional (notificaciones)
   DISCORD_STATS_CHANNEL_ID=id_canal  # Opcional (comandos stats)
   BOT_VERSION=vX.Y.Z                 # Opcional (texto del aviso de deploy)
   NOTIFY_DEPLOY=true                 # Opcional (aviso al quedar online)
   ENABLE_WRAPPED_SCHEDULER=false     # Opcional
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

**Cobertura:** correr `python -m pytest -q` antes de cada release.
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
├── bot.py                 # Entry point
├── core/                  # Sesiones, persistencia, cooldowns, health check
├── cogs/                  # events, config, stats (loader), utility
├── stats/                 # commands/, data/, visualization/
├── stats_viz.py           # Gráficos ASCII (legacy compartido)
├── docs/COMANDOS.md       # Lista actualizada de comandos
├── config.json / stats.json
├── railway.toml
└── requirements.txt
```

## 💡 Features Destacados

- **Verificación de voz:** Sistema de 2 fases (3s + 7s) para filtrar entradas rápidas
- **Juegos verificados:** Filtro multicapa que solo trackea actividades legítimas
  - Whitelist de clases: `Game`, `Streaming`, `Activity`, `Spotify`
  - Blacklist configurable de app IDs
  - Allowlist configurable para emuladores sin app ID (`allowed_no_app_id_games`)
  - Filtro de nombres sospechosos
- **Cooldown inteligente:** anti-spam por tipo de evento (juegos, voz, conexiones)
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
- **[ARQUITECTURA.md](ARQUITECTURA.md)** - Arquitectura (visión general; comandos en COMANDOS.md)
- **[docs/PLAN_MEJORAS.md](docs/PLAN_MEJORAS.md)** - Roadmap: métricas, tracking, LoL/lobby
- **[BUENAS_PRACTICAS.md](BUENAS_PRACTICAS.md)** - Guía de buenas prácticas

---

## 📝 Licencia

MIT - Uso libre personal y comercial

---

**⭐ Si te gusta el proyecto, dale una estrella!**

📖 Más info: `!bothelp` en Discord
