import uuid

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ActivityGroup(Base):
    """One student group taking part in an activity. A merged ETL slot can have several groups."""

    __tablename__ = "activity_groups"
    __table_args__ = (Index("ix_activity_groups_group_id", "group_id"),)

    activity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE", name="fk_activity_groups_activity"), primary_key=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("student_groups.id", ondelete="CASCADE", name="fk_activity_groups_group"), primary_key=True
    )
