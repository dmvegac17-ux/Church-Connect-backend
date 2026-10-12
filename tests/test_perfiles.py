from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy import update

from src.core.constants.enums import UserRole
from src.infrastructure.database.models.perfil_model import PerfilModel
from src.infrastructure.database.models.user_model import UserModel
from tests.conftest import AsyncSessionLocal
from tests.conftest import auth
from tests.conftest import crear_usuario as _crear_usuario

pytestmark = pytest.mark.asyncio

REGISTRO = {
    "nombre": "Marta", "apellido": "Ruiz", "correo": "marta@pruebas.example",
    "contrasena": "clave-segura-1", "telefono": "+573001234567",
}


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


async def perfil_de(usuario_id) -> PerfilModel | None:
    clave = usuario_id if isinstance(usuario_id, UUID) else UUID(str(usuario_id))
    async with AsyncSessionLocal() as db:
        return (
            await db.execute(select(PerfilModel).where(PerfilModel.usuario_id == clave))
        ).scalar_one_or_none()


async def test_registrarse_crea_la_cuenta_y_su_perfil(api):
    r = await api.post("/auth/register", json=REGISTRO)
    assert r.status_code == 201, r.text
    datos = r.json()["data"]
    assert (datos["nombre"], datos["apellido"], datos["telefono"]) == (
        "Marta", "Ruiz", "+573001234567"
    )

    # Los datos personales quedaron en el perfil, uno por cuenta.
    perfil = await perfil_de(datos["id"])
    assert (perfil.nombre, perfil.apellido, perfil.telefono) == (
        "Marta", "Ruiz", "+573001234567"
    )
    assert perfil.creado_en is not None

    # Y se puede entrar con la cuenta recién creada.
    r = await api.post(
        "/auth/login",
        json={"correo": REGISTRO["correo"], "contrasena": REGISTRO["contrasena"]},
    )
    assert r.status_code == 200, r.text


async def test_editar_el_perfil_propio_no_toca_la_cuenta(api):
    r = await api.post("/auth/register", json=REGISTRO)
    usuario_id = r.json()["data"]["id"]
    r = await api.post(
        "/auth/login",
        json={"correo": REGISTRO["correo"], "contrasena": REGISTRO["contrasena"]},
    )
    sesion = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}

    r = await api.put(
        f"/users/{usuario_id}", headers=sesion,
        json={"nombre": "Martha", "telefono": "+573009998877"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["nombre"] == "Martha"

    perfil = await perfil_de(usuario_id)
    assert (perfil.nombre, perfil.apellido, perfil.telefono) == (
        "Martha", "Ruiz", "+573009998877"
    )
    r = await api.get(f"/users/{usuario_id}", headers=sesion)
    assert r.json()["data"]["correo"] == REGISTRO["correo"]
    assert r.json()["data"]["rol"] == "MEMBER"


async def test_un_miembro_no_ve_ni_edita_el_perfil_de_otro_y_el_admin_si(api):
    ana = await crear_usuario("Ana")
    beto = await crear_usuario("Beto")
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    url = f"/users/{ana.id}"

    assert (await api.get(url, headers=auth(beto))).status_code == 403
    r = await api.put(url, headers=auth(beto), json={"telefono": "+573000000000"})
    assert r.status_code == 403
    assert (await api.get("/users", headers=auth(beto))).status_code == 403
    assert (await perfil_de(ana.id)).telefono is None

    # El administrador sí, y lo edita.
    r = await api.put(url, headers=auth(admin), json={"apellido": "García"})
    assert r.status_code == 200, r.text
    assert (await perfil_de(ana.id)).apellido == "García"


async def test_eliminar_un_usuario_elimina_su_perfil(api):
    ana = await crear_usuario("Ana")
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    assert await perfil_de(ana.id) is not None

    r = await api.delete(f"/users/{ana.id}", headers=auth(admin))
    assert r.status_code == 200, r.text

    assert await perfil_de(ana.id) is None
    async with AsyncSessionLocal() as db:
        assert await db.get(UserModel, ana.id) is None


async def test_los_listados_traen_el_nombre_sin_una_consulta_por_persona(api):
    from sqlalchemy import event

    from tests.conftest import engine

    admin = await crear_usuario("Admin", UserRole.ADMIN)
    for nombre in ("Ana", "Beto", "Caro", "Dani"):
        await crear_usuario(nombre)
    consultas: list[str] = []

    def anotar(_conn, _cursor, sentencia, *_):
        if "perfiles" in sentencia.lower():
            consultas.append(sentencia)

    event.listen(engine.sync_engine, "before_cursor_execute", anotar)
    try:
        r = await api.get("/users", headers=auth(admin), params={"limit": 100})
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", anotar)

    assert r.status_code == 200, r.text
    assert sorted(u["nombre"] for u in r.json()["data"]) == [
        "Admin", "Ana", "Beto", "Caro", "Dani"
    ]
    # Cinco personas, y los perfiles llegan en las mismas consultas de la
    # autenticación y del listado: ninguna extra por persona.
    assert len(consultas) <= 2
