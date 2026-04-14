"""create manual_weighing_sync table

Revision ID: 20260414_0017
Revises: 20260221_0016
Create Date: 2026-04-14
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260414_0017"
down_revision = "20260221_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manual_weighing_sync",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("reference_key", sa.String(length=32), nullable=False),
        sa.Column("handshake_address", sa.Integer(), nullable=False),
        sa.Column("batch_no", sa.Integer(), nullable=True),
        sa.Column("mo_id", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("consumption", sa.Float(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending_handshake'"),
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "odoo_synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("handshake_marked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_index(
        "ix_manual_weighing_sync_reference_key",
        "manual_weighing_sync",
        ["reference_key"],
    )
    op.create_index(
        "ix_manual_weighing_sync_handshake_address",
        "manual_weighing_sync",
        ["handshake_address"],
    )
    op.create_index(
        "ix_manual_weighing_sync_mo_id",
        "manual_weighing_sync",
        ["mo_id"],
    )
    op.create_index(
        "ix_manual_weighing_sync_payload_hash",
        "manual_weighing_sync",
        ["payload_hash"],
    )
    op.create_index(
        "ix_manual_weighing_sync_pending_lookup",
        "manual_weighing_sync",
        ["payload_hash", "reference_key", "handshake_address", "handshake_marked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_manual_weighing_sync_pending_lookup", table_name="manual_weighing_sync")
    op.drop_index("ix_manual_weighing_sync_payload_hash", table_name="manual_weighing_sync")
    op.drop_index("ix_manual_weighing_sync_mo_id", table_name="manual_weighing_sync")
    op.drop_index("ix_manual_weighing_sync_handshake_address", table_name="manual_weighing_sync")
    op.drop_index("ix_manual_weighing_sync_reference_key", table_name="manual_weighing_sync")
    op.drop_table("manual_weighing_sync")
