"""Add ML v2 realistic-data and optimization foundation.

Revision ID: c7f2a6d9b210
Revises: b62c9e71f001
Create Date: 2026-08-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c7f2a6d9b210"
down_revision: Union[str, Sequence[str], None] = "b62c9e71f001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "facility_operational_profiles",
        sa.Column("facility_id", sa.String(100), sa.ForeignKey("facilities.facility_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("weekday_base_volume", sa.Integer(), nullable=False),
        sa.Column("weekend_volume_factor", sa.Numeric(6, 3), nullable=False, server_default="0.55"),
        sa.Column("dock_efficiency_factor", sa.Numeric(6, 3), nullable=False, server_default="1.00"),
        sa.Column("labor_efficiency_factor", sa.Numeric(6, 3), nullable=False, server_default="1.00"),
        sa.Column("congestion_sensitivity", sa.Numeric(6, 3), nullable=False, server_default="1.00"),
        sa.Column("base_loader_capacity", sa.Integer(), nullable=False),
        sa.Column("base_forklift_capacity", sa.Integer(), nullable=False),
        sa.Column("peak_start_hour", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("peak_end_hour", sa.Integer(), nullable=False, server_default="16"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "carrier_operational_profiles",
        sa.Column("carrier_id", sa.String(100), sa.ForeignKey("carriers.carrier_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("baseline_on_time_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("mean_delay_minutes", sa.Numeric(8, 2), nullable=False),
        sa.Column("delay_stddev_minutes", sa.Numeric(8, 2), nullable=False),
        sa.Column("long_haul_penalty_minutes", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "customer_operational_profiles",
        sa.Column("customer_id", sa.String(100), sa.ForeignKey("customers.customer_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("handling_complexity_factor", sa.Numeric(6, 3), nullable=False),
        sa.Column("typical_pallets", sa.Integer(), nullable=False),
        sa.Column("typical_skus", sa.Integer(), nullable=False),
        sa.Column("inbound_share", sa.Numeric(6, 4), nullable=False),
        sa.Column("priority_bias", sa.Numeric(6, 3), nullable=False, server_default="1.00"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "product_operational_profiles",
        sa.Column("product_id", sa.String(50), sa.ForeignKey("products.product_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("base_minutes_per_pallet", sa.Numeric(8, 3), nullable=False),
        sa.Column("handling_complexity_factor", sa.Numeric(6, 3), nullable=False),
        sa.Column("forklift_intensity", sa.Numeric(6, 3), nullable=False),
        sa.Column("staging_intensity", sa.Numeric(6, 3), nullable=False),
        sa.Column("damage_risk_factor", sa.Numeric(6, 3), nullable=False, server_default="1.00"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "appointment_resource_allocations",
        sa.Column("allocation_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("appt_id", sa.String(50), sa.ForeignKey("appointments.appt_id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("planned_loaders", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("actual_loaders", sa.Integer(), nullable=True),
        sa.Column("planned_forklifts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("actual_forklifts", sa.Integer(), nullable=True),
        sa.Column("planned_staging_labor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_staging_labor", sa.Integer(), nullable=True),
        sa.Column("queue_depth_at_arrival", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dock_congestion_percent", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("labor_utilization_percent", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("forklift_utilization_percent", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("resource_plan_source", sa.String(30), nullable=False, server_default="Baseline"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_resource_allocations_appt", "appointment_resource_allocations", ["appt_id"])

    op.create_table(
        "product_handling_history",
        sa.Column("handling_history_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.String(50), sa.ForeignKey("products.product_id", ondelete="CASCADE"), nullable=False),
        sa.Column("facility_id", sa.String(100), sa.ForeignKey("facilities.facility_id", ondelete="CASCADE"), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("avg_minutes_per_pallet", sa.Numeric(8, 3), nullable=False),
        sa.Column("p50_minutes_per_pallet", sa.Numeric(8, 3), nullable=False),
        sa.Column("p90_minutes_per_pallet", sa.Numeric(8, 3), nullable=False),
        sa.Column("avg_loaders", sa.Numeric(6, 2), nullable=False),
        sa.Column("avg_forklifts", sa.Numeric(6, 2), nullable=False),
        sa.Column("sla_success_rate", sa.Numeric(6, 4), nullable=False),
        sa.UniqueConstraint("product_id", "facility_id", "as_of_date", name="uq_product_handling_history_snapshot"),
    )
    op.create_index("ix_product_handling_history_lookup", "product_handling_history", ["product_id", "facility_id", "as_of_date"])

    op.create_table(
        "optimization_missions",
        sa.Column("mission_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("facility_id", sa.String(100), sa.ForeignKey("facilities.facility_id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("window_end", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="Proposed"),
        sa.Column("appointments_at_risk", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("projected_sla_misses_before", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("projected_sla_misses_after", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_net_savings", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("optimizer_version", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_optimization_missions_facility_window", "optimization_missions", ["facility_id", "window_start", "window_end"])

    op.create_table(
        "optimization_mission_appointments",
        sa.Column("mission_id", sa.BigInteger(), sa.ForeignKey("optimization_missions.mission_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("appt_id", sa.String(50), sa.ForeignKey("appointments.appt_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("baseline_risk_score", sa.Integer(), nullable=True),
        sa.Column("baseline_projected_turn_minutes", sa.Integer(), nullable=True),
        sa.Column("optimized_projected_turn_minutes", sa.Integer(), nullable=True),
        sa.Column("sla_recovered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("priority_order", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("optimization_mission_appointments")
    op.drop_index("ix_optimization_missions_facility_window", table_name="optimization_missions")
    op.drop_table("optimization_missions")
    op.drop_index("ix_product_handling_history_lookup", table_name="product_handling_history")
    op.drop_table("product_handling_history")
    op.drop_index("ix_resource_allocations_appt", table_name="appointment_resource_allocations")
    op.drop_table("appointment_resource_allocations")
    op.drop_table("product_operational_profiles")
    op.drop_table("customer_operational_profiles")
    op.drop_table("carrier_operational_profiles")
    op.drop_table("facility_operational_profiles")
