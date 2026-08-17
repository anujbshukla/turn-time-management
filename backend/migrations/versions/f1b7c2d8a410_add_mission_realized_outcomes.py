"""Add realized mission outcomes.

Revision ID: f1b7c2d8a410
Revises: e8c4b9217f10
"""
from alembic import op
import sqlalchemy as sa

revision = "f1b7c2d8a410"
down_revision = "e8c4b9217f10"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("optimization_missions", sa.Column("realized_sla_misses", sa.Integer(), nullable=True))
    op.add_column("optimization_missions", sa.Column("realized_minutes_saved", sa.Numeric(10, 2), nullable=True))
    op.add_column("optimization_missions", sa.Column("realized_net_savings", sa.Numeric(12, 2), nullable=True))
    op.add_column("optimization_missions", sa.Column("outcome_sample_size", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("optimization_missions", sa.Column("outcome_captured_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("optimization_mission_appointments", sa.Column("actual_turn_minutes", sa.Numeric(10, 2), nullable=True))
    op.add_column("optimization_mission_appointments", sa.Column("actual_sla_missed", sa.Boolean(), nullable=True))
    op.add_column("optimization_mission_appointments", sa.Column("realized_minutes_saved", sa.Numeric(10, 2), nullable=True))
    op.add_column("optimization_mission_appointments", sa.Column("realized_net_savings", sa.Numeric(12, 2), nullable=True))

def downgrade() -> None:
    for col in ["realized_net_savings", "realized_minutes_saved", "actual_sla_missed", "actual_turn_minutes"]:
        op.drop_column("optimization_mission_appointments", col)
    for col in ["outcome_captured_at", "outcome_sample_size", "realized_net_savings", "realized_minutes_saved", "realized_sla_misses"]:
        op.drop_column("optimization_missions", col)
