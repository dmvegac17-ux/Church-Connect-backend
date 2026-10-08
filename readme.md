# Church Connect Backend

Backend desarrollado con:

* FastAPI
* SQLAlchemy 2.0
* Supabase PostgreSQL
* Alembic
* Pydantic v2
* Clean Architecture
* Repository Pattern
* Service Layer

---

# Requisitos

Instalar previamente:

* [uv](https://docs.astral.sh/uv/) (gestor de proyectos y dependencias de Python)
* Git

El proyecto fija la versión de Python en `.python-version` y en `pyproject.toml`
(`requires-python`), por lo que **no es necesario instalar Python manualmente**:
`uv` descarga e instala automáticamente la versión correcta la primera vez que
se use.

Instalar `uv`:

## Windows

PowerShell (recomendado):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Alternativa con winget:

```powershell
winget install --id=astral-sh.uv -e
```

Git Bash:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

> Git Bash puede ejecutar el mismo script `.sh` que Linux/Mac, ya que incluye
> `curl` y `sh`. El comando de PowerShell **no** funciona dentro de Git Bash.

## Linux / Mac

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Alternativa con Homebrew (Mac):

```bash
brew install uv
```

## Alternativa multiplataforma (con pipx)

```bash
pipx install uv
```

> Tras instalar, reiniciar la terminal para que `uv` quede disponible en el `PATH`.

Verificar instalación:

```bash
uv --version
git --version
```

---

# Clonar repositorio

```bash
git clone <URL_DEL_REPOSITORIO>
cd Church-Connect-backend
```

---

# Instalar dependencias

`uv` crea automáticamente el entorno virtual (`.venv`) e instala las
dependencias exactas fijadas en `uv.lock`:

```bash
uv sync
```

Para incluir también las dependencias de desarrollo (pytest, ruff, etc.):

```bash
uv sync --group dev
```

Verificar:

```bash
uv pip list
```

> No es necesario activar el entorno virtual manualmente: basta con anteponer
> `uv run` a cualquier comando (por ejemplo `uv run uvicorn ...`, `uv run pytest`)
> para ejecutarlo dentro del entorno del proyecto. Si prefieres activarlo:
>
> * PowerShell: `.venv\Scripts\Activate.ps1`
> * Git Bash: `source .venv/Scripts/activate`
> * CMD: `.venv\Scripts\activate.bat`
>
> Para desactivarlo: `deactivate`

---

# Agregar o actualizar dependencias

```bash
uv add <paquete>==<version>          # dependencia de producción
uv add --dev <paquete>==<version>    # dependencia de desarrollo
uv remove <paquete>                  # eliminar dependencia
uv lock --upgrade                    # actualizar todas dentro de los rangos permitidos
```

Estos comandos actualizan `pyproject.toml` y `uv.lock` automáticamente.
`uv.lock` debe commitearse siempre para garantizar builds reproducibles.

---

# Configuración de Variables de Entorno

Copiar archivo de ejemplo:

```bash
cp .env.example .env
```

Windows:

```cmd
copy .env.example .env
```

Completar las variables:

```env
APP_NAME=Church Connect API
API_VERSION=1.0.0
ENVIRONMENT=local
DEBUG=True

DATABASE_URL=postgresql+asyncpg://usuario:password@host:5432/postgres

JWT_SECRET_KEY=secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
```

---

# Ejecutar migraciones

Aplicar migraciones pendientes:

```bash
uv run alembic upgrade head
```

Verificar versión actual:

```bash
uv run alembic current
```

---

# Ejecutar API

```bash
uv run uvicorn src.main:app --reload
```

La aplicación quedará disponible en:

```text
http://localhost:8000
```

---

# Documentación Swagger

Con la API corriendo, acceder desde el navegador a:

```text
http://localhost:8000/docs
```

Para probar endpoints protegidos:

1. Ejecutar `POST /api/v1/auth/login` con `correo`/`contrasena` válidos y copiar el `data.access_token` de la respuesta.
2. Hacer clic en el botón **Authorize** (esquina superior derecha, ícono de candado).
3. Pegar el token en el campo **Value** (sin el prefijo `Bearer`, Swagger lo agrega solo) y confirmar.
4. Los endpoints con candado 🔒 quedarán autenticados para el resto de la sesión.

> El esquema de seguridad es `HTTPBearer` (pegar token manual) en vez de
> OAuth2 con formulario automático: es más simple y evita bugs de autofill
> de swagger-ui en algunos navegadores/versiones. Todos los endpoints,
> incluido `/auth/login`, usan JSON de forma consistente.

---

# Documentación ReDoc

```text
http://localhost:8000/redoc
```

---

# Health Check

```text
GET http://localhost:8000/api/v1/health
```

Respuesta esperada:

```json
{
  "status": "ok",
  "message": "API running"
}
```

---

# Health Check Base de Datos

```text
GET http://localhost:8000/api/v1/health/db
```

Respuesta esperada:

```json
{
  "database": 1
}
```

---

# Comandos útiles

Crear migración:

```bash
uv run alembic revision --autogenerate -m "descripcion"
```

Aplicar migraciones:

```bash
uv run alembic upgrade head
```

Revertir última migración:

```bash
uv run alembic downgrade -1
```

Mostrar historial:

```bash
uv run alembic history
```

---

# Ejecutar pruebas

```bash
uv run pytest
```

Cobertura:

```bash
uv run pytest --cov=src
```

---

# Estructura del Proyecto

```text
src/
├── api/
├── application/
├── core/
├── domain/
├── infrastructure/
└── main.py

tests/
migrations/
```
If you miss the Terminal-style experience of the previous extension, don’t worry! It hasn’t gone anywhere. Use the Claude Code: Use Terminal setting to switch back.