import asyncio
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from html import escape
from pathlib import Path
from string import Template

from src.core.config.settings import settings
from src.core.logging.logger import logger
from src.infrastructure.email.html_sanitizer import sanitize_message

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_NOTIFICATION_TEMPLATE = Template(
    (_TEMPLATES_DIR / "notification.html").read_text(encoding="utf-8")
)
_PASSWORD_RESET_TEMPLATE = Template(
    (_TEMPLATES_DIR / "password_reset.html").read_text(encoding="utf-8")
)


class EmailService:
    """
    Envía correos por SMTP. Si `settings.smtp_configured` es `False`
    (`MAIL_SMTP_HOST`/`MAIL_SMTP_FROM` sin definir, como en desarrollo local sin
    credenciales), el envío se omite silenciosamente. Cualquier error de
    conexión/autenticación se registra en el log pero no se propaga: enviar
    el correo es un efecto secundario best-effort, no debe hacer fallar la
    operación que lo dispara (p. ej. crear una notificación).
    """

    async def send(
        self,
        to: str,
        subject: str,
        body: str
    ) -> bool:
        return await self._dispatch(
            to,
            subject,
            body,
            html=None
        )

    async def send_notification(
        self,
        to: str,
        titulo: str,
        mensaje: str,
        usuario_nombre: str
    ) -> bool:
        """
        Envía una notificación usando la plantilla HTML compartida
        (`templates/notification.html`). `mensaje` llega como HTML
        enriquecido (negrilla/resaltado/fuente) desde el editor del
        frontend, así que se sanitiza (whitelist) en vez de escaparlo, y se
        deriva un texto plano equivalente como respaldo.
        """
        mensaje_html, mensaje_texto = sanitize_message(mensaje)

        html = _NOTIFICATION_TEMPLATE.substitute(
            usuario_nombre=escape(usuario_nombre),
            titulo=escape(titulo),
            mensaje=mensaje_html,
            anio=datetime.now(UTC).year
        )

        return await self._dispatch(
            to,
            titulo,
            mensaje_texto,
            html=html
        )

    async def send_password_reset(
        self,
        to: str,
        usuario_nombre: str,
        enlace: str,
        minutos: int
    ) -> bool:
        """
        Envía el enlace para restablecer la contraseña con su plantilla
        (`templates/password_reset.html`) y una versión en texto plano.
        """
        html = _PASSWORD_RESET_TEMPLATE.substitute(
            usuario_nombre=escape(usuario_nombre),
            enlace=escape(enlace, quote=True),
            minutos=minutos,
            anio=datetime.now(UTC).year
        )
        texto = (
            f"Hola, {usuario_nombre}\n\n"
            "Recibimos una solicitud para cambiar la contraseña de tu cuenta "
            "de Church Connect. Abre este enlace para elegir una nueva:\n\n"
            f"{enlace}\n\n"
            f"El enlace vence en {minutos} minutos y solo se puede usar una vez.\n\n"
            "Si no solicitaste este cambio, ignora este correo: tu contraseña "
            "seguirá siendo la misma.\n\n"
            "Church Connect · Conectados con tu fe"
        )

        return await self._dispatch(
            to,
            "Restablece tu contraseña de Church Connect",
            texto,
            html=html
        )

    async def _dispatch(
        self,
        to: str,
        subject: str,
        body: str,
        html: str | None
    ) -> bool:
        if not settings.smtp_configured:
            logger.info(
                "SMTP no configurado; se omite el envío de correo a %s (%s)",
                to,
                subject
            )
            return False

        try:
            await asyncio.to_thread(
                self._send_sync,
                to,
                subject,
                body,
                html
            )
            return True

        except Exception:
            logger.exception(
                "No se pudo enviar el correo a %s",
                to
            )
            return False

    def _send_sync(
        self,
        to: str,
        subject: str,
        body: str,
        html: str | None = None
    ) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.MAIL_SMTP_FROM
        message["To"] = to
        message.set_content(body)

        if html:
            message.add_alternative(
                html,
                subtype="html"
            )

        with smtplib.SMTP(
            settings.MAIL_SMTP_HOST,
            settings.MAIL_SMTP_PORT,
            timeout=10
        ) as smtp:
            smtp.ehlo()

            if smtp.has_extn("STARTTLS"):
                smtp.starttls()
                smtp.ehlo()

            if settings.MAIL_SMTP_USERNAME:
                smtp.login(
                    settings.MAIL_SMTP_USERNAME,
                    settings.MAIL_SMTP_PASSWORD
                )

            smtp.send_message(message)


email_service = EmailService()
