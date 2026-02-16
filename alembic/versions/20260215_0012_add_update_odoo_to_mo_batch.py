"""add update_odoo flag to mo_batch

Revision ID: 20260215_0012
Revises: 20260215_0011
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa


revision = "20260215_0012"
down_revision = "20260215_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mo_batch",
        sa.Column(
            "update_odoo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("mo_batch", "update_odoo")
