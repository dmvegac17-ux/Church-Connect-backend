import unicodedata
from collections.abc import Callable
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from datetime import timezone
from html import escape
from uuid import UUID
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from src.core.constants.enums import EstadoEnvioInvitacion
from src.core.constants.enums import EstadoRespuestaInvitacion
from src.core.constants.enums import UserRole
from src.core.logging.logger import logger
from src.infrastructure.database.models.event_model import EventModel
from src.infrastructure.database.models.invitacion_participacion_model import (
    InvitacionParticipacionModel,
)
from src.infrastructure.database.models.notificaciones_model import NotificacionesModel
from src.infrastructure.database.models.schedule_model import ScheduleModel
from src.infrastructure.database.models.user_model import UserModel
from src.infrastructure.email.email_service import EmailService
from src.infrastructure.repositories.invitacion_participacion_repository import (
    ESTADOS_LIBERADOS,
)
from src.infrastructure.repositories.invitacion_participacion_repository import (
    InvitacionParticipacionRepository,
)

# Colombia no tiene horario de verano: un desfase fijo evita depender de la
# base de datos de zonas horarias del sistema (ausente en Windows sin tzdata).
BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")

DIAS_PARA_CONFIRMAR_MAXIMO = 30
ELEGIBLES_LIMITE = 100

PENDIENTE = EstadoRespuestaInvitacion.PENDIENTE.value
ACEPTADA = EstadoRespuestaInvitacion.ACEPTADA.value
RECHAZADA = EstadoRespuestaInvitacion.RECHAZADA.value
VENCIDA = EstadoRespuestaInvitacion.VENCIDA.value
CANCELADA = EstadoRespuestaInvitacion.CANCELADA.value
REASIGNADA = EstadoRespuestaInvitacion.REASIGNADA.value
REVOCADA = EstadoRespuestaInvitacion.REVOCADA.value

ENVIO_ERROR = EstadoEnvioInvitacion.ERROR.value
ENVIO_ENVIADA = EstadoEnvioInvitacion.ENVIADA.value
ENVIO_EN_COLA = EstadoEnvioInvitacion.EN_COLA.value

VISTAS_PARTICIPANTE = ("pendientes", "respondidas", "todas")
FILTROS_ADMIN = ("todas", "pendientes", "aceptadas", "por_reasignar", "error_envio")

_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

_MENSAJES_ESTADO = {
    ACEPTADA: "Esta invitación ya fue aceptada.",
    RECHAZADA: "Esta invitación ya fue rechazada.",
    VENCIDA: "Esta invitación ya venció.",
    CANCELADA: "Esta invitación fue cancelada.",
    REASIGNADA: "Esta actividad ya fue reasignada a otra persona.",
    REVOCADA: "Esta confirmación ya fue revocada.",
    PENDIENTE: "Esta invitación sigue pendiente de respuesta.",
}

_MOTIVOS_LIBERACION = {
    RECHAZADA: "rechazo",
    VENCIDA: "sin_respuesta",
    CANCELADA: "cancelada",
    ACEPTADA: "aceptada",
}


class InvitacionNoEncontradaError(Exception):
    pass


class ActividadNoEncontradaError(Exception):
    pass


class EstadoInvitacionError(Exception):
    """La invitación no está en un estado que permita la operación (409)."""

    def __init__(self, estado_actual: str, mensaje: str | None = None):
        self.estado_actual = estado_actual
        super().__init__(mensaje or _MENSAJES_ESTADO.get(estado_actual, "La invitación cambió de estado."))


class PlazoInvalidoError(Exception):
    """`dias_para_confirmar` fuera del rango que permite la fecha del evento (422)."""

    def __init__(self, mensaje: str, dias_hasta_evento: int, dias_para_confirmar_max: int):
        self.dias_hasta_evento = dias_hasta_evento
        self.dias_para_confirmar_max = dias_para_confirmar_max
        super().__init__(mensaje)


class ParticipanteInvalidoError(Exception):
    pass


def _utc(valor: datetime | None) -> datetime | None:
    """Los motores sin zona horaria devuelven la fecha sin tz: siempre es UTC."""
    if valor is None:
        return None

    if valor.tzinfo is None:
        return valor.replace(tzinfo=UTC)

    return valor.astimezone(UTC)


def _fecha_bogota(valor: datetime) -> date:
    return _utc(valor).astimezone(BOGOTA).date()


def _nombre_completo(usuario: UserModel) -> str:
    return f"{usuario.nombre} {usuario.apellido or ''}".strip()


def _normalizar(texto: str | None) -> str | None:
    if not texto or not texto.strip():
        return None

    descompuesto = unicodedata.normalize("NFD", texto.strip().lower())

    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def _fecha_larga(valor: date) -> str:
    return f"{valor.day} de {_MESES[valor.month - 1]} de {valor.year}"


def _hora(valor: datetime) -> str:
    local = _utc(valor).astimezone(BOGOTA)
    sufijo = "a. m." if local.hour < 12 else "p. m."

    return f"{local.hour % 12 or 12}:{local.minute:02d} {sufijo}"


def _estado_para_participante(invitacion: InvitacionParticipacionModel) -> str:
    """
    El participante ve su propio desenlace: una invitación ya reasignada sigue
    siendo, para él, la que rechazó, dejó vencer o le cancelaron.
    """
    if invitacion.estado_respuesta == REASIGNADA:
        return invitacion.estado_previo or CANCELADA

    return invitacion.estado_respuesta


class ParticipacionService:

    def __init__(
        self,
        repository: InvitacionParticipacionRepository,
        email_service: EmailService,
        ahora: Callable[[], datetime] | None = None
    ):
        self.repository = repository
        self.email_service = email_service
        self._ahora = ahora or (lambda: datetime.now(UTC))

    # ── Tiempo ──────────────────────────────────────────────────────────

    def _hoy(self) -> date:
        return self._ahora().astimezone(BOGOTA).date()

    def _dias_hasta(self, actividad: ScheduleModel) -> int:
        """Días calendario (America/Bogota) desde hoy hasta el inicio de la actividad."""
        return (_fecha_bogota(actividad.hora_inicio) - self._hoy()).days

    def _dias_max(self, actividad: ScheduleModel) -> int:
        return min(DIAS_PARA_CONFIRMAR_MAXIMO, self._dias_hasta(actividad) - 1)

    def _admite_nueva_invitacion(self, actividad: ScheduleModel) -> bool:
        """Queda al menos un día completo antes del inicio para pedir confirmación."""
        return self._dias_max(actividad) >= 1

    def _limite_reasignacion(self) -> datetime:
        """Primer instante de inicio con el que una actividad aún admite reasignación."""
        dia = self._hoy() + timedelta(days=2)

        return datetime.combine(dia, time.min, BOGOTA).astimezone(UTC)

    def _fecha_limite(self, dias: int) -> datetime:
        dia = self._hoy() + timedelta(days=dias)

        return datetime.combine(dia, time(23, 59, 59), BOGOTA).astimezone(UTC)

    async def vencer_pendientes(self) -> int:
        """
        No hay tareas programadas en el proyecto: el vencimiento se aplica al
        consultar o responder, antes de leer cualquier estado.
        """
        vencidas = await self.repository.vencer_pendientes(self._ahora())

        if vencidas:
            await self.repository.liberar_responsables_sin_invitacion_activa()

        await self.repository.commit()

        return vencidas

    # ── DTOs ────────────────────────────────────────────────────────────

    def _actividad_dto(self, actividad: ScheduleModel, evento: EventModel) -> dict:
        return {
            "id": actividad.id,
            "nombre": actividad.actividad,
            "fecha": _fecha_bogota(actividad.hora_inicio).isoformat(),
            "hora_inicio": _utc(actividad.hora_inicio),
            "hora_fin": _utc(actividad.hora_fin),
            # El lugar vive en el evento: la actividad lo hereda.
            "lugar": evento.lugar,
            "descripcion": actividad.descripcion,
        }

    async def _responsables(self, filas) -> dict[UUID, dict]:
        """Quién invitó (a quien avisar) y su ministerio, por invitación."""
        ids = list({inv.invitada_por for inv, *_ in filas if inv.invitada_por})
        usuarios = await self.repository.usuarios_por_id(ids)
        areas = await self.repository.areas_de_usuarios(ids)

        return {
            usuario_id: {
                "nombre": _nombre_completo(usuario),
                "area": areas.get(usuario_id),
            }
            for usuario_id, usuario in usuarios.items()
        }

    def _dto_participante(self, fila, responsables: dict[UUID, dict]) -> dict:
        invitacion, actividad, evento, _ = fila

        return {
            "id": invitacion.id,
            "estado_respuesta": _estado_para_participante(invitacion),
            "fecha_invitacion": _utc(invitacion.fecha_envio or invitacion.created_at),
            "fecha_limite_respuesta": _utc(invitacion.fecha_limite_respuesta),
            "fecha_respuesta": _utc(invitacion.fecha_respuesta),
            "fecha_revocacion": _utc(invitacion.fecha_revocacion),
            "motivo_rechazo": invitacion.motivo_rechazo,
            "evento": {"id": evento.id, "nombre": evento.titulo},
            "actividad": self._actividad_dto(actividad, evento),
            "responsable": responsables.get(invitacion.invitada_por),
        }

    def _fila_admin(self, fila, reemplazos: dict) -> dict:
        invitacion, actividad, evento, participante = fila
        estado = invitacion.estado_respuesta
        con_plazo = self._admite_nueva_invitacion(actividad)
        reemplazo = reemplazos.get(invitacion.id)

        requiere = estado in ESTADOS_LIBERADOS and reemplazo is None and con_plazo

        acciones: list[str] = []
        if estado == PENDIENTE:
            if invitacion.estado_envio == ENVIO_ERROR:
                acciones.append("reenviar")
            acciones.append("cancelar")
        elif requiere:
            acciones.append("reasignar")
        elif estado == ACEPTADA and con_plazo:
            acciones.append("revocar_y_cambiar")

        datos_actividad = self._actividad_dto(actividad, evento)
        datos_actividad.pop("lugar")
        datos_actividad.pop("descripcion")

        return {
            "id": invitacion.id,
            "actividad": datos_actividad,
            "evento": {"id": evento.id, "nombre": evento.titulo},
            "participante": {
                "id": participante.id,
                "nombre_completo": _nombre_completo(participante),
            },
            "estado_envio": invitacion.estado_envio,
            "fecha_envio": _utc(invitacion.fecha_envio),
            "intentos_envio": invitacion.intentos_envio,
            "ultimo_error_envio": invitacion.ultimo_error_envio,
            "estado_respuesta": estado,
            "estado_previo": invitacion.estado_previo,
            "fecha_respuesta": _utc(invitacion.fecha_respuesta),
            "fecha_limite_respuesta": _utc(invitacion.fecha_limite_respuesta),
            "motivo_rechazo": invitacion.motivo_rechazo,
            "notificacion_revocacion_estado": invitacion.notificacion_revocacion_estado,
            "requiere_reasignacion": requiere,
            "acciones_permitidas": acciones,
            "reemplazo": (
                {
                    "participante": {
                        "id": reemplazo[1].id,
                        "nombre_completo": _nombre_completo(reemplazo[1]),
                    },
                    "fecha_limite_respuesta": _utc(reemplazo[0].fecha_limite_respuesta),
                }
                if reemplazo
                else None
            ),
        }

    async def _filas_admin(self, filas) -> list[dict]:
        reemplazos = await self.repository.reemplazos_de(
            [inv.id for inv, *_ in filas]
        )

        return [self._fila_admin(fila, reemplazos) for fila in filas]

    async def _fila_admin_por_id(self, invitacion_id: UUID) -> dict:
        fila = await self.repository.get_detalle(invitacion_id)

        return (await self._filas_admin([fila]))[0]

    # ── Participante ────────────────────────────────────────────────────

    async def listar_propias(self, usuario: UserModel, vista: str) -> dict:
        await self.vencer_pendientes()

        filas = await self.repository.listar_de_participante(usuario.id)
        responsables = await self._responsables(filas)

        pendientes = [f for f in filas if _estado_para_participante(f[0]) == PENDIENTE]
        respondidas = [f for f in filas if _estado_para_participante(f[0]) != PENDIENTE]

        lejano = datetime.max.replace(tzinfo=UTC)
        pendientes.sort(key=lambda f: _utc(f[0].fecha_limite_respuesta) or lejano)
        respondidas.sort(key=lambda f: _utc(f[1].hora_inicio), reverse=True)

        elegidas = {
            "pendientes": pendientes,
            "respondidas": respondidas,
            "todas": pendientes + respondidas,
        }[vista]

        return {
            "conteos": {
                "pendientes": len(pendientes),
                "respondidas": len(respondidas),
                "todas": len(filas),
            },
            "items": [self._dto_participante(f, responsables) for f in elegidas],
        }

    async def _responder(
        self,
        usuario: UserModel,
        invitacion_id: UUID,
        nuevo_estado: str,
        motivo: str | None
    ) -> dict:
        await self.vencer_pendientes()

        invitacion = await self.repository.get_by_id(invitacion_id)

        # Una invitación ajena responde igual que una inexistente.
        if not invitacion or invitacion.participante_id != usuario.id:
            raise InvitacionNoEncontradaError("Invitación no encontrada")

        ahora = self._ahora()
        registrada = await self.repository.transicionar(
            invitacion_id,
            (PENDIENTE,),
            {
                "estado_respuesta": nuevo_estado,
                "fecha_respuesta": ahora,
                "motivo_rechazo": motivo if nuevo_estado == RECHAZADA else None,
                "updated_at": ahora,
            }
        )

        if not registrada:
            await self.repository.rollback()
            actual = await self.repository.get_by_id(invitacion_id)

            raise EstadoInvitacionError(_estado_para_participante(actual))

        if nuevo_estado == RECHAZADA:
            await self.repository.asignar_responsable(invitacion.actividad_id, None)

        await self.repository.commit()

        fila = await self.repository.get_detalle(invitacion_id)

        return self._dto_participante(fila, await self._responsables([fila]))

    async def aceptar(self, usuario: UserModel, invitacion_id: UUID) -> dict:
        return await self._responder(usuario, invitacion_id, ACEPTADA, None)

    async def rechazar(
        self,
        usuario: UserModel,
        invitacion_id: UUID,
        motivo: str | None
    ) -> dict:
        motivo = (motivo or "").strip() or None

        return await self._responder(usuario, invitacion_id, RECHAZADA, motivo)

    # ── Administrador: consultas ────────────────────────────────────────

    async def listar_admin(
        self,
        filtro: str,
        q: str | None,
        pagina: int,
        por_pagina: int
    ) -> tuple[dict, int]:
        await self.vencer_pendientes()

        termino = _normalizar(q)
        limite = self._limite_reasignacion()

        conteos = await self.repository.conteos_admin(termino, limite)
        globales = (
            conteos if termino is None
            else await self.repository.conteos_admin(None, limite)
        )

        filas = await self.repository.listar_admin(
            filtro=filtro,
            q=termino,
            limite_inicio=limite,
            limit=por_pagina,
            offset=(pagina - 1) * por_pagina
        )

        return (
            {
                "conteos": conteos,
                # El banner avisa de todo lo pendiente, sin importar la búsqueda.
                "alertas": {
                    "actividades_por_reasignar": globales["por_reasignar"],
                    "invitaciones_error_envio": globales["error_envio"],
                },
                "items": await self._filas_admin(filas),
            },
            conteos[filtro]
        )

    async def vigentes_de_evento(self, evento_id: UUID) -> list[dict]:
        """Invitación vigente de cada actividad del evento (para el cronograma)."""
        await self.vencer_pendientes()

        actividad_ids = await self.repository.actividades_de_evento(evento_id)
        filas = await self.repository.ultimas_por_actividad(actividad_ids)

        # Si hubiera más de una liberada sin reemplazo, gana la más reciente.
        por_actividad = {fila[0].actividad_id: fila for fila in filas}

        return await self._filas_admin(list(por_actividad.values()))

    async def datos_reasignacion(self, invitacion_id: UUID) -> dict:
        await self.vencer_pendientes()

        fila = await self.repository.get_detalle(invitacion_id)

        if not fila:
            raise InvitacionNoEncontradaError("Invitación no encontrada")

        invitacion, actividad, evento, participante = fila
        estado = invitacion.estado_respuesta

        if estado not in _MOTIVOS_LIBERACION:
            raise EstadoInvitacionError(estado)

        if estado != ACEPTADA and await self.repository.reemplazos_de([invitacion.id]):
            raise EstadoInvitacionError(REASIGNADA)

        datos_actividad = self._actividad_dto(actividad, evento)
        datos_actividad.pop("lugar")
        datos_actividad.pop("descripcion")

        return {
            "modo": "revocar" if estado == ACEPTADA else "reasignar",
            "actividad": datos_actividad,
            "evento": {"id": evento.id, "nombre": evento.titulo},
            "asignado_actual": {
                "id": participante.id,
                "nombre_completo": _nombre_completo(participante),
            },
            "motivo_liberacion": _MOTIVOS_LIBERACION[estado],
            "motivo_rechazo": invitacion.motivo_rechazo,
            "dias_hasta_evento": self._dias_hasta(actividad),
            "dias_para_confirmar_max": self._dias_max(actividad),
        }

    async def elegibles(self, actividad_id: UUID, q: str | None) -> list[dict]:
        encontrada = await self.repository.get_actividad(actividad_id)

        if not encontrada:
            raise ActividadNoEncontradaError("Actividad no encontrada")

        actividad, _ = encontrada

        vigentes = await self.repository.ultimas_por_actividad([actividad_id])
        asignado_id = vigentes[-1][0].participante_id if vigentes else None

        usuarios = await self.repository.usuarios_invitables(
            _normalizar(q),
            ELEGIBLES_LIMITE
        )
        con_cruce = await self.repository.participantes_con_cruce(
            actividad_id,
            actividad.hora_inicio,
            actividad.hora_fin
        )

        return [
            {
                "id": usuario.id,
                "nombre_completo": _nombre_completo(usuario),
                "correo": usuario.correo,
                "rol": usuario.rol,
                "cruce_horario": usuario.id in con_cruce,
            }
            for usuario in usuarios
            if usuario.id != asignado_id
        ]

    # ── Administrador: validaciones ─────────────────────────────────────

    def _validar_plazo(self, actividad: ScheduleModel, dias: int) -> None:
        dias_hasta = self._dias_hasta(actividad)
        maximo = self._dias_max(actividad)

        if maximo < 1:
            mensaje = (
                "El evento es mañana o ya pasó: no queda tiempo para pedir "
                "confirmación."
            )
        elif dias < 1 or dias > DIAS_PARA_CONFIRMAR_MAXIMO:
            mensaje = (
                f"El plazo debe estar entre 1 y {DIAS_PARA_CONFIRMAR_MAXIMO} días."
            )
        elif dias > maximo:
            mensaje = (
                f"El evento empieza en {dias_hasta} días. El plazo máximo es de "
                f"{maximo} {'día' if maximo == 1 else 'días'}."
            )
        else:
            return

        raise PlazoInvalidoError(mensaje, dias_hasta, maximo)

    async def _validar_participante(
        self,
        participante_id: UUID,
        asignado_actual_id: UUID | None
    ) -> UserModel:
        usuarios = await self.repository.usuarios_por_id([participante_id])
        usuario = usuarios.get(participante_id)

        if not usuario or usuario.activo is not True:
            raise ParticipanteInvalidoError(
                "El participante no existe o está inactivo."
            )

        if usuario.rol == UserRole.ADMIN:
            raise ParticipanteInvalidoError(
                "Los administradores no reciben invitaciones de participación."
            )

        if asignado_actual_id is not None and usuario.id == asignado_actual_id:
            raise ParticipanteInvalidoError(
                "Elige a una persona distinta de la asignada actualmente."
            )

        return usuario

    # ── Administrador: creación y envío ─────────────────────────────────

    def _nueva_invitacion(
        self,
        actividad: ScheduleModel,
        evento: EventModel,
        participante: UserModel,
        dias: int,
        admin: UserModel,
        reemplaza_id: UUID | None
    ) -> InvitacionParticipacionModel:
        """Agrega la invitación a la transacción en curso (sin confirmar)."""
        ahora = self._ahora()
        fecha_limite = self._fecha_limite(dias)

        # Invitar a un miembro lo convierte en participante: gana solo la
        # confirmación de sus propias invitaciones, ningún permiso administrativo.
        if participante.rol == UserRole.MEMBER:
            participante.rol = UserRole.PARTICIPANT

        invitacion = InvitacionParticipacionModel(
            id=uuid4(),
            actividad_id=actividad.id,
            participante_id=participante.id,
            estado_respuesta=PENDIENTE,
            estado_envio=ENVIO_EN_COLA,
            intentos_envio=0,
            fecha_limite_respuesta=fecha_limite,
            invitada_por=admin.id,
            reemplaza_invitacion_id=reemplaza_id,
            created_at=ahora,
            updated_at=ahora
        )
        self.repository.add(invitacion)

        # La invitación queda visible en la app aunque el correo falle.
        self.repository.add(
            NotificacionesModel(
                id=uuid4(),
                usuario_id=participante.id,
                titulo=f"Invitación a participar: {actividad.actividad}",
                mensaje=self._mensaje_invitacion(actividad, evento, fecha_limite),
                leida=False,
                fecha_envio=ahora
            )
        )

        return invitacion

    def _mensaje_invitacion(
        self,
        actividad: ScheduleModel,
        evento: EventModel,
        fecha_limite: datetime
    ) -> str:
        return (
            f"<div>Te invitaron a participar en <b>{escape(actividad.actividad)}</b> "
            f"del evento <b>{escape(evento.titulo)}</b>, el "
            f"{_fecha_larga(_fecha_bogota(actividad.hora_inicio))} de "
            f"{_hora(actividad.hora_inicio)} a {_hora(actividad.hora_fin)} en "
            f"{escape(evento.lugar)}.</div><div><br></div>"
            f"<div>Responde antes del {_fecha_larga(_fecha_bogota(fecha_limite))} "
            f"desde «Confirmar participaciones» en Church Connect.</div>"
        )

    async def _confirmar_creacion(self, estado_actual: str) -> None:
        """
        El índice único parcial impide dos invitaciones activas por actividad:
        si otra petición ganó la carrera, se deshace todo y se responde 409.
        """
        try:
            await self.repository.commit()

        except IntegrityError:
            await self.repository.rollback()

            raise EstadoInvitacionError(
                estado_actual,
                "La actividad ya tiene una invitación activa."
            )

    async def _enviar_invitacion(self, invitacion_id: UUID) -> bool:
        """
        Se llama después de confirmar la transacción: un fallo de correo queda
        registrado en `estado_envio`, nunca cambia `estado_respuesta`.
        """
        invitacion, actividad, evento, participante = (
            await self.repository.get_detalle(invitacion_id)
        )

        try:
            enviado = await self.email_service.send_notification(
                to=participante.correo,
                titulo=f"Invitación a participar: {actividad.actividad}",
                mensaje=self._mensaje_invitacion(
                    actividad,
                    evento,
                    invitacion.fecha_limite_respuesta
                ),
                usuario_nombre=participante.nombre
            )
        except Exception:
            logger.exception(
                "Fallo al enviar la invitación %s",
                invitacion_id
            )
            enviado = False

        ahora = self._ahora()
        invitacion.intentos_envio = (invitacion.intentos_envio or 0) + 1
        invitacion.updated_at = ahora

        if enviado:
            invitacion.estado_envio = ENVIO_ENVIADA
            invitacion.fecha_envio = ahora
            invitacion.ultimo_error_envio = None
        else:
            invitacion.estado_envio = ENVIO_ERROR
            invitacion.ultimo_error_envio = (
                "El servicio de correo no pudo enviar la invitación."
            )

        await self.repository.commit()

        return enviado

    async def _notificar_revocacion(self, invitacion_id: UUID) -> None:
        invitacion, actividad, evento, participante = (
            await self.repository.get_detalle(invitacion_id)
        )

        try:
            enviado = await self.email_service.send_notification(
                to=participante.correo,
                titulo=f"Ya no estás asignado a: {actividad.actividad}",
                mensaje=self._mensaje_revocacion(actividad, evento),
                usuario_nombre=participante.nombre
            )
        except Exception:
            logger.exception(
                "Fallo al notificar la revocación %s",
                invitacion_id
            )
            enviado = False

        invitacion.notificacion_revocacion_estado = (
            ENVIO_ENVIADA if enviado else ENVIO_ERROR
        )
        invitacion.updated_at = self._ahora()

        await self.repository.commit()

    @staticmethod
    def _mensaje_revocacion(actividad: ScheduleModel, evento: EventModel) -> str:
        return (
            f"<div>El administrador retiró tu confirmación para "
            f"<b>{escape(actividad.actividad)}</b> del evento "
            f"<b>{escape(evento.titulo)}</b> "
            f"({_fecha_larga(_fecha_bogota(actividad.hora_inicio))}).</div>"
            f"<div><br></div><div>Ya no estás asignado a esta actividad. "
            f"No necesitas hacer nada.</div>"
        )

    # ── Administrador: acciones ─────────────────────────────────────────

    async def crear(
        self,
        admin: UserModel,
        actividad_id: UUID,
        participante_id: UUID,
        dias: int
    ) -> dict:
        await self.vencer_pendientes()

        encontrada = await self.repository.get_actividad(actividad_id)

        if not encontrada:
            raise ActividadNoEncontradaError("Actividad no encontrada")

        actividad, evento = encontrada

        activa = await self.repository.get_activa_de_actividad(actividad_id)
        if activa:
            raise EstadoInvitacionError(
                activa.estado_respuesta,
                "La actividad ya tiene una invitación activa. Cancélala, "
                "reasígnala o revócala para cambiar de persona."
            )

        # Aquí sí se puede volver a invitar a la misma persona con plazo nuevo.
        participante = await self._validar_participante(participante_id, None)
        self._validar_plazo(actividad, dias)

        try:
            ahora = self._ahora()
            liberadas = await self.repository.liberadas_sin_reemplazo(actividad_id)

            for anterior in liberadas:
                await self.repository.transicionar(
                    anterior.id,
                    ESTADOS_LIBERADOS,
                    {
                        "estado_respuesta": REASIGNADA,
                        "estado_previo": anterior.estado_respuesta,
                        "updated_at": ahora,
                    }
                )

            nueva = self._nueva_invitacion(
                actividad,
                evento,
                participante,
                dias,
                admin,
                liberadas[0].id if liberadas else None
            )
            await self.repository.asignar_responsable(
                actividad.id,
                participante.id,
                _nombre_completo(participante)
            )
        except Exception:
            await self.repository.rollback()
            raise

        await self._confirmar_creacion(PENDIENTE)
        await self._enviar_invitacion(nueva.id)

        return await self._fila_admin_por_id(nueva.id)

    async def cancelar(self, admin: UserModel, invitacion_id: UUID) -> dict:
        await self.vencer_pendientes()

        invitacion = await self.repository.get_by_id(invitacion_id)

        if not invitacion:
            raise InvitacionNoEncontradaError("Invitación no encontrada")

        ahora = self._ahora()
        cancelada = await self.repository.transicionar(
            invitacion_id,
            (PENDIENTE,),
            {
                "estado_respuesta": CANCELADA,
                "cancelada_por": admin.id,
                "fecha_cancelacion": ahora,
                "updated_at": ahora,
            }
        )

        if not cancelada:
            await self.repository.rollback()
            actual = await self.repository.get_by_id(invitacion_id)

            raise EstadoInvitacionError(
                actual.estado_respuesta,
                "Solo se puede cancelar una invitación pendiente. "
                + _MENSAJES_ESTADO.get(actual.estado_respuesta, "")
            )

        await self.repository.asignar_responsable(invitacion.actividad_id, None)
        await self.repository.commit()

        return await self._fila_admin_por_id(invitacion_id)

    async def reenviar(self, invitacion_id: UUID) -> tuple[dict, bool]:
        await self.vencer_pendientes()

        invitacion = await self.repository.get_by_id(invitacion_id)

        if not invitacion:
            raise InvitacionNoEncontradaError("Invitación no encontrada")

        if invitacion.estado_respuesta != PENDIENTE:
            raise EstadoInvitacionError(invitacion.estado_respuesta)

        if invitacion.estado_envio != ENVIO_ERROR:
            raise EstadoInvitacionError(
                invitacion.estado_respuesta,
                "La invitación ya fue enviada; solo se reenvían las que "
                "fallaron."
            )

        enviado = await self._enviar_invitacion(invitacion_id)

        return await self._fila_admin_por_id(invitacion_id), enviado

    async def _reemplazar(
        self,
        admin: UserModel,
        invitacion_id: UUID,
        participante_id: UUID,
        dias: int,
        revocar: bool
    ) -> dict:
        """
        Reasignar y revocar son la misma operación atómica: la original cambia
        de estado y se crea la nueva en una sola transacción.
        """
        await self.vencer_pendientes()

        fila = await self.repository.get_detalle(invitacion_id)

        if not fila:
            raise InvitacionNoEncontradaError("Invitación no encontrada")

        invitacion, actividad, evento, _ = fila
        estado = invitacion.estado_respuesta
        desde = (ACEPTADA,) if revocar else ESTADOS_LIBERADOS

        if estado not in desde:
            raise EstadoInvitacionError(estado)

        if not revocar and await self.repository.reemplazos_de([invitacion.id]):
            raise EstadoInvitacionError(REASIGNADA)

        participante = await self._validar_participante(
            participante_id,
            invitacion.participante_id
        )
        self._validar_plazo(actividad, dias)

        ahora = self._ahora()
        valores = (
            {
                "estado_respuesta": REVOCADA,
                "revocada_por": admin.id,
                "fecha_revocacion": ahora,
                "updated_at": ahora,
            }
            if revocar
            else {
                "estado_respuesta": REASIGNADA,
                "estado_previo": estado,
                "updated_at": ahora,
            }
        )

        try:
            cambiada = await self.repository.transicionar(
                invitacion_id,
                desde,
                valores
            )

            if not cambiada:
                await self.repository.rollback()
                actual = await self.repository.get_by_id(invitacion_id)

                raise EstadoInvitacionError(actual.estado_respuesta)

            nueva = self._nueva_invitacion(
                actividad,
                evento,
                participante,
                dias,
                admin,
                invitacion.id
            )
            await self.repository.asignar_responsable(
                actividad.id,
                participante.id,
                _nombre_completo(participante)
            )

            if revocar:
                self.repository.add(
                    NotificacionesModel(
                        id=uuid4(),
                        usuario_id=invitacion.participante_id,
                        titulo=f"Ya no estás asignado a: {actividad.actividad}",
                        mensaje=self._mensaje_revocacion(actividad, evento),
                        leida=False,
                        fecha_envio=ahora
                    )
                )
        except EstadoInvitacionError:
            raise
        except Exception:
            # Si falla la creación, la original conserva su estado.
            await self.repository.rollback()
            raise

        await self._confirmar_creacion(REASIGNADA if not revocar else REVOCADA)

        await self._enviar_invitacion(nueva.id)
        if revocar:
            await self._notificar_revocacion(invitacion_id)

        return {
            "original": await self._fila_admin_por_id(invitacion_id),
            "nueva": await self._fila_admin_por_id(nueva.id),
        }

    async def reasignar(
        self,
        admin: UserModel,
        invitacion_id: UUID,
        participante_id: UUID,
        dias: int
    ) -> dict:
        return await self._reemplazar(
            admin, invitacion_id, participante_id, dias, revocar=False
        )

    async def revocar(
        self,
        admin: UserModel,
        invitacion_id: UUID,
        participante_id: UUID,
        dias: int
    ) -> dict:
        return await self._reemplazar(
            admin, invitacion_id, participante_id, dias, revocar=True
        )
