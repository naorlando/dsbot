#!/bin/bash

# 🧹 Script de Limpieza del Repositorio
# Implementa la Fase 1 del análisis de mejoras
# Tiempo estimado: 30 minutos
# Ahorro: ~1.1MB (25% del repo)

set -e  # Exit on error

echo "🧹 Iniciando limpieza del repositorio..."
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para confirmar acción
confirm() {
    read -p "$1 (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "${RED}❌ Cancelado${NC}"
        exit 1
    fi
}

echo "${YELLOW}⚠️  ADVERTENCIA: Este script va a:${NC}"
echo "  1. Remover __pycache__ del repositorio Git"
echo "  2. Mover documentación obsoleta a docs/archive/"
echo "  3. Eliminar scripts redundantes"
echo "  4. Eliminar archivos de deployment no usados"
echo "  5. Crear .env.example"
echo ""
confirm "¿Continuar?"

echo ""
echo "${GREEN}✅ Iniciando limpieza...${NC}"
echo ""

# ============================================
# 1. REMOVER __pycache__ DEL REPOSITORIO
# ============================================
echo "📦 [1/7] Removiendo __pycache__ del repositorio..."

if [ -d "__pycache__" ]; then
    git rm -r --cached __pycache__ 2>/dev/null || true
    git rm -r --cached cogs/__pycache__ 2>/dev/null || true
    git rm -r --cached core/__pycache__ 2>/dev/null || true
    git rm -r --cached stats/__pycache__ 2>/dev/null || true
    git rm -r --cached stats/commands/__pycache__ 2>/dev/null || true
    git rm -r --cached stats/data/__pycache__ 2>/dev/null || true
    git rm -r --cached stats/visualization/__pycache__ 2>/dev/null || true
    echo "  ✅ __pycache__ removido del Git (ahorro: ~732KB)"
else
    echo "  ℹ️  No se encontraron carpetas __pycache__ commiteadas"
fi

# ============================================
# 2. CREAR ESTRUCTURA DE DOCS
# ============================================
echo ""
echo "📁 [2/7] Creando estructura de documentación..."

mkdir -p docs/archive
echo "  ✅ Carpeta docs/archive/ creada"

# ============================================
# 3. MOVER DOCUMENTACIÓN OBSOLETA
# ============================================
echo ""
echo "📄 [3/7] Moviendo documentación obsoleta..."

# Contador de archivos movidos
moved_count=0

# Mover archivos de análisis
for file in ANALISIS_*.md; do
    if [ -f "$file" ]; then
        git mv "$file" docs/archive/ 2>/dev/null || mv "$file" docs/archive/
        ((moved_count++))
    fi
done

# Mover archivos de propuestas
for file in PROPUESTA_*.md; do
    if [ -f "$file" ]; then
        git mv "$file" docs/archive/ 2>/dev/null || mv "$file" docs/archive/
        ((moved_count++))
    fi
done

# Mover archivos de refactor
for file in REFACTOR_*.md; do
    if [ -f "$file" ]; then
        git mv "$file" docs/archive/ 2>/dev/null || mv "$file" docs/archive/
        ((moved_count++))
    fi
done

# Mover archivos específicos
files_to_move=(
    "BUENAS_PRACTICAS.md"
    "BUFFER_GRACIA_UNIFICADO.md"
    "CAMBIO_BUFFER_15MIN.md"
    "COMANDOS_NUEVOS.md"
    "MEJORAS_GRAFICOS.md"
    "SIMPLIFICACION_AGRESIVA_FINAL.md"
)

for file in "${files_to_move[@]}"; do
    if [ -f "$file" ]; then
        git mv "$file" docs/archive/ 2>/dev/null || mv "$file" docs/archive/
        ((moved_count++))
    fi
done

echo "  ✅ $moved_count archivos movidos a docs/archive/ (ahorro: ~400KB)"

# ============================================
# 4. CREAR .env.example
# ============================================
echo ""
echo "🔐 [4/7] Creando .env.example..."

if [ -f "ENV_TEMPLATE.md" ]; then
    cat > .env.example << 'EOF'
# Discord Bot Configuration

# REQUIRED
DISCORD_BOT_TOKEN=your_token_here
DISCORD_OWNER_ID=your_user_id

# OPTIONAL
DISCORD_CHANNEL_ID=channel_id_for_notifications
DISCORD_STATS_CHANNEL_ID=channel_id_for_stats_commands
EOF
    git rm ENV_TEMPLATE.md 2>/dev/null || rm ENV_TEMPLATE.md
    echo "  ✅ .env.example creado y ENV_TEMPLATE.md eliminado"
else
    echo "  ℹ️  ENV_TEMPLATE.md no encontrado"
fi

# ============================================
# 5. ELIMINAR SCRIPTS REDUNDANTES
# ============================================
echo ""
echo "🗑️  [5/7] Eliminando scripts redundantes..."

scripts_to_remove=(
    "config_git.sh"
    "setup_github.sh"
    "push_to_github.sh"
    "deploy_completo.sh"
)

removed_scripts=0
for script in "${scripts_to_remove[@]}"; do
    if [ -f "$script" ]; then
        git rm "$script" 2>/dev/null || rm "$script"
        ((removed_scripts++))
    fi
done

echo "  ✅ $removed_scripts scripts eliminados"

# ============================================
# 6. MOVER SCRIPTS ÚTILES
# ============================================
echo ""
echo "📦 [6/7] Organizando scripts útiles..."

mkdir -p scripts/setup scripts/debug

if [ -f "create_env.sh" ]; then
    git mv create_env.sh scripts/setup/ 2>/dev/null || mv create_env.sh scripts/setup/
    echo "  ✅ create_env.sh → scripts/setup/"
fi

if [ -f "verify_setup.sh" ]; then
    git mv verify_setup.sh scripts/debug/ 2>/dev/null || mv verify_setup.sh scripts/debug/
    echo "  ✅ verify_setup.sh → scripts/debug/"
fi

# ============================================
# 7. ELIMINAR ARCHIVOS DEPLOYMENT REDUNDANTES
# ============================================
echo ""
echo "🐳 [7/7] Eliminando archivos de deployment redundantes..."

deployment_files=(
    "Dockerfile"
    "docker-compose.yml"
    "Procfile"
)

# Verificar si railway.json está vacío o tiene solo {}
if [ -f "railway.json" ]; then
    content=$(cat railway.json | tr -d '[:space:]')
    if [ "$content" = "{}" ] || [ -z "$content" ]; then
        deployment_files+=("railway.json")
    fi
fi

removed_deployment=0
for file in "${deployment_files[@]}"; do
    if [ -f "$file" ]; then
        git rm "$file" 2>/dev/null || rm "$file"
        ((removed_deployment++))
    fi
done

echo "  ✅ $removed_deployment archivos de deployment eliminados"

# ============================================
# RESUMEN Y COMMIT
# ============================================
echo ""
echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "${GREEN}✅ Limpieza completada!${NC}"
echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "📊 Resumen de cambios:"
echo "  • __pycache__ removido: ~732KB"
echo "  • Documentos archivados: $moved_count archivos (~400KB)"
echo "  • Scripts eliminados: $removed_scripts archivos"
echo "  • Deployment files eliminados: $removed_deployment archivos"
echo "  • Ahorro total estimado: ~1.1MB (25% del repo)"
echo ""
echo "📁 Estructura actualizada:"
echo "  • docs/archive/ - Documentación obsoleta"
echo "  • scripts/setup/ - Scripts de configuración"
echo "  • scripts/debug/ - Scripts de debugging"
echo "  • .env.example - Template de variables de entorno"
echo ""

# Verificar si hay cambios para commitear
if git status --porcelain | grep -q '^'; then
    echo "${YELLOW}📝 Cambios detectados en Git${NC}"
    echo ""
    confirm "¿Deseas hacer commit de los cambios?"
    
    echo ""
    echo "📝 Haciendo commit..."
    git add .
    git commit -m "Clean up repository structure

- Remove __pycache__ from repository (~732KB)
- Move obsolete documentation to docs/archive/ (~400KB)
- Remove redundant deployment scripts
- Remove unused deployment files (Dockerfile, docker-compose.yml, Procfile)
- Create .env.example template
- Organize utility scripts in scripts/ folder

Total savings: ~1.1MB (25% of repository)"
    
    echo ""
    echo "${GREEN}✅ Commit realizado${NC}"
    echo ""
    confirm "¿Deseas hacer push a GitHub?"
    
    git push
    echo ""
    echo "${GREEN}✅ Push completado!${NC}"
else
    echo "${YELLOW}ℹ️  No hay cambios para commitear${NC}"
fi

echo ""
echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "${GREEN}🎉 Repositorio limpio y optimizado!${NC}"
echo "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "📋 Próximos pasos recomendados:"
echo "  1. Revisar el archivo ANALISIS_ESTRUCTURA_Y_MEJORAS.md"
echo "  2. Implementar Fase 2 (reorganización)"
echo "  3. Actualizar README.md si es necesario"
echo ""

