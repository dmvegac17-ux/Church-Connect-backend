from datetime import UTC
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import event

from src.core.constants.enums import UserRole
from src.infrastructure.database.models.notificaciones_model import NotificacionesModel
from tests.conftest import AsyncSessionLocal
from tests.conftest import auth
from tests.conftest import crear_usuario
from tests.conftest import engine

pytestmark = pytest.mark.asyncio


async def avisos(usuario, cuantos: int, leida: bool = False) -> list[str]:
    async with AsyncSessionLocal() as db:
        filas = [
            NotificacionesModel(
                id=uuid4(), usuario_id=usuario.id, titulo=f"Aviso {i}",
                mensaje="<div>Hola</div>", leida=leida, fecha_envio=datetime.now(UTC),
            )
            for i in range(cuantos)
        ]
        db.add_all(filas)
        await db.commit()

        return [str(fila.id) for fila in filas]


async def no_leidas(api, usuario) -> int:
    r = await api.get("/notificaciones/no-leidas", headers=auth(usuario))
    assert r.status_code == 200, r.text

    return r.json()["data"]["total"]


async def test_marca_varias_con_una_sola_sentencia(api):
    ana = await crear_usuario("Ana")
    ids = await avisos(ana, 5)
    sentencias: list[str] = []

    def anotar(_conn, _cursor, sentencia, *_):
        if sentencia.lstrip().upper().startswith("UPDATE NOTIFICACIONES"):
            sentencias.append(sentencia)

    event.listen(engine.sync_engine, "before_cursor_execute", anotar)
    try:
        r = await api.put(
            "/notificaciones/leidas", headers=auth(ana), json={"ids": ids[:3]}
        )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", anotar)

    assert r.status_code == 200, r.text
    assert r.json()["data"] == {"actualizadas": 3}
    # Tres notificaciones, un único UPDATE.
    assert len(sentencias) == 1
    assert await no_leidas(api, ana) == 2

    # También en sentido contrario, y repetir un id no cuenta doble.
    r = await api.put(
        "/notificaciones/leidas", headers=auth(ana),
        json={"ids": [ids[0], ids[0]], "leida": False},
    )
    assert r.json()["data"] == {"actualizadas": 1}
    assert await no_leidas(api, ana) == 3


async def test_con_un_id_ajeno_no_se_marca_ninguna(api):
    ana = await crear_usuario("Ana")
    beto = await crear_usuario("Beto")
    propias = await avisos(ana, 2)
    ajena = await avisos(beto, 1)

    r = await api.put(
        "/notificaciones/leidas", headers=auth(ana), json={"ids": propias + ajena}
    )

    assert r.status_code == 403
    assert r.json()["message"] == "Alguna notificación no existe o no te pertenece"
    # Todo o nada: las propias siguen sin leer, y la de Beto intacta.
    assert await no_leidas(api, ana) == 2
    assert await no_leidas(api, beto) == 1

    # Ni siendo administrador se marcan las de otra persona.
    admin = await crear_usuario("Admin", UserRole.ADMIN)
    r = await api.put("/notificaciones/leidas", headers=auth(admin), json={"ids": ajena})
    assert r.status_code == 403


async def test_limites_de_la_peticion(api):
    ana = await crear_usuario("Ana")

    r = await api.put("/notificaciones/leidas", headers=auth(ana), json={"ids": []})
    assert r.status_code == 400
    assert r.json()["message"] == "Indica al menos una notificación"

    r = await api.put(
        "/notificaciones/leidas", headers=auth(ana),
        json={"ids": [str(uuid4()) for _ in range(501)]},
    )
    assert r.status_code == 400
    assert r.json()["message"] == (
        "Se pueden marcar como máximo 500 notificaciones por petición"
    )


async def test_marcar_todas_solo_toca_las_propias_sin_leer(api):
    ana = await crear_usuario("Ana")
    beto = await crear_usuario("Beto")
    await avisos(ana, 4)
    await avisos(ana, 2, leida=True)
    await avisos(beto, 3)

    r = await api.put("/notificaciones/leidas/todas", headers=auth(ana))

    assert r.status_code == 200, r.text
    assert r.json()["data"] == {"actualizadas": 4}
    assert await no_leidas(api, ana) == 0
    assert await no_leidas(api, beto) == 3

    # Sin nada pendiente no falla: simplemente no actualiza.
    r = await api.put("/notificaciones/leidas/todas", headers=auth(ana))
    assert r.json()["data"] == {"actualizadas": 0}


async def test_los_listados_no_vencen_invitaciones_en_cada_lectura(api, monkeypatch):
    from src.application.participaciones import services

    ana = await crear_usuario("Ana")
    llamadas = 0
    original = services.ParticipacionService.vencer_pendientes

    async def contar(self):
        nonlocal llamadas
        llamadas += 1
        return await original(self)

    monkeypatch.setattr(services.ParticipacionService, "vencer_pendientes", contar)
    monkeypatch.setattr(services, "VENCER_EN_LECTURAS_CADA_S", 60.0)
    monkeypatch.setattr(services, "_ultimo_vencimiento", float("-inf"))

    for _ in range(3):
        r = await api.get("/participante/invitaciones", headers=auth(ana))
        assert r.status_code == 200, r.text

    # Tres lecturas seguidas, un solo vencimiento.
    assert llamadas == 1
