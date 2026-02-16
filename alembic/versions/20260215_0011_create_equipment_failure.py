"""create equipment_failure table

Revision ID: 20260215_0011
Revises: 20260214_0010
Create Date: 2026-02-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260215_0011"
down_revision = "20260214_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "equipment_failure",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("equipment_code", sa.String(length=64), nullable=False),
        sa.Column("equipment_name", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("failure_type", sa.String(length=64), nullable=True),
        sa.Column("failure_date", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "is_resolved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="plc",
        ),
        sa.Column(
            "severity",
            sa.String(length=32),
            nullable=False,
            server_default="medium",
        ),
    )

    op.create_index(
        "ix_equipment_failure_equipment_code",
        "equipment_failure",
        ["equipment_code"],
    )
    op.create_index(
        "ix_equipment_failure_failure_date",
        "equipment_failure",
        ["failure_date"],
    )
    op.create_index(
        "ix_equipment_failure_created_at",
        "equipment_failure",
        ["created_at"],
    )
    op.create_index(
        "ix_equipment_failure_equipment_date",
        "equipment_failure",
        ["equipment_code", "failure_date"],
    )
    op.create_unique_constraint(
        "uq_equipment_failure_unique_report",
        "equipment_failure",
        ["equipment_code", "failure_date", "description"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_equipment_failure_unique_report",
        "equipment_failure",
        type_="unique",
    )
    op.drop_index("ix_equipment_failure_equipment_date", table_name="equipment_failure")
    op.drop_index("ix_equipment_failure_created_at", table_name="equipment_failure")
    op.drop_index("ix_equipment_failure_failure_date", table_name="equipment_failure")
    op.drop_index("ix_equipment_failure_equipment_code", table_name="equipment_failure")
    op.drop_table("equipment_failure")
