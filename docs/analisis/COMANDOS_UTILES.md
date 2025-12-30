# 🛠️ Comandos Útiles - Mantenimiento del Repositorio

## 🧹 Limpieza Automática

### Ejecutar Script de Limpieza
```bash
# Limpieza completa (recomendado)
./cleanup_repo.sh

# Ver qué haría sin ejecutar (dry-run)
bash -x cleanup_repo.sh 2>&1 | grep -E "git|rm|mv"
```

---

## 📊 Análisis del Repositorio

### Tamaño y Estructura
```bash
# Tamaño total del repositorio
du -sh .

# Tamaño por carpeta (top 10)
du -sh * | sort -hr | head -10

# Archivos más grandes
find . -type f -exec du -h {} + | sort -rh | head -20

# Contar archivos por tipo
find . -name "*.py" | wc -l
find . -name "*.md" | wc -l
find . -name "*.sh" | wc -l

# Líneas de código Python
find . -name "*.py" | xargs wc -l | tail -1
```

### Caché Python
```bash
# Encontrar todas las carpetas __pycache__
find . -type d -name "__pycache__"

# Tamaño total de caché
du -sh $(find . -type d -name "__pycache__")

# Eliminar caché local (no afecta Git)
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -name "*.pyc" -delete
find . -name "*.pyo" -delete
```

---

## 🔍 Git - Análisis

### Estado del Repositorio
```bash
# Ver archivos trackeados
git ls-files

# Ver archivos ignorados
git status --ignored

# Tamaño del repositorio
git count-objects -vH

# Archivos más grandes en Git
git rev-list --objects --all | \
  git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' | \
  sed -n 's/^blob //p' | \
  sort --numeric-sort --key=2 | \
  tail -20
```

### Historial de Commits
```bash
# Ver últimos 10 commits
git log --oneline -10

# Ver cambios en archivos específicos
git log --follow -- archivo.py

# Ver quién modificó qué
git blame archivo.py
```

---

## 🧹 Git - Limpieza

### Remover Archivos del Historial
```bash
# Remover __pycache__ del repositorio
git rm -r --cached __pycache__
git rm -r --cached cogs/__pycache__
git rm -r --cached core/__pycache__
git rm -r --cached stats/__pycache__
git rm -r --cached stats/commands/__pycache__
git rm -r --cached stats/data/__pycache__
git rm -r --cached stats/visualization/__pycache__

# Commit
git commit -m "Remove Python cache from repository"
```

### Limpiar Archivos No Trackeados
```bash
# Ver qué se eliminaría (dry-run)
git clean -n

# Eliminar archivos no trackeados
git clean -f

# Eliminar archivos y carpetas no trackeadas
git clean -fd

# Incluir archivos ignorados
git clean -fdx
```

---

## 📦 Organización de Archivos

### Mover Archivos (Git-aware)
```bash
# Mover archivo manteniendo historial
git mv archivo_viejo.py archivo_nuevo.py

# Mover múltiples archivos
git mv ANALISIS_*.md docs/archive/

# Mover y renombrar
git mv stats_viz.py stats/visualization/viz.py
```

### Crear Estructura de Carpetas
```bash
# Crear carpetas necesarias
mkdir -p docs/archive
mkdir -p scripts/setup
mkdir -p scripts/debug

# Mover archivos a carpetas
mv create_env.sh scripts/setup/
mv verify_setup.sh scripts/debug/
```

---

## 🔐 Variables de Entorno

### Crear .env desde Template
```bash
# Copiar template
cp .env.example .env

# Editar con nano
nano .env

# Editar con vim
vim .env

# Verificar variables
cat .env
```

### Verificar Configuración
```bash
# Ver variables de entorno
printenv | grep DISCORD

# Verificar que .env existe
[ -f .env ] && echo "✅ .env existe" || echo "❌ .env no existe"

# Verificar que tiene contenido
[ -s .env ] && echo "✅ .env tiene contenido" || echo "❌ .env está vacío"
```

---

## 🐍 Python - Desarrollo

### Entorno Virtual
```bash
# Crear entorno virtual
python3 -m venv venv

# Activar (Linux/Mac)
source venv/bin/activate

# Activar (Windows)
venv\Scripts\activate

# Desactivar
deactivate

# Instalar dependencias
pip install -r requirements.txt

# Actualizar requirements.txt
pip freeze > requirements.txt
```

### Ejecutar Bot
```bash
# Desarrollo local
python bot.py

# Con logging detallado
python -u bot.py

# En background (Linux/Mac)
nohup python bot.py > bot.log 2>&1 &

# Ver logs en tiempo real
tail -f bot.log
```

### Tests
```bash
# Ejecutar todos los tests
python test_bot.py

# Ejecutar test específico
python -m unittest test_bot.TestClassName

# Con verbose
python test_bot.py -v
```

---

## 🚀 Railway - Deployment

### Logs y Debugging
```bash
# Ver logs en Railway
railway logs

# Ver logs en tiempo real
railway logs --follow

# Ver últimas 100 líneas
railway logs --tail 100

# Filtrar por palabra
railway logs | grep ERROR
```

### Gestión del Proyecto
```bash
# Ver variables de entorno
railway variables

# Agregar variable
railway variables set DISCORD_BOT_TOKEN=tu_token

# Ver estado del deployment
railway status

# Redeploy manual
railway up
```

### Volume (Datos Persistentes)
```bash
# Ver volumen
railway volume list

# Descargar datos del volumen
railway volume download /data ./backup

# Subir datos al volumen
railway volume upload ./backup /data
```

---

## 📊 Monitoreo y Estadísticas

### Uso de Disco
```bash
# Espacio usado por datos
du -sh config.json stats.json

# Proyección de crecimiento
# (asumiendo 8 usuarios activos)
echo "Crecimiento estimado: 10KB/día = 3.6MB/año"

# Espacio disponible en Railway
echo "Límite: 500MB"
echo "Usado: $(du -sh . | cut -f1)"
```

### Performance del Bot
```bash
# Ver procesos Python
ps aux | grep python

# Uso de memoria
ps aux | grep bot.py | awk '{print $6}'

# Uso de CPU
top -p $(pgrep -f bot.py)

# Conexiones de red
netstat -an | grep ESTABLISHED | grep python
```

---

## 🔧 Mantenimiento Regular

### Semanal
```bash
# 1. Limpiar caché local
find . -type d -name "__pycache__" -exec rm -rf {} +

# 2. Verificar tamaño del repo
du -sh .

# 3. Ver logs recientes
tail -100 bot.log

# 4. Backup de datos
cp stats.json stats.json.backup
cp config.json config.json.backup
```

### Mensual
```bash
# 1. Actualizar dependencias
pip list --outdated

# 2. Ver crecimiento de datos
ls -lh stats.json config.json

# 3. Limpiar archivos temporales
git clean -fdx

# 4. Verificar .gitignore
git status --ignored
```

### Anual
```bash
# 1. Revisar documentación obsoleta
ls -lh docs/archive/

# 2. Limpiar historial de Git (si es necesario)
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 3. Actualizar README
nano README.md

# 4. Crear tag de versión
git tag -a v2.0.0 -m "Version 2.0.0"
git push origin v2.0.0
```

---

## 🐛 Debugging

### Verificar Configuración
```bash
# Ejecutar script de verificación
./scripts/debug/verify_setup.sh

# Verificar imports
python -c "import discord; print(discord.__version__)"

# Verificar permisos
ls -la bot.py

# Verificar encoding
file -i bot.py
```

### Errores Comunes
```bash
# Error: ModuleNotFoundError
pip install -r requirements.txt

# Error: Permission denied
chmod +x script.sh

# Error: Token inválido
cat .env | grep DISCORD_BOT_TOKEN

# Error: Canal no encontrado
python -c "from core.persistence import get_channel_id; print(get_channel_id())"
```

---

## 📝 Git - Workflows

### Commit y Push
```bash
# Ver cambios
git status

# Agregar archivos
git add .

# Commit con mensaje
git commit -m "Descripción del cambio"

# Push a GitHub
git push origin main

# Commit y push en un comando
git add . && git commit -m "Mensaje" && git push
```

### Branches
```bash
# Crear branch
git checkout -b feature/nueva-funcionalidad

# Cambiar de branch
git checkout main

# Ver branches
git branch -a

# Merge branch
git checkout main
git merge feature/nueva-funcionalidad

# Eliminar branch
git branch -d feature/nueva-funcionalidad
```

### Deshacer Cambios
```bash
# Deshacer cambios en archivo (no commiteado)
git checkout -- archivo.py

# Deshacer último commit (mantener cambios)
git reset --soft HEAD~1

# Deshacer último commit (descartar cambios)
git reset --hard HEAD~1

# Revertir commit específico
git revert <commit-hash>
```

---

## 🎯 Comandos del Bot (Discord)

### Configuración
```
!setchannel         - Configurar canal de notificaciones
!setstatschannel    - Configurar canal de estadísticas
!channels           - Ver configuración actual
!toggle             - Activar/desactivar notificaciones
!config             - Ver configuración completa
```

### Estadísticas
```
!stats [@user]      - Ver estadísticas de usuario
!topgames           - Ranking de juegos
!topusers           - Usuarios más activos
!voicetime [@user]  - Tiempo en voz
!voicetop           - Ranking por tiempo en voz
```

### Utilidades
```
!bothelp            - Ayuda completa
!export json        - Exportar datos en JSON
!export csv         - Exportar datos en CSV
!test               - Mensaje de prueba
```

---

## 🔗 Enlaces Útiles

### Documentación
- [README.md](README.md) - Documentación principal
- [ARQUITECTURA.md](ARQUITECTURA.md) - Arquitectura técnica
- [ANALISIS_ESTRUCTURA_Y_MEJORAS.md](ANALISIS_ESTRUCTURA_Y_MEJORAS.md) - Análisis completo

### Railway
- [Dashboard](https://railway.app/dashboard)
- [Documentación](https://docs.railway.app/)
- [Status](https://railway.app/status)

### Discord
- [Developer Portal](https://discord.com/developers/applications)
- [discord.py Docs](https://discordpy.readthedocs.io/)

---

## 💡 Tips y Trucos

### Alias Útiles (agregar a ~/.bashrc o ~/.zshrc)
```bash
# Alias para comandos frecuentes
alias bot-start='python bot.py'
alias bot-logs='tail -f bot.log'
alias bot-test='python test_bot.py'
alias bot-clean='find . -type d -name "__pycache__" -exec rm -rf {} +'
alias bot-size='du -sh .'
alias bot-backup='cp stats.json stats.json.backup && cp config.json config.json.backup'

# Git aliases
alias gs='git status'
alias ga='git add .'
alias gc='git commit -m'
alias gp='git push'
alias gl='git log --oneline -10'
```

### Scripts Rápidos
```bash
# Backup rápido
tar -czf backup-$(date +%Y%m%d).tar.gz stats.json config.json

# Ver crecimiento diario de datos
ls -lht stats.json | head -5

# Contar eventos en stats.json
jq '.users | length' stats.json
jq '.cooldowns | length' stats.json

# Ver usuarios más activos
jq '.users | to_entries | sort_by(.value.messages.count) | reverse | .[0:5] | .[].key' stats.json
```

---

**Última actualización:** 30 de Diciembre, 2025

