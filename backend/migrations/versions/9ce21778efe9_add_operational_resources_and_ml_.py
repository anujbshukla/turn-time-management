"""Add operational resources and ML outcomes

Revision ID: 9ce21778efe9
Revises: a4a25d9bb006
Create Date: 2026-07-23 11:06:43.410999

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ce21778efe9'
down_revision: Union[str, Sequence[str], None] = 'a4a25d9bb006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column(
            "customer_id",
            sa.String(length=100),
            primary_key=True,
        ),
        sa.Column(
            "customer_name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "industry",
            sa.String(length=75),
            nullable=True,
        ),
        sa.Column(
            "priority_tier",
            sa.String(length=30),
            nullable=False,
            server_default="Standard",
        ),
        sa.Column(
            "default_sla_minutes",
            sa.Integer(),
            nullable=False,
            server_default="120",
        ),
        sa.Column(
            "annual_revenue",
            sa.Numeric(16, 2),
            nullable=True,
        ),
        sa.Column(
            "preferred_facility_id",
            sa.String(length=100),
            sa.ForeignKey("facilities.facility_id"),
            nullable=True,
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "labor_shifts",
        sa.Column(
            "labor_shift_id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "facility_id",
            sa.String(length=100),
            sa.ForeignKey(
                "facilities.facility_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "shift_date",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "shift_name",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "planned_headcount",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "available_headcount",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "forklift_certified_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "hourly_rate",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="25.00",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "facility_id",
            "shift_date",
            "shift_name",
            "role",
            name="uq_labor_shift_facility_date_role",
        ),
    )

    op.create_table(
        "equipment",
        sa.Column(
            "equipment_id",
            sa.String(length=50),
            primary_key=True,
        ),
        sa.Column(
            "facility_id",
            sa.String(length=100),
            sa.ForeignKey(
                "facilities.facility_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "equipment_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "equipment_name",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "zone",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="Available",
        ),
        sa.Column(
            "hourly_operating_cost",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "capacity",
            sa.Numeric(12, 2),
            nullable=True,
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "equipment_status_events",
        sa.Column(
            "equipment_event_id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "equipment_id",
            sa.String(length=50),
            sa.ForeignKey(
                "equipment.equipment_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "event_time",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "expected_resolution_time",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "actual_loading_start_time",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "actual_loading_end_time",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "actual_departure_time",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "actual_arrival_delay_minutes",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "actual_loading_duration_minutes",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "actual_turn_time_minutes",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "actual_sla_missed",
            sa.Boolean(),
            nullable=True,
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "distance_band",
            sa.String(length=30),
            nullable=True,
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "traffic_severity",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "weather_severity",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "appointments",
        sa.Column(
            "surge_indicator",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_index(
        "ix_customers_priority_tier",
        "customers",
        ["priority_tier"],
    )

    op.create_index(
        "ix_labor_shifts_facility_date",
        "labor_shifts",
        ["facility_id", "shift_date"],
    )

    op.create_index(
        "ix_equipment_facility_status",
        "equipment",
        ["facility_id", "status"],
    )

    op.create_index(
        "ix_equipment_status_events_equipment_id",
        "equipment_status_events",
        ["equipment_id"],
    )

    op.create_index(
        "ix_appointments_actual_sla_missed",
        "appointments",
        ["actual_sla_missed"],
    )

    # op.create_foreign_key(
    #     "fk_appointments_customer_id",
    #     "appointments",
    #     "customers",
    #     ["customer_id"],
    #     ["customer_id"],
    # )


def downgrade() -> None:
    # op.drop_constraint(
    #     "fk_appointments_customer_id",
    #     "appointments",
    #     type_="foreignkey",
    # )

    op.drop_index(
        "ix_appointments_actual_sla_missed",
        table_name="appointments",
    )

    op.drop_index(
        "ix_equipment_status_events_equipment_id",
        table_name="equipment_status_events",
    )

    op.drop_index(
        "ix_equipment_facility_status",
        table_name="equipment",
    )

    op.drop_index(
        "ix_labor_shifts_facility_date",
        table_name="labor_shifts",
    )

    op.drop_index(
        "ix_customers_priority_tier",
        table_name="customers",
    )

    op.drop_column(
        "appointments",
        "surge_indicator",
    )

    op.drop_column(
        "appointments",
        "weather_severity",
    )

    op.drop_column(
        "appointments",
        "traffic_severity",
    )

    op.drop_column(
        "appointments",
        "distance_band",
    )

    op.drop_column(
        "appointments",
        "actual_sla_missed",
    )

    op.drop_column(
        "appointments",
        "actual_turn_time_minutes",
    )

    op.drop_column(
        "appointments",
        "actual_loading_duration_minutes",
    )

    op.drop_column(
        "appointments",
        "actual_arrival_delay_minutes",
    )

    op.drop_column(
        "appointments",
        "actual_departure_time",
    )

    op.drop_column(
        "appointments",
        "actual_loading_end_time",
    )

    op.drop_column(
        "appointments",
        "actual_loading_start_time",
    )

    op.drop_table("equipment_status_events")
    op.drop_table("equipment")
    op.drop_table("labor_shifts")
    op.drop_table("customers")
