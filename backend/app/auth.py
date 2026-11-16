"""Google sign-in: the "bouncer" that decides who may log in, and the login action itself."""
import uuid

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import GOOGLE_WEB_CLIENT_ID, GOOGLE_WEB_CLIENT_SECRET
from app.db import get_db
from app.models import Invitation, Role, User

UNIVERSITY_DOMAIN = "ulbsibiu.ro"
DENIED = "Access denied. Please use your institutional @ulbsibiu.ro account or request an invitation."

oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_WEB_CLIENT_ID,
    client_secret=GOOGLE_WEB_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def resolve_user(db: Session, claims: dict) -> User:
    """Apply the bouncer rules to Google's ID-token claims; return the user or raise 403."""
    sub = claims.get("sub")
    email = (claims.get("email") or "").strip().lower()
    if not sub or not email or claims.get("email_verified") is not True:
        raise HTTPException(403, "Your Google email address is not verified.")

    # The hd claim is only present for Workspace accounts; require the address to agree with it.
    is_university = claims.get("hd") == UNIVERSITY_DOMAIN
    if is_university and not email.endswith("@" + UNIVERSITY_DOMAIN):
        raise HTTPException(403, DENIED)

    user = db.scalar(select(User).where(User.google_sub == sub))
    if user is not None:
        return user

    name = claims.get("name") or email
    try:
        if is_university:
            user = _provision_university_user(db, sub, email, name)
        else:
            user = _accept_invitation(db, sub, email, name)
        db.commit()
    except IntegrityError:
        # Either a concurrent callback created this user first, or the email belongs to another account.
        db.rollback()
        user = db.scalar(select(User).where(User.google_sub == sub))
        if user is None:
            raise HTTPException(403, DENIED) from None
    return user


def _provision_university_user(db: Session, sub: str, email: str, name: str) -> User:
    """Every university account is a STUDENT; raising the role is an admin action (Q-009)."""
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        if existing.google_sub is not None:
            raise HTTPException(403, DENIED)
        existing.google_sub = sub
        return existing
    user = User(email=email, name=name, role=Role.STUDENT, google_sub=sub)
    db.add(user)
    db.flush()
    return user


def _accept_invitation(db: Session, sub: str, email: str, name: str) -> User:
    # One atomic UPDATE, so two simultaneous logins cannot both use the same invitation.
    role = db.execute(
        update(Invitation)
        .where(Invitation.email == email, Invitation.is_used.is_(False))
        .values(is_used=True)
        .returning(Invitation.role)
    ).scalar()
    if role is None:
        raise HTTPException(403, DENIED)
    user = User(email=email, name=name, role=role, google_sub=sub)
    db.add(user)
    db.flush()
    return user


def start_session(request: Request, user: User) -> None:
    """The login action: a fresh signed, HttpOnly session cookie (see SessionMiddleware in main.py)."""
    request.session.clear()  # drops the OAuth state and any earlier login
    request.session["user_id"] = str(user.id)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    try:
        user = db.get(User, uuid.UUID(request.session.get("user_id", "")))
    except ValueError:
        user = None
    if user is None:
        raise HTTPException(401, "Not signed in.")
    return user
