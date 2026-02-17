"""add odoo_cancelled flag to mo_batch for idempotent cancel tracking

Revision ID: 20260216_0013
Revises: 20260215_0012
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20260216_0013"
down_revision = "20260215_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mo_batch",
        sa.Column(
            "odoo_cancelled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Flag indicating if MO was successfully cancelled in Odoo",
        ),
    )


def downgrade() -> None:
    op.drop_column("mo_batch", "odoo_cancelled")
