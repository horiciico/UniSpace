import uuid

from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Classroom(Base):
    __tablename__ = "classroom"
    __table_args__ = (CheckConstraint("capacity > 0", name="ck_classroom_capacity"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(50))  # e.g. "S02"
    capacity: Mapped[int] = mapped_column(Integer)
    has_projector: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    has_outlets: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    access_status: Mapped[str | None] = mapped_column(Text)  # how to access / open the room

    activities: Mapped[list["Activity"]] = relationship(  # noqa: F821
        back_populates="classroom", foreign_keys="Activity.classroom_id"
    )
