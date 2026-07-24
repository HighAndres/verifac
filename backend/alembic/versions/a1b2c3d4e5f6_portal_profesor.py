"""portal profesor: usuarios.profesor_id y profesores.drive_url

Revision ID: a1b2c3d4e5f6
Revises: d50f5838fbe4
Create Date: 2026-07-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd50f5838fbe4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('profesores', sa.Column('drive_url', sa.String(length=500), nullable=True))
    op.add_column('usuarios', sa.Column('profesor_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_usuarios_profesor_id'), 'usuarios', ['profesor_id'], unique=False)
    op.create_foreign_key(
        'fk_usuarios_profesor_id_profesores',
        'usuarios', 'profesores',
        ['profesor_id'], ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_usuarios_profesor_id_profesores', 'usuarios', type_='foreignkey')
    op.drop_index(op.f('ix_usuarios_profesor_id'), table_name='usuarios')
    op.drop_column('usuarios', 'profesor_id')
    op.drop_column('profesores', 'drive_url')
