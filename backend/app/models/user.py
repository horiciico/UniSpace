import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import Role

if TYPE_CHECKING:
    from app.models.activity import Activity


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"))
    google_sub: Mapped[str | None] = mapped_column(
        String(255), unique=True
    )  # Google's immutable subject id
    professor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid
    )  # ULBS professorId of a professor account (no FK)
    # Student onboarding (D-022): chosen on first sign-in; filled only for students.
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("faculties.id", ondelete="SET NULL", name="fk_users_faculty")
    )
    study_formation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("student_groups.id", ondelete="SET NULL", name="fk_users_study_formation")
    )
    picture: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # An admin set this role (Users tab or an accepted invitation); sign-in keeps it (D-025).
    role_set_by_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    activities: Mapped[list["Activity"]] = relationship(back_populates="user")  # noqa: F821

    @property
    def needs_onboarding(self) -> bool:
        """A student who has not chosen a faculty yet (D-022)."""
        return self.role == Role.STUDENT and self.faculty_id is None
