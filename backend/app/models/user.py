import uuid

from sqlalchemy import Enum, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import Role


class User(Base):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"))

    activities: Mapped[list["Activity"]] = relationship(back_populates="user")  # noqa: F821
