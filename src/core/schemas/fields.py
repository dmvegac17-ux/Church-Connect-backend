"""Tipos de campo reutilizables con las validaciones de entrada del producto.

Son las mismas reglas que aplica el frontend (`src/lib/validators.ts`): el
backend las repite para garantizarlas aunque la petición no venga de la app.
"""

import re
from typing import Annotated

from pydantic import AfterValidator
from pydantic import BeforeValidator
from pydantic import EmailStr
from pydantic import StringConstraints

PERSON_NAME_MIN = 2
PERSON_NAME_MAX = 50
EMAIL_MAX = 100

# Solo letras (con acentos, ü y ñ) separadas por espacios simples.
_PERSON_NAME_RE = re.compile(
    r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+( [A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)*$"
)
# 7 a 15 dígitos, con el indicativo `+` opcional al inicio.
_PHONE_RE = re.compile(r"^\+?\d{7,15}$")


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def _validate_person_name(value: str) -> str:
    if len(value) < PERSON_NAME_MIN:
        raise ValueError("Debe tener al menos 2 letras.")

    if len(value) > PERSON_NAME_MAX:
        raise ValueError(f"Máximo {PERSON_NAME_MAX} caracteres.")

    if not _PERSON_NAME_RE.fullmatch(value):
        raise ValueError(
            "Usa solo letras, sin números ni caracteres especiales."
        )

    return value


def _validate_phone(value: str) -> str:
    # Cadena vacía = "sin teléfono" (así lo limpia el formulario de edición).
    if value and not _PHONE_RE.fullmatch(value):
        raise ValueError(
            "Usa solo números (7 a 15) y, si quieres, el indicativo con + "
            "al inicio."
        )

    return value


def _validate_email_length(value: str) -> str:
    if len(value) > EMAIL_MAX:
        raise ValueError(f"Máximo {EMAIL_MAX} caracteres.")

    return value


PersonName = Annotated[
    str,
    BeforeValidator(_strip),
    AfterValidator(_validate_person_name),
]
"""Nombre o apellido de una persona: 2–50 letras, sin números ni símbolos."""

Phone = Annotated[
    str,
    BeforeValidator(_strip),
    AfterValidator(_validate_phone),
]
"""Teléfono opcional: vacío, o 7–15 dígitos con `+` inicial opcional."""

Email = Annotated[
    EmailStr,
    AfterValidator(_validate_email_length),
]
"""Correo válido de máximo 100 caracteres."""


def trimmed_text(min_length: int, max_length: int):
    """Texto obligatorio: se recortan los espacios y se valida el largo."""
    return Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=min_length,
            max_length=max_length,
        ),
    ]
