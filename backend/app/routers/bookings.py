import uuid
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import (
    Activity,
    Booking,
    BookingStatus,
    Classroom,
    Faculty,
    Role,
    User,
)
from app.planning import LOCAL_TZ, booking_window, hhmm, local_now, occurrences

router = APIRouter(prefix="/api/bookings", tags=["bookings"])

class BookingIn(BaseModel):
    classroom_id: uuid.UUID
    specific_date: date
    start_time: time
    end_time: time
    title: str

    @field_validator("title")
    @classmethod
    def title_is_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be empty")
        if len(value) > 255:
            raise ValueError("title must be at most 255 characters")
        return value


def _overlaps(start: time, end: time, other_start: time, other_end: time) -> bool:
    return start < other_end and other_start < end


def approved_busy(db: Session, day: date) -> list[tuple[uuid.UUID, time, time]]:
    """(room, start, end) of every approved booking on a day. Pending bookings do not block."""
    rows = db.execute(
        select(Booking.classroom_id, Booking.start_time, Booking.end_time).where(
            Booking.specific_date == day, Booking.status == BookingStatus.APPROVED
        )
    ).all()
    return [(room_id, start, end) for room_id, start, end in rows]


def clash(db: Session, room_id: uuid.UUID, day: date, start: time, end: time) -> str | None:
    """Why a room is taken from start to end on a day, or None.

    Recurring activities count on their weeks and parity, and as they really happen (the shared
    occurrences helper: cancelled ones do not, a moved one counts at its new time, Q-017).
    Approved bookings count; pending ones do not.
    """
    for occurrence in occurrences(db, day, day, Activity.classroom_id == room_id):
        if _overlaps(start, end, occurrence.start_time, occurrence.end_time):
            return (f"The room is taken from {hhmm(occurrence.start_time)} to {hhmm(occurrence.end_time)} "
                    f"by {occurrence.activity.name}.")
    for room, busy_start, busy_end in approved_busy(db, day):
        if room == room_id and _overlaps(start, end, busy_start, busy_end):
            return f"The room is taken from {hhmm(busy_start)} to {hhmm(busy_end)} by an approved booking."
    return None


def booking_out(booking: Booking, room_name: str, faculty_name: str | None) -> dict:
    return {
        "id": str(booking.id),
        "classroom_id": str(booking.classroom_id),
        "room_name": room_name,
        "faculty_name": faculty_name,  # null for a room with no faculty; the frontend shows "Campus" (D-012)
        "specific_date": booking.specific_date.isoformat(),
        "start_time": hhmm(booking.start_time),
        "end_time": hhmm(booking.end_time),
        "title": booking.title,
        "status": booking.status.value,
        "created_at": booking.created_at.isoformat() if booking.created_at else None,
        "decided_at": booking.decided_at.isoformat() if booking.decided_at else None,
        "decision_message": booking.decision_message,  # the admin's message, if any (issue #23)
    }


def _faculty_name(db: Session, room: Classroom) -> str | None:
    faculty = db.get(Faculty, room.faculty_id) if room.faculty_id else None
    return faculty.name if faculty else None


@router.post("", status_code=201)
def create_booking(body: BookingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """A booking request. Admins' bookings are approved at once; everyone else's wait for an admin."""
    room = db.get(Classroom, body.classroom_id)
    if room is None:
        raise HTTPException(404, "Room not found.")
    if not room.is_bookable:
        raise HTTPException(400, "This room cannot be booked.")
    try:
        start, end = booking_window(body.start_time, body.end_time)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if datetime.combine(body.specific_date, start, tzinfo=LOCAL_TZ) <= local_now():
        raise HTTPException(400, "That time has already passed.")
    reason = clash(db, room.id, body.specific_date, start, end)
    if reason is not None:
        raise HTTPException(409, reason)

    booking = Booking(
        user_id=user.id,
        classroom_id=room.id,
        specific_date=body.specific_date,
        start_time=start,
        end_time=end,
        title=body.title,
        status=BookingStatus.APPROVED if user.role == Role.ADMIN else BookingStatus.PENDING,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking_out(booking, room.name, _faculty_name(db, room))


@router.get("/my")
def my_bookings(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    """Your bookings: upcoming ones first (earliest date and start, newest created first on a tie),
    then the past ones, most recent first."""
    rows = db.execute(
        select(Booking, Classroom.name, Faculty.name)
        .join(Classroom, Classroom.id == Booking.classroom_id)
        .outerjoin(Faculty, Faculty.id == Classroom.faculty_id)
        .where(Booking.user_id == user.id)
    ).all()
    today = local_now().date()
    upcoming = [row for row in rows if row[0].specific_date >= today]
    past = [row for row in rows if row[0].specific_date < today]
    upcoming.sort(key=lambda row: row[0].created_at or datetime.min, reverse=True)
    upcoming.sort(key=lambda row: (row[0].specific_date, row[0].start_time))
    past.sort(key=lambda row: (row[0].specific_date, row[0].start_time), reverse=True)
    return [booking_out(booking, room_name, faculty_name) for booking, room_name, faculty_name in upcoming + past]


@router.delete("/{booking_id}")
def cancel_booking(booking_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Cancel your own pending booking. The row is kept with status cancelled."""
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(404, "Booking not found.")
    if booking.user_id != user.id:
        raise HTTPException(403, "You can only cancel your own bookings.")
    if booking.status != BookingStatus.PENDING:
        raise HTTPException(409, "Only a pending booking can be cancelled.")
    booking.status = BookingStatus.CANCELLED
    db.commit()
    room = db.get(Classroom, booking.classroom_id)
    return booking_out(booking, room.name, _faculty_name(db, room))
