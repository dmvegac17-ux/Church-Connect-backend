from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy import update

from src.application.auth import password_reset
from src.core.security.hashing import hash_password
from src.core.security.hashing import verify_password
from src.infrastructure.database.models.restablecimiento_contrasena_model import (
    RestablecimientoContrasenaModel as Solicitud,
)
from src.infrastructure.database.models.user_model import UserModel
from tests.conftest import AsyncSessionLocal
from tests.conftest import auth
from tests.conftest import crear_usuario

pytestmark = pytest.mark.asyncio

GENERICA = (
    "Si el correo está registrado, recibirás un enlace para restablecer tu "
    "contraseña. Vence en 15 minutos."
)
NUEVA = "clave-nueva-22"


@pytest.fixture(autouse=True)
def _sin_limites_previos():
    password_reset.reiniciar_limites()
    yield
    password_reset.reiniciar_limites()


async def con_correo(nombre: str) -> UserModel:
    """Un usuario con contraseña real y un correo que la respuesta acepta."""
    usuario = await crear_usuario(nombre)
    correo = f"{nombre.lower()}-{usuario.id.hex[:6]}@iglesia-pruebas.org"
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(UserModel).where(UserModel.id == usuario.id).values(
                correo=correo, contrasena=hash_password("clave-vieja-11")
            )
        )
        await db.commit()
    usuario.correo = correo

    return usuario


async def pedir(api, correo: str, ip: str = "10.0.0.1"):
    return await api.post(
        "/auth/olvide-contrasena", json={"correo": correo},
        headers={"x-forwarded-for": ip},
    )


def token_de(correo_falso) -> str:
    return correo_falso.enviados[-1]["enlace"].split("token=")[1]


async def cambiar(api, token: str, contrasena: str = NUEVA):
    return await api.post(
        "/auth/restablecer-contrasena", json={"token": token, "contrasena": contrasena}
    )


async def test_flujo_completo_y_el_enlace_sirve_una_sola_vez(api, correo):
    ana = await con_correo("Ana")

    r = await pedir(api, ana.correo)
    assert r.status_code == 200, r.text
    assert r.json()["message"] == GENERICA

    enviado = correo.enviados[-1]
    assert enviado["to"] == ana.correo
    assert enviado["minutos"] == 15
    assert "/restablecer-contrasena?token=" in enviado["enlace"]
    token = token_de(correo)

    # En la base no queda el token, solo su hash.
    async with AsyncSessionLocal() as db:
        guardado = (await db.execute(select(Solicitud))).scalar_one()
    assert guardado.token_hash != token and len(guardado.token_hash) == 64

    r = await api.get("/auth/restablecer-contrasena/validar", params={"token": token})
    assert r.status_code == 200, r.text

    r = await cambiar(api, token)
    assert r.status_code == 200, r.text
    r = await api.post("/auth/login", json={"correo": ana.correo, "contrasena": NUEVA})
    assert r.status_code == 200, r.text

    # Usarlo otra vez ya no sirve.
    r = await cambiar(api, token, "otra-clave-33")
    assert r.status_code == 400
    assert r.json()["data"]["codigo"] == "enlace_usado"
    r = await api.get("/auth/restablecer-contrasena/validar", params={"token": token})
    assert r.json()["data"]["codigo"] == "enlace_usado"


async def test_un_correo_inexistente_recibe_la_misma_respuesta_y_ningun_correo(api, correo):
    ana = await con_correo("Ana")

    existente = await pedir(api, ana.correo)
    inexistente = await pedir(api, "nadie@iglesia-pruebas.org")

    assert inexistente.status_code == existente.status_code == 200
    assert inexistente.json()["message"] == existente.json()["message"] == GENERICA
    assert [e["to"] for e in correo.enviados] == [ana.correo]


async def test_un_enlace_vencido_o_inventado_se_rechaza(api, correo):
    ana = await con_correo("Ana")
    await pedir(api, ana.correo)
    token = token_de(correo)
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Solicitud).values(expira_en=datetime.now(UTC) - timedelta(minutes=1))
        )
        await db.commit()

    r = await cambiar(api, token)
    assert r.status_code == 400
    assert r.json()["data"]["codigo"] == "enlace_vencido"
    assert r.json()["message"] == "El enlace ya venció. Solicita uno nuevo."

    r = await cambiar(api, "un-token-que-no-existe")
    assert r.status_code == 400
    assert r.json()["data"]["codigo"] == "enlace_invalido"

    # La contraseña sigue siendo la de antes.
    async with AsyncSessionLocal() as db:
        actual = (await db.get(UserModel, ana.id)).contrasena
    assert verify_password("clave-vieja-11", actual)


async def test_pedir_otro_enlace_anula_el_anterior(api, correo):
    ana = await con_correo("Ana")
    await pedir(api, ana.correo)
    primero = token_de(correo)
    await pedir(api, ana.correo)
    segundo = token_de(correo)

    assert (await cambiar(api, primero)).json()["data"]["codigo"] == "enlace_usado"
    assert (await cambiar(api, segundo)).status_code == 200


@pytest.mark.parametrize("contrasena", ["corta", "x" * 21])
async def test_la_contrasena_nueva_cumple_las_reglas_del_registro(api, correo, contrasena):
    ana = await con_correo("Ana")
    await pedir(api, ana.correo)

    r = await cambiar(api, token_de(correo), contrasena)

    assert r.status_code == 422
    # El enlace no se gastó por el intento fallido.
    assert (await cambiar(api, token_de(correo))).status_code == 200


async def test_restablecer_cierra_las_sesiones_abiertas(api, correo):
    ana = await con_correo("Ana")
    sesion = auth(ana)
    assert (await api.get(f"/users/{ana.id}", headers=sesion)).status_code == 200
    # La sesión se abrió antes del cambio.
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(UserModel).where(UserModel.id == ana.id).values(
                contrasena_cambiada_en=datetime.now(UTC) + timedelta(seconds=5)
            )
        )
        await db.commit()

    assert (await api.get(f"/users/{ana.id}", headers=sesion)).status_code == 401


async def test_despues_de_restablecer_se_puede_entrar_de_nuevo(api, correo):
    ana = await con_correo("Ana")
    await pedir(api, ana.correo)
    assert (await cambiar(api, token_de(correo))).status_code == 200

    r = await api.post("/auth/login", json={"correo": ana.correo, "contrasena": NUEVA})
    nueva_sesion = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}

    assert (await api.get(f"/users/{ana.id}", headers=nueva_sesion)).status_code == 200


async def test_limite_por_cuenta_en_silencio_y_por_ip_con_aviso(api, correo):
    ana = await con_correo("Ana")

    # Por cuenta: tres por hora. La cuarta responde igual, pero no envía.
    for _ in range(4):
        r = await pedir(api, ana.correo)
        assert r.status_code == 200 and r.json()["message"] == GENERICA
    assert len(correo.enviados) == 3

    # Por IP: diez por hora, exista o no el correo.
    for i in range(10):
        r = await pedir(api, f"persona{i}@iglesia-pruebas.org", ip="10.9.9.9")
        assert r.status_code == 200
    r = await pedir(api, "otra@iglesia-pruebas.org", ip="10.9.9.9")
    assert r.status_code == 429
    assert r.json()["message"].startswith("Demasiadas solicitudes")

    # Otra dirección no se ve afectada.
    assert (await pedir(api, "otra@iglesia-pruebas.org", ip="10.7.7.7")).status_code == 200
