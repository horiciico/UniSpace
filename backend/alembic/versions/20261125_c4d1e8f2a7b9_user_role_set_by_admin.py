"""users.role_set_by_admin: a role an admin set is kept on every sign-in (D-025)

- users.role_set_by_admin BOOLEAN NOT NULL, default false. An admin's role change (the Users tab)
  and a role given by an accepted invitation set it to true. A sign-in keeps such a role and does
  not overwrite it. Existing rows are false, so they keep the D-020 rules until an admin changes them.

Downgrade: drops the column. Admin-set roles then follow the sign-in rules again.

Revision ID: c4d1e8f2a7b9
Revises: b7e2d4a9c013
Create Date: 2026-11-25 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4d1e8f2a7b9'
down_revision: str | None = 'b7e2d4a9c013'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('role_set_by_admin', sa.Boolean(), server_default=sa.text(
        'false'), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'role_set_by_admin')
