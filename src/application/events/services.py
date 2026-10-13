from datetime import UTC
from datetime import datetime
from datetime import timedelta
from uuid import UUID
from uuid import uuid4

from src.api.v1.events.schemas import EventCreate
from src.api.v1.events.schemas import EventUpdate
from src.application.events.date_change import EventChangeEmail
from src.application.events.date_change import EventSnapshot
from src.application.events.date_change import event_change_notice
from src.application.events.registration_window import cancellation_closed
from src.application.events.registration_window import cancellation_deadline
from src.application.events.registration_window import days_until_event
from src.application.events.registration_window import deadline_before_today
from src.application.events.registration_window import registration_closed
from src.application.schedules.services import ScheduleService
from src.core.constants.enums import UserRole
from src.core.exceptions.custom_exceptions import EventoFinalizadoError
from src.core.exceptions.custom_exceptions import VersionDesactualizadaError
from src.core.exceptions.custom_exceptions import evento_finalizado
from src.infrastructure.database.models.event_model import EventModel
from src.infrastructure.database.models.notificaciones_model import NotificacionesModel
from src.infrastructure.database.models.user_model import UserModel
from src.infrastructure.email.email_service import email_service
from src.infrastructure.repositories.aforo_repository import AforoRepository
from src.infrastructure.repositories.aforo_repository import Ocupacion
from src.infrastructure.repositories.event_repository import EventRepository
from src.infrastructure.repositories.schedule_repository import ScheduleRepository


# Margen para aceptar un inicio «de ahora»: el reloj corre mientras se guarda.
MARGEN_INICIO = timedelta(minutes=5)


class InvalidEventDateRangeError(Exception):
    pass


class InvalidEventLocationError(Exception):
    pass


class InvalidRegistrationDeadlineError(Exception):
    pass


class EventCapacityBelowOccupiedError(Exception):
    """El aforo no puede quedar por debajo de los lugares ya ocupados."""

    def __init__(self, ocupados: int):
        self.ocupados = ocupados
        super().__init__(
            f"Hay {ocupados} lugares ocupados. El aforo no puede ser menor."
        )


def _utc(valor: datetime) -> datetime:
    return valor.replace(tzinfo=UTC) if valor.tzinfo is None else valor


class EventService:

    def __init__(
        self,
        repository: EventRepository,
        schedule_repository: ScheduleRepository,
        aforo_repository: AforoRepository
    ):
        self.repository = repository
        self.schedule_repository = schedule_repository
        self.aforo_repository = aforo_repository

    async def _dtos(
        self,
        events: list[EventModel],
        user: UserModel
    ) -> list[dict]:
        """
        Eventos con su aforo. Se arma un dict en vez de tocar el modelo: al
        miembro se le entrega su cupo como `capacidad`, y ese valor nunca debe
        llegar a la fila del evento.
        """
        ids = [event.id for event in events]
        es_admin = user.rol == UserRole.ADMIN

        actividades = await self.schedule_repository.count_by_evento_ids(ids)
        ocupaciones = await self.aforo_repository.ocupacion(
            {event.id: event.capacidad for event in events}
        )
        participa = await self.aforo_repository.eventos_donde_participa(
            user.id, ids
        )
        inscripciones = await self.aforo_repository.inscripciones_de(
            user.id, ids
        )
        reemplazadas = (
            await self.aforo_repository.eventos_con_inscripcion_reemplazada(
                user.id, list(participa)
            )
        )
        ahora = datetime.now(UTC)

        return [
            self._dto(
                event,
                ocupaciones[event.id],
                es_admin,
                total_actividades=actividades.get(event.id, 0),
                participa=event.id in participa,
                inscripcion_id=inscripciones.get(event.id),
                reemplazada=event.id in reemplazadas,
                cerradas=registration_closed(event, es_admin, ahora),
                sin_cancelar=cancellation_closed(event, es_admin, ahora)
            )
            for event in events
        ]

    @staticmethod
    def _dto(
        event: EventModel,
        ocupacion: Ocupacion,
        es_admin: bool,
        total_actividades: int,
        participa: bool,
        inscripcion_id: UUID | None,
        reemplazada: bool,
        cerradas: bool,
        sin_cancelar: bool
    ) -> dict:
        aforo = {
            "cupo_publico": ocupacion.cupo_publico,
            "disponibles": max(0, ocupacion.disponibles),
            "inscrito": inscripcion_id is not None,
            "inscripcion_id": inscripcion_id,
            "participa": participa,
            "inscripcion_reemplazada": reemplazada,
            "inscripciones_cerradas": cerradas,
            "cancelacion_cerrada": sin_cancelar,
        }

        if es_admin:
            aforo.update(
                participantes=ocupacion.participantes,
                publico=ocupacion.publico,
                ocupados=ocupacion.ocupados,
                sobrecupo=ocupacion.sobrecupo
            )

        return {
            "id": event.id,
            "titulo": event.titulo,
            "descripcion": event.descripcion,
            "fecha_inicio": event.fecha_inicio,
            "fecha_fin": event.fecha_fin,
            "lugar": event.lugar,
            "direccion": event.direccion,
            "latitud": event.latitud,
            "longitud": event.longitud,
            "capacidad": (
                event.capacidad if es_admin else ocupacion.cupo_publico
            ),
            "fecha_limite_inscripcion": event.fecha_limite_inscripcion,
            "dias_limite_cancelacion": event.dias_limite_cancelacion,
            "fecha_limite_cancelacion": cancellation_deadline(event),
            "creado_por": event.creado_por,
            "version": event.version or 1,
            "total_actividades": total_actividades,
            "aforo": aforo,
        }

    async def get_all(
        self,
        limit: int,
        offset: int,
        user: UserModel
    ):
        events = await self.repository.get_all(
            limit=limit,
            offset=offset
        )

        return await self._dtos(
            list(events),
            user
        )

    async def count(self) -> int:
        return await self.repository.count()

    async def get_by_id(
        self,
        event_id: UUID,
        user: UserModel
    ):
        event = await self.repository.get_by_id(
            event_id
        )

        if not event:
            raise ValueError(
                "Evento no encontrado"
            )

        return (await self._dtos([event], user))[0]

    def _validate(
        self,
        event: EventModel
    ) -> None:
        # Al cambiar solo una, la otra puede venir de la base sin zona horaria.
        if _utc(event.fecha_fin) <= _utc(event.fecha_inicio):
            raise InvalidEventDateRangeError(
                "La fecha/hora de fin debe ser posterior a la "
                "fecha/hora de inicio"
            )

        has_lat = event.latitud is not None
        has_lng = event.longitud is not None
        if has_lat != has_lng:
            raise InvalidEventLocationError(
                "latitud y longitud deben enviarse juntas o no enviarse"
            )

        # También al mover el evento: la fecha límite no puede quedar después
        # de su nuevo inicio.
        if event.fecha_limite_inscripcion is not None and (
            _utc(event.fecha_limite_inscripcion) > _utc(event.fecha_inicio)
        ):
            raise InvalidRegistrationDeadlineError(
                "La fecha límite de inscripción no puede ser posterior al "
                "inicio del evento"
            )

    @staticmethod
    def _validate_not_past(event: EventModel) -> None:
        # Con unos minutos de margen: el formulario no ofrece horas que ya
        # pasaron, pero entre elegir la hora y guardar corre el reloj.
        if _utc(event.fecha_inicio) < datetime.now(UTC) - MARGEN_INICIO:
            raise InvalidEventDateRangeError(
                "La fecha y hora de inicio no pueden estar en el pasado"
            )

    @staticmethod
    def _validate_limits(
        event: EventModel,
        limite_cambio: bool,
        dias_cambio: bool
    ) -> None:
        """
        Los límites se eligen entre hoy y el día del evento.

        Solo se revisa lo que se está cambiando: un evento cuya fecha límite
        ya pasó (las inscripciones cerraron) se puede seguir editando sin
        tener que tocarla.
        """
        if (
            limite_cambio
            and event.fecha_limite_inscripcion is not None
            and deadline_before_today(event.fecha_limite_inscripcion)
        ):
            raise InvalidRegistrationDeadlineError(
                "La fecha límite de inscripción no puede ser anterior a hoy"
            )

        if dias_cambio and event.dias_limite_cancelacion:
            disponibles = days_until_event(event.fecha_inicio)

            if event.dias_limite_cancelacion > disponibles:
                cuando = (
                    "El evento es hoy" if disponibles == 0
                    else "El evento es mañana" if disponibles == 1
                    else f"El evento es en {disponibles} días"
                )
                raise InvalidRegistrationDeadlineError(
                    f"{cuando}: los días límite para cancelar no pueden ser "
                    f"más de {disponibles}"
                )

    async def create(
        self,
        request: EventCreate,
        user: UserModel
    ):
        event = EventModel(
            id=uuid4(),
            titulo=request.titulo,
            descripcion=request.descripcion,
            fecha_inicio=request.fecha_inicio,
            fecha_fin=request.fecha_fin,
            lugar=request.lugar,
            direccion=request.direccion,
            latitud=request.latitud,
            longitud=request.longitud,
            capacidad=request.capacidad,
            fecha_limite_inscripcion=request.fecha_limite_inscripcion,
            dias_limite_cancelacion=request.dias_limite_cancelacion,
            creado_por=str(user.id)
        )

        self._validate(event)
        self._validate_not_past(event)
        self._validate_limits(event, limite_cambio=True, dias_cambio=True)

        created = await self.repository.create(
            event
        )

        return (await self._dtos([created], user))[0]

    async def update(
        self,
        event_id: UUID,
        request: EventUpdate,
        user: UserModel
    ) -> tuple[dict, list[EventChangeEmail]]:
        """
        Devuelve el evento actualizado y los correos de aviso a los inscritos
        si cambió la fecha, el horario, el lugar o la dirección. Se envían después de
        responder; el aviso en la aplicación queda guardado aquí mismo.
        """
        # Bloquea la fila: una inscripción simultánea espera aquí, así el
        # aforo nuevo se compara con la ocupación real.
        event = await self.repository.get_by_id_for_update(
            event_id
        )

        if not event:
            raise ValueError(
                "Evento no encontrado"
            )

        # Lo que pasó, pasó: cambiar la fecha, el lugar o el aforo de un
        # evento terminado falsearía el registro (y avisaría a sus inscritos
        # de un cambio que ya no les sirve). Uno en curso sí se puede editar.
        if evento_finalizado(event.fecha_fin):
            # Libera el bloqueo de la fila.
            await self.repository.rollback()
            raise EventoFinalizadoError()

        if request.version is not None and request.version != (event.version or 1):
            await self.repository.rollback()
            raise VersionDesactualizadaError()

        update_data = request.model_dump(
            exclude_unset=True,
            exclude={"version", "actividades"}
        )
        antes = self._snapshot(event)

        try:
            if "capacidad" in update_data:
                ocupacion = (
                    await self.aforo_repository.ocupacion(
                        {event.id: update_data["capacidad"]}
                    )
                )[event.id]

                if ocupacion.disponibles < 0 and (
                    update_data["capacidad"] < event.capacidad
                ):
                    raise EventCapacityBelowOccupiedError(ocupacion.ocupados)

            limite_antes = event.fecha_limite_inscripcion
            dias_antes = event.dias_limite_cancelacion

            for field, value in update_data.items():
                setattr(event, field, value)

            event.version = (event.version or 1) + 1

            self._validate(event)

            limite_cambio = (limite_antes is None) != (
                event.fecha_limite_inscripcion is None
            ) or (
                limite_antes is not None
                and event.fecha_limite_inscripcion is not None
                and _utc(limite_antes) != _utc(event.fecha_limite_inscripcion)
            )
            # Mover el evento cambia cuántos días quedan: los días límite
            # tienen que seguir cabiendo.
            inicio_cambio = _utc(antes.fecha_inicio) != _utc(event.fecha_inicio)
            # Solo al mover la fecha: un evento en curso se sigue editando.
            if inicio_cambio:
                self._validate_not_past(event)
            self._validate_limits(
                event,
                limite_cambio=limite_cambio,
                dias_cambio=(
                    dias_antes != event.dias_limite_cancelacion or inicio_cambio
                )
            )

            # El cronograma se acomoda en la misma transacción: si alguna
            # actividad queda fuera del horario nuevo, no se guarda nada.
            cronograma = ScheduleService(
                self.schedule_repository, self.repository, email_service
            )
            avisos_actividades: list[dict] = []
            rango_cambio = inicio_cambio or (
                _utc(antes.fecha_fin) != _utc(event.fecha_fin)
            )
            if rango_cambio or request.actividades:
                avisos_actividades = await cronograma.ajustar_con_evento(
                    event, request.actividades or [], user
                )

            # En la misma transacción que el cambio: o se guardan el evento
            # y los avisos, o ninguno.
            correos = await self._avisos_de_cambio(event, antes)

        except Exception:
            # Sin esto, el siguiente autoflush guardaría los cambios rechazados.
            await self.repository.rollback()
            raise

        updated = await self.repository.update(
            event
        )
        # A los responsables cuya actividad cambió o se canceló.
        await cronograma.enviar(avisos_actividades)

        return (await self._dtos([updated], user))[0], correos

    @staticmethod
    def _snapshot(event: EventModel) -> EventSnapshot:
        return EventSnapshot(
            fecha_inicio=event.fecha_inicio,
            fecha_fin=event.fecha_fin,
            lugar=event.lugar,
            direccion=event.direccion
        )

    async def _avisos_de_cambio(
        self,
        event: EventModel,
        antes: EventSnapshot
    ) -> list[EventChangeEmail]:
        """
        Solo si cambió la fecha, el horario, el lugar o la dirección (y no
        es un simple retoque de texto): deja un aviso en la bandeja de cada
        inscrito y prepara su correo. Con cualquier otro cambio, o sin
        inscritos, no hace nada.
        """
        aviso = event_change_notice(
            event.titulo,
            antes,
            self._snapshot(event)
        )

        if aviso is None:
            return []

        inscritos = await self.repository.registered_users(event.id)

        if not inscritos:
            return []

        enviado = datetime.now(UTC)

        # El aviso queda visible en la aplicación aunque el correo falle.
        self.repository.add_all(
            [
                NotificacionesModel(
                    id=uuid4(),
                    usuario_id=usuario.id,
                    titulo=aviso.titulo,
                    mensaje=aviso.mensaje,
                    leida=False,
                    fecha_envio=enviado
                )
                for usuario in inscritos
            ]
        )

        return [
            EventChangeEmail(
                to=usuario.correo,
                usuario_nombre=usuario.nombre,
                titulo=aviso.titulo,
                mensaje=aviso.mensaje
            )
            for usuario in inscritos
        ]

    async def delete(
        self,
        event_id: UUID
    ):
        event = await self.repository.get_by_id(
            event_id
        )

        if not event:
            raise ValueError(
                "Evento no encontrado"
            )

        await self.repository.delete(
            event
        )
