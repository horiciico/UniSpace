"""user_invitations table: schema and constraints (admin Users tab, step 1). Real PostgreSQL."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import InvitationStatus, Role, User, UserInvitation


def add_invitation(db: Session, email: str = "ion@ulbsibiu.ro", **fields) -> UserInvitation:
    values = {
        "email": email,
        "role": Role.STUDENT_ORG,
        "token": uuid.uuid4().hex,
        "status": InvitationStatus.PENDING,
    }
    values.update(fields)
    invitation = UserInvitation(**values)
    db.add(invitation)
    db.flush()
    return invitation


def test_table_has_the_agreed_columns(db: Session) -> None:
    columns = {c["name"]: c for c in inspect(db.connection()).get_columns("user_invitations")}

    assert set(columns) == {
        "id",
        "email",
        "role",
        "token",
        "invited_by",
        "status",
        "expires_at",
        "created_at",
    }
    assert str(columns["email"]["type"]) == "VARCHAR(255)"
    assert columns["email"]["nullable"] is False
    assert str(columns["token"]["type"]) == "VARCHAR(128)"
    assert columns["token"]["nullable"] is False
    assert columns["invited_by"]["nullable"] is True
    assert columns["status"]["nullable"] is False
    assert columns["expires_at"]["nullable"] is False
    assert columns["expires_at"]["type"].timezone is True
    assert columns["created_at"]["type"].timezone is True
    assert columns["created_at"]["nullable"] is False


def test_status_is_a_native_enum_with_three_values(db: Session) -> None:
    labels = db.scalars(
        text(
            "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
            "WHERE t.typname = 'invitation_status' ORDER BY e.enumsortorder"
        )
    ).all()
    assert list(labels) == ["pending", "accepted", "revoked"]


def test_token_is_unique(db: Session) -> None:
    add_invitation(db, "a@ulbsibiu.ro", token="same-token")
    with pytest.raises(IntegrityError), db.begin_nested():
        add_invitation(db, "b@ulbsibiu.ro", token="same-token")


def test_email_is_stored_in_lower_case(db: Session) -> None:
    with pytest.raises(IntegrityError), db.begin_nested():
        add_invitation(db, "Ion@ulbsibiu.ro")


def test_only_one_pending_invitation_per_email(db: Session) -> None:
    add_invitation(db, "ion@ulbsibiu.ro")
    with pytest.raises(IntegrityError), db.begin_nested():
        add_invitation(db, "ion@ulbsibiu.ro")


def test_an_accepted_or_revoked_invitation_does_not_block_a_new_one(db: Session) -> None:
    add_invitation(db, "ion@ulbsibiu.ro", status=InvitationStatus.ACCEPTED)
    add_invitation(db, "ion@ulbsibiu.ro", status=InvitationStatus.REVOKED)
    add_invitation(db, "ion@ulbsibiu.ro", status=InvitationStatus.PENDING)  # the one active invite
    with pytest.raises(IntegrityError), db.begin_nested():
        add_invitation(db, "ion@ulbsibiu.ro", status=InvitationStatus.PENDING)


def test_expiry_defaults_to_seven_days_after_creation(db: Session) -> None:
    invitation = UserInvitation(
        email="ion@ulbsibiu.ro", role=Role.PROFESSOR, token="default-expiry-token"
    )
    db.add(invitation)
    db.flush()
    db.refresh(invitation)

    assert invitation.status == InvitationStatus.PENDING
    assert invitation.created_at is not None
    assert invitation.expires_at - invitation.created_at == timedelta(days=7)


def test_deleting_the_inviting_admin_keeps_the_invitation(db: Session) -> None:
    admin = User(email="admin@ulbsibiu.ro", name="Admin", role=Role.ADMIN)
    db.add(admin)
    db.flush()
    invitation = add_invitation(db, "ion@ulbsibiu.ro", invited_by=admin.id)

    db.execute(text("DELETE FROM users WHERE id = :id"), {"id": admin.id})
    invited_by = db.scalar(
        text("SELECT invited_by FROM user_invitations WHERE id = :id"), {"id": invitation.id}
    )
    assert invited_by is None
