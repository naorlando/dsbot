# Guía: Publicar Bot de Discord como Open Source

## 📋 Checklist para Publicar como Open Source

### 1. Preparar el Código

- [ ] **Eliminar información sensible:**
  - ✅ Token del bot (usar variables de entorno)
  - ✅ IDs de servidores/canales específicos
  - ✅ Credenciales o API keys
  - ✅ Información personal

- [ ] **Archivos importantes:**
  - ✅ `.gitignore` configurado correctamente
  - ✅ `README.md` completo y claro
  - ✅ `LICENSE` (elige una licencia)
  - ✅ `requirements.txt` actualizado

### 2. Crear Repositorio en GitHub

1. Ve a [github.com](https://github.com) y crea cuenta (si no tienes)
2. Haz clic en "New repository"
3. Configura:
   - **Name:** `dsbot` (o el nombre que prefieras)
   - **Description:** "Bot de Discord para notificar actividad de miembros"
   - **Visibility:** Public (para open source)
   - ✅ Marca "Add a README file" (si no tienes uno)
   - ✅ Marca "Add .gitignore" > Python
   - ✅ Elige una licencia (MIT recomendada para proyectos simples)

4. Haz clic en "Create repository"

### 3. Subir el Código

```bash
# Inicializar git (si no lo has hecho)
git init

# Agregar todos los archivos
git add .

# Hacer commit
git commit -m "Initial commit: Bot de Discord para notificaciones"

# Conectar con GitHub (reemplaza USERNAME con tu usuario)
git remote add origin https://github.com/USERNAME/dsbot.git

# Subir código
git branch -M main
git push -u origin main
```

### 4. Configurar el Repositorio

#### Agregar Descripción y Topics

En la página de tu repositorio:
1. Haz clic en el ícono de engranaje ⚙️ junto a "About"
2. Agrega una descripción: "Bot de Discord que notifica cuando miembros juegan o entran a canales de voz"
3. Agrega topics: `discord`, `discord-bot`, `python`, `discord-py`, `bot`, `notifications`

#### Agregar Badges (Opcional)

Puedes agregar badges al README para mostrar:
- Estado del proyecto
- Versión de Python
- Licencia
- etc.

Ejemplo de badges:
```markdown
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Discord.py](https://img.shields.io/badge/discord.py-2.3+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
```

### 5. Crear LICENSE

Elige una licencia según tus necesidades:

#### MIT License (Recomendada para proyectos simples)

Crea archivo `LICENSE`:
```
MIT License

Copyright (c) 2024 [Tu Nombre]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Otras opciones:
- **Apache 2.0:** Para proyectos más grandes
- **GPL v3:** Para proyectos que quieren mantener código abierto
- **Unlicense:** Para dominio público

### 6. Mejorar el README

Asegúrate de que tu README incluya:

- ✅ Descripción clara del proyecto
- ✅ Características principales
- ✅ Instrucciones de instalación
- ✅ Cómo configurar el bot
- ✅ Comandos disponibles
- ✅ Ejemplos de uso
- ✅ Contribuciones (si aceptas)
- ✅ Licencia
- ✅ Créditos/Agradecimientos

### 7. Configurar GitHub Actions (Opcional)

Puedes agregar CI/CD para:
- Verificar que el código funciona
- Ejecutar tests
- Verificar formato de código

Ejemplo `.github/workflows/test.yml`:
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python -m py_compile bot.py
```

### 8. Agregar Contributing.md (Opcional)

Si quieres que otros contribuyan:

```markdown
# Contribuyendo

¡Gracias por tu interés en contribuir!

## Cómo contribuir

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## Estándares de código

- Sigue PEP 8 para Python
- Agrega comentarios cuando sea necesario
- Prueba tus cambios antes de hacer commit
```

### 9. Publicar en Discord Bot Lists (Opcional)

Si quieres que otros descubran tu bot:

#### top.gg
1. Ve a [top.gg](https://top.gg)
2. Crea cuenta y verifica tu bot
3. Agrega tu bot a la lista

#### Discord Bot List
1. Ve a [discordbotlist.com](https://discordbotlist.com)
2. Crea cuenta
3. Agrega tu bot

### 10. Configurar Issues y Pull Requests

En la configuración del repositorio:
- ✅ Habilita Issues
- ✅ Habilita Pull Requests
- ✅ Configura templates (opcional)

## 🔒 Seguridad

### ✅ Verificar antes de publicar:

```bash
# Buscar tokens o información sensible
grep -r "DISCORD_BOT_TOKEN" .
grep -r "your_token" .
grep -r "MT.*\." .  # Buscar tokens de Discord

# Verificar .gitignore
cat .gitignore

# Verificar que .env no esté en el repo
git ls-files | grep .env
```

### Archivos que NUNCA deben estar en el repo:

- ❌ `.env`
- ❌ `config.json` (si contiene tokens)
- ❌ Cualquier archivo con tokens
- ❌ Credenciales de bases de datos
- ❌ API keys

## 📝 Ejemplo de README para Open Source

```markdown
# Bot de Discord - Notificaciones de Actividad

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3+-green.svg)](https://discordpy.readthedocs.io/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Un bot de Discord open source que notifica en el canal general cuando los miembros:
- 🎮 Empiezan a jugar un juego
- 🔊 Entran a un canal de voz
- 🔄 Cambian de canal de voz

## ✨ Características

- Notificaciones configurables
- Soporte para diferentes tipos de actividades
- Comandos de administración
- Fácil de configurar y desplegar

## 🚀 Instalación Rápida

1. Clona el repositorio
2. Instala dependencias: `pip install -r requirements.txt`
3. Configura tu token en `.env`
4. Ejecuta: `python bot.py`

[Ver guía completa de instalación](INSTALACION.md)

## 📚 Documentación

- [Instalación](INSTALACION.md)
- [Hosting Gratuito](HOSTING.md)
- [Configuración](README.md#configuración)

## 🤝 Contribuir

Las contribuciones son bienvenidas! Por favor lee [CONTRIBUTING.md](CONTRIBUTING.md) para más detalles.

## 📄 Licencia

Este proyecto está bajo la licencia MIT - ver [LICENSE](LICENSE) para más detalles.

## 🙏 Agradecimientos

- [discord.py](https://discordpy.readthedocs.io/) - Librería de Discord para Python
```

## 🎯 Checklist Final

Antes de hacer público tu repositorio:

- [ ] Código limpio y comentado
- [ ] README completo
- [ ] LICENSE agregada
- [ ] .gitignore configurado
- [ ] Sin tokens o información sensible
- [ ] Documentación clara
- [ ] Instrucciones de instalación
- [ ] Ejemplos de uso

## 🚀 Siguiente Paso: Hosting

Una vez que tu código esté en GitHub, puedes desplegarlo fácilmente:

1. **Railway:** Conecta tu repo de GitHub y despliega en 2 minutos
2. **Render:** Conecta tu repo y despliega automáticamente

Ver [HOSTING.md](HOSTING.md) para más detalles.

---

**¡Felicidades! Tu bot de Discord está ahora disponible como open source** 🎉

