import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import PlanningUnitType


class PlanningTimeUnit(Base):
    """The active period of a faculty (a semester or a module), from the ULBS API.

    Schedule rules (activities) belong to one of these; their validity is this period.
    """

    __tablename__ = "planning_time_units"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_planning_unit_dates"),
        UniqueConstraint("faculty_id", "external_id", name="uq_planning_unit_faculty_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    faculty_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("faculties.id", ondelete="CASCADE"))
    external_id: Mapped[int] = mapped_column(Integer)  # the "id" returned by the ULBS API, e.g. 12
    year: Mapped[int] = mapped_column(Integer)  # e.g. 2026
    name: Mapped[str] = mapped_column(String(100))  # e.g. "Modul 1"
    display_name: Mapped[str | None] = mapped_column(String(150))  # e.g. "Modul 1 2026"
    type: Mapped[PlanningUnitType] = mapped_column(
        Enum(PlanningUnitType, name="planning_unit_type")
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
