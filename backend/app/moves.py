"""Moving one teaching occurrence (step 3; D-026, business rules 1 to 6).

- A weekly occurrence moves by an ActivityException with is_cancelled = True (the original slot
  stops happening, so it is free at once) plus a new one-off row for the new slot.
- A one-off moves by a new one-off row, and the old row is set CANCELLED. An imported one-off is
  marked is_manually_modified, so the ETL does not overwrite it.
- Whole 90-minute modules only; the room must be bookable; a new date before today is refused.
- The new slot must be free for the room, the professor and every group of the activity.
"""

import uuid
from datetime import date, time

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.availability import slot_clashes
from app.models import (
    Activity,
    ActivityException,
    ActivityGroup,
    Classroom,
    Parity,
    Professor,
    Status,
    StudentGroup,
    User,
)
from app.planning import booking_window, occurrences


def move_occurrence(
    db: Session,
    professor: Professor,
    user: User,
    activity_id: uuid.UUID,
    original_date: date,
    new_date: date,
    start_time: time,
    end_time: time,
    new_classroom_id: uuid.UUID,
    today: date,
) -> tuple[Activity, Classroom]:
    """Move one occurrence: returns the new one-off and its room, or raises HTTPException."""
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(404, "Activity not found.")
    if activity.professor_id != professor.id:
        raise HTTPException(403, "You can only move your own activities.")
    if new_date < today:
        raise HTTPException(400, "The new date is in the past.")
    try:
        start, end = booking_window(start_time, end_time)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    room = db.get(Classroom, new_classroom_id)
    if room is None:
        raise HTTPException(404, "Room not found.")
    if not room.is_bookable:
        raise HTTPException(400, "This room cannot be booked.")

    is_one_off = activity.specific_date is not None
    if is_one_off:
        if original_date != activity.specific_date:
            raise HTTPException(400, "A one-off activity moves on its own date.")
    elif (
        db.scalar(
            select(ActivityException.id).where(
                ActivityException.activity_id == activity.id,
                ActivityException.original_date == original_date,
            )
        )
        is not None
    ):
        raise HTTPException(400, "This occurrence has already been moved.")
    if not occurrences(db, original_date, original_date, Activity.id == activity.id):
        raise HTTPException(400, "There is no occurrence of this activity on that date.")

    groups = [
        (group.id, group.name)
        for group in db.scalars(
            select(StudentGroup)
            .join(ActivityGroup, ActivityGroup.group_id == StudentGroup.id)
            .where(ActivityGroup.activity_id == activity.id)
        ).all()
    ]
    same_day = new_date == original_date
    reasons = slot_clashes(
        db,
        new_date,
        start,
        end,
        professor.id,
        groups,
        room.id,
        exclude_activity_id=activity.id if same_day else None,
    )
    if reasons:
        raise HTTPException(409, " ".join(reasons))

    if is_one_off:
        activity.status = Status.CANCELLED
        activity.is_manually_modified = True
    else:
        db.add(
            ActivityException(
                activity_id=activity.id,
                original_date=original_date,
                is_cancelled=True,
                created_by_id=user.id,
            )
        )
    new = Activity(
        name=activity.name,
        type=activity.type,
        priority=activity.priority,
        classroom_id=room.id,
        day_of_week=new_date.isoweekday(),
        start_time=start,
        end_time=end,
        parity=Parity.ALL,
        specific_date=new_date,
        professor_id=activity.professor_id,
        professor_name=activity.professor_name,
        user_id=user.id,
        status=Status.APPROVED,
        is_manually_modified=True,
    )
    db.add(new)
    db.flush()
    for group_id, _ in groups:
        db.add(ActivityGroup(activity_id=new.id, group_id=group_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This occurrence was just moved.") from None
    db.refresh(new)
    return new, room
