from __future__ import annotations
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

from sqlalchemy import Boolean, Column, ForeignKey, String

class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

class Facility(Base):
    __tablename__ = "facilities"

    facility_id = Column(
        String(100),
        primary_key=True,
    )

    facility_name = Column(
        String(100),
        nullable=False,
    )

    timezone = Column(
        String(50),
        nullable=False,
        default="America/New_York",
    )

    active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

class Carrier(Base):
    __tablename__ = "carriers"

    carrier_id = Column(
        String(100),
        primary_key=True,
    )

    carrier_name = Column(
        String(100),
        nullable=False,
    )

    active = Column(
        Boolean,
        nullable=False,
        default=True,
    )
class Dock(Base):
    __tablename__ = "docks"

    dock_id = Column(
        String(50),
        primary_key=True,
    )

    facility_id = Column(
        String(100),
        ForeignKey("facilities.facility_id"),
        nullable=False,
    )

    dock_name = Column(
        String(100),
        nullable=False,
    )

    dock_type = Column(
        String(50),
    )

    temperature_zone = Column(
        String(50),
    )

    active = Column(
        Boolean,
        default=True,
        nullable=False,
    )
class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )


from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    appt_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    appt_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    customer_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("customers.customer_id"),
        nullable=True,
    )

    customer_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    facility_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("facilities.facility_id"),
        nullable=False,
    )

    carrier_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("carriers.carrier_id"),
        nullable=True,
    )

    scheduled_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    estimated_arrival_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    actual_arrival_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    planned_start_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    actual_start_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    planned_end_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    actual_end_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    assigned_dock_id: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("docks.dock_id"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Scheduled",
    )

    appointment_type: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    load_type: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    trailer_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    pallet_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    sku_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    total_weight: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    total_cube: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    sla_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=120,
    )

    detention_cost_per_hour: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("100.00"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    actual_loading_start_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    actual_loading_end_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    actual_departure_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    actual_arrival_delay_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    actual_loading_duration_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    actual_turn_time_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    actual_sla_missed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    distance_band: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    traffic_severity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    weather_severity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    surge_indicator: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )