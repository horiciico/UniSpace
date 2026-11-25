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
from email.message import EmailMessage as MailMessage

import pytest
from fastapi import BackgroundTasks

from app import config, email_service
from app.email_service import EmailMessage, queue, send

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
