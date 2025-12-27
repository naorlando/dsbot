# 🔐 Variables de Entorno

Este archivo documenta todas las variables de entorno necesarias para el bot.

## 📋 Variables Requeridas

### `DISCORD_BOT_TOKEN` **(REQUERIDO)**
Token de tu bot de Discord.

**Cómo obtenerlo:**
1. Ve a https://discord.com/developers/applications
2. Selecciona tu aplicación
3. Ve a "Bot" en el menú lateral
4. Copia el token (si no lo ves, haz clic en "Reset Token")

**Ejemplo:**
```
DISCORD_BOT_TOKEN=YOUR_DISCORD_BOT_TOKEN_HERE
```

---

### `DISCORD_OWNER_ID` **(REQUERIDO)**
Tu Discord User ID (o múltiples IDs separados por comas). Necesario para usar comandos protegidos de configuración.

**Cómo obtenerlo:**
1. Habilita "Modo Desarrollador" en Discord:
   - Settings > Advanced > Developer Mode
2. Haz clic derecho en tu perfil de usuario
3. Selecciona "Copiar ID de usuario"

**Ejemplo (un solo owner):**
```
DISCORD_OWNER_ID=123456789012345678
```

**Ejemplo (múltiples owners):**
```
DISCORD_OWNER_ID=123456789012345678,987654321098765432,111222333444555666
```

**Comandos que requieren ser owner:**
- `!setchannel`
- `!unsetchannel`
- `!setstatschannel`
- `!unsetstatschannel`
- `!toggle`

---

## 📋 Variables Opcionales

### `DISCORD_CHANNEL_ID` *(OPCIONAL)*
ID del canal donde se enviarán las notificaciones de actividad (juegos, voz, etc.).

**Alternativa:** Usar el comando `!setchannel` en Discord.

**Ejemplo:**
```
DISCORD_CHANNEL_ID=987654321098765432
```

---

### `DISCORD_STATS_CHANNEL_ID` *(OPCIONAL)*
ID del canal donde funcionarán los comandos de estadísticas.

**Alternativa:** Usar el comando `!setstatschannel` en Discord.

**Si no se configura:** Los comandos de stats funcionarán en cualquier canal.

**Ejemplo:**
```
DISCORD_STATS_CHANNEL_ID=987654321098765432
```

---

## 🚀 Configuración en Railway

1. Ve a tu proyecto en Railway
2. Haz clic en "Variables"
3. Agrega cada variable con su valor:
   - `DISCORD_BOT_TOKEN` = tu_token
   - `DISCORD_OWNER_ID` = tu_user_id
   - *(Opcional)* `DISCORD_CHANNEL_ID` = canal_de_notificaciones
   - *(Opcional)* `DISCORD_STATS_CHANNEL_ID` = canal_de_stats

---

## 🔧 Configuración Local (.env)

Crea un archivo `.env` en la raíz del proyecto:

```env
# REQUERIDAS
DISCORD_BOT_TOKEN=tu_token_aqui
DISCORD_OWNER_ID=tu_user_id_aqui

# OPCIONALES
DISCORD_CHANNEL_ID=canal_notificaciones_aqui
DISCORD_STATS_CHANNEL_ID=canal_stats_aqui
```

**⚠️ IMPORTANTE:** El archivo `.env` está en `.gitignore` y NO debe subirse a GitHub.

---

## 💡 Tips

- **Múltiples Owners:** Puedes agregar varios owners separándolos por comas (sin espacios o con espacios, ambos funcionan).
- **Canales:** Los IDs de canales también se pueden configurar con comandos (`!setchannel`, `!setstatschannel`), pero las variables de entorno son más persistentes.
- **Railway:** Las variables de Railway tienen prioridad sobre `config.json` para evitar perder configuración en redeploys.
- **Seguridad:** Los IDs de usuario son permanentes (no cambian aunque el usuario cambie su nombre o tag).

