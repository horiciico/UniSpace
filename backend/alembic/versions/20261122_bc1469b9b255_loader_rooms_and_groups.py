"""rooms without capacity, global room ids, student group ids for the ETL loader

- classrooms.capacity becomes nullable: NULL means "unknown capacity" (the ULBS API has no
  value for some rooms). The CHECK capacity > 0 still applies to real values.
- classrooms.external_id is unique on its own: the ULBS room id is global, and a room can be
  used by a faculty other than its owner. The old key was (faculty_id, external_id), which
  does not stop duplicates when faculty_id is NULL.
- student_groups.external_id: the ULBS studyFormation id, unique, so the loader can upsert.

Downgrade fails while any classroom has a NULL capacity; fill or delete those rows first.

Revision ID: bc1469b9b255
Revises: a9cda1e005be
Create Date: 2026-11-22 10:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc1469b9b255'
down_revision: str | None = 'a9cda1e005be'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column('classrooms', 'capacity', existing_type=sa.Integer(), nullable=True)
    op.drop_constraint('uq_classroom_external', 'classrooms', type_='unique')
    op.create_unique_constraint('uq_classroom_external_id', 'classrooms', ['external_id'])

    op.add_column('student_groups', sa.Column('external_id', sa.Integer(), nullable=True))
    op.create_unique_constraint('uq_student_group_external', 'student_groups', ['external_id'])


def downgrade() -> None:
    op.drop_constraint('uq_student_group_external', 'student_groups', type_='unique')
    op.drop_column('student_groups', 'external_id')

    op.drop_constraint('uq_classroom_external_id', 'classrooms', type_='unique')
    op.create_unique_constraint('uq_classroom_external', 'classrooms', ['faculty_id', 'external_id'])
    op.alter_column('classrooms', 'capacity', existing_type=sa.Integer(), nullable=False)
