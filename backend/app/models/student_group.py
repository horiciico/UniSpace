import uuid

from sqlalchemy import Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class StudentGroup(Base):
    __tablename__ = "student_groups"
    __table_args__ = (UniqueConstraint("external_id", name="uq_student_group_external"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(50))  # e.g. "332CA"
    external_id: Mapped[int | None] = mapped_column(Integer)  # the studyFormation id in the ULBS API

    activities: Mapped[list["Activity"]] = relationship(back_populates="group")  # noqa: F821
