# 🔐 Permisos del Bot - Guía Rápida

## ⚡ Permisos Esenciales

### En Discord Developer Portal:

1. Ve a: https://discord.com/developers/applications
2. Selecciona tu aplicación "Activity Bot"
3. Ve a **"Bot"** en el menú lateral

### Privileged Gateway Intents (OBLIGATORIO):

Habilita estos dos:
- ✅ **PRESENCE INTENT** 
- ✅ **SERVER MEMBERS INTENT**

**Sin estos, el bot NO funcionará.**

---

### Permisos del Bot (OAuth2 URL Generator):

1. Ve a **"OAuth2"** → **"URL Generator"**

2. En **Scopes**, marca:
   - ✅ `bot`
   - ✅ `applications.commands` (opcional pero recomendado)

3. En **Bot Permissions**, marca estos permisos:

**Mínimos Necesarios:**
- ✅ View Channels
- ✅ Send Messages
- ✅ Read Message History
- ✅ Connect (para detectar voice channels)

**Recomendados Adicionales:**
- ✅ Embed Links
- ✅ Use External Emojis

4. **Copia la URL generada** y ábrela en tu navegador
5. Selecciona tu servidor y autoriza

---

## 📋 Resumen Visual

```
Discord Developer Portal
├── Bot
│   └── Privileged Gateway Intents
│       ✅ Presence Intent
│       ✅ Server Members Intent
│
└── OAuth2 → URL Generator
    ├── Scopes
    │   ✅ bot
    │   ✅ applications.commands
    │
    └── Bot Permissions
        ✅ View Channels
        ✅ Send Messages
        ✅ Read Message History
        ✅ Connect
        ✅ Embed Links (recomendado)
```

---

## ✅ Checklist

- [ ] Presence Intent habilitado
- [ ] Server Members Intent habilitado
- [ ] Bot invitado al servidor con permisos correctos
- [ ] Bot probado con `!test` en Discord

---

**¡Con estos permisos tu bot funcionará perfectamente!** 🚀

