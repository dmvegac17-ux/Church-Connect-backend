from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants.enums import EstadoRespuestaInvitacion
from src.infrastructure.database.models.event_model import EventModel
from src.infrastructure.database.models.cambio_cronograma_model import (
    CambioCronogramaModel,
)
from src.infrastructure.database.models.invitacion_participacion_model import (
    InvitacionParticipacionModel,
)
from src.infrastructure.database.models.notificaciones_model import NotificacionesModel
from src.infrastructure.database.models.schedule_model import ScheduleModel
from src.infrastructure.database.models.user_model import UserModel

# Una actividad eliminada queda cancelada: no forma parte del cronograma.
VIGENTE = ScheduleModel.cancelada_en.is_(None)


class ScheduleRepository:

    def __init__(
        self,
        db: AsyncSession
    ):
        self.db = db

    async def get_all(
        self,
        limit: int,
        offset: int
    ):
        query = (
            select(ScheduleModel)
            .where(VIGENTE)
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def count(
        self,
        evento_id: UUID | None = None
    ) -> int:
        query = select(func.count()).select_from(
            ScheduleModel
        ).where(VIGENTE)

        if evento_id is not None:
            query = query.where(
                ScheduleModel.evento_id == evento_id
            )

        result = await self.db.execute(query)

        return result.scalar_one()

    async def get_by_id(
        self,
        schedule_id: UUID
    ):
        query = select(ScheduleModel).where(
            ScheduleModel.id == schedule_id,
            VIGENTE
        )

        result = await self.db.execute(query)

        return result.scalar_one_or_none()

    async def get_by_evento_id(
        self,
        evento_id: UUID
    ):
        query = select(ScheduleModel).where(
            ScheduleModel.evento_id == evento_id,
            VIGENTE
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    async def count_by_evento_ids(
        self,
        evento_ids: list[UUID]
    ) -> dict[UUID, int]:
        if not evento_ids:
            return {}

        query = (
            select(
                ScheduleModel.evento_id,
                func.count()
            )
            .where(ScheduleModel.evento_id.in_(evento_ids), VIGENTE)
            .group_by(ScheduleModel.evento_id)
        )

        result = await self.db.execute(query)

        return dict(result.all())

    async def create(
        self,
        schedule: ScheduleModel
    ):
        self.db.add(schedule)

        await self.db.commit()

        await self.db.refresh(schedule)

        return schedule

    async def update(
        self,
        schedule: ScheduleModel
    ):
        await self.db.commit()

        await self.db.refresh(schedule)

        return schedule

    async def delete(
        self,
        schedule: ScheduleModel
    ):
        await self.db.delete(schedule)

        await self.db.commit()

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()

    def add(self, entidad) -> None:
        self.db.add(entidad)

    async def flush(self) -> None:
        await self.db.flush()

    async def refresh(self, entidad) -> None:
        await self.db.refresh(entidad)

    async def invitacion_activa(self, actividad_id: UUID):
        """La invitación pendiente o aceptada de la actividad y su participante."""
        result = await self.db.execute(
            select(InvitacionParticipacionModel, UserModel)
            .join(
                UserModel,
                UserModel.id == InvitacionParticipacionModel.participante_id
            )
            .where(
                InvitacionParticipacionModel.actividad_id == actividad_id,
                InvitacionParticipacionModel.estado_respuesta.in_((
                    EstadoRespuestaInvitacion.PENDIENTE.value,
                    EstadoRespuestaInvitacion.ACEPTADA.value,
                ))
            )
        )

        return result.first()

    async def get_notificacion(self, notificacion_id: UUID):
        return await self.db.get(NotificacionesModel, notificacion_id)

    async def historial(self, evento_id: UUID):
        result = await self.db.execute(
            select(CambioCronogramaModel)
            .where(CambioCronogramaModel.evento_id == evento_id)
            .order_by(CambioCronogramaModel.fecha.desc())
        )

        return result.scalars().all()

    async def eventos_con_cronograma(self):
        """
        Todos los eventos con sus actividades vigentes y la invitación más
        reciente de cada una. Tres consultas en total, sin importar cuántos
        eventos o actividades haya.
        """
        eventos = (
            await self.db.execute(
                select(EventModel).order_by(EventModel.fecha_inicio.asc())
            )
        ).scalars().all()

        actividades = (
            await self.db.execute(
                select(ScheduleModel)
                .where(VIGENTE)
                .order_by(ScheduleModel.hora_inicio.asc())
            )
        ).scalars().all()

        invitaciones = (
            await self.db.execute(
                select(InvitacionParticipacionModel)
                .join(
                    ScheduleModel,
                    ScheduleModel.id == InvitacionParticipacionModel.actividad_id
                )
                .where(VIGENTE)
                .order_by(InvitacionParticipacionModel.created_at.asc())
            )
        ).scalars().all()

        # La última de cada actividad pisa a las anteriores.
        ultima = {inv.actividad_id: inv for inv in invitaciones}

        return eventos, actividades, ultima

    async def estados_de_invitacion(self, actividad_ids: list[UUID]) -> dict[UUID, str]:
        """Estado de la invitación activa (pendiente o aceptada) de cada actividad."""
        if not actividad_ids:
            return {}

        result = await self.db.execute(
            select(
                InvitacionParticipacionModel.actividad_id,
                InvitacionParticipacionModel.estado_respuesta
            ).where(
                InvitacionParticipacionModel.actividad_id.in_(actividad_ids),
                InvitacionParticipacionModel.estado_respuesta.in_((
                    EstadoRespuestaInvitacion.PENDIENTE.value,
                    EstadoRespuestaInvitacion.ACEPTADA.value,
                ))
            )
        )

        return dict(result.all())

    async def contexto_de_estado(self, schedules):
        """
        Lo necesario para saber en qué está cada actividad: su evento y su
        invitación más reciente. Dos consultas para toda la lista.
        """
        if not schedules:
            return {}, {}

        eventos = (
            await self.db.execute(
                select(EventModel).where(
                    EventModel.id.in_({schedule.evento_id for schedule in schedules})
                )
            )
        ).scalars().all()

        invitaciones = (
            await self.db.execute(
                select(InvitacionParticipacionModel)
                .where(
                    InvitacionParticipacionModel.actividad_id.in_(
                        [schedule.id for schedule in schedules]
                    )
                )
                .order_by(InvitacionParticipacionModel.created_at.asc())
            )
        ).scalars().all()

        return (
            {evento.id: evento for evento in eventos},
            # La última de cada actividad pisa a las anteriores.
            {invitacion.actividad_id: invitacion for invitacion in invitaciones},
        )
