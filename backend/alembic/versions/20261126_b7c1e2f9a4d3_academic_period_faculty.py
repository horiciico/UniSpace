"""academic_periods.faculty_id: a period of one faculty, or of all faculties (D-028)

- faculty_id: nullable UUID, FK faculties ON DELETE CASCADE. NULL = all faculties. Existing rows
  stay NULL. Overlap stays an application check, now within the same faculty.

Downgrade: deletes the periods of single faculties (without the column they would count for
everyone), then drops the column.

Revision ID: b7c1e2f9a4d3
Revises: aa97baefd548
Create Date: 2026-11-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1e2f9a4d3"
down_revision: str | None = "aa97baefd548"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("academic_periods", sa.Column("faculty_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_academic_periods_faculty",
        "academic_periods",
        "faculties",
        ["faculty_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.execute("DELETE FROM academic_periods WHERE faculty_id IS NOT NULL")
    op.drop_constraint("fk_academic_periods_faculty", "academic_periods", type_="foreignkey")
    op.drop_column("academic_periods", "faculty_id")
