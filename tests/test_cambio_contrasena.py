import pytest
from sqlalchemy import update

from src.core.constants.enums import UserRole
from src.core.security.hashing import hash_password
from src.core.security.hashing import verify_password
from src.infrastructure.database.models.user_model import UserModel
from tests.conftest import AsyncSessionLocal
from tests.conftest import auth
from tests.conftest import crear_usuario

pytestmark = pytest.mark.asyncio

ACTUAL = "clave-actual-1"
NUEVA = "clave-nueva-22"


async def con_clave(nombre: str, rol: UserRole = UserRole.MEMBER) -> UserModel:
    usuario = await crear_usuario(nombre, rol)
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(UserModel)
            .where(UserModel.id == usuario.id)
            .values(
                contrasena=hash_password(ACTUAL),
                # La respuesta valida el correo: un dominio no reservado.
                correo=f"{nombre.lower()}-{usuario.id.hex[:6]}@iglesia-pruebas.org"
            )
        )
        await db.commit()

    return usuario


async def clave_de(usuario: UserModel) -> str:
    async with AsyncSessionLocal() as db:
        return (await db.get(UserModel, usuario.id)).contrasena


@pytest.mark.parametrize("rol", [UserRole.MEMBER, UserRole.ADMIN])
async def test_cambiar_la_propia_contrasena_exige_la_actual(api, rol):
    usuario = await con_clave("Ana", rol)
    url = f"/users/{usuario.id}"
    sesion = auth(usuario)

    r = await api.put(url, headers=sesion, json={"contrasena": NUEVA})
    assert r.status_code == 400
    assert r.json()["message"] == "Escribe tu contraseña actual para cambiarla"

    r = await api.put(
        url, headers=sesion, json={"contrasena": NUEVA, "contrasena_actual": "otra-clave-9"}
    )
    assert r.status_code == 400
    assert r.json()["message"] == "La contraseña actual no es correcta"

    r = await api.put(
        url, headers=sesion, json={"contrasena": ACTUAL, "contrasena_actual": ACTUAL}
    )
    assert r.status_code == 400
    assert r.json()["message"] == "La nueva contraseña debe ser distinta de la actual"

    # Nada de lo anterior la cambió.
    assert verify_password(ACTUAL, await clave_de(usuario))

    r = await api.put(
        url, headers=sesion, json={"contrasena": NUEVA, "contrasena_actual": ACTUAL}
    )
    assert r.status_code == 200, r.text
    assert verify_password(NUEVA, await clave_de(usuario))


async def test_editar_el_perfil_sin_tocar_la_contrasena_no_la_pide(api):
    usuario = await con_clave("Ana")

    r = await api.put(f"/users/{usuario.id}", headers=auth(usuario), json={"nombre": "Anita"})

    assert r.status_code == 200, r.text


async def test_el_admin_restablece_la_de_otro_sin_conocerla(api):
    admin = await con_clave("Admin", UserRole.ADMIN)
    ana = await con_clave("Ana")

    r = await api.put(f"/users/{ana.id}", headers=auth(admin), json={"contrasena": NUEVA})

    assert r.status_code == 200, r.text
    assert verify_password(NUEVA, await clave_de(ana))
