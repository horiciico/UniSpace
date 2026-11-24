import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Booking, BookingStatus, Classroom, Faculty, Role, User
from app.planning import local_now
from app.routers.bookings import booking_out, clash

router = APIRouter(prefix="/api/admin/bookings", tags=["admin bookings"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(403, "Only an administrator can review booking requests.")
    return user


class Decision(BaseModel):
    decision: Literal["approve", "reject"]
    message: str | None = Field(default=None, max_length=1000)

    @field_validator("message")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()


@router.get("/pending")
def pending_requests(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
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
        item["requester"] = {"name": requester.name, "email": requester.email, "role": requester.role.value}
        out.append(item)
    return out


@router.post("/{booking_id}/decision")
def decide(booking_id: uuid.UUID, body: Decision, admin: User = Depends(require_admin),
           db: Session = Depends(get_db)) -> dict:
    """Accept (approve) or reject a pending request, with an optional message to the requester.

    An approval is checked for clashes again, since a clash may have been approved since the request.
    """
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(404, "Booking not found.")
    if booking.status != BookingStatus.PENDING:
        raise HTTPException(409, "Only a pending request can be decided.")
    if body.decision == "approve":
        reason = clash(db, booking.classroom_id, booking.specific_date, booking.start_time, booking.end_time)
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
    faculty = db.get(Faculty, room.faculty_id) if room.faculty_id else None
    return booking_out(booking, room.name, faculty.name if faculty else None)
