from datetime import UTC
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy import update

from src.core.constants.enums import UserRole
from src.infrastructure.database.models.documento_legal_model import (
    AceptacionDocumentoModel as Aceptacion,
)
from src.infrastructure.database.models.documento_legal_model import (
    DocumentoLegalModel as Documento,
)
from src.infrastructure.database.models.user_model import UserModel
from tests.conftest import AsyncSessionLocal
from tests.conftest import auth
from tests.conftest import crear_usuario as _crear_usuario

pytestmark = pytest.mark.asyncio

PENDIENTE = "aceptacion_pendiente"


async def crear_usuario(nombre: str, rol: UserRole = UserRole.MEMBER) -> UserModel:
    """Como el de `conftest`, con un correo que las respuestas de la API aceptan."""
    usuario = await _crear_usuario(nombre, rol)
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(UserModel).where(UserModel.id == usuario.id).values(
                correo=f"{nombre.lower()}-{usuario.id.hex[:6]}@pruebas.example"
            )
        )
        await db.commit()

    return usuario


@pytest_asyncio.fixture
async def vigentes(api) -> dict[str, str]:
    """Versión 1.0 publicada de los dos documentos. Devuelve sus ids por tipo."""
    ahora = datetime.now(UTC)
    ids = {"terminos": uuid4(), "privacidad": uuid4()}
    async with AsyncSessionLocal() as db:
        db.add_all(
            Documento(
                id=ids[tipo], tipo=tipo, version_mayor=1, version_menor=0,
                titulo=titulo, contenido=f"## {titulo}\n\nTexto de prueba.",
                estado="publicado", requiere_reaceptacion=True, publicado_en=ahora,
            )
            for tipo, titulo in (
                ("terminos", "Términos y condiciones"),
                ("privacidad", "Política de privacidad"),
            )
        )
        await db.commit()

    return {tipo: str(valor) for tipo, valor in ids.items()}


async def aceptar_todo(api, usuario) -> None:
    pendientes = (await api.get("/legal/mis-pendientes", headers=auth(usuario))).json()["data"]
    r = await api.post(
        "/legal/aceptaciones", headers=auth(usuario),
        json={"documentos": [p["id"] for p in pendientes]},
    )
    assert r.status_code == 200, r.text


async def admin_al_dia(api) -> UserModel:
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    await aceptar_todo(api, admin)

    return admin


async def publicar_nueva(api, admin, tipo: str, requiere: bool, contenido="Texto nuevo.") -> dict:
    """Borrador desde la vigente → editar → publicar."""
    r = await api.post(f"/legal/admin/documentos/{tipo}/borrador", headers=auth(admin))
    assert r.status_code == 201, r.text
    borrador = r.json()["data"]
    r = await api.put(
        f"/legal/admin/documentos/{borrador['id']}", headers=auth(admin),
        json={"titulo": borrador["titulo"], "contenido": contenido},
    )
    assert r.status_code == 200, r.text
    r = await api.post(
        f"/legal/admin/documentos/{borrador['id']}/publicar", headers=auth(admin),
        json={"requiere_reaceptacion": requiere},
    )
    assert r.status_code == 200, r.text

    return r.json()["data"]


REGISTRO = {
    "nombre": "Marta", "apellido": "Ruiz", "correo": "marta@pruebas.example",
    "contrasena": "clave-segura-1",
}


# ── Lectura pública ─────────────────────────────────────────────────────

async def test_cualquiera_lee_los_documentos_vigentes_sin_sesion(api, vigentes):
    r = await api.get("/legal/documentos")
    assert r.status_code == 200, r.text
    assert [(d["tipo"], d["version"]) for d in r.json()["data"]] == [
        ("terminos", "1.0"), ("privacidad", "1.0")
    ]

    r = await api.get("/legal/documentos/privacidad")
    assert r.status_code == 200
    assert r.json()["data"]["titulo"] == "Política de privacidad"
    assert r.json()["data"]["publicado_en"] is not None

    assert (await api.get("/legal/documentos/otro")).status_code == 422


# ── Registro ────────────────────────────────────────────────────────────

async def test_registrarse_sin_aceptar_se_rechaza_aunque_se_llame_a_la_api(api, vigentes):
    r = await api.post("/auth/register", json=REGISTRO)
    assert r.status_code == 400
    assert r.json()["data"]["codigo"] == "aceptacion_requerida"

    # Tampoco aceptando solo uno, ni una versión que no es la vigente.
    for ids in ([vigentes["terminos"]], [vigentes["terminos"], str(uuid4())]):
        r = await api.post("/auth/register", json={**REGISTRO, "documentos_aceptados": ids})
        assert r.status_code == 400
        assert r.json()["data"]["codigo"] == "version_no_vigente"

    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(UserModel))).scalars().all() == []


async def test_registrarse_aceptando_guarda_la_constancia_con_fecha_y_version(api, vigentes):
    r = await api.post(
        "/auth/register",
        json={**REGISTRO, "documentos_aceptados": list(vigentes.values())},
        headers={"x-forwarded-for": "190.1.2.3", "user-agent": "NavegadorDePrueba/1.0"},
    )
    assert r.status_code == 201, r.text
    usuario_id = r.json()["data"]["id"]

    async with AsyncSessionLocal() as db:
        constancias = (await db.execute(select(Aceptacion))).scalars().all()
    assert {str(c.documento_id) for c in constancias} == set(vigentes.values())
    assert all(str(c.usuario_id) == usuario_id for c in constancias)
    assert all(c.aceptado_en is not None for c in constancias)
    assert {(c.ip, c.user_agent) for c in constancias} == {
        ("190.1.2.3", "NavegadorDePrueba/1.0")
    }

    # Entra y usa la aplicación sin que se le pida nada más.
    r = await api.post(
        "/auth/login",
        json={"correo": REGISTRO["correo"], "contrasena": REGISTRO["contrasena"]},
    )
    sesion = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
    assert (await api.get("/legal/mis-pendientes", headers=sesion)).json()["data"] == []
    assert (await api.get("/events", headers=sesion)).status_code == 200
    historial = (await api.get("/legal/mis-aceptaciones", headers=sesion)).json()["data"]
    assert sorted((a["tipo"], a["version"]) for a in historial) == [
        ("privacidad", "1.0"), ("terminos", "1.0")
    ]


# ── Aceptación obligatoria ──────────────────────────────────────────────

async def test_quien_no_ha_aceptado_no_puede_usar_la_aplicacion_hasta_hacerlo(api, vigentes):
    # Cuenta creada por un administrador: nunca vio la casilla.
    ana = await crear_usuario("Ana")
    sesion = auth(ana)

    for ruta in ("/events", "/notificaciones", "/schedules", "/participante/invitaciones"):
        r = await api.get(ruta, headers=sesion)
        assert r.status_code == 403, ruta
        assert r.json()["data"]["codigo"] == PENDIENTE

    # Lo que sí puede: ver su usuario, leer los documentos y renovar la sesión.
    assert (await api.get(f"/users/{ana.id}", headers=sesion)).status_code == 200
    assert (await api.post("/auth/refresh", headers=sesion)).status_code == 200
    pendientes = (await api.get("/legal/mis-pendientes", headers=sesion)).json()["data"]
    assert sorted(p["tipo"] for p in pendientes) == ["privacidad", "terminos"]

    # Aceptar solo uno no vale.
    r = await api.post(
        "/legal/aceptaciones", headers=sesion, json={"documentos": [vigentes["terminos"]]}
    )
    assert r.status_code == 409
    assert (await api.get("/events", headers=sesion)).status_code == 403

    await aceptar_todo(api, ana)
    assert (await api.get("/events", headers=sesion)).status_code == 200
    assert (await api.get("/legal/mis-pendientes", headers=sesion)).json()["data"] == []


async def test_el_administrador_tambien_debe_aceptar(api, vigentes):
    admin = await crear_usuario("Admin", UserRole.ADMIN)

    r = await api.get("/users", headers=auth(admin))
    assert r.status_code == 403
    assert r.json()["data"]["codigo"] == PENDIENTE

    await aceptar_todo(api, admin)
    assert (await api.get("/users", headers=auth(admin))).status_code == 200


# ── Versiones ───────────────────────────────────────────────────────────

async def test_una_correccion_menor_no_pide_volver_a_aceptar(api, vigentes):
    admin = await admin_al_dia(api)
    ana = await crear_usuario("Ana")
    await aceptar_todo(api, ana)

    nueva = await publicar_nueva(api, admin, "terminos", requiere=False)

    assert (nueva["version"], nueva["estado"]) == ("1.1", "publicado")
    # Quien aceptó la 1.0 sigue al día…
    assert (await api.get("/events", headers=auth(ana))).status_code == 200
    # …y quien llega después acepta la 1.1.
    beto = await crear_usuario("Beto")
    pendientes = (await api.get("/legal/mis-pendientes", headers=auth(beto))).json()["data"]
    assert {(p["tipo"], p["version"]) for p in pendientes} == {
        ("terminos", "1.1"), ("privacidad", "1.0")
    }


async def test_un_cambio_importante_obliga_a_todos_a_aceptar_de_nuevo(api, vigentes):
    admin = await admin_al_dia(api)
    ana = await crear_usuario("Ana")
    await aceptar_todo(api, ana)

    nueva = await publicar_nueva(api, admin, "privacidad", requiere=True)
    assert nueva["version"] == "2.0"

    for usuario in (ana, admin):
        r = await api.get("/events", headers=auth(usuario))
        assert r.status_code == 403
        assert r.json()["data"]["codigo"] == PENDIENTE
        pendientes = (
            await api.get("/legal/mis-pendientes", headers=auth(usuario))
        ).json()["data"]
        # Solo el que cambió: los términos ya aceptados siguen valiendo.
        assert [(p["tipo"], p["version"]) for p in pendientes] == [("privacidad", "2.0")]

    await aceptar_todo(api, ana)
    assert (await api.get("/events", headers=auth(ana))).status_code == 200


async def test_solo_hay_una_version_publicada_y_lo_publicado_no_se_toca(api, vigentes):
    admin = await admin_al_dia(api)
    await publicar_nueva(api, admin, "terminos", requiere=False, contenido="Versión corregida.")

    versiones = (await api.get("/legal/admin/documentos", headers=auth(admin))).json()["data"]
    terminos = [(d["version"], d["estado"]) for d in versiones if d["tipo"] == "terminos"]
    assert terminos == [("1.1", "publicado"), ("1.0", "archivado")]

    # El texto que la gente aceptó no se puede editar ni eliminar.
    for documento_id in (vigentes["terminos"], versiones[0]["id"]):
        r = await api.put(
            f"/legal/admin/documentos/{documento_id}", headers=auth(admin),
            json={"titulo": "Otro", "contenido": "Otro texto"},
        )
        assert r.status_code == 409
        assert r.json()["data"]["codigo"] == "no_es_borrador"
        r = await api.delete(f"/legal/admin/documentos/{documento_id}", headers=auth(admin))
        assert r.status_code == 409

    # El público lee la vigente.
    assert (await api.get("/legal/documentos/terminos")).json()["data"]["contenido"] == (
        "Versión corregida."
    )


async def test_un_borrador_se_edita_se_descarta_y_no_se_publica_vacio(api, vigentes):
    admin = await admin_al_dia(api)
    url = "/legal/admin/documentos/terminos/borrador"

    borrador = (await api.post(url, headers=auth(admin))).json()["data"]
    assert borrador["estado"] == "borrador"
    # Parte del texto vigente, y pedirlo otra vez devuelve el mismo.
    assert borrador["contenido"].startswith("## Términos y condiciones")
    assert (await api.post(url, headers=auth(admin))).json()["data"]["id"] == borrador["id"]
    # Un borrador no cambia lo que ve el público.
    assert (await api.get("/legal/documentos/terminos")).json()["data"]["version"] == "1.0"

    await api.put(
        f"/legal/admin/documentos/{borrador['id']}", headers=auth(admin),
        json={"titulo": "Términos", "contenido": "   "},
    )
    r = await api.post(
        f"/legal/admin/documentos/{borrador['id']}/publicar", headers=auth(admin),
        json={"requiere_reaceptacion": False},
    )
    assert r.status_code == 409
    assert r.json()["data"]["codigo"] == "documento_vacio"

    r = await api.delete(f"/legal/admin/documentos/{borrador['id']}", headers=auth(admin))
    assert r.status_code == 200, r.text
    versiones = (await api.get("/legal/admin/documentos", headers=auth(admin))).json()["data"]
    assert [d["estado"] for d in versiones if d["tipo"] == "terminos"] == ["publicado"]


# ── Permisos y constancia ───────────────────────────────────────────────

async def test_un_miembro_no_administra_documentos_ni_ve_aceptaciones_ajenas(api, vigentes):
    admin = await admin_al_dia(api)
    ana = await crear_usuario("Ana")
    await aceptar_todo(api, ana)
    sesion = auth(ana)

    assert (await api.get("/legal/admin/documentos", headers=sesion)).status_code == 403
    assert (
        await api.post("/legal/admin/documentos/terminos/borrador", headers=sesion)
    ).status_code == 403
    assert (await api.get("/legal/admin/aceptaciones", headers=sesion)).status_code == 403
    assert (
        await api.get(f"/legal/admin/usuarios/{admin.id}/aceptaciones", headers=sesion)
    ).status_code == 403

    # Lo suyo sí, y solo lo suyo.
    propias = (await api.get("/legal/mis-aceptaciones", headers=sesion)).json()["data"]
    assert len(propias) == 2

    # El administrador consulta las de cualquiera.
    r = await api.get(f"/legal/admin/usuarios/{ana.id}/aceptaciones", headers=auth(admin))
    assert r.status_code == 200 and len(r.json()["data"]) == 2


async def test_las_aceptaciones_no_se_pueden_modificar_ni_borrar(api, vigentes):
    ana = await crear_usuario("Ana")
    await aceptar_todo(api, ana)
    aceptacion = (await api.get("/legal/mis-aceptaciones", headers=auth(ana))).json()["data"][0]

    # No existe ninguna ruta para ello.
    for metodo in (api.put, api.patch, api.delete):
        r = await metodo(f"/legal/aceptaciones/{aceptacion['id']}", headers=auth(ana))
        assert r.status_code in (404, 405)

    # Aceptar de nuevo no duplica ni cambia la fecha.
    await aceptar_todo(api, ana)
    despues = (await api.get("/legal/mis-aceptaciones", headers=auth(ana))).json()["data"]
    assert len(despues) == 2
    assert aceptacion in despues


async def test_el_administrador_ve_quien_acepto_y_quien_esta_pendiente(api, vigentes):
    admin = await admin_al_dia(api)
    ana = await crear_usuario("Ana")
    await crear_usuario("Beto")
    await aceptar_todo(api, ana)

    r = await api.get("/legal/admin/aceptaciones", headers=auth(admin))
    assert r.status_code == 200, r.text
    resumen = r.json()["data"]

    assert (resumen["total"], resumen["al_dia"]) == (3, 2)
    assert resumen["documentos"]["terminos"]["version"] == "1.0"
    personas = {p["nombre_completo"]: p for p in resumen["personas"]}
    assert personas["Ana Prueba"]["al_dia"] is True
    assert personas["Ana Prueba"]["aceptaciones"]["privacidad"]["version"] == "1.0"
    assert personas["Beto Prueba"]["al_dia"] is False
    assert personas["Beto Prueba"]["aceptaciones"] == {"terminos": None, "privacidad": None}


async def test_eliminar_la_cuenta_elimina_sus_aceptaciones(api, vigentes):
    admin = await admin_al_dia(api)
    ana = await crear_usuario("Ana")
    await aceptar_todo(api, ana)

    r = await api.delete(f"/users/{ana.id}", headers=auth(admin))
    assert r.status_code == 200, r.text

    async with AsyncSessionLocal() as db:
        restantes = (await db.execute(select(Aceptacion.usuario_id))).scalars().all()
    assert set(restantes) == {admin.id}
