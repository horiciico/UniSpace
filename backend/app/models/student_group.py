import uuid

from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class StudentGroup(Base):
    __tablename__ = "student_group"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(50))  # e.g. "332CA"

    activities: Mapped[list["Activity"]] = relationship(back_populates="group")  # noqa: F821
