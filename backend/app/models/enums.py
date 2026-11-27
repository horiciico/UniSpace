import enum


class Role(enum.StrEnum):
    STUDENT = "STUDENT"
    PROFESSOR = "PROFESSOR"
    STUDENT_ORG = "STUDENT_ORG"
    ADMIN = "ADMIN"


class ActivityType(enum.StrEnum):
    COURSE = "COURSE"
    LAB = "LAB"
    SEMINAR = "SEMINAR"
    EXAM = "EXAM"
    RESERVATION = "RESERVATION"


class Parity(enum.StrEnum):
    ALL = "ALL"
    EVEN = "EVEN"
    ODD = "ODD"
    CUSTOM = "CUSTOM"  # not usable yet: blocked by a CHECK until the customization flow exists


class Status(enum.StrEnum):
    APPROVED = "APPROVED"
    BUMPED_PENDING = "BUMPED_PENDING"
    CANCELLED = "CANCELLED"


class InvitationStatus(enum.StrEnum):
    """Lowercase, as the user_invitations.status values (step 1 of the admin Users tab)."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"


class PlanningUnitType(enum.StrEnum):
    SEMESTER = "SEMESTER"
    MODULE = "MODULE"


class RequestStatus(enum.StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class BookingStatus(enum.StrEnum):
    """Lowercase values, as confirmed for the bookings table. Only `approved` blocks a slot."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class BoardType(enum.StrEnum):
    """Lowercase values, as in classrooms.board_type (admin-managed, never set by the ETL)."""

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


class AcademicPeriodType(enum.StrEnum):
    """What a date range of the academic calendar is (D-027)."""

    TEACHING = "TEACHING"
    EXAM_SESSION = "EXAM_SESSION"
    HOLIDAY = "HOLIDAY"
