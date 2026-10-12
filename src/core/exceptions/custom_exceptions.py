from datetime import UTC
from datetime import datetime


class EventoFinalizadoError(Exception):
    """
    Un evento que ya terminó queda como registro: ni él, ni su cronograma,
    ni quién participa en sus actividades se pueden modificar. Solo se puede
    eliminar. Se responde `409` con `data.codigo = "evento_finalizado"`.
    """

    codigo = "evento_finalizado"

    def __init__(
        self,
        mensaje: str = "El evento ya finalizó: no se puede editar, solo eliminar."
    ):
        super().__init__(mensaje)


class VersionDesactualizadaError(Exception):
    """
    Otro administrador guardó cambios en el evento o en su cronograma después
    de que este formulario los cargó. Se responde `409` con
    `data.codigo = "version_desactualizada"` para no sobrescribirlos.
    """

    codigo = "version_desactualizada"

    def __init__(self):
        super().__init__(
            "Otra persona modificó este evento o su cronograma mientras lo "
            "editabas. Recarga para ver la versión actual antes de guardar."
        )


def evento_finalizado(fecha_fin: datetime, ahora: datetime | None = None) -> bool:
    """`True` si el evento ya terminó. Uno en curso todavía no."""
    # Los motores sin zona horaria devuelven la fecha sin tz: siempre es UTC.
    fin = fecha_fin.replace(tzinfo=UTC) if fecha_fin.tzinfo is None else fecha_fin

    return fin < (ahora or datetime.now(UTC))
