"""sync actual consumption columns on mo_batch

Revision ID: 20260213_0008
Revises: 20260212_0007
Create Date: 2026-02-13
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260213_0008"
down_revision = "20260212_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing columns if they were not applied in earlier migrations.
    op.execute("ALTER TABLE mo_batch ADD COLUMN IF NOT EXISTS actual_consumption_silo_a DOUBLE PRECISION")
    op.execute("ALTER TABLE mo_batch ADD COLUMN IF NOT EXISTS actual_consumption_silo_b DOUBLE PRECISION")
    op.execute("ALTER TABLE mo_batch ADD COLUMN IF NOT EXISTS actual_consumption_silo_c DOUBLE PRECISION")
    op.execute("ALTER TABLE mo_batch ADD COLUMN IF NOT EXISTS actual_consumption_silo_d DOUBLE PRECISION")
    op.execute("ALTER TABLE mo_batch ADD COLUMN IF NOT EXISTS actual_consumption_silo_e DOUBLE PRECISION")
    op.execute("ALTER TABLE mo_batch ADD COLUMN IF NOT EXISTS actual_consumption_silo_f DOUBLE PRECISION")
    op.execute("ALTER TABLE mo_batch ADD COLUMN IF NOT EXISTS actual_consumption_silo_g DOUBLE PRECISION")
    op.execute("ALTER TABLE mo_batch ADD COLUMN IF NOT EXISTS actual_consumption_silo_h DOUBLE PRECISION")
    op.execute("ALTER TABLE mo_batch ADD COLUMN IF NOT EXISTS actual_consumption_silo_i DOUBLE PRECISION")
    op.execute("ALTER TABLE mo_batch ADD COLUMN IF NOT EXISTS actual_consumption_silo_j DOUBLE PRECISION")
    op.execute("ALTER TABLE mo_batch ADD COLUMN IF NOT EXISTS actual_consumption_silo_k DOUBLE PRECISION")
    op.execute("ALTER TABLE mo_batch ADD COLUMN IF NOT EXISTS actual_consumption_silo_l DOUBLE PRECISION")
    op.execute("ALTER TABLE mo_batch ADD COLUMN IF NOT EXISTS actual_consumption_silo_m DOUBLE PRECISION")
    op.execute("ALTER TABLE mo_batch ADD COLUMN IF NOT EXISTS last_read_from_plc TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE mo_batch DROP COLUMN IF EXISTS last_read_from_plc")
    op.execute("ALTER TABLE mo_batch DROP COLUMN IF EXISTS actual_consumption_silo_m")
    op.execute("ALTER TABLE mo_batch DROP COLUMN IF EXISTS actual_consumption_silo_l")
    op.execute("ALTER TABLE mo_batch DROP COLUMN IF EXISTS actual_consumption_silo_k")
    op.execute("ALTER TABLE mo_batch DROP COLUMN IF EXISTS actual_consumption_silo_j")
    op.execute("ALTER TABLE mo_batch DROP COLUMN IF EXISTS actual_consumption_silo_i")
    op.execute("ALTER TABLE mo_batch DROP COLUMN IF EXISTS actual_consumption_silo_h")
    op.execute("ALTER TABLE mo_batch DROP COLUMN IF EXISTS actual_consumption_silo_g")
    op.execute("ALTER TABLE mo_batch DROP COLUMN IF EXISTS actual_consumption_silo_f")
    op.execute("ALTER TABLE mo_batch DROP COLUMN IF EXISTS actual_consumption_silo_e")
    op.execute("ALTER TABLE mo_batch DROP COLUMN IF EXISTS actual_consumption_silo_d")
    op.execute("ALTER TABLE mo_batch DROP COLUMN IF EXISTS actual_consumption_silo_c")
    op.execute("ALTER TABLE mo_batch DROP COLUMN IF EXISTS actual_consumption_silo_b")
    op.execute("ALTER TABLE mo_batch DROP COLUMN IF EXISTS actual_consumption_silo_a")
