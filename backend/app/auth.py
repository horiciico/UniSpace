"""Google sign-in and admin sign-in: the "bouncer" that decides who may log in and handles login.

The role is resolved on every sign-in (D-020): professor list first, then the student association
hook, then a university address, otherwise the sign-in is refused. The admin signs in with the
credentials in `.env` (D-021).
"""

import secrets
import uuid

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config
from app.config import GOOGLE_WEB_CLIENT_ID, GOOGLE_WEB_CLIENT_SECRET
from app.db import get_db
from app.invitations import usable_for_sign_in
from app.models import InvitationStatus, Professor, Role, User

UNIVERSITY_DOMAIN = "ulbsibiu.ro"
DENIED = (
    "Access denied. Login is restricted to @ulbsibiu.ro accounts or registered faculty members."
)
# A login never lowers these roles (D-020).
KEPT_ROLES = (Role.ADMIN, Role.STUDENT_ORG)

oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_WEB_CLIENT_ID,
    client_secret=GOOGLE_WEB_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_student_association(email: str) -> bool:
    """Placeholder tier (D-020): student associations are not identified yet, so nobody is one."""
    return False


def decide_role(
    current: Role | None,
    is_professor: bool,
    is_association: bool,
    is_university: bool,
    invited: Role | None = None,
    admin_set: bool = False,
) -> Role | None:
    """The role for a sign-in, or None when the sign-in is refused (D-020, D-025)."""
    if admin_set and current is not None:
        return current  # a role an admin set holds from any address (D-025)
    if is_professor:
        target = Role.PROFESSOR
    elif invited is not None:
        target = invited  # a valid invitation for a new account (D-025)
    elif is_association:
        target = Role.STUDENT_ORG
    elif is_university:
        target = (
            Role.STUDENT
        )  # a former professor who is no longer listed goes back to STUDENT here
    else:
        return None
    return current if current in KEPT_ROLES else target


def resolve_user(db: Session, claims: dict, invite_token: str | None = None) -> User:
    """Apply the sign-in rules to Google's ID-token claims; return the user or raise 403."""
    sub = claims.get("sub")
    email = normalize_email(claims.get("email") or "")
    if not sub or not email or claims.get("email_verified") is not True:
        raise HTTPException(403, "Your Google email address is not verified.")

    # The hd claim is only present for Workspace accounts; a university address must agree with it.
    hd = claims.get("hd")
    if hd == UNIVERSITY_DOMAIN and not email.endswith("@" + UNIVERSITY_DOMAIN):
        raise HTTPException(403, DENIED)
    is_university = hd == UNIVERSITY_DOMAIN and email.endswith("@" + UNIVERSITY_DOMAIN)

    professor = db.scalar(select(Professor).where(Professor.email == email))
    user = db.scalar(select(User).where(User.google_sub == sub))
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
        if user is not None and user.google_sub is not None:
            raise HTTPException(403, DENIED)  # the address belongs to another Google account

    # An invitation admits a new account only, and only with its own token and email (D-025).
    invitation = None
    if user is None and professor is None and invite_token:
        invitation = usable_for_sign_in(db, invite_token, email)

    role = decide_role(
        user.role if user is not None else None,
        is_professor=professor is not None,
        is_association=not professor and is_student_association(email),
        is_university=is_university,
        invited=invitation.role if invitation is not None else None,
        admin_set=user is not None and user.role_set_by_admin,
    )
    if role is None:
        raise HTTPException(403, DENIED)

    professor_id = professor.id if professor is not None else None
    name = claims.get("name") or email
    picture = claims.get("picture")
    try:
        if user is None:
            user = User(
                email=email,
                name=name,
                role=role,
                google_sub=sub,
                professor_id=professor_id,
                picture=picture,
                role_set_by_admin=invitation is not None,
            )
            db.add(user)
        else:
            if user.google_sub is None:
                user.google_sub = sub
            user.role = role
            user.professor_id = professor_id
            user.picture = picture
        if invitation is not None:
            invitation.status = InvitationStatus.ACCEPTED
        db.commit()
    except IntegrityError:
        # A concurrent callback created the same account first.
        db.rollback()
        raise HTTPException(403, DENIED) from None
    return user


def admin_credentials_match(username: str, password: str) -> bool:
    """Constant-time comparison with the .env pair (D-021).

    An empty pair turns the admin sign-in off.
    """
    expected_user, expected_password = config.ADMIN_USERNAME, config.ADMIN_PASSWORD
    if not expected_user or not expected_password:
        return False
    user_ok = secrets.compare_digest(username.encode("utf-8"), expected_user.encode("utf-8"))
    password_ok = secrets.compare_digest(
        password.encode("utf-8"), expected_password.encode("utf-8")
    )
    return user_ok and password_ok


def ensure_admin_user(db: Session, username: str) -> User:
    """The admin's users row (email = the admin username, lower-case, role ADMIN). Created once."""
    email = normalize_email(username)
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=email, role=Role.ADMIN)
        db.add(user)
    else:
        user.role = Role.ADMIN
    db.commit()
    return user


def start_session(request: Request, user: User) -> None:
    """The login action: a fresh signed, HttpOnly session cookie (see main.py)."""
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
