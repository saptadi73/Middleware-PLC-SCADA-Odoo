"""add uuid pk to mo_batch

Revision ID: 20260212_0002
Revises: 20260212_0001
Create Date: 2026-02-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260212_0002"
down_revision = "20260212_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.add_column(
        "mo_batch",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )

    op.execute("ALTER TABLE mo_batch DROP CONSTRAINT IF EXISTS mo_batch_pkey")
    op.create_primary_key("mo_batch_pkey", "mo_batch", ["id"])


def downgrade() -> None:
    op.execute("ALTER TABLE mo_batch DROP CONSTRAINT IF EXISTS mo_batch_pkey")
    op.create_primary_key("mo_batch_pkey", "mo_batch", ["batch_no"])
    op.drop_column("mo_batch", "id")
