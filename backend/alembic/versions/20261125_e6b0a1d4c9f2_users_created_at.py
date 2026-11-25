"""users.created_at: when the account was first created (for the admin Users tab)

- users.created_at TIMESTAMPTZ NOT NULL, default now(). Existing accounts get the time this
  migration ran, since their real creation time was never stored.

Downgrade: drops the column.

Revision ID: e6b0a1d4c9f2
Revises: d5a9f0c3b8e1
Create Date: 2026-11-25 12:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6b0a1d4c9f2"
down_revision: str | None = "d5a9f0c3b8e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "created_at")
