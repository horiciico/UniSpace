"""Academic calendar lookups and the no-overlap rule (D-028).

For a faculty and a date: the faculty's own period, else the period of all faculties, else
teaching. faculty_id None means "no faculty" (a campus room): only all-faculties periods count.
"""

import uuid
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    AcademicPeriod,
    AcademicPeriodType,
    Activity,
    ActivityGroup,
    PlanningTimeUnit,
)


class PeriodOverlapError(ValueError):
    """The date range overlaps an existing academic period."""

    def __init__(self, other: AcademicPeriod) -> None:
        span = f"{other.start_date.isoformat()} to {other.end_date.isoformat()}"
        super().__init__(f"overlaps '{other.name}' ({span})")
        self.other = other


def get_period_for_date(
    db: Session, target_date: date, faculty_id: uuid.UUID | None = None
) -> AcademicPeriod | None:
    """The period that counts for the faculty on the date (both ends inclusive), or None."""
    return db.scalars(
        select(AcademicPeriod)
        .where(
            AcademicPeriod.start_date <= target_date,
            AcademicPeriod.end_date >= target_date,
            or_(AcademicPeriod.faculty_id.is_(None), AcademicPeriod.faculty_id == faculty_id),
        )
        # The faculty's own period before the all-faculties one.
        .order_by(AcademicPeriod.faculty_id.is_(None))
        .limit(1)
    ).first()


def get_period_type_for_date(
    db: Session, target_date: date, faculty_id: uuid.UUID | None = None
) -> AcademicPeriodType:
    """The type that counts for the faculty on the date; TEACHING when no period covers it."""
    period = get_period_for_date(db, target_date, faculty_id)
    return period.type if period else AcademicPeriodType.TEACHING


def teaching_faculty_ids(db: Session, activity: Activity) -> set[uuid.UUID | None]:
    """The faculties whose calendar a class follows: its planning unit's. A moved one-off has no
    unit, so the units of its groups' other activities tell. {None} (no faculty) when unknown."""
    if activity.planning_time_unit_id is not None:
        units = select(PlanningTimeUnit.faculty_id).where(
            PlanningTimeUnit.id == activity.planning_time_unit_id
        )
    else:
        groups = select(ActivityGroup.group_id).where(ActivityGroup.activity_id == activity.id)
        units = (
            select(PlanningTimeUnit.faculty_id)
            .join(Activity, Activity.planning_time_unit_id == PlanningTimeUnit.id)
            .join(ActivityGroup, ActivityGroup.activity_id == Activity.id)
            .where(ActivityGroup.group_id.in_(groups))
        )
    return set(db.scalars(units.distinct()).all()) or {None}


def is_holiday(db: Session, day: date, faculty_ids: set[uuid.UUID | None]) -> bool:
    """Whether the day is a holiday for any of the faculties."""
    return any(
        get_period_type_for_date(db, day, faculty_id) == AcademicPeriodType.HOLIDAY
        for faculty_id in faculty_ids
    )


def find_overlapping_period(
    db: Session,
    start_date: date,
    end_date: date,
    ignore_id: uuid.UUID | None = None,
    faculty_id: uuid.UUID | None = None,
) -> AcademicPeriod | None:
    """An existing period of the same scope (that faculty, or all faculties) that shares a day
    with start_date..end_date. ignore_id skips one row (the period being edited)."""
    query = select(AcademicPeriod).where(
        AcademicPeriod.start_date <= end_date,
        AcademicPeriod.end_date >= start_date,
        AcademicPeriod.faculty_id == faculty_id,
    )
    if ignore_id is not None:
        query = query.where(AcademicPeriod.id != ignore_id)
    return db.scalars(query.limit(1)).first()


def add_period(db: Session, period: AcademicPeriod) -> AcademicPeriod:
    """Validate and add a period. Raises ValueError (order) or PeriodOverlapError."""
    if period.start_date > period.end_date:
        raise ValueError("start_date must be on or before end_date")
    other = find_overlapping_period(
        db, period.start_date, period.end_date, period.id, period.faculty_id
    )
    if other is not None:
        raise PeriodOverlapError(other)
    db.add(period)
    db.flush()
    return period
