from datetime import UTC
from datetime import datetime
from datetime import timedelta
from uuid import UUID
from uuid import uuid4

from src.api.v1.schedules.schemas import ScheduleCreate
from src.api.v1.schedules.schemas import ScheduleTimesUpdate
from src.api.v1.schedules.schemas import ScheduleUpdate
from src.application.events.registration_window import deadline_before_today
from src.application.notificaciones.services import firmar_mensaje
from src.application.schedules.cambios import Foto
from src.application.schedules.cambios import cambio_material
from src.application.schedules.cambios import diferencias
from src.application.schedules.cambios import mensaje_actualizada
from src.application.schedules.cambios import mensaje_cancelada
from src.application.schedules.cambios import mensaje_reconfirmar
from src.application.schedules.cambios import mensaje_sin_cambio
from src.application.schedules.cambios import momento as _momento
from src.core.constants.enums import EstadoEnvioInvitacion
from src.core.constants.enums import EstadoRespuestaInvitacion
from src.core.exceptions.custom_exceptions import EventoFinalizadoError
from src.core.exceptions.custom_exceptions import VersionDesactualizadaError
from src.core.logging.logger import logger
from src.infrastructure.database.models.cambio_cronograma_model import (
    CambioCronogramaModel,
)
from src.infrastructure.database.models.notificaciones_model import NotificacionesModel
from src.core.exceptions.custom_exceptions import evento_finalizado
from src.infrastructure.database.models.schedule_model import ScheduleModel
from src.infrastructure.repositories.event_repository import EventRepository
from src.infrastructure.repositories.schedule_repository import ScheduleRepository


class ScheduleNotFoundError(Exception):
    pass


class EventNotFoundError(Exception):
    pass


class InvalidScheduleTimeError(Exception):
    pass


class ScheduleOutOfEventRangeError(Exception):
    pass


class ScheduleOverlapError(Exception):
    pass


class ActividadesFueraDeRangoError(Exception):
    """
    El horario nuevo del evento deja actividades por fuera y no se dijo qué
    hacer con ellas. Se responde `409` con la lista, para resolverlas (mover,
    ajustar o eliminar) en el mismo guardado.
    """

    codigo = "actividades_fuera_de_rango"

    def __init__(self, actividades: list[dict]):
        self.actividades = actividades
        cuantas = len(actividades)
        super().__init__(
            (
                "1 actividad del cronograma queda"
                if cuantas == 1
                else f"{cuantas} actividades del cronograma quedan"
            )
            + " fuera del nuevo horario del evento. Muévelas con el evento, "
            "ajústalas o elimínalas para poder guardar."
        )


def _fuera_del_evento(event) -> ScheduleOutOfEventRangeError:
    return ScheduleOutOfEventRangeError(
        f"Esta actividad debe estar entre el {_momento(event.fecha_inicio)} "
        f"y el {_momento(event.fecha_fin)}"
    )


def _utc(valor: datetime) -> datetime:
    """Los motores sin zona horaria devuelven la fecha sin tz: siempre es UTC."""
    return valor.replace(tzinfo=UTC) if valor.tzinfo is None else valor


def _estado_actividad(evento, actividad, invitacion) -> str:
    """En qué está una actividad: lo que muestra su indicador en el panel."""
    if (
        _utc(actividad.hora_inicio) < _utc(evento.fecha_inicio)
        or _utc(actividad.hora_fin) > _utc(evento.fecha_fin)
    ):
        return "fuera_de_rango"

    if invitacion is None:
        return "sin_asignar"

    estado = invitacion.estado_respuesta

    if estado == EstadoRespuestaInvitacion.ACEPTADA.value:
        return "confirmado"

    if estado == EstadoRespuestaInvitacion.PENDIENTE.value:
        return "por_reconfirmar" if invitacion.reconfirmacion else "pendiente"

    if estado == EstadoRespuestaInvitacion.RECHAZADA.value:
        return "rechazado"

    if estado == EstadoRespuestaInvitacion.VENCIDA.value:
        return "sin_respuesta"

    # Cancelada, revocada o ya reasignada sin nadie nuevo: está libre.
    return "sin_asignar"


RESPONSABLE_POR_CONFIRMAR = "Pendiente por confirmar"
RESPONSABLE_POR_ASIGNAR = "Pendiente por asignar"

_CRONOGRAMA_CERRADO = (
    "El evento ya finalizó: su cronograma no se puede modificar."
)


class ScheduleService:

    def __init__(
        self,
        repository: ScheduleRepository,
        event_repository: EventRepository,
        email_service=None
    ):
        self.repository = repository
        self.event_repository = event_repository
        self.email_service = email_service

    async def get_all(
        self,
        limit: int,
        offset: int,
        evento_id: UUID | None = None
    ):
        if evento_id is not None:
            return await self.repository.get_by_evento_id(
                evento_id
            )

        return await self.repository.get_all(
            limit=limit,
            offset=offset
        )

    async def count(
        self,
        evento_id: UUID | None = None
    ) -> int:
        return await self.repository.count(
            evento_id
        )

    async def get_by_id(
        self,
        schedule_id: UUID
    ):
        schedule = await self.repository.get_by_id(
            schedule_id
        )

        if not schedule:
            raise ScheduleNotFoundError(
                "Cronograma no encontrado"
            )

        return schedule

    async def _evento_editable(self, evento_id: UUID, version: int | None):
        """El evento, si existe, no terminó y nadie lo cambió entre tanto."""
        event = await self.event_repository.get_by_id(
            evento_id
        )

        if not event:
            raise EventNotFoundError(
                "Evento no encontrado"
            )

        if evento_finalizado(event.fecha_fin):
            raise EventoFinalizadoError(_CRONOGRAMA_CERRADO)

        if version is not None and version != (event.version or 1):
            raise VersionDesactualizadaError()

        return event

    async def create(
        self,
        request: ScheduleCreate,
        admin=None,
        version: int | None = None
    ):
        event = await self._evento_editable(request.evento_id, version)

        self._validate_not_past(request.hora_inicio)

        if _utc(request.hora_fin) <= _utc(request.hora_inicio):
            raise InvalidScheduleTimeError(
                "hora_fin debe ser posterior a hora_inicio"
            )

        existing = await self.repository.get_by_evento_id(
            event.id
        )

        self._validate_range_and_overlap(
            event=event,
            hora_inicio=request.hora_inicio,
            hora_fin=request.hora_fin,
            existing_schedules=existing,
            schedule_id=None
        )

        schedule = ScheduleModel(
            id=uuid4(),
            evento_id=request.evento_id,
            actividad=request.actividad,
            hora_inicio=request.hora_inicio,
            hora_fin=request.hora_fin,
            responsable=request.responsable,
            descripcion=request.descripcion
        )

        self.repository.add(schedule)
        # La actividad se inserta antes que su entrada en el historial, que
        # la referencia.
        await self.repository.flush()
        self._historial(event, schedule, "creada", None, Foto.de(schedule).json(), admin)
        self._subir_version(event)

        await self.repository.commit()
        await self.repository.refresh(schedule)

        return schedule

    async def update(
        self,
        schedule_id: UUID,
        request: ScheduleUpdate,
        admin=None,
        version: int | None = None
    ):
        schedule = await self.get_by_id(
            schedule_id
        )

        # Se revisa el evento antes de tocar la actividad: si ya terminó, no
        # debe quedar ningún cambio a medias en la sesión.
        event = await self._evento_editable(schedule.evento_id, version)

        update_data = request.model_dump(
            exclude_unset=True
        )

        # Solo al mover el horario: lo demás se edita aunque el día ya pasó.
        nuevo_inicio = update_data.get("hora_inicio")
        if nuevo_inicio is not None and (
            _utc(nuevo_inicio) != _utc(schedule.hora_inicio)
        ):
            self._validate_not_past(nuevo_inicio)

        antes = Foto.de(schedule)

        for field, value in update_data.items():
            setattr(schedule, field, value)

        if _utc(schedule.hora_fin) <= _utc(schedule.hora_inicio):
            raise InvalidScheduleTimeError(
                "hora_fin debe ser posterior a hora_inicio"
            )

        existing = await self.repository.get_by_evento_id(
            event.id
        )

        self._validate_range_and_overlap(
            event=event,
            hora_inicio=schedule.hora_inicio,
            hora_fin=schedule.hora_fin,
            existing_schedules=existing,
            schedule_id=schedule.id
        )

        avisos = await self._tras_editar(event, schedule, antes, admin)

        await self.repository.commit()
        await self.repository.refresh(schedule)
        await self._enviar(avisos)

        return schedule

    async def reschedule(
        self,
        request: ScheduleTimesUpdate,
        admin=None,
        version: int | None = None
    ):
        """
        Cambia el horario de varias actividades de un evento de una vez.

        Reordenar un cronograma intercambia horarios: guardando una actividad
        a la vez, la primera chocaría con la que todavía ocupa su hueco. Aquí
        se valida cómo queda el cronograma completo y se guarda todo o nada.
        """
        event = await self._evento_editable(request.evento_id, version)

        existing = list(
            await self.repository.get_by_evento_id(event.id)
        )
        por_id = {schedule.id: schedule for schedule in existing}
        nuevos = {item.id: item for item in request.items}

        if any(schedule_id not in por_id for schedule_id in nuevos):
            raise ScheduleNotFoundError(
                "Alguna actividad no existe o no pertenece a este evento"
            )

        # Horario final de cada actividad: el nuevo si viene, el actual si no.
        final = {
            schedule.id: (
                (_utc(nuevos[schedule.id].hora_inicio), _utc(nuevos[schedule.id].hora_fin))
                if schedule.id in nuevos
                else (_utc(schedule.hora_inicio), _utc(schedule.hora_fin))
            )
            for schedule in existing
        }
        inicio_evento = _utc(event.fecha_inicio)
        fin_evento = _utc(event.fecha_fin)

        for schedule_id in nuevos:
            inicio, fin = final[schedule_id]

            if inicio != _utc(por_id[schedule_id].hora_inicio):
                self._validate_not_past(inicio)

            if fin <= inicio:
                raise InvalidScheduleTimeError(
                    "hora_fin debe ser posterior a hora_inicio"
                )

            if inicio < inicio_evento or fin > fin_evento:
                raise _fuera_del_evento(event)

            for otro_id, (otro_inicio, otro_fin) in final.items():
                if otro_id != schedule_id and otro_inicio < fin and otro_fin > inicio:
                    raise ScheduleOverlapError(
                        "El horario se solapa con otra actividad del "
                        "cronograma de este evento"
                    )

        # Todo validado: recién ahora se toca la sesión.
        avisos: list[dict] = []
        for schedule_id, item in nuevos.items():
            schedule = por_id[schedule_id]
            antes = Foto.de(schedule)
            schedule.hora_inicio = item.hora_inicio
            schedule.hora_fin = item.hora_fin
            avisos += await self._tras_editar(event, schedule, antes, admin)

        await self.repository.commit()
        await self._enviar(avisos)

        return await self.repository.get_by_evento_id(event.id)

    @staticmethod
    def _validate_not_past(hora_inicio: datetime) -> None:
        if deadline_before_today(hora_inicio):
            raise InvalidScheduleTimeError(
                "La actividad no puede ser anterior a hoy"
            )

    def _validate_range_and_overlap(
        self,
        event,
        hora_inicio,
        hora_fin,
        existing_schedules,
        schedule_id: UUID | None
    ) -> None:
        # Lo que llega en la petición trae zona horaria; lo leído de la base
        # puede no traerla. Se comparan siempre como instantes.
        hora_inicio, hora_fin = _utc(hora_inicio), _utc(hora_fin)

        if hora_inicio < _utc(event.fecha_inicio) or hora_fin > _utc(event.fecha_fin):
            raise _fuera_del_evento(event)

        for other in existing_schedules:
            if schedule_id is not None and other.id == schedule_id:
                continue

            if _utc(other.hora_inicio) < hora_fin and _utc(other.hora_fin) > hora_inicio:
                raise ScheduleOverlapError(
                    "El horario se solapa con otra actividad del "
                    "cronograma de este evento"
                )

    async def delete(
        self,
        schedule_id: UUID,
        admin=None,
        version: int | None = None
    ):
        """
        Borrado lógico: la actividad queda cancelada. Así su responsable la
        sigue viendo (como cancelada) en sus participaciones y queda rastro
        en el historial. Si tenía a alguien asignado, se le avisa.
        """
        schedule = await self.get_by_id(
            schedule_id
        )

        # Las actividades de un evento terminado se van con él al eliminarlo,
        # no una por una.
        event = await self._evento_editable(schedule.evento_id, version)

        avisos = await self._cancelar(event, schedule, admin)

        await self.repository.commit()
        await self._enviar(avisos)

    async def _cancelar(self, event, schedule, admin) -> list[dict]:
        """Cancela la actividad en la transacción en curso (sin confirmar)."""
        ahora = datetime.now(UTC)
        foto = Foto.de(schedule)
        avisos: list[dict] = []
        fila = await self.repository.invitacion_activa(schedule.id)

        if fila:
            invitacion, participante = fila
            invitacion.estado_respuesta = EstadoRespuestaInvitacion.CANCELADA.value
            invitacion.reconfirmacion = False
            invitacion.cancelada_por = admin.id if admin else None
            invitacion.fecha_cancelacion = ahora
            invitacion.updated_at = ahora

            # Quien se la asignó a sí mismo es quien la está eliminando.
            if admin is None or participante.id != admin.id:
                avisos.append(
                    await self._avisar(
                        invitacion,
                        participante,
                        f"Se canceló la actividad: {foto.actividad}",
                        self._firmar(mensaje_cancelada(event.titulo, foto), admin)
                    )
                )

        schedule.cancelada_en = ahora
        schedule.cancelada_por = admin.id if admin else None
        schedule.responsable_id = None

        self._historial(event, schedule, "eliminada", foto.json(), None, admin)
        self._subir_version(event)

        return avisos

    async def ajustar_con_evento(self, event, ajustes, admin) -> list[dict]:
        """
        Acomoda el cronograma al horario nuevo del evento, dentro de la misma
        transacción que lo cambia (quien llama confirma o deshace todo).

        `ajustes` dice qué hacer con cada actividad afectada: darle otro
        horario o eliminarla. Ninguna se elimina sin que se pida. Si después
        de aplicarlos queda alguna fuera del evento, no se guarda nada.
        Devuelve los correos por enviar una vez confirmado el cambio.
        """
        existing = list(
            await self.repository.get_by_evento_id(event.id)
        )
        por_id = {schedule.id: schedule for schedule in existing}
        pedidos = {ajuste.id: ajuste for ajuste in ajustes}

        if any(schedule_id not in por_id for schedule_id in pedidos):
            raise ScheduleNotFoundError(
                "Alguna actividad no existe o no pertenece a este evento"
            )

        eliminar = {ajuste.id for ajuste in ajustes if ajuste.eliminar}
        final: dict[UUID, tuple[datetime, datetime]] = {}

        for schedule in existing:
            if schedule.id in eliminar:
                continue

            pedido = pedidos.get(schedule.id)
            final[schedule.id] = (
                _utc(pedido.hora_inicio if pedido and pedido.hora_inicio else schedule.hora_inicio),
                _utc(pedido.hora_fin if pedido and pedido.hora_fin else schedule.hora_fin),
            )

        inicio_evento = _utc(event.fecha_inicio)
        fin_evento = _utc(event.fecha_fin)
        fuera = [
            schedule
            for schedule in existing
            if schedule.id in final
            and (
                final[schedule.id][0] < inicio_evento
                or final[schedule.id][1] > fin_evento
            )
        ]

        if fuera:
            raise ActividadesFueraDeRangoError(
                [
                    {
                        "id": str(schedule.id),
                        "actividad": schedule.actividad,
                        "hora_inicio": final[schedule.id][0].isoformat(),
                        "hora_fin": final[schedule.id][1].isoformat(),
                    }
                    for schedule in sorted(fuera, key=lambda s: final[s.id][0])
                ]
            )

        for schedule_id, (inicio, fin) in final.items():
            if fin <= inicio:
                raise InvalidScheduleTimeError(
                    "hora_fin debe ser posterior a hora_inicio"
                )

            for otro_id, (otro_inicio, otro_fin) in final.items():
                if otro_id != schedule_id and otro_inicio < fin and otro_fin > inicio:
                    raise ScheduleOverlapError(
                        f"Con el horario nuevo, «{por_id[schedule_id].actividad}» "
                        f"se cruza con «{por_id[otro_id].actividad}»"
                    )

        # Todo validado: recién ahora se toca el cronograma.
        avisos: list[dict] = []

        for schedule_id in eliminar:
            avisos += await self._cancelar(event, por_id[schedule_id], admin)

        for schedule_id, (inicio, fin) in final.items():
            schedule = por_id[schedule_id]

            if inicio != _utc(schedule.hora_inicio) or fin != _utc(schedule.hora_fin):
                antes = Foto.de(schedule)
                schedule.hora_inicio = inicio
                schedule.hora_fin = fin
                avisos += await self._tras_editar(event, schedule, antes, admin)

        return avisos

    async def enviar(self, avisos: list[dict]) -> None:
        await self._enviar(avisos)

    async def con_estado(self, schedules) -> list[dict]:
        """
        El cronograma como lo ve el administrador: cada actividad con el
        estado de su responsable (confirmado, pendiente, rechazado…).
        """
        eventos, ultima = await self.repository.contexto_de_estado(schedules)

        return [
            {
                "id": schedule.id,
                "evento_id": schedule.evento_id,
                "actividad": schedule.actividad,
                "hora_inicio": schedule.hora_inicio,
                "hora_fin": schedule.hora_fin,
                "responsable": schedule.responsable,
                "responsable_id": schedule.responsable_id,
                "descripcion": schedule.descripcion,
                "estado": (
                    _estado_actividad(
                        eventos[schedule.evento_id], schedule, ultima.get(schedule.id)
                    )
                    if schedule.evento_id in eventos
                    else None
                ),
            }
            for schedule in schedules
        ]

    async def para_miembro(self, schedules) -> list[dict]:
        """
        El cronograma como lo ve un miembro: el nombre del responsable solo
        aparece cuando esa persona ya confirmó. Mientras tanto se dice que
        está pendiente, sin exponer a quién se invitó.
        """
        estados = await self.repository.estados_de_invitacion(
            [schedule.id for schedule in schedules]
        )
        vista = []

        for schedule in schedules:
            estado = estados.get(schedule.id)
            confirmado = estado == EstadoRespuestaInvitacion.ACEPTADA.value

            if confirmado:
                responsable = schedule.responsable
            elif estado == EstadoRespuestaInvitacion.PENDIENTE.value:
                responsable = RESPONSABLE_POR_CONFIRMAR
            else:
                responsable = RESPONSABLE_POR_ASIGNAR

            vista.append({
                "id": schedule.id,
                "evento_id": schedule.evento_id,
                "actividad": schedule.actividad,
                "hora_inicio": schedule.hora_inicio,
                "hora_fin": schedule.hora_fin,
                "responsable": responsable,
                "responsable_id": schedule.responsable_id if confirmado else None,
                "responsable_confirmado": confirmado,
                "descripcion": schedule.descripcion,
            })

        return vista

    async def agrupados(self) -> list[dict]:
        """
        El cronograma de todos los eventos, agrupado por evento y con el
        estado de cada actividad (según su responsable y el rango del evento).
        """
        eventos, actividades, ultima = await self.repository.eventos_con_cronograma()
        por_evento: dict[UUID, list] = {}

        for actividad in actividades:
            por_evento.setdefault(actividad.evento_id, []).append(actividad)

        return [
            {
                "evento": {
                    "id": evento.id,
                    "titulo": evento.titulo,
                    "fecha_inicio": _utc(evento.fecha_inicio),
                    "fecha_fin": _utc(evento.fecha_fin),
                    "lugar": evento.lugar,
                },
                "actividades": [
                    {
                        "id": actividad.id,
                        "evento_id": actividad.evento_id,
                        "actividad": actividad.actividad,
                        "hora_inicio": _utc(actividad.hora_inicio),
                        "hora_fin": _utc(actividad.hora_fin),
                        "responsable": actividad.responsable,
                        "responsable_id": actividad.responsable_id,
                        "descripcion": actividad.descripcion,
                        "estado": _estado_actividad(
                            evento, actividad, ultima.get(actividad.id)
                        ),
                    }
                    for actividad in por_evento.get(evento.id, [])
                ],
            }
            for evento in eventos
        ]

    async def historial(self, evento_id: UUID):
        return await self.repository.historial(evento_id)

    # ── Cambios: historial, versión y reconfirmación ────────────────────

    @staticmethod
    def _firmar(mensaje: str, admin) -> str:
        return firmar_mensaje(mensaje, admin) if admin else mensaje

    @staticmethod
    def _subir_version(event) -> None:
        event.version = (event.version or 1) + 1

    def _historial(self, event, schedule, tipo, antes, despues, admin) -> None:
        nombre = "Sistema"
        if admin:
            nombre = " ".join(filter(None, [admin.nombre, admin.apellido]))

        self.repository.add(
            CambioCronogramaModel(
                id=uuid4(),
                evento_id=event.id,
                actividad_id=schedule.id,
                actividad=schedule.actividad,
                tipo=tipo,
                antes=antes,
                despues=despues,
                autor_id=admin.id if admin else None,
                autor_nombre=nombre,
                fecha=datetime.now(UTC)
            )
        )

    @staticmethod
    def _plazo(hora_inicio: datetime) -> datetime:
        """Hasta cuándo se puede reconfirmar: tres días, sin pasar del inicio."""
        ahora = datetime.now(UTC)
        limite = min(ahora + timedelta(days=3), _utc(hora_inicio))

        return limite if limite > ahora else ahora + timedelta(days=1)

    async def _tras_editar(self, event, schedule, antes: Foto, admin) -> list[dict]:
        """Deja rastro del cambio y, si hace falta, pide reconfirmar."""
        despues = Foto.de(schedule)
        cambiado_antes, cambiado_despues = diferencias(antes, despues)

        if not cambiado_antes:
            return []

        self._historial(
            event, schedule, "editada", cambiado_antes, cambiado_despues, admin
        )
        self._subir_version(event)

        return await self._revisar_confirmacion(event, schedule, antes, despues, admin)

    async def _revisar_confirmacion(
        self,
        event,
        schedule,
        antes: Foto,
        despues: Foto,
        admin
    ) -> list[dict]:
        fila = await self.repository.invitacion_activa(schedule.id)

        if not fila:
            return []

        invitacion, participante = fila

        # Quien se asignó a sí mismo no tiene a quién reconfirmarle.
        if invitacion.estado_envio == EstadoEnvioInvitacion.AUTOASIGNADA.value:
            return []

        ahora = datetime.now(UTC)
        aceptada = EstadoRespuestaInvitacion.ACEPTADA.value
        pendiente = EstadoRespuestaInvitacion.PENDIENTE.value

        if invitacion.estado_respuesta == aceptada:
            confirmado = antes.json()

            if not cambio_material(confirmado, despues):
                return []

            limite = self._plazo(despues.hora_inicio)
            invitacion.estado_respuesta = pendiente
            invitacion.reconfirmacion = True
            invitacion.confirmado = confirmado
            invitacion.fecha_respuesta = None
            invitacion.fecha_limite_respuesta = limite
            invitacion.updated_at = ahora

            return [
                await self._avisar(
                    invitacion,
                    participante,
                    f"Cambió una actividad que confirmaste: {despues.actividad}",
                    self._firmar(
                        mensaje_reconfirmar(event.titulo, confirmado, despues, limite),
                        admin
                    )
                )
            ]

        if invitacion.reconfirmacion and invitacion.confirmado:
            confirmado = invitacion.confirmado

            # Volvió a quedar como la confirmó: no hay nada que reconfirmar.
            if not cambio_material(confirmado, despues):
                invitacion.estado_respuesta = aceptada
                invitacion.reconfirmacion = False
                invitacion.confirmado = None
                invitacion.fecha_respuesta = ahora
                invitacion.updated_at = ahora

                return [
                    await self._avisar(
                        invitacion,
                        participante,
                        f"Tu confirmación sigue vigente: {despues.actividad}",
                        self._firmar(mensaje_sin_cambio(event.titulo, despues), admin)
                    )
                ]

            # Otro cambio antes de que respondiera: un solo aviso, siempre
            # contra lo que confirmó.
            limite = self._plazo(despues.hora_inicio)
            invitacion.fecha_limite_respuesta = limite
            invitacion.updated_at = ahora

            return [
                await self._avisar(
                    invitacion,
                    participante,
                    f"Cambió una actividad que confirmaste: {despues.actividad}",
                    self._firmar(
                        mensaje_reconfirmar(event.titulo, confirmado, despues, limite),
                        admin
                    )
                )
            ]

        # Invitación que todavía no había respondido: solo se le actualiza.
        if not cambio_material(antes.json(), despues):
            return []

        return [
            await self._avisar(
                invitacion,
                participante,
                f"Cambió una actividad a la que te invitaron: {despues.actividad}",
                self._firmar(
                    mensaje_actualizada(event.titulo, antes.json(), despues), admin
                )
            )
        ]

    async def _avisar(self, invitacion, participante, titulo: str, mensaje: str) -> dict:
        """
        Deja el aviso en la aplicación reescribiendo el anterior de esta
        invitación, si sigue ahí: varios cambios seguidos no se apilan.
        """
        ahora = datetime.now(UTC)
        aviso = None

        if invitacion.aviso_cambio_id:
            aviso = await self.repository.get_notificacion(invitacion.aviso_cambio_id)

        if aviso is None:
            aviso = NotificacionesModel(
                id=uuid4(),
                usuario_id=participante.id,
                titulo=titulo,
                mensaje=mensaje,
                leida=False,
                fecha_envio=ahora
            )
            self.repository.add(aviso)
            invitacion.aviso_cambio_id = aviso.id
        else:
            aviso.titulo = titulo
            aviso.mensaje = mensaje
            aviso.leida = False
            aviso.fecha_envio = ahora

        return {
            "to": participante.correo,
            "titulo": titulo,
            "mensaje": mensaje,
            "usuario_nombre": participante.nombre,
        }

    async def _enviar(self, avisos: list[dict]) -> None:
        """Después de guardar: un fallo de correo no deshace el cambio."""
        if not self.email_service:
            return

        for aviso in avisos:
            try:
                await self.email_service.send_notification(**aviso)
            except Exception:
                logger.exception("Fallo al avisar del cambio a %s", aviso["to"])
