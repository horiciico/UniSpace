"""Email (step 1): one way to send a message, with two backends chosen in config.

`console` logs the message; `smtp` sends it with STARTTLS. Callers queue a message on the request's
BackgroundTasks, so the response does not wait for the server. A failed send is logged with the
subject and the error's type only: never the body, the address or the password (AGENTS.md).
"""

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage as MailMessage
from email.utils import formataddr

from fastapi import BackgroundTasks

from app import config

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 10
HIDDEN_PLACEHOLDER = "[link hidden]"


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str
    # A part of the body that is a secret (an invite link). The console backend never prints it.
    hidden: str | None = None


def queue(background_tasks: BackgroundTasks, message: EmailMessage) -> None:
    """Sends the message after the response is returned."""
    background_tasks.add_task(send, message)


def send(message: EmailMessage) -> None:
    """Sends the message now. Never raises: a failure is logged and the caller carries on."""
    try:
        if config.EMAIL_BACKEND == "smtp":
            _smtp(message)
        else:
            _console(message)
    except Exception as error:
        logger.error(
            "Email '%s' was not sent (%s).",
            message.subject,
            type(error).__name__,
        )


def _console(message: EmailMessage) -> None:
    body = message.body
    if message.hidden:
        body = body.replace(message.hidden, HIDDEN_PLACEHOLDER)
    logger.info("Email (console backend) · %s\n%s", message.subject, body)


def _smtp(message: EmailMessage) -> None:
    mail = MailMessage()
    mail["From"] = formataddr((config.SMTP_FROM_NAME, config.SMTP_FROM_EMAIL))
    mail["To"] = message.to
    mail["Subject"] = message.subject
    mail.set_content(message.body)
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as server:
        if config.SMTP_USE_TLS:
            server.starttls(context=ssl.create_default_context())
        if config.SMTP_USERNAME:
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        server.send_message(mail)
