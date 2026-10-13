"""legal documents, acceptances and the initial published texts

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-10-16 10:00:00.000000

"""
from datetime import UTC
from datetime import datetime
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TERMINOS = """\
Estos términos explican cómo se usa **Church Connect**, la aplicación de Church Connection (en adelante, "la iglesia"). Al crear una cuenta o usar la aplicación aceptas lo que aquí se dice. Si no estás de acuerdo, no la uses.

## 1. Qué es Church Connect

Church Connect es una herramienta para organizar la vida de la comunidad: consultar eventos, inscribirse en ellos, ver su cronograma, participar en actividades, pertenecer a ministerios y recibir avisos de la iglesia.

No es una red social abierta ni un servicio comercial. Su uso es gratuito.

## 2. Tu cuenta

- Para usar la aplicación necesitas una cuenta con tu nombre, apellido, correo electrónico y una contraseña. El teléfono es opcional.
- Los datos que registres deben ser tuyos y verdaderos.
- Tu cuenta es personal. No la prestes ni compartas tu contraseña.
- Eres responsable de lo que se haga con tu cuenta. Si crees que alguien más entró en ella, cambia tu contraseña y avísanos.
- Un administrador de la iglesia también puede crear una cuenta para ti. En ese caso se te pedirá aceptar estos términos la primera vez que entres.

## 3. Quién puede hacer qué

Hay dos tipos de cuenta:

- **Miembro**: consulta eventos y cronogramas, se inscribe en eventos, responde las invitaciones a participar en actividades, pertenece a ministerios y recibe avisos.
- **Administrador**: además crea y edita eventos y cronogramas, invita a personas a participar, gestiona las inscripciones, envía avisos y administra las cuentas.

Los administradores son personas designadas por la iglesia.

## 4. Uso adecuado

Al usar la aplicación te comprometes a:

- Tratar con respeto a las demás personas.
- No usar los datos de otras personas (nombre, correo, teléfono) para fines distintos a la vida de la comunidad.
- No intentar entrar a cuentas ajenas ni a partes de la aplicación que no te corresponden.
- No usar la aplicación para publicidad, ventas, campañas políticas ni para enviar mensajes no deseados.
- No intentar dañar, sobrecargar o alterar el funcionamiento de la aplicación.

## 5. Eventos, inscripciones y participaciones

- **Inscripciones**: al inscribirte en un evento reservas un cupo. Si no puedes asistir, cancela tu inscripción dentro del plazo que indique el evento, para que otra persona pueda usar el cupo.
- **Participaciones**: un administrador puede invitarte a ser responsable de una actividad. Puedes aceptar o rechazar la invitación. Si aceptas, la iglesia cuenta contigo; si después no puedes, avisa con tiempo.
- **Cambios**: los eventos y las actividades pueden cambiar de fecha, hora o lugar, o cancelarse. Cuando eso pase te avisaremos por la aplicación y, si es posible, por correo. Si una actividad que ya habías confirmado cambia, se te pedirá confirmar de nuevo.
- Tu nombre puede aparecer en el cronograma de un evento como responsable de una actividad, una vez la hayas confirmado.

## 6. Avisos y correos

Al usar la aplicación aceptas recibir avisos relacionados con tu cuenta y con la vida de la comunidad: invitaciones, cambios en eventos, recordatorios y comunicaciones de la iglesia. Llegan a tu bandeja dentro de la aplicación y, en algunos casos, a tu correo electrónico.

## 7. Responsabilidades

- La iglesia procura que la aplicación funcione bien y que la información esté al día, pero no garantiza que esté disponible todo el tiempo ni libre de errores.
- La aplicación es una ayuda para organizarse. La información oficial sobre un evento es la que comunique la iglesia.
- La iglesia no responde por el uso indebido que una persona haga de su cuenta o de la información de otras personas.

## 8. Suspensión y cierre de cuentas

- Puedes pedir que se elimine tu cuenta en cualquier momento, escribiendo al contacto indicado al final.
- La iglesia puede suspender o eliminar una cuenta que incumpla estos términos, o que deje de pertenecer a la comunidad.

## 9. Tus datos personales

El tratamiento de tus datos se explica en la **Política de privacidad**, que hace parte de estos términos.

## 10. Cambios a estos términos

Podemos actualizar estos términos. Cuando el cambio sea importante, la aplicación te pedirá aceptarlos de nuevo antes de seguir usándola. Las correcciones de redacción que no cambian tus derechos ni obligaciones se publican sin pedir una nueva aceptación.

## 11. Ley aplicable

Estos términos se rigen por las leyes de la República de Colombia.

## 12. Contacto

Church Connection
NIT: 900.123.456-7
Dirección: Carrera 84 # 33AA-1, Medellín, Colombia
Correo: churchconnection.contacto@gmail.com
"""

PRIVACIDAD = """\
Esta política explica qué datos personales recoge **Church Connect**, para qué los usa y qué derechos tienes sobre ellos. Se rige por la Ley 1581 de 2012 de protección de datos personales de Colombia y sus normas reglamentarias.

## 1. Responsable del tratamiento

Church Connection
NIT: 900.123.456-7
Dirección: Carrera 84 # 33AA-1, Medellín, Colombia
Correo para asuntos de datos personales: churchconnection.contacto@gmail.com

## 2. Qué datos recogemos

**Los que tú nos das:**

- Nombre y apellido.
- Correo electrónico.
- Teléfono (opcional).
- Contraseña. Se guarda cifrada: nadie en la iglesia puede verla.
- Otros datos que en el futuro decidas agregar a tu perfil.

**Los que resultan de usar la aplicación:**

- Los eventos en los que te inscribes y tu asistencia.
- Las actividades en las que participas y tus respuestas a las invitaciones.
- Los ministerios a los que perteneces.
- Los avisos que recibes y si los has leído.
- La fecha en que aceptaste estos documentos, junto con la dirección IP y el navegador desde el que lo hiciste, como constancia.

No recogemos datos de pago ni tu ubicación.

## 3. Datos sensibles

Por tratarse de la aplicación de una iglesia, el solo hecho de tener una cuenta y participar en sus actividades puede revelar tus **convicciones religiosas**. La ley colombiana considera ese dato como **sensible** y le da una protección especial.

Queremos que lo sepas con claridad:

- No estás obligado a autorizar el tratamiento de datos sensibles.
- Sin esa autorización no es posible usar la aplicación, porque su único fin es organizar la vida de esta comunidad de fe.
- Estos datos no se comparten con terceros ni se usan para ningún fin distinto a los que se indican en esta política.

**Al aceptar esta política autorizas de forma expresa a la iglesia a tratar ese dato sensible para las finalidades aquí descritas.**

## 4. Para qué usamos tus datos

- Crear y administrar tu cuenta.
- Organizar eventos, inscripciones, cronogramas y participaciones.
- Enviarte avisos relacionados con tu cuenta y con la vida de la comunidad, por la aplicación y por correo electrónico.
- Mostrar tu nombre a otros miembros donde es necesario para organizarse, por ejemplo como responsable confirmado de una actividad o como integrante de un ministerio.
- Proteger la seguridad de las cuentas.
- Cumplir obligaciones legales.

No usamos tus datos para publicidad ni los vendemos.

## 5. Quién puede ver tus datos

- **Tú**: todos tus datos.
- **Los administradores de la iglesia**: tus datos de cuenta y de perfil, tus inscripciones y tus participaciones, para poder organizar la comunidad.
- **Otros miembros**: solo tu nombre, y solo donde la aplicación lo muestra. No ven tu teléfono.

## 6. Tus derechos

Como titular de tus datos tienes derecho a:

- **Conocer** qué datos tuyos tenemos y para qué los usamos.
- **Actualizar y rectificar** tus datos si están incompletos o equivocados.
- **Pedir prueba** de la autorización que diste.
- **Revocar** la autorización y **pedir que se supriman** tus datos, cuando no exista un deber legal de conservarlos.
- **Acceder gratis** a tus datos.
- **Presentar una queja** ante la Superintendencia de Industria y Comercio si consideras que se incumplió la ley, después de haber reclamado primero ante la iglesia.

## 7. Cómo ejercer tus derechos

- **Desde la aplicación**: en "Mi perfil" puedes ver y corregir tu nombre, apellido, correo y teléfono.
- **Por correo**: escribe a churchconnection.contacto@gmail.com indicando tu nombre, el correo de tu cuenta y qué solicitas.

Respondemos las **consultas** en un máximo de diez (10) días hábiles y los **reclamos** en un máximo de quince (15) días hábiles, contados desde el día siguiente al que los recibimos. Si no es posible responder en ese plazo, te informaremos el motivo y la nueva fecha, dentro de los límites que fija la ley.

Si pides que se eliminen tus datos, tu cuenta dejará de existir y no podrás seguir usando la aplicación.

## 8. Cuánto tiempo los conservamos

Conservamos tus datos mientras tengas una cuenta. Si la eliminas, o si pides suprimir tus datos, se borran junto con tu cuenta, salvo los que la ley obligue a conservar.

## 9. Proveedores que nos ayudan

Para funcionar, la aplicación usa servicios de otras empresas que guardan o procesan datos por encargo de la iglesia:

- **Supabase**, donde se aloja la base de datos.
- **El servicio de alojamiento** de la aplicación.
- **El servicio de correo electrónico** con el que se envían los avisos.

Estos proveedores pueden tener sus servidores fuera de Colombia. Solo tratan los datos para prestar su servicio y no pueden usarlos para fines propios. Al aceptar esta política autorizas esa transmisión.

## 10. Cómo protegemos tus datos

- Las contraseñas se guardan cifradas.
- La conexión con la aplicación es segura (HTTPS).
- Solo las personas autorizadas pueden ver los datos de los miembros.
- Las sesiones se cierran solas después de un tiempo sin uso.

Ningún sistema es infalible. Si ocurre un incidente que afecte tus datos, te lo informaremos.

## 11. Menores de edad

Los datos de niños, niñas y adolescentes solo se tratan con la autorización de su madre, padre o representante legal, y respetando siempre sus derechos. Si eres menor de edad, pide a quien te representa que cree la cuenta contigo.

## 12. Cambios a esta política

Podemos actualizar esta política. Cuando el cambio sea importante, la aplicación te pedirá aceptarla de nuevo antes de seguir usándola.

## 13. Vigencia

Esta política rige desde la fecha de publicación que aparece al inicio de este documento.
"""


def upgrade() -> None:
    op.create_table(
        "documentos_legales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("version_mayor", sa.Integer(), nullable=False),
        sa.Column("version_menor", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("requiere_reaceptacion", sa.Boolean(), nullable=False),
        sa.Column("publicado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publicado_por", sa.Uuid(), nullable=True),
        sa.Column("creado_por", sa.Uuid(), nullable=True),
        sa.Column("actualizado_por", sa.Uuid(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('terminos', 'privacidad')", name="ck_documentos_legales_tipo"
        ),
        sa.CheckConstraint(
            "estado IN ('borrador', 'publicado', 'archivado')",
            name="ck_documentos_legales_estado"
        ),
        sa.ForeignKeyConstraint(["publicado_por"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["creado_por"], ["usuarios.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actualizado_por"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tipo", "version_mayor", "version_menor",
            name="uq_documentos_legales_version"
        ),
    )
    # Una sola versión publicada y un solo borrador por tipo.
    op.create_index(
        "uq_documentos_legales_publicado", "documentos_legales", ["tipo"],
        unique=True, postgresql_where=sa.text("estado = 'publicado'")
    )
    op.create_index(
        "uq_documentos_legales_borrador", "documentos_legales", ["tipo"],
        unique=True, postgresql_where=sa.text("estado = 'borrador'")
    )

    op.create_table(
        "aceptaciones_documentos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("documento_id", sa.Uuid(), nullable=False),
        sa.Column("aceptado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["documento_id"], ["documentos_legales.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "usuario_id", "documento_id", name="uq_aceptaciones_usuario_documento"
        ),
    )
    op.create_index("ix_aceptaciones_usuario", "aceptaciones_documentos", ["usuario_id"])

    # Registro de cumplimiento: una aceptación no se modifica. (Sí se va con
    # la cuenta si la persona pide suprimir sus datos.)
    op.execute(
        """
        CREATE FUNCTION aceptaciones_inmutables() RETURNS trigger
        LANGUAGE plpgsql SET search_path = '' AS $$
        BEGIN
            RAISE EXCEPTION 'Las aceptaciones de documentos no se pueden modificar';
        END;
        $$
        """
    )
    op.execute(
        "CREATE TRIGGER aceptaciones_documentos_inmutables "
        "BEFORE UPDATE ON aceptaciones_documentos "
        "FOR EACH ROW EXECUTE FUNCTION aceptaciones_inmutables()"
    )

    # Solo el backend toca estas tablas: cerradas a la API pública de Supabase.
    op.execute("ALTER TABLE documentos_legales ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aceptaciones_documentos ENABLE ROW LEVEL SECURITY")

    # Versión 1.0 de los dos documentos, ya publicada.
    ahora = datetime.now(UTC)
    documentos = sa.table(
        "documentos_legales",
        sa.column("id", sa.Uuid()),
        sa.column("tipo", sa.String()),
        sa.column("version_mayor", sa.Integer()),
        sa.column("version_menor", sa.Integer()),
        sa.column("titulo", sa.String()),
        sa.column("contenido", sa.Text()),
        sa.column("estado", sa.String()),
        sa.column("requiere_reaceptacion", sa.Boolean()),
        sa.column("publicado_en", sa.DateTime(timezone=True)),
        sa.column("creado_en", sa.DateTime(timezone=True)),
        sa.column("actualizado_en", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        documentos,
        [
            {
                "id": uuid4(), "tipo": tipo, "version_mayor": 1, "version_menor": 0,
                "titulo": titulo, "contenido": contenido, "estado": "publicado",
                "requiere_reaceptacion": True, "publicado_en": ahora,
                "creado_en": ahora, "actualizado_en": ahora,
            }
            for tipo, titulo, contenido in (
                ("terminos", "Términos y condiciones", TERMINOS),
                ("privacidad", "Política de privacidad", PRIVACIDAD),
            )
        ],
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS aceptaciones_documentos_inmutables "
        "ON aceptaciones_documentos"
    )
    op.execute("DROP FUNCTION IF EXISTS aceptaciones_inmutables()")
    op.drop_index("ix_aceptaciones_usuario", table_name="aceptaciones_documentos")
    op.drop_table("aceptaciones_documentos")
    op.drop_index("uq_documentos_legales_borrador", table_name="documentos_legales")
    op.drop_index("uq_documentos_legales_publicado", table_name="documentos_legales")
    op.drop_table("documentos_legales")
