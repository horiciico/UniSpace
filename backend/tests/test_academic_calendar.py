"""Academic calendar (D-027, Task 1): model, period lookup and the overlap rule."""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.academic_calendar import (
    PeriodOverlapError,
    add_period,
    find_overlapping_period,
    get_period_for_date,
    get_period_type_for_date,
)
from app.models import AcademicPeriod, AcademicPeriodType


def _period(name: str, kind: AcademicPeriodType, start: date, end: date) -> AcademicPeriod:
    return AcademicPeriod(name=name, type=kind, start_date=start, end_date=end)


def test_lookup_is_inclusive_on_both_ends(db: Session) -> None:
    exam = add_period(
        db, _period("Sesiune", AcademicPeriodType.EXAM_SESSION, date(2031, 1, 10), date(2031, 2, 1))
    )
    assert get_period_for_date(db, date(2031, 1, 10)) == exam
    assert get_period_for_date(db, date(2031, 1, 20)) == exam
    assert get_period_for_date(db, date(2031, 2, 1)) == exam
    assert get_period_for_date(db, date(2031, 1, 9)) is None
    assert get_period_for_date(db, date(2031, 2, 2)) is None


def test_type_defaults_to_teaching_when_no_period_covers_the_date(db: Session) -> None:
    assert get_period_type_for_date(db, date(2031, 5, 5)) is AcademicPeriodType.TEACHING


@pytest.mark.parametrize("kind", list(AcademicPeriodType))
def test_type_is_the_covering_periods_type(db: Session, kind: AcademicPeriodType) -> None:
    add_period(db, _period("P", kind, date(2032, 3, 1), date(2032, 3, 10)))
    assert get_period_type_for_date(db, date(2032, 3, 5)) is kind


def test_one_day_period_is_allowed(db: Session) -> None:
    add_period(db, _period("Zi", AcademicPeriodType.HOLIDAY, date(2033, 4, 4), date(2033, 4, 4)))
    assert get_period_type_for_date(db, date(2033, 4, 4)) is AcademicPeriodType.HOLIDAY


def test_overlapping_period_is_rejected(db: Session) -> None:
    add_period(db, _period("A", AcademicPeriodType.TEACHING, date(2034, 2, 1), date(2034, 2, 28)))
    for start, end in [
        (date(2034, 2, 28), date(2034, 3, 5)),  # touches the last day
        (date(2034, 1, 20), date(2034, 2, 1)),  # touches the first day
        (date(2034, 2, 10), date(2034, 2, 11)),  # inside
        (date(2034, 1, 1), date(2034, 4, 1)),  # contains
    ]:
        with pytest.raises(PeriodOverlapError):
            add_period(db, _period("B", AcademicPeriodType.HOLIDAY, start, end))


def test_adjacent_periods_do_not_overlap(db: Session) -> None:
    add_period(db, _period("A", AcademicPeriodType.TEACHING, date(2035, 2, 1), date(2035, 2, 28)))
    add_period(db, _period("B", AcademicPeriodType.HOLIDAY, date(2035, 3, 1), date(2035, 3, 7)))
    assert get_period_type_for_date(db, date(2035, 3, 1)) is AcademicPeriodType.HOLIDAY


def test_find_overlap_can_ignore_the_period_being_edited(db: Session) -> None:
    a = add_period(
        db, _period("A", AcademicPeriodType.TEACHING, date(2036, 2, 1), date(2036, 2, 28))
    )
    assert find_overlapping_period(db, date(2036, 2, 5), date(2036, 2, 6)) == a
    assert find_overlapping_period(db, date(2036, 2, 5), date(2036, 2, 6), ignore_id=a.id) is None


def test_start_after_end_is_rejected(db: Session) -> None:
    with pytest.raises(ValueError):
        add_period(db, _period("X", AcademicPeriodType.HOLIDAY, date(2037, 2, 2), date(2037, 2, 1)))


def test_database_check_rejects_start_after_end(db: Session) -> None:
    db.add(_period("X", AcademicPeriodType.HOLIDAY, date(2038, 2, 2), date(2038, 2, 1)))
    with pytest.raises(IntegrityError):
        db.flush()
