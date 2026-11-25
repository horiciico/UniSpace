import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Classroom
from app.models.enums import BoardType
from app.routers.admin_bookings import require_admin
from app.routers.classrooms import faculty_condition

router = APIRouter(prefix="/api/admin/classrooms", tags=["admin classrooms"])


class RoomUpdate(BaseModel):
    """Only the fields sent are changed. A null clears a nullable field (back to unspecified)."""

    is_bookable: bool | None = None
    has_projector: bool | None = None
    board_type: BoardType | None = None
    access_notes: str | None = Field(default=None, max_length=255)
    equipment_notes: str | None = Field(default=None, max_length=500)

    @field_validator("is_bookable")
    @classmethod
    def not_null(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("is_bookable cannot be null")
        return value

    @field_validator("access_notes", "equipment_notes")
    @classmethod
    def blank_is_none(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip()


def room_out(room: Classroom) -> dict:
    return {
        "id": str(room.id),
        "name": room.name,
        "faculty_id": str(room.faculty_id) if room.faculty_id else None,
        "capacity": room.capacity,
        "is_bookable": room.is_bookable,
        "has_projector": room.has_projector,
        "board_type": room.board_type.value if room.board_type else None,
        "access_notes": room.access_notes,
        "equipment_notes": room.equipment_notes,
    }


@router.get("")
def list_rooms(
    faculty_id: str | None = Query(None),
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(Classroom).order_by(Classroom.name)
    condition = faculty_condition(faculty_id)
    if condition is not None:
        stmt = stmt.where(condition)
    return [room_out(room) for room in db.scalars(stmt).all()]


@router.patch("/{classroom_id}")
def update_room(
    classroom_id: uuid.UUID,
    body: RoomUpdate,
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    room = db.get(Classroom, classroom_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found.")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(room, field, value)
    db.commit()
    db.refresh(room)
    return room_out(room)
