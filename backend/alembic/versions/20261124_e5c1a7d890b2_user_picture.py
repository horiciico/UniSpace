"""user picture from google oauth

Revision ID: e5c1a7d890b2
Revises: b0f9c8035187
Create Date: 2026-11-24 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5c1a7d890b2'
down_revision: str | None = 'b0f9c8035187'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('picture', sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'picture')

