import uuid
from datetime import time

from sqlalchemy import CheckConstraint, Enum, ForeignKey, SmallInteger, Text, Time, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import RequestStatus


class RuleChangeRequest(Base):
    """A professor asks an admin for a permanent change to a weekly rule (D-016).

    Only the fields the professor wants changed are set; at least one must be set.
    """

    __tablename__ = "rule_change_requests"
    __table_args__ = (
        CheckConstraint("new_day_of_week BETWEEN 1 AND 7", name="ck_rule_change_day_of_week"),
        CheckConstraint(
            "new_classroom_id IS NOT NULL OR new_day_of_week IS NOT NULL "
            "OR new_start_time IS NOT NULL OR new_end_time IS NOT NULL",
            name="ck_rule_change_has_change",
        ),
        CheckConstraint(
            "new_start_time IS NULL OR new_end_time IS NULL OR new_end_time > new_start_time",
            name="ck_rule_change_time_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"))
    requested_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    new_classroom_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("classrooms.id", ondelete="SET NULL"))
    new_day_of_week: Mapped[int | None] = mapped_column(SmallInteger)  # 1 = Monday .. 7 = Sunday (D-008)
    new_start_time: Mapped[time | None] = mapped_column(Time)
    new_end_time: Mapped[time | None] = mapped_column(Time)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"),
        default=RequestStatus.PENDING,
        server_default=RequestStatus.PENDING.value,
    )

    activity: Mapped["Activity"] = relationship()  # noqa: F821
