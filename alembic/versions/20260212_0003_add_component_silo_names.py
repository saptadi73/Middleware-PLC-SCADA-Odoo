"""add component_silo_*_name columns

Revision ID: 20260212_0003
Revises: 20260212_0002
Create Date: 2026-02-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260212_0003"
down_revision = "20260212_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mo_batch", sa.Column("component_silo_a_name", sa.String(length=64), nullable=True))
    op.add_column("mo_batch", sa.Column("component_silo_b_name", sa.String(length=64), nullable=True))
    op.add_column("mo_batch", sa.Column("component_silo_c_name", sa.String(length=64), nullable=True))
    op.add_column("mo_batch", sa.Column("component_silo_d_name", sa.String(length=64), nullable=True))
    op.add_column("mo_batch", sa.Column("component_silo_e_name", sa.String(length=64), nullable=True))
    op.add_column("mo_batch", sa.Column("component_silo_f_name", sa.String(length=64), nullable=True))
    op.add_column("mo_batch", sa.Column("component_silo_g_name", sa.String(length=64), nullable=True))
    op.add_column("mo_batch", sa.Column("component_silo_h_name", sa.String(length=64), nullable=True))
    op.add_column("mo_batch", sa.Column("component_silo_i_name", sa.String(length=64), nullable=True))
    op.add_column("mo_batch", sa.Column("component_silo_j_name", sa.String(length=64), nullable=True))
    op.add_column("mo_batch", sa.Column("component_silo_k_name", sa.String(length=64), nullable=True))
    op.add_column("mo_batch", sa.Column("component_silo_l_name", sa.String(length=64), nullable=True))
    op.add_column("mo_batch", sa.Column("component_silo_m_name", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("mo_batch", "component_silo_m_name")
    op.drop_column("mo_batch", "component_silo_l_name")
    op.drop_column("mo_batch", "component_silo_k_name")
    op.drop_column("mo_batch", "component_silo_j_name")
    op.drop_column("mo_batch", "component_silo_i_name")
    op.drop_column("mo_batch", "component_silo_h_name")
    op.drop_column("mo_batch", "component_silo_g_name")
    op.drop_column("mo_batch", "component_silo_f_name")
    op.drop_column("mo_batch", "component_silo_e_name")
    op.drop_column("mo_batch", "component_silo_d_name")
    op.drop_column("mo_batch", "component_silo_c_name")
    op.drop_column("mo_batch", "component_silo_b_name")
    op.drop_column("mo_batch", "component_silo_a_name")
