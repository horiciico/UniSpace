"""all groups of a merged activity, and room flags for the free-room search

- activity_groups: one row per (activity, student group). The ETL merges every entry in one
  room, day, parity and time slot into one activity, so one activity can have several groups.
  activities.group_id keeps the first group, as before. This table backfills from it; a
  re-run of the ETL load step adds the other groups of each merged slot.
- classrooms.is_bookable: a room with FALSE is left out of the free-room search. Default TRUE.
- classrooms.is_field_verified: the room was checked on site. Default FALSE ("date estimate").

Revision ID: d41f7c2a9e10
Revises: bc1469b9b255
Create Date: 2026-11-22 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd41f7c2a9e10'
down_revision: str | None = 'bc1469b9b255'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('classrooms', sa.Column('is_bookable', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('classrooms', sa.Column('is_field_verified', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    op.create_table(
        'activity_groups',
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('group_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], name='fk_activity_groups_activity', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['student_groups.id'], name='fk_activity_groups_group', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('activity_id', 'group_id', name='pk_activity_groups'),
    )
    op.create_index('ix_activity_groups_group_id', 'activity_groups', ['group_id'])
    op.execute(
        "INSERT INTO activity_groups (activity_id, group_id) "
        "SELECT id, group_id FROM activities WHERE group_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index('ix_activity_groups_group_id', table_name='activity_groups')
    op.drop_table('activity_groups')
    op.drop_column('classrooms', 'is_field_verified')
    op.drop_column('classrooms', 'is_bookable')
