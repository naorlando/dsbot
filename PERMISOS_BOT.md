# 🔐 Permisos del Bot de Discord

## Permisos Necesarios en Discord Developer Portal

### 1. Privileged Gateway Intents (OBLIGATORIO)

Ve a tu bot en [Discord Developer Portal](https://discord.com/developers/applications) → Selecciona tu aplicación → "Bot"

En la sección **"Privileged Gateway Intents"**, habilita:

- ✅ **PRESENCE INTENT** (Necesario para detectar cuando alguien juega)
- ✅ **SERVER MEMBERS INTENT** (Necesario para detectar miembros y sus actividades)

**⚠️ IMPORTANTE:** Sin estos intents, el bot NO podrá detectar juegos ni actividades.

---

### 2. Permisos del Bot (OAuth2 URL Generator)

Ve a **"OAuth2"** → **"URL Generator"**

#### Scopes (Alcances):
- ✅ **bot** - Permite que sea un bot
- ✅ **applications.commands** - Para comandos slash (opcional, pero recomendado)

#### Bot Permissions (Permisos del Bot):

**Permisos Básicos (Necesarios):**
- ✅ **View Channels** (`VIEW_CHANNELS`) - Ver canales
- ✅ **Send Messages** (`SEND_MESSAGES`) - Enviar mensajes
- ✅ **Read Message History** (`READ_MESSAGE_HISTORY`) - Leer historial

**Permisos de Voz (Para detectar voice channels):**
- ✅ **Connect** (`CONNECT`) - Conectarse a canales de voz
- ✅ **View Channel** (ya incluido arriba)

**Permisos Opcionales (Recomendados):**
- ✅ **Embed Links** (`EMBED_LINKS`) - Para mensajes con embeds
- ✅ **Attach Files** (`ATTACH_FILES`) - Adjuntar archivos (si lo necesitas)
- ✅ **Use External Emojis** (`USE_EXTERNAL_EMOJIS`) - Usar emojis externos

**Permisos de Administración (Solo si necesitas comandos admin):**
- ⚠️ **Manage Messages** (`MANAGE_MESSAGES`) - Solo si necesitas borrar mensajes
- ⚠️ **Administrator** (`ADMINISTRATOR`) - **NO recomendado** a menos que sea necesario

---

## 📋 Resumen de Permisos Mínimos

### Para que el bot funcione básicamente:

```
✅ View Channels
✅ Send Messages  
✅ Read Message History
✅ Connect (para voice channels)
```

### Permisos Recomendados (Más completos):

```
✅ View Channels
✅ Send Messages
✅ Read Message History
✅ Connect
✅ Embed Links
✅ Use External Emojis
```

---

## 🔗 Generar URL de Invitación

Después de configurar los permisos:

1. En "OAuth2" → "URL Generator"
2. Selecciona los scopes y permisos de arriba
3. Copia la URL generada
4. Ábrela en tu navegador
5. Selecciona el servidor donde quieres agregar el bot
6. Autoriza

**Ejemplo de URL generada:**
```
https://discord.com/api/oauth2/authorize?client_id=TU_CLIENT_ID&permissions=277025508416&scope=bot%20applications.commands
```

---

## ⚙️ Configuración en el Servidor

Una vez que el bot esté en tu servidor:

1. Ve a **Configuración del Servidor** → **Roles**
2. Encuentra el rol del bot (tendrá el nombre de tu bot)
3. Asegúrate de que tenga permisos para:
   - Ver los canales donde quieres que notifique
   - Enviar mensajes en esos canales
   - Ver canales de voz (para detectar entradas)

**Nota:** Si el bot no puede ver un canal, no podrá enviar mensajes ahí.

---

## 🧪 Verificar Permisos

Para verificar que el bot tiene los permisos correctos:

1. Ejecuta el bot: `python bot.py`
2. En Discord, escribe: `!test` (en un canal donde el bot pueda escribir)
3. Si responde, los permisos básicos están bien
4. Si no responde, verifica:
   - Que el bot esté en línea
   - Que tenga permisos en ese canal
   - Que el canal no esté silenciado para el bot

---

## 🆘 Problemas Comunes

### "El bot no detecta juegos"
- ✅ Verifica que **Presence Intent** esté habilitado
- ✅ Verifica que **Server Members Intent** esté habilitado
- ✅ Reinicia el bot después de habilitar los intents

### "El bot no puede enviar mensajes"
- ✅ Verifica que tenga **Send Messages** en ese canal
- ✅ Verifica que el canal no esté silenciado para el bot
- ✅ Verifica que el bot tenga permisos de **View Channels**

### "El bot no detecta voice channels"
- ✅ Verifica que tenga **Connect** y **View Channels**
- ✅ Verifica que **Server Members Intent** esté habilitado

---

## 📝 Checklist Final

- [ ] Presence Intent habilitado
- [ ] Server Members Intent habilitado
- [ ] Bot invitado al servidor con permisos correctos
- [ ] Bot tiene permisos en los canales donde debe notificar
- [ ] Bot probado con `!test`

---

**¡Con estos permisos tu bot debería funcionar perfectamente!** 🚀

