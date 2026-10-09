"""
Entorno de pruebas: SQLite en un archivo temporal y correo simulado.

Las variables se fijan ANTES de importar `src`, y tienen prioridad sobre el
`.env`: las pruebas nunca tocan la base de datos real ni envían correos.
"""
import os
import tempfile
from datetime import UTC
from datetime import datetime
from datetime import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

_DB_DIR = tempfile.mkdtemp(prefix="church-connect-tests-")
_DB_PATH = Path(_DB_DIR) / "test.db"

os.environ.update(
    {
        "APP_NAME": "Church Connect (tests)",
        "API_VERSION": "test",
        "ENVIRONMENT": "local",
        "DEBUG": "False",
        "DATABASE_URL": f"sqlite+aiosqlite:///{_DB_PATH.as_posix()}",
        "JWT_SECRET_KEY": "clave-solo-para-pruebas-de-al-menos-32-bytes",
        "JWT_ALGORITHM": "HS256",
        "MAIL_SMTP_HOST": "",
        "MAIL_SMTP_FROM": "",
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import event  # noqa: E402

from src.api.dependencies.participaciones import get_email_service  # noqa: E402
from src.application.participaciones.services import BOGOTA  # noqa: E402
from src.core.constants.enums import UserRole  # noqa: E402
from src.core.security.jwt import create_access_token  # noqa: E402
from src.infrastructure.database.base import Base  # noqa: E402
from src.infrastructure.database.models.event_model import EventModel  # noqa: E402
from src.infrastructure.database.models.schedule_model import ScheduleModel  # noqa: E402
from src.infrastructure.database.models.user_model import UserModel  # noqa: E402
from src.infrastructure.database.session import AsyncSessionLocal  # noqa: E402
from src.infrastructure.database.session import engine  # noqa: E402
from src.main import app  # noqa: E402

assert engine.url.get_backend_name() == "sqlite", "Las pruebas solo corren sobre SQLite"


@event.listens_for(engine.sync_engine, "connect")
def _sqlite_setup(dbapi_connection, _record):
    # Los CHECK de los modelos usan `char_length`, que SQLite no trae.
    dbapi_connection.run_async(
        lambda conn: conn.create_function(
            "char_length", 1, lambda v: None if v is None else len(v),
            deterministic=True
        )
    )
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class FakeEmailService:
    """Servicio de correo simulado: registra los envíos y puede fallar."""

    def __init__(self):
        self.enviados: list[dict] = []
        self.fallar = False

    async def send_notification(self, to, titulo, mensaje, usuario_nombre):
        if self.fallar:
            return False

        self.enviados.append({"to": to, "titulo": titulo, "mensaje": mensaje})

        return True


@pytest_asyncio.fixture(autouse=True)
async def _base_de_datos():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()


@pytest.fixture
def correo():
    fake = FakeEmailService()
    app.dependency_overrides[get_email_service] = lambda: fake

    yield fake

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def api(correo):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test/api/v1"
    ) as client:
        yield client


def auth(usuario: UserModel) -> dict[str, str]:
    token = create_access_token(usuario.id, usuario.rol.value)

    return {"Authorization": f"Bearer {token}"}


# Datos ficticios, solo para pruebas.

async def crear_usuario(
    nombre: str,
    rol: UserRole = UserRole.PARTICIPANT,
    activo: bool = True
) -> UserModel:
    async with AsyncSessionLocal() as db:
        usuario = UserModel(
            id=uuid4(),
            nombre=nombre,
            apellido="Prueba",
            correo=f"{nombre.lower()}-{uuid4().hex[:6]}@example.test",
            contrasena="x",
            rol=rol,
            activo=activo,
            fecha_creacion=datetime.now(UTC)
        )
        db.add(usuario)
        await db.commit()

        return usuario


async def crear_evento(titulo: str = "Culto de prueba", en_dias: int = 10) -> EventModel:
    # A las 10:00 de Bogotá, `en_dias` días calendario después de hoy (Bogotá).
    dia = datetime.now(UTC).astimezone(BOGOTA).date() + timedelta(days=en_dias)
    inicio = datetime.combine(dia, time(10, 0), BOGOTA).astimezone(UTC)

    async with AsyncSessionLocal() as db:
        evento = EventModel(
            id=uuid4(),
            titulo=titulo,
            descripcion="Evento de prueba",
            fecha_inicio=inicio,
            fecha_fin=inicio + timedelta(hours=4),
            lugar="Templo de prueba",
            capacidad=50,
            creado_por="tests"
        )
        db.add(evento)
        await db.commit()

        return evento


async def crear_actividad(
    evento: EventModel,
    nombre: str = "Alabanza",
    desde_min: int = 0,
    duracion_min: int = 30
) -> ScheduleModel:
    inicio = evento.fecha_inicio + timedelta(minutes=desde_min)

    async with AsyncSessionLocal() as db:
        actividad = ScheduleModel(
            id=uuid4(),
            evento_id=evento.id,
            actividad=nombre,
            hora_inicio=inicio,
            hora_fin=inicio + timedelta(minutes=duracion_min),
            responsable="Por asignar",
            descripcion="Actividad de prueba"
        )
        db.add(actividad)
        await db.commit()

        return actividad
