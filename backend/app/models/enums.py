import enum


class Role(str, enum.Enum):
    STUDENT = "STUDENT"
    PROFESSOR = "PROFESSOR"
    STUDENT_ORG = "STUDENT_ORG"
    ADMIN = "ADMIN"


class ActivityType(str, enum.Enum):
    COURSE = "COURSE"
    LAB = "LAB"
    SEMINAR = "SEMINAR"
    EXAM = "EXAM"
    RESERVATION = "RESERVATION"


class Parity(str, enum.Enum):
    ALL = "ALL"
    EVEN = "EVEN"
    ODD = "ODD"
    CUSTOM = "CUSTOM"  # not usable yet: blocked by a CHECK until the customization flow exists


class Status(str, enum.Enum):
    APPROVED = "APPROVED"
    BUMPED_PENDING = "BUMPED_PENDING"
    CANCELLED = "CANCELLED"


class PlanningUnitType(str, enum.Enum):
    SEMESTER = "SEMESTER"
    MODULE = "MODULE"


class RequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class BookingStatus(str, enum.Enum):
    """Lowercase values, as confirmed for the bookings table. Only `approved` bookings block a slot (later step)."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class BoardType(str, enum.Enum):
    """Lowercase values, as in the classrooms.board_type column (admin-managed, never set by the ETL)."""

    WHITEBOARD = "whiteboard"
    BLACKBOARD = "blackboard"
    SMARTBOARD = "smartboard"
    NONE = "none"


class Priority(enum.IntEnum):
    """Higher number wins a bump: course > exam > official faculty > student org > student."""

    STUDENT = 1
    STUDENT_ORG = 2
    OFFICIAL_FACULTY = 3
    EXAM = 4
    COURSE = 5
