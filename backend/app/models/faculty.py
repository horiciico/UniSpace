import uuid

from sqlalchemy import String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Faculty(Base):
    """A faculty from the ULBS API. `code` is the API id, e.g. "dre" (Facultatea de Drept)."""

    __tablename__ = "faculties"
    __table_args__ = (UniqueConstraint("code", name="uq_faculty_code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(255))
