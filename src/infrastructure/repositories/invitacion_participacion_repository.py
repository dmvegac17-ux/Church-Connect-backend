from datetime import datetime
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy import case
from sqlalchemy import exists
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.core.constants.enums import EstadoEnvioInvitacion
from src.core.constants.enums import EstadoRespuestaInvitacion
from src.core.constants.enums import UserRole
from src.infrastructure.database.models.event_model import EventModel
from src.infrastructure.database.models.invitacion_participacion_model import (
    InvitacionParticipacionModel,
)
from src.infrastructure.database.models.ministry_model import MinistryModel
from src.infrastructure.database.models.schedule_model import ScheduleModel
from src.infrastructure.database.models.user_ministry_model import UserMinistryModel
from src.infrastructure.database.models.user_model import UserModel

Inv = InvitacionParticipacionModel

ESTADOS_ACTIVOS = (
    EstadoRespuestaInvitacion.PENDIENTE.value,
    EstadoRespuestaInvitacion.ACEPTADA.value,
)

# Estados que dejan la actividad sin persona asignada.
ESTADOS_LIBERADOS = (
    EstadoRespuestaInvitacion.RECHAZADA.value,
    EstadoRespuestaInvitacion.VENCIDA.value,
    EstadoRespuestaInvitacion.CANCELADA.value,
)

_ACENTOS = (
    ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ü", "u"),
    ("Á", "a"), ("É", "e"), ("Í", "i"), ("Ó", "o"), ("Ú", "u"), ("Ü", "u"),
)


def _sin_tildes(columna):
    """
    Minúsculas y sin tildes en SQL, con funciones que existen en cualquier
    motor (no depende de la extensión `unaccent`).
    """
    expresion = columna

    for con_tilde, sin_tilde in _ACENTOS:
        expresion = func.replace(expresion, con_tilde, sin_tilde)

    return func.lower(expresion)


class InvitacionParticipacionRepository:

    def __init__(
        self,
        db: AsyncSession
    ):
        self.db = db

    # ── Transacción ─────────────────────────────────────────────────────

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()

    async def flush(self) -> None:
        await self.db.flush()

    def add(self, entidad) -> None:
        self.db.add(entidad)

    # ── Expresiones derivadas ───────────────────────────────────────────

    @staticmethod
    def requiere_reasignacion(limite_inicio: datetime):
        """
        Invitación liberada, sin reemplazo y con plazo todavía para pedir una
        nueva confirmación (`limite_inicio` = primer instante en que una
        actividad aún admite reasignación).
        """
        reemplazo = aliased(Inv)

        return and_(
            Inv.estado_respuesta.in_(ESTADOS_LIBERADOS),
            ~exists().where(reemplazo.reemplaza_invitacion_id == Inv.id),
            ScheduleModel.hora_inicio >= limite_inicio
        )

    @staticmethod
    def _filtro_busqueda(q: str | None):
        if not q:
            return None

        patron = f"%{q}%"

        return or_(
            _sin_tildes(ScheduleModel.actividad).like(patron),
            _sin_tildes(EventModel.titulo).like(patron),
            _sin_tildes(
                UserModel.nombre + " " + func.coalesce(UserModel.apellido, "")
            ).like(patron)
        )

    def _condicion_filtro(self, filtro: str, limite_inicio: datetime):
        if filtro == "pendientes":
            return Inv.estado_respuesta == EstadoRespuestaInvitacion.PENDIENTE.value

        if filtro == "aceptadas":
            return Inv.estado_respuesta == EstadoRespuestaInvitacion.ACEPTADA.value

        if filtro == "por_reasignar":
            return self.requiere_reasignacion(limite_inicio)

        if filtro == "error_envio":
            return Inv.estado_envio == EstadoEnvioInvitacion.ERROR.value

        return None

    @staticmethod
    def _detalle():
        """Invitación + actividad + evento + participante."""
        return (
            select(Inv, ScheduleModel, EventModel, UserModel)
            .join(ScheduleModel, ScheduleModel.id == Inv.actividad_id)
            .join(EventModel, EventModel.id == ScheduleModel.evento_id)
            .join(UserModel, UserModel.id == Inv.participante_id)
            # Los cambios de estado van por UPDATE directo: al releer se
            # descarta lo que la sesión tuviera en memoria.
            .execution_options(populate_existing=True)
        )

    # ── Lecturas ────────────────────────────────────────────────────────

    async def get_by_id(self, invitacion_id: UUID):
        result = await self.db.execute(
            select(Inv)
            .where(Inv.id == invitacion_id)
            .execution_options(populate_existing=True)
        )

        return result.scalar_one_or_none()

    async def get_detalle(self, invitacion_id: UUID):
        result = await self.db.execute(
            self._detalle()
            .where(Inv.id == invitacion_id)
            .execution_options(populate_existing=True)
        )

        return result.first()

    async def listar_de_participante(self, participante_id: UUID):
        result = await self.db.execute(
            self._detalle().where(Inv.participante_id == participante_id)
        )

        return result.all()

    async def listar_admin(
        self,
        filtro: str,
        q: str | None,
        limite_inicio: datetime,
        limit: int,
        offset: int
    ):
        query = self._detalle()

        for condicion in (
            self._condicion_filtro(filtro, limite_inicio),
            self._filtro_busqueda(q)
        ):
            if condicion is not None:
                query = query.where(condicion)

        query = (
            query
            .order_by(ScheduleModel.hora_inicio.asc(), Inv.created_at.asc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)

        return result.all()

    async def conteos_admin(
        self,
        q: str | None,
        limite_inicio: datetime
    ) -> dict[str, int]:
        def contar(filtro: str):
            return func.coalesce(
                func.sum(
                    case(
                        (self._condicion_filtro(filtro, limite_inicio), 1),
                        else_=0
                    )
                ),
                0
            )

        query = (
            select(
                func.count(),
                contar("pendientes"),
                contar("aceptadas"),
                contar("por_reasignar"),
                contar("error_envio")
            )
            .select_from(Inv)
            .join(ScheduleModel, ScheduleModel.id == Inv.actividad_id)
            .join(EventModel, EventModel.id == ScheduleModel.evento_id)
            .join(UserModel, UserModel.id == Inv.participante_id)
        )

        busqueda = self._filtro_busqueda(q)
        if busqueda is not None:
            query = query.where(busqueda)

        todas, pendientes, aceptadas, por_reasignar, error_envio = (
            await self.db.execute(query)
        ).one()

        return {
            "todas": int(todas),
            "pendientes": int(pendientes),
            "aceptadas": int(aceptadas),
            "por_reasignar": int(por_reasignar),
            "error_envio": int(error_envio),
        }

    async def reemplazos_de(self, invitacion_ids: list[UUID]):
        """Invitación que reemplazó a cada una de las indicadas."""
        if not invitacion_ids:
            return {}

        result = await self.db.execute(
            select(Inv, UserModel)
            .join(UserModel, UserModel.id == Inv.participante_id)
            .where(Inv.reemplaza_invitacion_id.in_(invitacion_ids))
            .execution_options(populate_existing=True)
        )

        return {
            invitacion.reemplaza_invitacion_id: (invitacion, usuario)
            for invitacion, usuario in result.all()
        }

    async def get_activa_de_actividad(self, actividad_id: UUID):
        result = await self.db.execute(
            select(Inv).where(
                Inv.actividad_id == actividad_id,
                Inv.estado_respuesta.in_(ESTADOS_ACTIVOS)
            )
        )

        return result.scalar_one_or_none()

    async def ultimas_por_actividad(self, actividad_ids: list[UUID]):
        """
        La invitación vigente de cada actividad: la activa o, si no hay, la
        liberada que todavía no tiene reemplazo.
        """
        if not actividad_ids:
            return []

        reemplazo = aliased(Inv)

        result = await self.db.execute(
            self._detalle()
            .where(
                Inv.actividad_id.in_(actividad_ids),
                or_(
                    Inv.estado_respuesta.in_(ESTADOS_ACTIVOS),
                    and_(
                        Inv.estado_respuesta.in_(ESTADOS_LIBERADOS),
                        ~exists().where(
                            reemplazo.reemplaza_invitacion_id == Inv.id
                        )
                    )
                )
            )
            .order_by(Inv.created_at.asc())
        )

        return result.all()

    async def liberadas_sin_reemplazo(self, actividad_id: UUID):
        reemplazo = aliased(Inv)

        result = await self.db.execute(
            select(Inv)
            .where(
                Inv.actividad_id == actividad_id,
                Inv.estado_respuesta.in_(ESTADOS_LIBERADOS),
                ~exists().where(reemplazo.reemplaza_invitacion_id == Inv.id)
            )
            .order_by(Inv.created_at.desc())
            .execution_options(populate_existing=True)
        )

        return result.scalars().all()

    async def get_actividad(self, actividad_id: UUID):
        result = await self.db.execute(
            select(ScheduleModel, EventModel)
            .join(EventModel, EventModel.id == ScheduleModel.evento_id)
            .where(ScheduleModel.id == actividad_id)
        )

        return result.first()

    async def actividades_de_evento(self, evento_id: UUID) -> list[UUID]:
        result = await self.db.execute(
            select(ScheduleModel.id).where(ScheduleModel.evento_id == evento_id)
        )

        return list(result.scalars().all())

    async def areas_de_usuarios(self, usuario_ids: list[UUID]) -> dict[UUID, str]:
        """Primer ministerio (por nombre) de cada usuario."""
        if not usuario_ids:
            return {}

        result = await self.db.execute(
            select(UserMinistryModel.usuario_id, MinistryModel.nombre)
            .join(MinistryModel, MinistryModel.id == UserMinistryModel.ministerio_id)
            .where(UserMinistryModel.usuario_id.in_(usuario_ids))
            .order_by(MinistryModel.nombre.asc())
        )

        areas: dict[UUID, str] = {}
        for usuario_id, nombre in result.all():
            areas.setdefault(usuario_id, nombre)

        return areas

    async def usuarios_por_id(self, usuario_ids: list[UUID]) -> dict[UUID, UserModel]:
        if not usuario_ids:
            return {}

        result = await self.db.execute(
            select(UserModel).where(UserModel.id.in_(usuario_ids))
        )

        return {usuario.id: usuario for usuario in result.scalars().all()}

    async def usuarios_invitables(self, q: str | None, limit: int):
        """Usuarios activos que pueden recibir invitaciones (no administradores)."""
        query = select(UserModel).where(
            UserModel.activo.is_(True),
            UserModel.rol.in_([UserRole.MEMBER, UserRole.PARTICIPANT])
        )

        if q:
            patron = f"%{q}%"
            query = query.where(
                or_(
                    _sin_tildes(
                        UserModel.nombre + " " + func.coalesce(UserModel.apellido, "")
                    ).like(patron),
                    func.lower(UserModel.correo).like(patron)
                )
            )

        result = await self.db.execute(
            query.order_by(UserModel.nombre.asc(), UserModel.apellido.asc()).limit(limit)
        )

        return result.scalars().all()

    async def participantes_con_cruce(
        self,
        actividad_id: UUID,
        hora_inicio: datetime,
        hora_fin: datetime
    ) -> set[UUID]:
        """Quiénes tienen otra actividad activa que se cruza con ese horario."""
        result = await self.db.execute(
            select(Inv.participante_id)
            .join(ScheduleModel, ScheduleModel.id == Inv.actividad_id)
            .where(
                Inv.actividad_id != actividad_id,
                Inv.estado_respuesta.in_(ESTADOS_ACTIVOS),
                ScheduleModel.hora_inicio < hora_fin,
                ScheduleModel.hora_fin > hora_inicio
            )
        )

        return set(result.scalars().all())

    # ── Escrituras ──────────────────────────────────────────────────────

    async def transicionar(
        self,
        invitacion_id: UUID,
        desde: tuple[str, ...],
        valores: dict
    ) -> bool:
        """
        Cambia de estado solo si la invitación sigue en uno de los estados
        `desde`. La comparación va en el propio UPDATE, así que de dos
        peticiones simultáneas solo una encuentra la fila.
        """
        result = await self.db.execute(
            update(Inv)
            .where(
                Inv.id == invitacion_id,
                Inv.estado_respuesta.in_(desde)
            )
            .values(**valores)
            .execution_options(synchronize_session=False)
        )

        return result.rowcount == 1

    async def vencer_pendientes(self, ahora: datetime) -> int:
        result = await self.db.execute(
            update(Inv)
            .where(
                Inv.estado_respuesta == EstadoRespuestaInvitacion.PENDIENTE.value,
                Inv.fecha_limite_respuesta.is_not(None),
                Inv.fecha_limite_respuesta < ahora
            )
            .values(
                estado_respuesta=EstadoRespuestaInvitacion.VENCIDA.value,
                updated_at=ahora
            )
            .execution_options(synchronize_session=False)
        )

        return result.rowcount

    async def liberar_responsables_sin_invitacion_activa(self) -> None:
        """
        `cronogramas.responsable_id` refleja la invitación activa: se limpia
        en las actividades que tuvieron invitaciones y ya no tienen una activa.
        """
        con_invitaciones = select(Inv.actividad_id)
        con_activa = select(Inv.actividad_id).where(
            Inv.estado_respuesta.in_(ESTADOS_ACTIVOS)
        )

        await self.db.execute(
            update(ScheduleModel)
            .where(
                ScheduleModel.responsable_id.is_not(None),
                ScheduleModel.id.in_(con_invitaciones),
                ScheduleModel.id.not_in(con_activa)
            )
            .values(responsable_id=None)
            .execution_options(synchronize_session=False)
        )

    async def asignar_responsable(
        self,
        actividad_id: UUID,
        responsable_id: UUID | None,
        responsable: str | None = None
    ) -> None:
        valores: dict = {"responsable_id": responsable_id}

        if responsable is not None:
            valores["responsable"] = responsable

        await self.db.execute(
            update(ScheduleModel)
            .where(ScheduleModel.id == actividad_id)
            .values(**valores)
            .execution_options(synchronize_session=False)
        )
