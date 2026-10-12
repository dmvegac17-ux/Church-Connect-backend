from urllib.parse import quote
from urllib.parse import urlsplit

import httpx

from src.core.config.settings import settings
from src.core.logging.logger import logger


def _base_url(valor: str) -> str:
    """
    Solo esquema y dominio del proyecto. Así funciona aunque se copie la URL
    de la API REST (`https://<ref>.supabase.co/rest/v1`) en vez de la base.
    """
    partes = urlsplit(valor.strip())

    if not partes.scheme or not partes.netloc:
        return valor.strip().rstrip("/")

    return f"{partes.scheme}://{partes.netloc}"


class StorageNoConfiguradoError(Exception):
    pass


class StorageError(Exception):
    pass


class SupabaseStorage:
    """
    Cliente mínimo de la API REST de Supabase Storage para un bucket.

    Se autentica con la service role key, así que solo debe usarse desde el
    backend: el bucket no tiene políticas de escritura para `anon` ni para
    `authenticated`, y este servidor es el único que sube o borra.
    """

    def __init__(
        self,
        url: str | None = None,
        service_key: str | None = None,
        bucket: str | None = None,
        timeout: float = 20.0
    ):
        self.url = _base_url(url if url is not None else settings.SUPABASE_URL)
        self.service_key = (
            service_key if service_key is not None
            else settings.SUPABASE_SERVICE_ROLE_KEY
        ).strip()
        self.bucket = (
            bucket if bucket is not None
            else settings.SUPABASE_ANNOUNCEMENTS_BUCKET
        ).strip()
        self.timeout = timeout

    @property
    def configurado(self) -> bool:
        return bool(self.url and self.service_key and self.bucket)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
        }

    def _ruta(self, path: str) -> str:
        return f"{quote(self.bucket)}/{quote(path)}"

    def public_url(self, path: str) -> str:
        """El bucket es público para lectura: la URL no caduca."""
        return f"{self.url}/storage/v1/object/public/{self._ruta(path)}"

    async def upload(self, path: str, contenido: bytes, content_type: str) -> str:
        """Sube un archivo nuevo (sin sobrescribir) y devuelve su URL pública."""
        if not self.configurado:
            raise StorageNoConfiguradoError(
                "La subida de imágenes no está configurada en el servidor."
            )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                respuesta = await client.post(
                    f"{self.url}/storage/v1/object/{self._ruta(path)}",
                    content=contenido,
                    headers={
                        **self._headers(),
                        "Content-Type": content_type,
                        "x-upsert": "false",
                        "cache-control": "31536000",
                    },
                )
        except httpx.HTTPError as ex:
            logger.exception("Fallo de red al subir %s a Storage", path)
            raise StorageError("No se pudo subir la imagen. Inténtalo de nuevo.") from ex

        if respuesta.status_code >= 300:
            logger.error(
                "Storage rechazó la subida de %s: %s %s",
                path,
                respuesta.status_code,
                respuesta.text[:300]
            )
            raise StorageError("No se pudo subir la imagen. Inténtalo de nuevo.")

        return self.public_url(path)

    async def delete(self, path: str) -> bool:
        """
        Borra un archivo. Nunca lanza: devuelve `False` y deja el error en el
        log, porque se llama después de confirmar el cambio en la base y un
        archivo huérfano no debe deshacerlo.
        """
        if not self.configurado:
            logger.warning(
                "Storage no configurado; no se borró %s del bucket", path
            )
            return False

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                respuesta = await client.request(
                    "DELETE",
                    f"{self.url}/storage/v1/object/{quote(self.bucket)}",
                    json={"prefixes": [path]},
                    headers=self._headers(),
                )
        except httpx.HTTPError:
            logger.exception("Fallo de red al borrar %s de Storage", path)
            return False

        if respuesta.status_code >= 300:
            logger.error(
                "Storage no borró %s: %s %s",
                path,
                respuesta.status_code,
                respuesta.text[:300]
            )
            return False

        return True


announcements_storage = SupabaseStorage()
