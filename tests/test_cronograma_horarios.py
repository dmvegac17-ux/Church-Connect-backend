from datetime import UTC
from datetime import datetime
from datetime import timedelta
from uuid import uuid4

import pytest

from src.core.constants.enums import UserRole
from tests.conftest import auth
from tests.conftest import crear_actividad
from tests.conftest import crear_evento
from tests.conftest import crear_usuario

pytestmark = pytest.mark.asyncio


def instante(texto: str) -> datetime:
    """SQLite devuelve las fechas sin zona horaria: siempre son UTC."""
    valor = datetime.fromisoformat(texto)

    return valor.replace(tzinfo=UTC) if valor.tzinfo is None else valor


@pytest.fixture
async def escena(api):
    """Evento de 4 horas con Alabanza (0–30 min) y Estudio (30–90 min)."""
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    evento = await crear_evento(en_dias=10)
    alabanza = await crear_actividad(evento, "Alabanza", 0, 30)
    estudio = await crear_actividad(evento, "Estudio bíblico", 30, 60)

    return {"admin": admin, "evento": evento, "alabanza": alabanza, "estudio": estudio}


def cuerpo(evento, *items) -> dict:
    return {
        "evento_id": str(evento.id),
        "items": [
            {
                "id": str(actividad.id),
                "hora_inicio": (evento.fecha_inicio + timedelta(minutes=desde)).isoformat(),
                "hora_fin": (evento.fecha_inicio + timedelta(minutes=hasta)).isoformat(),
            }
            for actividad, desde, hasta in items
        ],
    }


async def horarios(api, escena) -> dict[str, tuple[int, int]]:
    """Minutos desde el inicio del evento en que empieza y termina cada actividad."""
    r = await api.get(
        "/schedules",
        headers=auth(escena["admin"]),
        params={"evento_id": str(escena["evento"].id)},
    )
    inicio = escena["evento"].fecha_inicio

    return {
        a["actividad"]: (
            int((instante(a["hora_inicio"]) - inicio).total_seconds() // 60),
            int((instante(a["hora_fin"]) - inicio).total_seconds() // 60),
        )
        for a in r.json()["data"]
    }


async def test_intercambiar_los_horarios_de_dos_actividades(api, escena):
    evento = escena["evento"]

    # Estudio pasa primero (0–60) y Alabanza después (60–90): cada una
    # conserva su duración. Guardadas de a una, la primera chocaría con la
    # que todavía ocupa su hueco.
    r = await api.put(
        "/schedules/horarios",
        headers=auth(escena["admin"]),
        json=cuerpo(evento, (escena["estudio"], 0, 60), (escena["alabanza"], 60, 90)),
    )

    assert r.status_code == 200, r.text
    assert len(r.json()["data"]) == 2
    assert await horarios(api, escena) == {
        "Estudio bíblico": (0, 60),
        "Alabanza": (60, 90),
    }


async def test_de_a_una_el_mismo_intercambio_choca(api, escena):
    """Por eso existe el servicio: el cambio individual sí se solapa."""
    evento = escena["evento"]

    r = await api.put(
        f"/schedules/{escena['estudio'].id}",
        headers=auth(escena["admin"]),
        json={
            "hora_inicio": evento.fecha_inicio.isoformat(),
            "hora_fin": (evento.fecha_inicio + timedelta(minutes=60)).isoformat(),
        },
    )

    assert r.status_code == 400


async def test_se_guarda_todo_o_nada(api, escena):
    evento = escena["evento"]
    antes = await horarios(api, escena)

    # La primera es válida, pero la segunda queda solapada con ella.
    r = await api.put(
        "/schedules/horarios",
        headers=auth(escena["admin"]),
        json=cuerpo(evento, (escena["estudio"], 0, 60), (escena["alabanza"], 30, 60)),
    )

    assert r.status_code == 400
    assert "solapa" in r.json()["message"]
    assert await horarios(api, escena) == antes


async def test_no_puede_chocar_con_una_actividad_que_no_se_mueve(api, escena):
    evento = escena["evento"]
    antes = await horarios(api, escena)

    # Solo se mueve Alabanza, encima de Estudio (30–90).
    r = await api.put(
        "/schedules/horarios",
        headers=auth(escena["admin"]),
        json=cuerpo(evento, (escena["alabanza"], 60, 90)),
    )

    assert r.status_code == 400
    assert await horarios(api, escena) == antes


@pytest.mark.parametrize(
    ("desde", "hasta"),
    [
        (-30, 0),      # antes de que empiece el evento
        (230, 260),    # termina después del evento (dura 240 min)
        (120, 120),    # sin duración
        (150, 120),    # fin antes que el inicio
    ],
)
async def test_el_horario_debe_ser_valido_y_quedar_dentro_del_evento(api, escena, desde, hasta):
    antes = await horarios(api, escena)

    r = await api.put(
        "/schedules/horarios",
        headers=auth(escena["admin"]),
        json=cuerpo(escena["evento"], (escena["alabanza"], desde, hasta)),
    )

    assert r.status_code == 400
    assert await horarios(api, escena) == antes


async def test_el_borde_exacto_del_evento_si_se_acepta(api, escena):
    r = await api.put(
        "/schedules/horarios",
        headers=auth(escena["admin"]),
        json=cuerpo(escena["evento"], (escena["alabanza"], 210, 240)),
    )

    assert r.status_code == 200, r.text
    assert (await horarios(api, escena))["Alabanza"] == (210, 240)


async def test_solo_actividades_de_ese_evento(api, escena):
    otro = await crear_evento("Otro evento", en_dias=12)
    ajena = await crear_actividad(otro, "Bienvenida", 0, 30)
    admin = auth(escena["admin"])
    evento = escena["evento"]

    r = await api.put("/schedules/horarios", headers=admin, json=cuerpo(evento, (ajena, 120, 150)))
    assert r.status_code == 404

    inexistente = cuerpo(evento, (escena["alabanza"], 120, 150))
    inexistente["items"][0]["id"] = str(uuid4())
    r = await api.put("/schedules/horarios", headers=admin, json=inexistente)
    assert r.status_code == 404

    sin_evento = cuerpo(evento, (escena["alabanza"], 120, 150))
    sin_evento["evento_id"] = str(uuid4())
    r = await api.put("/schedules/horarios", headers=admin, json=sin_evento)
    assert r.status_code == 404


async def test_solo_el_administrador_y_no_en_eventos_finalizados(api, escena):
    miembro = await crear_usuario("Ana")
    evento = escena["evento"]
    cambio = cuerpo(evento, (escena["alabanza"], 120, 150))

    r = await api.put("/schedules/horarios", headers=auth(miembro), json=cambio)
    assert r.status_code == 403

    pasado = await crear_evento("Vigilia de ayer", en_dias=-1)
    vieja = await crear_actividad(pasado, "Alabanza", 0, 30)
    r = await api.put(
        "/schedules/horarios",
        headers=auth(escena["admin"]),
        json=cuerpo(pasado, (vieja, 60, 90)),
    )
    assert r.status_code == 409
    assert r.json()["data"] == {"codigo": "evento_finalizado"}


async def test_la_lista_no_puede_ir_vacia(api, escena):
    r = await api.put(
        "/schedules/horarios",
        headers=auth(escena["admin"]),
        json={"evento_id": str(escena["evento"].id), "items": []},
    )

    assert r.status_code == 422
