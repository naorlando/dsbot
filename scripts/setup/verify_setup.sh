#!/bin/bash

echo "🔍 Verificando configuración del proyecto..."
echo ""

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# 1. Verificar que .env existe y no está en git
echo "1️⃣  Verificando seguridad de credenciales..."
if [ -f ".env" ]; then
    if git ls-files --error-unmatch .env &>/dev/null; then
        echo -e "${RED}❌ ERROR: .env está siendo rastreado por git${NC}"
        ERRORS=$((ERRORS+1))
    else
        echo -e "${GREEN}✅ .env existe y NO está en git${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  .env no existe (normal si aún no lo has creado)${NC}"
    WARNINGS=$((WARNINGS+1))
fi

# 2. Verificar .gitignore
echo ""
echo "2️⃣  Verificando .gitignore..."
if grep -q "\.env" .gitignore 2>/dev/null; then
    echo -e "${GREEN}✅ .env está en .gitignore${NC}"
else
    echo -e "${RED}❌ ERROR: .env NO está en .gitignore${NC}"
    ERRORS=$((ERRORS+1))
fi

# 3. Verificar que no hay tokens hardcodeados
echo ""
echo "3️⃣  Buscando tokens hardcodeados..."
# Buscar asignaciones de token que NO sean os.getenv/os.environ y NO sean mensajes de error
if grep -E "DISCORD_BOT_TOKEN\s*=\s*['\"][^'\"]+['\"]" bot.py 2>/dev/null | grep -v "os.getenv\|os.environ\|print\|#\|tu_token_aqui" > /dev/null; then
    echo -e "${RED}❌ ERROR: Posible token hardcodeado encontrado${NC}"
    ERRORS=$((ERRORS+1))
else
    echo -e "${GREEN}✅ No se encontraron tokens hardcodeados${NC}"
fi

# 4. Verificar uso de variables de entorno
echo ""
echo "4️⃣  Verificando uso de variables de entorno..."
if grep -q "os.getenv.*DISCORD_BOT_TOKEN" bot.py; then
    echo -e "${GREEN}✅ Usa os.getenv() para el token${NC}"
else
    echo -e "${RED}❌ ERROR: No se usa os.getenv() para el token${NC}"
    ERRORS=$((ERRORS+1))
fi

# 5. Verificar requirements.txt
echo ""
echo "5️⃣  Verificando dependencias..."
if [ -f "requirements.txt" ]; then
    if grep -q "discord.py" requirements.txt && grep -q "python-dotenv" requirements.txt; then
        echo -e "${GREEN}✅ requirements.txt tiene las dependencias necesarias${NC}"
    else
        echo -e "${YELLOW}⚠️  requirements.txt puede estar incompleto${NC}"
        WARNINGS=$((WARNINGS+1))
    fi
else
    echo -e "${RED}❌ ERROR: requirements.txt no existe${NC}"
    ERRORS=$((ERRORS+1))
fi

# 6. Verificar estructura de archivos
echo ""
echo "6️⃣  Verificando estructura del proyecto..."
FILES=("bot.py" "README.md" ".gitignore" "config.json")
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ $file existe${NC}"
    else
        echo -e "${RED}❌ ERROR: $file no existe${NC}"
        ERRORS=$((ERRORS+1))
    fi
done

# 7. Verificar configuración git local
echo ""
echo "7️⃣  Verificando configuración git..."
if [ -d ".git" ]; then
    LOCAL_USER=$(git config --local user.name 2>/dev/null)
    LOCAL_EMAIL=$(git config --local user.email 2>/dev/null)
    
    if [ -n "$LOCAL_USER" ] && [ -n "$LOCAL_EMAIL" ]; then
        echo -e "${GREEN}✅ Git configurado localmente${NC}"
        echo "   Usuario: $LOCAL_USER"
        echo "   Email: $LOCAL_EMAIL"
    else
        echo -e "${YELLOW}⚠️  Git no configurado localmente (usa: git config user.name/email)${NC}"
        WARNINGS=$((WARNINGS+1))
    fi
else
    echo -e "${YELLOW}⚠️  Repositorio git no inicializado${NC}"
    WARNINGS=$((WARNINGS+1))
fi

# Resumen
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 RESUMEN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ Todo está perfecto!${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠️  $WARNINGS advertencia(s) - Revisa los puntos arriba${NC}"
    exit 0
else
    echo -e "${RED}❌ $ERRORS error(es) encontrado(s)${NC}"
    echo -e "${YELLOW}⚠️  $WARNINGS advertencia(s)${NC}"
    echo ""
    echo "Corrige los errores antes de continuar."
    exit 1
fi

