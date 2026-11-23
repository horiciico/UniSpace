"""Seeder: one demo course for the ing faculty, to check the app end to end.

Adds "Demo Course" (Curs Demo):
- faculty ing, its current planning unit (so the timetable shows it for the current week);
- Friday (ISO day 5), in room IE102, in a module (90 minutes) that no other activity of the room uses;
- parity ALL, type COURSE, priority 5 (course);
- student group "test" (created if missing);
- professor from --professor-email (created if missing). A Google sign-in with that address gets
  the PROFESSOR role (D-020), because the address is in the professors table.

The module is picked at random among the open ones. Running it again does not add a second copy.

The professor's address is an argument, so it is not written in this file:
    docker compose run --rm -e PYTHONPATH=/app -v "C:/Users/Horishca/Desktop/UniSpace/scripts:/app/scripts" backend python scripts/seeders/seed_demo_course.py --professor-email <address>
"""

import argparse
import random
import uuid
from datetime import time

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Activity,
    ActivityGroup,
    ActivityType,
    Classroom,
    Faculty,
    Parity,
    PlanningTimeUnit,
    Priority,
    Professor,
    Status,
    StudentGroup,
)
from app.planning import MODULES

FACULTY_CODE = "ing"
ROOM_NAME = "IE102"
COURSE_NAME = "Demo Course"
DAY_FRIDAY = 5  # ISO, Monday = 1 (D-008)
GROUP_NAME = "test"
PROFESSOR_NAME = "Demo Professor"


def overlaps(start: time, end: time, other_start: time, other_end: time) -> bool:
    return start < other_end and other_start < end


def open_modules(busy: list[tuple[time, time]]) -> list[tuple[time, time]]:
    """The modules that no busy interval of the room overlaps."""
    return [m for m in MODULES if not any(overlaps(m[0], m[1], s, e) for s, e in busy)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Add the Demo Course for a demo sign-in.")
    parser.add_argument("--professor-email", required=True, help="the professor address to link")
    professor_email = parser.parse_args(argv).professor_email.strip().lower()
    with SessionLocal() as db:
        faculty = db.scalar(select(Faculty).where(Faculty.code == FACULTY_CODE))
        if faculty is None:
            print("No ing faculty in the database. Run the schedule sync step first.")
            return 1
        room = db.scalar(select(Classroom).where(Classroom.name == ROOM_NAME, Classroom.faculty_id == faculty.id))
        if room is None:
            print(f"No room {ROOM_NAME} for the ing faculty in the database.")
            return 1

        already = db.scalar(select(Activity.id).where(
            Activity.name == COURSE_NAME, Activity.classroom_id == room.id, Activity.day_of_week == DAY_FRIDAY,
        ))
        if already is not None:
            print(f"{COURSE_NAME} is already in {ROOM_NAME} on Friday: nothing added.")
            return 0

        busy = [(a.start_time, a.end_time) for a in db.scalars(
            select(Activity).where(Activity.classroom_id == room.id, Activity.day_of_week == DAY_FRIDAY)
        ).all()]
        options = open_modules(busy)
        if not options:
            print(f"No open module in {ROOM_NAME} on Friday.")
            return 1
        start, end = random.choice(options)

        unit = db.scalar(select(PlanningTimeUnit).where(
            PlanningTimeUnit.faculty_id == faculty.id, PlanningTimeUnit.is_current.is_(True),
        ))

        professor = db.scalar(select(Professor).where(Professor.email == professor_email))
        if professor is None:
            professor = Professor(id=uuid.uuid4(), name=PROFESSOR_NAME, email=professor_email)
            db.add(professor)
            db.flush()

        group = db.scalar(select(StudentGroup).where(
            StudentGroup.name == GROUP_NAME, StudentGroup.external_id.is_(None),
        ))
        if group is None:
            group = StudentGroup(name=GROUP_NAME)
            db.add(group)
            db.flush()

        activity = Activity(
            name=COURSE_NAME,
            type=ActivityType.COURSE,
            priority=Priority.COURSE,
            group_id=group.id,
            classroom_id=room.id,
            day_of_week=DAY_FRIDAY,
            start_time=start,
            end_time=end,
            parity=Parity.ALL,
            status=Status.APPROVED,
            planning_time_unit_id=unit.id if unit is not None else None,
            professor_name=PROFESSOR_NAME,
            professor_id=professor.id,
        )
        db.add(activity)
        db.flush()
        db.add(ActivityGroup(activity_id=activity.id, group_id=group.id))
        db.commit()

    print(f"Added {COURSE_NAME} in {ROOM_NAME}, Friday {start:%H:%M}-{end:%H:%M}, group {GROUP_NAME}, "
          f"professor {professor_email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
