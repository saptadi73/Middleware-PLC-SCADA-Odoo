"""create system_log table for application debug logs

Revision ID: 20260217_0014
Revises: 20260216_0013
Create Date: 2026-02-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260217_0014"
down_revision = "20260216_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("module", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("batch_no", sa.String(length=64), nullable=True),
        sa.Column("mo_id", sa.String(length=64), nullable=True),
    )

    op.create_index("ix_system_log_timestamp", "system_log", ["timestamp"])
    op.create_index("ix_system_log_level", "system_log", ["level"])
    op.create_index("ix_system_log_module", "system_log", ["module"])
    op.create_index("ix_system_log_mo_id", "system_log", ["mo_id"])
    op.create_index(
        "ix_system_log_level_timestamp",
        "system_log",
        ["level", "timestamp"],
    )
    op.create_index(
        "ix_system_log_module_timestamp",
        "system_log",
        ["module", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_system_log_module_timestamp", table_name="system_log")
    op.drop_index("ix_system_log_level_timestamp", table_name="system_log")
    op.drop_index("ix_system_log_mo_id", table_name="system_log")
    op.drop_index("ix_system_log_module", table_name="system_log")
    op.drop_index("ix_system_log_level", table_name="system_log")
    op.drop_index("ix_system_log_timestamp", table_name="system_log")
    op.drop_table("system_log")
