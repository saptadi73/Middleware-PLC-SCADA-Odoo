"""create mo_batch

Revision ID: 20260212_0001
Revises:
Create Date: 2026-02-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260212_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mo_batch",
        sa.Column("batch_no", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("mo_id", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=3), nullable=False),
        sa.Column("equipment_id_batch", sa.String(length=64), nullable=False),
        sa.Column("silo_a", sa.Integer(), nullable=False, server_default="101"),
        sa.Column("quantity_silo_a", sa.Float(), nullable=True),
        sa.Column("silo_b", sa.Integer(), nullable=False, server_default="102"),
        sa.Column("quantity_silo_b", sa.Float(), nullable=True),
        sa.Column("silo_c", sa.Integer(), nullable=False, server_default="103"),
        sa.Column("quantity_silo_c", sa.Float(), nullable=True),
        sa.Column("silo_d", sa.Integer(), nullable=False, server_default="104"),
        sa.Column("quantity_silo_d", sa.Float(), nullable=True),
        sa.Column("silo_e", sa.Integer(), nullable=False, server_default="105"),
        sa.Column("quantity_silo_e", sa.Float(), nullable=True),
        sa.Column("silo_f", sa.Integer(), nullable=False, server_default="106"),
        sa.Column("quantity_silo_f", sa.Float(), nullable=True),
        sa.Column("silo_g", sa.Integer(), nullable=False, server_default="107"),
        sa.Column("quantity_silo_g", sa.Float(), nullable=True),
        sa.Column("silo_h", sa.Integer(), nullable=False, server_default="108"),
        sa.Column("quantity_silo_h", sa.Float(), nullable=True),
        sa.Column("silo_i", sa.Integer(), nullable=False, server_default="109"),
        sa.Column("quantity_silo_i", sa.Float(), nullable=True),
        sa.Column("silo_j", sa.Integer(), nullable=False, server_default="110"),
        sa.Column("quantity_silo_j", sa.Float(), nullable=True),
        sa.Column("silo_k", sa.Integer(), nullable=False, server_default="111"),
        sa.Column("quantity_silo_k", sa.Float(), nullable=True),
        sa.Column("silo_l", sa.Integer(), nullable=False, server_default="112"),
        sa.Column("quantity_silo_l", sa.Float(), nullable=True),
        sa.Column("silo_m", sa.Integer(), nullable=False, server_default="113"),
        sa.Column("quantity_silo_m", sa.Float(), nullable=True),
    )
    op.create_index(
        "ix_mo_batch_batch_no",
        "mo_batch",
        ["batch_no"],
        unique=False,
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_mo_batch_batch_no")
    op.execute("DROP INDEX IF EXISTS ix_tablesmo_batch_batch_no")
    op.execute("DROP TABLE IF EXISTS mo_batch")
    op.execute("DROP TABLE IF EXISTS tablesmo_batch")
