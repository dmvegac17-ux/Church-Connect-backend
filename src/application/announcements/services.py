from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from uuid import UUID
from uuid import uuid4

from src.core.logging.logger import logger
from src.infrastructure.database.models.announcement_model import AnnouncementModel
from src.infrastructure.database.models.user_model import UserModel
from src.infrastructure.repositories.announcement_repository import AnnouncementRepository
from src.infrastructure.supabase.client import SupabaseStorage

TITULO_MAX = 150
CONTENIDO_MAX = 5000
IMAGEN_MAX_BYTES = 5 * 1024 * 1024

# Tipo → extensión. El tipo se deduce del contenido, no de lo que declare el
# navegador ni del nombre del archivo.
TIPOS_IMAGEN = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

# Carpeta dentro del bucket compartido.
CARPETA = "announcements"


class AnuncioNoEncontradoError(Exception):
    pass


class DatosAnuncioInvalidosError(Exception):
    """Validación de un campo, con el nombre del campo para el cliente (422)."""

    def __init__(self, campo: str, mensaje: str):
        self.campo = campo
        super().__init__(mensaje)


class ImagenInvalidaError(DatosAnuncioInvalidosError):
    def __init__(self, mensaje: str):
        super().__init__("imagen", mensaje)


@dataclass
class ImagenSubida:
    """Archivo recibido del cliente, aún sin validar."""

    contenido: bytes
    nombre: str | None = None


def detectar_tipo(contenido: bytes) -> str | None:
    """Tipo real de la imagen por sus primeros bytes (firma del formato)."""
    if contenido.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    if len(contenido) >= 12 and contenido[:4] == b"RIFF" and contenido[8:12] == b"WEBP":
        return "image/webp"

    return None


def validar_imagen(imagen: ImagenSubida) -> str:
    """Devuelve el tipo de la imagen o lanza `ImagenInvalidaError`."""
    if not imagen.contenido:
        raise ImagenInvalidaError("La imagen está vacía.")

    if len(imagen.contenido) > IMAGEN_MAX_BYTES:
        raise ImagenInvalidaError("La imagen supera el tamaño máximo de 5 MB.")

    tipo = detectar_tipo(imagen.contenido)

    if tipo is None:
        raise ImagenInvalidaError(
            "Formato no permitido. Usa una imagen JPG, PNG o WebP."
        )

    return tipo


def _nombre_completo(nombre: str | None, apellido: str | None) -> str | None:
    if not nombre:
        return None

    return f"{nombre} {apellido or ''}".strip()


def _texto(valor: str | None, campo: str, etiqueta: str, maximo: int) -> str:
    texto = (valor or "").strip()

    if not texto:
        raise DatosAnuncioInvalidosError(campo, f"Escribe {etiqueta}.")

    if len(texto) > maximo:
        raise DatosAnuncioInvalidosError(
            campo, f"{etiqueta.capitalize()} admite máximo {maximo} caracteres."
        )

    return texto


class AnnouncementService:

    def __init__(
        self,
        repository: AnnouncementRepository,
        storage: SupabaseStorage,
        ahora: Callable[[], datetime] | None = None
    ):
        self.repository = repository
        self.storage = storage
        self._ahora = ahora or (lambda: datetime.now(UTC))

    # ── DTO ─────────────────────────────────────────────────────────────

    @staticmethod
    def _dto(fila) -> dict:
        anuncio, autor_nombre, autor_apellido, editor_nombre, editor_apellido = fila

        def persona(usuario_id, nombre, apellido):
            if usuario_id is None:
                return None

            return {
                "id": usuario_id,
                "nombre_completo": _nombre_completo(nombre, apellido) or "Usuario",
            }

        return {
            "id": anuncio.id,
            "titulo": anuncio.titulo,
            "contenido": anuncio.contenido,
            "imagen_url": anuncio.imagen_url,
            "publicado_por": persona(anuncio.publicado_por, autor_nombre, autor_apellido),
            "fecha_publicacion": anuncio.fecha_publicacion,
            "actualizado_por": persona(anuncio.actualizado_por, editor_nombre, editor_apellido),
            "fecha_actualizacion": anuncio.fecha_actualizacion,
        }

    async def _detalle(self, announcement_id: UUID) -> dict:
        fila = await self.repository.get_detalle(announcement_id)

        if not fila:
            raise AnuncioNoEncontradoError("Anuncio no encontrado")

        return self._dto(fila)

    # ── Lectura ─────────────────────────────────────────────────────────

    async def get_all(self, limit: int, offset: int) -> list[dict]:
        filas = await self.repository.get_all(limit=limit, offset=offset)

        return [self._dto(fila) for fila in filas]

    async def count(self) -> int:
        return await self.repository.count()

    async def get_by_id(self, announcement_id: UUID) -> dict:
        return await self._detalle(announcement_id)

    # ── Imágenes ────────────────────────────────────────────────────────

    async def _subir(self, announcement_id: UUID, imagen: ImagenSubida) -> tuple[str, str]:
        """Valida y sube la imagen. Devuelve `(path, url_publica)`."""
        tipo = validar_imagen(imagen)
        # Nombre único: una imagen reemplazada nunca reaparece por la caché.
        path = f"{CARPETA}/{announcement_id}/{uuid4().hex}.{TIPOS_IMAGEN[tipo]}"
        url = await self.storage.upload(path, imagen.contenido, tipo)

        return path, url

    async def _borrar_archivo(self, path: str | None, motivo: str) -> None:
        if path and not await self.storage.delete(path):
            logger.warning(
                "Imagen huérfana en Storage (%s): %s", motivo, path
            )

    # ── Escritura ───────────────────────────────────────────────────────

    async def create(
        self,
        autor: UserModel,
        titulo: str | None,
        contenido: str | None,
        imagen: ImagenSubida | None
    ) -> dict:
        titulo = _texto(titulo, "titulo", "el título", TITULO_MAX)
        contenido = _texto(contenido, "contenido", "el texto", CONTENIDO_MAX)
        if imagen is not None:
            validar_imagen(imagen)

        anuncio_id = uuid4()
        path = url = None

        # 1) Primero la imagen: si falla, no se crea nada.
        if imagen is not None:
            path, url = await self._subir(anuncio_id, imagen)

        anuncio = AnnouncementModel(
            id=anuncio_id,
            titulo=titulo,
            contenido=contenido,
            imagen_url=url,
            imagen_path=path,
            # Siempre el usuario autenticado, nunca lo que mande el cliente.
            publicado_por=autor.id,
            fecha_publicacion=self._ahora()
        )

        # 2) Después la base: si falla, se retira la imagen recién subida.
        try:
            await self.repository.create(anuncio)
        except Exception:
            await self.repository.rollback()
            await self._borrar_archivo(path, "falló al crear el anuncio")
            raise

        return await self._detalle(anuncio_id)

    async def update(
        self,
        announcement_id: UUID,
        editor: UserModel,
        titulo: str | None,
        contenido: str | None,
        imagen: ImagenSubida | None,
        quitar_imagen: bool
    ) -> dict:
        anuncio = await self.repository.get_by_id(announcement_id)

        if not anuncio:
            raise AnuncioNoEncontradoError("Anuncio no encontrado")

        if imagen is not None and quitar_imagen:
            raise DatosAnuncioInvalidosError(
                "imagen", "Elige entre reemplazar la imagen o quitarla, no ambas."
            )

        nuevo_titulo = (
            _texto(titulo, "titulo", "el título", TITULO_MAX)
            if titulo is not None else None
        )
        nuevo_contenido = (
            _texto(contenido, "contenido", "el texto", CONTENIDO_MAX)
            if contenido is not None else None
        )
        if imagen is not None:
            validar_imagen(imagen)

        anterior = anuncio.imagen_path
        nuevo_path = nuevo_url = None

        # 1) La imagen nueva se sube antes de tocar la base.
        if imagen is not None:
            nuevo_path, nuevo_url = await self._subir(announcement_id, imagen)

        if nuevo_titulo is not None:
            anuncio.titulo = nuevo_titulo
        if nuevo_contenido is not None:
            anuncio.contenido = nuevo_contenido
        if imagen is not None:
            anuncio.imagen_url = nuevo_url
            anuncio.imagen_path = nuevo_path
        elif quitar_imagen:
            anuncio.imagen_url = None
            anuncio.imagen_path = None

        anuncio.actualizado_por = editor.id
        anuncio.fecha_actualizacion = self._ahora()

        # 2) La base. Si falla, se retira la nueva y la anterior sigue intacta.
        try:
            await self.repository.update(anuncio)
        except Exception:
            await self.repository.rollback()
            await self._borrar_archivo(nuevo_path, "falló al actualizar el anuncio")
            raise

        # 3) Solo con el cambio confirmado se borra la imagen que ya no se usa.
        if (imagen is not None or quitar_imagen) and anterior:
            await self._borrar_archivo(anterior, "reemplazada o quitada")

        return await self._detalle(announcement_id)

    async def delete(self, announcement_id: UUID) -> None:
        anuncio = await self.repository.get_by_id(announcement_id)

        if not anuncio:
            raise AnuncioNoEncontradoError("Anuncio no encontrado")

        path = anuncio.imagen_path

        # Primero la base: un fallo en Storage deja como mucho un archivo
        # huérfano (registrado en el log), nunca un anuncio con imagen rota.
        await self.repository.delete(anuncio)
        await self._borrar_archivo(path, "anuncio eliminado")
