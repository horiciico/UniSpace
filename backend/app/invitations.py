"""Invitations (D-025): an admin invites an email with a non-admin role; a first sign-in admits it.

An invitation is pending until it is used (accepted) or revoked. It expires 7 days after it is
created (the table default). At most one pending invitation per email (the partial unique index).
"""

import logging
import secrets

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import InvitationStatus, UserInvitation

logger = logging.getLogger(__name__)

INVITE_PATH = "/login"


def new_token() -> str:
    """A cryptographically random, URL-safe token (43 characters)."""
    return secrets.token_urlsafe(32)


def invite_url(token: str) -> str:
    return f"{INVITE_PATH}?invite={token}"


def revoke_expired_pending(db: Session, email: str) -> None:
    """An expired pending invitation for this email is revoked, so a new one can be made."""
    db.execute(
        update(UserInvitation)
        .where(
            func.lower(UserInvitation.email) == email,
            UserInvitation.status == InvitationStatus.PENDING,
            UserInvitation.expires_at <= func.now(),
        )
        .values(status=InvitationStatus.REVOKED)
    )


def active_pending(db: Session, email: str) -> UserInvitation | None:
    """The pending, unexpired invitation for this email, if any."""
    return db.scalar(
        select(UserInvitation).where(
            func.lower(UserInvitation.email) == email,
            UserInvitation.status == InvitationStatus.PENDING,
            UserInvitation.expires_at > func.now(),
        )
    )


def usable_for_sign_in(db: Session, token: str, email: str) -> UserInvitation | None:
    """The invitation a sign-in may use: token and email match, pending and unexpired."""
    return db.scalar(
        select(UserInvitation).where(
            UserInvitation.token == token,
            UserInvitation.email == email,
            UserInvitation.status == InvitationStatus.PENDING,
            UserInvitation.expires_at > func.now(),
        )
    )


def announce(invitation: UserInvitation) -> None:
    """The place where an invitation is sent (SMTP later). The link is not logged: it is a secret
    (AGENTS.md), and the admin copies it from the pending list."""
    logger.info(
        "Invitation %s created for a %s account.",
        invitation.id,
        invitation.role.value,
    )
