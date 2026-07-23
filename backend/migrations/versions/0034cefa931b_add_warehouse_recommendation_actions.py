"""Add warehouse recommendation actions

Revision ID: 0034cefa931b
Revises: 9ce21778efe9
Create Date: 2026-07-23 11:43:57.678364

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0034cefa931b'
down_revision: Union[str, Sequence[str], None] = '9ce21778efe9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendation_actions",
        sa.Column(
            "recommendation_action_id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "recommendation_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "appointment_recommendations.recommendation_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "sequence_number",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "action_code",
            sa.String(length=75),
            nullable=False,
        ),
        sa.Column(
            "action_title",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "action_description",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "owner_role",
            sa.String(length=75),
            nullable=True,
        ),
        sa.Column(
            "start_by",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "estimated_minutes_saved",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "additional_loaders",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "additional_forklifts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "required_equipment_type",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "required_dock_id",
            sa.String(length=50),
            sa.ForeignKey("docks.dock_id"),
            nullable=True,
        ),
        sa.Column(
            "estimated_action_cost",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="Proposed",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "recommendation_id",
            "sequence_number",
            name="uq_recommendation_action_sequence",
        ),
    )

    op.create_index(
        "ix_recommendation_actions_recommendation_id",
        "recommendation_actions",
        ["recommendation_id"],
    )

    op.create_index(
        "ix_recommendation_actions_action_code",
        "recommendation_actions",
        ["action_code"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recommendation_actions_action_code",
        table_name="recommendation_actions",
    )

    op.drop_index(
        "ix_recommendation_actions_recommendation_id",
        table_name="recommendation_actions",
    )

    op.drop_table("recommendation_actions")
