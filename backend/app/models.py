from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

from sqlalchemy import Boolean, Column, ForeignKey, String

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

class Appointment(Base):
    __tablename__ = "appointments_temp"

    appt_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    appt_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    customer_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    customer_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    facility_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    facility_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    scheduled_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    carrier_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )