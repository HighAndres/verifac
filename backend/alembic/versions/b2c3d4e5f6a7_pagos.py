"""pagos: control de pago a profesores por mes/año

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'pagos',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('profesor_id', sa.UUID(), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('anio', sa.Integer(), nullable=False),
        sa.Column('pagada', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('fecha_pago', sa.Date(), nullable=True),
        sa.Column('metodo_pago', sa.String(length=40), nullable=True),
        sa.Column('monto_pagado', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('registrado_por', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['profesor_id'], ['profesores.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('profesor_id', 'mes', 'anio', name='uq_pago_profesor_periodo'),
    )
    op.create_index(op.f('ix_pagos_profesor_id'), 'pagos', ['profesor_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_pagos_profesor_id'), table_name='pagos')
    op.drop_table('pagos')
