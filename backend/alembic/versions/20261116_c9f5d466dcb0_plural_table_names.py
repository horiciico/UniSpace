"""plural table names

Revision ID: c9f5d466dcb0
Revises: a450e1ab3044
Create Date: 2026-11-16 19:04:42.197927

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9f5d466dcb0'
down_revision: str | None = 'a450e1ab3044'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Tables named in the singular by the first two revisions are renamed to plural, to match
# the models. Renames keep rows, constraints and indexes; the index names still say "activity".
RENAMES = [
    ("classroom", "classrooms"),
    ("student_group", "student_groups"),
    ("user", "users"),
    ("activity", "activities"),
    ("event_exception", "event_exceptions"),
    ("invitation", "invitations"),
]


def upgrade() -> None:
    for old, new in RENAMES:
        op.rename_table(old, new)


def downgrade() -> None:
    for old, new in reversed(RENAMES):
        op.rename_table(new, old)
