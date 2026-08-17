"""Add persisted actions for coordinated optimization missions.

Revision ID: d4a8b7c1e220
Revises: c7f2a6d9b210
Create Date: 2026-08-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4a8b7c1e220"
down_revision: Union[str, Sequence[str], None] = "c7f2a6d9b210"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "optimization_mission_actions",
        sa.Column("mission_action_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "mission_id",
            sa.BigInteger(),
            sa.ForeignKey("optimization_missions.mission_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "appt_id",
            sa.String(50),
            sa.ForeignKey("appointments.appt_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("action_code", sa.String(50), nullable=False),
        sa.Column("action_description", sa.Text(), nullable=False),
        sa.Column("additional_loaders", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("additional_forklifts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("staging_labor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required_dock_id", sa.String(100), nullable=True),
        sa.Column("expected_minutes_saved", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("estimated_action_cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="Proposed"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "mission_id",
            "appt_id",
            "sequence_number",
            name="uq_optimization_mission_action_sequence",
        ),
    )
    op.create_index(
        "ix_optimization_mission_actions_mission",
        "optimization_mission_actions",
        ["mission_id", "appt_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_optimization_mission_actions_mission",
        table_name="optimization_mission_actions",
    )
    op.drop_table("optimization_mission_actions")
