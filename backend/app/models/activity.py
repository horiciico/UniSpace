import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import INT4RANGE, Range
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import ActivityType, Parity, Status

# Minutes since midnight, [start, end). Lets overlap checks use `&&` with a GiST index.
# least/greatest keep the expression valid for reversed times, so the CHECK constraint
# (end_time > start_time) is what rejects them, with a plain IntegrityError.
_START_MIN = "(extract(hour from start_time)::int * 60 + extract(minute from start_time)::int)"
_END_MIN = "(extract(hour from end_time)::int * 60 + extract(minute from end_time)::int)"
_TIME_RANGE = f"int4range(least({_START_MIN}, {_END_MIN}), greatest({_START_MIN}, {_END_MIN}), '[)')"


class Activity(Base):
    """One row for both the imported official schedule and bookings (weekly recurrence rule)."""

    __tablename__ = "activity"
    __table_args__ = (
        CheckConstraint("priority BETWEEN 1 AND 5", name="ck_activity_priority"),
        CheckConstraint("day_of_week BETWEEN 1 AND 7", name="ck_activity_day_of_week"),
        CheckConstraint("end_time > start_time", name="ck_activity_time_order"),
        # CUSTOM parity needs a weeks list; left unusable until the customization flow exists.
        CheckConstraint("parity <> 'CUSTOM'", name="ck_activity_parity_custom_unusable"),
        Index("ix_activity_room_day_start_end", "classroom_id", "day_of_week", "start_time", "end_time"),
        Index("ix_activity_group_day", "group_id", "day_of_week"),
        Index("ix_activity_day_parity", "day_of_week", "parity"),
        Index("ix_activity_room_day_time_range", "classroom_id", "day_of_week", "time_range", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[ActivityType] = mapped_column(Enum(ActivityType, name="activity_type"))
    priority: Mapped[int] = mapped_column(SmallInteger)  # Priority values, 1-5
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("student_group.id", ondelete="SET NULL"))
    classroom_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classroom.id", ondelete="RESTRICT"))

    day_of_week: Mapped[int] = mapped_column(SmallInteger)  # 1 = Monday .. 7 = Sunday (ISO)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    parity: Mapped[Parity] = mapped_column(
        Enum(Parity, name="parity"), default=Parity.ALL, server_default=Parity.ALL.value
    )
    time_range: Mapped[Range[int]] = mapped_column(INT4RANGE, Computed(_TIME_RANGE, persisted=True))

    status: Mapped[Status] = mapped_column(
        Enum(Status, name="status"), default=Status.APPROVED, server_default=Status.APPROVED.value
    )
    alt_classroom_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("classroom.id", ondelete="SET NULL"))
    alt_start_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    alt_end_datetime: Mapped[datetime | None] = mapped_column(DateTime)
    bumped_date: Mapped[date | None] = mapped_column(Date)  # which occurrence was bumped
    bump_decision_deadline: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped["User | None"] = relationship(back_populates="activities")  # noqa: F821
    group: Mapped["StudentGroup | None"] = relationship(back_populates="activities")  # noqa: F821
    classroom: Mapped["Classroom"] = relationship(  # noqa: F821
        back_populates="activities", foreign_keys=[classroom_id]
    )
    alt_classroom: Mapped["Classroom | None"] = relationship(foreign_keys=[alt_classroom_id])  # noqa: F821
    exceptions: Mapped[list["EventException"]] = relationship(  # noqa: F821
        back_populates="activity", cascade="all, delete-orphan"
    )
