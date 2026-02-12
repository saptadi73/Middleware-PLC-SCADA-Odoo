"""rename quantity columns to consumption

Revision ID: 20260212_0004
Revises: 20260212_0003
Create Date: 2026-02-12 00:00:00.000000
"""

from alembic import op


revision = "20260212_0004"
down_revision = "20260212_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("mo_batch", "quantity", new_column_name="consumption")
    op.alter_column("mo_batch", "quantity_silo_a", new_column_name="consumption_silo_a")
    op.alter_column("mo_batch", "quantity_silo_b", new_column_name="consumption_silo_b")
    op.alter_column("mo_batch", "quantity_silo_c", new_column_name="consumption_silo_c")
    op.alter_column("mo_batch", "quantity_silo_d", new_column_name="consumption_silo_d")
    op.alter_column("mo_batch", "quantity_silo_e", new_column_name="consumption_silo_e")
    op.alter_column("mo_batch", "quantity_silo_f", new_column_name="consumption_silo_f")
    op.alter_column("mo_batch", "quantity_silo_g", new_column_name="consumption_silo_g")
    op.alter_column("mo_batch", "quantity_silo_h", new_column_name="consumption_silo_h")
    op.alter_column("mo_batch", "quantity_silo_i", new_column_name="consumption_silo_i")
    op.alter_column("mo_batch", "quantity_silo_j", new_column_name="consumption_silo_j")
    op.alter_column("mo_batch", "quantity_silo_k", new_column_name="consumption_silo_k")
    op.alter_column("mo_batch", "quantity_silo_l", new_column_name="consumption_silo_l")
    op.alter_column("mo_batch", "quantity_silo_m", new_column_name="consumption_silo_m")


def downgrade() -> None:
    op.alter_column("mo_batch", "consumption", new_column_name="quantity")
    op.alter_column("mo_batch", "consumption_silo_a", new_column_name="quantity_silo_a")
    op.alter_column("mo_batch", "consumption_silo_b", new_column_name="quantity_silo_b")
    op.alter_column("mo_batch", "consumption_silo_c", new_column_name="quantity_silo_c")
    op.alter_column("mo_batch", "consumption_silo_d", new_column_name="quantity_silo_d")
    op.alter_column("mo_batch", "consumption_silo_e", new_column_name="quantity_silo_e")
    op.alter_column("mo_batch", "consumption_silo_f", new_column_name="quantity_silo_f")
    op.alter_column("mo_batch", "consumption_silo_g", new_column_name="quantity_silo_g")
    op.alter_column("mo_batch", "consumption_silo_h", new_column_name="quantity_silo_h")
    op.alter_column("mo_batch", "consumption_silo_i", new_column_name="quantity_silo_i")
    op.alter_column("mo_batch", "consumption_silo_j", new_column_name="quantity_silo_j")
    op.alter_column("mo_batch", "consumption_silo_k", new_column_name="quantity_silo_k")
    op.alter_column("mo_batch", "consumption_silo_l", new_column_name="quantity_silo_l")
    op.alter_column("mo_batch", "consumption_silo_m", new_column_name="quantity_silo_m")
