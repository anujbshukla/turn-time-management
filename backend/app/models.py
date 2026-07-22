from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


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