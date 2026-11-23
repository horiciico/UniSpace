import uuid

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import (
    admin_credentials_match,
    ensure_admin_user,
    get_current_user,
    oauth,
    resolve_user,
    start_session,
)
from app.config import GOOGLE_REDIRECT_URI, POST_LOGIN_URL
from app.db import get_db
from app.models import Role, User

router = APIRouter(tags=["auth"])


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    role: Role


@router.get("/auth/login")
async def login(request: Request):
    return await oauth.google.authorize_redirect(request, GOOGLE_REDIRECT_URI)


@router.get("/auth/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        raise HTTPException(400, "Google sign-in failed. Please try again.") from error
    claims = token.get("userinfo")
    if not claims:
        raise HTTPException(400, "Google sign-in failed. Please try again.")

    user = await run_in_threadpool(resolve_user, db, dict(claims))
    start_session(request, user)
    return RedirectResponse(POST_LOGIN_URL, status_code=303)


class AdminLogin(BaseModel):
    username: str
    password: str


@router.post("/auth/admin-login", response_model=UserOut)
def admin_login(body: AdminLogin, request: Request, db: Session = Depends(get_db)) -> User:
    """The admin sign-in (D-021): the same session cookie as Google sign-in, with role ADMIN."""
    if not admin_credentials_match(body.username, body.password):
        raise HTTPException(401, "Invalid admin credentials.")
    user = ensure_admin_user(db, body.username)
    start_session(request, user)
    return user


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/auth/logout", status_code=204)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=204)


@router.get("/auth/admin", status_code=204)
def admin_check(user: User = Depends(get_current_user)) -> Response:
    """Asked by nginx (auth_request) before it serves /admin/ pages."""
    if user.role != Role.ADMIN:
        raise HTTPException(403, "Admins only.")
    return Response(status_code=204)
