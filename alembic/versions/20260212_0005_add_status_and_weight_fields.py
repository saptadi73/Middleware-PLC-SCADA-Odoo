"""add status and weight fields

Revision ID: 20260212_0005
Revises: 20260212_0004
Create Date: 2026-02-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260212_0005"
down_revision = "20260212_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mo_batch", sa.Column("status_manufacturing", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("mo_batch", sa.Column("status_operation", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("mo_batch", sa.Column("actual_weight_quantity_finished_goods", sa.Numeric(precision=18, scale=3), nullable=True))


def downgrade() -> None:
    op.drop_column("mo_batch", "actual_weight_quantity_finished_goods")
    op.drop_column("mo_batch", "status_operation")
    op.drop_column("mo_batch", "status_manufacturing")
