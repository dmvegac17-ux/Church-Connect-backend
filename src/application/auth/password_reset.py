"""
Restablecer la contraseña por correo.

Quien olvidó su contraseña pide un enlace; llega a su correo y sirve una sola
vez durante pocos minutos. Tres cuidados de seguridad:

- La respuesta al pedirlo es siempre la misma, exista o no el correo: no se
  puede usar para averiguar quién tiene cuenta.
- En la base solo queda el hash del token.
- Al cambiar la contraseña se cierran las sesiones abiertas de esa cuenta.
"""
import hashlib
import secrets
from collections import defaultdict
from collections import deque
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from time import monotonic
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config.settings import settings
from src.core.logging.logger import logger
from src.core.security.hashing import hash_password
from src.infrastructure.database.models.restablecimiento_contrasena_model import (
    RestablecimientoContrasenaModel as Solicitud,
)
from src.infrastructure.database.models.user_model import UserModel

# Un restablecimiento se hace en el momento: el enlace dura poco.
MINUTOS_DE_VIGENCIA = 15
# Solicitudes por hora: por cuenta (en la base) y por dirección IP (en memoria).
MAXIMO_POR_CUENTA = 3
MAXIMO_POR_IP = 10
VENTANA = timedelta(hours=1)

_por_ip: dict[str, deque[float]] = defaultdict(deque)


class DemasiadasSolicitudesError(Exception):
    def __init__(self):
        super().__init__(
            "Demasiadas solicitudes desde este dispositivo. Inténtalo de "
            "nuevo más tarde."
        )


class EnlaceError(Exception):
    """El enlace no sirve: `codigo` dice por qué, para explicarlo en pantalla."""

    MENSAJES = {
        "enlace_invalido": "El enlace no es válido. Solicita uno nuevo.",
        "enlace_vencido": "El enlace ya venció. Solicita uno nuevo.",
        "enlace_usado": (
            "Este enlace ya se usó o fue reemplazado por uno más reciente. "
            "Solicita uno nuevo."
        ),
    }

    def __init__(self, codigo: str):
        self.codigo = codigo
        super().__init__(self.MENSAJES[codigo])


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _utc(valor: datetime) -> datetime:
    return valor.replace(tzinfo=UTC) if valor.tzinfo is None else valor


def reiniciar_limites() -> None:
    """Olvida las solicitudes contadas por IP (para las pruebas)."""
    _por_ip.clear()


class PasswordResetService:

    def __init__(self, db: AsyncSession, email_service):
        self.db = db
        self.email_service = email_service

    @staticmethod
    def _contar_ip(ip: str) -> None:
        ahora = monotonic()
        recientes = _por_ip[ip]

        while recientes and ahora - recientes[0] > VENTANA.total_seconds():
            recientes.popleft()

        if len(recientes) >= MAXIMO_POR_IP:
            raise DemasiadasSolicitudesError()

        recientes.append(ahora)

    async def solicitar(self, correo: str, ip: str) -> None:
        """
        Envía el enlace si el correo es de una cuenta activa. No dice si lo
        era: quien llama responde siempre lo mismo.
        """
        self._contar_ip(ip)

        usuario = (
            await self.db.execute(
                select(UserModel).where(
                    func.lower(UserModel.correo) == correo.strip().lower()
                )
            )
        ).scalar_one_or_none()

        if not usuario or usuario.activo is False:
            return

        ahora = datetime.now(UTC)
        recientes = (
            await self.db.execute(
                select(func.count())
                .select_from(Solicitud)
                .where(
                    Solicitud.usuario_id == usuario.id,
                    Solicitud.creado_en >= ahora - VENTANA
                )
            )
        ).scalar_one()

        # En silencio: avisar del límite revelaría que la cuenta existe.
        if recientes >= MAXIMO_POR_CUENTA:
            logger.info("Límite de restablecimientos alcanzado para %s", usuario.id)
            return

        # Solo vale el enlace más reciente.
        await self._anular_pendientes(usuario.id, ahora)

        token = secrets.token_urlsafe(32)
        self.db.add(
            Solicitud(
                id=uuid4(),
                usuario_id=usuario.id,
                token_hash=_hash(token),
                expira_en=ahora + timedelta(minutes=MINUTOS_DE_VIGENCIA),
                creado_en=ahora
            )
        )
        await self.db.commit()

        enlace = f"{settings.frontend_url}/restablecer-contrasena?token={token}"

        if not settings.smtp_configured:
            # En desarrollo sin correo configurado, el enlace queda a la vista.
            logger.info("Enlace para restablecer la contraseña de %s: %s", correo, enlace)

        await self.email_service.send_password_reset(
            to=usuario.correo,
            usuario_nombre=usuario.nombre,
            enlace=enlace,
            minutos=MINUTOS_DE_VIGENCIA
        )

    async def _anular_pendientes(self, usuario_id, ahora: datetime) -> None:
        await self.db.execute(
            update(Solicitud)
            .where(
                Solicitud.usuario_id == usuario_id,
                Solicitud.usado_en.is_(None)
            )
            .values(usado_en=ahora)
            .execution_options(synchronize_session=False)
        )

    async def _vigente(self, token: str) -> Solicitud:
        solicitud = (
            await self.db.execute(
                select(Solicitud).where(Solicitud.token_hash == _hash(token))
            )
        ).scalar_one_or_none()

        if not solicitud:
            raise EnlaceError("enlace_invalido")

        if solicitud.usado_en is not None:
            raise EnlaceError("enlace_usado")

        if _utc(solicitud.expira_en) < datetime.now(UTC):
            raise EnlaceError("enlace_vencido")

        return solicitud

    async def validar(self, token: str) -> None:
        """Lanza `EnlaceError` si el enlace ya no sirve."""
        await self._vigente(token)

    async def restablecer(self, token: str, contrasena: str) -> None:
        solicitud = await self._vigente(token)
        ahora = datetime.now(UTC)

        # La comparación va en el propio UPDATE: de dos intentos simultáneos
        # con el mismo enlace, solo uno lo consume.
        consumido = await self.db.execute(
            update(Solicitud)
            .where(Solicitud.id == solicitud.id, Solicitud.usado_en.is_(None))
            .values(usado_en=ahora)
            .execution_options(synchronize_session=False)
        )

        if consumido.rowcount != 1:
            await self.db.rollback()
            raise EnlaceError("enlace_usado")

        await self.db.execute(
            update(UserModel)
            .where(UserModel.id == solicitud.usuario_id)
            .values(
                contrasena=hash_password(contrasena),
                # Cierra las sesiones abiertas: sus tokens son anteriores.
                contrasena_cambiada_en=ahora
            )
            .execution_options(synchronize_session=False)
        )
        await self._anular_pendientes(solicitud.usuario_id, ahora)
        await self.db.commit()
