from datetime import timedelta

import pytest
import pytest_asyncio

from src.core.constants.enums import UserRole
from tests.conftest import auth
from tests.conftest import crear_actividad
from tests.conftest import crear_evento
from tests.conftest import crear_usuario

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def escena(api):
    """
    Evento de 10:00 a. m. a 2:00 p. m. con «Alabanza» (10:00–10:30, que Ana
    ya confirmó) y «Estudio» (1:00–1:30 p. m.).
    """
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    ana = await crear_usuario("Ana")
    evento = await crear_evento(en_dias=10)
    alabanza = await crear_actividad(evento, "Alabanza", 0)
    estudio = await crear_actividad(evento, "Estudio", 180)

    r = await api.post(
        "/admin/participaciones", headers=auth(admin),
        json={
            "actividad_id": str(alabanza.id), "participante_id": str(ana.id),
            "dias_para_confirmar": 3,
        },
    )
    invitacion = r.json()["data"]["id"]
    r = await api.post(f"/participante/invitaciones/{invitacion}/aceptar", headers=auth(ana))
    assert r.status_code == 200, r.text

    return {
        "admin": admin, "ana": ana, "evento": evento,
        "alabanza": alabanza, "estudio": estudio, "invitacion": invitacion,
    }


def rango(evento, inicio_min: int = 0, fin_min: int = 0, dias: int = 0) -> dict:
    """El horario del evento con el inicio y el fin desplazados."""
    return {
        "fecha_inicio": (evento.fecha_inicio + timedelta(days=dias, minutes=inicio_min)).isoformat(),
        "fecha_fin": (evento.fecha_fin + timedelta(days=dias, minutes=fin_min)).isoformat(),
    }


def mover(actividad, dias: int = 0, minutos: int = 0) -> dict:
    delta = timedelta(days=dias, minutes=minutos)

    return {
        "id": str(actividad.id),
        "hora_inicio": (actividad.hora_inicio + delta).isoformat(),
        "hora_fin": (actividad.hora_fin + delta).isoformat(),
    }


async def guardar(api, escena, cuerpo: dict):
    return await api.put(
        f"/events/{escena['evento'].id}", headers=auth(escena["admin"]), json=cuerpo
    )


async def cronograma(api, escena) -> dict[str, dict]:
    r = await api.get(
        "/schedules", headers=auth(escena["admin"]),
        params={"evento_id": str(escena["evento"].id)},
    )

    return {s["actividad"]: s for s in r.json()["data"]}


async def invitacion_de_ana(api, escena) -> dict:
    r = await api.get(
        "/participante/invitaciones", headers=auth(escena["ana"]), params={"vista": "todas"}
    )

    return next(i for i in r.json()["data"]["items"] if i["id"] == escena["invitacion"])


async def test_ampliar_el_rango_no_pide_nada(api, escena):
    r = await guardar(api, escena, rango(escena["evento"], inicio_min=-60, fin_min=60))

    assert r.status_code == 200, r.text
    assert (await invitacion_de_ana(api, escena))["estado_respuesta"] == "aceptada"


async def test_acortar_dejando_actividades_fuera_se_rechaza_con_la_lista(api, escena):
    # El evento pasa a terminar a las 12:00: «Estudio» (1:00 p. m.) queda fuera.
    r = await guardar(api, escena, rango(escena["evento"], fin_min=-120))

    assert r.status_code == 409
    datos = r.json()["data"]
    assert datos["codigo"] == "actividades_fuera_de_rango"
    assert [a["actividad"] for a in datos["actividades"]] == ["Estudio"]
    assert r.json()["message"].startswith("1 actividad del cronograma queda fuera")

    # Nada cambió: ni el evento ni el cronograma.
    r = await api.get(f"/events/{escena['evento'].id}", headers=auth(escena["admin"]))
    assert r.json()["data"]["fecha_fin"].startswith(
        escena["evento"].fecha_fin.isoformat()[:16]
    )
    assert set(await cronograma(api, escena)) == {"Alabanza", "Estudio"}


async def test_acortar_resolviendo_cada_actividad_guarda_todo_junto(api, escena):
    # «Estudio» se elimina; el evento termina a las 12:00.
    r = await guardar(
        api, escena,
        {
            **rango(escena["evento"], fin_min=-120),
            "actividades": [{"id": str(escena["estudio"].id), "eliminar": True}],
        },
    )

    assert r.status_code == 200, r.text
    assert set(await cronograma(api, escena)) == {"Alabanza"}
    assert r.json()["data"]["total_actividades"] == 1


async def test_mover_el_evento_arrastra_las_actividades_y_pide_reconfirmar(api, escena):
    # Todo se corre dos días, conservando la posición relativa.
    r = await guardar(
        api, escena,
        {
            **rango(escena["evento"], dias=2),
            "actividades": [mover(escena["alabanza"], dias=2), mover(escena["estudio"], dias=2)],
        },
    )
    assert r.status_code == 200, r.text

    actividades = await cronograma(api, escena)
    esperado = (escena["alabanza"].hora_inicio + timedelta(days=2)).isoformat()[:16]
    assert actividades["Alabanza"]["hora_inicio"].startswith(esperado)

    # A Ana, que había confirmado, se le pide reconfirmar el horario nuevo.
    inv = await invitacion_de_ana(api, escena)
    assert inv["por_reconfirmar"] is True
    assert inv["cambio"]["antes"]["hora_inicio"].startswith(
        escena["alabanza"].hora_inicio.isoformat()[:16]
    )

    # Queda en el historial.
    r = await api.get(
        "/schedules/historial", headers=auth(escena["admin"]),
        params={"evento_id": str(escena["evento"].id)},
    )
    assert sorted(c["actividad"] for c in r.json()["data"]) == ["Alabanza", "Estudio"]


async def test_mover_el_evento_sin_mover_las_actividades_no_se_guarda(api, escena):
    r = await guardar(api, escena, rango(escena["evento"], dias=2))

    assert r.status_code == 409
    assert len(r.json()["data"]["actividades"]) == 2
    assert (await invitacion_de_ana(api, escena))["estado_respuesta"] == "aceptada"


async def test_un_ajuste_que_cruza_dos_actividades_se_rechaza_entero(api, escena):
    # «Estudio» se lleva encima de «Alabanza».
    r = await guardar(
        api, escena,
        {
            **rango(escena["evento"], fin_min=-120),
            "actividades": [mover(escena["estudio"], minutos=-180)],
        },
    )

    assert r.status_code == 400
    assert "se cruza con" in r.json()["message"]
    actividades = await cronograma(api, escena)
    assert actividades["Estudio"]["hora_inicio"].startswith(
        escena["estudio"].hora_inicio.isoformat()[:16]
    )
