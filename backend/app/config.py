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
