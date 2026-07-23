"""Add products and appointment line items

Revision ID: a4a25d9bb006
Revises: 1e785c75eaad
Create Date: 2026-07-23 10:34:50.806053

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4a25d9bb006'
down_revision: Union[str, Sequence[str], None] = '1e785c75eaad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column(
            "product_id",
            sa.String(length=50),
            primary_key=True,
        ),
        sa.Column(
            "product_name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "sku",
            sa.String(length=75),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "category",
            sa.String(length=75),
            nullable=False,
        ),
        sa.Column(
            "unit_of_measure",
            sa.String(length=20),
            nullable=False,
            server_default="Each",
        ),
        sa.Column(
            "unit_weight_lb",
            sa.Numeric(12, 2),
            nullable=False,
        ),
        sa.Column(
            "length_in",
            sa.Numeric(10, 2),
            nullable=False,
        ),
        sa.Column(
            "width_in",
            sa.Numeric(10, 2),
            nullable=False,
        ),
        sa.Column(
            "height_in",
            sa.Numeric(10, 2),
            nullable=False,
        ),
        sa.Column(
            "unit_volume_cuft",
            sa.Numeric(12, 4),
            nullable=False,
        ),
        sa.Column(
            "units_per_case",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "cases_per_pallet",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "temperature_zone",
            sa.String(length=30),
            nullable=False,
            server_default="Ambient",
        ),
        sa.Column(
            "handling_type",
            sa.String(length=50),
            nullable=False,
            server_default="Standard",
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
        "appointment_products",
        sa.Column(
            "appointment_product_id",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "appt_id",
            sa.String(length=50),
            sa.ForeignKey(
                "appointments.appt_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.String(length=50),
            sa.ForeignKey(
                "products.product_id",
            ),
            nullable=False,
        ),
        sa.Column(
            "quantity",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "case_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "pallet_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "line_weight_lb",
            sa.Numeric(14, 2),
            nullable=False,
        ),
        sa.Column(
            "line_volume_cuft",
            sa.Numeric(14, 4),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "appt_id",
            "product_id",
            name="uq_appointment_product",
        ),
    )

    op.create_index(
        "ix_appointment_products_appt_id",
        "appointment_products",
        ["appt_id"],
    )

    op.create_index(
        "ix_appointment_products_product_id",
        "appointment_products",
        ["product_id"],
    )

    op.create_index(
        "ix_products_category",
        "products",
        ["category"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_products_category",
        table_name="products",
    )

    op.drop_index(
        "ix_appointment_products_product_id",
        table_name="appointment_products",
    )

    op.drop_index(
        "ix_appointment_products_appt_id",
        table_name="appointment_products",
    )

    op.drop_table("appointment_products")
    op.drop_table("products")
