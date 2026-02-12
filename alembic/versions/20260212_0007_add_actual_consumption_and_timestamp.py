"""add actual consumption fields and last_read_from_plc timestamp

Revision ID: 20260212_0007
Revises: 20260212_0006
Create Date: 2026-02-12
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260212_0007"
down_revision = "20260212_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add actual consumption fields for silos a-m
    op.add_column(
        "mo_batch",
        sa.Column("actual_consumption_silo_a", sa.Float(), nullable=True),
    )
    op.add_column(
        "mo_batch",
        sa.Column("actual_consumption_silo_b", sa.Float(), nullable=True),
    )
    op.add_column(
        "mo_batch",
        sa.Column("actual_consumption_silo_c", sa.Float(), nullable=True),
    )
    op.add_column(
        "mo_batch",
        sa.Column("actual_consumption_silo_d", sa.Float(), nullable=True),
    )
    op.add_column(
        "mo_batch",
        sa.Column("actual_consumption_silo_e", sa.Float(), nullable=True),
    )
    op.add_column(
        "mo_batch",
        sa.Column("actual_consumption_silo_f", sa.Float(), nullable=True),
    )
    op.add_column(
        "mo_batch",
        sa.Column("actual_consumption_silo_g", sa.Float(), nullable=True),
    )
    op.add_column(
        "mo_batch",
        sa.Column("actual_consumption_silo_h", sa.Float(), nullable=True),
    )
    op.add_column(
        "mo_batch",
        sa.Column("actual_consumption_silo_i", sa.Float(), nullable=True),
    )
    op.add_column(
        "mo_batch",
        sa.Column("actual_consumption_silo_j", sa.Float(), nullable=True),
    )
    op.add_column(
        "mo_batch",
        sa.Column("actual_consumption_silo_k", sa.Float(), nullable=True),
    )
    op.add_column(
        "mo_batch",
        sa.Column("actual_consumption_silo_l", sa.Float(), nullable=True),
    )
    op.add_column(
        "mo_batch",
        sa.Column("actual_consumption_silo_m", sa.Float(), nullable=True),
    )

    # Add timestamp for last PLC read
    op.add_column(
        "mo_batch",
        sa.Column("last_read_from_plc", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # Drop timestamp
    op.drop_column("mo_batch", "last_read_from_plc")

    # Drop actual consumption fields
    op.drop_column("mo_batch", "actual_consumption_silo_m")
    op.drop_column("mo_batch", "actual_consumption_silo_l")
    op.drop_column("mo_batch", "actual_consumption_silo_k")
    op.drop_column("mo_batch", "actual_consumption_silo_j")
    op.drop_column("mo_batch", "actual_consumption_silo_i")
    op.drop_column("mo_batch", "actual_consumption_silo_h")
    op.drop_column("mo_batch", "actual_consumption_silo_g")
    op.drop_column("mo_batch", "actual_consumption_silo_f")
    op.drop_column("mo_batch", "actual_consumption_silo_e")
    op.drop_column("mo_batch", "actual_consumption_silo_d")
    op.drop_column("mo_batch", "actual_consumption_silo_c")
    op.drop_column("mo_batch", "actual_consumption_silo_b")
    op.drop_column("mo_batch", "actual_consumption_silo_a")
