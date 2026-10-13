from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from html import escape
import re
import unicodedata

"""
Aviso a los inscritos cuando cambia la fecha, el horario, el lugar o la
dirección de un evento. Ningún otro cambio (título, descripción, aforo,
coordenadas) genera aviso, y tampoco los retoques de texto que no cambian
adónde hay que ir (ver `text_changed`).
"""

# Colombia no tiene horario de verano: un desfase fijo evita depender de la
# base de datos de zonas horarias del sistema (ausente en Windows sin tzdata).
BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")

_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


@dataclass(frozen=True)
class EventChangeEmail:
    """Un correo pendiente de envío: se despacha después de responder."""

    to: str
    usuario_nombre: str
    titulo: str
    mensaje: str


def as_utc(valor: datetime) -> datetime:
    """Los motores sin zona horaria devuelven la fecha sin tz: siempre es UTC."""
    if valor.tzinfo is None:
        return valor.replace(tzinfo=UTC)

    return valor.astimezone(UTC)


def _fecha(valor: datetime) -> str:
    local = as_utc(valor).astimezone(BOGOTA)

    return (
        f"{_DIAS[local.weekday()]} {local.day} de {_MESES[local.month - 1]} "
        f"de {local.year}"
    )


def _hora(valor: datetime) -> str:
    local = as_utc(valor).astimezone(BOGOTA)
    sufijo = "a. m." if local.hour < 12 else "p. m."

    return f"{local.hour % 12 or 12}:{local.minute:02d} {sufijo}"


def describe_range(inicio: datetime, fin: datetime) -> str:
    """«sábado 17 de octubre de 2026, de 7:00 p. m. a 9:00 p. m.» (hora de Bogotá)."""
    mismo_dia = (
        as_utc(inicio).astimezone(BOGOTA).date()
        == as_utc(fin).astimezone(BOGOTA).date()
    )

    if mismo_dia:
        return f"{_fecha(inicio)}, de {_hora(inicio)} a {_hora(fin)}"

    return (
        f"del {_fecha(inicio)} a las {_hora(inicio)} "
        f"al {_fecha(fin)} a las {_hora(fin)}"
    )


def dates_changed(
    antes: tuple[datetime, datetime],
    ahora: tuple[datetime, datetime]
) -> bool:
    """Compara instantes, no representaciones: la misma hora en otra zona no es un cambio."""
    return (
        as_utc(antes[0]) != as_utc(ahora[0])
        or as_utc(antes[1]) != as_utc(ahora[1])
    )


# Palabras que no cambian de qué sitio se habla.
_VACIAS = frozenset(
    {"el", "la", "los", "las", "de", "del", "y", "en", "a", "al"}
)


def _limpio(valor: str | None) -> str:
    return (valor or "").strip()


def _palabras(valor: str | None) -> list[str]:
    """Minúsculas, sin tildes ni signos, sin palabras vacías."""
    sin_tildes = "".join(
        c
        for c in unicodedata.normalize("NFD", _limpio(valor).lower())
        if unicodedata.category(c) != "Mn"
    )

    return [
        palabra
        for palabra in re.findall(r"[a-z0-9]+", sin_tildes)
        if palabra not in _VACIAS
    ]


def _distancia(a: str, b: str) -> int:
    """
    Ediciones para pasar de `a` a `b`: insertar, borrar o cambiar una letra,
    o intercambiar dos vecinas (el error de tecleo más común).
    """
    previa2: list[int] = []
    previa = list(range(len(b) + 1))

    for i, ca in enumerate(a, start=1):
        actual = [i]
        for j, cb in enumerate(b, start=1):
            costo = min(
                previa[j] + 1,
                actual[j - 1] + 1,
                previa[j - 1] + (ca != cb)
            )
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                costo = min(costo, previa2[j - 2] + 1)
            actual.append(costo)
        previa2, previa = previa, actual

    return previa[-1]


def _misma_palabra(a: str, b: str) -> bool:
    """Iguales, o tan parecidas que solo puede ser una corrección de tecleo."""
    if a == b:
        return True

    # Los números identifican el sitio (calle 10 no es calle 11), y en una
    # palabra de hasta tres letras una letra distinta ya es otra palabra
    # (sur / sub).
    largo = max(len(a), len(b))
    if largo <= 3 or any(c.isdigit() for c in a + b):
        return False

    return _distancia(a, b) <= max(1, largo // 4)


def text_changed(antes: str | None, ahora: str | None) -> bool:
    """
    `True` si el texto de un lugar o una dirección cambió de verdad.

    No cuentan como cambio: mayúsculas, tildes, signos, espacios, artículos
    y preposiciones, ni corregir una errata («Templo centrl» → «Templo
    central»). Sí cuentan: cualquier número distinto, una palabra de más o
    de menos, o una palabra que pasa a ser otra.
    """
    a, b = _palabras(antes), _palabras(ahora)

    if len(a) != len(b):
        return True

    return not all(_misma_palabra(x, y) for x, y in zip(a, b))


@dataclass(frozen=True)
class EventChangeNotice:
    titulo: str
    mensaje: str


@dataclass(frozen=True)
class EventSnapshot:
    """Lo que un inscrito necesita para llegar: cuándo y dónde."""

    fecha_inicio: datetime
    fecha_fin: datetime
    lugar: str
    direccion: str | None

    @property
    def fechas(self) -> tuple[datetime, datetime]:
        return self.fecha_inicio, self.fecha_fin


_ASUNTOS = {
    "fecha": ("Cambio de fecha", "de fecha u horario"),
    "lugar": ("Cambio de lugar", "de lugar"),
    "direccion": ("Cambio de dirección", "de dirección"),
}


def _lista(partes: list[str]) -> str:
    """«de fecha u horario, de lugar y de dirección»."""
    if len(partes) == 1:
        return partes[0]

    return f"{', '.join(partes[:-1])} y {partes[-1]}"


def _antes_ahora(etiqueta: str, antes: str, ahora: str) -> str:
    return (
        f"<div><b>{etiqueta}</b></div>"
        f"<div>Antes: {antes}.</div>"
        f"<div>Ahora: {ahora}.</div><div><br></div>"
    )


def event_change_notice(
    titulo_evento: str,
    antes: EventSnapshot,
    ahora: EventSnapshot
) -> EventChangeNotice | None:
    """
    Aviso para los inscritos, o `None` si no cambió nada que les afecte.

    El HTML (mismo formato que el resto de notificaciones) nombra el evento
    y muestra, de cada cosa modificada, el valor anterior junto al nuevo.
    """
    cambios = [
        clave
        for clave, cambio in (
            ("fecha", dates_changed(antes.fechas, ahora.fechas)),
            ("lugar", text_changed(antes.lugar, ahora.lugar)),
            ("direccion", text_changed(antes.direccion, ahora.direccion)),
        )
        if cambio
    ]

    if not cambios:
        return None

    asunto = (
        _ASUNTOS[cambios[0]][0] if len(cambios) == 1 else "Cambios en el evento"
    )
    partes = [
        f"<div>El evento <b>{escape(titulo_evento)}</b>, en el que estás "
        f"inscrito, cambió {_lista([_ASUNTOS[c][1] for c in cambios])}."
        f"</div><div><br></div>"
    ]

    # Lo que cambió va con su «Antes» y «Ahora»; lo demás, como referencia.
    if "fecha" in cambios:
        partes.append(
            _antes_ahora(
                "Fecha y horario",
                describe_range(*antes.fechas),
                describe_range(*ahora.fechas)
            )
        )
    else:
        partes.append(
            f"<div>Fecha: {describe_range(*ahora.fechas)}.</div><div><br></div>"
        )

    if "lugar" in cambios:
        partes.append(
            _antes_ahora("Lugar", escape(_limpio(antes.lugar)), escape(_limpio(ahora.lugar)))
        )
    else:
        partes.append(
            f"<div>Lugar: {escape(_limpio(ahora.lugar))}.</div><div><br></div>"
        )

    if "direccion" in cambios:
        partes.append(
            _antes_ahora(
                "Dirección",
                escape(_limpio(antes.direccion)) or "sin dirección",
                escape(_limpio(ahora.direccion)) or "sin dirección"
            )
        )
    elif _limpio(ahora.direccion):
        partes.append(
            f"<div>Dirección: {escape(_limpio(ahora.direccion))}.</div>"
            f"<div><br></div>"
        )

    partes.append(
        "<div>Tu inscripción sigue vigente. Si ya no puedes asistir, cancélala "
        "desde «Mis inscripciones» en Church Connect para liberar tu cupo.</div>"
    )

    return EventChangeNotice(
        titulo=f"{asunto}: {titulo_evento}",
        mensaje="".join(partes)
    )
