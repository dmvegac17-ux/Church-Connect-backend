from datetime import UTC
from datetime import datetime
from datetime import timedelta
from uuid import UUID
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.api.dependencies.announcements import get_announcements_storage
from src.application.announcements.services import IMAGEN_MAX_BYTES
from src.core.constants.enums import UserRole
from src.infrastructure.database.models.announcement_model import AnnouncementModel
from src.infrastructure.repositories.announcement_repository import AnnouncementRepository
from src.infrastructure.supabase.client import StorageError
from src.main import app
from tests.conftest import AsyncSessionLocal
from tests.conftest import auth
from tests.conftest import crear_usuario

pytestmark = pytest.mark.asyncio

# Firmas mínimas de cada formato: el servidor mira el contenido, no el nombre.
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64


class FakeStorage:
    """Bucket en memoria: registra subidas y borrados, y puede fallar."""

    def __init__(self):
        self.archivos: dict[str, bytes] = {}
        self.borrados: list[str] = []
        self.fallar_subida = False
        self.fallar_borrado = False

    def public_url(self, path):
        return f"https://storage.test/public/Flyers/{path}"

    async def upload(self, path, contenido, content_type):
        if self.fallar_subida:
            raise StorageError("No se pudo subir la imagen. Inténtalo de nuevo.")
        assert path not in self.archivos, "los nombres deben ser únicos"
        self.archivos[path] = contenido
        return self.public_url(path)

    async def delete(self, path):
        if self.fallar_borrado:
            return False
        self.borrados.append(path)
        self.archivos.pop(path, None)
        return True


@pytest.fixture
def storage(api):
    fake = FakeStorage()
    app.dependency_overrides[get_announcements_storage] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_announcements_storage, None)


@pytest.fixture
async def gente(api):
    return {
        "admin": await crear_usuario("Ada", UserRole.ADMIN),
        "otro_admin": await crear_usuario("Otto", UserRole.ADMIN),
        "miembro": await crear_usuario("Mia", UserRole.MEMBER),
    }


async def crear(api, admin, titulo="Aviso", contenido="Texto del aviso", imagen=None, extra=None):
    files = {"imagen": imagen} if imagen else None
    return await api.post(
        "/announcements",
        headers=auth(admin),
        data={"titulo": titulo, "contenido": contenido, **(extra or {})},
        files=files,
    )


async def leer(anuncio_id) -> AnnouncementModel:
    async with AsyncSessionLocal() as db:
        return (
            await db.execute(
                select(AnnouncementModel).where(AnnouncementModel.id == UUID(str(anuncio_id)))
            )
        ).scalar_one_or_none()


# ── Crear ───────────────────────────────────────────────────────────────

async def test_crear_sin_imagen(api, storage, gente):
    r = await crear(api, gente["admin"])

    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["imagen_url"] is None
    assert data["publicado_por"]["nombre_completo"] == "Ada Prueba"
    assert data["actualizado_por"] is None
    assert data["fecha_actualizacion"] is None
    assert storage.archivos == {}


@pytest.mark.parametrize("contenido,ext", [(PNG, "png"), (JPG, "jpg"), (WEBP, "webp")])
async def test_crear_con_imagen(api, storage, gente, contenido, ext):
    r = await crear(api, gente["admin"], imagen=("foto.bin", contenido, "application/octet-stream"))

    assert r.status_code == 201, r.text
    data = r.json()["data"]
    anuncio = await leer(data["id"])

    # La extensión sale del contenido real, no del nombre ni del tipo declarado.
    assert anuncio.imagen_path.startswith(f"announcements/{data['id']}/")
    assert anuncio.imagen_path.endswith(f".{ext}")
    assert data["imagen_url"] == storage.public_url(anuncio.imagen_path)
    assert storage.archivos[anuncio.imagen_path] == contenido


async def test_el_autor_es_siempre_el_usuario_autenticado(api, storage, gente):
    falso = str(uuid4())
    r = await crear(
        api, gente["admin"],
        extra={"publicado_por": falso, "actualizado_por": falso, "imagen_url": "https://x.test/a.png"},
    )

    data = r.json()["data"]
    assert data["publicado_por"]["id"] == str(gente["admin"].id)
    assert data["imagen_url"] is None

    r = await api.put(
        f"/announcements/{data['id']}",
        headers=auth(gente["otro_admin"]),
        data={"titulo": "Nuevo", "actualizado_por": falso, "publicado_por": falso},
    )
    data = r.json()["data"]
    assert data["publicado_por"]["id"] == str(gente["admin"].id)
    assert data["actualizado_por"]["id"] == str(gente["otro_admin"].id)


@pytest.mark.parametrize(
    "datos,campo",
    [
        ({"titulo": "   ", "contenido": "x"}, "titulo"),
        ({"titulo": "x" * 151, "contenido": "x"}, "titulo"),
        ({"titulo": "x", "contenido": ""}, "contenido"),
        ({"titulo": "x", "contenido": "x" * 5001}, "contenido"),
    ],
)
async def test_titulo_y_texto_validados(api, storage, gente, datos, campo):
    r = await crear(api, gente["admin"], **datos)

    assert r.status_code == 422
    assert r.json()["data"]["campo"] == campo


async def test_imagen_con_tipo_no_permitido(api, storage, gente):
    # Un GIF (o cualquier otra cosa) se rechaza aunque diga ser PNG.
    r = await crear(api, gente["admin"], imagen=("foto.png", b"GIF89a" + b"\x00" * 32, "image/png"))

    assert r.status_code == 422
    assert r.json()["data"]["campo"] == "imagen"
    assert "JPG, PNG o WebP" in r.json()["message"]
    assert storage.archivos == {}
    async with AsyncSessionLocal() as db:
        assert (await AnnouncementRepository(db).count()) == 0


async def test_imagen_demasiado_grande(api, storage, gente):
    grande = PNG + b"\x00" * IMAGEN_MAX_BYTES
    r = await crear(api, gente["admin"], imagen=("grande.png", grande, "image/png"))

    assert r.status_code == 422
    assert "5 MB" in r.json()["message"]
    assert storage.archivos == {}


async def test_si_storage_falla_no_se_crea_el_anuncio(api, storage, gente):
    storage.fallar_subida = True
    r = await crear(api, gente["admin"], imagen=("f.png", PNG, "image/png"))

    assert r.status_code == 502
    assert "No se pudo subir la imagen" in r.json()["message"]
    async with AsyncSessionLocal() as db:
        assert (await AnnouncementRepository(db).count()) == 0


async def test_sin_storage_configurado_se_avisa(api, gente):
    # Con la configuración real de pruebas (sin SUPABASE_URL ni clave).
    r = await crear(api, gente["admin"], imagen=("f.png", PNG, "image/png"))

    assert r.status_code == 503
    assert "no está configurada" in r.json()["message"]


# ── Editar ──────────────────────────────────────────────────────────────

async def test_editar_texto(api, storage, gente):
    creado = (await crear(api, gente["admin"])).json()["data"]

    r = await api.put(
        f"/announcements/{creado['id']}",
        headers=auth(gente["otro_admin"]),
        data={"contenido": "Texto corregido"},
    )

    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["contenido"] == "Texto corregido"
    assert data["titulo"] == "Aviso"
    assert data["actualizado_por"]["nombre_completo"] == "Otto Prueba"
    assert data["fecha_actualizacion"] is not None


async def test_reemplazar_imagen_borra_la_anterior(api, storage, gente):
    creado = (await crear(api, gente["admin"], imagen=("a.png", PNG, "image/png"))).json()["data"]
    anterior = (await leer(creado["id"])).imagen_path

    r = await api.put(
        f"/announcements/{creado['id']}",
        headers=auth(gente["admin"]),
        files={"imagen": ("b.jpg", JPG, "image/jpeg")},
    )

    assert r.status_code == 200, r.text
    nueva = (await leer(creado["id"])).imagen_path
    assert nueva != anterior and nueva.endswith(".jpg")
    assert storage.borrados == [anterior]
    assert list(storage.archivos) == [nueva]
    assert r.json()["data"]["imagen_url"] == storage.public_url(nueva)


async def test_quitar_imagen(api, storage, gente):
    creado = (await crear(api, gente["admin"], imagen=("a.png", PNG, "image/png"))).json()["data"]
    anterior = (await leer(creado["id"])).imagen_path

    r = await api.put(
        f"/announcements/{creado['id']}",
        headers=auth(gente["admin"]),
        data={"quitar_imagen": "true"},
    )

    assert r.status_code == 200
    assert r.json()["data"]["imagen_url"] is None
    anuncio = await leer(creado["id"])
    assert anuncio.imagen_path is None and anuncio.imagen_url is None
    assert storage.borrados == [anterior]
    assert storage.archivos == {}


async def test_reemplazo_fallido_conserva_la_imagen_anterior(api, storage, gente):
    creado = (await crear(api, gente["admin"], imagen=("a.png", PNG, "image/png"))).json()["data"]
    anterior = await leer(creado["id"])

    storage.fallar_subida = True
    r = await api.put(
        f"/announcements/{creado['id']}",
        headers=auth(gente["admin"]),
        data={"titulo": "No debe guardarse"},
        files={"imagen": ("b.png", PNG, "image/png")},
    )

    assert r.status_code == 502
    actual = await leer(creado["id"])
    assert actual.imagen_path == anterior.imagen_path
    assert actual.titulo == "Aviso"
    assert storage.borrados == []


async def test_reemplazar_y_quitar_a_la_vez_es_invalido(api, storage, gente):
    creado = (await crear(api, gente["admin"])).json()["data"]

    r = await api.put(
        f"/announcements/{creado['id']}",
        headers=auth(gente["admin"]),
        data={"quitar_imagen": "true"},
        files={"imagen": ("b.png", PNG, "image/png")},
    )

    assert r.status_code == 422
    assert storage.archivos == {}


# ── Eliminar ────────────────────────────────────────────────────────────

async def test_eliminar_borra_la_imagen_del_bucket(api, storage, gente):
    creado = (await crear(api, gente["admin"], imagen=("a.png", PNG, "image/png"))).json()["data"]
    path = (await leer(creado["id"])).imagen_path

    r = await api.delete(f"/announcements/{creado['id']}", headers=auth(gente["admin"]))

    assert r.status_code == 200
    assert await leer(creado["id"]) is None
    assert storage.borrados == [path]
    assert storage.archivos == {}


async def test_si_falla_el_borrado_en_storage_el_anuncio_igual_se_elimina(api, storage, gente):
    creado = (await crear(api, gente["admin"], imagen=("a.png", PNG, "image/png"))).json()["data"]
    storage.fallar_borrado = True

    r = await api.delete(f"/announcements/{creado['id']}", headers=auth(gente["admin"]))

    # Queda a lo sumo un archivo huérfano (en el log), nunca un anuncio roto.
    assert r.status_code == 200
    assert await leer(creado["id"]) is None


# ── Permisos y listado ──────────────────────────────────────────────────

async def test_un_miembro_no_puede_crear_editar_eliminar_ni_subir(api, storage, gente):
    creado = (await crear(api, gente["admin"])).json()["data"]
    cabeceras = auth(gente["miembro"])

    r = await api.post(
        "/announcements", headers=cabeceras,
        data={"titulo": "x", "contenido": "x"}, files={"imagen": ("a.png", PNG, "image/png")},
    )
    assert r.status_code == 403
    r = await api.put(
        f"/announcements/{creado['id']}", headers=cabeceras,
        files={"imagen": ("a.png", PNG, "image/png")},
    )
    assert r.status_code == 403
    assert (await api.delete(f"/announcements/{creado['id']}", headers=cabeceras)).status_code == 403

    assert storage.archivos == {}
    assert (await leer(creado["id"])).titulo == "Aviso"


async def test_un_miembro_puede_listar_y_ver(api, storage, gente):
    creado = (await crear(api, gente["admin"])).json()["data"]
    cabeceras = auth(gente["miembro"])

    assert (await api.get("/announcements", headers=cabeceras)).status_code == 200
    r = await api.get(f"/announcements/{creado['id']}", headers=cabeceras)
    assert r.status_code == 200
    assert r.json()["data"]["publicado_por"]["nombre_completo"] == "Ada Prueba"

    assert (await api.get("/announcements")).status_code in (401, 403)


async def test_listado_paginado_del_mas_reciente_al_mas_antiguo(api, storage, gente):
    ahora = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        for dias, titulo in ((3, "Viejo"), (1, "Reciente"), (2, "Medio")):
            db.add(
                AnnouncementModel(
                    id=uuid4(), titulo=titulo, contenido="x",
                    publicado_por=gente["admin"].id,
                    fecha_publicacion=ahora - timedelta(days=dias),
                )
            )
        await db.commit()

    r = await api.get("/announcements", headers=auth(gente["miembro"]), params={"limit": 2})
    assert [a["titulo"] for a in r.json()["data"]] == ["Reciente", "Medio"]
    assert r.json()["meta"] == {"totalAnnouncements": 3}

    r = await api.get(
        "/announcements", headers=auth(gente["miembro"]), params={"limit": 2, "offset": 2}
    )
    assert [a["titulo"] for a in r.json()["data"]] == ["Viejo"]


async def test_el_listado_trae_los_nombres_en_una_sola_consulta(api, storage, gente):
    for i in range(5):
        await crear(api, gente["admin"], titulo=f"Aviso {i}")

    from sqlalchemy import event as sa_event

    from src.infrastructure.database.session import engine

    sentencias: list[str] = []

    def contar(_conn, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith("SELECT"):
            sentencias.append(statement)

    sa_event.listen(engine.sync_engine, "before_cursor_execute", contar)
    try:
        async with AsyncSessionLocal() as db:
            filas = await AnnouncementRepository(db).get_all(limit=10, offset=0)
    finally:
        sa_event.remove(engine.sync_engine, "before_cursor_execute", contar)

    assert len(filas) == 5
    assert len(sentencias) == 1
    assert all(fila[1] == "Ada" for fila in filas)


async def test_autor_eliminado_conserva_el_anuncio(api, storage, gente):
    creado = (await crear(api, gente["otro_admin"])).json()["data"]

    from src.infrastructure.database.models.user_model import UserModel

    async with AsyncSessionLocal() as db:
        usuario = await db.get(UserModel, gente["otro_admin"].id)
        await db.delete(usuario)
        await db.commit()

    r = await api.get(f"/announcements/{creado['id']}", headers=auth(gente["miembro"]))
    assert r.status_code == 200
    assert r.json()["data"]["publicado_por"] is None
