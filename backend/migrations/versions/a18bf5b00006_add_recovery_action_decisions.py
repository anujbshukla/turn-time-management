"""Add recovery action decisions

Revision ID: a18bf5b00006
Revises: 0034cefa931b
Create Date: 2026-07-24 10:40:00.521446

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a18bf5b00006'
down_revision: Union[str, Sequence[str], None] = '0034cefa931b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recommendation_actions",
        sa.Column(
            "decision_status",
            sa.String(length=30),
            nullable=False,
            server_default="Pending",
        ),
    )

    op.add_column(
        "recommendation_actions",
        sa.Column(
            "decision_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.add_column(
        "recommendation_actions",
        sa.Column(
            "decision_by",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.add_column(
        "recommendation_actions",
        sa.Column(
            "decision_notes",
            sa.Text(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_recommendation_actions_decision_status",
        "recommendation_actions",
        ["decision_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recommendation_actions_decision_status",
        table_name="recommendation_actions",
    )

    op.drop_column(
        "recommendation_actions",
        "decision_notes",
    )

    op.drop_column(
        "recommendation_actions",
        "decision_by",
    )

    op.drop_column(
        "recommendation_actions",
        "decision_at",
    )

    op.drop_column(
        "recommendation_actions",
        "decision_status",
    )