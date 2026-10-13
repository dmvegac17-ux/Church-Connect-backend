import asyncio
from uuid import UUID
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.core.constants.enums import UserRole
from src.infrastructure.database.models.registration_model import RegistrationModel
from src.infrastructure.database.session import AsyncSessionLocal
from tests.conftest import auth
from tests.conftest import crear_actividad
from tests.conftest import crear_evento
from tests.conftest import crear_usuario

pytestmark = pytest.mark.asyncio


# ── Utilidades ──────────────────────────────────────────────────────────

async def inscribir(api, usuario, evento, **extra):
    return await api.post(
        "/registrations",
        headers=auth(usuario),
        json={"evento_id": str(evento.id), **extra}
    )


async def asignar(api, admin, actividad, participante, dias=3):
    cuerpo = {
        "actividad_id": str(actividad.id),
        "participante_id": str(participante.id),
    }
    if participante.id != admin.id:
        cuerpo["dias_para_confirmar"] = dias

    return await api.post("/admin/participaciones", headers=auth(admin), json=cuerpo)


async def ver_evento(api, usuario, evento) -> dict:
    r = await api.get(f"/events/{evento.id}", headers=auth(usuario))
    assert r.status_code == 200, r.text

    return r.json()["data"]


async def inscripciones_de(evento) -> list[RegistrationModel]:
    async with AsyncSessionLocal() as db:
        return list(
            (
                await db.execute(
                    select(RegistrationModel).where(
                        RegistrationModel.evento_id == UUID(str(evento.id))
                    )
                )
            ).scalars().all()
        )


@pytest.fixture
async def escena(api):
    """Un admin, tres miembros y un evento de aforo 4 con dos actividades."""
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    ana = await crear_usuario("Ana")
    beto = await crear_usuario("Beto")
    caro = await crear_usuario("Caro")
    evento = await crear_evento(en_dias=10, capacidad=4)
    alabanza = await crear_actividad(evento, "Alabanza", 0)
    estudio = await crear_actividad(evento, "Estudio bíblico", 30)

    return {
        "admin": admin, "ana": ana, "beto": beto, "caro": caro,
        "evento": evento, "alabanza": alabanza, "estudio": estudio,
    }


# ── Aforo ───────────────────────────────────────────────────────────────

async def test_los_participantes_descuentan_aforo_y_cuentan_una_vez(api, escena):
    admin = escena["admin"]

    # Ana tiene dos actividades: ocupa un solo lugar.
    await asignar(api, admin, escena["alabanza"], escena["ana"])
    await asignar(api, admin, escena["estudio"], escena["ana"])
    await inscribir(api, escena["beto"], escena["evento"])

    aforo = (await ver_evento(api, admin, escena["evento"]))["aforo"]
    assert aforo["participantes"] == 1
    assert aforo["publico"] == 1
    assert aforo["ocupados"] == 2
    assert aforo["cupo_publico"] == 3
    assert aforo["disponibles"] == 2
    assert aforo["sobrecupo"] == 0


async def test_el_miembro_no_ve_el_aforo_total_ni_los_participantes(api, escena):
    await asignar(api, escena["admin"], escena["alabanza"], escena["ana"])
    await inscribir(api, escena["beto"], escena["evento"])

    como_admin = await ver_evento(api, escena["admin"], escena["evento"])
    assert como_admin["capacidad"] == 4

    como_miembro = await ver_evento(api, escena["caro"], escena["evento"])
    # Su «aforo» es el cupo para público: 4 − 1 participante.
    assert como_miembro["capacidad"] == 3
    assert como_miembro["aforo"]["cupo_publico"] == 3
    assert como_miembro["aforo"]["disponibles"] == 2
    for interno in ("participantes", "publico", "ocupados", "sobrecupo"):
        assert como_miembro["aforo"][interno] is None

    # El listado aplica la misma regla.
    lista = (await api.get("/events", headers=auth(escena["caro"]))).json()["data"]
    assert lista[0]["capacidad"] == 3
    assert lista[0]["aforo"]["participantes"] is None


async def test_el_evento_dice_la_situacion_de_quien_consulta(api, escena):
    evento = escena["evento"]
    await asignar(api, escena["admin"], escena["alabanza"], escena["ana"])
    inscripcion = (await inscribir(api, escena["beto"], evento)).json()["data"]

    de_ana = (await ver_evento(api, escena["ana"], evento))["aforo"]
    assert (de_ana["participa"], de_ana["inscrito"]) == (True, False)

    de_beto = (await ver_evento(api, escena["beto"], evento))["aforo"]
    assert (de_beto["participa"], de_beto["inscrito"]) == (False, True)
    assert de_beto["inscripcion_id"] == inscripcion["id"]

    de_caro = (await ver_evento(api, escena["caro"], evento))["aforo"]
    assert (de_caro["participa"], de_caro["inscrito"]) == (False, False)
    assert de_caro["inscripciones_cerradas"] is False


# ── Inscribirse ─────────────────────────────────────────────────────────

async def test_inscribirse_devuelve_los_cupos_que_quedan(api, escena):
    await asignar(api, escena["admin"], escena["alabanza"], escena["ana"])

    r = await inscribir(api, escena["beto"], escena["evento"])
    assert r.status_code == 201, r.text
    data = r.json()["data"]

    # Cupo para público 3; con Beto quedan 2.
    assert data["cupos_disponibles"] == 2
    assert data["inscrito_por"] is None
    assert data["usuario"]["nombre_completo"] == "Beto Prueba"


async def test_no_hay_inscripcion_doble(api, escena):
    assert (await inscribir(api, escena["beto"], escena["evento"])).status_code == 201

    r = await inscribir(api, escena["beto"], escena["evento"])
    assert r.status_code == 409
    assert r.json()["data"] == {"codigo": "ya_inscrito"}


async def test_un_participante_no_se_inscribe(api, escena):
    await asignar(api, escena["admin"], escena["alabanza"], escena["ana"])

    r = await inscribir(api, escena["ana"], escena["evento"])
    assert r.status_code == 409
    assert r.json()["data"] == {"codigo": "es_participante"}
    assert await inscripciones_de(escena["evento"]) == []


async def test_un_administrador_participante_tampoco_se_inscribe(api, escena):
    admin = escena["admin"]
    await asignar(api, admin, escena["alabanza"], admin)

    r = await inscribir(api, admin, escena["evento"])
    assert r.status_code == 409
    assert r.json()["data"] == {"codigo": "es_participante"}


async def test_sin_cupos_cuando_participantes_y_publico_llenan_el_aforo(api, escena):
    evento = escena["evento"]
    # Aforo 4: 2 participantes dejan 2 cupos para público.
    await asignar(api, escena["admin"], escena["alabanza"], escena["ana"])
    await asignar(api, escena["admin"], escena["estudio"], escena["beto"])
    assert (await inscribir(api, escena["caro"], evento)).json()["data"]["cupos_disponibles"] == 1
    assert (await inscribir(api, escena["admin"], evento)).json()["data"]["cupos_disponibles"] == 0

    tarde = await crear_usuario("Dora")
    r = await inscribir(api, tarde, evento)
    assert r.status_code == 409
    assert r.json()["data"] == {"codigo": "sin_cupos"}

    assert (await ver_evento(api, tarde, evento))["aforo"]["disponibles"] == 0


async def test_dos_inscripciones_simultaneas_al_ultimo_cupo(api, escena):
    evento = await crear_evento("Cupo único", en_dias=10, capacidad=1)

    respuestas = await asyncio.gather(
        inscribir(api, escena["ana"], evento),
        inscribir(api, escena["beto"], evento),
    )

    assert sorted(r.status_code for r in respuestas) == [201, 409]
    assert len(await inscripciones_de(evento)) == 1


async def test_inscripciones_cerradas_cuando_el_evento_ya_empezo(api, escena):
    pasado = await crear_evento("Ya empezó", en_dias=-1)

    r = await inscribir(api, escena["ana"], pasado)
    assert r.status_code == 409
    assert r.json()["data"] == {"codigo": "inscripciones_cerradas"}

    assert (await ver_evento(api, escena["ana"], pasado))["aforo"]["inscripciones_cerradas"] is True


async def test_cancelar_la_propia_libera_el_cupo(api, escena):
    evento = escena["evento"]
    inscripcion = (await inscribir(api, escena["ana"], evento)).json()["data"]

    # Nadie más que el dueño (o un administrador) la cancela.
    r = await api.delete(f"/registrations/{inscripcion['id']}", headers=auth(escena["beto"]))
    assert r.status_code == 403

    r = await api.delete(f"/registrations/{inscripcion['id']}", headers=auth(escena["ana"]))
    assert r.status_code == 200
    assert (await ver_evento(api, escena["ana"], evento))["aforo"]["inscrito"] is False
    assert (await ver_evento(api, escena["admin"], evento))["aforo"]["publico"] == 0


async def test_mis_inscripciones_solo_lista_las_propias(api, escena):
    otro = await crear_evento("Otro evento", en_dias=12)
    await inscribir(api, escena["ana"], escena["evento"])
    await inscribir(api, escena["ana"], otro)
    await inscribir(api, escena["beto"], escena["evento"])

    r = await api.get("/registrations/me", headers=auth(escena["ana"]))
    assert r.status_code == 200
    assert {i["evento_id"] for i in r.json()["data"]} == {str(escena["evento"].id), str(otro.id)}
    assert r.json()["meta"] == {"totalRegistrations": 2}


# ── Gestión del administrador ───────────────────────────────────────────

async def test_el_administrador_inscribe_a_otra_persona_con_nota(api, escena):
    admin = escena["admin"]

    r = await inscribir(
        api, admin, escena["evento"],
        usuario_id=str(escena["ana"].id), nota="  Asistirá con un acompañante  "
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]

    assert data["usuario_id"] == str(escena["ana"].id)
    assert data["inscrito_por"] == str(admin.id)
    assert data["inscrito_por_usuario"]["nombre_completo"] == "Admin Prueba"
    assert data["nota"] == "Asistirá con un acompañante"

    # Aparece en las inscripciones de Ana, no en las del administrador.
    de_ana = (await api.get("/registrations/me", headers=auth(escena["ana"]))).json()["data"]
    assert [i["id"] for i in de_ana] == [data["id"]]
    del_admin = (await api.get("/registrations/me", headers=auth(admin))).json()["data"]
    assert del_admin == []


async def test_un_miembro_no_inscribe_a_otros_ni_deja_notas(api, escena):
    r = await inscribir(api, escena["ana"], escena["evento"], usuario_id=str(escena["beto"].id))
    assert r.status_code == 403

    r = await inscribir(api, escena["ana"], escena["evento"], nota="hola")
    assert r.status_code == 403

    assert await inscripciones_de(escena["evento"]) == []


async def test_el_administrador_no_inscribe_participantes_ni_inactivos(api, escena):
    admin = escena["admin"]
    await asignar(api, admin, escena["alabanza"], escena["ana"])
    inactivo = await crear_usuario("Ines", activo=False)

    r = await inscribir(api, admin, escena["evento"], usuario_id=str(escena["ana"].id))
    assert r.status_code == 409
    assert r.json()["data"] == {"codigo": "es_participante"}

    r = await inscribir(api, admin, escena["evento"], usuario_id=str(inactivo.id))
    assert r.status_code == 404

    r = await inscribir(api, admin, escena["evento"], usuario_id=str(uuid4()))
    assert r.status_code == 404


async def test_editar_la_nota_y_eliminar_un_inscrito(api, escena):
    admin = escena["admin"]
    inscripcion = (await inscribir(api, escena["ana"], escena["evento"])).json()["data"]
    url = f"/registrations/{inscripcion['id']}"

    assert (
        await api.patch(url, headers=auth(escena["ana"]), json={"nota": "x"})
    ).status_code == 403
    assert (
        await api.patch(url, headers=auth(admin), json={"nota": "x" * 201})
    ).status_code == 422

    r = await api.patch(url, headers=auth(admin), json={"nota": "Llevará pan"})
    assert r.status_code == 200
    assert r.json()["data"]["nota"] == "Llevará pan"

    r = await api.patch(url, headers=auth(admin), json={"nota": "   "})
    assert r.json()["data"]["nota"] is None

    r = await api.delete(url, headers=auth(admin))
    assert r.status_code == 200
    assert await inscripciones_de(escena["evento"]) == []


async def test_listado_de_inscritos_del_evento_para_el_administrador(api, escena):
    admin = escena["admin"]
    await inscribir(api, escena["ana"], escena["evento"])
    await inscribir(api, admin, escena["evento"], usuario_id=str(escena["beto"].id))

    r = await api.get(
        "/registrations", headers=auth(admin), params={"evento_id": str(escena["evento"].id)}
    )
    assert r.status_code == 200
    filas = {f["usuario"]["nombre_completo"]: f for f in r.json()["data"]}

    assert filas["Ana Prueba"]["inscrito_por_usuario"] is None
    assert filas["Ana Prueba"]["usuario"]["correo"] == escena["ana"].correo
    assert filas["Beto Prueba"]["inscrito_por_usuario"]["id"] == str(admin.id)
    assert r.json()["meta"] == {"totalRegistrations": 2}

    # El miembro nunca ve la lista de inscritos.
    assert (
        await api.get("/registrations", headers=auth(escena["ana"]))
    ).status_code == 403


# ── Inscripción y participación ─────────────────────────────────────────

async def test_asignar_a_un_inscrito_reemplaza_su_inscripcion(api, escena):
    admin = escena["admin"]
    evento = escena["evento"]
    await inscribir(api, escena["ana"], evento)

    elegibles = {
        e["nombre_completo"]: e
        for e in (
            await api.get(
                "/admin/participantes/elegibles",
                headers=auth(admin),
                params={"actividad_id": str(escena["alabanza"].id)}
            )
        ).json()["data"]
    }
    assert elegibles["Ana Prueba"]["inscrito"] is True
    assert elegibles["Beto Prueba"]["inscrito"] is False

    assert (await asignar(api, admin, escena["alabanza"], escena["ana"])).status_code == 201

    # Pasa de público a participante: el aforo ocupado no cambia.
    assert await inscripciones_de(evento) == []
    aforo = (await ver_evento(api, admin, evento))["aforo"]
    assert (aforo["participantes"], aforo["publico"], aforo["ocupados"]) == (1, 0, 1)

    de_ana = (await ver_evento(api, escena["ana"], evento))["aforo"]
    assert de_ana["participa"] is True
    assert de_ana["inscripcion_reemplazada"] is True

    # A quien no estaba inscrito no se le avisa de ningún reemplazo.
    await asignar(api, admin, escena["estudio"], escena["beto"])
    assert (await ver_evento(api, escena["beto"], evento))["aforo"]["inscripcion_reemplazada"] is False


async def test_asignar_con_el_evento_lleno_deja_sobrecupo_sin_borrar_publico(api, escena):
    admin = escena["admin"]
    evento = escena["evento"]
    extras = [await crear_usuario(f"Extra{i}") for i in range(4)]
    for usuario in extras:
        assert (await inscribir(api, usuario, evento)).status_code == 201

    # Lleno: 4 de 4. Aun así se puede asignar un participante.
    assert (await asignar(api, admin, escena["alabanza"], escena["ana"])).status_code == 201

    aforo = (await ver_evento(api, admin, evento))["aforo"]
    assert (aforo["participantes"], aforo["publico"]) == (1, 4)
    assert aforo["sobrecupo"] == 1
    assert aforo["disponibles"] == 0
    assert len(await inscripciones_de(evento)) == 4

    # Para el miembro es simplemente un evento sin cupos.
    de_miembro = (await ver_evento(api, escena["beto"], evento))["aforo"]
    assert de_miembro["disponibles"] == 0
    assert de_miembro["sobrecupo"] is None
    assert (await inscribir(api, escena["beto"], evento)).json()["data"] == {"codigo": "sin_cupos"}


async def test_quien_rechaza_deja_de_ocupar_aforo_y_puede_inscribirse(api, escena):
    admin = escena["admin"]
    evento = escena["evento"]
    inv = (await asignar(api, admin, escena["alabanza"], escena["ana"])).json()["data"]
    assert (await ver_evento(api, admin, evento))["aforo"]["participantes"] == 1

    await api.post(f"/participante/invitaciones/{inv['id']}/rechazar", headers=auth(escena["ana"]))

    assert (await ver_evento(api, admin, evento))["aforo"]["participantes"] == 0
    de_ana = (await ver_evento(api, escena["ana"], evento))["aforo"]
    assert de_ana["participa"] is False
    assert de_ana["inscripcion_reemplazada"] is False
    # No se le inscribe sola: decide ella.
    assert de_ana["inscrito"] is False
    assert (await inscribir(api, escena["ana"], evento)).status_code == 201


# ── Aforo del evento ────────────────────────────────────────────────────

async def test_el_aforo_no_puede_bajar_de_lo_ocupado(api, escena):
    admin = escena["admin"]
    evento = escena["evento"]
    await asignar(api, admin, escena["alabanza"], escena["ana"])
    await inscribir(api, escena["beto"], evento)
    await inscribir(api, escena["caro"], evento)
    url = f"/events/{evento.id}"

    r = await api.put(url, headers=auth(admin), json={"capacidad": 2})
    assert r.status_code == 409
    assert r.json()["message"] == "Hay 3 lugares ocupados. El aforo no puede ser menor."
    assert r.json()["data"] == {"campo": "capacidad", "ocupados": 3}
    assert (await ver_evento(api, admin, evento))["capacidad"] == 4

    # Justo lo ocupado sí se acepta: el evento queda lleno.
    r = await api.put(url, headers=auth(admin), json={"capacidad": 3})
    assert r.status_code == 200
    assert r.json()["data"]["aforo"]["disponibles"] == 0

    # Otros campos se editan sin tocar el aforo.
    r = await api.put(url, headers=auth(admin), json={"titulo": "Culto renombrado"})
    assert r.status_code == 200
    assert r.json()["data"]["capacidad"] == 3


# ── Notificaciones propias ──────────────────────────────────────────────

async def test_el_miembro_elimina_solo_sus_notificaciones(api, escena):
    admin = escena["admin"]
    # La invitación deja un aviso en la bandeja de Ana.
    await asignar(api, admin, escena["alabanza"], escena["ana"])

    avisos = (await api.get("/notificaciones", headers=auth(escena["ana"]))).json()["data"]
    assert len(avisos) == 1
    url = f"/notificaciones/{avisos[0]['id']}"

    assert (await api.delete(url, headers=auth(escena["beto"]))).status_code == 403
    assert (await api.delete(url, headers=auth(escena["ana"]))).status_code == 200
    assert (await api.get("/notificaciones", headers=auth(escena["ana"]))).json()["data"] == []


async def test_el_miembro_marca_su_notificacion_como_leida_y_como_no_leida(api, escena):
    await asignar(api, escena["admin"], escena["alabanza"], escena["ana"])
    ana = auth(escena["ana"])
    aviso = (await api.get("/notificaciones", headers=ana)).json()["data"][0]
    url = f"/notificaciones/{aviso['id']}"

    for leida in (True, False):
        r = await api.put(url, headers=ana, json={"leida": leida})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["leida"] is leida

    # Solo el estado, y solo la propia.
    assert (await api.put(url, headers=ana, json={"titulo": "Otro"})).status_code == 403
    r = await api.put(url, headers=auth(escena["beto"]), json={"leida": True})
    assert r.status_code == 403


async def test_el_aforo_tiene_un_tope_de_diez_millones(api, escena):
    """Cubre eventos multitudinarios; más allá responde 422 señalando el campo."""
    admin = escena["admin"]
    evento = escena["evento"]
    maximo = 10_000_000
    nuevo = {
        "titulo": "Evento enorme",
        "descripcion": "Evento de prueba",
        "fecha_inicio": evento.fecha_inicio.isoformat(),
        "fecha_fin": evento.fecha_fin.isoformat(),
        "lugar": "Templo de prueba",
    }

    r = await api.post("/events", headers=auth(admin), json={**nuevo, "capacidad": maximo + 1})
    assert r.status_code == 422
    assert any("capacidad" in error for error in r.json()["errors"])

    r = await api.put(
        f"/events/{evento.id}", headers=auth(admin), json={"capacidad": maximo + 1}
    )
    assert r.status_code == 422
    assert (await ver_evento(api, admin, evento))["capacidad"] == 4

    # El máximo exacto sí se acepta.
    r = await api.post("/events", headers=auth(admin), json={**nuevo, "capacidad": maximo})
    assert r.status_code == 201, r.text
    assert r.json()["data"]["capacidad"] == maximo
    assert r.json()["data"]["aforo"]["disponibles"] == maximo
