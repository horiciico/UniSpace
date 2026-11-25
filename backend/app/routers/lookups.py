import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Activity, ActivityGroup, Faculty, PlanningTimeUnit, StudentGroup

router = APIRouter(prefix="/api", tags=["lookups"])


@router.get("/faculties")
def list_faculties(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {"id": str(f.id), "code": f.code, "name": f.name}
        for f in db.scalars(select(Faculty).order_by(Faculty.name)).all()
    ]


def faculty_groups(faculty_id: uuid.UUID):
    """Study formations of a faculty: groups with an activity in one of its units."""
    return (
        select(StudentGroup)
        .join(ActivityGroup, ActivityGroup.group_id == StudentGroup.id)
        .join(Activity, Activity.id == ActivityGroup.activity_id)
        .join(PlanningTimeUnit, PlanningTimeUnit.id == Activity.planning_time_unit_id)
        .where(PlanningTimeUnit.faculty_id == faculty_id)
        .distinct()
        .order_by(StudentGroup.name)
    )


@router.get("/groups")
def list_groups(faculty_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict]:
    """Student groups with at least one activity in a planning unit of the faculty."""
    return [
        {"id": str(group.id), "name": group.name, "faculty_id": str(faculty_id)}
        for group in db.scalars(faculty_groups(faculty_id)).all()
    ]


@router.get("/professors")
def list_professors(faculty_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict]:
    """Professors named on the faculty's activities. A joint activity lists several names."""
    stmt = (
        select(Activity.professor_name)
        .join(PlanningTimeUnit, PlanningTimeUnit.id == Activity.planning_time_unit_id)
        .where(PlanningTimeUnit.faculty_id == faculty_id, Activity.professor_name.is_not(None))
        .distinct()
    )
    names = {
        part.strip()
        for raw in db.scalars(stmt).all()
        if raw
        for part in raw.split(" / ")
        if part.strip()
    }
    return [{"name": name} for name in sorted(names)]
