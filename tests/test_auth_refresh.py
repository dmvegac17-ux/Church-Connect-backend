from datetime import UTC
from datetime import datetime
from datetime import timedelta

import jwt
import pytest

from src.core.config import settings
from src.core.constants.enums import UserRole
from src.core.security.jwt import decode_access_token
from tests.conftest import auth
from tests.conftest import crear_usuario

pytestmark = pytest.mark.asyncio


def token_con(usuario, **claims) -> dict[str, str]:
    payload = {"sub": str(usuario.id), "rol": usuario.rol.value, **claims}
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    return {"Authorization": f"Bearer {token}"}


async def test_renovar_devuelve_un_token_con_la_expiracion_completa(api):
    ana = await crear_usuario("Ana")
    # A punto de vencer: le queda un minuto.
    por_vencer = token_con(ana, exp=datetime.now(UTC) + timedelta(minutes=1))

    r = await api.post("/auth/refresh", headers=por_vencer)
    assert r.status_code == 200, r.text

    nuevo = decode_access_token(r.json()["data"]["access_token"])
    assert nuevo["sub"] == str(ana.id)
    restante = nuevo["exp"] - datetime.now(UTC).timestamp()
    completo = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert completo - 30 < restante <= completo

    # El token nuevo sirve para seguir trabajando.
    cabecera = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
    assert (await api.get("/events", headers=cabecera)).status_code == 200


async def test_un_token_vencido_no_se_renueva(api):
    ana = await crear_usuario("Ana")
    vencido = token_con(ana, exp=datetime.now(UTC) - timedelta(seconds=5))

    r = await api.post("/auth/refresh", headers=vencido)

    assert r.status_code == 401


async def test_sin_token_no_se_renueva(api):
    r = await api.post("/auth/refresh")

    assert r.status_code in (401, 403)


async def test_un_usuario_inactivo_no_renueva(api):
    inactivo = await crear_usuario("Ines", activo=False)

    r = await api.post("/auth/refresh", headers=auth(inactivo))

    assert r.status_code == 401
    assert r.json()["message"] == "El usuario está inactivo"


async def test_el_token_renovado_lleva_el_rol_actual(api):
    ana = await crear_usuario("Ana", UserRole.ADMIN)
    # Token emitido cuando todavía era miembro.
    antiguo = token_con(
        ana, rol="MEMBER", exp=datetime.now(UTC) + timedelta(minutes=5)
    )

    r = await api.post("/auth/refresh", headers=antiguo)

    assert decode_access_token(r.json()["data"]["access_token"])["rol"] == "ADMIN"
