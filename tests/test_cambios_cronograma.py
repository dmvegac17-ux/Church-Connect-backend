from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select

from src.core.constants.enums import UserRole
from src.infrastructure.database.models.notificaciones_model import NotificacionesModel
from src.infrastructure.database.models.schedule_model import ScheduleModel
from tests.conftest import AsyncSessionLocal
from tests.conftest import auth
from tests.conftest import crear_actividad
from tests.conftest import crear_evento
from tests.conftest import crear_usuario

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def escena(api):
    """Un admin y Ana, que ya confirmó «Alabanza» (10:00–10:30 a. m.)."""
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    ana = await crear_usuario("Ana")
    evento = await crear_evento(en_dias=10)
    alabanza = await crear_actividad(evento, "Alabanza", 0)
    estudio = await crear_actividad(evento, "Estudio bíblico", 60)

    r = await api.post(
        "/admin/participaciones", headers=auth(admin),
        json={
            "actividad_id": str(alabanza.id), "participante_id": str(ana.id),
            "dias_para_confirmar": 3,
        },
    )
    assert r.status_code == 201, r.text
    invitacion = r.json()["data"]["id"]
    r = await api.post(f"/participante/invitaciones/{invitacion}/aceptar", headers=auth(ana))
    assert r.status_code == 200, r.text

    return {
        "admin": admin, "ana": ana, "evento": evento,
        "alabanza": alabanza, "estudio": estudio, "invitacion": invitacion,
    }


def horario(actividad, minutos: int, duracion: int = 30) -> dict:
    """La actividad desplazada `minutos` desde su inicio original."""
    inicio = actividad.hora_inicio + timedelta(minutes=minutos)

    return {
        "hora_inicio": inicio.isoformat(),
        "hora_fin": (inicio + timedelta(minutes=duracion)).isoformat(),
    }


async def propia(api, escena) -> dict:
    """La invitación de Ana, como la ve ella."""
    r = await api.get(
        "/participante/invitaciones", headers=auth(escena["ana"]), params={"vista": "todas"}
    )
    assert r.status_code == 200, r.text

    return next(i for i in r.json()["data"]["items"] if i["id"] == escena["invitacion"])


async def avisos_de(usuario) -> list[NotificacionesModel]:
    async with AsyncSessionLocal() as db:
        return list(
            (
                await db.execute(
                    select(NotificacionesModel)
                    .where(NotificacionesModel.usuario_id == usuario.id)
                    .order_by(NotificacionesModel.fecha_envio)
                )
            ).scalars()
        )


async def editar(api, escena, cuerpo: dict, actividad="alabanza", **params):
    return await api.put(
        f"/schedules/{escena[actividad].id}",
        headers=auth(escena["admin"]), json=cuerpo, params=params,
    )


# ── Escenario B: editar una actividad confirmada ────────────────────────

async def test_mover_el_horario_de_una_actividad_confirmada_pide_reconfirmar(api, escena):
    r = await editar(api, escena, horario(escena["alabanza"], 30))
    assert r.status_code == 200, r.text

    # El cambio se guardó y la confirmación quedó pendiente.
    inv = await propia(api, escena)
    assert inv["estado_respuesta"] == "pendiente"
    assert inv["por_reconfirmar"] is True
    assert inv["cambio"]["antes"]["actividad"] == "Alabanza"
    assert inv["fecha_limite_respuesta"] is not None

    # Ana recibe un aviso con el antes y el después, firmado.
    aviso = (await avisos_de(escena["ana"]))[-1]
    assert aviso.titulo == "Cambió una actividad que confirmaste: Alabanza"
    # Lo anterior va tachado en rojo y lo nuevo en verde, con estilos en
    # línea (lo que respetan Gmail y Outlook).
    assert '<span style="color:#b42318;text-decoration:line-through;"><s>' in aviso.mensaje
    assert "10:00 a. m. – 10:30 a. m.</s></span>" in aviso.mensaje
    assert '<span style="color:#1a7f37;">' in aviso.mensaje
    assert "10:30 a. m. – 11:00 a. m." in aviso.mensaje
    assert "Atte, Admin Prueba" in aviso.mensaje

    # Reconfirma: vuelve a estar aceptada y sin nada pendiente.
    r = await api.post(
        f"/participante/invitaciones/{escena['invitacion']}/aceptar", headers=auth(escena["ana"])
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["estado_respuesta"] == "aceptada"
    assert r.json()["data"]["por_reconfirmar"] is False
    assert r.json()["data"]["cambio"] is None


async def test_varios_cambios_seguidos_dejan_un_solo_aviso_contra_lo_confirmado(api, escena):
    antes = len(await avisos_de(escena["ana"]))

    await editar(api, escena, horario(escena["alabanza"], 30))
    r = await editar(api, escena, {"actividad": "Alabanza y adoración congregacional"})
    assert r.status_code == 200, r.text

    avisos = await avisos_de(escena["ana"])
    assert len(avisos) == antes + 1
    # El aviso compara con lo que confirmó, no con el cambio anterior.
    assert "10:00 a. m. – 10:30 a. m." in avisos[-1].mensaje
    assert "Alabanza y adoración congregacional" in avisos[-1].mensaje
    assert avisos[-1].leida is False

    inv = await propia(api, escena)
    assert inv["por_reconfirmar"] is True
    assert inv["cambio"]["antes"]["actividad"] == "Alabanza"


async def test_devolver_la_actividad_a_lo_confirmado_restituye_la_confirmacion(api, escena):
    await editar(api, escena, horario(escena["alabanza"], 30))
    r = await editar(api, escena, horario(escena["alabanza"], 0))
    assert r.status_code == 200, r.text

    inv = await propia(api, escena)
    assert inv["estado_respuesta"] == "aceptada"
    assert inv["por_reconfirmar"] is False
    aviso = (await avisos_de(escena["ana"]))[-1]
    assert aviso.titulo == "Tu confirmación sigue vigente: Alabanza"


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"actividad": "alabánza"},  # una tilde y mayúsculas
        {"descripcion": "Traer las partituras nuevas"},
    ],
)
async def test_un_retoque_de_texto_no_pide_reconfirmar(api, escena, cuerpo):
    antes = len(await avisos_de(escena["ana"]))

    r = await editar(api, escena, cuerpo)
    assert r.status_code == 200, r.text

    inv = await propia(api, escena)
    assert inv["estado_respuesta"] == "aceptada"
    assert inv["por_reconfirmar"] is False
    assert len(await avisos_de(escena["ana"])) == antes


async def test_si_el_participante_rechaza_el_cambio_la_actividad_queda_por_reasignar(api, escena):
    await editar(api, escena, horario(escena["alabanza"], 30))

    r = await api.post(
        f"/participante/invitaciones/{escena['invitacion']}/rechazar",
        headers=auth(escena["ana"]), json={"motivo": "A esa hora no puedo"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["estado_respuesta"] == "rechazada"

    r = await api.get(
        "/admin/participaciones", headers=auth(escena["admin"]),
        params={"filtro": "por_reasignar"},
    )
    assert [p["id"] for p in r.json()["data"]["items"]] == [escena["invitacion"]]
    async with AsyncSessionLocal() as db:
        assert (await db.get(ScheduleModel, escena["alabanza"].id)).responsable_id is None


async def test_reordenar_el_cronograma_tambien_pide_reconfirmar(api, escena):
    # Se intercambian los horarios de las dos actividades.
    r = await api.put(
        "/schedules/horarios", headers=auth(escena["admin"]),
        json={
            "evento_id": str(escena["evento"].id),
            "items": [
                {"id": str(escena["alabanza"].id), **horario(escena["estudio"], 0)},
                {"id": str(escena["estudio"].id), **horario(escena["alabanza"], 0)},
            ],
        },
    )
    assert r.status_code == 200, r.text

    assert (await propia(api, escena))["por_reconfirmar"] is True


# ── Escenario C: eliminar una actividad con responsable ─────────────────

async def test_eliminar_una_actividad_avisa_al_responsable_y_la_deja_cancelada(api, escena):
    admin = auth(escena["admin"])

    r = await api.delete(f"/schedules/{escena['alabanza'].id}", headers=admin)
    assert r.status_code == 200, r.text

    # Sale del cronograma…
    r = await api.get("/schedules", headers=admin, params={"evento_id": str(escena["evento"].id)})
    assert [s["actividad"] for s in r.json()["data"]] == ["Estudio bíblico"]
    assert (await api.get(f"/schedules/{escena['alabanza'].id}", headers=admin)).status_code == 404

    # …pero Ana la sigue viendo, como cancelada, y recibe el aviso.
    inv = await propia(api, escena)
    assert inv["estado_respuesta"] == "cancelada"
    assert inv["actividad"]["nombre"] == "Alabanza"
    aviso = (await avisos_de(escena["ana"]))[-1]
    assert aviso.titulo == "Se canceló la actividad: Alabanza"
    assert "Culto de prueba" in aviso.mensaje

    # No queda como pendiente de reasignar ni ocupa aforo.
    r = await api.get("/admin/participaciones", headers=admin, params={"filtro": "por_reasignar"})
    assert r.json()["data"]["items"] == []
    r = await api.get(f"/events/{escena['evento'].id}", headers=admin)
    assert r.json()["data"]["aforo"]["participantes"] == 0
    assert r.json()["data"]["total_actividades"] == 1

    # Su hueco queda libre para otra actividad.
    r = await api.post(
        "/schedules", headers=admin,
        json={
            "evento_id": str(escena["evento"].id), "actividad": "Bienvenida",
            "responsable": "Por asignar", **horario(escena["alabanza"], 0),
        },
    )
    assert r.status_code == 201, r.text


# ── Historial ───────────────────────────────────────────────────────────

async def test_el_historial_dice_quien_cambio_que_y_cuando(api, escena):
    admin = auth(escena["admin"])
    await editar(api, escena, {"actividad": "Adoración", **horario(escena["alabanza"], 30)})
    await api.delete(f"/schedules/{escena['estudio'].id}", headers=admin)

    r = await api.get(
        "/schedules/historial", headers=admin, params={"evento_id": str(escena["evento"].id)}
    )
    assert r.status_code == 200, r.text
    eliminada, editada = r.json()["data"]

    assert (eliminada["tipo"], eliminada["actividad"]) == ("eliminada", "Estudio bíblico")
    assert eliminada["autor_nombre"] == "Admin Prueba"
    assert editada["tipo"] == "editada"
    # Solo los campos que cambiaron, con su antes y su después.
    assert set(editada["antes"]) == {"actividad", "hora_inicio", "hora_fin"}
    assert editada["antes"]["actividad"] == "Alabanza"
    assert editada["despues"]["actividad"] == "Adoración"

    # Solo el administrador lo consulta.
    r = await api.get(
        "/schedules/historial", headers=auth(escena["ana"]),
        params={"evento_id": str(escena["evento"].id)},
    )
    assert r.status_code == 403


# ── Edición concurrente ─────────────────────────────────────────────────

async def test_guardar_con_una_version_vieja_del_evento_se_rechaza(api, escena):
    admin = auth(escena["admin"])
    url = f"/events/{escena['evento'].id}"
    version = (await api.get(url, headers=admin)).json()["data"]["version"]

    # Otro administrador cambia el cronograma entre tanto.
    r = await editar(api, escena, {"descripcion": "Con el coro"}, version=version)
    assert r.status_code == 200, r.text

    # Quien tenía la versión anterior no sobrescribe: ni el evento…
    r = await api.put(url, headers=admin, json={"titulo": "Otro título", "version": version})
    assert r.status_code == 409
    assert r.json()["data"]["codigo"] == "version_desactualizada"
    assert (await api.get(url, headers=admin)).json()["data"]["titulo"] == "Culto de prueba"

    # …ni su cronograma.
    r = await editar(api, escena, {"descripcion": "Sin el coro"}, version=version)
    assert r.status_code == 409
    r = await api.delete(
        f"/schedules/{escena['estudio'].id}", headers=admin, params={"version": version}
    )
    assert r.status_code == 409

    # Con la versión vigente sí.
    vigente = (await api.get(url, headers=admin)).json()["data"]["version"]
    assert vigente == version + 1
    r = await api.put(url, headers=admin, json={"titulo": "Otro título", "version": vigente})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["version"] == vigente + 1


# ── Cronogramas agrupados por evento ────────────────────────────────────

async def test_el_panel_recibe_los_cronogramas_agrupados_con_su_estado(api, escena):
    admin = auth(escena["admin"])
    sin_cronograma = await crear_evento("Vigilia", en_dias=20)
    # «Alabanza» cambia de hora: Ana debe reconfirmar.
    await editar(api, escena, horario(escena["alabanza"], 30))

    r = await api.get("/schedules/agrupados", headers=admin)
    assert r.status_code == 200, r.text
    grupos = {g["evento"]["titulo"]: g for g in r.json()["data"]}

    # Los eventos van por fecha y los que no tienen actividades también salen.
    assert list(grupos) == ["Culto de prueba", "Vigilia"]
    assert grupos["Vigilia"]["evento"]["id"] == str(sin_cronograma.id)
    assert grupos["Vigilia"]["actividades"] == []

    actividades = grupos["Culto de prueba"]["actividades"]
    assert [(a["actividad"], a["estado"]) for a in actividades] == [
        ("Alabanza", "por_reconfirmar"),
        ("Estudio bíblico", "sin_asignar"),
    ]

    # Una eliminada ya no aparece; solo el administrador lo consulta.
    await api.delete(f"/schedules/{escena['estudio'].id}", headers=admin)
    r = await api.get("/schedules/agrupados", headers=admin)
    assert [a["actividad"] for a in r.json()["data"][0]["actividades"]] == ["Alabanza"]
    assert (
        await api.get("/schedules/agrupados", headers=auth(escena["ana"]))
    ).status_code == 403


# ── Lo que ve un miembro en el cronograma ───────────────────────────────

async def test_el_miembro_solo_ve_al_responsable_que_ya_confirmo(api, escena):
    beto = await crear_usuario("Beto")
    evento = str(escena["evento"].id)

    async def cronograma(usuario) -> dict[str, dict]:
        r = await api.get("/schedules", headers=auth(usuario), params={"evento_id": evento})
        assert r.status_code == 200, r.text

        return {s["actividad"]: s for s in r.json()["data"]}

    # A «Estudio bíblico» se invita a Beto, que todavía no responde.
    r = await api.post(
        "/admin/participaciones", headers=auth(escena["admin"]),
        json={
            "actividad_id": str(escena["estudio"].id), "participante_id": str(beto.id),
            "dias_para_confirmar": 3,
        },
    )
    assert r.status_code == 201, r.text

    visto = await cronograma(escena["ana"])
    # Ana confirmó «Alabanza»: su nombre sí aparece.
    assert visto["Alabanza"]["responsable"] == "Ana Prueba"
    assert visto["Alabanza"]["responsable_confirmado"] is True
    # Beto no ha confirmado: ni su nombre ni su id.
    assert visto["Estudio bíblico"]["responsable"] == "Pendiente por confirmar"
    assert visto["Estudio bíblico"]["responsable_id"] is None
    assert visto["Estudio bíblico"]["responsable_confirmado"] is False

    r = await api.get(f"/schedules/{escena['estudio'].id}", headers=auth(escena["ana"]))
    assert r.json()["data"]["responsable"] == "Pendiente por confirmar"

    # El administrador siempre ve a quién invitó, y en qué está cada uno.
    del_admin = await cronograma(escena["admin"])
    assert del_admin["Estudio bíblico"]["responsable"] == "Beto Prueba"
    assert del_admin["Estudio bíblico"]["estado"] == "pendiente"
    assert del_admin["Alabanza"]["estado"] == "confirmado"
    # Al miembro no se le entrega ese estado.
    assert visto["Alabanza"]["estado"] is None

    # Si la actividad cambia y Ana debe reconfirmar, su nombre deja de verse.
    await editar(api, escena, horario(escena["alabanza"], 30))
    assert (await cronograma(beto))["Alabanza"]["responsable"] == "Pendiente por confirmar"

    # Y sin nadie invitado, queda por asignar.
    await api.post(
        f"/participante/invitaciones/{escena['invitacion']}/rechazar",
        headers=auth(escena["ana"]), json={},
    )
    assert (await cronograma(beto))["Alabanza"]["responsable"] == "Pendiente por asignar"
