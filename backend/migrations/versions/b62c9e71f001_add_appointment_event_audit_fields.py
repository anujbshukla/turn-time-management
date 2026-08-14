"""add appointment event audit fields

Revision ID: b62c9e71f001
Revises: a18bf5b00006
Create Date: 2026-08-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b62c9e71f001"
down_revision: Union[str, Sequence[str], None] = "a18bf5b00006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "appointment_events",
        sa.Column("performed_by", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "appointment_events",
        sa.Column("field_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "appointment_events",
        sa.Column("old_value", sa.Text(), nullable=True),
    )
    op.add_column(
        "appointment_events",
        sa.Column("new_value", sa.Text(), nullable=True),
    )
    op.add_column(
        "appointment_events",
        sa.Column(
            "details_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("appointment_events", "details_json")
    op.drop_column("appointment_events", "new_value")
    op.drop_column("appointment_events", "old_value")
    op.drop_column("appointment_events", "field_name")
    op.drop_column("appointment_events", "performed_by")
