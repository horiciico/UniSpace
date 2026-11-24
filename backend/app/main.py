from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import COOKIE_SECURE, SESSION_MAX_AGE_SECONDS, SESSION_SECRET_KEY
from app.routers import auth, bookings, classrooms, health, lookups, schedule, study_profile

# Tables come from Alembic migrations only (D-002). The backend container runs
# `alembic upgrade head` before it starts (see docker-compose.yml).
app = FastAPI(title="UniSpace API")

# Signed, HttpOnly cookie. Holds the login (user_id) and the OAuth state during sign-in.
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    max_age=SESSION_MAX_AGE_SECONDS,
    same_site="lax",
    https_only=COOKIE_SECURE,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(classrooms.router)
app.include_router(lookups.router)
app.include_router(schedule.router)
app.include_router(study_profile.router)
app.include_router(bookings.router)