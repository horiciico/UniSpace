import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import BoardType

if TYPE_CHECKING:
    from app.models.activity import Activity


class Classroom(Base):
    __tablename__ = "classrooms"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_classroom_capacity"),
        # The ULBS room id is global: a room can be used by a faculty other than its owner
        # (D-015 style key).
        UniqueConstraint("external_id", name="uq_classroom_external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(50))  # e.g. "S02"
    # The faculty that owns the room (from the ULBS rooms list), not the faculty whose schedule
    # uses it.
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("faculties.id", ondelete="SET NULL")
    )
    external_id: Mapped[str | None] = mapped_column(String(50))  # the room id in the ULBS API
    # NULL = capacity unknown (the ULBS API has no value for the room). Shown as "unknown capacity".
    capacity: Mapped[int | None] = mapped_column(Integer)
    # Admin-managed, never set by the ETL. NULL = unspecified (Free Now treats it as no projector).
    has_projector: Mapped[bool | None] = mapped_column(Boolean)
    has_outlets: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    # Admin-managed, never set by the ETL. NULL = unspecified.
    board_type: Mapped[BoardType | None] = mapped_column(
        Enum(
            BoardType,
            name="board_type",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        )
    )
    # Admin-managed, never set by the ETL: how to get into the room, written in plain words.
    access_notes: Mapped[str | None] = mapped_column(String(255))
    # Admin-managed free-text inventory, never set by the ETL, e.g. "24 PCs, 10 oscilloscopes".
    equipment_notes: Mapped[str | None] = mapped_column(String(500))
    # FALSE: left out of the free-room search. TRUE by default.
    is_bookable: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    # TRUE: checked on site. FALSE by default, so the room shows as "date estimate".
    is_field_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    activities: Mapped[list["Activity"]] = relationship(  # noqa: F821
        back_populates="classroom", foreign_keys="Activity.classroom_id"
    )
