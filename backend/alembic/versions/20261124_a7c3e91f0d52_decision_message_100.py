"""decision message limit: 100 characters (was 1000)

Revision ID: a7c3e91f0d52
Revises: 3b4860b5bd9c
Create Date: 2026-11-24 19:00:00.000000

"""
from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7c3e91f0d52'
down_revision: str | None = '3b4860b5bd9c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint('ck_booking_decision_message_length', 'bookings', type_='check')
    op.create_check_constraint('ck_booking_decision_message_length', 'bookings',
                               'decision_message IS NULL OR char_length(decision_message) <= 100')


def downgrade() -> None:
    op.drop_constraint('ck_booking_decision_message_length', 'bookings', type_='check')
    op.create_check_constraint('ck_booking_decision_message_length', 'bookings',
                               'decision_message IS NULL OR char_length(decision_message) <= 1000')
