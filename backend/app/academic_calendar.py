"""Academic calendar lookups and the no-overlap rule (D-027)."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AcademicPeriod, AcademicPeriodType


class PeriodOverlapError(ValueError):
    """The date range overlaps an existing academic period."""

    def __init__(self, other: AcademicPeriod) -> None:
        span = f"{other.start_date.isoformat()} to {other.end_date.isoformat()}"
        super().__init__(f"overlaps '{other.name}' ({span})")
        self.other = other


def get_period_for_date(db: Session, target_date: date) -> AcademicPeriod | None:
    """The period covering the date (both ends inclusive), or None."""
    return db.scalars(
        select(AcademicPeriod)
        .where(AcademicPeriod.start_date <= target_date, AcademicPeriod.end_date >= target_date)
        .limit(1)
    ).first()


def get_period_type_for_date(db: Session, target_date: date) -> AcademicPeriodType:
    """The covering period's type; TEACHING when no period covers the date."""
    period = get_period_for_date(db, target_date)
    return period.type if period else AcademicPeriodType.TEACHING


def find_overlapping_period(
    db: Session, start_date: date, end_date: date, ignore_id: uuid.UUID | None = None
) -> AcademicPeriod | None:
    """An existing period that shares a day with start_date..end_date. ignore_id skips one row
    (the period being edited)."""
    query = select(AcademicPeriod).where(
        AcademicPeriod.start_date <= end_date, AcademicPeriod.end_date >= start_date
    )
    if ignore_id is not None:
        query = query.where(AcademicPeriod.id != ignore_id)
    return db.scalars(query.limit(1)).first()


def add_period(db: Session, period: AcademicPeriod) -> AcademicPeriod:
    """Validate and add a period. Raises ValueError (order) or PeriodOverlapError."""
    if period.start_date > period.end_date:
        raise ValueError("start_date must be on or before end_date")
    other = find_overlapping_period(db, period.start_date, period.end_date, period.id)
    if other is not None:
        raise PeriodOverlapError(other)
    db.add(period)
    db.flush()
    return period
