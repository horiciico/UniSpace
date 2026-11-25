"""classroom attributes: projector unspecified, board type, access and equipment notes

- classrooms.has_projector becomes nullable. Existing rows are set to NULL (unspecified): the ETL
  never set a real value, so the old false was only the default. Free Now treats NULL as no projector.
- classrooms.access_status is renamed to access_notes and becomes VARCHAR(255). The column was
  not used by the ETL or the UI. The change fails if any stored value is longer than 255.
- classrooms.board_type: native enum (whiteboard, blackboard, smartboard, none), nullable.
- classrooms.equipment_notes: VARCHAR(500), nullable, free-text inventory written by an admin.

No row is written by the ETL to these columns; the admin sets them (ETL protection, see the loader test).

Downgrade: rows with a NULL has_projector become false (the old NOT NULL default), and the new
columns and the enum are dropped. The values of board_type, access_notes and equipment_notes are lost.

Revision ID: f3a9c2d71e05
Revises: a7c3e91f0d52
Create Date: 2026-11-24 21:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f3a9c2d71e05'
down_revision: str | None = 'a7c3e91f0d52'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

board_type = postgresql.ENUM('whiteboard', 'blackboard', 'smartboard', 'none', name='board_type')


def upgrade() -> None:
    op.alter_column('classrooms', 'has_projector', existing_type=sa.Boolean(), nullable=True,
                    server_default=None)
    op.execute('UPDATE classrooms SET has_projector = NULL')

    op.alter_column('classrooms', 'access_status', new_column_name='access_notes')
    op.alter_column('classrooms', 'access_notes', existing_type=sa.Text(), type_=sa.String(255),
                    existing_nullable=True)

    board_type.create(op.get_bind(), checkfirst=False)
    op.add_column('classrooms', sa.Column('board_type', board_type, nullable=True))

    op.add_column('classrooms', sa.Column('equipment_notes', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('classrooms', 'equipment_notes')
    op.drop_column('classrooms', 'board_type')
    board_type.drop(op.get_bind(), checkfirst=False)

    op.alter_column('classrooms', 'access_notes', existing_type=sa.String(255), type_=sa.Text(),
                    existing_nullable=True)
    op.alter_column('classrooms', 'access_notes', new_column_name='access_status')

    op.execute('UPDATE classrooms SET has_projector = false WHERE has_projector IS NULL')
    op.alter_column('classrooms', 'has_projector', existing_type=sa.Boolean(), nullable=False,
                    server_default=sa.text('false'))
