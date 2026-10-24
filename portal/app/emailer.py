"""Minimal e-mail sending. Without SMTP_HOST, messages go to DATA_DIR/outbox."""
from __future__ import annotations

import logging
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path

from .config import Settings

log = logging.getLogger("wp-portal.email")

Attachment = tuple[str, bytes, str]  # filename, content, mime type like "application/pdf"


def send_email(settings: Settings, to: list[str], subject: str, body: str,
               attachments: list[Attachment] | None = None, cc: list[str] | None = None) -> None:
    to = [t for t in to if t]
    cc = [c for c in (cc or []) if c]
    if not to:
        log.warning("No recipient for e-mail %r; skipped", subject)
        return
    msg = EmailMessage()
    msg["From"] = settings.mail_from
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg.set_content(body)
    for filename, content, mime in attachments or []:
        maintype, _, subtype = mime.partition("/")
        msg.add_attachment(content, maintype=maintype, subtype=subtype or "octet-stream",
                           filename=filename)

    if not settings.smtp_host:
        outbox: Path = settings.outbox_dir
        outbox.mkdir(parents=True, exist_ok=True)
        path = outbox / f"{time.time_ns()}.eml"
        path.write_bytes(bytes(msg))
        log.info("SMTP not configured; e-mail written to %s", path)
        return

    recipients = to + cc
    if settings.smtp_ssl:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
    with server:
        if not settings.smtp_ssl:
            server.ehlo()
            if server.has_extn("STARTTLS"):
                server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg, to_addrs=recipients)
    log.info("E-mail %r sent to %s", subject, recipients)
