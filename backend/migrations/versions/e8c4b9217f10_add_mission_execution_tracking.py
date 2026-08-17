"""Add coordinated mission execution tracking.

Revision ID: e8c4b9217f10
Revises: d4a8b7c1e220
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e8c4b9217f10"
down_revision: Union[str, Sequence[str], None] = "d4a8b7c1e220"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "optimization_missions",
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "optimization_missions",
        sa.Column("started_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "optimization_missions",
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    op.add_column(
        "optimization_mission_actions",
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "optimization_mission_actions",
        sa.Column("started_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "optimization_mission_actions",
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    op.add_column(
        "appointment_recommendations",
        sa.Column(
            "optimization_mission_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "optimization_missions.mission_id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_appointment_recommendations_optimization_mission",
        "appointment_recommendations",
        ["optimization_mission_id", "appt_id"],
    )
    op.create_unique_constraint(
        "uq_appointment_recommendation_mission_appt",
        "appointment_recommendations",
        ["optimization_mission_id", "appt_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_appointment_recommendation_mission_appt",
        "appointment_recommendations",
        type_="unique",
    )
    op.drop_index(
        "ix_appointment_recommendations_optimization_mission",
        table_name="appointment_recommendations",
    )
    op.drop_column(
        "appointment_recommendations",
        "optimization_mission_id",
    )
    op.drop_column("optimization_mission_actions", "completed_at")
    op.drop_column("optimization_mission_actions", "started_at")
    op.drop_column("optimization_mission_actions", "accepted_at")
    op.drop_column("optimization_missions", "completed_at")
    op.drop_column("optimization_missions", "started_at")
    op.drop_column("optimization_missions", "accepted_at")
