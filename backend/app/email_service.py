"""Email: one way to send a message, with two backends chosen in config.

`console` logs the text part; `smtp` sends it, with the HTML part as an alternative. Callers queue a
send on the request's BackgroundTasks, so the response does not wait for the server.
A failed send is logged with the subject and the error's type only: never the body,
the address or the password (AGENTS.md). The invite link is a secret: the console shows
`[link hidden]` in its place.

The three helpers (invitation, booking approved, booking rejected) write each message in Romanian
and English. User-supplied text is escaped in the HTML part.
"""

import html
import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import date, datetime, time
from email.message import EmailMessage as MailMessage
from email.utils import formataddr
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks

from app import config

logger = logging.getLogger(__name__)

# Times in emails are shown in Romanian local time.
LOCAL_TIME = ZoneInfo("Europe/Bucharest")

SMTP_TIMEOUT_SECONDS = 10
HIDDEN_PLACEHOLDER = "[link hidden]"


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str
    html: str | None = None
    # A part of the body that is a secret (an invite link). The console backend never prints it.
    hidden: str | None = None


def queue(background_tasks: BackgroundTasks, message: EmailMessage) -> None:
    """Sends the message after the response is returned."""
    background_tasks.add_task(send, message)


def send_email(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    hidden: str | None = None,
) -> None:
    """Sends the message now. Never raises: a failure is logged and the caller carries on."""
    send(EmailMessage(to=to_email, subject=subject, body=text_body, html=html_body, hidden=hidden))


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
    if message.html:
        mail.add_alternative(message.html, subtype="html")
        html_part = mail.get_body(("html",))
        assert html_part is not None  # set just above
        html_part.add_related(
            LOGO_PATH.read_bytes(),
            maintype="image",
            subtype="png",
            cid="<unispace-logo>",
            disposition="inline",
            filename="brand-mark.png",
        )
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as server:
        if config.SMTP_USE_TLS:
            server.starttls(context=ssl.create_default_context())
        if config.SMTP_USERNAME:
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        server.send_message(mail)
    logger.info("Email '%s' sent.", message.subject)


# ---- The messages -----------------------------------------------------------

ROLE_NAMES = {
    "STUDENT": ("Student", "Student"),
    "PROFESSOR": ("Profesor", "Professor"),
    "STUDENT_ORG": ("Organizație studențească", "Student organization"),
}
SECTION_BREAK = "\n\n---\n\n"
# The brand mark: attached to every HTML email and shown at the top of it (cid = its reference).
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "brand-mark.png"
LOGO_HTML = (
    '<p><img src="cid:unispace-logo" alt="UniSpace" width="40" height="40" '
    'style="vertical-align:middle"> <strong>UniSpace</strong></p>'
)


@dataclass(frozen=True)
class _Section:
    """One language of a message: an opening sentence, labelled rows, an optional closing sentence
    and an optional link. The text part and the HTML part are both drawn from these fields."""

    intro: str
    rows: list[tuple[str, str]] = field(default_factory=list)
    closing: str | None = None
    link_label: str | None = None
    link: str | None = None


def _render(sections: list[_Section]) -> tuple[str, str]:
    """The text part and the HTML part for the sections (one per language)."""
    texts: list[str] = []
    htmls: list[str] = []
    for section in sections:
        lines = [section.intro]
        lines += [f"{label}: {value}" for label, value in section.rows]
        if section.closing:
            lines.append(section.closing)
        if section.link:
            lines.append(f"{section.link_label}: {section.link}")
        texts.append("\n".join(lines))

        parts = [f"<p>{html.escape(section.intro)}</p>"]
        if section.rows:
            items = "".join(
                f"<li><strong>{html.escape(label)}:</strong> {html.escape(value)}</li>"
                for label, value in section.rows
            )
            parts.append(f"<ul>{items}</ul>")
        if section.closing:
            parts.append(f"<p>{html.escape(section.closing)}</p>")
        if section.link:
            href = html.escape(section.link, quote=True)
            parts.append(f'<p><a href="{href}">{html.escape(section.link_label or "")}</a></p>')
        htmls.append("".join(parts))
    body = "<hr>".join(f"<div>{part}</div>" for part in htmls)
    return SECTION_BREAK.join(texts), f"{LOGO_HTML}{body}"


def _day(day: date) -> str:
    return day.strftime("%d.%m.%Y")


def _span(start: time, end: time) -> str:
    return f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"


def send_invitation_email(to_email: str, role: str, invite_url: str, expires_at: datetime) -> None:
    """The invitation to sign in with the invited role. The link is hidden from the console."""
    role_ro, role_en = ROLE_NAMES.get(role, (role, role))
    expires = (
        expires_at.astimezone(LOCAL_TIME).strftime("%d.%m.%Y %H:%M")
        + " (ora României / Romanian time)"
    )
    text, html_body = _render(
        [
            _Section(
                intro=f"Ai fost invitat(ă) în UniSpace cu rolul {role_ro}.",
                closing=(
                    f"Invitația expiră la {expires}. Deschide linkul și autentifică-te "
                    "cu contul Google al acestei adrese de e-mail."
                ),
                link_label="Deschide invitația",
                link=invite_url,
            ),
            _Section(
                intro=f"You have been invited to UniSpace with the role {role_en}.",
                closing=(
                    f"The invitation expires on {expires}. Open the link and sign in "
                    "with the Google account of this email address."
                ),
                link_label="Open the invitation",
                link=invite_url,
            ),
        ]
    )
    send_email(
        to_email,
        "Invitație în UniSpace · Invitation to UniSpace",
        text,
        html_body,
        hidden=invite_url,
    )


def send_booking_approved_email(
    to_email: str,
    room_name: str,
    date: date,
    start_time: time,
    end_time: time,
    title: str,
) -> None:
    text, html_body = _render(
        [
            _Section(
                intro="Cererea ta de rezervare a fost aprobată.",
                rows=[
                    ("Sală", room_name),
                    ("Data", _day(date)),
                    ("Interval", _span(start_time, end_time)),
                    ("Titlu", title),
                ],
            ),
            _Section(
                intro="Your booking request has been approved.",
                rows=[
                    ("Room", room_name),
                    ("Date", _day(date)),
                    ("Time", _span(start_time, end_time)),
                    ("Title", title),
                ],
            ),
        ]
    )
    send_email(to_email, "Rezervare aprobată · Booking approved", text, html_body)


def send_booking_rejected_email(
    to_email: str,
    room_name: str,
    date: date,
    start_time: time,
    end_time: time,
    title: str,
    reason: str | None,
) -> None:
    """The rejection. The admin's reason is given in both languages, only when there is one."""
    ro_rows = [
        ("Sală", room_name),
        ("Data", _day(date)),
        ("Interval", _span(start_time, end_time)),
        ("Titlu", title),
    ]
    en_rows = [
        ("Room", room_name),
        ("Date", _day(date)),
        ("Time", _span(start_time, end_time)),
        ("Title", title),
    ]
    if reason:
        ro_rows.append(("Motiv", reason))
        en_rows.append(("Reason", reason))
    text, html_body = _render(
        [
            _Section(
                intro="Din păcate, cererea ta de rezervare a fost respinsă.",
                rows=ro_rows,
            ),
            _Section(
                intro="Unfortunately, your booking request has been rejected.",
                rows=en_rows,
            ),
        ]
    )
    send_email(to_email, "Rezervare respinsă · Booking rejected", text, html_body)
