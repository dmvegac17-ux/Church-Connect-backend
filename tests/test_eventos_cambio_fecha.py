from datetime import timedelta

import pytest
from sqlalchemy import select

from src.application.events.date_change import describe_range
from src.application.events.date_change import text_changed
from src.core.constants.enums import UserRole
from src.infrastructure.database.models.notificaciones_model import NotificacionesModel
from src.infrastructure.database.session import AsyncSessionLocal
from tests.conftest import auth
from tests.conftest import crear_actividad
from tests.conftest import crear_evento
from tests.conftest import crear_usuario

pytestmark = pytest.mark.asyncio


async def inscribir(api, usuario, evento):
    r = await api.post(
        "/registrations", headers=auth(usuario), json={"evento_id": str(evento.id)}
    )
    assert r.status_code == 201, r.text


async def avisos_de(usuario) -> list[NotificacionesModel]:
    async with AsyncSessionLocal() as db:
        return list(
            (
                await db.execute(
                    select(NotificacionesModel).where(
                        NotificacionesModel.usuario_id == usuario.id
                    )
                )
            ).scalars().all()
        )


@pytest.fixture
async def escena(api):
    """Un admin y un evento con dos personas inscritas y una que no lo está."""
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    ana = await crear_usuario("Ana")
    beto = await crear_usuario("Beto")
    caro = await crear_usuario("Caro")
    evento = await crear_evento("Culto de jóvenes", en_dias=10)
    await inscribir(api, ana, evento)
    await inscribir(api, beto, evento)

    return {"admin": admin, "ana": ana, "beto": beto, "caro": caro, "evento": evento}


def nuevas_fechas(evento, dias: int = 2) -> dict:
    return {
        "fecha_inicio": (evento.fecha_inicio + timedelta(days=dias)).isoformat(),
        "fecha_fin": (evento.fecha_fin + timedelta(days=dias)).isoformat(),
    }


async def test_cambiar_la_fecha_avisa_por_correo_a_los_inscritos(api, escena, correo):
    evento = escena["evento"]

    r = await api.put(
        f"/events/{evento.id}", headers=auth(escena["admin"]), json=nuevas_fechas(evento)
    )

    assert r.status_code == 200, r.text
    assert r.json()["meta"] == {"inscritosNotificados": 2}

    # Solo a quienes están inscritos; Caro no recibe nada.
    assert sorted(c["to"] for c in correo.enviados) == sorted(
        [escena["ana"].correo, escena["beto"].correo]
    )

    enviado = correo.enviados[0]
    assert enviado["titulo"] == "Cambio de fecha: Culto de jóvenes"
    # Nombra el evento y muestra la fecha anterior y la nueva.
    antes = describe_range(evento.fecha_inicio, evento.fecha_fin)
    ahora = describe_range(
        evento.fecha_inicio + timedelta(days=2), evento.fecha_fin + timedelta(days=2)
    )
    assert antes != ahora
    assert "<b>Culto de jóvenes</b>" in enviado["mensaje"]
    assert f"Antes: {antes}." in enviado["mensaje"]
    assert f"Ahora: {ahora}." in enviado["mensaje"]
    # Ni el lugar ni la dirección cambiaron: no aparecen como modificación.
    assert "<b>Lugar</b>" not in enviado["mensaje"]
    assert "Dirección" not in enviado["mensaje"]
    assert "Lugar: Templo de prueba." in enviado["mensaje"]


async def test_el_aviso_tambien_queda_en_la_bandeja_de_cada_inscrito(api, escena):
    evento = escena["evento"]

    await api.put(
        f"/events/{evento.id}", headers=auth(escena["admin"]), json=nuevas_fechas(evento)
    )

    for nombre in ("ana", "beto"):
        avisos = await avisos_de(escena[nombre])
        assert [a.titulo for a in avisos] == ["Cambio de fecha: Culto de jóvenes"]
        assert avisos[0].leida is False
    assert await avisos_de(escena["caro"]) == []
    # Quien hizo el cambio no se avisa a sí mismo (no está inscrito).
    assert await avisos_de(escena["admin"]) == []


async def test_cambiar_solo_el_horario_tambien_avisa(api, escena, correo):
    evento = escena["evento"]

    r = await api.put(
        f"/events/{evento.id}",
        headers=auth(escena["admin"]),
        json={"fecha_fin": (evento.fecha_fin + timedelta(hours=1)).isoformat()},
    )

    assert r.json()["meta"] == {"inscritosNotificados": 2}
    assert len(correo.enviados) == 2


async def test_cambiar_la_direccion_avisa_con_la_anterior_y_la_nueva(api, escena, correo):
    evento = escena["evento"]
    url = f"/events/{evento.id}"
    admin = auth(escena["admin"])

    # El evento no tenía dirección.
    r = await api.put(url, headers=admin, json={"direccion": "Calle 10 # 5-20"})
    assert r.json()["meta"] == {"inscritosNotificados": 2}
    enviado = correo.enviados[0]
    assert enviado["titulo"] == "Cambio de dirección: Culto de jóvenes"
    assert "Antes: sin dirección." in enviado["mensaje"]
    assert "Ahora: Calle 10 # 5-20." in enviado["mensaje"]
    # La fecha no cambió: se menciona para ubicar el evento, no como cambio.
    assert "Fecha y horario" not in enviado["mensaje"]
    assert f"Fecha: {describe_range(evento.fecha_inicio, evento.fecha_fin)}." in enviado["mensaje"]

    correo.enviados.clear()
    r = await api.put(url, headers=admin, json={"direccion": "Carrera 7 # 12-34"})
    assert r.json()["meta"] == {"inscritosNotificados": 2}
    assert "Antes: Calle 10 # 5-20." in correo.enviados[0]["mensaje"]
    assert "Ahora: Carrera 7 # 12-34." in correo.enviados[0]["mensaje"]


async def test_fecha_y_direccion_juntas_van_en_un_solo_aviso(api, escena, correo):
    evento = escena["evento"]

    r = await api.put(
        f"/events/{evento.id}",
        headers=auth(escena["admin"]),
        json={**nuevas_fechas(evento), "direccion": "Calle 10 # 5-20"},
    )

    assert r.json()["meta"] == {"inscritosNotificados": 2}
    # Un correo por persona, no uno por cada cosa que cambió.
    assert len(correo.enviados) == 2
    enviado = correo.enviados[0]
    assert enviado["titulo"] == "Cambios en el evento: Culto de jóvenes"
    assert "<b>Fecha y horario</b>" in enviado["mensaje"]
    assert "<b>Dirección</b>" in enviado["mensaje"]
    assert len(await avisos_de(escena["ana"])) == 1


async def test_reenviar_la_misma_direccion_no_es_un_cambio(api, escena, correo):
    evento = escena["evento"]
    url = f"/events/{evento.id}"
    admin = auth(escena["admin"])
    await api.put(url, headers=admin, json={"direccion": "Calle 10 # 5-20"})
    correo.enviados.clear()

    for igual in ("Calle 10 # 5-20", "  Calle 10 # 5-20  "):
        r = await api.put(url, headers=admin, json={"direccion": igual})
        assert r.json()["meta"] == {"inscritosNotificados": 0}

    assert correo.enviados == []


async def test_editar_otros_campos_no_avisa(api, escena, correo):
    evento = escena["evento"]

    # Ni el título, la descripción, el aforo o las coordenadas.
    r = await api.put(
        f"/events/{evento.id}",
        headers=auth(escena["admin"]),
        json={
            "titulo": "Culto renombrado",
            "descripcion": "Otra descripción",
            "capacidad": 80,
            "latitud": 4.61,
            "longitud": -74.08,
        },
    )

    assert r.status_code == 200
    assert r.json()["meta"] == {"inscritosNotificados": 0}
    assert correo.enviados == []
    assert await avisos_de(escena["ana"]) == []


async def test_reenviar_la_misma_fecha_no_es_un_cambio(api, escena, correo):
    evento = escena["evento"]

    # El formulario manda las fechas aunque no se hayan tocado, y puede
    # expresarlas en otra zona horaria: sigue siendo el mismo instante.
    r = await api.put(
        f"/events/{evento.id}",
        headers=auth(escena["admin"]),
        json={
            "fecha_inicio": evento.fecha_inicio.isoformat().replace("+00:00", "Z"),
            "fecha_fin": (evento.fecha_fin - timedelta(hours=5)).isoformat().replace(
                "+00:00", "-05:00"
            ),
        },
    )

    assert r.status_code == 200, r.text
    assert r.json()["meta"] == {"inscritosNotificados": 0}
    assert correo.enviados == []


async def test_sin_inscritos_no_se_envia_nada(api, correo):
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    evento = await crear_evento("Sin público", en_dias=10)

    r = await api.put(
        f"/events/{evento.id}", headers=auth(admin), json=nuevas_fechas(evento)
    )

    assert r.status_code == 200
    assert r.json()["meta"] == {"inscritosNotificados": 0}
    assert correo.enviados == []


async def test_un_cambio_rechazado_no_avisa_ni_deja_avisos(api, escena, correo):
    evento = escena["evento"]

    # Fin anterior al inicio: el evento no cambia.
    r = await api.put(
        f"/events/{evento.id}",
        headers=auth(escena["admin"]),
        json={"fecha_fin": (evento.fecha_inicio - timedelta(hours=1)).isoformat()},
    )

    assert r.status_code == 400
    assert correo.enviados == []
    assert await avisos_de(escena["ana"]) == []


async def test_si_el_correo_falla_el_cambio_y_el_aviso_se_conservan(api, escena, correo):
    evento = escena["evento"]
    correo.fallar = True

    r = await api.put(
        f"/events/{evento.id}", headers=auth(escena["admin"]), json=nuevas_fechas(evento)
    )

    assert r.status_code == 200
    assert correo.enviados == []
    # La fecha cambió y el aviso sigue en la aplicación.
    detalle = (await api.get(f"/events/{evento.id}", headers=auth(escena["admin"]))).json()
    assert detalle["data"]["fecha_inicio"] != evento.fecha_inicio.isoformat()
    assert len(await avisos_de(escena["ana"])) == 1


async def test_solo_se_avisa_al_publico_inscrito(api, escena, correo):
    """Los participantes no están inscritos: este aviso es para el público."""
    evento = escena["evento"]
    actividad = await crear_actividad(evento, "Alabanza")
    r = await api.post(
        "/admin/participaciones",
        headers=auth(escena["admin"]),
        json={
            "actividad_id": str(actividad.id),
            "participante_id": str(escena["caro"].id),
            "dias_para_confirmar": 3,
        },
    )
    assert r.status_code == 201, r.text
    correo.enviados.clear()

    r = await api.put(
        f"/events/{evento.id}",
        headers=auth(escena["admin"]),
        json={"fecha_fin": (evento.fecha_fin + timedelta(hours=1)).isoformat()},
    )

    assert r.json()["meta"] == {"inscritosNotificados": 2}
    assert escena["caro"].correo not in [c["to"] for c in correo.enviados]


async def test_el_rango_se_describe_en_hora_de_bogota():
    from datetime import UTC
    from datetime import datetime

    # 00:00 UTC del 18 es 7:00 p. m. del 17 en Bogotá.
    inicio = datetime(2026, 10, 18, 0, 0, tzinfo=UTC)

    assert describe_range(inicio, inicio + timedelta(hours=2)) == (
        "sábado 17 de octubre de 2026, de 7:00 p. m. a 9:00 p. m."
    )
    assert describe_range(inicio, inicio + timedelta(days=2, hours=14)) == (
        "del sábado 17 de octubre de 2026 a las 7:00 p. m. "
        "al martes 20 de octubre de 2026 a las 9:00 a. m."
    )


async def test_cambiar_el_lugar_avisa_con_el_anterior_y_el_nuevo(api, escena, correo):
    evento = escena["evento"]

    r = await api.put(
        f"/events/{evento.id}",
        headers=auth(escena["admin"]),
        json={"lugar": "Finca La Esperanza"},
    )

    assert r.json()["meta"] == {"inscritosNotificados": 2}
    enviado = correo.enviados[0]
    assert enviado["titulo"] == "Cambio de lugar: Culto de jóvenes"
    assert "cambió de lugar." in enviado["mensaje"]
    assert "<b>Lugar</b>" in enviado["mensaje"]
    assert "Antes: Templo de prueba." in enviado["mensaje"]
    assert "Ahora: Finca La Esperanza." in enviado["mensaje"]


@pytest.mark.parametrize(
    "retoque",
    [
        "templo de prueba",        # mayúsculas
        "Templo de Pruéba",        # tildes
        "  Templo  de  prueba. ",  # espacios y signos
        "Templo prueba",           # preposición
        "Templo de preuba",        # dos letras intercambiadas
        "Tenplo de prueba",        # una letra equivocada
    ],
)
async def test_un_retoque_del_lugar_no_avisa(api, escena, correo, retoque):
    evento = escena["evento"]

    r = await api.put(
        f"/events/{evento.id}", headers=auth(escena["admin"]), json={"lugar": retoque}
    )

    assert r.status_code == 200, r.text
    # El texto se guarda tal como se escribió…
    assert r.json()["data"]["lugar"] == retoque
    # …pero nadie recibe un aviso por eso.
    assert r.json()["meta"] == {"inscritosNotificados": 0}
    assert correo.enviados == []
    assert await avisos_de(escena["ana"]) == []


async def test_corregir_una_errata_de_la_direccion_no_avisa_pero_un_numero_si(
    api, escena, correo
):
    evento = escena["evento"]
    url = f"/events/{evento.id}"
    admin = auth(escena["admin"])
    await api.put(url, headers=admin, json={"direccion": "Cale 10 # 5-20, Barrio Centro"})
    correo.enviados.clear()

    r = await api.put(url, headers=admin, json={"direccion": "Calle 10 # 5-20, barrio centro"})
    assert r.json()["meta"] == {"inscritosNotificados": 0}
    assert correo.enviados == []

    # Un solo dígito distinto ya es otra puerta.
    r = await api.put(url, headers=admin, json={"direccion": "Calle 10 # 5-21, barrio centro"})
    assert r.json()["meta"] == {"inscritosNotificados": 2}
    assert "Ahora: Calle 10 # 5-21, barrio centro." in correo.enviados[0]["mensaje"]


async def test_fecha_lugar_y_direccion_juntos_van_en_un_solo_aviso(api, escena, correo):
    evento = escena["evento"]

    r = await api.put(
        f"/events/{evento.id}",
        headers=auth(escena["admin"]),
        json={
            **nuevas_fechas(evento),
            "lugar": "Finca La Esperanza",
            "direccion": "Vereda El Carmen",
        },
    )

    assert r.json()["meta"] == {"inscritosNotificados": 2}
    assert len(correo.enviados) == 2
    enviado = correo.enviados[0]
    assert enviado["titulo"] == "Cambios en el evento: Culto de jóvenes"
    assert "cambió de fecha u horario, de lugar y de dirección." in enviado["mensaje"]


@pytest.mark.parametrize(
    ("antes", "ahora", "cambio"),
    [
        # Retoques: no cuentan.
        ("Templo central", "Templo central", False),
        ("Templo central", "TEMPLO CENTRAL", False),
        ("Salón social", "Salon social", False),
        ("Templo centrl", "Templo central", False),
        ("Finca La Esperansa", "Finca la Esperanza", False),
        ("Parques del Río", "Parques de Rio", False),
        ("", None, False),
        (None, "   ", False),
        # Cambios reales: cuentan.
        ("Templo central", "Templo norte", True),
        ("Salón social", "Salón comunal", True),
        ("Templo", "Templo central", True),
        ("Sede sur", "Sede sub", True),
        ("Salón 1", "Salón 2", True),
        ("Calle 10 # 5-20", "Calle 10 # 5-21", True),
        ("Calle 100", "Calle 10", True),
        (None, "Calle 10 # 5-20", True),
        ("Calle 10 # 5-20", "", True),
    ],
)
async def test_text_changed_distingue_retoques_de_cambios(antes, ahora, cambio):
    assert text_changed(antes, ahora) is cambio
    # No depende de en qué sentido se haga la corrección.
    assert text_changed(ahora, antes) is cambio
