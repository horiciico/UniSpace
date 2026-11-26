"""A professor's subjects, and scheduling an exam for some of their groups.

- professor_subjects: the distinct subjects the professor teaches (activities not CANCELLED),
  each with the groups that take part. Subjects are matched by name.
- schedule_exam: one one-off EXAM activity for the chosen groups, after the room, the professor
  and every group are checked free on the day and time (409 with the reasons otherwise).
  One atomic write.
"""

import uuid
from collections import defaultdict
from datetime import date, time

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.availability import slot_clashes
from app.models import (
    Activity,
    ActivityGroup,
    ActivityType,
    Classroom,
    Parity,
    Priority,
    Professor,
    Status,
    StudentGroup,
    User,
)

# Exam times (D-030): start on :00 or :30, length a multiple of 30 minutes and at least 1 hour,
# between 08:00 and 21:30. Exams are not on the 90-minute module grid.
EXAM_EARLIEST = time(8, 0)
EXAM_LATEST = time(21, 30)


def exam_window(start: time, end: time) -> tuple[time, time]:
    """The exam's start and end if they are on the exam grid; raises ValueError otherwise."""
    if start.second or start.microsecond or end.second or end.microsecond:
        raise ValueError("An exam starts and ends on the minute.")
    if start.minute % 30:
        raise ValueError("An exam starts on the hour or the half hour.")
    if end <= start:
        raise ValueError("end_time must be after start_time")
    length = (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)
    if length < 60 or length % 30:
        raise ValueError("An exam lasts a whole number of half hours, at least one hour.")
    if start < EXAM_EARLIEST or end > EXAM_LATEST:
        raise ValueError("An exam runs between 08:00 and 21:30.")
    return start, end


def professor_subjects(db: Session, professor: Professor) -> list[dict]:
    """[{name, groups: [{id, name}]}] by subject name, each subject's groups by name."""
    rows = db.execute(
        select(Activity.name, StudentGroup.id, StudentGroup.name)
        .outerjoin(ActivityGroup, ActivityGroup.activity_id == Activity.id)
        .outerjoin(StudentGroup, StudentGroup.id == ActivityGroup.group_id)
        .where(Activity.professor_id == professor.id, Activity.status != Status.CANCELLED)
    ).all()
    groups_of: dict[str, dict[uuid.UUID, str]] = defaultdict(dict)
    for name, group_id, group_name in rows:
        bucket = groups_of[name]  # a subject with no group still counts
        if group_id is not None:
            bucket[group_id] = group_name
    return [
        {
            "name": name,
            "groups": [
                {"id": str(group_id), "name": group_name}
                for group_id, group_name in sorted(bucket.items(), key=lambda item: item[1])
            ],
        }
        for name, bucket in sorted(groups_of.items())
    ]


def schedule_exam(
    db: Session,
    professor: Professor,
    user: User,
    subject_name: str,
    group_ids: list[uuid.UUID],
    exam_date: date,
    start_time: time,
    end_time: time,
    classroom_id: uuid.UUID,
    today: date,
) -> tuple[Activity, Classroom, list[str]]:
    """Schedule the exam. Returns the activity, its room and the group names, or raises."""
    subject = next(
        (s for s in professor_subjects(db, professor) if s["name"] == subject_name), None
    )
    if subject is None:
        raise HTTPException(400, "You do not teach this subject.")
    allowed = {group["id"]: group["name"] for group in subject["groups"]}
    chosen = list(dict.fromkeys(str(group_id) for group_id in group_ids))
    if not chosen:
        raise HTTPException(400, "Choose at least one group.")
    if any(group_id not in allowed for group_id in chosen):
        raise HTTPException(400, "A group is not taught in this subject.")
    if exam_date < today:
        raise HTTPException(400, "The exam date is in the past.")
    try:
        start, end = exam_window(start_time, end_time)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    room = db.get(Classroom, classroom_id)
    if room is None:
        raise HTTPException(404, "Room not found.")
    if not room.is_bookable:
        raise HTTPException(400, "This room cannot be booked.")

    groups = [(uuid.UUID(group_id), allowed[group_id]) for group_id in chosen]
    reasons = slot_clashes(db, exam_date, start, end, professor.id, groups, room.id)
    if reasons:
        raise HTTPException(409, " ".join(reasons))

    exam = Activity(
        name=subject_name,
        type=ActivityType.EXAM,
        priority=Priority.EXAM,
        classroom_id=room.id,
        day_of_week=exam_date.isoweekday(),
        start_time=start,
        end_time=end,
        parity=Parity.ALL,
        specific_date=exam_date,
        professor_id=professor.id,
        professor_name=professor.name,
        user_id=user.id,
        status=Status.APPROVED,
        is_manually_modified=True,
    )
    db.add(exam)
    db.flush()
    for group_id, _ in groups:
        db.add(ActivityGroup(activity_id=exam.id, group_id=group_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This exam was just scheduled.") from None
    db.refresh(exam)
    return exam, room, sorted(name for _, name in groups)
