"""pagos: quitar monto_pagado, agregar incidencia (motivo de retraso)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('pagos', sa.Column('incidencia', sa.String(length=40), nullable=True))
    op.drop_column('pagos', 'monto_pagado')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('pagos', sa.Column('monto_pagado', sa.Numeric(precision=12, scale=2), nullable=True))
    op.drop_column('pagos', 'incidencia')
