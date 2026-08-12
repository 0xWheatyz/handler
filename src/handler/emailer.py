"""Outbound email (invites + password resets) over plain SMTP.

Stdlib ``smtplib`` behind one function, configured entirely from the environment
(``SMTP_HOST`` et al — see ``config.Settings``). When SMTP is not configured the API
degrades gracefully: admin-facing flows return the invite/reset *link* in the response
instead of mailing it, and the self-serve forgot-password flow reports that email is
unavailable. Nothing in the control layer depends on this module.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formatdate

from .config import Settings, get_settings


class EmailError(Exception):
    """SMTP delivery failed (or email is not configured)."""


def configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.smtp_host and settings.smtp_from)


def send(to: str, subject: str, body: str, settings: Settings | None = None) -> None:
    """Deliver one plain-text message; raises :class:`EmailError` on any failure."""
    settings = settings or get_settings()
    if not configured(settings):
        raise EmailError("SMTP is not configured (set SMTP_HOST and SMTP_FROM)")

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message.set_content(body)

    try:
        if settings.smtp_ssl:
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=15
            )
        else:
            client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        with client:
            if settings.smtp_starttls and not settings.smtp_ssl:
                client.starttls()
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password or "")
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailError(f"could not send email via {settings.smtp_host}: {exc}") from exc
