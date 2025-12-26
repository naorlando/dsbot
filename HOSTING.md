# Guía Completa: Hosting Gratuito para Bot de Discord Open Source

## 🏆 Mejores Opciones Gratuitas (2024)

### 1. Railway.app ⭐ RECOMENDADO

**Ventajas:**
- ✅ **500 horas/mes GRATIS** (suficiente para 24/7)
- ✅ **Siempre activo** - No se duerme
- ✅ **Despliegue automático** desde GitHub
- ✅ **Muy fácil de usar** - Interfaz intuitiva
- ✅ **Sin configuración compleja**
- ✅ **Logs en tiempo real**
- ✅ **Variables de entorno fáciles**

**Limitaciones:**
- 500 horas/mes (suficiente para un mes completo)
- Puede requerir tarjeta de crédito (pero no cobra si no excedes el límite)

**Cómo usar:**
1. Ve a [railway.app](https://railway.app) y crea cuenta (puedes usar GitHub)
2. Haz clic en "New Project"
3. Selecciona "Deploy from GitHub repo" (o "Empty Project" y sube archivos)
4. Si usas GitHub:
   - Conecta tu repositorio
   - Railway detectará automáticamente que es Python
   - Configura el comando de inicio: `python bot.py`
5. Ve a "Variables" y agrega:
   - `DISCORD_BOT_TOKEN` = `tu_token`
6. El bot se desplegará automáticamente y estará siempre activo

**Costo:** Gratis (500 horas/mes)

---

### 2. Render.com ⭐ ALTERNATIVA EXCELENTE

**Ventajas:**
- ✅ **100% GRATIS** - Sin tarjeta de crédito
- ✅ **Siempre activo** - Se reactiva automáticamente si se duerme
- ✅ **Despliegue desde GitHub** automático
- ✅ **SSL automático**
- ✅ **Muy fácil de configurar**

**Limitaciones:**
- Se "duerme" después de 15 minutos de inactividad
- Se reactiva automáticamente cuando alguien lo usa (tarda ~30 segundos)
- Para bots de Discord esto NO es problema (siempre hay actividad)

**Cómo usar:**
1. Ve a [render.com](https://render.com) y crea cuenta
2. Haz clic en "New" > "Web Service"
3. Conecta tu repositorio de GitHub o sube archivos manualmente
4. Configura:
   - **Name:** `discord-bot` (o el que quieras)
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
5. En "Environment Variables", agrega:
   - `DISCORD_BOT_TOKEN` = `tu_token`
6. Haz clic en "Create Web Service"
7. Espera a que termine el despliegue (2-3 minutos)

**Costo:** 100% Gratis

---

### 3. Replit.com

**Ventajas:**
- ✅ **100% GRATIS**
- ✅ **Editor integrado** - Puedes editar código directamente
- ✅ **Muy fácil** para principiantes
- ✅ **Sin configuración**

**Limitaciones:**
- ⚠️ **Se detiene si cierras la pestaña** del navegador
- ⚠️ **Requiere mantener activo** o usar UptimeRobot
- ⚠️ **Recursos limitados**

**Cómo usar:**
1. Ve a [replit.com](https://replit.com) y crea cuenta
2. Crea nuevo proyecto "Python"
3. Sube tus archivos o pégalos
4. En "Secrets" (icono de candado), agrega:
   - `DISCORD_BOT_TOKEN` = `tu_token`
5. Ejecuta el bot
6. **IMPORTANTE:** Para mantenerlo activo 24/7:
   - Usa [UptimeRobot](https://uptimerobot.com) (gratis)
   - Configura un monitor HTTP que haga ping cada 5 minutos
   - O usa el servicio "Always On" de Replit (requiere pago)

**Costo:** Gratis (pero requiere trabajo extra para mantener activo)

---

### 4. Fly.io

**Ventajas:**
- ✅ **3 VMs pequeñas GRATIS**
- ✅ **Siempre activo**
- ✅ **Muy rápido**
- ✅ **Escalable**

**Limitaciones:**
- Requiere tarjeta de crédito (pero no cobra si no excedes límites)
- Configuración más compleja

**Cómo usar:**
1. Instala Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Crea cuenta en [fly.io](https://fly.io)
3. Ejecuta: `fly launch`
4. Sigue las instrucciones
5. Configura variables: `fly secrets set DISCORD_BOT_TOKEN=tu_token`

**Costo:** Gratis (3 VMs pequeñas)

---

### 5. Oracle Cloud (VPS Gratuito)

**Ventajas:**
- ✅ **VPS completo GRATIS** (siempre activo)
- ✅ **Recursos generosos** (1 CPU, 1GB RAM)
- ✅ **Control total**
- ✅ **Sin límites de tiempo**

**Limitaciones:**
- ⚠️ **Configuración más compleja**
- ⚠️ **Requiere conocimientos de Linux**
- ⚠️ **Proceso de registro más largo**

**Cómo usar:**
1. Crea cuenta en [Oracle Cloud](https://www.oracle.com/cloud/free/)
2. Crea una instancia "Always Free"
3. Conéctate por SSH
4. Instala Python y dependencias
5. Clona tu repositorio
6. Configura systemd para mantener el bot activo

**Costo:** 100% Gratis (VPS completo)

---

## 📊 Comparación Rápida

| Plataforma | Gratis | Siempre Activo | Facilidad | Mejor Para |
|------------|-------|----------------|----------|------------|
| **Railway** | ✅ (500h/mes) | ✅ Sí | ⭐⭐⭐⭐⭐ | Principiantes |
| **Render** | ✅ Sí | ✅ Auto-reactiva | ⭐⭐⭐⭐⭐ | Principiantes |
| **Replit** | ✅ Sí | ⚠️ Con trabajo | ⭐⭐⭐⭐ | Aprendizaje |
| **Fly.io** | ✅ Sí | ✅ Sí | ⭐⭐⭐ | Intermedios |
| **Oracle Cloud** | ✅ Sí | ✅ Sí | ⭐⭐ | Avanzados |

---

## 🚀 Guía Paso a Paso: Railway (Recomendado)

### Paso 1: Preparar el código

Asegúrate de tener estos archivos en tu repositorio:
- `bot.py`
- `requirements.txt`
- `.gitignore` (con `.env` incluido)

### Paso 2: Crear cuenta en Railway

1. Ve a [railway.app](https://railway.app)
2. Haz clic en "Login" y usa tu cuenta de GitHub
3. Autoriza Railway para acceder a tus repositorios

### Paso 3: Desplegar

1. En Railway, haz clic en "New Project"
2. Selecciona "Deploy from GitHub repo"
3. Elige tu repositorio `dsbot`
4. Railway detectará automáticamente que es Python

### Paso 4: Configurar

1. Haz clic en tu servicio
2. Ve a la pestaña "Variables"
3. Agrega:
   ```
   DISCORD_BOT_TOKEN = tu_token_aqui
   ```
4. Railway reiniciará automáticamente el bot

### Paso 5: Verificar

1. Ve a la pestaña "Deployments"
2. Verifica que el estado sea "Active"
3. Revisa los logs para confirmar que el bot se conectó
4. En Discord, verifica que el bot esté en línea

**¡Listo! Tu bot está en línea 24/7**

---

## 🚀 Guía Paso a Paso: Render (Alternativa)

### Paso 1: Preparar el código

Mismo que Railway - asegúrate de tener `bot.py` y `requirements.txt`

### Paso 2: Crear cuenta en Render

1. Ve a [render.com](https://render.com)
2. Crea cuenta (puedes usar GitHub)

### Paso 3: Crear servicio

1. Haz clic en "New" > "Web Service"
2. Conecta tu repositorio de GitHub
3. Selecciona tu repositorio `dsbot`

### Paso 4: Configurar

1. **Name:** `discord-bot` (o el que prefieras)
2. **Region:** Elige el más cercano
3. **Branch:** `main` (o tu rama principal)
4. **Root Directory:** (déjalo vacío)
5. **Runtime:** `Python 3`
6. **Build Command:** `pip install -r requirements.txt`
7. **Start Command:** `python bot.py`

### Paso 5: Variables de entorno

1. En "Environment Variables", haz clic en "Add Environment Variable"
2. Agrega:
   - Key: `DISCORD_BOT_TOKEN`
   - Value: `tu_token`

### Paso 6: Desplegar

1. Haz clic en "Create Web Service"
2. Espera 2-3 minutos mientras Render construye y despliega
3. Revisa los logs para verificar que todo está bien

**¡Listo! Tu bot está en línea**

---

## 🔧 Mantener el Bot Activo (Solo para Replit)

Si usas Replit, necesitas mantenerlo activo:

### Opción 1: UptimeRobot (Gratis)

1. Ve a [uptimerobot.com](https://uptimerobot.com)
2. Crea cuenta gratuita
3. Haz clic en "Add New Monitor"
4. Configura:
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** Discord Bot
   - **URL:** La URL de tu Repl (ej: `https://tu-repl.repl.co`)
   - **Monitoring Interval:** 5 minutes
5. Guarda y listo

### Opción 2: Servicio "Always On" de Replit

- Requiere plan de pago ($7/mes)
- Mantiene el bot activo sin necesidad de pings

---

## 📝 Checklist Antes de Publicar

- [ ] El bot funciona localmente
- [ ] El archivo `.env` está en `.gitignore`
- [ ] El token NO está en el código
- [ ] `requirements.txt` está actualizado
- [ ] Los Intents están habilitados en Discord Developer Portal:
  - [ ] Presence Intent
  - [ ] Server Members Intent
- [ ] El bot tiene permisos en tu servidor de Discord

---

## 🛡️ Seguridad

### ✅ HACER:
- Usar variables de entorno para el token
- Mantener el token privado
- Usar `.gitignore` para `.env`
- Revisar logs regularmente

### ❌ NO HACER:
- Subir el token al repositorio
- Compartir el token públicamente
- Hardcodear el token en el código
- Ignorar errores en los logs

---

## 🆘 Solución de Problemas

### El bot no se conecta
1. Verifica que el token sea correcto
2. Revisa los logs del servicio
3. Asegúrate de que los Intents estén habilitados

### El bot se desconecta frecuentemente
1. Revisa los logs para ver errores
2. Verifica que no haya problemas de memoria
3. Considera usar Railway o Render (más estables)

### Error: "Module not found"
1. Verifica que `requirements.txt` tenga todas las dependencias
2. Revisa que el Build Command instale las dependencias

---

## 💡 Recomendación Final

**Para la mayoría de usuarios:** Usa **Railway** o **Render**
- Son las más fáciles de usar
- Mantienen el bot siempre activo
- Tienen buena documentación
- Son confiables y gratuitas

**Para aprender:** Usa **Replit**
- Editor integrado
- Fácil de experimentar
- Buena para desarrollo

**Para control total:** Usa **Oracle Cloud** o **Fly.io**
- Más recursos
- Más control
- Requiere más conocimiento técnico

---

## 📚 Recursos Adicionales

- [Railway Docs](https://docs.railway.app)
- [Render Docs](https://render.com/docs)
- [Discord.py Docs](https://discordpy.readthedocs.io/)
- [Discord Developer Portal](https://discord.com/developers)

---

**¿Necesitas ayuda?** Revisa los logs de tu servicio o consulta la documentación de la plataforma que elegiste.

