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

* Python 3.13+
* Git

Verificar instalación:

```bash
py --version
git --version
```

---

# Clonar repositorio

```bash
git clone <URL_DEL_REPOSITORIO>
cd Church-Connect-backend
```

---

# Crear entorno virtual

Windows:

```bash
py -m venv .venv
```

Linux / Mac:

```bash
python3 -m venv .venv
```

---

# Activar entorno virtual

## Git Bash

```bash
source .venv/Scripts/activate
```

## PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

## CMD

```cmd
.venv\Scripts\activate.bat
```

Validar activación:

```bash
py --version
```

Debe aparecer:

```text
(.venv)
```

al inicio de la consola.

---

# Instalar dependencias

```bash
pip install -r requirements.txt
```

Verificar:

```bash
pip list
```

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
alembic upgrade head
```

Verificar versión actual:

```bash
alembic current
```

---

# Ejecutar API

```bash
uvicorn src.main:app --reload
```

La aplicación quedará disponible en:

```text
http://localhost:8000
```

---

# Documentación Swagger

```text
http://localhost:8000/docs
```

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
alembic revision --autogenerate -m "descripcion"
```

Aplicar migraciones:

```bash
alembic upgrade head
```

Revertir última migración:

```bash
alembic downgrade -1
```

Mostrar historial:

```bash
alembic history
```

---

# Ejecutar pruebas

```bash
pytest
```

Cobertura:

```bash
pytest --cov=src
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
