"""ORM models. Import each model module here so Alembic sees it in Base.metadata."""
from app.models.activity import Activity
from app.models.activity_exception import ActivityException
from app.models.activity_group import ActivityGroup
from app.models.classroom import Classroom
from app.models.enums import (
    ActivityType,
    Parity,
    PlanningUnitType,
    Priority,
    RequestStatus,
    Role,
    Status,
)
from app.models.faculty import Faculty
from app.models.invitation import Invitation
from app.models.planning_time_unit import PlanningTimeUnit
from app.models.professor import Professor
from app.models.rule_change_request import RuleChangeRequest
from app.models.student_group import StudentGroup
from app.models.user import User

__all__ = [
    "Activity", "ActivityException", "ActivityGroup", "ActivityType", "Classroom", "Faculty", "Invitation",
    "Parity", "PlanningTimeUnit", "PlanningUnitType", "Priority", "Professor", "RequestStatus",
    "RuleChangeRequest", "Role", "Status", "StudentGroup", "User",
]
