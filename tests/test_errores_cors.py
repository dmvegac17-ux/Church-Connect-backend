import pytest

from src.application.events.services import EventService
from src.core.constants.enums import UserRole
from tests.conftest import auth
from tests.conftest import crear_usuario

pytestmark = pytest.mark.asyncio

# Origen permitido en desarrollo (`DEV_CORS_ORIGINS`).
ORIGEN = "http://localhost:5173"


async def test_un_error_no_controlado_responde_500_con_cabeceras_cors(api, monkeypatch):
    """
    Sin las cabeceras CORS el navegador bloquea el 500 y el frontend solo ve
    un fallo de red, no el error real.
    """
    admin = await crear_usuario("Admin", UserRole.ADMIN)

    async def falla(*args, **kwargs):
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(EventService, "get_all", falla)

    r = await api.get("/events", headers={**auth(admin), "Origin": ORIGEN})

    assert r.status_code == 500
    assert r.headers["access-control-allow-origin"] == ORIGEN
    cuerpo = r.json()
    assert cuerpo["success"] is False
    assert cuerpo["message"] == "Error interno del servidor"
    # El detalle interno queda en el log, no en la respuesta.
    assert "fallo simulado" not in r.text


async def test_las_respuestas_normales_conservan_sus_cabeceras_cors(api):
    admin = await crear_usuario("Admin", UserRole.ADMIN)

    ok = await api.get("/events", headers={**auth(admin), "Origin": ORIGEN})
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == ORIGEN

    # Los errores controlados (aquí, sin token) tampoco cambian.
    sin_token = await api.get("/events", headers={"Origin": ORIGEN})
    assert sin_token.status_code in (401, 403)
    assert sin_token.headers["access-control-allow-origin"] == ORIGEN
    assert sin_token.json()["success"] is False
