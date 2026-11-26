"""Email (step 1): the settings and the EmailService, with two backends.

`console` logs the message and never shows the hidden part (an invite link is a secret, AGENTS.md).
`smtp` sends it with STARTTLS. A failed send is logged without the body, the address or the
password, and never reaches the request: the service is queued on BackgroundTasks.
No test opens a real connection: the SMTP class is replaced with a fake.
"""

import asyncio
import importlib
import logging
import smtplib
from datetime import UTC, date, datetime, time
from email.message import EmailMessage as MailMessage
from pathlib import Path

import pytest
from fastapi import BackgroundTasks

from app import config, email_service
from app.email_service import (
    EmailMessage,
    queue,
    send,
    send_booking_approved_email,
    send_booking_rejected_email,
    send_email,
    send_invitation_email,
)

EMAIL_SETTINGS = [
    "EMAIL_BACKEND",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_FROM_EMAIL",
    "SMTP_FROM_NAME",
    "SMTP_USE_TLS",
    "APP_BASE_URL",
]
LINK = "https://unispace.test/login?invite=SECRET-TOKEN-123"


class FakeSMTP:
    """Records what the service does with the server. Set `fail` to make send_message raise."""

    instances: list["FakeSMTP"] = []
    fail: Exception | None = None

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self.started_tls = False
        self.logged_in: tuple[str, str] | None = None
        self.sent: list[MailMessage] = []
        FakeSMTP.instances.append(self)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def starttls(self, context: object = None) -> None:
        self.started_tls = True

    def login(self, user: str, password: str) -> None:
        self.logged_in = (user, password)

    def send_message(self, mail: MailMessage) -> None:
        if FakeSMTP.fail is not None:
            raise FakeSMTP.fail
        self.sent.append(mail)


@pytest.fixture(autouse=True)
def service_logger_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # The migration fixture runs alembic's fileConfig, which disables loggers created before it.
    # The service's logger is switched back on for each test, so its records reach caplog.
    monkeypatch.setattr(email_service.logger, "disabled", False)


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[FakeSMTP]:
    FakeSMTP.instances = []
    FakeSMTP.fail = None
    monkeypatch.setattr("app.email_service.smtplib.SMTP", FakeSMTP)
    return FakeSMTP


def _message(body: str = "Hello, Sală 4.", hidden: str | None = None) -> EmailMessage:
    return EmailMessage(to="guest@example.test", subject="Test subject", body=body, hidden=hidden)


# ---- Settings ---------------------------------------------------------------


def test_defaults_when_no_email_settings_are_set(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in EMAIL_SETTINGS:
        monkeypatch.delenv(name, raising=False)
    try:
        importlib.reload(config)
        assert config.EMAIL_BACKEND == "console"
        assert config.SMTP_HOST == "smtp.gmail.com"
        assert config.SMTP_PORT == 587
        assert config.SMTP_USERNAME == ""
        assert config.SMTP_PASSWORD == ""
        assert config.SMTP_FROM_EMAIL == "noreply@unispace.local"
        assert config.SMTP_FROM_NAME == "UniSpace"
        assert config.SMTP_USE_TLS is True
        assert config.APP_BASE_URL == "http://localhost:8080"
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_settings_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMAIL_BACKEND", "smtp")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setenv("SMTP_USE_TLS", "false")
    try:
        importlib.reload(config)
        assert config.EMAIL_BACKEND == "smtp"
        assert config.SMTP_PORT == 2525
        assert config.SMTP_USE_TLS is False
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_an_unknown_backend_fails_at_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMAIL_BACKEND", "carrier-pigeon")
    try:
        with pytest.raises(RuntimeError, match="EMAIL_BACKEND"):
            importlib.reload(config)
    finally:
        monkeypatch.undo()
        importlib.reload(config)


# ---- The console backend ----------------------------------------------------


def test_console_logs_the_message_and_hides_the_link(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(config, "EMAIL_BACKEND", "console")
    caplog.set_level(logging.INFO, logger="app.email_service")

    send(_message(body=f"Your invitation: {LINK}", hidden=LINK))

    assert "Test subject" in caplog.text
    assert "Your invitation:" in caplog.text
    assert "[link hidden]" in caplog.text
    assert "SECRET-TOKEN-123" not in caplog.text
    assert "guest@example.test" not in caplog.text


def test_console_opens_no_connection(
    monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP]
) -> None:
    monkeypatch.setattr(config, "EMAIL_BACKEND", "console")

    send(_message())

    assert fake_smtp.instances == []


# ---- The SMTP backend -------------------------------------------------------


def _smtp_settings(monkeypatch: pytest.MonkeyPatch, **values: object) -> None:
    defaults: dict[str, object] = {
        "EMAIL_BACKEND": "smtp",
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PORT": 587,
        "SMTP_USERNAME": "",
        "SMTP_PASSWORD": "",
        "SMTP_FROM_EMAIL": "noreply@unispace.local",
        "SMTP_FROM_NAME": "UniSpace",
        "SMTP_USE_TLS": True,
    }
    defaults.update(values)
    for name, value in defaults.items():
        monkeypatch.setattr(config, name, value)


def test_smtp_connects_with_starttls_and_sends_the_full_message(
    monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP]
) -> None:
    _smtp_settings(monkeypatch, SMTP_USERNAME="mailer", SMTP_PASSWORD="pw-123")

    send(_message(body=f"Link: {LINK}", hidden=LINK))

    server = fake_smtp.instances[0]
    assert (server.host, server.port) == ("smtp.example.test", 587)
    assert server.started_tls is True
    assert server.logged_in == ("mailer", "pw-123")
    sent = server.sent[0]
    assert sent["To"] == "guest@example.test"
    assert sent["Subject"] == "Test subject"
    assert sent["From"] == "UniSpace <noreply@unispace.local>"
    # The link is only hidden from the console; the recipient must receive it.
    assert LINK in sent.get_body(preferencelist=("plain",)).get_content()


def test_smtp_keeps_romanian_text_intact(
    monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP]
) -> None:
    _smtp_settings(monkeypatch)

    send(
        EmailMessage(
            to="guest@example.test", subject="Rezervare aprobată", body="Sală: Aula Ș, ora 10–12."
        )
    )

    sent = fake_smtp.instances[0].sent[0]
    assert sent["Subject"] == "Rezervare aprobată"
    assert "Aula Ș, ora 10–12." in sent.get_body(preferencelist=("plain",)).get_content()


def test_smtp_skips_starttls_and_login_when_not_configured(
    monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP]
) -> None:
    _smtp_settings(monkeypatch, SMTP_USE_TLS=False)

    send(_message())

    server = fake_smtp.instances[0]
    assert server.started_tls is False
    assert server.logged_in is None
    assert len(server.sent) == 1


def test_a_failed_smtp_send_is_logged_without_secrets_and_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
    fake_smtp: type[FakeSMTP],
    caplog: pytest.LogCaptureFixture,
) -> None:
    _smtp_settings(monkeypatch, SMTP_PASSWORD="pw-very-secret")
    fake_smtp.fail = smtplib.SMTPAuthenticationError(535, b"bad credentials for guest@example.test")
    caplog.set_level(logging.ERROR, logger="app.email_service")

    send(_message(body=f"Link: {LINK}", hidden=LINK))

    assert "Test subject" in caplog.text
    assert "SMTPAuthenticationError" in caplog.text
    assert "pw-very-secret" not in caplog.text
    assert "SECRET-TOKEN-123" not in caplog.text
    assert "Hello, Sală 4." not in caplog.text
    assert "guest@example.test" not in caplog.text


# ---- Queuing ----------------------------------------------------------------


def test_queue_sends_later_on_the_background_tasks(
    monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP]
) -> None:
    _smtp_settings(monkeypatch)
    tasks = BackgroundTasks()

    queue(tasks, _message())

    assert len(tasks.tasks) == 1
    assert fake_smtp.instances == []
    asyncio.run(tasks())
    assert len(fake_smtp.instances[0].sent) == 1


# ---- Multipart and the bilingual templates (step 1b) ------------------------


def test_an_html_body_is_sent_as_multipart_alternative(
    monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP]
) -> None:
    _smtp_settings(monkeypatch)

    send_email("guest@example.test", "Subject", "plain text", "<p>html text</p>")

    mail = fake_smtp.instances[0].sent[0]
    assert mail.get_content_type() == "multipart/alternative"
    assert mail.get_body(("plain",)).get_content().strip() == "plain text"
    assert "<p>html text</p>" in mail.get_body(("html",)).get_content()


def test_the_console_logs_the_text_part_only(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(config, "EMAIL_BACKEND", "console")
    caplog.set_level(logging.INFO, logger="app.email_service")

    send_email("guest@example.test", "Subject", "plain words", "<p>markup-only</p>")

    assert "plain words" in caplog.text
    assert "markup-only" not in caplog.text


def test_the_invitation_is_bilingual_and_its_link_is_hidden_in_the_console(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(config, "EMAIL_BACKEND", "console")
    caplog.set_level(logging.INFO, logger="app.email_service")

    send_invitation_email(
        "guest@example.test", "STUDENT_ORG", LINK, datetime(2026, 12, 3, 10, 30, tzinfo=UTC)
    )

    assert "Organizație studențească" in caplog.text
    assert "Student organization" in caplog.text
    assert "03.12.2026 12:30 (ora României / Romanian time)" in caplog.text
    assert "[link hidden]" in caplog.text
    assert "SECRET-TOKEN-123" not in caplog.text
    assert "guest@example.test" not in caplog.text


def test_the_invitation_sent_over_smtp_contains_the_real_link(
    monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP]
) -> None:
    _smtp_settings(monkeypatch)

    send_invitation_email(
        "guest@example.test", "PROFESSOR", LINK, datetime(2026, 12, 3, 10, 30, tzinfo=UTC)
    )

    mail = fake_smtp.instances[0].sent[0]
    assert mail["Subject"] == "Invitație în UniSpace · Invitation to UniSpace"
    assert LINK in mail.get_body(("plain",)).get_content()
    assert f'href="{LINK}"' in mail.get_body(("html",)).get_content()


def test_the_approved_email_names_the_room_date_time_and_title(
    monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP]
) -> None:
    _smtp_settings(monkeypatch)

    send_booking_approved_email(
        "guest@example.test", "Aula Ș", date(2026, 12, 5), time(10, 0), time(12, 0), "Seminar"
    )

    mail = fake_smtp.instances[0].sent[0]
    text = mail.get_body(("plain",)).get_content()
    assert "Aula Ș" in text
    assert "05.12.2026" in text
    assert "10:00–12:00" in text
    assert "Seminar" in text
    assert "aprobată" in text and "approved" in text


def test_user_text_is_escaped_in_the_html_part(
    monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP]
) -> None:
    _smtp_settings(monkeypatch)

    send_booking_rejected_email(
        "guest@example.test",
        "<i>Room</i>",
        date(2026, 12, 5),
        time(10, 0),
        time(12, 0),
        "<b>Seminar</b>",
        '<img src="x" onerror="alert(1)">',
    )

    mail = fake_smtp.instances[0].sent[0]
    html_part = mail.get_body(("html",)).get_content()
    assert "&lt;b&gt;Seminar&lt;/b&gt;" in html_part
    assert "&lt;i&gt;Room&lt;/i&gt;" in html_part
    assert "&lt;img" in html_part
    assert "<b>Seminar</b>" not in html_part
    assert '<img src="x"' not in html_part  # the logo is an <img>; the user's tag must not be


def test_the_rejection_gives_the_reason_only_when_there_is_one(
    monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP]
) -> None:
    _smtp_settings(monkeypatch)

    send_booking_rejected_email(
        "guest@example.test",
        "Aula Ș",
        date(2026, 12, 5),
        time(10, 0),
        time(12, 0),
        "Seminar",
        "Sală ocupată",
    )
    send_booking_rejected_email(
        "guest@example.test", "Aula Ș", date(2026, 12, 5), time(10, 0), time(12, 0), "Seminar", None
    )

    with_reason, without_reason = (server.sent[0] for server in fake_smtp.instances)
    assert "Motiv: Sală ocupată" in with_reason.get_body(("plain",)).get_content()
    assert "Reason: Sală ocupată" in with_reason.get_body(("plain",)).get_content()
    assert "Motiv" not in without_reason.get_body(("plain",)).get_content()
    assert "Reason" not in without_reason.get_body(("plain",)).get_content()


def test_blank_settings_fall_back_to_the_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    # .env.example leaves some values blank; a blank value must not stop the app from starting.
    for name in EMAIL_SETTINGS:
        monkeypatch.setenv(name, "")
    try:
        importlib.reload(config)
        assert config.EMAIL_BACKEND == "console"
        assert config.SMTP_HOST == "smtp.gmail.com"
        assert config.SMTP_PORT == 587
        assert config.SMTP_FROM_EMAIL == "noreply@unispace.local"
        assert config.SMTP_FROM_NAME == "UniSpace"
        assert config.SMTP_USE_TLS is True
        assert config.APP_BASE_URL == "http://localhost:8080"
    finally:
        monkeypatch.undo()
        importlib.reload(config)


# ---- The logo (every HTML email) --------------------------------------------

LOGO_BYTES = (
    Path(__file__).resolve().parents[1] / "app" / "assets" / "brand-mark.png"
).read_bytes()


def _logo_parts(mail: MailMessage) -> list[MailMessage]:
    return [
        part
        for part in mail.walk()
        if part.get_content_type() == "image/png" and part["Content-ID"] == "<unispace-logo>"
    ]


@pytest.mark.parametrize(
    "send_it",
    [
        lambda: send_invitation_email(
            "guest@example.test", "STUDENT", LINK, datetime(2026, 12, 3, 10, 30, tzinfo=UTC)
        ),
        lambda: send_booking_approved_email(
            "guest@example.test", "Aula Ș", date(2026, 12, 5), time(10, 0), time(12, 0), "Seminar"
        ),
        lambda: send_booking_rejected_email(
            "guest@example.test",
            "Aula Ș",
            date(2026, 12, 5),
            time(10, 0),
            time(12, 0),
            "Seminar",
            None,
        ),
    ],
    ids=["invitation", "approved", "rejected"],
)
def test_every_html_email_carries_the_logo_inline(
    monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP], send_it
) -> None:
    _smtp_settings(monkeypatch)

    send_it()

    mail = fake_smtp.instances[0].sent[0]
    html_part = mail.get_body(("html",)).get_content()
    assert 'src="cid:unispace-logo"' in html_part
    logos = _logo_parts(mail)
    assert len(logos) == 1
    assert logos[0].get_payload(decode=True) == LOGO_BYTES
    assert logos[0].get_content_disposition() == "inline"


def test_the_plain_text_part_has_no_logo(
    monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP]
) -> None:
    _smtp_settings(monkeypatch)

    send_email("guest@example.test", "Subject", "plain text", "<p>html</p>")

    assert "cid:" not in fake_smtp.instances[0].sent[0].get_body(("plain",)).get_content()


def test_a_sent_email_is_logged_by_subject_only(
    monkeypatch: pytest.MonkeyPatch, fake_smtp: type[FakeSMTP], caplog: pytest.LogCaptureFixture
) -> None:
    # Visible in the container log, so a sent message can be seen without reading the mailbox.
    _smtp_settings(monkeypatch)
    caplog.set_level(logging.INFO, logger="app.email_service")

    send(_message())

    assert "Email 'Test subject' sent." in caplog.text
    assert "guest@example.test" not in caplog.text
