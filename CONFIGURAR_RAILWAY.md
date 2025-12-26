# 🚀 Configurar Variables en Railway - GUÍA COMPLETA

## 🎯 Variables que Necesitas Configurar

### 1. DISCORD_BOT_TOKEN (Ya configurado ✅)
Tu token del bot de Discord.

### 2. DISCORD_CHANNEL_ID (NUEVO - IMPORTANTE) ⭐
El ID del canal donde el bot enviará las notificaciones.

**Tu Channel ID:** `1139681313197133874`

---

## 📋 Pasos para Configurar

### Paso 1: Ir a Railway

1. Ve a **https://railway.app/dashboard**
2. Haz clic en tu proyecto **"dsbot"**
3. Haz clic en tu **servicio** (el que está corriendo)

### Paso 2: Abrir Variables

1. En el menú lateral izquierdo, haz clic en **"Variables"**
2. Verás las variables actuales

### Paso 3: Agregar DISCORD_CHANNEL_ID

**Opción A: Raw Editor (Más Rápido)**

1. Haz clic en **"Raw Editor"**
2. Agrega esta línea:
   ```
   DISCORD_CHANNEL_ID=1139681313197133874
   ```
3. Haz clic en **"Save"** o **"Update Variables"**

**Opción B: New Variable**

1. Haz clic en **"New Variable"**
2. En **"Variable Name"** escribe: `DISCORD_CHANNEL_ID`
3. En **"Value"** escribe: `1139681313197133874`
4. Haz clic en **"Add"**

### Paso 4: Esperar Redeploy

- Railway **automáticamente** hará un nuevo deploy
- Espera **1-2 minutos**
- El bot se reiniciará con la nueva configuración

---

## ✅ Verificar que Funcionó

1. Ve a **"Logs"** en Railway
2. Deberías ver:
   ```
   ✅ Canal configurado: 1139681313197133874
   📁 Directorio de datos: /data
   BotName#1234 se ha conectado a Discord!
   ```
3. En Discord, el bot debería estar **en línea** (punto verde)
4. Escribe `!config` en Discord para verificar la configuración

---

## 🎉 ¿Por Qué Esto Es Mejor?

### Antes (Problema):
```
Redeploy → config.json se pierde → Canal = null → Necesitas !setchannel 😢
```

### Ahora (Solución):
```
Redeploy → DISCORD_CHANNEL_ID en ENV sigue ahí → Canal SIEMPRE configurado ✅
```

**Beneficios:**
- ✅ **Nunca más** necesitas hacer `!setchannel` después de un redeploy
- ✅ El canal está **siempre** configurado
- ✅ Configuración **100% robusta**
- ✅ Stats se guardan en Railway Volume (persistentes)

---

## 📊 Nuevas Funcionalidades

### Estadísticas Persistentes

El bot ahora guarda estadísticas de:
- **Juegos:** Cuántas veces cada usuario jugó cada juego
- **Voz:** Cuántas veces cada usuario entró a canales de voz
- **Cooldown:** 10 minutos entre eventos similares (evita spam)

### Nuevos Comandos

```
!stats              - Tus estadísticas
!stats @usuario     - Estadísticas de otro usuario
!topgames           - Top 5 juegos más jugados
!topusers           - Top 5 usuarios más activos
!config             - Ver configuración actual
!toggle             - Activar/desactivar notificaciones
!test               - Mensaje de prueba
```

### Ejemplo de Uso

```
Usuario: !stats
Bot: 
📊 Estadísticas de Usuario1

🎮 Juegos:
• Valorant: 15 veces
• League of Legends: 8 veces

Total juegos: 2

🔊 Voz:
Entradas a canal: 23 veces
Última vez: hace 30 minutos
```

---

## 🔧 Persistencia de Datos

### Railway Volume

El bot ahora usa un **volumen persistente** de Railway:
- **Capacidad:** 500 MB (gratis)
- **Ubicación:** `/data`
- **Archivos guardados:**
  - `/data/config.json` - Configuración
  - `/data/stats.json` - Estadísticas

### ¿Qué Significa?

- ✅ Los datos **NO se pierden** al redeploy
- ✅ Las estadísticas son **permanentes**
- ✅ La configuración es **persistente**

### Espacio Disponible

Para 8 usuarios con ~30 eventos/día:
- **Por día:** ~6 KB
- **Por año:** ~2.2 MB
- **Capacidad:** 500 MB
- **Duración:** ~227 años de datos 😄

---

## 🆘 Troubleshooting

### El bot no se conecta

1. Verifica que ambas variables estén configuradas:
   - `DISCORD_BOT_TOKEN`
   - `DISCORD_CHANNEL_ID`
2. Ve a **Logs** en Railway para ver errores
3. Verifica que los **Intents** estén habilitados en Discord Developer Portal

### No veo estadísticas

1. Las estadísticas se empiezan a registrar después del redeploy
2. Necesitas actividad (jugar juegos, entrar a voz) para generar datos
3. Usa `!stats` para ver tus estadísticas

### El canal no está configurado

1. Verifica que `DISCORD_CHANNEL_ID` esté en Variables de Railway
2. El valor debe ser: `1139681313197133874`
3. Sin comillas, solo el número

---

## 📝 Resumen

**Lo que hiciste:**
1. ✅ Agregaste `DISCORD_CHANNEL_ID` a Railway Variables
2. ✅ Railway hizo redeploy automático
3. ✅ El bot ahora tiene canal permanente

**Lo que ganaste:**
- ✅ Canal nunca se des-configura
- ✅ Estadísticas persistentes
- ✅ Nuevos comandos útiles
- ✅ Sistema robusto y productivo

**¡Tu bot está listo! 🎉**

