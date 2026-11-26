import logging

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import COOKIE_SECURE, SESSION_MAX_AGE_SECONDS, SESSION_SECRET_KEY
from app.routers import (
    admin_bookings,
    admin_users,
    auth,
    bookings,
    classroom_attributes,
    classrooms,
    health,
    lookups,
    professors,
    schedule,
    study_profile,
)

# The app's INFO lines (a sent email, a console email) reach the container log. Without this
# Python drops them.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

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
app.include_router(professors.router)
app.include_router(study_profile.router)
app.include_router(bookings.router)
app.include_router(admin_bookings.router)
app.include_router(admin_users.router)
app.include_router(classroom_attributes.router)
