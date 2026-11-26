import os

# Set by docker-compose from .env. Fails fast when missing, so no default credentials live in code.
DATABASE_URL: str = os.environ["DATABASE_URL"]

GOOGLE_WEB_CLIENT_ID: str = os.environ["GOOGLE_WEB_CLIENT_ID"]
GOOGLE_WEB_CLIENT_SECRET: str = os.environ["GOOGLE_WEB_CLIENT_SECRET"]
GOOGLE_REDIRECT_URI: str = os.environ["GOOGLE_REDIRECT_URI"]
SESSION_SECRET_KEY: str = os.environ["SESSION_SECRET_KEY"]

# The session cookie is Secure (HTTPS only) when true. Local dev runs on http, so it defaults to
# false; set it to true wherever the site is served over HTTPS.
COOKIE_SECURE: bool = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
SESSION_MAX_AGE_SECONDS: int = 8 * 60 * 60
# Where the browser lands after a successful sign-in (the frontend runs on another port locally).
POST_LOGIN_URL: str = os.environ.get("POST_LOGIN_URL", "/")

# Admin sign-in (D-021): one credential pair, plain text for now. Empty values turn it off.
ADMIN_USERNAME: str = os.environ.get("ADMIN_USERNAME", "")
ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "")


def _setting(name: str, default: str) -> str:
    """The environment value. A blank one (as .env.example leaves some) is the default."""
    return os.environ.get(name) or default


# Email. "console" logs each message (an invite link is hidden in the log); "smtp" sends it.
EMAIL_BACKEND: str = _setting("EMAIL_BACKEND", "console")
if EMAIL_BACKEND not in ("console", "smtp"):
    raise RuntimeError("EMAIL_BACKEND must be 'console' or 'smtp'.")
SMTP_HOST: str = _setting("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(_setting("SMTP_PORT", "587"))
# Optional. Leave empty when the server needs no sign-in.
SMTP_USERNAME: str = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD: str = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL: str = _setting("SMTP_FROM_EMAIL", "noreply@unispace.local")
SMTP_FROM_NAME: str = _setting("SMTP_FROM_NAME", "UniSpace")
# STARTTLS on the SMTP port (587). Turn it off only for a server on a trusted local network.
SMTP_USE_TLS: bool = _setting("SMTP_USE_TLS", "true").lower() == "true"
# The site's address, used to build the links in emails (the frontend runs on port 8080 locally).
APP_BASE_URL: str = _setting("APP_BASE_URL", "http://localhost:8080")
