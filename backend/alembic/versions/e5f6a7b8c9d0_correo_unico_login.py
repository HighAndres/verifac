"""correo único (case-insensitive) para login por correo

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-12

Índice único parcial sobre lower(correo). Es parcial (WHERE correo IS NOT NULL)
para no chocar con las filas que aún no tienen correo capturado.
"""
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX ix_usuarios_correo_lower "
        "ON usuarios (lower(correo)) WHERE correo IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_usuarios_correo_lower")
