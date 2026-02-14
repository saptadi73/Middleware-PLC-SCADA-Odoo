"""add status column to mo_histories

Revision ID: 20260214_0010
Revises: 20260213_0009
Create Date: 2026-02-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260214_0010"
down_revision = "20260213_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add status column to mo_histories table.
    
    Status values:
    - 'completed': Batch successfully processed and sent to Odoo
    - 'failed': Batch processing failed (can be retried)
    - 'cancelled': Batch cancelled by operator (should not be retried)
    """
    op.add_column(
        "mo_histories",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="completed",
        ),
    )
    
    # Add index for faster queries by status
    op.create_index(
        "ix_mo_histories_status",
        "mo_histories",
        ["status"],
    )
    
    # Add notes column for additional information
    op.add_column(
        "mo_histories",
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove status and notes columns"""
    op.drop_index("ix_mo_histories_status", table_name="mo_histories")
    op.drop_column("mo_histories", "notes")
    op.drop_column("mo_histories", "status")
