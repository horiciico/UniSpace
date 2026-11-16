import uuid

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import get_current_user, oauth, resolve_user, start_session
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


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/auth/logout", status_code=204)
def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=204)
