"""Add ML monitoring, model registry and retraining governance.

Revision ID: h5f2c8a7d630
Revises: g3d9e4a1c520
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "h5f2c8a7d630"
down_revision = "g3d9e4a1c520"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ml_model_registry",
        sa.Column("registry_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("model_version", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="Production"),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("training_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("training_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("training_rows", sa.Integer(), nullable=True),
        sa.Column("algorithm", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("training_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("promotion_checks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "ml_monitoring_snapshots",
        sa.Column("snapshot_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("health_status", sa.String(40), nullable=False),
        sa.Column("retrain_recommended", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("turn_duration_mae", sa.Numeric(10, 4), nullable=True),
        sa.Column("turn_duration_rmse", sa.Numeric(10, 4), nullable=True),
        sa.Column("arrival_mae", sa.Numeric(10, 4), nullable=True),
        sa.Column("sla_precision", sa.Numeric(10, 6), nullable=True),
        sa.Column("sla_recall", sa.Numeric(10, 6), nullable=True),
        sa.Column("sla_f2", sa.Numeric(10, 6), nullable=True),
        sa.Column("false_positives", sa.Integer(), nullable=True),
        sa.Column("false_negatives", sa.Integer(), nullable=True),
        sa.Column("feature_drift_score", sa.Numeric(10, 6), nullable=True),
        sa.Column("optimizer_savings_error_percent", sa.Numeric(10, 4), nullable=True),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_ml_monitoring_snapshots_version_created",
        "ml_monitoring_snapshots",
        ["model_version", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ml_monitoring_snapshots_version_created",
        table_name="ml_monitoring_snapshots",
    )
    op.drop_table("ml_monitoring_snapshots")
    op.drop_table("ml_model_registry")
