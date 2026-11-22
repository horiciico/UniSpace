"""Shared rules for the timetable and the free-room search.

- Week 1 is the week that contains the start of the planning unit (D-014). Week numbers
  are counted per planning unit, because each faculty has its own semester dates.
- A recurring activity (specific_date NULL) happens on a day when its planning unit covers
  that day, the weekday matches day_of_week, and its parity matches the week number.
- A one-off activity (specific_date set) happens only on that date (D-008: ISO weekday).
- Local dates and times are in Europe/Bucharest.
"""
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Activity, Parity, PlanningTimeUnit

LOCAL_TZ = ZoneInfo("Europe/Bucharest")


def local_now() -> datetime:
    return datetime.now(LOCAL_TZ)


def local_today() -> date:
    return local_now().date()


def week_monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_number(unit_start: date, day: date) -> int:
    """1 for the week that contains unit_start, then 2, 3, ..."""
    return (week_monday(day) - week_monday(unit_start)).days // 7 + 1


def parity_for_week(number: int) -> Parity:
    """Odd weeks are ODD, even weeks are EVEN (D-014)."""
    return Parity.ODD if number % 2 == 1 else Parity.EVEN


@dataclass(frozen=True)
class Occurrence:
    """One activity on one date. unit_start and unit_id are the planning unit's (None for one-offs)."""

    activity: Activity
    day: date
    unit_start: date | None = None
    unit_id: uuid.UUID | None = None


def occurrences(db: Session, first: date, last: date, *conditions) -> list[Occurrence]:
    """Every activity that happens between first and last (both inclusive), with its date.

    `conditions` filter the activities (for example by room or group).
    """
    stmt = (
        select(Activity, PlanningTimeUnit.id, PlanningTimeUnit.start_date, PlanningTimeUnit.end_date)
        .outerjoin(PlanningTimeUnit, PlanningTimeUnit.id == Activity.planning_time_unit_id)
        .options(joinedload(Activity.classroom))
        .where(*conditions)
        .where(or_(
            Activity.specific_date.between(first, last),
            and_(
                Activity.specific_date.is_(None),
                PlanningTimeUnit.start_date <= last,
                PlanningTimeUnit.end_date >= first,
            ),
        ))
    )
    found: list[Occurrence] = []
    for activity, unit_id, unit_start, unit_end in db.execute(stmt).all():
        for offset in range((last - first).days + 1):
            day = first + timedelta(days=offset)
            if day.isoweekday() != activity.day_of_week:
                continue
            if activity.specific_date is not None:
                if activity.specific_date == day:
                    found.append(Occurrence(activity, day))
                continue
            if not (unit_start <= day <= unit_end):
                continue
            if activity.parity != Parity.ALL and parity_for_week(week_number(unit_start, day)) != activity.parity:
                continue
            found.append(Occurrence(activity, day, unit_start, unit_id))
    return found


def week_info(unit_start: date, monday: date) -> tuple[int, Parity]:
    number = week_number(unit_start, monday)
    return number, parity_for_week(number)


def hhmm(value: time) -> str:
    return value.strftime("%H:%M")
