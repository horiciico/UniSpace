import uuid
from datetime import date, datetime, time

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, String, Text, Time, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import BookingStatus


class Booking(Base):
    """A room request made by a student or a student organization, separate from the ULBS schedule."""

    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="ck_booking_time_order"),
        # A decision message is at most 1000 characters (issue #23).
        CheckConstraint("decision_message IS NULL OR char_length(decision_message) <= 1000",
                        name="ck_booking_decision_message_length"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    classroom_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classrooms.id", ondelete="RESTRICT"), index=True)
    specific_date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[BookingStatus] = mapped_column(
        Enum(
            BookingStatus,
            name="booking_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=BookingStatus.PENDING,
        server_default=BookingStatus.PENDING.value,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # The admin's decision (issue #23): who decided, when, and an optional message to the requester.
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_bookings_decided_by")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    decision_message: Mapped[str | None] = mapped_column(Text)
