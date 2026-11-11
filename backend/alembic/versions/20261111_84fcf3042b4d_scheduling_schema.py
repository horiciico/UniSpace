"""scheduling schema

Revision ID: 84fcf3042b4d
Revises: 
Create Date: 2026-11-11 22:14:11.383015

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '84fcf3042b4d'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # btree_gist lets the GiST index below mix uuid/smallint columns with the int4range.
    op.execute('CREATE EXTENSION IF NOT EXISTS btree_gist')
    op.create_table('classroom',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False),
    sa.Column('has_projector', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('has_outlets', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('access_status', sa.Text(), nullable=True),
    sa.CheckConstraint('capacity > 0', name='ck_classroom_capacity'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('student_group',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('role', sa.Enum('STUDENT', 'PROFESSOR', 'STUDENT_ORG', 'ADMIN', name='role'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('activity',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('type', sa.Enum('COURSE', 'LAB', 'SEMINAR', 'EXAM', 'RESERVATION', name='activity_type'), nullable=False),
    sa.Column('priority', sa.SmallInteger(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('group_id', sa.Uuid(), nullable=True),
    sa.Column('classroom_id', sa.Uuid(), nullable=False),
    sa.Column('day_of_week', sa.SmallInteger(), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('end_time', sa.Time(), nullable=False),
    sa.Column('parity', sa.Enum('ALL', 'EVEN', 'ODD', 'CUSTOM', name='parity'), server_default='ALL', nullable=False),
    sa.Column('time_range', postgresql.INT4RANGE(), sa.Computed("int4range(least((extract(hour from start_time)::int * 60 + extract(minute from start_time)::int), (extract(hour from end_time)::int * 60 + extract(minute from end_time)::int)), greatest((extract(hour from start_time)::int * 60 + extract(minute from start_time)::int), (extract(hour from end_time)::int * 60 + extract(minute from end_time)::int)), '[)')", persisted=True), nullable=False),
    sa.Column('status', sa.Enum('APPROVED', 'BUMPED_PENDING', 'CANCELLED', name='status'), server_default='APPROVED', nullable=False),
    sa.Column('alt_classroom_id', sa.Uuid(), nullable=True),
    sa.Column('alt_start_datetime', sa.DateTime(), nullable=True),
    sa.Column('alt_end_datetime', sa.DateTime(), nullable=True),
    sa.Column('bumped_date', sa.Date(), nullable=True),
    sa.Column('bump_decision_deadline', sa.DateTime(), nullable=True),
    sa.CheckConstraint("parity <> 'CUSTOM'", name='ck_activity_parity_custom_unusable'),
    sa.CheckConstraint('day_of_week BETWEEN 1 AND 7', name='ck_activity_day_of_week'),
    sa.CheckConstraint('end_time > start_time', name='ck_activity_time_order'),
    sa.CheckConstraint('priority BETWEEN 1 AND 5', name='ck_activity_priority'),
    sa.ForeignKeyConstraint(['alt_classroom_id'], ['classroom.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['classroom_id'], ['classroom.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['group_id'], ['student_group.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_activity_day_parity', 'activity', ['day_of_week', 'parity'], unique=False)
    op.create_index('ix_activity_group_day', 'activity', ['group_id', 'day_of_week'], unique=False)
    op.create_index('ix_activity_room_day_start_end', 'activity', ['classroom_id', 'day_of_week', 'start_time', 'end_time'], unique=False)
    op.create_index('ix_activity_room_day_time_range', 'activity', ['classroom_id', 'day_of_week', 'time_range'], unique=False, postgresql_using='gist')
    op.create_table('event_exception',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('activity_id', sa.Uuid(), nullable=False),
    sa.Column('original_date', sa.Date(), nullable=False),
    sa.Column('new_date', sa.Date(), nullable=True),
    sa.Column('new_classroom_id', sa.Uuid(), nullable=True),
    sa.Column('is_cancelled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.ForeignKeyConstraint(['activity_id'], ['activity.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['new_classroom_id'], ['classroom.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('activity_id', 'original_date', name='uq_event_exception_occurrence')
    )


def downgrade() -> None:
    op.drop_table('event_exception')
    op.drop_index('ix_activity_room_day_time_range', table_name='activity', postgresql_using='gist')
    op.drop_index('ix_activity_room_day_start_end', table_name='activity')
    op.drop_index('ix_activity_group_day', table_name='activity')
    op.drop_index('ix_activity_day_parity', table_name='activity')
    op.drop_table('activity')
    op.drop_table('user')
    op.drop_table('student_group')
    op.drop_table('classroom')
    for enum_name in ('status', 'parity', 'activity_type', 'role'):
        op.execute(f'DROP TYPE {enum_name}')
