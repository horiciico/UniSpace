"""Academic calendar API (D-027, C-010).

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
from app.models import AcademicPeriod, AcademicPeriodType, User
from app.routers.admin_bookings import require_admin

public_router = APIRouter(prefix="/api/academic-periods", tags=["academic calendar"])
admin_router = APIRouter(prefix="/api/admin/academic-periods", tags=["admin academic calendar"])


class PeriodBody(BaseModel):
    name: str = Field(max_length=150)
    type: AcademicPeriodType
    start_date: date
    end_date: date

    @field_validator("name")
    @classmethod
    def trimmed_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


def period_out(period: AcademicPeriod) -> dict:
    return {
        "id": str(period.id),
        "name": period.name,
        "type": period.type.value,
        "start_date": period.start_date.isoformat(),
        "end_date": period.end_date.isoformat(),
    }


def all_periods(db: Session) -> list[dict]:
    rows = db.scalars(select(AcademicPeriod).order_by(AcademicPeriod.start_date)).all()
    return [period_out(row) for row in rows]


def check_body(db: Session, body: PeriodBody, own_id: uuid.UUID | None = None) -> None:
    """400 for inverted dates, 409 for an overlap with another period."""
    if body.start_date > body.end_date:
        raise HTTPException(400, "start_date must be on or before end_date.")
    other = find_overlapping_period(db, body.start_date, body.end_date, ignore_id=own_id)
    if other is not None:
        span = f"{other.start_date.isoformat()} to {other.end_date.isoformat()}"
        raise HTTPException(409, f"Overlaps the period '{other.name}' ({span}).")


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
    check_body(db, body)
    period = AcademicPeriod(**body.model_dump())
    db.add(period)
    db.commit()
    return period_out(period)


@admin_router.put("/{period_id}")
def update_period(
    period_id: uuid.UUID,
    body: PeriodBody,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    period = get_period(db, period_id)
    check_body(db, body, own_id=period.id)
    for field, value in body.model_dump().items():
        setattr(period, field, value)
    db.commit()
    return period_out(period)


@admin_router.delete("/{period_id}", status_code=204)
def delete_period(
    period_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> Response:
    db.delete(get_period(db, period_id))
    db.commit()
    return Response(status_code=204)
