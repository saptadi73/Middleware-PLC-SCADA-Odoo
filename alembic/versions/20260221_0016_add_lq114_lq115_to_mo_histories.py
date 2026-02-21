"""add lq114 and lq115 equipment support to mo_histories table

Revision ID: 20260221_0016
Revises: 20260221_0015
Create Date: 2026-02-21

This migration adds support for two liquid tanks (LQ114 and LQ115)
to the mo_histories table with scada_tag-based naming convention:
- LQ114 (TETES): scada_tag "lq_tetes"
- LQ115 (FML): scada_tag "lq_fml"

Columns added (same as mo_batch for consistency):
- Equipment IDs (lq114, lq115) with server defaults
- Component names (component_lq_tetes_name, component_lq_fml_name)
- Consumption (consumption_lq_tetes, consumption_lq_fml)
- Actual consumption (actual_consumption_lq_tetes, actual_consumption_lq_fml)
"""

from alembic import op
import sqlalchemy as sa


revision = "20260221_0016"
down_revision = "20260221_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add LQ114 equipment support (TETES - scada_tag: lq_tetes)
    op.add_column(
        "mo_histories",
        sa.Column("lq114", sa.Integer(), nullable=False, server_default="114"),
    )
    op.add_column(
        "mo_histories",
        sa.Column("component_lq_tetes_name", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "mo_histories",
        sa.Column("consumption_lq_tetes", sa.Float(), nullable=True),
    )
    op.add_column(
        "mo_histories",
        sa.Column("actual_consumption_lq_tetes", sa.Float(), nullable=True),
    )

    # Add LQ115 equipment support (FML - scada_tag: lq_fml)
    op.add_column(
        "mo_histories",
        sa.Column("lq115", sa.Integer(), nullable=False, server_default="115"),
    )
    op.add_column(
        "mo_histories",
        sa.Column("component_lq_fml_name", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "mo_histories",
        sa.Column("consumption_lq_fml", sa.Float(), nullable=True),
    )
    op.add_column(
        "mo_histories",
        sa.Column("actual_consumption_lq_fml", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    # Remove LQ115 equipment support
    op.drop_column("mo_histories", "actual_consumption_lq_fml")
    op.drop_column("mo_histories", "consumption_lq_fml")
    op.drop_column("mo_histories", "component_lq_fml_name")
    op.drop_column("mo_histories", "lq115")

    # Remove LQ114 equipment support
    op.drop_column("mo_histories", "actual_consumption_lq_tetes")
    op.drop_column("mo_histories", "consumption_lq_tetes")
    op.drop_column("mo_histories", "component_lq_tetes_name")
    op.drop_column("mo_histories", "lq114")
