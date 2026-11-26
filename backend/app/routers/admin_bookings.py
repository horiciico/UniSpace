import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.email_service import send_booking_approved_email, send_booking_rejected_email
from app.models import Booking, BookingStatus, Classroom, Faculty, Role, User
from app.planning import LOCAL_TZ, local_now
from app.routers.bookings import booking_out, clash
from app.routers.classrooms import faculty_condition

router = APIRouter(prefix="/api/admin/bookings", tags=["admin bookings"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(403, "Only an administrator can review booking requests.")
    return user


class Decision(BaseModel):
    decision: Literal["approve", "reject"]
    message: str | None = Field(default=None, max_length=100)

    @field_validator("message")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()


@router.get("/pending")
def pending_requests(
    admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[dict]:
    """The requests waiting for a decision, oldest first, with who asked and their role."""
    rows = db.execute(
        select(Booking, Classroom.name, Faculty.name, User)
        .join(Classroom, Classroom.id == Booking.classroom_id)
        .outerjoin(Faculty, Faculty.id == Classroom.faculty_id)
        .join(User, User.id == Booking.user_id)
        .where(Booking.status == BookingStatus.PENDING)
        .order_by(Booking.created_at, Booking.id)
    ).all()
    out = []
    for booking, room_name, faculty_name, requester in rows:
        item = booking_out(booking, room_name, faculty_name)
        item["requester"] = {
            "name": requester.name,
            "email": requester.email,
            "role": requester.role.value,
        }
        out.append(item)
    return out


@router.post("/{booking_id}/decision")
def decide(
    booking_id: uuid.UUID,
    body: Decision,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Accept (approve) or reject a pending request, with an optional message to the requester.

    An approval is checked for clashes again, since a clash may have appeared since the request.
    The requester is emailed once the decision is saved.
    """
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(404, "Booking not found.")
    if booking.status != BookingStatus.PENDING:
        raise HTTPException(409, "Only a pending request can be decided.")
    if body.decision == "approve":
        reason = clash(
            db, booking.classroom_id, booking.specific_date, booking.start_time, booking.end_time
        )
        if reason is not None:
            raise HTTPException(409, reason)
        booking.status = BookingStatus.APPROVED
    else:
        booking.status = BookingStatus.REJECTED
    booking.decided_by_id = admin.id
    booking.decided_at = local_now().replace(tzinfo=None)
    booking.decision_message = body.message
    db.commit()
    room = db.get(Classroom, booking.classroom_id)
    assert room is not None
    requester = db.get(User, booking.user_id)
    assert requester is not None
    if body.decision == "approve":
        background_tasks.add_task(
            send_booking_approved_email,
            requester.email,
            room.name,
            booking.specific_date,
            booking.start_time,
            booking.end_time,
            booking.title,
        )
    else:
        background_tasks.add_task(
            send_booking_rejected_email,
            requester.email,
            room.name,
            booking.specific_date,
            booking.start_time,
            booking.end_time,
            booking.title,
            body.message,
        )
    faculty = db.get(Faculty, room.faculty_id) if room.faculty_id else None
    return booking_out(booking, room.name, faculty.name if faculty else None)


def _history_item(
    booking: Booking, room: Classroom, faculty_name: str | None, requester: User
) -> dict:
    return {
        "id": str(booking.id),
        "classroom_id": str(room.id),
        "classroom_name": room.name,
        "faculty_id": str(room.faculty_id) if room.faculty_id else None,
        "faculty_name": faculty_name,
        "specific_date": booking.specific_date.isoformat(),
        "start_time": booking.start_time.strftime("%H:%M"),
        "end_time": booking.end_time.strftime("%H:%M"),
        "title": booking.title,
        "status": booking.status.value,
        "created_at": booking.created_at.isoformat() if booking.created_at else None,
        "user_id": str(requester.id),
        "user_email": requester.email,
        "user_role": requester.role.value,
    }


@router.get("")
def history(
    faculty_id: str | None = None,
    classroom_id: uuid.UUID | None = None,
    status: BookingStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Every booking, past and current, newest first. faculty_id is a faculty, or "campus" for rooms
    with no faculty (the classrooms rule). Each filter is optional; `total` counts all matches."""
    conditions = []
    if faculty_id is not None:
        conditions.append(faculty_condition(faculty_id))
    if classroom_id is not None:
        conditions.append(Booking.classroom_id == classroom_id)
    if status is not None:
        conditions.append(Booking.status == status)
    joins = (
        select(Booking)
        .join(Classroom, Classroom.id == Booking.classroom_id)
        .join(User, User.id == Booking.user_id)
        .where(*conditions)
    )
    total = db.scalar(select(func.count()).select_from(joins.subquery()))
    rows = db.execute(
        select(Booking, Classroom, Faculty.name, User)
        .join(Classroom, Classroom.id == Booking.classroom_id)
        .outerjoin(Faculty, Faculty.id == Classroom.faculty_id)
        .join(User, User.id == Booking.user_id)
        .where(*conditions)
        .order_by(
            Booking.specific_date.desc(),
            Booking.start_time.desc(),
            Booking.created_at.desc(),
            Booking.id,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "items": [
            _history_item(booking, room, faculty_name, requester)
            for booking, room, faculty_name, requester in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


class AdminCancel(BaseModel):
    message: str | None = Field(default=None, max_length=100)

    @field_validator("message")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()


@router.post("/{booking_id}/cancel")
def admin_cancel(
    booking_id: uuid.UUID,
    body: AdminCancel | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """An admin cancels a future approved booking of anyone. The booking becomes `rejected`
    (the requester sees that), with an optional message from the admin."""
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(404, "Booking not found.")
    if booking.status != BookingStatus.APPROVED:
        raise HTTPException(409, "Only an approved booking can be cancelled by an administrator.")
    if datetime.combine(booking.specific_date, booking.start_time, tzinfo=LOCAL_TZ) <= local_now():
        raise HTTPException(409, "Only a booking that has not started yet can be cancelled.")
    booking.status = BookingStatus.REJECTED
    booking.decided_by_id = admin.id
    booking.decided_at = local_now().replace(tzinfo=None)
    booking.decision_message = body.message if body else None
    db.commit()
    room = db.get(Classroom, booking.classroom_id)
    assert room is not None
    faculty = db.get(Faculty, room.faculty_id) if room.faculty_id else None
    return booking_out(booking, room.name, faculty.name if faculty else None)
