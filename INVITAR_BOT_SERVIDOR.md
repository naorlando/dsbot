# 🤖 Guía: Invitar el Bot a un Servidor de Discord

## 📋 Requisitos Previos

- ✅ Bot creado en Discord Developer Portal
- ✅ Privileged Intents activados (PRESENCE INTENT y SERVER MEMBERS INTENT)
- ✅ Token configurado en Railway

## 🚀 Pasos para Invitar el Bot

### Paso 1: Ir a Discord Developer Portal

1. Ve a: **https://discord.com/developers/applications**
2. **Inicia sesión** con tu cuenta de Discord
3. Selecciona tu aplicación (bot)

### Paso 2: Configurar OAuth2 URL

1. En el menú lateral izquierdo, haz clic en **"OAuth2"**
2. Luego haz clic en **"URL Generator"** (en el submenú)

### Paso 3: Seleccionar Scopes (Permisos de Aplicación)

En la sección **"SCOPES"**, marca:

- ✅ **bot** (obligatorio)
- ✅ **applications.commands** (opcional, para comandos slash)

### Paso 4: Seleccionar Bot Permissions (Permisos del Bot)

En la sección **"BOT PERMISSIONS"**, marca estos permisos:

**Permisos Básicos (Mínimas necesarias):**
- ✅ **View Channels** (Ver canales)
- ✅ **Send Messages** (Enviar mensajes)
- ✅ **Read Message History** (Leer historial de mensajes)

**Permisos Recomendadas (Para mejor funcionamiento):**
- ✅ **View Channels**
- ✅ **Send Messages**
- ✅ **Read Message History**
- ✅ **Embed Links** (Incluir enlaces embebidos)
- ✅ **Attach Files** (Adjuntar archivos)
- ✅ **Use External Emojis** (Usar emojis externos)

**Permisos Opcionales (Si quieres más funcionalidades):**
- ✅ **Manage Messages** (Gestionar mensajes)
- ✅ **Add Reactions** (Agregar reacciones)

### Paso 5: Copiar la URL de Invitación

1. Al final de la página verás una sección **"GENERATED URL"**
2. Se generará automáticamente una URL como:
   ```
   https://discord.com/api/oauth2/authorize?client_id=TU_CLIENT_ID&permissions=PERMISSIONS&scope=bot%20applications.commands
   ```
3. **Copia esta URL** (haz clic en "Copy" o selecciónala y copia)

### Paso 6: Abrir la URL en el Navegador

1. Pega la URL copiada en tu navegador
2. Se abrirá una página de Discord para seleccionar el servidor

### Paso 7: Seleccionar el Servidor

1. En el dropdown **"Add to Server"**, selecciona tu servidor de prueba
2. Haz clic en **"Continue"**

### Paso 8: Autorizar Permisos

1. Verás una lista de permisos que el bot solicita
2. **Revisa los permisos** (deben coincidir con los que seleccionaste)
3. Haz clic en **"Authorize"**

### Paso 9: Verificar que el Bot Está en el Servidor

1. Ve a tu servidor de Discord
2. En la lista de miembros (lado derecho), deberías ver tu bot
3. El bot debería aparecer como **"offline"** inicialmente
4. Después de unos segundos, debería cambiar a **"online"** (punto verde)

## ✅ Verificación Final

### Verificar que el Bot Funciona

1. En cualquier canal de texto, escribe: `!test`
2. El bot debería responder: `✅ Mensaje de prueba enviado!`
3. Deberías ver un mensaje en el canal configurado

### Configurar el Canal de Notificaciones

1. Ve al canal donde quieres recibir notificaciones (ej: `#general`)
2. Escribe: `!setchannel`
3. El bot responderá: `✅ Canal de notificaciones configurado: #general`

### Probar las Notificaciones

1. **Prueba de voz:**
   - Entra a un canal de voz
   - Deberías ver una notificación en el canal configurado

2. **Prueba de juego:**
   - Inicia un juego
   - Deberías ver una notificación cuando empieces a jugar

## 🔧 Troubleshooting

### "El bot no aparece en el servidor"

- Verifica que completaste todos los pasos
- Asegúrate de haber hecho clic en "Authorize"
- Recarga Discord (Ctrl+R o Cmd+R)

### "El bot aparece pero está offline"

- Espera 30-60 segundos (Railway puede tardar en conectar)
- Revisa los logs de Railway para ver si hay errores
- Verifica que el token esté correcto en Railway

### "El bot no responde a comandos"

- Verifica que el bot tenga permisos para:
  - Ver canales
  - Enviar mensajes
  - Leer historial de mensajes
- Verifica que estés escribiendo el comando en un canal donde el bot pueda ver

### "Error: Missing Permissions"

- Ve a Configuración del Servidor → Roles
- Selecciona el rol del bot
- Verifica que tenga los permisos necesarios
- O invita el bot nuevamente con más permisos

## 📸 Ubicación Visual

```
Discord Developer Portal
│
├── Applications
│   └── Tu Aplicación
│       │
│       ├── Bot
│       ├── OAuth2 ← AQUÍ
│       │   └── URL Generator ← AQUÍ
│       │       │
│       │       ├── SCOPES
│       │       │   └── ✅ bot
│       │       │
│       │       ├── BOT PERMISSIONS
│       │       │   ├── ✅ View Channels
│       │       │   ├── ✅ Send Messages
│       │       │   └── ✅ Read Message History
│       │       │
│       │       └── GENERATED URL ← Copia esta URL
│       │
│       └── ...
```

## 🎯 Permisos Mínimos Recomendados

Para que el bot funcione correctamente, necesita estos permisos mínimos:

```
✅ View Channels          (Ver canales)
✅ Send Messages          (Enviar mensajes)
✅ Read Message History   (Leer historial)
✅ Embed Links            (Enlaces embebidos)
```

**Código de permisos:** `277025508160` (puedes usar este número directamente)

## 🔗 Generar URL Rápida

Si ya tienes el Client ID de tu bot, puedes generar la URL manualmente:

```
https://discord.com/api/oauth2/authorize?client_id=TU_CLIENT_ID&permissions=277025508160&scope=bot
```

Reemplaza `TU_CLIENT_ID` con el Client ID de tu bot (lo encuentras en OAuth2 → General).

---

**¡Una vez que el bot esté en el servidor, debería conectarse automáticamente y estar listo para usar!** 🚀

