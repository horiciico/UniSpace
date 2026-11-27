"""The admin's data import (D-031, C-012). ADMIN only.

POST starts the schedule and professors pipelines in the background (202; 409 while one runs).
GET answers the state of the current or last run.
"""

from fastapi import APIRouter, Depends, HTTPException

from app import data_import
from app.models import User
from app.routers.admin_bookings import require_admin

router = APIRouter(prefix="/api/admin/data-import", tags=["admin data import"])


@router.get("")
def import_state(admin: User = Depends(require_admin)) -> dict:
    return data_import.state()


@router.post("", status_code=202)
def start_import(admin: User = Depends(require_admin)) -> dict:
    if not data_import.start():
        raise HTTPException(409, "An import is already running.")
    return data_import.state()
