"""planning units, faculties, ETL binding, exceptions and rule change requests

Decisions: D-014 (parity), D-015 (planning unit binding, ETL skips manual rows),
D-016 (one-off exceptions, permanent changes by request). The off_limits table
(D-017) waits for Q-014 and is not in this revision.

Revision ID: 6a3817a9edb2
Revises: c9f5d466dcb0
Create Date: 2026-11-19 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a3817a9edb2'
down_revision: str | None = 'c9f5d466dcb0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Faculties from the ULBS API. `code` is the API id (e.g. "dre").
    op.create_table('faculties',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code', name='uq_faculty_code')
    )

    # Active period per faculty, from the ULBS API (Q-008, planning_time_units).
    op.create_table('planning_time_units',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('faculty_id', sa.Uuid(), nullable=False),
    sa.Column('external_id', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('type', sa.Enum('SEMESTER', 'MODULE', name='planning_unit_type'), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.Column('is_current', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.CheckConstraint('end_date >= start_date', name='ck_planning_unit_dates'),
    sa.ForeignKeyConstraint(['faculty_id'], ['faculties.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('faculty_id', 'external_id', name='uq_planning_unit_external')
    )

    # Rooms: the ULBS room id and the faculty it belongs to. Capacity stays required.
    op.add_column('classrooms', sa.Column('faculty_id', sa.Uuid(), nullable=True))
    op.add_column('classrooms', sa.Column('external_id', sa.String(length=50), nullable=True))
    op.create_foreign_key('fk_classroom_faculty', 'classrooms', 'faculties',
                          ['faculty_id'], ['id'], ondelete='SET NULL')
    op.create_unique_constraint('uq_classroom_external', 'classrooms', ['faculty_id', 'external_id'])

    # Activities: imported rows carry the ETL binding; specific_date makes a one-off row.
    op.add_column('activities', sa.Column('planning_time_unit_id', sa.Uuid(), nullable=True))
    op.add_column('activities', sa.Column('external_id', sa.String(length=50), nullable=True))
    op.add_column('activities', sa.Column('is_manually_modified', sa.Boolean(),
                                          server_default=sa.text('false'), nullable=False))
    op.add_column('activities', sa.Column('specific_date', sa.Date(), nullable=True))
    op.add_column('activities', sa.Column('professor_name', sa.String(length=255), nullable=True))
    op.create_foreign_key('fk_activity_planning_unit', 'activities', 'planning_time_units',
                          ['planning_time_unit_id'], ['id'], ondelete='RESTRICT')
    op.create_unique_constraint('uq_activity_unit_external', 'activities',
                                ['planning_time_unit_id', 'external_id'])
    op.create_check_constraint(
        'ck_activity_specific_date_weekday', 'activities',
        'specific_date IS NULL OR extract(isodow from specific_date)::int = day_of_week',
    )

    # event_exceptions becomes activity_exceptions (D-016). Index and constraint names keep
    # the old word, as in the earlier plural-names revision.
    op.rename_table('event_exceptions', 'activity_exceptions')
    op.add_column('activity_exceptions', sa.Column('new_start_time', sa.Time(), nullable=True))
    op.add_column('activity_exceptions', sa.Column('new_end_time', sa.Time(), nullable=True))
    op.add_column('activity_exceptions', sa.Column('reason', sa.Text(), nullable=True))
    op.add_column('activity_exceptions', sa.Column('created_by_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_activity_exception_created_by', 'activity_exceptions', 'users',
                          ['created_by_id'], ['id'], ondelete='SET NULL')
    op.create_check_constraint(
        'ck_activity_exception_time_order', 'activity_exceptions',
        'new_start_time IS NULL OR new_end_time IS NULL OR new_end_time > new_start_time',
    )

    # Permanent change requests: a professor asks, an admin decides (D-016).
    op.create_table('rule_change_requests',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('activity_id', sa.Uuid(), nullable=False),
    sa.Column('requested_by_id', sa.Uuid(), nullable=False),
    sa.Column('reviewed_by_id', sa.Uuid(), nullable=True),
    sa.Column('new_classroom_id', sa.Uuid(), nullable=True),
    sa.Column('new_day_of_week', sa.SmallInteger(), nullable=True),
    sa.Column('new_start_time', sa.Time(), nullable=True),
    sa.Column('new_end_time', sa.Time(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', name='request_status'),
              server_default='PENDING', nullable=False),
    sa.CheckConstraint('new_day_of_week BETWEEN 1 AND 7', name='ck_rule_change_day_of_week'),
    sa.CheckConstraint(
        'new_classroom_id IS NOT NULL OR new_day_of_week IS NOT NULL '
        'OR new_start_time IS NOT NULL OR new_end_time IS NOT NULL',
        name='ck_rule_change_has_change',
    ),
    sa.CheckConstraint(
        'new_start_time IS NULL OR new_end_time IS NULL OR new_end_time > new_start_time',
        name='ck_rule_change_time_order',
    ),
    sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['requested_by_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['new_classroom_id'], ['classrooms.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('rule_change_requests')
    op.execute('DROP TYPE request_status')

    op.drop_constraint('ck_activity_exception_time_order', 'activity_exceptions', type_='check')
    op.drop_constraint('fk_activity_exception_created_by', 'activity_exceptions', type_='foreignkey')
    op.drop_column('activity_exceptions', 'created_by_id')
    op.drop_column('activity_exceptions', 'reason')
    op.drop_column('activity_exceptions', 'new_end_time')
    op.drop_column('activity_exceptions', 'new_start_time')
    op.rename_table('activity_exceptions', 'event_exceptions')

    op.drop_constraint('ck_activity_specific_date_weekday', 'activities', type_='check')
    op.drop_constraint('uq_activity_unit_external', 'activities', type_='unique')
    op.drop_constraint('fk_activity_planning_unit', 'activities', type_='foreignkey')
    op.drop_column('activities', 'professor_name')
    op.drop_column('activities', 'specific_date')
    op.drop_column('activities', 'is_manually_modified')
    op.drop_column('activities', 'external_id')
    op.drop_column('activities', 'planning_time_unit_id')

    op.drop_constraint('uq_classroom_external', 'classrooms', type_='unique')
    op.drop_constraint('fk_classroom_faculty', 'classrooms', type_='foreignkey')
    op.drop_column('classrooms', 'external_id')
    op.drop_column('classrooms', 'faculty_id')

    op.drop_table('planning_time_units')
    op.execute('DROP TYPE planning_unit_type')
    op.drop_table('faculties')
