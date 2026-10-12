import pytest

from src.core.constants.enums import UserRole
from tests.conftest import auth
from tests.conftest import crear_actividad
from tests.conftest import crear_evento
from tests.conftest import crear_usuario

pytestmark = pytest.mark.asyncio


async def test_un_evento_finalizado_no_se_edita(api):
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    pasado = await crear_evento("Vigilia de ayer", en_dias=-1)
    url = f"/events/{pasado.id}"

    for cambio in (
        {"titulo": "Otro título"},
        {"capacidad": 500},
        {"lugar": "Otro lugar"},
        # Ni siquiera para moverlo al futuro.
        {
            "fecha_inicio": "2099-01-01T10:00:00Z",
            "fecha_fin": "2099-01-01T12:00:00Z",
        },
    ):
        r = await api.put(url, headers=auth(admin), json=cambio)

        assert r.status_code == 409, cambio
        assert r.json()["message"] == (
            "El evento ya finalizó: no se puede editar, solo eliminar."
        )
        assert r.json()["data"] == {"codigo": "evento_finalizado"}

    detalle = (await api.get(url, headers=auth(admin))).json()["data"]
    assert detalle["titulo"] == "Vigilia de ayer"
    assert detalle["capacidad"] == 50
    assert detalle["lugar"] == "Templo de prueba"


async def test_un_evento_finalizado_si_se_puede_eliminar(api):
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    pasado = await crear_evento("Vigilia de ayer", en_dias=-1)

    r = await api.delete(f"/events/{pasado.id}", headers=auth(admin))
    assert r.status_code == 200

    r = await api.get(f"/events/{pasado.id}", headers=auth(admin))
    assert r.status_code == 404


async def test_intentar_editar_un_finalizado_no_avisa_a_sus_inscritos(api, correo):
    from datetime import UTC
    from datetime import datetime

    from src.infrastructure.database.models.registration_model import RegistrationModel
    from src.infrastructure.database.session import AsyncSessionLocal
    from uuid import uuid4

    admin = await crear_usuario("Admin", UserRole.ADMIN)
    ana = await crear_usuario("Ana")
    pasado = await crear_evento("Vigilia de ayer", en_dias=-1)
    # Se inscribió cuando el evento todavía no había empezado.
    async with AsyncSessionLocal() as db:
        db.add(
            RegistrationModel(
                id=uuid4(),
                usuario_id=ana.id,
                evento_id=pasado.id,
                fecha_inscripcion=datetime.now(UTC),
            )
        )
        await db.commit()

    r = await api.put(
        f"/events/{pasado.id}", headers=auth(admin), json={"lugar": "Finca La Esperanza"}
    )

    assert r.status_code == 409
    assert correo.enviados == []


async def test_un_evento_en_curso_o_futuro_si_se_edita(api):
    from datetime import UTC
    from datetime import datetime
    from datetime import timedelta
    from uuid import uuid4

    from src.infrastructure.database.models.event_model import EventModel
    from src.infrastructure.database.session import AsyncSessionLocal

    admin = await crear_usuario("Admin", UserRole.ADMIN)
    futuro = await crear_evento("Culto del domingo", en_dias=5)
    # Empezó hace una hora y termina en una hora.
    ahora = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        en_curso = EventModel(
            id=uuid4(),
            titulo="En curso",
            descripcion="Evento de prueba",
            fecha_inicio=ahora - timedelta(hours=1),
            fecha_fin=ahora + timedelta(hours=1),
            lugar="Templo de prueba",
            capacidad=50,
            creado_por="tests",
        )
        db.add(en_curso)
        await db.commit()

    for evento in (futuro, en_curso):
        r = await api.put(
            f"/events/{evento.id}", headers=auth(admin), json={"titulo": "Renombrado"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["titulo"] == "Renombrado"


# ── Cronograma y participantes de un evento finalizado ──────────────────

CRONOGRAMA_CERRADO = "El evento ya finalizó: su cronograma no se puede modificar."


async def test_el_cronograma_de_un_evento_finalizado_no_se_modifica(api):
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    pasado = await crear_evento("Vigilia de ayer", en_dias=-1)
    actividad = await crear_actividad(pasado, "Alabanza")
    cabeceras = auth(admin)

    crear = await api.post(
        "/schedules",
        headers=cabeceras,
        json={
            "evento_id": str(pasado.id),
            "actividad": "Oración final",
            "hora_inicio": (pasado.fecha_inicio).isoformat(),
            "hora_fin": (pasado.fecha_fin).isoformat(),
            "responsable": "Por asignar",
        },
    )
    editar = await api.put(
        f"/schedules/{actividad.id}", headers=cabeceras, json={"actividad": "Otra"}
    )
    borrar = await api.delete(f"/schedules/{actividad.id}", headers=cabeceras)

    for respuesta in (crear, editar, borrar):
        assert respuesta.status_code == 409, respuesta.text
        assert respuesta.json()["message"] == CRONOGRAMA_CERRADO
        assert respuesta.json()["data"] == {"codigo": "evento_finalizado"}

    # Sigue igual: una sola actividad, con su nombre original.
    actividades = (
        await api.get("/schedules", headers=cabeceras, params={"evento_id": str(pasado.id)})
    ).json()["data"]
    assert [a["actividad"] for a in actividades] == ["Alabanza"]


async def test_el_cronograma_sigue_consultable_y_se_va_al_eliminar_el_evento(api):
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    miembro = await crear_usuario("Ana")
    pasado = await crear_evento("Vigilia de ayer", en_dias=-1)
    actividad = await crear_actividad(pasado, "Alabanza")

    # Lectura intacta, también para un miembro.
    r = await api.get(f"/schedules/{actividad.id}", headers=auth(miembro))
    assert r.status_code == 200

    assert (await api.delete(f"/events/{pasado.id}", headers=auth(admin))).status_code == 200
    r = await api.get(f"/schedules/{actividad.id}", headers=auth(admin))
    assert r.status_code == 404


async def test_en_un_evento_finalizado_no_se_asignan_participantes(api, correo):
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    ana = await crear_usuario("Ana")
    pasado = await crear_evento("Vigilia de ayer", en_dias=-1)
    actividad = await crear_actividad(pasado, "Alabanza")

    # Ni a otra persona ni a uno mismo (que no necesita plazo de confirmación).
    for participante, extra in ((ana, {"dias_para_confirmar": 3}), (admin, {})):
        r = await api.post(
            "/admin/participaciones",
            headers=auth(admin),
            json={
                "actividad_id": str(actividad.id),
                "participante_id": str(participante.id),
                **extra,
            },
        )

        assert r.status_code == 409, r.text
        assert r.json()["message"] == (
            "El evento ya finalizó: no se pueden asignar participantes."
        )
        assert r.json()["data"] == {"codigo": "evento_finalizado"}

    assert correo.enviados == []
    aforo = (await api.get(f"/events/{pasado.id}", headers=auth(admin))).json()["data"]["aforo"]
    assert aforo["participantes"] == 0


async def test_el_cronograma_de_un_evento_vigente_se_sigue_editando(api):
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    futuro = await crear_evento("Culto del domingo", en_dias=5)
    actividad = await crear_actividad(futuro, "Alabanza")

    r = await api.put(
        f"/schedules/{actividad.id}", headers=auth(admin), json={"actividad": "Adoración"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["actividad"] == "Adoración"

    r = await api.post(
        "/admin/participaciones",
        headers=auth(admin),
        json={"actividad_id": str(actividad.id), "participante_id": str(admin.id)},
    )
    assert r.status_code == 201, r.text

    assert (
        await api.delete(f"/schedules/{actividad.id}", headers=auth(admin))
    ).status_code == 200
