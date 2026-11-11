import os

# Set by docker-compose from .env. Fails fast when missing, so no default credentials live in code.
DATABASE_URL: str = os.environ["DATABASE_URL"]
