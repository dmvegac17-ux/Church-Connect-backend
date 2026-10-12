"""
Documentos legales (Términos y condiciones, Política de privacidad) y la
constancia de quién los aceptó.

Reglas:
- Lo publicado no se modifica. Un cambio es una versión nueva: borrador →
  publicado, y la anterior pasa a archivada.
- Publicar con «requiere volver a aceptar» sube la versión mayor (2.0) y deja
  a todos pendientes; sin eso sube la menor (1.1) y no le pide nada a quien
  ya había aceptado.
- Está al día quien aceptó la última versión que exigía aceptación, o una
  posterior.
- Las aceptaciones solo se crean: no hay forma de editarlas ni borrarlas.
"""
from datetime import UTC
from datetime import datetime
from uuid import UUID
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.documento_legal_model import ARCHIVADO
from src.infrastructure.database.models.documento_legal_model import BORRADOR
from src.infrastructure.database.models.documento_legal_model import PUBLICADO
from src.infrastructure.database.models.documento_legal_model import TIPOS
from src.infrastructure.database.models.documento_legal_model import (
    AceptacionDocumentoModel as Aceptacion,
)
from src.infrastructure.database.models.documento_legal_model import (
    DocumentoLegalModel as Documento,
)
from src.infrastructure.database.models.user_model import UserModel

NOMBRES = {
    "terminos": "Términos y condiciones",
    "privacidad": "Política de privacidad",
}


class DocumentoNoEncontradoError(Exception):
    pass


class DocumentoLegalError(Exception):
    """Operación que el estado del documento no permite (`codigo` dice cuál)."""

    def __init__(self, mensaje: str, codigo: str):
        self.codigo = codigo
        super().__init__(mensaje)


def _orden(documento: Documento) -> tuple[int, int]:
    return (documento.version_mayor, documento.version_menor)


class LegalService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Lectura pública ─────────────────────────────────────────────────

    async def vigentes(self) -> list[Documento]:
        """La versión publicada de cada tipo (las que hay que aceptar hoy)."""
        result = await self.db.execute(
            select(Documento).where(Documento.estado == PUBLICADO)
        )

        return sorted(result.scalars().all(), key=lambda d: TIPOS.index(d.tipo))

    async def vigente(self, tipo: str) -> Documento:
        result = await self.db.execute(
            select(Documento).where(
                Documento.tipo == tipo,
                Documento.estado == PUBLICADO
            )
        )
        documento = result.scalar_one_or_none()

        if not documento:
            raise DocumentoNoEncontradoError("Este documento aún no está publicado")

        return documento

    # ── Quién está al día ───────────────────────────────────────────────

    async def _validos_por_tipo(self) -> dict[str, tuple[Documento, set[UUID]]]:
        """
        Por tipo: la versión vigente y los ids de las versiones cuya
        aceptación sigue valiendo (desde la última que exigió aceptar).
        """
        result = await self.db.execute(
            select(Documento).where(Documento.estado.in_((PUBLICADO, ARCHIVADO)))
        )
        por_tipo: dict[str, list[Documento]] = {}

        for documento in result.scalars().all():
            por_tipo.setdefault(documento.tipo, []).append(documento)

        validos: dict[str, tuple[Documento, set[UUID]]] = {}

        for tipo, versiones in por_tipo.items():
            vigente = next((d for d in versiones if d.estado == PUBLICADO), None)

            if vigente is None:
                continue

            exigidas = [d for d in versiones if d.requiere_reaceptacion]
            base = max(exigidas, key=_orden) if exigidas else min(versiones, key=_orden)
            validos[tipo] = (
                vigente,
                {d.id for d in versiones if _orden(d) >= _orden(base)},
            )

        return validos

    async def pendientes(self, usuario_id: UUID) -> list[Documento]:
        """Documentos vigentes que esa persona todavía debe aceptar."""
        validos = await self._validos_por_tipo()

        if not validos:
            return []

        result = await self.db.execute(
            select(Aceptacion.documento_id).where(Aceptacion.usuario_id == usuario_id)
        )
        aceptados = set(result.scalars().all())

        return [
            vigente
            for tipo in TIPOS
            if tipo in validos
            for vigente, ids in [validos[tipo]]
            if not (ids & aceptados)
        ]

    # ── Aceptar ─────────────────────────────────────────────────────────

    async def validar_para_registro(self, documento_ids: list[UUID]) -> list[Documento]:
        """
        Quien se registra debe aceptar exactamente las versiones vigentes.
        Devuelve esos documentos; lanza si falta alguno o alguno ya no rige.
        """
        vigentes = await self.vigentes()
        esperados = {d.id for d in vigentes}

        if not esperados:
            return []

        if not documento_ids:
            raise DocumentoLegalError(
                "Para crear tu cuenta debes aceptar los términos y condiciones "
                "y la política de privacidad.",
                "aceptacion_requerida"
            )

        if set(documento_ids) != esperados:
            raise DocumentoLegalError(
                "Los documentos cambiaron mientras llenabas el formulario. "
                "Revísalos de nuevo antes de aceptar.",
                "version_no_vigente"
            )

        return vigentes

    @staticmethod
    def constancias(
        usuario_id: UUID,
        documentos: list[Documento],
        ip: str | None,
        user_agent: str | None
    ) -> list[Aceptacion]:
        ahora = datetime.now(UTC)

        return [
            Aceptacion(
                id=uuid4(),
                usuario_id=usuario_id,
                documento_id=documento.id,
                aceptado_en=ahora,
                ip=(ip or None) and ip[:64],
                user_agent=(user_agent or None) and user_agent[:300]
            )
            for documento in documentos
        ]

    async def aceptar(
        self,
        usuario: UserModel,
        documento_ids: list[UUID],
        ip: str | None,
        user_agent: str | None
    ) -> list[Documento]:
        """Registra la aceptación de lo que esa persona tenía pendiente."""
        pendientes = await self.pendientes(usuario.id)
        esperados = {d.id for d in pendientes}

        if not esperados:
            return []

        if set(documento_ids) != esperados:
            raise DocumentoLegalError(
                "Los documentos cambiaron. Revísalos de nuevo antes de aceptar.",
                "version_no_vigente"
            )

        self.db.add_all(self.constancias(usuario.id, pendientes, ip, user_agent))
        await self.db.commit()

        return pendientes

    async def aceptaciones_de(self, usuario_id: UUID) -> list[dict]:
        result = await self.db.execute(
            select(Aceptacion, Documento)
            .join(Documento, Documento.id == Aceptacion.documento_id)
            .where(Aceptacion.usuario_id == usuario_id)
            .order_by(Aceptacion.aceptado_en.desc())
        )

        return [
            {
                "id": aceptacion.id,
                "documento_id": documento.id,
                "tipo": documento.tipo,
                "titulo": documento.titulo,
                "version": documento.version,
                "aceptado_en": aceptacion.aceptado_en,
            }
            for aceptacion, documento in result.all()
        ]

    # ── Administración ──────────────────────────────────────────────────

    async def todos(self) -> list[Documento]:
        result = await self.db.execute(select(Documento))

        return sorted(
            result.scalars().all(),
            key=lambda d: (TIPOS.index(d.tipo), -d.version_mayor, -d.version_menor)
        )

    async def _por_id(self, documento_id: UUID) -> Documento:
        documento = await self.db.get(Documento, documento_id)

        if not documento:
            raise DocumentoNoEncontradoError("Documento no encontrado")

        return documento

    async def _borrador(self, documento_id: UUID) -> Documento:
        documento = await self._por_id(documento_id)

        if documento.estado != BORRADOR:
            raise DocumentoLegalError(
                "Una versión publicada no se puede modificar: es el texto que "
                "las personas aceptaron. Crea una versión nueva.",
                "no_es_borrador"
            )

        return documento

    async def crear_borrador(self, tipo: str, admin: UserModel) -> Documento:
        """Borrador de la siguiente versión, con el texto de la vigente."""
        existentes = [d for d in await self.todos() if d.tipo == tipo]
        borrador = next((d for d in existentes if d.estado == BORRADOR), None)

        if borrador:
            return borrador

        vigente = next((d for d in existentes if d.estado == PUBLICADO), None)
        ultima = max(existentes, key=_orden) if existentes else None
        documento = Documento(
            id=uuid4(),
            tipo=tipo,
            # Provisional: el número definitivo se asigna al publicar.
            version_mayor=(ultima.version_mayor + 1) if ultima else 1,
            version_menor=0,
            titulo=vigente.titulo if vigente else NOMBRES[tipo],
            contenido=vigente.contenido if vigente else "",
            estado=BORRADOR,
            requiere_reaceptacion=True,
            creado_por=admin.id,
            actualizado_por=admin.id
        )
        self.db.add(documento)
        await self.db.commit()

        return documento

    async def actualizar_borrador(
        self,
        documento_id: UUID,
        titulo: str,
        contenido: str,
        admin: UserModel
    ) -> Documento:
        documento = await self._borrador(documento_id)
        documento.titulo = titulo
        documento.contenido = contenido
        documento.actualizado_por = admin.id
        await self.db.commit()

        return documento

    async def eliminar_borrador(self, documento_id: UUID) -> None:
        documento = await self._borrador(documento_id)
        await self.db.delete(documento)
        await self.db.commit()

    async def publicar(
        self,
        documento_id: UUID,
        requiere_reaceptacion: bool,
        admin: UserModel
    ) -> Documento:
        documento = await self._borrador(documento_id)

        if not documento.contenido.strip():
            raise DocumentoLegalError(
                "El documento está vacío: escribe su contenido antes de publicarlo.",
                "documento_vacio"
            )

        hermanos = [d for d in await self.todos() if d.tipo == documento.tipo]
        vigente = next((d for d in hermanos if d.estado == PUBLICADO), None)
        ahora = datetime.now(UTC)

        if vigente is None:
            # La primera versión siempre hay que aceptarla.
            requiere_reaceptacion = True
            mayor, menor = 1, 0
        elif requiere_reaceptacion:
            mayor, menor = vigente.version_mayor + 1, 0
        else:
            mayor, menor = vigente.version_mayor, vigente.version_menor + 1

        if vigente is not None:
            # Primero se archiva la anterior: solo puede haber una publicada.
            vigente.estado = ARCHIVADO
            await self.db.flush()

        documento.version_mayor = mayor
        documento.version_menor = menor
        documento.estado = PUBLICADO
        documento.requiere_reaceptacion = requiere_reaceptacion
        documento.publicado_en = ahora
        documento.publicado_por = admin.id
        documento.actualizado_por = admin.id
        await self.db.commit()

        return documento

    async def resumen_de_aceptaciones(self) -> dict:
        """
        Por cada persona activa: qué versión aceptó de cada documento vigente
        y cuándo, o si la tiene pendiente.
        """
        validos = await self._validos_por_tipo()
        usuarios = (
            await self.db.execute(
                select(UserModel).where(UserModel.activo.is_not(False))
            )
        ).scalars().all()
        filas = (
            await self.db.execute(
                select(Aceptacion, Documento)
                .join(Documento, Documento.id == Aceptacion.documento_id)
            )
        ).all()

        # La aceptación válida más reciente de cada persona, por tipo.
        ultima: dict[tuple[UUID, str], tuple[Aceptacion, Documento]] = {}
        for aceptacion, documento in filas:
            if documento.tipo not in validos:
                continue
            if documento.id not in validos[documento.tipo][1]:
                continue
            clave = (aceptacion.usuario_id, documento.tipo)
            if clave not in ultima or _orden(documento) > _orden(ultima[clave][1]):
                ultima[clave] = (aceptacion, documento)

        personas = []
        for usuario in sorted(usuarios, key=lambda u: (u.nombre or "").lower()):
            estados = {}
            for tipo in validos:
                hallada = ultima.get((usuario.id, tipo))
                estados[tipo] = (
                    {"version": hallada[1].version, "aceptado_en": hallada[0].aceptado_en}
                    if hallada
                    else None
                )
            personas.append({
                "usuario_id": usuario.id,
                "nombre_completo": " ".join(
                    filter(None, [usuario.nombre, usuario.apellido])
                ),
                "correo": usuario.correo,
                "aceptaciones": estados,
                "al_dia": all(estados.values()),
            })

        return {
            "documentos": {
                tipo: {"version": vigente.version, "titulo": vigente.titulo}
                for tipo, (vigente, _) in validos.items()
            },
            "total": len(personas),
            "al_dia": sum(1 for p in personas if p["al_dia"]),
            "personas": personas,
        }
