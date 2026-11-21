import uuid
from datetime import date, time

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Text, Time, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ActivityException(Base):
    """A one-off change to one occurrence of an Activity (D-016): moved, relocated or cancelled."""

    __tablename__ = "activity_exceptions"
    __table_args__ = (
        UniqueConstraint("activity_id", "original_date", name="uq_event_exception_occurrence"),
        CheckConstraint(
            "new_start_time IS NULL OR new_end_time IS NULL OR new_end_time > new_start_time",
            name="ck_activity_exception_time_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"))
    original_date: Mapped[date] = mapped_column(Date)  # the date it was supposed to happen
    new_date: Mapped[date | None] = mapped_column(Date)
    new_classroom_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("classrooms.id", ondelete="SET NULL"))
    new_start_time: Mapped[time | None] = mapped_column(Time)
    new_end_time: Mapped[time | None] = mapped_column(Time)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    reason: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    activity: Mapped["Activity"] = relationship(back_populates="exceptions")  # noqa: F821
    new_classroom: Mapped["Classroom | None"] = relationship()  # noqa: F821
