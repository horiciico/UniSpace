import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Role, StudentGroup, User
from app.routers.auth import UserOut
from app.routers.lookups import faculty_groups

router = APIRouter(prefix="/api", tags=["study profile"])


class StudyProfile(BaseModel):
    faculty_id: uuid.UUID
    study_formation_id: uuid.UUID


@router.put("/me/study-profile", response_model=UserOut)
def save_study_profile(
    body: StudyProfile, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> User:
    """A student's faculty and study formation (D-022). The formation must belong to the faculty."""
    if user.role != Role.STUDENT:
        raise HTTPException(403, "Only students choose a faculty and a study formation.")
    formation = db.scalar(
        faculty_groups(body.faculty_id).where(StudentGroup.id == body.study_formation_id)
    )
    if formation is None:
        raise HTTPException(422, "That study formation is not in the chosen faculty.")
    user.faculty_id = body.faculty_id
    user.study_formation_id = formation.id
    db.commit()
    return user
