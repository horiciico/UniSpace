"""Admin Users tab (D-025): list and search users, change a role, invite and revoke.

Every endpoint is for an ADMIN only (403 for others, 401 signed out).
"""

import re
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config
from app.auth import get_current_user
from app.db import get_db
from app.email_service import send_invitation_email
from app.invitations import (
    active_pending,
    announce,
    invite_url,
    new_token,
    revoke_expired_pending,
)
from app.models import Faculty, InvitationStatus, Role, StudentGroup, User, UserInvitation

router = APIRouter(prefix="/api/admin", tags=["admin users"])

EMAIL_SHAPE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(403, "Only an administrator can manage users.")
    return user


def _no_admin_role(value: Role) -> Role:
    if value == Role.ADMIN:
        raise ValueError("The ADMIN role cannot be given here.")
    return value


class RoleChange(BaseModel):
    role: Role

    @field_validator("role")
    @classmethod
    def not_admin(cls, value: Role) -> Role:
        return _no_admin_role(value)


class InvitationIn(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=EMAIL_SHAPE.pattern)
    role: Role

    @field_validator("email")
    @classmethod
    def lower_case(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("role")
    @classmethod
    def not_admin(cls, value: Role) -> Role:
        return _no_admin_role(value)


def _like_contains(text: str) -> str:
    """A LIKE pattern that matches `text` as a plain substring (% and _ are not wildcards)."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _user_out(user: User, faculty_name: str | None, group_name: str | None) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role.value,
        "faculty_name": faculty_name,
        "study_formation_name": group_name,
        "created_at": user.created_at.isoformat(),
    }


def _invitation_out(invitation: UserInvitation) -> dict:
    return {
        "id": str(invitation.id),
        "email": invitation.email,
        "role": invitation.role.value,
        "token": invitation.token,
        "invite_url": invite_url(invitation.token),
        "expires_at": invitation.expires_at.isoformat(),
        "created_at": invitation.created_at.isoformat(),
    }


@router.get("/users")
def list_users(
    role: Role | None = None,
    search: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Users by email (A to Z), filtered by role and by a part of the email (any case)."""
    conditions = []
    if role is not None:
        conditions.append(User.role == role)
    if search is not None and search.strip():
        conditions.append(User.email.ilike(_like_contains(search.strip().lower()), escape="\\"))

    total = db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0
    rows = db.execute(
        select(User, Faculty.name, StudentGroup.name)
        .outerjoin(Faculty, Faculty.id == User.faculty_id)
        .outerjoin(StudentGroup, StudentGroup.id == User.study_formation_id)
        .where(*conditions)
        .order_by(User.email, User.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "items": [_user_out(user, faculty, group) for user, faculty, group in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.patch("/users/{user_id}/role")
def change_role(
    user_id: uuid.UUID,
    body: RoleChange,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Set a non-admin role. The role is kept on later sign-ins (D-025)."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found.")
    if user.role == Role.ADMIN:
        raise HTTPException(403, "An administrator's role cannot be changed here.")
    user.role = body.role
    user.role_set_by_admin = True
    db.commit()
    faculty = db.get(Faculty, user.faculty_id) if user.faculty_id else None
    group = db.get(StudentGroup, user.study_formation_id) if user.study_formation_id else None
    return _user_out(user, faculty.name if faculty else None, group.name if group else None)


@router.get("/invitations")
def list_invitations(
    admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[dict]:
    """Pending invitations that have not expired, newest first."""
    rows = db.scalars(
        select(UserInvitation)
        .where(
            UserInvitation.status == InvitationStatus.PENDING,
            UserInvitation.expires_at > func.now(),
        )
        .order_by(UserInvitation.created_at.desc(), UserInvitation.id)
    ).all()
    return [_invitation_out(invitation) for invitation in rows]


@router.post("/invitations", status_code=201, response_model=None)
def create_invitation(
    body: InvitationIn,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    """Invite an email with a non-admin role. The admin copies the link from the pending list, and
    the invitation is also emailed (after the save; a failed email does not fail the request)."""
    existing = db.scalar(select(User).where(func.lower(User.email) == body.email))
    if existing is not None:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "User already exists",
                "existing_user": {"email": existing.email, "role": existing.role.value},
            },
        )

    revoke_expired_pending(db, body.email)
    if active_pending(db, body.email) is not None:
        raise HTTPException(409, "An invitation for this email is already pending.")

    invitation = UserInvitation(
        email=body.email,
        role=body.role,
        token=new_token(),
        invited_by=admin.id,
    )
    db.add(invitation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # a concurrent invitation for the same email won the race
        raise HTTPException(409, "An invitation for this email is already pending.") from None
    announce(invitation)
    background_tasks.add_task(
        send_invitation_email,
        invitation.email,
        invitation.role.value,
        f"{config.APP_BASE_URL.rstrip('/')}{invite_url(invitation.token)}",
        invitation.expires_at,
    )
    return _invitation_out(invitation)


@router.delete("/invitations/{invitation_id}", status_code=204)
def revoke_invitation(
    invitation_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    invitation = db.get(UserInvitation, invitation_id)
    if invitation is None:
        raise HTTPException(404, "Invitation not found.")
    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(409, "Only a pending invitation can be revoked.")
    invitation.status = InvitationStatus.REVOKED
    db.commit()
    return Response(status_code=204)
