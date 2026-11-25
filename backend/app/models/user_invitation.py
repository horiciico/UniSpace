import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import InvitationStatus, Role


class UserInvitation(Base):
    """An admin's invitation for one email to sign in with a given non-admin role.

    The token is stored as plain text on purpose: an admin copies the invite link again from the
    pending list (a trade-off accepted by the user). A registration consumes it (D-025).
    """

    __tablename__ = "user_invitations"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_user_invitation_email_lowercase"),
        # At most one active (pending) invitation per email.
        Index(
            "uq_user_invitations_pending_email",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(255))  # stored lower-case
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"))
    token: Mapped[str] = mapped_column(String(128), unique=True)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL", name="fk_user_invitations_invited_by"),
        nullable=True,
    )
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(
            InvitationStatus,
            name="invitation_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        server_default=text("'pending'"),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now() + interval '7 days'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
