from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest
from sqlalchemy import update

from src.core.constants.enums import UserRole
from src.infrastructure.database.models.event_model import EventModel
from tests.conftest import AsyncSessionLocal
from tests.conftest import auth
from tests.conftest import crear_actividad
from tests.conftest import crear_evento
from tests.conftest import crear_usuario

pytestmark = pytest.mark.asyncio

EVENTO_PASADO = "La fecha y hora de inicio no pueden estar en el pasado"
ACTIVIDAD_PASADA = "La actividad no puede ser anterior a hoy"


def fechas(inicio: datetime) -> dict:
    return {
        "fecha_inicio": inicio.isoformat(),
        "fecha_fin": (inicio + timedelta(hours=2)).isoformat(),
    }


async def en_curso(evento: EventModel) -> datetime:
    """Deja el evento empezado hace dos días y todavía sin terminar."""
    inicio = datetime.now(UTC) - timedelta(days=2)
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(EventModel).where(EventModel.id == evento.id).values(
                fecha_inicio=inicio, fecha_fin=inicio + timedelta(days=14)
            )
        )
        await db.commit()

    return inicio


async def test_no_se_crea_ni_se_mueve_un_evento_a_una_fecha_anterior_a_hoy(api):
    admin = auth(await crear_usuario("Admin", UserRole.ADMIN))
    pasado = datetime.now(UTC) - timedelta(days=2)
    nuevo = {
        "titulo": "Retiro", "descripcion": "Evento de prueba",
        "lugar": "Templo de prueba", "capacidad": 50,
    }

    r = await api.post("/events", headers=admin, json={**nuevo, **fechas(pasado)})
    assert r.status_code == 400, r.text
    assert r.json()["message"] == EVENTO_PASADO

    evento = await crear_evento(en_dias=10)
    r = await api.put(f"/events/{evento.id}", headers=admin, json=fechas(pasado))
    assert r.status_code == 400, r.text
    assert r.json()["message"] == EVENTO_PASADO

    # De hoy en adelante sí.
    r = await api.post(
        "/events", headers=admin,
        json={**nuevo, **fechas(datetime.now(UTC) + timedelta(days=1))},
    )
    assert r.status_code in (200, 201), r.text


async def test_un_evento_en_curso_se_edita_sin_mover_su_fecha(api):
    admin = auth(await crear_usuario("Admin", UserRole.ADMIN))
    evento = await crear_evento(en_dias=10)
    await en_curso(evento)

    r = await api.put(f"/events/{evento.id}", headers=admin, json={"titulo": "Renombrado"})

    assert r.status_code == 200, r.text


async def test_no_se_crea_ni_se_mueve_una_actividad_a_una_fecha_anterior_a_hoy(api):
    admin = auth(await crear_usuario("Admin", UserRole.ADMIN))
    evento = await crear_evento(en_dias=10)
    actividad = await crear_actividad(evento, "Alabanza", 60, 30)
    inicio = await en_curso(evento)
    pasado = {
        "hora_inicio": inicio.isoformat(),
        "hora_fin": (inicio + timedelta(minutes=30)).isoformat(),
    }

    r = await api.post(
        "/schedules", headers=admin,
        json={"evento_id": str(evento.id), "actividad": "Oración",
              "responsable": "Por asignar", **pasado},
    )
    assert r.status_code == 400, r.text
    assert r.json()["message"] == ACTIVIDAD_PASADA

    r = await api.put(f"/schedules/{actividad.id}", headers=admin, json=pasado)
    assert r.status_code == 400, r.text
    assert r.json()["message"] == ACTIVIDAD_PASADA

    r = await api.put(
        "/schedules/horarios", headers=admin,
        json={"evento_id": str(evento.id), "items": [{"id": str(actividad.id), **pasado}]},
    )
    assert r.status_code == 400, r.text
    assert r.json()["message"] == ACTIVIDAD_PASADA

    # Editar su nombre sin tocar el horario sigue permitido.
    r = await api.put(f"/schedules/{actividad.id}", headers=admin, json={"actividad": "Adoración"})
    assert r.status_code == 200, r.text



async def test_un_evento_de_hoy_no_empieza_a_una_hora_que_ya_paso(api):
    admin = auth(await crear_usuario("Admin", UserRole.ADMIN))
    nuevo = {
        "titulo": "Vigilia", "descripcion": "Evento de prueba",
        "lugar": "Templo de prueba", "capacidad": 50,
    }
    hace_dos_horas = datetime.now(UTC) - timedelta(hours=2)

    r = await api.post("/events", headers=admin, json={**nuevo, **fechas(hace_dos_horas)})
    assert r.status_code == 400, r.text
    assert r.json()["message"] == EVENTO_PASADO

    # «Ahora mismo» sí: hay unos minutos de margen mientras se guarda.
    r = await api.post(
        "/events", headers=admin,
        json={**nuevo, **fechas(datetime.now(UTC) - timedelta(minutes=1))},
    )
    assert r.status_code in (200, 201), r.text


async def test_una_actividad_fuera_del_evento_se_rechaza_diciendo_el_rango(api):
    admin = auth(await crear_usuario("Admin", UserRole.ADMIN))
    evento = await crear_evento(en_dias=10)  # de 10:00 a. m. a 2:00 p. m. (Colombia)
    antes = evento.fecha_inicio - timedelta(hours=1)

    r = await api.post(
        "/schedules", headers=admin,
        json={
            "evento_id": str(evento.id), "actividad": "Montaje",
            "responsable": "Por asignar",
            "hora_inicio": antes.isoformat(),
            "hora_fin": (antes + timedelta(minutes=30)).isoformat(),
        },
    )

    assert r.status_code in (400, 409), r.text
    mensaje = r.json()["message"]
    assert mensaje.startswith("Esta actividad debe estar entre el ")
    assert "10:00 a. m." in mensaje and "2:00 p. m." in mensaje
