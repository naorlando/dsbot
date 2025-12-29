# 🎮 Comandos Nuevos - Guía Rápida

## 📊 Rankings Separados (Lo Más Importante)

### `!topgamers [period]` 🥇
**Ranking de jugadores por tiempo de juego**

```
!topgamers          → Histórico completo
!topgamers today    → Solo hoy
!topgamers week     → Última semana
!topgamers month    → Último mes
```

**Output mejorado:**
```
╔══════════════════════════════════════════════════════════════════╗
║            🎮 TOP GAMERS - ÚLTIMO MES                            ║
╠══════════════════════════════════════════════════════════════════╣
║ 🥇  Pino                  ████████████████████  120h   (45.2%) ║
║     └─ 85 sesiones • 12 juegos                                  ║
║ 🥈  Zamu                  ███████████████      90h    (33.8%) ║
║     └─ 65 sesiones • 8 juegos                                   ║
║ 🥉  Zeta                  ██████████          56h    (21.0%) ║
║     └─ 42 sesiones • 15 juegos                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

---

### `!topvoice [period]` 🔊
**Ranking de usuarios por tiempo en voz**

```
!topvoice          → Histórico completo
!topvoice week     → Última semana
!topvoice month    → Último mes
```

---

### `!topchat` 💬
**Ranking de usuarios por mensajes**

```
!topchat
```

---

## 🎮 Comandos de Juegos

### `!topgames [sort]` (MEJORADO)
**Lista de juegos más populares**

```
!topgames          → Por tiempo jugado
!topgames time     → Por tiempo jugado
!topgames players  → Por cantidad de jugadores
!topgames sessions → Por número de sesiones
```

**Ejemplo output:**
```
╔══════════════════════════════════════════════════════════════════╗
║                 🎮 TOP JUEGOS - POR JUGADORES                    ║
╚══════════════════════════════════════════════════════════════════╝
🥇 League of Legends      ██████████████████████████████   12 jugadores
    └─ 450h • 320 sesiones
🥈 Minecraft              ████████████████████          10 jugadores
    └─ 380h • 250 sesiones
🥉 Among Us               ███████████████              8 jugadores
    └─ 120h • 180 sesiones
```

---

### `!topgame <juego>` 🎯 (NUEVO)
**Estadísticas detalladas de un juego específico**

```
!topgame Hades
!topgame "League of Legends"
```

**Muestra:**
- ⏱️ Tiempo total jugado
- 🎯 Número de sesiones
- 👥 Cantidad de jugadores
- 📅 Primera y última vez jugado
- 🏆 Top 5 jugadores del juego

---

### `!mygames` 🎮 (NUEVO)
**Tus juegos más jugados**

```
!mygames
```

Muestra tu top 10 personal con tiempo y sesiones.

---

## 📊 Comandos de Usuario

### `!stats [@usuario]` (MEJORADO)
**Perfil completo de estadísticas**

```
!stats           → Tus propias stats
!stats @Pino     → Stats de Pino
```

**Muestra:**
- 🎮 **Gaming**: Tiempo total, sesiones, top 3 juegos
- 🔊 **Voz**: Tiempo total, conexiones, última actividad
- 💬 **Chat**: Mensajes, promedio de caracteres
- 😄 **Reacciones**: Total de reacciones

---

### `!mystats` ⚡ (NUEVO)
**Atajo rápido para tus stats**

```
!mystats    (= !stats sin argumentos)
```

---

### `!compare @usuario` 🆚 (MEJORADO)
**Compara tus stats con otro usuario**

```
!compare @Pino
```

**Output visual mejorado:**
```
╔══════════════════════════════════════════════════════════════╗
║ 🆚 Zamu vs Pino                                              ║
╚══════════════════════════════════════════════════════════════╝
║ Gaming                                                       ║
║   🟦 Zamu  ████████████████████  120h                        ║
║   🟩 Pino  ████████████          85h                         ║
╠──────────────────────────────────────────────────────────────╣
║ Voz                                                          ║
║   🟦 Zamu  ██████████████        45h                         ║
║   🟩 Pino  ████████████████████  60h                         ║
╠──────────────────────────────────────────────────────────────╣
```

---

## 😄 Comandos Sociales

### `!topreactions` 
**Top por reacciones enviadas**

### `!topstickers`
**Top por stickers enviados**

---

## 👥 Comandos de Parties (PRÓXIMAMENTE)

### `!partymaster`
Top usuarios por parties formadas

### `!partywith [@usuario]`
Con quién has jugado más en party

### `!partygames`
Juegos más populares para parties

> ⚠️ **Nota**: Estos comandos están listos pero requieren datos de parties en stats.json

---

## ⚠️ Comando Deprecado

### `!topusers` ❌
**YA NO FUNCIONA**

Reemplazado por:
- `!topgamers [period]` - Para gaming
- `!topvoice [period]` - Para voz
- `!topchat` - Para mensajes

Al ejecutar `!topusers` ahora muestra un mensaje indicando los nuevos comandos.

---

## 💡 Tips

### Períodos Disponibles
- `today` - Solo hoy
- `week` - Última semana
- `month` - Último mes
- `all` - Todo el historial (default)

### Búsqueda de Juegos
- Case-insensitive
- Si no encuentra el juego exacto, sugiere similares
- Usa `!topgames` para ver la lista completa

### Comparaciones
- Solo puedes compararte con otros usuarios
- Muestra 3 métricas principales: Gaming, Voz, Mensajes

---

## 🎨 Estilos de Gráficos

Los nuevos gráficos incluyen:
- ✅ Medallas (🥇🥈🥉) para top 3
- ✅ Barras con gradiente
- ✅ Porcentajes
- ✅ Información extra (sesiones, jugadores, etc.)
- ✅ Boxes con marcos ASCII copados
- ✅ Colores diferenciados (🟦🟩) para comparaciones

---

## 📱 Ejemplos de Uso

### Caso 1: Ver el ranking del mes
```
!topgamers month
```

### Caso 2: Buscar stats de un juego
```
!topgame Hades
```

### Caso 3: Compararse con un amigo
```
!compare @Zeta
```

### Caso 4: Ver tus juegos favoritos
```
!mygames
```

### Caso 5: Ver perfil completo de alguien
```
!stats @Pino
```

---

**¡Todos los comandos están listos para usar! 🚀**

