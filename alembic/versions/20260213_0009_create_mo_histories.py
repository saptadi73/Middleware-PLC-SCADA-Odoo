"""create mo_histories

Revision ID: 20260213_0009
Revises: 20260213_0008
Create Date: 2026-02-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260213_0009"
down_revision = "20260213_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "mo_histories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("batch_no", sa.Integer(), nullable=False),
        sa.Column("mo_id", sa.String(length=64), nullable=False),
        sa.Column("consumption", sa.Numeric(precision=18, scale=3), nullable=False),
        sa.Column("equipment_id_batch", sa.String(length=64), nullable=False),
        sa.Column("finished_goods", sa.String(length=128), nullable=True),
        sa.Column("silo_a", sa.Integer(), nullable=False, server_default="101"),
        sa.Column("component_silo_a_name", sa.String(length=64), nullable=True),
        sa.Column("consumption_silo_a", sa.Float(), nullable=True),
        sa.Column("silo_b", sa.Integer(), nullable=False, server_default="102"),
        sa.Column("component_silo_b_name", sa.String(length=64), nullable=True),
        sa.Column("consumption_silo_b", sa.Float(), nullable=True),
        sa.Column("silo_c", sa.Integer(), nullable=False, server_default="103"),
        sa.Column("component_silo_c_name", sa.String(length=64), nullable=True),
        sa.Column("consumption_silo_c", sa.Float(), nullable=True),
        sa.Column("silo_d", sa.Integer(), nullable=False, server_default="104"),
        sa.Column("component_silo_d_name", sa.String(length=64), nullable=True),
        sa.Column("consumption_silo_d", sa.Float(), nullable=True),
        sa.Column("silo_e", sa.Integer(), nullable=False, server_default="105"),
        sa.Column("component_silo_e_name", sa.String(length=64), nullable=True),
        sa.Column("consumption_silo_e", sa.Float(), nullable=True),
        sa.Column("silo_f", sa.Integer(), nullable=False, server_default="106"),
        sa.Column("component_silo_f_name", sa.String(length=64), nullable=True),
        sa.Column("consumption_silo_f", sa.Float(), nullable=True),
        sa.Column("silo_g", sa.Integer(), nullable=False, server_default="107"),
        sa.Column("component_silo_g_name", sa.String(length=64), nullable=True),
        sa.Column("consumption_silo_g", sa.Float(), nullable=True),
        sa.Column("silo_h", sa.Integer(), nullable=False, server_default="108"),
        sa.Column("component_silo_h_name", sa.String(length=64), nullable=True),
        sa.Column("consumption_silo_h", sa.Float(), nullable=True),
        sa.Column("silo_i", sa.Integer(), nullable=False, server_default="109"),
        sa.Column("component_silo_i_name", sa.String(length=64), nullable=True),
        sa.Column("consumption_silo_i", sa.Float(), nullable=True),
        sa.Column("silo_j", sa.Integer(), nullable=False, server_default="110"),
        sa.Column("component_silo_j_name", sa.String(length=64), nullable=True),
        sa.Column("consumption_silo_j", sa.Float(), nullable=True),
        sa.Column("silo_k", sa.Integer(), nullable=False, server_default="111"),
        sa.Column("component_silo_k_name", sa.String(length=64), nullable=True),
        sa.Column("consumption_silo_k", sa.Float(), nullable=True),
        sa.Column("silo_l", sa.Integer(), nullable=False, server_default="112"),
        sa.Column("component_silo_l_name", sa.String(length=64), nullable=True),
        sa.Column("consumption_silo_l", sa.Float(), nullable=True),
        sa.Column("silo_m", sa.Integer(), nullable=False, server_default="113"),
        sa.Column("component_silo_m_name", sa.String(length=64), nullable=True),
        sa.Column("consumption_silo_m", sa.Float(), nullable=True),
        sa.Column("status_manufacturing", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status_operation", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "actual_weight_quantity_finished_goods",
            sa.Numeric(precision=18, scale=3),
            nullable=True,
        ),
        sa.Column("actual_consumption_silo_a", sa.Float(), nullable=True),
        sa.Column("actual_consumption_silo_b", sa.Float(), nullable=True),
        sa.Column("actual_consumption_silo_c", sa.Float(), nullable=True),
        sa.Column("actual_consumption_silo_d", sa.Float(), nullable=True),
        sa.Column("actual_consumption_silo_e", sa.Float(), nullable=True),
        sa.Column("actual_consumption_silo_f", sa.Float(), nullable=True),
        sa.Column("actual_consumption_silo_g", sa.Float(), nullable=True),
        sa.Column("actual_consumption_silo_h", sa.Float(), nullable=True),
        sa.Column("actual_consumption_silo_i", sa.Float(), nullable=True),
        sa.Column("actual_consumption_silo_j", sa.Float(), nullable=True),
        sa.Column("actual_consumption_silo_k", sa.Float(), nullable=True),
        sa.Column("actual_consumption_silo_l", sa.Float(), nullable=True),
        sa.Column("actual_consumption_silo_m", sa.Float(), nullable=True),
        sa.Column("last_read_from_plc", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_mo_histories_batch_no", "mo_histories", ["batch_no"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mo_histories_batch_no", table_name="mo_histories")
    op.drop_table("mo_histories")
