"""user_invitations.expires_at default: 48 hours (was 7 days)

Only the default changes. Pending invitations already stored keep the expires_at they were given.

Downgrade: the default goes back to 7 days.

Revision ID: d5a9f0c3b8e1
Revises: c4d1e8f2a7b9
Create Date: 2026-11-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5a9f0c3b8e1"
down_revision: str | None = "c4d1e8f2a7b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "user_invitations", "expires_at", server_default=sa.text("now() + interval '2 days'")
    )


def downgrade() -> None:
    op.alter_column(
        "user_invitations", "expires_at", server_default=sa.text("now() + interval '7 days'")
    )
