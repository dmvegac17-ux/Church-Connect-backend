import asyncio
from datetime import UTC
from datetime import datetime
from datetime import time
from datetime import timedelta
from uuid import UUID
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy import update

from src.application.participaciones.services import BOGOTA
from src.application.participaciones.services import ParticipacionService
from src.core.constants.enums import UserRole
from src.core.security.permissions import ROLE_PERMISSIONS
from src.infrastructure.database.models.invitacion_participacion_model import (
    InvitacionParticipacionModel as Inv,
)
from src.infrastructure.database.models.notificaciones_model import NotificacionesModel
from src.infrastructure.database.models.schedule_model import ScheduleModel
from src.infrastructure.database.models.user_model import UserModel
from src.infrastructure.database.session import AsyncSessionLocal
from tests.conftest import auth
from tests.conftest import crear_actividad
from tests.conftest import crear_evento
from tests.conftest import crear_usuario

pytestmark = pytest.mark.asyncio


# ── Utilidades ──────────────────────────────────────────────────────────

async def invitar(api, admin, actividad, participante, dias=3):
    return await api.post(
        "/admin/participaciones",
        headers=auth(admin),
        json={
            "actividad_id": str(actividad.id),
            "participante_id": str(participante.id),
            "dias_para_confirmar": dias,
        }
    )


async def vencer(invitacion_id):
    """Deja la fecha límite en el pasado, como si el plazo hubiera terminado."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Inv)
            .where(Inv.id == UUID(str(invitacion_id)))
            .values(fecha_limite_respuesta=datetime.now(UTC) - timedelta(hours=1))
        )
        await db.commit()


async def leer(modelo, id_):
    async with AsyncSessionLocal() as db:
        return (
            await db.execute(select(modelo).where(modelo.id == UUID(str(id_))))
        ).scalar_one()


async def listar_admin(api, admin, **params):
    r = await api.get("/admin/participaciones", headers=auth(admin), params=params)
    assert r.status_code == 200, r.text

    return r.json()["data"]


@pytest.fixture
async def escena(api):
    """Un admin, dos participantes, un miembro y un evento con dos actividades."""
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    ana = await crear_usuario("Ana")
    beto = await crear_usuario("Beto")
    miembro = await crear_usuario("Mila", UserRole.MEMBER)
    evento = await crear_evento(en_dias=10)
    alabanza = await crear_actividad(evento, "Alabanza", 0)
    estudio = await crear_actividad(evento, "Estudio bíblico", 30)

    return {
        "admin": admin, "ana": ana, "beto": beto, "miembro": miembro,
        "evento": evento, "alabanza": alabanza, "estudio": estudio,
    }


# ── Permisos ────────────────────────────────────────────────────────────

async def test_participante_hereda_los_permisos_del_miembro():
    assert ROLE_PERMISSIONS[UserRole.MEMBER] <= ROLE_PERMISSIONS[UserRole.PARTICIPANT]


async def test_participante_conserva_el_acceso_del_miembro(api, escena):
    for ruta in ("/events", "/schedules", "/ministries", "/notificaciones"):
        como_miembro = await api.get(ruta, headers=auth(escena["miembro"]))
        como_participante = await api.get(ruta, headers=auth(escena["ana"]))

        assert como_miembro.status_code == 200, ruta
        assert como_participante.status_code == 200, ruta


async def test_miembro_sin_rol_participante_recibe_403(api, escena):
    cabeceras = auth(escena["miembro"])

    assert (await api.get("/participante/invitaciones", headers=cabeceras)).status_code == 403
    assert (
        await api.post(f"/participante/invitaciones/{uuid4()}/aceptar", headers=cabeceras)
    ).status_code == 403


async def test_participante_recibe_403_en_admin(api, escena):
    cabeceras = auth(escena["ana"])
    cuerpo = {"participante_id": str(escena["beto"].id), "dias_para_confirmar": 3}

    assert (await api.get("/admin/participaciones", headers=cabeceras)).status_code == 403
    assert (
        await api.get(
            "/admin/participantes/elegibles",
            headers=cabeceras,
            params={"actividad_id": str(escena["alabanza"].id)}
        )
    ).status_code == 403

    for accion in ("cancelar", "reenviar", "reasignar", "revocar"):
        r = await api.post(
            f"/admin/participaciones/{uuid4()}/{accion}", headers=cabeceras, json=cuerpo
        )
        assert r.status_code == 403, accion


async def test_administrador_no_responde_invitaciones(api, escena):
    r = await api.get("/participante/invitaciones", headers=auth(escena["admin"]))

    assert r.status_code == 403


# ── Participante ────────────────────────────────────────────────────────

async def test_participante_solo_ve_sus_invitaciones(api, escena):
    propia = (await invitar(api, escena["admin"], escena["alabanza"], escena["ana"])).json()["data"]
    ajena = (await invitar(api, escena["admin"], escena["estudio"], escena["beto"])).json()["data"]

    r = await api.get("/participante/invitaciones", headers=auth(escena["ana"]))
    data = r.json()["data"]

    assert [i["id"] for i in data["items"]] == [propia["id"]]
    assert data["conteos"] == {"pendientes": 1, "respondidas": 0, "todas": 1}

    item = data["items"][0]
    assert item["actividad"]["lugar"] == "Templo de prueba"
    assert item["responsable"]["nombre"] == "Admin Prueba"
    # Nada administrativo ni de envío en el DTO del participante.
    for campo in ("estado_envio", "ultimo_error_envio", "participante", "acciones_permitidas"):
        assert campo not in item

    # La invitación ajena responde igual que una que no existe.
    for accion in ("aceptar", "rechazar"):
        r = await api.post(
            f"/participante/invitaciones/{ajena['id']}/{accion}", headers=auth(escena["ana"])
        )
        assert r.status_code == 404

    assert (await leer(Inv, ajena["id"])).estado_respuesta == "pendiente"


async def test_aceptar_y_no_poder_cambiar_la_respuesta(api, escena):
    inv = (await invitar(api, escena["admin"], escena["alabanza"], escena["ana"])).json()["data"]
    cabeceras = auth(escena["ana"])

    r = await api.post(f"/participante/invitaciones/{inv['id']}/aceptar", headers=cabeceras)
    assert r.status_code == 200
    assert r.json()["data"]["estado_respuesta"] == "aceptada"
    assert r.json()["data"]["fecha_respuesta"] is not None

    for accion in ("aceptar", "rechazar"):
        r = await api.post(f"/participante/invitaciones/{inv['id']}/{accion}", headers=cabeceras)
        assert r.status_code == 409
        assert r.json()["data"] == {"estado_actual": "aceptada"}


async def test_rechazar_con_motivo_y_limite_de_255(api, escena):
    inv = (await invitar(api, escena["admin"], escena["alabanza"], escena["ana"])).json()["data"]
    url = f"/participante/invitaciones/{inv['id']}/rechazar"

    r = await api.post(url, headers=auth(escena["ana"]), json={"motivo": "x" * 256})
    assert r.status_code == 422
    assert (await leer(Inv, inv["id"])).estado_respuesta == "pendiente"

    r = await api.post(url, headers=auth(escena["ana"]), json={"motivo": "x" * 255})
    assert r.status_code == 200
    assert r.json()["data"]["estado_respuesta"] == "rechazada"
    assert r.json()["data"]["motivo_rechazo"] == "x" * 255

    # La actividad queda sin persona asignada.
    assert (await leer(ScheduleModel, escena["alabanza"].id)).responsable_id is None


async def test_rechazar_sin_cuerpo(api, escena):
    inv = (await invitar(api, escena["admin"], escena["alabanza"], escena["ana"])).json()["data"]

    r = await api.post(
        f"/participante/invitaciones/{inv['id']}/rechazar", headers=auth(escena["ana"])
    )

    assert r.status_code == 200
    assert r.json()["data"]["motivo_rechazo"] is None


async def test_no_se_responde_una_invitacion_vencida_o_cancelada(api, escena):
    vencida = (await invitar(api, escena["admin"], escena["alabanza"], escena["ana"])).json()["data"]
    cancelada = (await invitar(api, escena["admin"], escena["estudio"], escena["ana"])).json()["data"]

    # Vence sin que haya corrido ninguna tarea: lo detecta el propio endpoint.
    await vencer(vencida["id"])
    r = await api.post(
        f"/admin/participaciones/{cancelada['id']}/cancelar", headers=auth(escena["admin"])
    )
    assert r.status_code == 200

    for inv, estado in ((vencida, "vencida"), (cancelada, "cancelada")):
        for accion in ("aceptar", "rechazar"):
            r = await api.post(
                f"/participante/invitaciones/{inv['id']}/{accion}", headers=auth(escena["ana"])
            )
            assert r.status_code == 409
            assert r.json()["data"]["estado_actual"] == estado

    data = (
        await api.get(
            "/participante/invitaciones", headers=auth(escena["ana"]), params={"vista": "respondidas"}
        )
    ).json()["data"]
    assert {i["estado_respuesta"] for i in data["items"]} == {"vencida", "cancelada"}
    assert data["conteos"] == {"pendientes": 0, "respondidas": 2, "todas": 2}


async def test_dos_respuestas_concurrentes_solo_registran_una(api, escena):
    inv = (await invitar(api, escena["admin"], escena["alabanza"], escena["ana"])).json()["data"]
    cabeceras = auth(escena["ana"])

    respuestas = await asyncio.gather(
        api.post(f"/participante/invitaciones/{inv['id']}/aceptar", headers=cabeceras),
        api.post(f"/participante/invitaciones/{inv['id']}/rechazar", headers=cabeceras),
    )

    assert sorted(r.status_code for r in respuestas) == [200, 409]
    ganadora = next(r for r in respuestas if r.status_code == 200).json()["data"]
    assert (await leer(Inv, inv["id"])).estado_respuesta == ganadora["estado_respuesta"]


# ── Invitaciones activas por actividad ──────────────────────────────────

async def test_una_actividad_no_admite_dos_invitaciones_activas(api, escena):
    assert (await invitar(api, escena["admin"], escena["alabanza"], escena["ana"])).status_code == 201

    r = await invitar(api, escena["admin"], escena["alabanza"], escena["beto"])
    assert r.status_code == 409
    assert r.json()["data"] == {"estado_actual": "pendiente"}


async def test_un_participante_puede_estar_en_varias_actividades(api, escena):
    assert (await invitar(api, escena["admin"], escena["alabanza"], escena["ana"])).status_code == 201
    assert (await invitar(api, escena["admin"], escena["estudio"], escena["ana"])).status_code == 201

    data = (await api.get("/participante/invitaciones", headers=auth(escena["ana"]))).json()["data"]
    assert data["conteos"]["pendientes"] == 2


async def test_invitar_a_un_miembro_le_da_el_rol_participante(api, escena):
    r = await invitar(api, escena["admin"], escena["alabanza"], escena["miembro"])
    assert r.status_code == 201

    assert (await leer(UserModel, escena["miembro"].id)).rol == UserRole.PARTICIPANT
    assert (
        await api.get("/participante/invitaciones", headers=auth(escena["miembro"]))
    ).status_code == 200


async def test_no_se_invita_a_administradores_ni_inactivos(api, escena):
    inactivo = await crear_usuario("Ines", activo=False)

    for usuario in (escena["admin"], inactivo):
        r = await invitar(api, escena["admin"], escena["alabanza"], usuario)
        assert r.status_code == 422
        assert r.json()["data"]["campo"] == "participante_id"


# ── Correo ──────────────────────────────────────────────────────────────

async def test_fallo_de_correo_no_cambia_la_respuesta(api, escena, correo):
    correo.fallar = True
    inv = (await invitar(api, escena["admin"], escena["alabanza"], escena["ana"])).json()["data"]

    assert inv["estado_envio"] == "error"
    assert inv["estado_respuesta"] == "pendiente"
    assert inv["fecha_envio"] is None
    assert inv["acciones_permitidas"] == ["reenviar", "cancelar"]

    # Sigue visible para el participante, que puede responder en la app.
    data = (await api.get("/participante/invitaciones", headers=auth(escena["ana"]))).json()["data"]
    assert data["conteos"]["pendientes"] == 1

    # Reintento fallido: 200 con la fila en error, no un 500.
    r = await api.post(
        f"/admin/participaciones/{inv['id']}/reenviar", headers=auth(escena["admin"])
    )
    assert r.status_code == 200
    assert r.json()["data"]["estado_envio"] == "error"
    assert r.json()["data"]["intentos_envio"] == 2

    correo.fallar = False
    r = await api.post(
        f"/admin/participaciones/{inv['id']}/reenviar", headers=auth(escena["admin"])
    )
    assert r.json()["data"]["estado_envio"] == "enviada"
    assert r.json()["data"]["estado_respuesta"] == "pendiente"
    assert r.json()["data"]["acciones_permitidas"] == ["cancelar"]

    # Ya enviada: no hay nada que reenviar.
    r = await api.post(
        f"/admin/participaciones/{inv['id']}/reenviar", headers=auth(escena["admin"])
    )
    assert r.status_code == 409


# ── Supervisión del administrador ───────────────────────────────────────

async def test_rechazo_vencimiento_y_cancelacion_quedan_por_reasignar(api, escena):
    tercera = await crear_actividad(escena["evento"], "Lectura", 60)
    admin = escena["admin"]

    rechazada = (await invitar(api, admin, escena["alabanza"], escena["ana"])).json()["data"]
    vencida = (await invitar(api, admin, escena["estudio"], escena["ana"])).json()["data"]
    cancelada = (await invitar(api, admin, tercera, escena["beto"])).json()["data"]

    await api.post(f"/participante/invitaciones/{rechazada['id']}/rechazar", headers=auth(escena["ana"]))
    await vencer(vencida["id"])
    await api.post(f"/admin/participaciones/{cancelada['id']}/cancelar", headers=auth(admin))

    data = await listar_admin(api, admin, filtro="por_reasignar")

    assert {i["id"] for i in data["items"]} == {rechazada["id"], vencida["id"], cancelada["id"]}
    assert all(i["requiere_reasignacion"] for i in data["items"])
    assert all(i["acciones_permitidas"] == ["reasignar"] for i in data["items"])
    assert data["conteos"]["por_reasignar"] == 3
    assert data["alertas"] == {"actividades_por_reasignar": 3, "invitaciones_error_envio": 0}


async def test_conteos_y_alertas_coinciden_con_los_items(api, escena, correo):
    admin = escena["admin"]
    tercera = await crear_actividad(escena["evento"], "Lectura", 60)
    otro_evento = await crear_evento("Vigilia de oración", en_dias=8)
    cuarta = await crear_actividad(otro_evento, "Bienvenida", 0)

    aceptada = (await invitar(api, admin, escena["alabanza"], escena["ana"])).json()["data"]
    await api.post(f"/participante/invitaciones/{aceptada['id']}/aceptar", headers=auth(escena["ana"]))
    rechazada = (await invitar(api, admin, escena["estudio"], escena["beto"])).json()["data"]
    await api.post(f"/participante/invitaciones/{rechazada['id']}/rechazar", headers=auth(escena["beto"]))
    await invitar(api, admin, tercera, escena["ana"])
    correo.fallar = True
    await invitar(api, admin, cuarta, escena["beto"])

    todas = await listar_admin(api, admin)
    assert todas["conteos"] == {
        "todas": 4, "pendientes": 2, "aceptadas": 1, "por_reasignar": 1, "error_envio": 1,
    }
    assert todas["alertas"] == {"actividades_por_reasignar": 1, "invitaciones_error_envio": 1}

    # Orden por fecha y hora de la actividad: primero el evento más cercano.
    assert todas["items"][0]["actividad"]["nombre"] == "Bienvenida"

    for filtro in ("todas", "pendientes", "aceptadas", "por_reasignar", "error_envio"):
        data = await listar_admin(api, admin, filtro=filtro)
        assert len(data["items"]) == data["conteos"][filtro], filtro

    # "Error de envío" se cruza con "Pendientes".
    con_error = (await listar_admin(api, admin, filtro="error_envio"))["items"][0]
    assert con_error["estado_respuesta"] == "pendiente"


async def test_busqueda_sin_mayusculas_ni_tildes_y_conteos_filtrados(api, escena):
    admin = escena["admin"]
    await invitar(api, admin, escena["alabanza"], escena["ana"])
    await invitar(api, admin, escena["estudio"], escena["beto"])

    por_actividad = await listar_admin(api, admin, q="ESTUDIO BIBLICO")
    assert [i["actividad"]["nombre"] for i in por_actividad["items"]] == ["Estudio bíblico"]
    assert por_actividad["conteos"]["todas"] == 1
    assert por_actividad["conteos"]["pendientes"] == 1

    por_participante = await listar_admin(api, admin, q="ana pru")
    assert [i["participante"]["nombre_completo"] for i in por_participante["items"]] == ["Ana Prueba"]

    por_evento = await listar_admin(api, admin, q="culto")
    assert por_evento["conteos"]["todas"] == 2

    assert (await listar_admin(api, admin, q="no existe"))["items"] == []


async def test_paginacion(api, escena):
    admin = escena["admin"]
    await invitar(api, admin, escena["alabanza"], escena["ana"])
    await invitar(api, admin, escena["estudio"], escena["beto"])

    r = await api.get(
        "/admin/participaciones", headers=auth(admin), params={"pagina": 2, "por_pagina": 1}
    )

    assert r.json()["meta"] == {"total": 2, "pagina": 2, "por_pagina": 1}
    assert [i["actividad"]["nombre"] for i in r.json()["data"]["items"]] == ["Estudio bíblico"]


# ── Reasignar ───────────────────────────────────────────────────────────

async def test_reasignar_enlaza_la_nueva_y_saca_la_actividad_de_por_reasignar(api, escena):
    admin = escena["admin"]
    original = (await invitar(api, admin, escena["alabanza"], escena["ana"])).json()["data"]
    await api.post(
        f"/participante/invitaciones/{original['id']}/rechazar",
        headers=auth(escena["ana"]),
        json={"motivo": "Estaré de viaje"}
    )

    datos = (
        await api.get(f"/admin/participaciones/{original['id']}/reasignacion", headers=auth(admin))
    ).json()["data"]
    assert datos["modo"] == "reasignar"
    assert datos["motivo_liberacion"] == "rechazo"
    assert datos["motivo_rechazo"] == "Estaré de viaje"
    assert datos["dias_hasta_evento"] == 10
    assert datos["dias_para_confirmar_max"] == 9

    r = await api.post(
        f"/admin/participaciones/{original['id']}/reasignar",
        headers=auth(admin),
        json={"participante_id": str(escena["beto"].id), "dias_para_confirmar": 3}
    )
    assert r.status_code == 200, r.text
    resultado = r.json()["data"]

    assert resultado["original"]["estado_respuesta"] == "reasignada"
    assert resultado["original"]["estado_previo"] == "rechazada"
    assert resultado["original"]["acciones_permitidas"] == []
    assert resultado["original"]["reemplazo"]["participante"]["nombre_completo"] == "Beto Prueba"
    assert resultado["nueva"]["estado_respuesta"] == "pendiente"
    assert resultado["nueva"]["participante"]["id"] == str(escena["beto"].id)

    # Fecha límite: fin del día (Bogotá) de hoy + 3.
    esperado = datetime.combine(
        datetime.now(UTC).astimezone(BOGOTA).date() + timedelta(days=3),
        time(23, 59, 59),
        BOGOTA
    )
    limite = datetime.fromisoformat(resultado["nueva"]["fecha_limite_respuesta"])
    assert limite == esperado

    nueva = await leer(Inv, resultado["nueva"]["id"])
    assert str(nueva.reemplaza_invitacion_id) == original["id"]
    assert (await leer(ScheduleModel, escena["alabanza"].id)).responsable_id == escena["beto"].id

    data = await listar_admin(api, admin, filtro="por_reasignar")
    assert data["items"] == []
    assert data["alertas"]["actividades_por_reasignar"] == 0

    # El participante original sigue viendo su rechazo, no un estado interno.
    propias = (
        await api.get("/participante/invitaciones", headers=auth(escena["ana"]), params={"vista": "todas"})
    ).json()["data"]["items"]
    assert propias[0]["estado_respuesta"] == "rechazada"

    # La original ya no admite otra reasignación.
    r = await api.post(
        f"/admin/participaciones/{original['id']}/reasignar",
        headers=auth(admin),
        json={"participante_id": str(escena["ana"].id), "dias_para_confirmar": 3}
    )
    assert r.status_code == 409
    assert r.json()["data"]["estado_actual"] == "reasignada"


async def test_reasignar_exige_una_persona_distinta_y_una_invitacion_liberada(api, escena):
    admin = escena["admin"]
    inv = (await invitar(api, admin, escena["alabanza"], escena["ana"])).json()["data"]
    url = f"/admin/participaciones/{inv['id']}/reasignar"
    cuerpo = {"participante_id": str(escena["beto"].id), "dias_para_confirmar": 3}

    # Sigue pendiente: no requiere reasignación.
    r = await api.post(url, headers=auth(admin), json=cuerpo)
    assert r.status_code == 409
    assert r.json()["data"]["estado_actual"] == "pendiente"

    await api.post(f"/participante/invitaciones/{inv['id']}/rechazar", headers=auth(escena["ana"]))

    r = await api.post(
        url, headers=auth(admin),
        json={"participante_id": str(escena["ana"].id), "dias_para_confirmar": 3}
    )
    assert r.status_code == 422
    assert (await leer(Inv, inv["id"])).estado_respuesta == "rechazada"


@pytest.mark.parametrize("dias", [0, 31, 2.5, "tres", "", None, 10])
async def test_dias_para_confirmar_invalidos(api, escena, dias):
    admin = escena["admin"]
    inv = (await invitar(api, admin, escena["alabanza"], escena["ana"])).json()["data"]
    await api.post(f"/participante/invitaciones/{inv['id']}/rechazar", headers=auth(escena["ana"]))

    r = await api.post(
        f"/admin/participaciones/{inv['id']}/reasignar",
        headers=auth(admin),
        json={"participante_id": str(escena["beto"].id), "dias_para_confirmar": dias}
    )

    assert r.status_code == 422, r.text
    assert (await leer(Inv, inv["id"])).estado_respuesta == "rechazada"

    if dias == 10:
        # Mayor que `dias_hasta_evento − 1`: el error trae el límite.
        assert r.json()["data"] == {
            "campo": "dias_para_confirmar",
            "dias_hasta_evento": 10,
            "dias_para_confirmar_max": 9,
        }


async def test_el_limite_exacto_de_dias_se_acepta(api, escena):
    admin = escena["admin"]
    inv = (await invitar(api, admin, escena["alabanza"], escena["ana"], dias=9)).json()["data"]
    await api.post(f"/participante/invitaciones/{inv['id']}/rechazar", headers=auth(escena["ana"]))

    r = await api.post(
        f"/admin/participaciones/{inv['id']}/reasignar",
        headers=auth(admin),
        json={"participante_id": str(escena["beto"].id), "dias_para_confirmar": 9}
    )

    assert r.status_code == 200, r.text


async def test_si_falla_la_creacion_la_original_conserva_su_estado(api, escena, monkeypatch):
    admin = escena["admin"]
    inv = (await invitar(api, admin, escena["alabanza"], escena["ana"])).json()["data"]
    await api.post(f"/participante/invitaciones/{inv['id']}/rechazar", headers=auth(escena["ana"]))

    def falla(*_args, **_kwargs):
        raise RuntimeError("fallo simulado al crear la invitación")

    monkeypatch.setattr(ParticipacionService, "_nueva_invitacion", falla)

    r = await api.post(
        f"/admin/participaciones/{inv['id']}/reasignar",
        headers=auth(admin),
        json={"participante_id": str(escena["beto"].id), "dias_para_confirmar": 3}
    )
    assert r.status_code == 500

    original = await leer(Inv, inv["id"])
    assert original.estado_respuesta == "rechazada"
    assert original.estado_previo is None


async def test_dos_reasignaciones_concurrentes_solo_registran_una(api, escena):
    admin = escena["admin"]
    carla = await crear_usuario("Carla")
    inv = (await invitar(api, admin, escena["alabanza"], escena["ana"])).json()["data"]
    await api.post(f"/participante/invitaciones/{inv['id']}/rechazar", headers=auth(escena["ana"]))

    url = f"/admin/participaciones/{inv['id']}/reasignar"
    respuestas = await asyncio.gather(
        api.post(url, headers=auth(admin), json={"participante_id": str(escena["beto"].id), "dias_para_confirmar": 3}),
        api.post(url, headers=auth(admin), json={"participante_id": str(carla.id), "dias_para_confirmar": 3}),
    )

    assert sorted(r.status_code for r in respuestas) == [200, 409]

    async with AsyncSessionLocal() as db:
        activas = (
            await db.execute(
                select(Inv).where(
                    Inv.actividad_id == escena["alabanza"].id,
                    Inv.estado_respuesta.in_(("pendiente", "aceptada"))
                )
            )
        ).scalars().all()
    assert len(activas) == 1


# ── Revocar ─────────────────────────────────────────────────────────────

async def test_revocar_una_aceptada_crea_la_nueva_y_notifica(api, escena, correo):
    admin = escena["admin"]
    inv = (await invitar(api, admin, escena["alabanza"], escena["ana"])).json()["data"]
    await api.post(f"/participante/invitaciones/{inv['id']}/aceptar", headers=auth(escena["ana"]))

    fila = (await listar_admin(api, admin, filtro="aceptadas"))["items"][0]
    assert fila["acciones_permitidas"] == ["revocar_y_cambiar"]

    datos = (
        await api.get(f"/admin/participaciones/{inv['id']}/reasignacion", headers=auth(admin))
    ).json()["data"]
    assert datos["modo"] == "revocar"
    assert datos["motivo_liberacion"] == "aceptada"

    correo.enviados.clear()
    r = await api.post(
        f"/admin/participaciones/{inv['id']}/revocar",
        headers=auth(admin),
        json={"participante_id": str(escena["beto"].id), "dias_para_confirmar": 2}
    )
    assert r.status_code == 200, r.text
    resultado = r.json()["data"]

    assert resultado["original"]["estado_respuesta"] == "revocada"
    assert resultado["original"]["notificacion_revocacion_estado"] == "enviada"
    assert resultado["original"]["requiere_reasignacion"] is False
    assert resultado["original"]["acciones_permitidas"] == []
    assert resultado["nueva"]["estado_respuesta"] == "pendiente"

    original = await leer(Inv, inv["id"])
    assert original.revocada_por == admin.id
    assert original.fecha_revocacion is not None

    # Correo real (simulado en pruebas) al revocado y a la nueva persona.
    destinatarios = {c["to"]: c["titulo"] for c in correo.enviados}
    assert "Ya no estás asignado" in destinatarios[escena["ana"].correo]
    assert "Invitación a participar" in destinatarios[escena["beto"].correo]

    # Y aviso dentro de la aplicación.
    async with AsyncSessionLocal() as db:
        avisos = (
            await db.execute(
                select(NotificacionesModel.titulo).where(
                    NotificacionesModel.usuario_id == escena["ana"].id
                )
            )
        ).scalars().all()
    assert any("Ya no estás asignado" in titulo for titulo in avisos)

    # El revocado la ve en "Respondidas" como revocada, ya no como confirmada.
    propias = (
        await api.get(
            "/participante/invitaciones", headers=auth(escena["ana"]), params={"vista": "respondidas"}
        )
    ).json()["data"]["items"]
    assert [i["estado_respuesta"] for i in propias] == ["revocada"]

    # Una revocada nunca cuenta como pendiente de asignación.
    assert (await listar_admin(api, admin, filtro="por_reasignar"))["items"] == []


async def test_fallo_al_notificar_la_revocacion_no_la_deshace(api, escena, correo):
    admin = escena["admin"]
    inv = (await invitar(api, admin, escena["alabanza"], escena["ana"])).json()["data"]
    await api.post(f"/participante/invitaciones/{inv['id']}/aceptar", headers=auth(escena["ana"]))

    correo.fallar = True
    r = await api.post(
        f"/admin/participaciones/{inv['id']}/revocar",
        headers=auth(admin),
        json={"participante_id": str(escena["beto"].id), "dias_para_confirmar": 2}
    )

    assert r.status_code == 200
    assert r.json()["data"]["original"]["estado_respuesta"] == "revocada"
    assert r.json()["data"]["original"]["notificacion_revocacion_estado"] == "error"
    assert r.json()["data"]["nueva"]["estado_envio"] == "error"
    assert r.json()["data"]["nueva"]["estado_respuesta"] == "pendiente"


async def test_solo_se_revoca_una_aceptada(api, escena):
    admin = escena["admin"]
    inv = (await invitar(api, admin, escena["alabanza"], escena["ana"])).json()["data"]

    r = await api.post(
        f"/admin/participaciones/{inv['id']}/revocar",
        headers=auth(admin),
        json={"participante_id": str(escena["beto"].id), "dias_para_confirmar": 2}
    )

    assert r.status_code == 409
    assert r.json()["data"]["estado_actual"] == "pendiente"


# ── Actividades sin plazo ───────────────────────────────────────────────

@pytest.mark.parametrize("en_dias", [1, -2])
async def test_actividad_de_manana_o_pasada_no_admite_cambios(api, escena, en_dias):
    admin = escena["admin"]
    evento = await crear_evento("Evento cercano", en_dias=en_dias)
    liberada_act = await crear_actividad(evento, "Lectura", 0)
    aceptada_act = await crear_actividad(evento, "Oración", 30)

    # No se pueden crear por la API (ya no hay plazo): se insertan directamente.
    ahora = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        liberada = Inv(
            id=uuid4(), actividad_id=liberada_act.id, participante_id=escena["ana"].id,
            estado_respuesta="vencida", estado_envio="enviada", intentos_envio=1,
            created_at=ahora, updated_at=ahora
        )
        aceptada = Inv(
            id=uuid4(), actividad_id=aceptada_act.id, participante_id=escena["ana"].id,
            estado_respuesta="aceptada", estado_envio="enviada", intentos_envio=1,
            created_at=ahora, updated_at=ahora
        )
        db.add_all([liberada, aceptada])
        await db.commit()

    todas = await listar_admin(api, admin)
    filas = {i["id"]: i for i in todas["items"]}

    # Conservan su badge de estado, pero sin acciones ni alerta.
    assert filas[str(liberada.id)]["estado_respuesta"] == "vencida"
    assert filas[str(liberada.id)]["requiere_reasignacion"] is False
    assert filas[str(liberada.id)]["acciones_permitidas"] == []
    assert filas[str(aceptada.id)]["acciones_permitidas"] == []
    assert todas["conteos"]["por_reasignar"] == 0
    assert todas["alertas"]["actividades_por_reasignar"] == 0

    cuerpo = {"participante_id": str(escena["beto"].id), "dias_para_confirmar": 1}

    r = await api.post(f"/admin/participaciones/{liberada.id}/reasignar", headers=auth(admin), json=cuerpo)
    assert r.status_code == 422
    assert r.json()["data"]["dias_para_confirmar_max"] < 1

    r = await api.post(f"/admin/participaciones/{aceptada.id}/revocar", headers=auth(admin), json=cuerpo)
    assert r.status_code == 422

    assert (await invitar(api, admin, liberada_act, escena["beto"], dias=1)).status_code == 422
    assert (await leer(Inv, liberada.id)).estado_respuesta == "vencida"
    assert (await leer(Inv, aceptada.id)).estado_respuesta == "aceptada"


# ── Elegibles y cronograma ──────────────────────────────────────────────

async def test_elegibles_excluye_al_asignado_y_marca_cruces(api, escena):
    admin = escena["admin"]
    otro_evento = await crear_evento("Otro evento", en_dias=10)
    cruzada = await crear_actividad(otro_evento, "Bienvenida", 15)

    await invitar(api, admin, escena["alabanza"], escena["ana"])
    await invitar(api, admin, cruzada, escena["beto"])

    r = await api.get(
        "/admin/participantes/elegibles",
        headers=auth(admin),
        params={"actividad_id": str(escena["alabanza"].id)}
    )
    assert r.status_code == 200
    elegibles = {e["nombre_completo"]: e for e in r.json()["data"]}

    assert "Ana Prueba" not in elegibles          # asignada actualmente
    assert "Admin Prueba" not in elegibles        # los administradores no se invitan
    assert elegibles["Beto Prueba"]["cruce_horario"] is True
    assert elegibles["Mila Prueba"]["cruce_horario"] is False

    r = await api.get(
        "/admin/participantes/elegibles",
        headers=auth(admin),
        params={"actividad_id": str(escena["alabanza"].id), "q": "BETO"}
    )
    assert [e["nombre_completo"] for e in r.json()["data"]] == ["Beto Prueba"]


async def test_invitacion_vigente_por_actividad_del_evento(api, escena):
    admin = escena["admin"]
    inv = (await invitar(api, admin, escena["alabanza"], escena["ana"])).json()["data"]
    await api.post(f"/participante/invitaciones/{inv['id']}/rechazar", headers=auth(escena["ana"]))
    await invitar(api, admin, escena["alabanza"], escena["beto"])

    r = await api.get(
        f"/admin/participaciones/eventos/{escena['evento'].id}", headers=auth(admin)
    )
    filas = r.json()["data"]

    # Una sola fila por actividad: la vigente, no el historial.
    assert len(filas) == 1
    assert filas[0]["participante"]["nombre_completo"] == "Beto Prueba"
    assert filas[0]["estado_respuesta"] == "pendiente"

    # La rechazada quedó como historial enlazado a la nueva.
    assert (await leer(Inv, inv["id"])).estado_respuesta == "reasignada"

    r = await api.get("/schedules", headers=auth(admin), params={"evento_id": str(escena["evento"].id)})
    por_nombre = {s["actividad"]: s for s in r.json()["data"]}
    assert por_nombre["Alabanza"]["responsable_id"] == str(escena["beto"].id)
    assert por_nombre["Alabanza"]["responsable"] == "Beto Prueba"
    assert por_nombre["Estudio bíblico"]["responsable_id"] is None
