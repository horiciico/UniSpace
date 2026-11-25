import uuid

from sqlalchemy import Boolean, CheckConstraint, Enum, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import Role


class Invitation(Base):
    """Lets one external (non-university) email sign in once, with the given role."""

    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_invitation_email_lowercase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(255), unique=True)  # stored lower-case
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"))
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
