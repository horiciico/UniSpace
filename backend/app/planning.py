"""Shared rules for the timetable and the free-room search.

- Week 1 is the week that contains the start of the planning unit (D-014). Week numbers
  are counted per planning unit, because each faculty has its own semester dates.
- A recurring activity (specific_date NULL) happens on a day when its planning unit covers
  that day, the weekday matches day_of_week, and its parity matches the week number.
- A one-off activity (specific_date set) happens only on that date (D-008: ISO weekday).
- Local dates and times are in Europe/Bucharest.
"""

import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Activity, ActivityException, Parity, PlanningTimeUnit, Status

LOCAL_TZ = ZoneInfo("Europe/Bucharest")


def _clock(minutes: int) -> time:
    return time(minutes // 60, minutes % 60)


# The university's modules: 90 minutes of teaching, then a 10-minute break.
# 08:00-09:30, 09:40-11:10, ... 19:40-21:10. A room is booked for whole modules only.
MODULES: tuple[tuple[time, time], ...] = tuple(
    (_clock(8 * 60 + index * 100), _clock(8 * 60 + index * 100 + 90)) for index in range(8)
)
MODULE_STARTS = frozenset(start for start, _ in MODULES)
MODULE_ENDS = frozenset(end for _, end in MODULES)
BOOKING_END = MODULES[-1][1]  # 21:10: no room can be booked after the last module


class NoModuleLeft(ValueError):
    """No module starts at or after this time on the day it is asked for."""


def booking_window(start: time | None, end: time | None) -> tuple[time, time]:
    """The module interval a free-room search covers. Raises ValueError when it is not allowed.

    - No times: the module that contains now, or the next one during a break.
    - start only: the same, from that time (so an exact local time gives its module).
    - start and end: from the start of one module to the end of another.
    """
    if end is None:
        if start is None:
            start = local_now().time().replace(second=0, microsecond=0)
        for module_start, module_end in MODULES:
            if start < module_end:
                return module_start, module_end
        raise NoModuleLeft("no module is left today: the last module ends at 21:10")
    if start is None:
        raise ValueError("start_time is needed with end_time")
    if end <= start:
        raise ValueError("end_time must be after start_time")
    if start not in MODULE_STARTS or end not in MODULE_ENDS:
        raise ValueError(
            "a booking starts at the start of a module and ends at the end of a module"
        )
    return start, end


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
    """One activity on one date, with the day and times it really has (moved ones have new ones).

    unit_start and unit_id are the planning unit's (None for one-offs). start_time and end_time
    default to the activity's.
    """

    activity: Activity
    day: date
    unit_start: date | None = None
    unit_id: uuid.UUID | None = None
    start_time: time | None = None
    end_time: time | None = None

    def __post_init__(self) -> None:
        if self.start_time is None:
            object.__setattr__(self, "start_time", self.activity.start_time)
        if self.end_time is None:
            object.__setattr__(self, "end_time", self.activity.end_time)


def occurrences(db: Session, first: date, last: date, *conditions) -> list[Occurrence]:
    """Every occurrence that happens between first and last (both inclusive), with date and times.

    Q-017 (answered 2026-11-24): an activity with status CANCELLED does not happen, and an
    occurrence cancelled by an exception does not happen. A moved occurrence happens on its new
    date and at its new time, not at the old ones. A move is found from either date: an occurrence
    moved into the window from another day is included. A move to a day outside the window is
    left out. A move that is only a new time keeps the day. Moving rooms is not handled yet.

    `conditions` filter the activities (for example by room or group).
    """
    moves = db.scalars(
        select(ActivityException)
        .join(Activity, Activity.id == ActivityException.activity_id)
        .where(*conditions)
        .where(
            or_(
                ActivityException.original_date.between(first, last),
                ActivityException.new_date.between(first, last),
            )
        )
    ).all()
    found = _base_occurrences(db, first, last, *conditions)
    # Occurrences that move into the window come from their original day, outside it.
    for day in sorted({m.original_date for m in moves if not first <= m.original_date <= last}):
        keys = {m.activity_id for m in moves if m.original_date == day}
        found += [o for o in _base_occurrences(db, day, day, *conditions) if o.activity.id in keys]

    by_occurrence = {(m.activity_id, m.original_date): m for m in moves}
    result: list[Occurrence] = []
    for o in found:
        move = by_occurrence.get((o.activity.id, o.day))
        if move is None:
            if first <= o.day <= last:
                result.append(o)
            continue
        if move.is_cancelled:
            continue
        day = move.new_date or o.day
        if not (first <= day <= last):
            continue
        result.append(
            replace(
                o,
                day=day,
                start_time=move.new_start_time or o.start_time,
                end_time=move.new_end_time or o.end_time,
            )
        )
    return result


def _base_occurrences(db: Session, first: date, last: date, *conditions) -> list[Occurrence]:
    """The weekly and one-off occurrences by their own dates, before any exception."""
    stmt = (
        select(
            Activity, PlanningTimeUnit.id, PlanningTimeUnit.start_date, PlanningTimeUnit.end_date
        )
        .outerjoin(PlanningTimeUnit, PlanningTimeUnit.id == Activity.planning_time_unit_id)
        .options(joinedload(Activity.classroom))
        .where(*conditions)
        .where(Activity.status != Status.CANCELLED)
        .where(
            or_(
                Activity.specific_date.between(first, last),
                and_(
                    Activity.specific_date.is_(None),
                    PlanningTimeUnit.start_date <= last,
                    PlanningTimeUnit.end_date >= first,
                ),
            )
        )
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
            if (
                activity.parity != Parity.ALL
                and parity_for_week(week_number(unit_start, day)) != activity.parity
            ):
                continue
            found.append(Occurrence(activity, day, unit_start, unit_id))
    return found


def week_info(unit_start: date, monday: date) -> tuple[int, Parity]:
    number = week_number(unit_start, monday)
    return number, parity_for_week(number)


def hhmm(value: time) -> str:
    return value.strftime("%H:%M")
