import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class EventException(Base):
    """Override for one occurrence of a recurring Activity: moved, relocated or cancelled."""

    __tablename__ = "event_exception"
    __table_args__ = (UniqueConstraint("activity_id", "original_date", name="uq_event_exception_occurrence"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activity.id", ondelete="CASCADE"))
    original_date: Mapped[date] = mapped_column(Date)  # the date it was supposed to happen
    new_date: Mapped[date | None] = mapped_column(Date)
    new_classroom_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("classroom.id", ondelete="SET NULL"))
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    activity: Mapped["Activity"] = relationship(back_populates="exceptions")  # noqa: F821
    new_classroom: Mapped["Classroom | None"] = relationship()  # noqa: F821
