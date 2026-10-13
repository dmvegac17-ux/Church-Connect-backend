from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest
from sqlalchemy import update

from src.core.constants.enums import UserRole
from src.infrastructure.database.models.event_model import EventModel
from src.infrastructure.database.session import AsyncSessionLocal
from tests.conftest import auth
from tests.conftest import crear_evento
from tests.conftest import crear_usuario

pytestmark = pytest.mark.asyncio


def instante(texto: str) -> datetime:
    """SQLite devuelve las fechas sin zona horaria: siempre son UTC."""
    valor = datetime.fromisoformat(texto)

    return valor.replace(tzinfo=UTC) if valor.tzinfo is None else valor


async def configurar(evento, **valores) -> None:
    """Fija los límites directamente, como si el evento se hubiera creado así."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(EventModel).where(EventModel.id == evento.id).values(**valores)
        )
        await db.commit()


async def inscribir(api, usuario, evento, **extra):
    return await api.post(
        "/registrations",
        headers=auth(usuario),
        json={"evento_id": str(evento.id), **extra},
    )


async def ver(api, usuario, evento) -> dict:
    r = await api.get(f"/events/{evento.id}", headers=auth(usuario))
    assert r.status_code == 200, r.text

    return r.json()["data"]


@pytest.fixture
async def escena(api):
    """Un admin, dos miembros y un evento dentro de 10 días."""
    return {
        "admin": await crear_usuario("Admin", UserRole.ADMIN),
        "ana": await crear_usuario("Ana"),
        "beto": await crear_usuario("Beto"),
        "evento": await crear_evento(en_dias=10),
    }


# ── Sin límites: como antes ─────────────────────────────────────────────

async def test_sin_limites_se_inscribe_y_se_cancela_hasta_que_el_evento_empieza(api, escena):
    evento = escena["evento"]

    detalle = await ver(api, escena["ana"], evento)
    assert detalle["fecha_limite_inscripcion"] is None
    assert detalle["dias_limite_cancelacion"] is None
    # Sin días límite, se puede cancelar hasta el inicio.
    assert instante(detalle["fecha_limite_cancelacion"]) == evento.fecha_inicio
    assert detalle["aforo"]["inscripciones_cerradas"] is False
    assert detalle["aforo"]["cancelacion_cerrada"] is False

    inscripcion = (await inscribir(api, escena["ana"], evento)).json()["data"]
    r = await api.delete(f"/registrations/{inscripcion['id']}", headers=auth(escena["ana"]))
    assert r.status_code == 200


# ── Fecha límite para inscribirse ───────────────────────────────────────

async def test_antes_de_la_fecha_limite_el_publico_se_inscribe(api, escena):
    evento = escena["evento"]
    limite = datetime.now(UTC) + timedelta(days=3)
    await configurar(evento, fecha_limite_inscripcion=limite)

    assert (await ver(api, escena["ana"], evento))["aforo"]["inscripciones_cerradas"] is False
    assert (await inscribir(api, escena["ana"], evento)).status_code == 201


async def test_pasada_la_fecha_limite_el_publico_ya_no_se_inscribe(api, escena):
    evento = escena["evento"]
    # El evento es en 10 días, pero las inscripciones cerraron ayer.
    await configurar(evento, fecha_limite_inscripcion=datetime.now(UTC) - timedelta(days=1))

    r = await inscribir(api, escena["ana"], evento)

    assert r.status_code == 409
    assert r.json()["data"] == {"codigo": "inscripciones_cerradas"}
    assert r.json()["message"] == "La fecha límite para inscribirse a este evento ya pasó"
    assert (await ver(api, escena["ana"], evento))["aforo"]["inscripciones_cerradas"] is True


async def test_el_administrador_inscribe_despues_de_la_fecha_limite(api, escena):
    evento = escena["evento"]
    await configurar(evento, fecha_limite_inscripcion=datetime.now(UTC) - timedelta(days=1))

    # El límite es para el público: el administrador decide hasta el inicio.
    assert (await ver(api, escena["admin"], evento))["aforo"]["inscripciones_cerradas"] is False
    r = await inscribir(api, escena["admin"], evento, usuario_id=str(escena["ana"].id))
    assert r.status_code == 201, r.text

    # Un miembro no puede saltarse el límite inscribiendo «a otro».
    r = await inscribir(api, escena["beto"], evento, usuario_id=str(escena["beto"].id))
    assert r.status_code == 409


async def test_quien_ya_estaba_inscrito_lo_sigue_estando_tras_la_fecha_limite(api, escena):
    evento = escena["evento"]
    await inscribir(api, escena["ana"], evento)
    await configurar(evento, fecha_limite_inscripcion=datetime.now(UTC) - timedelta(days=1))

    aforo = (await ver(api, escena["ana"], evento))["aforo"]

    assert aforo["inscrito"] is True
    assert aforo["inscripciones_cerradas"] is True
    # Cerrar inscripciones no cierra la cancelación.
    assert aforo["cancelacion_cerrada"] is False


# ── Días límite para cancelar ───────────────────────────────────────────

async def test_dentro_del_plazo_se_puede_cancelar(api, escena):
    evento = escena["evento"]
    # Faltan 10 días y se puede cancelar hasta 3 días antes.
    await configurar(evento, dias_limite_cancelacion=3)
    inscripcion = (await inscribir(api, escena["ana"], evento)).json()["data"]

    detalle = await ver(api, escena["ana"], evento)
    assert detalle["aforo"]["cancelacion_cerrada"] is False
    assert instante(detalle["fecha_limite_cancelacion"]) == (
        evento.fecha_inicio - timedelta(days=3)
    )

    r = await api.delete(f"/registrations/{inscripcion['id']}", headers=auth(escena["ana"]))
    assert r.status_code == 200


async def test_pasado_el_plazo_el_publico_ya_no_cancela(api, escena):
    evento = escena["evento"]
    inscripcion = (await inscribir(api, escena["ana"], evento)).json()["data"]
    # Faltan 10 días, pero la cancelación cerraba 15 días antes.
    await configurar(evento, dias_limite_cancelacion=15)

    r = await api.delete(f"/registrations/{inscripcion['id']}", headers=auth(escena["ana"]))

    assert r.status_code == 409
    assert r.json()["data"] == {"codigo": "cancelacion_cerrada"}
    assert r.json()["message"] == (
        "El plazo para cancelar la inscripción a este evento ya terminó"
    )
    aforo = (await ver(api, escena["ana"], evento))["aforo"]
    assert aforo["inscrito"] is True
    assert aforo["cancelacion_cerrada"] is True


async def test_el_administrador_retira_a_alguien_despues_del_plazo(api, escena):
    evento = escena["evento"]
    inscripcion = (await inscribir(api, escena["ana"], evento)).json()["data"]
    await configurar(evento, dias_limite_cancelacion=15)

    assert (await ver(api, escena["admin"], evento))["aforo"]["cancelacion_cerrada"] is False
    r = await api.delete(f"/registrations/{inscripcion['id']}", headers=auth(escena["admin"]))

    assert r.status_code == 200
    assert (await ver(api, escena["ana"], evento))["aforo"]["inscrito"] is False


async def test_el_plazo_para_cancelar_no_impide_inscribirse(api, escena):
    evento = escena["evento"]
    await configurar(evento, dias_limite_cancelacion=15)

    # Puede inscribirse sabiendo que ya no podrá cancelar.
    assert (await inscribir(api, escena["ana"], evento)).status_code == 201
    aforo = (await ver(api, escena["ana"], evento))["aforo"]
    assert (aforo["inscripciones_cerradas"], aforo["cancelacion_cerrada"]) == (False, True)


# ── Configurarlos desde el evento ───────────────────────────────────────

def cuerpo_evento(evento, **extra) -> dict:
    return {
        "titulo": "Retiro",
        "descripcion": "Evento de prueba",
        "fecha_inicio": evento.fecha_inicio.isoformat(),
        "fecha_fin": evento.fecha_fin.isoformat(),
        "lugar": "Templo de prueba",
        "capacidad": 50,
        **extra,
    }


async def test_crear_y_editar_un_evento_con_sus_limites(api, escena):
    admin = auth(escena["admin"])
    evento = escena["evento"]
    limite = evento.fecha_inicio - timedelta(days=2)

    r = await api.post(
        "/events",
        headers=admin,
        json=cuerpo_evento(
            evento,
            fecha_limite_inscripcion=limite.isoformat(),
            dias_limite_cancelacion=4,
        ),
    )
    assert r.status_code == 201, r.text
    creado = r.json()["data"]
    assert instante(creado["fecha_limite_inscripcion"]) == limite
    assert creado["dias_limite_cancelacion"] == 4
    assert instante(creado["fecha_limite_cancelacion"]) == (
        evento.fecha_inicio - timedelta(days=4)
    )

    # `null` explícito quita el límite; lo que no se envía no cambia.
    r = await api.put(
        f"/events/{creado['id']}", headers=admin, json={"fecha_limite_inscripcion": None}
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["fecha_limite_inscripcion"] is None
    assert r.json()["data"]["dias_limite_cancelacion"] == 4


async def test_la_fecha_limite_no_puede_ser_posterior_al_inicio(api, escena):
    admin = auth(escena["admin"])
    evento = escena["evento"]
    tarde = (evento.fecha_inicio + timedelta(hours=1)).isoformat()
    mensaje = (
        "La fecha límite de inscripción no puede ser posterior al inicio del evento"
    )

    r = await api.post(
        "/events", headers=admin, json=cuerpo_evento(evento, fecha_limite_inscripcion=tarde)
    )
    assert r.status_code == 400
    assert r.json()["message"] == mensaje

    r = await api.put(
        f"/events/{evento.id}", headers=admin, json={"fecha_limite_inscripcion": tarde}
    )
    assert r.status_code == 400
    assert (await ver(api, escena["admin"], evento))["fecha_limite_inscripcion"] is None

    # Justo en el inicio sí se acepta.
    r = await api.put(
        f"/events/{evento.id}",
        headers=admin,
        json={"fecha_limite_inscripcion": evento.fecha_inicio.isoformat()},
    )
    assert r.status_code == 200, r.text


async def test_adelantar_el_evento_no_puede_dejar_la_fecha_limite_despues_del_inicio(
    api, escena
):
    admin = auth(escena["admin"])
    evento = escena["evento"]
    await configurar(evento, fecha_limite_inscripcion=evento.fecha_inicio - timedelta(days=1))

    r = await api.put(
        f"/events/{evento.id}",
        headers=admin,
        json={
            "fecha_inicio": (evento.fecha_inicio - timedelta(days=5)).isoformat(),
            "fecha_fin": (evento.fecha_fin - timedelta(days=5)).isoformat(),
        },
    )

    assert r.status_code == 400
    assert instante(
        (await ver(api, escena["admin"], evento))["fecha_inicio"]
    ) == evento.fecha_inicio


@pytest.mark.parametrize("dias", [-1, 366, 2.5, "tres"])
async def test_los_dias_limite_van_de_0_a_365(api, escena, dias):
    r = await api.put(
        f"/events/{escena['evento'].id}",
        headers=auth(escena["admin"]),
        json={"dias_limite_cancelacion": dias},
    )

    assert r.status_code == 422


async def test_cambiar_los_limites_no_avisa_a_los_inscritos(api, escena, correo):
    evento = escena["evento"]
    await inscribir(api, escena["ana"], evento)

    r = await api.put(
        f"/events/{evento.id}",
        headers=auth(escena["admin"]),
        json={
            "dias_limite_cancelacion": 2,
            "fecha_limite_inscripcion": (evento.fecha_inicio - timedelta(days=1)).isoformat(),
        },
    )

    assert r.status_code == 200, r.text
    assert r.json()["meta"] == {"inscritosNotificados": 0}
    assert correo.enviados == []


# ── Entre hoy y el día del evento ───────────────────────────────────────

async def test_la_fecha_limite_no_puede_ser_anterior_a_hoy(api, escena):
    admin = auth(escena["admin"])
    evento = escena["evento"]
    ayer = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    mensaje = "La fecha límite de inscripción no puede ser anterior a hoy"

    r = await api.post(
        "/events", headers=admin, json=cuerpo_evento(evento, fecha_limite_inscripcion=ayer)
    )
    assert r.status_code == 400
    assert r.json()["message"] == mensaje

    r = await api.put(
        f"/events/{evento.id}", headers=admin, json={"fecha_limite_inscripcion": ayer}
    )
    assert r.status_code == 400
    assert r.json()["message"] == mensaje
    assert (await ver(api, escena["admin"], evento))["fecha_limite_inscripcion"] is None

    # Hoy mismo sí: las inscripciones cierran al final del día.
    hoy = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    r = await api.put(
        f"/events/{evento.id}", headers=admin, json={"fecha_limite_inscripcion": hoy}
    )
    assert r.status_code == 200, r.text


async def test_un_evento_con_la_fecha_limite_ya_vencida_se_puede_seguir_editando(api, escena):
    admin = auth(escena["admin"])
    evento = escena["evento"]
    vencida = datetime.now(UTC) - timedelta(days=3)
    await configurar(evento, fecha_limite_inscripcion=vencida)

    # Sin tocar la fecha límite…
    r = await api.put(f"/events/{evento.id}", headers=admin, json={"titulo": "Renombrado"})
    assert r.status_code == 200, r.text

    # …o reenviándola tal cual, como hace el formulario.
    r = await api.put(
        f"/events/{evento.id}",
        headers=admin,
        json={"fecha_limite_inscripcion": vencida.isoformat(), "capacidad": 60},
    )
    assert r.status_code == 200, r.text
    assert instante(r.json()["data"]["fecha_limite_inscripcion"]) == vencida

    # Cambiarla a otra fecha pasada sí se rechaza.
    r = await api.put(
        f"/events/{evento.id}",
        headers=admin,
        json={"fecha_limite_inscripcion": (vencida - timedelta(days=1)).isoformat()},
    )
    assert r.status_code == 400


async def test_los_dias_para_cancelar_no_superan_los_que_faltan_para_el_evento(api, escena):
    admin = auth(escena["admin"])
    evento = escena["evento"]  # en 10 días

    r = await api.put(
        f"/events/{evento.id}", headers=admin, json={"dias_limite_cancelacion": 11}
    )
    assert r.status_code == 400
    assert r.json()["message"] == (
        "El evento es en 10 días: los días límite para cancelar no pueden ser más de 10"
    )
    assert (await ver(api, escena["admin"], evento))["dias_limite_cancelacion"] is None

    # El máximo exacto sí, y también cero o quitarlo.
    for dias in (10, 0, None):
        r = await api.put(
            f"/events/{evento.id}", headers=admin, json={"dias_limite_cancelacion": dias}
        )
        assert r.status_code == 200, (dias, r.text)

    r = await api.post(
        "/events", headers=admin, json=cuerpo_evento(evento, dias_limite_cancelacion=11)
    )
    assert r.status_code == 400


async def test_con_el_evento_manana_solo_cabe_un_dia(api, escena):
    from src.application.events.registration_window import BOGOTA

    admin = auth(escena["admin"])
    evento = escena["evento"]
    # Mañana a mediodía de Bogotá, en UTC como lo guarda la aplicación.
    dia = datetime.now(UTC).astimezone(BOGOTA).date() + timedelta(days=1)
    inicio = datetime(dia.year, dia.month, dia.day, 12, 0, tzinfo=BOGOTA).astimezone(UTC)
    await configurar(evento, fecha_inicio=inicio, fecha_fin=inicio + timedelta(hours=2))

    r = await api.put(
        f"/events/{evento.id}", headers=admin, json={"dias_limite_cancelacion": 2}
    )
    assert r.status_code == 400
    assert r.json()["message"] == (
        "El evento es mañana: los días límite para cancelar no pueden ser más de 1"
    )

    r = await api.put(
        f"/events/{evento.id}", headers=admin, json={"dias_limite_cancelacion": 1}
    )
    assert r.status_code == 200, r.text


async def test_los_dias_se_cuentan_en_el_calendario_de_colombia():
    from src.application.events.registration_window import days_until_event
    from src.application.events.registration_window import deadline_before_today

    # Son las 9:00 p. m. del 9 de octubre en Bogotá (ya es día 10 en UTC).
    ahora = datetime(2026, 10, 10, 2, 0, tzinfo=UTC)

    def bogota(dia: int, hora: int) -> datetime:
        return datetime(2026, 10, dia, hora, 0, tzinfo=UTC) + timedelta(hours=5)

    # Evento hoy más tarde: 0 días. Mañana temprano: 1, aunque falten horas.
    assert days_until_event(bogota(9, 23), ahora) == 0
    assert days_until_event(bogota(10, 6), ahora) == 1
    assert days_until_event(bogota(19, 10), ahora) == 10
    # Un evento que ya pasó no deja días negativos.
    assert days_until_event(bogota(5, 10), ahora) == 0

    # La fecha límite puede ser hoy (aunque la hora ya haya pasado), no ayer.
    assert deadline_before_today(bogota(9, 8), ahora) is False
    assert deadline_before_today(bogota(8, 23), ahora) is True


async def test_acercar_el_evento_exige_que_los_dias_sigan_cabiendo(api, escena):
    admin = auth(escena["admin"])
    evento = escena["evento"]  # en 10 días
    await configurar(evento, dias_limite_cancelacion=8)

    # Se mueve a dentro de 5 días: 8 días de anticipación ya no caben.
    cerca = {
        "fecha_inicio": (evento.fecha_inicio - timedelta(days=5)).isoformat(),
        "fecha_fin": (evento.fecha_fin - timedelta(days=5)).isoformat(),
    }
    r = await api.put(f"/events/{evento.id}", headers=admin, json=cerca)
    assert r.status_code == 400
    assert "no pueden ser más de 5" in r.json()["message"]

    # Ajustando los días en el mismo guardado sí.
    r = await api.put(
        f"/events/{evento.id}", headers=admin, json={**cerca, "dias_limite_cancelacion": 3}
    )
    assert r.status_code == 200, r.text


async def test_los_dias_ya_guardados_no_bloquean_otros_cambios(api, escena):
    admin = auth(escena["admin"])
    evento = escena["evento"]
    # Se fijaron cuando faltaba más: hoy ya no cabrían, pero no se tocan.
    await configurar(evento, dias_limite_cancelacion=30)

    r = await api.put(
        f"/events/{evento.id}",
        headers=admin,
        json={"titulo": "Renombrado", "dias_limite_cancelacion": 30},
    )

    assert r.status_code == 200, r.text
    assert r.json()["data"]["dias_limite_cancelacion"] == 30
