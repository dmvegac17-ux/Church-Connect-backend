from datetime import UTC
from datetime import datetime
from uuid import UUID
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from src.application.events.registration_window import cancellation_closed
from src.application.events.registration_window import registration_closed
from src.application.events.registration_window import started
from src.core.constants.enums import UserRole
from src.infrastructure.database.models.registration_model import RegistrationModel
from src.infrastructure.database.models.user_model import UserModel
from src.infrastructure.repositories.aforo_repository import AforoRepository
from src.infrastructure.repositories.event_repository import EventRepository
from src.infrastructure.repositories.registration_repository import RegistrationRepository


class RegistrationNotFoundError(Exception):
    pass


class EventNotFoundError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class ForbiddenRegistrationAccessError(Exception):
    pass


class RegistrationConflictError(Exception):
    """La inscripción no procede (409). `codigo` le dice al cliente por qué."""

    codigo = "conflicto"


class EventFullError(RegistrationConflictError):
    codigo = "sin_cupos"


class DuplicateRegistrationError(RegistrationConflictError):
    codigo = "ya_inscrito"


class ParticipantRegistrationError(RegistrationConflictError):
    codigo = "es_participante"


class RegistrationClosedError(RegistrationConflictError):
    codigo = "inscripciones_cerradas"


class CancellationClosedError(RegistrationConflictError):
    codigo = "cancelacion_cerrada"


def _utc(valor: datetime) -> datetime:
    return valor.replace(tzinfo=UTC) if valor.tzinfo is None else valor


def _nombre_completo(usuario: UserModel) -> str:
    return f"{usuario.nombre} {usuario.apellido or ''}".strip()


class RegistrationService:

    def __init__(
        self,
        repository: RegistrationRepository,
        event_repository: EventRepository,
        aforo_repository: AforoRepository
    ):
        self.repository = repository
        self.event_repository = event_repository
        self.aforo_repository = aforo_repository

    # ── DTO ─────────────────────────────────────────────────────────────

    async def _dtos(
        self,
        registrations: list[RegistrationModel],
        cupos_disponibles: int | None = None
    ) -> list[dict]:
        ids = {r.usuario_id for r in registrations} | {
            r.inscrito_por for r in registrations if r.inscrito_por
        }
        usuarios = await self.repository.usuarios_por_id(list(ids))

        def persona(usuario_id: UUID | None) -> dict | None:
            usuario = usuarios.get(usuario_id) if usuario_id else None

            if not usuario:
                return None

            return {
                "id": usuario.id,
                "nombre_completo": _nombre_completo(usuario),
                "correo": usuario.correo,
            }

        return [
            {
                "id": r.id,
                "usuario_id": r.usuario_id,
                "evento_id": r.evento_id,
                "fecha_inscripcion": r.fecha_inscripcion,
                "inscrito_por": r.inscrito_por,
                "nota": r.nota,
                "usuario": persona(r.usuario_id),
                "inscrito_por_usuario": persona(r.inscrito_por),
                "cupos_disponibles": cupos_disponibles,
            }
            for r in registrations
        ]

    # ── Consultas ───────────────────────────────────────────────────────

    async def get_all(
        self,
        limit: int,
        offset: int,
        evento_id: UUID | None = None
    ):
        if evento_id is not None:
            registrations = await self.repository.get_by_event_id(
                evento_id=evento_id,
                limit=limit,
                offset=offset
            )
        else:
            registrations = await self.repository.get_all(
                limit=limit,
                offset=offset
            )

        return await self._dtos(list(registrations))

    async def count(
        self,
        evento_id: UUID | None = None
    ) -> int:
        if evento_id is not None:
            return await self.repository.count_by_event_id(
                evento_id
            )

        return await self.repository.count()

    async def get_my_registrations(
        self,
        user_id: UUID,
        limit: int,
        offset: int
    ):
        registrations = await self.repository.get_by_user_id(
            usuario_id=user_id,
            limit=limit,
            offset=offset
        )

        return await self._dtos(list(registrations))

    async def count_my_registrations(
        self,
        user_id: UUID
    ) -> int:
        return await self.repository.count_by_user_id(
            user_id
        )

    async def get_by_id(
        self,
        registration_id: UUID,
        current_user: UserModel
    ):
        registration = await self._get_own_or_admin(
            registration_id,
            current_user
        )

        return (await self._dtos([registration]))[0]

    # ── Escrituras ──────────────────────────────────────────────────────

    async def create(
        self,
        evento_id: UUID,
        current_user: UserModel,
        usuario_id: UUID | None = None,
        nota: str | None = None
    ):
        """
        Inscribe al usuario autenticado o, si es administrador, a la persona
        indicada en `usuario_id`.
        """
        por_otro = usuario_id is not None and usuario_id != current_user.id
        es_admin = current_user.rol == UserRole.ADMIN

        if not es_admin and (por_otro or nota is not None):
            raise ForbiddenRegistrationAccessError(
                "Solo un administrador puede inscribir a otra persona o "
                "agregar una nota"
            )

        destino_id = usuario_id or current_user.id

        try:
            # Bloquea la fila del evento hasta el commit: cualquier otra
            # inscripción o asignación de participante al mismo evento espera
            # aquí, cerrando la carrera tanto del cupo como del duplicado.
            event = await self.event_repository.get_by_id_for_update(
                evento_id
            )

            if not event:
                raise EventNotFoundError(
                    "Evento no encontrado"
                )

            if por_otro:
                usuarios = await self.repository.usuarios_por_id([destino_id])
                destino = usuarios.get(destino_id)

                if not destino or destino.activo is not True:
                    raise UserNotFoundError(
                        "El usuario no existe o está inactivo"
                    )

            if registration_closed(event, es_admin):
                raise RegistrationClosedError(
                    "Las inscripciones de este evento están cerradas"
                    if started(event)
                    else "La fecha límite para inscribirse a este evento ya pasó"
                )

            if await self.aforo_repository.es_participante(destino_id, evento_id):
                raise ParticipantRegistrationError(
                    "Participa en el evento: ya tiene su lugar y no necesita "
                    "inscribirse"
                )

            existing = await self.repository.get_by_user_and_event(
                usuario_id=destino_id,
                evento_id=evento_id
            )

            if existing:
                raise DuplicateRegistrationError(
                    "El usuario ya está inscrito en este evento"
                )

            ocupacion = (
                await self.aforo_repository.ocupacion(
                    {event.id: event.capacidad}
                )
            )[event.id]

            if ocupacion.disponibles <= 0:
                raise EventFullError(
                    "El evento no tiene cupos disponibles"
                )

        except Exception:
            # Libera el bloqueo del evento.
            await self.repository.rollback()
            raise

        registration = RegistrationModel(
            id=uuid4(),
            usuario_id=destino_id,
            evento_id=evento_id,
            fecha_inscripcion=datetime.now(UTC),
            inscrito_por=current_user.id if por_otro else None,
            nota=(nota or "").strip() or None
        )

        try:
            created = await self.repository.create(
                registration
            )

        except IntegrityError:
            raise DuplicateRegistrationError(
                "El usuario ya está inscrito en este evento"
            )

        return (
            await self._dtos(
                [created],
                cupos_disponibles=ocupacion.disponibles - 1
            )
        )[0]

    async def update_note(
        self,
        registration_id: UUID,
        nota: str | None
    ):
        registration = await self.repository.get_by_id(
            registration_id
        )

        if not registration:
            raise RegistrationNotFoundError(
                "Inscripción no encontrada"
            )

        registration.nota = (nota or "").strip() or None

        updated = await self.repository.update(
            registration
        )

        return (await self._dtos([updated]))[0]

    async def delete(
        self,
        registration_id: UUID,
        current_user: UserModel
    ):
        registration = await self._get_own_or_admin(
            registration_id,
            current_user
        )

        if current_user.rol != UserRole.ADMIN:
            event = await self.event_repository.get_by_id(
                registration.evento_id
            )

            if event and started(event):
                raise CancellationClosedError(
                    "El evento ya empezó: la inscripción no se puede cancelar"
                )

            if event and cancellation_closed(event, es_admin=False):
                raise CancellationClosedError(
                    "El plazo para cancelar la inscripción a este evento ya terminó"
                )

        await self.repository.delete(
            registration
        )

    async def _get_own_or_admin(
        self,
        registration_id: UUID,
        current_user: UserModel
    ) -> RegistrationModel:
        registration = await self.repository.get_by_id(
            registration_id
        )

        if not registration:
            raise RegistrationNotFoundError(
                "Inscripción no encontrada"
            )

        if (
            current_user.rol != UserRole.ADMIN
            and current_user.id != registration.usuario_id
        ):
            raise ForbiddenRegistrationAccessError(
                "No tiene permisos para acceder a esta inscripción"
            )

        return registration
