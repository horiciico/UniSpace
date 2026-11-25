"""google auth

Revision ID: a450e1ab3044
Revises: 84fcf3042b4d
Create Date: 2026-11-16 17:37:22.878726

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a450e1ab3044'
down_revision: str | None = '84fcf3042b4d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('invitation',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('role', postgresql.ENUM('STUDENT', 'PROFESSOR', 'STUDENT_ORG', 'ADMIN', name='role', create_type=False), nullable=False),
    sa.Column('is_used', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.CheckConstraint('email = lower(email)', name='ck_invitation_email_lowercase'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.add_column('user', sa.Column('google_sub', sa.String(length=255), nullable=True))
    op.create_unique_constraint('uq_user_google_sub', 'user', ['google_sub'])


def downgrade() -> None:
    op.drop_constraint('uq_user_google_sub', 'user', type_='unique')
    op.drop_column('user', 'google_sub')
    op.drop_table('invitation')
