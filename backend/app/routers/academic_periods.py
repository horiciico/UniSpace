"""Academic calendar API (D-028, C-010).

GET /api/academic-periods is for any signed-in user (the timetable reads it).
/api/admin/academic-periods is ADMIN only: list, create, update, delete.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.academic_calendar import find_overlapping_period
from app.auth import get_current_user
from app.db import get_db
from app.models import AcademicPeriod, AcademicPeriodType, Faculty, User
from app.routers.admin_bookings import require_admin

public_router = APIRouter(prefix="/api/academic-periods", tags=["academic calendar"])
admin_router = APIRouter(prefix="/api/admin/academic-periods", tags=["admin academic calendar"])


class PeriodBody(BaseModel):
    name: str = Field(max_length=150)
    type: AcademicPeriodType
    start_date: date
    end_date: date
    faculty_id: uuid.UUID | None = None  # None: all faculties

    @field_validator("name")
    @classmethod
    def trimmed_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


def period_out(period: AcademicPeriod, faculty_name: str | None) -> dict:
    return {
        "id": str(period.id),
        "name": period.name,
        "type": period.type.value,
        "start_date": period.start_date.isoformat(),
        "end_date": period.end_date.isoformat(),
        "faculty_id": str(period.faculty_id) if period.faculty_id else None,
        "faculty_name": faculty_name,
    }


def all_periods(db: Session) -> list[dict]:
    rows = db.execute(
        select(AcademicPeriod, Faculty.name)
        .outerjoin(Faculty, Faculty.id == AcademicPeriod.faculty_id)
        # On the same start date: all faculties first, then by faculty name.
        .order_by(AcademicPeriod.start_date, Faculty.name.nulls_first())
    ).all()
    return [period_out(period, faculty_name) for period, faculty_name in rows]


def check_body(db: Session, body: PeriodBody, own_id: uuid.UUID | None = None) -> str | None:
    """400 for inverted dates, 404 for an unknown faculty, 409 for an overlap with another period
    of the same scope. Returns the faculty's name (None for all faculties)."""
    if body.start_date > body.end_date:
        raise HTTPException(400, "start_date must be on or before end_date.")
    faculty = None
    if body.faculty_id is not None:
        faculty = db.get(Faculty, body.faculty_id)
        if faculty is None:
            raise HTTPException(404, "Faculty not found.")
    other = find_overlapping_period(
        db, body.start_date, body.end_date, ignore_id=own_id, faculty_id=body.faculty_id
    )
    if other is not None:
        span = f"{other.start_date.isoformat()} to {other.end_date.isoformat()}"
        raise HTTPException(409, f"Overlaps the period '{other.name}' ({span}).")
    return faculty.name if faculty else None


def get_period(db: Session, period_id: uuid.UUID) -> AcademicPeriod:
    period = db.get(AcademicPeriod, period_id)
    if period is None:
        raise HTTPException(404, "Academic period not found.")
    return period


@public_router.get("")
def list_periods(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    return all_periods(db)


@admin_router.get("")
def admin_list_periods(
    admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[dict]:
    return all_periods(db)


@admin_router.post("", status_code=201)
def create_period(
    body: PeriodBody, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    faculty_name = check_body(db, body)
    period = AcademicPeriod(**body.model_dump())
    db.add(period)
    db.commit()
    return period_out(period, faculty_name)


@admin_router.put("/{period_id}")
def update_period(
    period_id: uuid.UUID,
    body: PeriodBody,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    period = get_period(db, period_id)
    faculty_name = check_body(db, body, own_id=period.id)
    for field, value in body.model_dump().items():
        setattr(period, field, value)
    db.commit()
    return period_out(period, faculty_name)


@admin_router.delete("/{period_id}", status_code=204)
def delete_period(
    period_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> Response:
    db.delete(get_period(db, period_id))
    db.commit()
    return Response(status_code=204)
