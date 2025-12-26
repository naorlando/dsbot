# 📊 Guía Completa de Estadísticas

## 🎯 Comandos Disponibles

### Menú Interactivo

```
!statsmenu
```

Abre un menú interactivo con múltiples visualizaciones:
- 📊 Vista General - Resumen completo
- 🎮 Ranking Juegos - Gráfico de juegos más jugados
- 🔊 Ranking Voz - Usuarios más activos en voz
- 👥 Ranking Usuarios - Actividad total por usuario
- 📈 Línea de Tiempo - Actividad de los últimos 7 días

**Filtros de Período:**
- 📅 Hoy
- 📆 Última Semana
- 🗓️ Último Mes
- 📚 Histórico

---

### Comandos Directos

#### Ranking de Juegos
```
!statsgames [período]
```

Muestra gráfico de barras con los juegos más jugados.

**Ejemplos:**
```
!statsgames           # Histórico
!statsgames today     # Solo hoy
!statsgames week      # Última semana
!statsgames month     # Último mes
```

**Salida:**
```
🎮 Ranking de Juegos - Última Semana
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Valorant     ████████████████ 45
League       ████████████ 32
Minecraft    ████████ 21
Fortnite     █████ 15
```

---

#### Ranking de Voz
```
!statsvoice [período]
```

Muestra gráfico de usuarios más activos en canales de voz.

**Ejemplos:**
```
!statsvoice
!statsvoice week
```

**Salida:**
```
🔊 Ranking de Actividad de Voz - Última Semana
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Usuario1     ████████████████████ 30
Usuario2     ████████████████ 25
Usuario3     ████████████ 20
```

---

#### Línea de Tiempo
```
!timeline [días]
```

Muestra actividad diaria de los últimos N días (1-30).

**Ejemplos:**
```
!timeline        # Últimos 7 días
!timeline 14     # Últimos 14 días
```

**Salida:**
```
📈 Actividad (7 días)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lun 20/12  ████████ 12
Mar 21/12  ██████████ 15
Mié 22/12  ████████████ 18
Jue 23/12  ██████ 9
Vie 24/12  ██████████████ 21
Sáb 25/12  ████████████████████ 30
Dom 26/12  ██████████████ 20
```

---

#### Comparar Usuarios
```
!compare @usuario1 @usuario2
```

Compara estadísticas entre dos usuarios.

**Ejemplo:**
```
!compare @Juan @María
```

**Salida:**
```
📊 Comparación: Juan vs María
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎮 Sesiones de Juego:
Juan: 45
María: 38
👑 Ganador: Juan

🔊 Entradas a Voz:
Juan: 23
María: 30
👑 Ganador: María

🏆 Actividad Total:
Juan: 68
María: 68
👑 Ganador General: Empate
```

---

#### Estadísticas de Usuario
```
!statsuser [@usuario]
```

Muestra estadísticas detalladas de un usuario específico.

**Ejemplos:**
```
!statsuser           # Tus estadísticas
!statsuser @Juan     # Estadísticas de Juan
```

**Salida:**
```
📊 Estadísticas Detalladas: Juan

🎮 Juegos (Total: 45 sesiones)
• Valorant: 20 veces (desde 01/12/2025)
• League of Legends: 15 veces (desde 05/12/2025)
• Minecraft: 10 veces (desde 10/12/2025)

Juegos únicos: 3

🔊 Actividad de Voz
Entradas: 23 veces
Última vez: hace 30 minutos
```

---

## 📈 Características

### Cooldown de 10 Minutos
- Evita spam en las estadísticas
- Si juegas el mismo juego < 10 min después, no cuenta como nueva sesión
- Si entras al mismo canal < 10 min después, no cuenta

### Persistencia
- Todas las estadísticas se guardan en `/data/stats.json`
- No se pierden al redeploy de Railway
- Historial completo desde que se activó el bot

### Filtros de Período
- **Hoy**: Solo actividad del día actual
- **Semana**: Últimos 7 días
- **Mes**: Últimos 30 días
- **Histórico**: Todos los datos

---

## 🎨 Visualizaciones

### Gráficos de Barras ASCII
- Ligeros y rápidos
- No requieren librerías externas
- Se ven bien en Discord

### Menú Interactivo
- Select menus para elegir visualización
- Filtros de período dinámicos
- Timeout de 5 minutos

---

## 💾 Estructura de Datos

```json
{
  "users": {
    "user_id": {
      "username": "Usuario1",
      "games": {
        "Valorant": {
          "count": 15,
          "first_played": "2025-12-01T10:00:00Z",
          "last_played": "2025-12-26T20:00:00Z"
        }
      },
      "voice": {
        "count": 23,
        "last_join": "2025-12-26T19:00:00Z"
      }
    }
  },
  "cooldowns": {
    "user_id:game:Valorant": "2025-12-26T20:10:00Z",
    "user_id:voice": "2025-12-26T19:10:00Z"
  }
}
```

---

## 🧪 Tests

Ejecutar tests:
```bash
python test_bot.py
```

**Cobertura:**
- ✅ Gráficos ASCII
- ✅ Línea de tiempo
- ✅ Comparaciones
- ✅ Filtros por período
- ✅ Cálculo de actividad diaria
- ✅ Estructura de datos
- ✅ Workflow completo

**Resultado:**
```
Tests ejecutados: 21
✅ Exitosos: 21
❌ Fallidos: 0
💥 Errores: 0
```

---

#### Exportar Estadísticas
```
!export [formato]
```

Exporta todas las estadísticas a un archivo.

**Formatos disponibles:**
- `json` - Formato JSON (por defecto)
- `csv` - Formato CSV compatible con Excel

**Ejemplos:**
```
!export           # JSON por defecto
!export json      # Formato JSON
!export csv       # Formato CSV
```

**Salida:**
- Archivo enviado directamente en Discord
- Nombre: `stats_20251226_200000.json` o `.csv`
- Se limpia automáticamente después de enviar

---

#### Ayuda de Comandos
```
!help [comando]
```

Muestra la lista completa de comandos o ayuda específica.

**Aliases:** `!ayuda`, `!comandos`

**Ejemplos:**
```
!help             # Lista todos los comandos
!help stats       # Ayuda específica de !stats
!help export      # Ayuda específica de !export
```

---

## 📊 Ejemplos de Uso

### Caso 1: Ver actividad de la semana
```
Usuario: !statsmenu
Bot: [Menú interactivo]
Usuario: [Selecciona "Ranking Juegos" y "Última Semana"]
Bot: [Muestra gráfico de juegos de la semana]
```

### Caso 2: Comparar dos jugadores
```
Usuario: !compare @Pedro @Ana
Bot: [Muestra comparación detallada]
```

### Caso 3: Ver tu progreso
```
Usuario: !statsuser
Bot: [Muestra tus estadísticas completas]
```

### Caso 4: Línea de tiempo del mes
```
Usuario: !timeline 30
Bot: [Muestra gráfico de 30 días]
```

---

## 🎯 Tips

1. **Usa el menú interactivo** (`!statsmenu`) para explorar diferentes vistas
2. **Filtra por período** para ver actividad reciente
3. **Compara usuarios** para competencias amistosas
4. **Revisa la línea de tiempo** para ver tendencias

---

## 🔧 Configuración

Las estadísticas se activan automáticamente cuando:
- ✅ Alguien empieza a jugar un juego
- ✅ Alguien entra a un canal de voz

**Cooldown:** 10 minutos entre eventos similares

**Almacenamiento:** Railway Volume persistente (500 MB)

---

## 📝 Notas

- Las estadísticas son por servidor
- Solo se registran usuarios (no bots)
- Los datos son persistentes y no se pierden
- El cooldown evita spam y datos duplicados

---

**¡Disfruta explorando tus estadísticas!** 📊🎮🔊

