import uuid

from sqlalchemy import Enum, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import Role


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)  # Google's immutable subject id
    professor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # ULBS professorId of a professor account (no FK)

    activities: Mapped[list["Activity"]] = relationship(back_populates="user")  # noqa: F821
