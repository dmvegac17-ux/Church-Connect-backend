"""
Cambios en una actividad del cronograma: qué cambió, si obliga a que su
responsable vuelva a confirmar, y los avisos que recibe.

Una actividad confirmada no puede cambiar de condiciones a espaldas de quien
la aceptó: si se mueve el horario o cambia de verdad el nombre, la
confirmación queda «por reconfirmar» y se le dice qué cambió respecto de lo
que había confirmado.
"""
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from html import escape

from src.application.events.date_change import text_changed
from src.application.events.registration_window import BOGOTA

_MESES = (
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic"
)

CAMPOS = ("actividad", "hora_inicio", "hora_fin", "descripcion", "responsable")


def _utc(valor: datetime) -> datetime:
    return valor.replace(tzinfo=UTC) if valor.tzinfo is None else valor


def momento(valor: datetime) -> str:
    """"14 nov 3:00 p. m.", en hora de Colombia."""
    local = _utc(valor).astimezone(BOGOTA)
    sufijo = "a. m." if local.hour < 12 else "p. m."

    return (
        f"{local.day} {_MESES[local.month - 1]} "
        f"{local.hour % 12 or 12}:{local.minute:02d} {sufijo}"
    )


def _hora(valor: datetime) -> str:
    return momento(valor).split(" ", 2)[2]


def horario(inicio: datetime, fin: datetime) -> str:
    """"14 nov 3:00 p. m. – 4:00 p. m." (con su día si termina otro)."""
    mismo_dia = (
        _utc(inicio).astimezone(BOGOTA).date() == _utc(fin).astimezone(BOGOTA).date()
    )

    return f"{momento(inicio)} – {_hora(fin) if mismo_dia else momento(fin)}"


@dataclass(frozen=True)
class Foto:
    """Los datos de una actividad en un momento dado."""

    actividad: str
    hora_inicio: datetime
    hora_fin: datetime
    descripcion: str | None
    responsable: str

    @classmethod
    def de(cls, schedule) -> "Foto":
        return cls(
            actividad=schedule.actividad,
            hora_inicio=_utc(schedule.hora_inicio),
            hora_fin=_utc(schedule.hora_fin),
            descripcion=schedule.descripcion,
            responsable=schedule.responsable,
        )

    def json(self) -> dict:
        return {
            "actividad": self.actividad,
            "hora_inicio": self.hora_inicio.isoformat(),
            "hora_fin": self.hora_fin.isoformat(),
            "descripcion": self.descripcion,
            "responsable": self.responsable,
        }


def diferencias(antes: Foto, despues: Foto) -> tuple[dict, dict]:
    """Solo los campos que cambiaron, antes y después (para el historial)."""
    a, d = antes.json(), despues.json()
    cambiados = [campo for campo in CAMPOS if a[campo] != d[campo]]

    return (
        {campo: a[campo] for campo in cambiados},
        {campo: d[campo] for campo in cambiados},
    )


def cambio_material(confirmado: dict, ahora: Foto) -> bool:
    """
    `True` si la actividad ya no es la que el responsable confirmó: otro
    horario, o un nombre que cambió de verdad (no una tilde o una errata).
    La descripción no cuenta.
    """
    return (
        datetime.fromisoformat(confirmado["hora_inicio"]) != ahora.hora_inicio
        or datetime.fromisoformat(confirmado["hora_fin"]) != ahora.hora_fin
        or text_changed(confirmado["actividad"], ahora.actividad)
    )


# Estilos en línea y etiquetas básicas: es lo que respetan Gmail y
# Outlook/Hotmail (ignoran las hojas de estilo). `<s>` refuerza el tachado
# donde `text-decoration` no se aplica.
_ROJO = "color:#b42318;text-decoration:line-through;"
_VERDE = "color:#1a7f37;"


def _antes(texto: str) -> str:
    return f'<span style="{_ROJO}"><s>{texto}</s></span>'


def _despues(texto: str) -> str:
    return f'<b><span style="{_VERDE}">{texto}</span></b>'


def _lineas_de_cambio(confirmado: dict, ahora: Foto) -> str:
    inicio = datetime.fromisoformat(confirmado["hora_inicio"])
    fin = datetime.fromisoformat(confirmado["hora_fin"])
    lineas = []

    if inicio != ahora.hora_inicio or fin != ahora.hora_fin:
        lineas.append(
            f"<div><b>Horario:</b> {_antes(horario(inicio, fin))} → "
            f"{_despues(horario(ahora.hora_inicio, ahora.hora_fin))}</div>"
        )

    if text_changed(confirmado["actividad"], ahora.actividad):
        lineas.append(
            f"<div><b>Nombre:</b> {_antes(escape(confirmado['actividad']))} → "
            f"{_despues(escape(ahora.actividad))}</div>"
        )

    return "".join(lineas)


def mensaje_reconfirmar(
    evento_titulo: str,
    confirmado: dict,
    ahora: Foto,
    limite: datetime
) -> str:
    """Siempre compara con lo que la persona confirmó, no con el último cambio."""
    return (
        f"<div>Cambió la actividad <b>{escape(confirmado['actividad'])}</b> del "
        f"evento <b>{escape(evento_titulo)}</b>, que habías confirmado.</div>"
        f"<div><br></div>{_lineas_de_cambio(confirmado, ahora)}<div><br></div>"
        f"<div>Tu confirmación quedó pendiente: confirma de nuevo o indica que "
        f"no puedes, antes del {momento(limite)}, desde <b>«Mis participaciones»</b> "
        f"en Church Connect.</div>"
    )


def mensaje_actualizada(evento_titulo: str, antes: dict, ahora: Foto) -> str:
    """Para una invitación que todavía no se había respondido."""
    return (
        f"<div>Cambió la actividad <b>{escape(antes['actividad'])}</b> del "
        f"evento <b>{escape(evento_titulo)}</b>, a la que te invitaron.</div>"
        f"<div><br></div>{_lineas_de_cambio(antes, ahora)}<div><br></div>"
        f"<div>Tu invitación sigue pendiente: respóndela desde <b>«Mis "
        f"participaciones»</b> en Church Connect.</div>"
    )


def mensaje_sin_cambio(evento_titulo: str, ahora: Foto) -> str:
    return (
        f"<div>La actividad <b>{escape(ahora.actividad)}</b> del evento "
        f"<b>{escape(evento_titulo)}</b> volvió a quedar como la confirmaste: "
        f"{horario(ahora.hora_inicio, ahora.hora_fin)}.</div><div><br></div>"
        f"<div>Tu confirmación sigue vigente. No necesitas hacer nada.</div>"
    )


def mensaje_cancelada(evento_titulo: str, foto: Foto) -> str:
    return (
        f"<div>Se canceló la actividad <b>{escape(foto.actividad)}</b> del "
        f"evento <b>{escape(evento_titulo)}</b> "
        f"({horario(foto.hora_inicio, foto.hora_fin)}).</div><div><br></div>"
        f"<div>Ya no estás asignado a ella. No necesitas hacer nada.</div>"
    )
