import uuid

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Professor(Base):
    """A professor from the ULBS list. `id` is the ULBS professorId (from the API, no default)."""

    __tablename__ = "professors"
    __table_args__ = (
        # Stored normalized: strip().lower() of the address (checked by DB constraint).
        CheckConstraint("email = lower(btrim(email))", name="ck_professor_email_normalized"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
