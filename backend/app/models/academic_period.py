import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import AcademicPeriodType


class AcademicPeriod(Base):
    """A date range of the academic calendar set by an admin (D-027). Both ends are inclusive.

    Ranges must not overlap; that is checked by app.academic_calendar, not by the database.
    """

    __tablename__ = "academic_periods"
    __table_args__ = (
        CheckConstraint("start_date <= end_date", name="ck_academic_period_date_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(150))
    type: Mapped[AcademicPeriodType] = mapped_column(
        Enum(AcademicPeriodType, name="academic_period_type")
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )
