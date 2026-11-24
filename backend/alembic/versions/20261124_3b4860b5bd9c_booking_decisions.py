"""booking decisions: who decided, when, and the message to the requester (issue #23)

Revision ID: 3b4860b5bd9c
Revises: 58cba83b6174
Create Date: 2026-11-24 17:53:36.232443

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b4860b5bd9c'
down_revision: str | None = '58cba83b6174'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('bookings', sa.Column('decided_by_id', sa.Uuid(), nullable=True))
    op.add_column('bookings', sa.Column('decided_at', sa.DateTime(), nullable=True))
    op.add_column('bookings', sa.Column('decision_message', sa.Text(), nullable=True))
    op.create_foreign_key('fk_bookings_decided_by', 'bookings', 'users', ['decided_by_id'], ['id'],
                          ondelete='SET NULL')
    # Alembic does not autogenerate CHECK constraints, so this one is written by hand.
    op.create_check_constraint('ck_booking_decision_message_length', 'bookings',
                               'decision_message IS NULL OR char_length(decision_message) <= 1000')


def downgrade() -> None:
    op.drop_constraint('ck_booking_decision_message_length', 'bookings', type_='check')
    op.drop_constraint('fk_bookings_decided_by', 'bookings', type_='foreignkey')
    op.drop_column('bookings', 'decision_message')
    op.drop_column('bookings', 'decided_at')
    op.drop_column('bookings', 'decided_by_id')
