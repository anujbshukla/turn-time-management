"""Add learned optimizer action-effectiveness profiles.

Revision ID: g3d9e4a1c520
Revises: f1b7c2d8a410
"""

from alembic import op
import sqlalchemy as sa


revision = "g3d9e4a1c520"
down_revision = "f1b7c2d8a410"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "optimization_action_effectiveness",
        sa.Column(
            "profile_id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("facility_id", sa.String(100), nullable=False),
        sa.Column("action_signature", sa.String(200), nullable=False),
        sa.Column("appointment_type", sa.String(30), nullable=False),
        sa.Column("load_type", sa.String(50), nullable=False),
        sa.Column("temperature_zone", sa.String(30), nullable=False),
        sa.Column("pallet_band", sa.String(20), nullable=False),
        sa.Column("congestion_band", sa.String(20), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column(
            "sla_success_rate",
            sa.Numeric(8, 6),
            nullable=False,
        ),
        sa.Column(
            "avg_realized_minutes_saved",
            sa.Numeric(10, 3),
            nullable=False,
        ),
        sa.Column(
            "avg_realized_net_savings",
            sa.Numeric(12, 2),
            nullable=False,
        ),
        sa.Column(
            "confidence_weight",
            sa.Numeric(8, 6),
            nullable=False,
        ),
        sa.Column(
            "last_outcome_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "facility_id",
            "action_signature",
            "appointment_type",
            "load_type",
            "temperature_zone",
            "pallet_band",
            "congestion_band",
            name="uq_optimization_action_effectiveness_context",
        ),
    )
    op.create_index(
        "ix_optimization_action_effectiveness_lookup",
        "optimization_action_effectiveness",
        [
            "facility_id",
            "action_signature",
            "appointment_type",
            "load_type",
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_optimization_action_effectiveness_lookup",
        table_name="optimization_action_effectiveness",
    )
    op.drop_table("optimization_action_effectiveness")
