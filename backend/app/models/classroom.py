import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Classroom(Base):
    __tablename__ = "classrooms"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_classroom_capacity"),
        # The ULBS room id is global: a room can be used by a faculty other than its owner (D-015 style key).
        UniqueConstraint("external_id", name="uq_classroom_external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(50))  # e.g. "S02"
    # The faculty that owns the room (from the ULBS rooms list), not the faculty whose schedule uses it.
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("faculties.id", ondelete="SET NULL"))
    external_id: Mapped[str | None] = mapped_column(String(50))  # the room id in the ULBS API
    # NULL = capacity unknown (the ULBS API has no value for the room). Shown as "unknown capacity".
    capacity: Mapped[int | None] = mapped_column(Integer)
    has_projector: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    has_outlets: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    access_status: Mapped[str | None] = mapped_column(Text)  # how to access / open the room

    activities: Mapped[list["Activity"]] = relationship(  # noqa: F821
        back_populates="classroom", foreign_keys="Activity.classroom_id"
    )
