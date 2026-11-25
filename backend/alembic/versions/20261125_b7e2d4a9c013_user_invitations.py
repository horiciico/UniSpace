"""user_invitations: an admin's invitation for an email to sign in with a non-admin role

- user_invitations: UUID primary key; email VARCHAR(255), lower-case (CHECK); role (the native
  "role" enum; non-admin is enforced by the application, not here); token VARCHAR(128), unique,
  plain text (accepted trade-off: the admin copies the link again); invited_by → users.id,
  ON DELETE SET NULL; status (native invitation_status: pending, accepted, revoked, default
  pending); expires_at TIMESTAMPTZ, default now() + 7 days; created_at TIMESTAMPTZ, default now().
- A partial unique index on lower(email) WHERE status = 'pending': at most one active invitation
  per email. Accepted and revoked rows are kept and do not block a new invitation.

The old invitations table is untouched (it is no longer read for sign-in, D-020 / D-025).

Downgrade: drops the table and the invitation_status enum. Invitations are lost.

Revision ID: b7e2d4a9c013
Revises: f3a9c2d71e05
Create Date: 2026-11-25 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7e2d4a9c013'
down_revision: str | None = 'f3a9c2d71e05'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

role = postgresql.ENUM('STUDENT', 'PROFESSOR', 'STUDENT_ORG', 'ADMIN', name='role',
                       create_type=False)
invitation_status = postgresql.ENUM('pending', 'accepted', 'revoked', name='invitation_status',
                                    create_type=False)


def upgrade() -> None:
    invitation_type = postgresql.ENUM('pending', 'accepted', 'revoked', name='invitation_status')
    invitation_type.create(op.get_bind(), checkfirst=False)
    op.create_table(
        'user_invitations',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', role, nullable=False),
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column('invited_by', sa.Uuid(), nullable=True),
        sa.Column('status', invitation_status, server_default=sa.text("'pending'"),
                  nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True),
                  server_default=sa.text("now() + interval '7 days'"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.CheckConstraint('email = lower(email)', name='ck_user_invitation_email_lowercase'),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'],
                                name='fk_user_invitations_invited_by', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index('uq_user_invitations_pending_email', 'user_invitations',
                    [sa.text('lower(email)')], unique=True,
                    postgresql_where=sa.text("status = 'pending'"))


def downgrade() -> None:
    op.drop_index('uq_user_invitations_pending_email', table_name='user_invitations')
    op.drop_table('user_invitations')
    postgresql.ENUM(name='invitation_status').drop(op.get_bind(), checkfirst=False)
