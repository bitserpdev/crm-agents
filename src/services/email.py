import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from core.logger import logger
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class EmailMessage:
    to: str | list[str]
    subject: str
    body_text: str  # plain text — always required
    body_html: Optional[str] = None  # optional HTML version
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: Optional[str] = None
    attachments: list[Path] = field(default_factory=list)


class EmailService:
    """
    Single reusable SMTP email sender.
    All agents and scheduler import this instead of building their own.

    Usage:
        svc = EmailService()
        svc.send(EmailMessage(to="x@y.com", subject="Hi", body_text="Hello"))
    """

    def __init__(self):
        self.host = os.getenv("SMTP_HOST")
        self.port = int(os.getenv("SMTP_PORT", 587))
        self.user = os.getenv("SMTP_USER")
        self.password = os.getenv("SMTP_PASSWORD")

        if not all([self.host, self.user, self.password]):
            raise EnvironmentError(
                "SMTP_HOST, SMTP_USER, SMTP_PASSWORD must all be set"
            )

    def send(self, message: EmailMessage) -> bool:
        """
        Send a single email. Returns True on success, False on failure.
        Never raises — logs the error and returns False so callers
        can decide whether to retry.
        """
        try:
            msg = self._build_mime(message)
            recipients = self._flatten(message.to) + message.cc + message.bcc

            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.sendmail(self.user, recipients, msg.as_string())

            logger.info("[email] Sent", subject=message.subject, to=message.to)
            return True

        except Exception as e:
            logger.error(
                "[email] Send failed",
                subject=message.subject,
                to=message.to,
                error=str(e),
            )
            return False

    def send_bulk(self, messages: list[EmailMessage]) -> dict:
        """
        Send multiple emails over a single SMTP connection.
        Returns {"sent": int, "failed": int}.
        """
        sent = failed = 0
        try:
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.user, self.password)

                for message in messages:
                    try:
                        mime = self._build_mime(message)
                        recipients = (
                            self._flatten(message.to) + message.cc + message.bcc
                        )
                        server.sendmail(self.user, recipients, mime.as_string())
                        sent += 1
                        logger.info(
                            "[email] Bulk sent", subject=message.subject, to=message.to
                        )
                    except Exception as e:
                        failed += 1
                        logger.error(
                            "[email] Bulk item failed",
                            subject=message.subject,
                            to=message.to,
                            error=str(e),
                        )

        except Exception as e:
            logger.error("[email] Bulk SMTP connection failed", error=str(e))

        logger.info("[email] Bulk complete", sent=sent, failed=failed)
        return {"sent": sent, "failed": failed}

    def _build_mime(self, message: EmailMessage) -> MIMEMultipart:
        mime = (
            MIMEMultipart("alternative")
            if not message.attachments
            else MIMEMultipart("mixed")
        )

        mime["Subject"] = message.subject
        mime["From"] = self.user
        mime["To"] = ", ".join(self._flatten(message.to))

        if message.cc:
            mime["Cc"] = ", ".join(message.cc)
        if message.reply_to:
            mime["Reply-To"] = message.reply_to

        # Always attach plain text first (fallback for email clients)
        mime.attach(MIMEText(message.body_text, "plain"))
        if message.body_html:
            mime.attach(MIMEText(message.body_html, "html"))

        for path in message.attachments:
            self._attach_file(mime, path)

        return mime

    def _attach_file(self, mime: MIMEMultipart, path: Path):
        try:
            with open(path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={path.name}")
            mime.attach(part)
        except Exception as e:
            logger.error("[email] Attachment failed", file=str(path), error=str(e))

    @staticmethod
    def _flatten(to: str | list[str]) -> list[str]:
        return [to] if isinstance(to, str) else to


# ── Module-level singleton — import and use directly ─────────────────────────
email_service = EmailService()
