import asyncio
import smtplib
from email.message import EmailMessage

from src.core.config.settings import settings
from src.core.logging.logger import logger


class EmailService:
    """
    Envía correos por SMTP. Si `settings.smtp_configured` es `False`
    (`SMTP_HOST`/`SMTP_FROM` sin definir, como en desarrollo local sin
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
                body
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
        body: str
    ) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.SMTP_FROM
        message["To"] = to
        message.set_content(body)

        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=10
        ) as smtp:
            smtp.ehlo()

            if smtp.has_extn("STARTTLS"):
                smtp.starttls()
                smtp.ehlo()

            if settings.SMTP_USERNAME:
                smtp.login(
                    settings.SMTP_USERNAME,
                    settings.SMTP_PASSWORD
                )

            smtp.send_message(message)


email_service = EmailService()
