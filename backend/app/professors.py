"""Which professor a signed-in user is (business rule 6).

A PROFESSOR user is linked to a `professors` row by the address: LOWER(users.email) equals
LOWER(professors.email). A PROFESSOR user with no such row has no activities.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Professor, User


def get_professor_for_user(db: Session, user: User) -> Professor | None:
    """The professor row for this user's address, matched without case; None when unlinked."""
    return db.scalar(select(Professor).where(func.lower(Professor.email) == user.email.lower()))
