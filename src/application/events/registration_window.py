from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone

"""
Hasta cuándo se puede inscribir alguien a un evento y hasta cuándo puede
cancelar su inscripción. Lo usan el servicio de inscripciones (que decide) y
el de eventos (que se lo cuenta a quien consulta).

Los límites son para el público. Un administrador puede inscribir o retirar
a alguien hasta que el evento empiece.
"""

DIAS_LIMITE_CANCELACION_MAX = 365

# Los días se cuentan en el calendario de Colombia, que no tiene horario de
# verano: un desfase fijo evita depender de la base de zonas del sistema.
BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")


def _utc(valor: datetime) -> datetime:
    """Los motores sin zona horaria devuelven la fecha sin tz: siempre es UTC."""
    return valor.replace(tzinfo=UTC) if valor.tzinfo is None else valor


def registration_deadline(event) -> datetime:
    """Último instante para inscribirse: la fecha límite o, sin ella, el inicio."""
    inicio = _utc(event.fecha_inicio)

    if event.fecha_limite_inscripcion is None:
        return inicio

    return min(_utc(event.fecha_limite_inscripcion), inicio)


def cancellation_deadline(event) -> datetime:
    """Último instante para cancelar: N días antes del inicio (o el inicio)."""
    return _utc(event.fecha_inicio) - timedelta(
        days=event.dias_limite_cancelacion or 0
    )


def started(event, ahora: datetime | None = None) -> bool:
    return _utc(event.fecha_inicio) <= (ahora or datetime.now(UTC))


def registration_closed(event, es_admin: bool, ahora: datetime | None = None) -> bool:
    ahora = ahora or datetime.now(UTC)

    if started(event, ahora):
        return True

    return not es_admin and registration_deadline(event) <= ahora


def cancellation_closed(event, es_admin: bool, ahora: datetime | None = None) -> bool:
    ahora = ahora or datetime.now(UTC)

    if es_admin:
        return False

    return cancellation_deadline(event) <= ahora


# ── Qué valores se aceptan al configurar un evento ──────────────────────

def local_date(valor: datetime) -> date:
    """Día de calendario (Colombia) en que cae un instante."""
    return _utc(valor).astimezone(BOGOTA).date()


def days_until_event(fecha_inicio: datetime, ahora: datetime | None = None) -> int:
    """
    Días de calendario desde hoy hasta el día del evento; 0 si es hoy o ya
    pasó. Es el máximo de `dias_limite_cancelacion`: pedir más días de
    anticipación de los que quedan cerraría la cancelación en el pasado.
    """
    hoy = local_date(ahora or datetime.now(UTC))

    return max(0, (local_date(fecha_inicio) - hoy).days)


def deadline_before_today(limite: datetime, ahora: datetime | None = None) -> bool:
    """La fecha límite de inscripción cae en un día anterior a hoy."""
    return local_date(limite) < local_date(ahora or datetime.now(UTC))
