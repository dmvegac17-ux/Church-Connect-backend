from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.invitacion_participacion_model import (
    InvitacionParticipacionModel,
)
from src.infrastructure.database.models.registration_model import RegistrationModel
from src.infrastructure.database.models.schedule_model import ScheduleModel
from src.infrastructure.repositories.invitacion_participacion_repository import (
    ESTADOS_ACTIVOS,
)


@dataclass(frozen=True)
class Ocupacion:
    """
    Quién ocupa el aforo de un evento.

    - `participantes`: personas distintas asignadas a alguna actividad. Cada
      una cuenta una vez aunque tenga varias actividades, y ocupa su lugar
      desde que se le invita (pendiente o aceptada).
    - `publico`: inscripciones.
    """

    capacidad: int
    participantes: int
    publico: int

    @property
    def ocupados(self) -> int:
        return self.participantes + self.publico

    @property
    def cupo_publico(self) -> int:
        return max(0, self.capacidad - self.participantes)

    @property
    def disponibles(self) -> int:
        """Negativo cuando hay sobrecupo."""
        return self.capacidad - self.ocupados

    @property
    def sobrecupo(self) -> int:
        return max(0, -self.disponibles)


class AforoRepository:

    def __init__(
        self,
        db: AsyncSession
    ):
        self.db = db

    async def participantes_por_evento(
        self,
        evento_ids: list[UUID]
    ) -> dict[UUID, int]:
        if not evento_ids:
            return {}

        # `cronogramas.responsable_id` refleja la invitación activa de cada
        # actividad (ver `ParticipacionService`).
        result = await self.db.execute(
            select(
                ScheduleModel.evento_id,
                func.count(func.distinct(ScheduleModel.responsable_id))
            )
            .where(
                ScheduleModel.evento_id.in_(evento_ids),
                ScheduleModel.responsable_id.is_not(None)
            )
            .group_by(ScheduleModel.evento_id)
        )

        return dict(result.all())

    async def publico_por_evento(
        self,
        evento_ids: list[UUID]
    ) -> dict[UUID, int]:
        if not evento_ids:
            return {}

        result = await self.db.execute(
            select(
                RegistrationModel.evento_id,
                func.count()
            )
            .where(RegistrationModel.evento_id.in_(evento_ids))
            .group_by(RegistrationModel.evento_id)
        )

        return dict(result.all())

    async def ocupacion(
        self,
        capacidades: dict[UUID, int]
    ) -> dict[UUID, Ocupacion]:
        ids = list(capacidades)
        participantes = await self.participantes_por_evento(ids)
        publico = await self.publico_por_evento(ids)

        return {
            evento_id: Ocupacion(
                capacidad=capacidad,
                participantes=participantes.get(evento_id, 0),
                publico=publico.get(evento_id, 0)
            )
            for evento_id, capacidad in capacidades.items()
        }

    async def es_participante(
        self,
        usuario_id: UUID,
        evento_id: UUID
    ) -> bool:
        return evento_id in await self.eventos_donde_participa(
            usuario_id,
            [evento_id]
        )

    async def eventos_donde_participa(
        self,
        usuario_id: UUID,
        evento_ids: list[UUID]
    ) -> set[UUID]:
        if not evento_ids:
            return set()

        result = await self.db.execute(
            select(ScheduleModel.evento_id)
            .where(
                ScheduleModel.evento_id.in_(evento_ids),
                ScheduleModel.responsable_id == usuario_id
            )
            .distinct()
        )

        return set(result.scalars().all())

    async def inscripciones_de(
        self,
        usuario_id: UUID,
        evento_ids: list[UUID]
    ) -> dict[UUID, UUID]:
        """Inscripción del usuario en cada evento: `evento_id → inscripcion_id`."""
        if not evento_ids:
            return {}

        result = await self.db.execute(
            select(RegistrationModel.evento_id, RegistrationModel.id)
            .where(
                RegistrationModel.usuario_id == usuario_id,
                RegistrationModel.evento_id.in_(evento_ids)
            )
        )

        return dict(result.all())

    async def eventos_con_inscripcion_reemplazada(
        self,
        usuario_id: UUID,
        evento_ids: list[UUID]
    ) -> set[UUID]:
        """Eventos donde su participación vigente reemplazó una inscripción."""
        if not evento_ids:
            return set()

        Inv = InvitacionParticipacionModel

        result = await self.db.execute(
            select(ScheduleModel.evento_id)
            .join(Inv, Inv.actividad_id == ScheduleModel.id)
            .where(
                ScheduleModel.evento_id.in_(evento_ids),
                Inv.participante_id == usuario_id,
                Inv.estado_respuesta.in_(ESTADOS_ACTIVOS),
                Inv.reemplazo_inscripcion.is_(True)
            )
            .distinct()
        )

        return set(result.scalars().all())
