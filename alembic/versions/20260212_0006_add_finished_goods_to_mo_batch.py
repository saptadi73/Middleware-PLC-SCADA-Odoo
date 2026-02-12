"""add finished_goods to mo_batch

Revision ID: 20260212_0006
Revises: 20260212_0005
Create Date: 2026-02-12
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260212_0006"
down_revision = "20260212_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mo_batch",
        sa.Column("finished_goods", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mo_batch", "finished_goods")
