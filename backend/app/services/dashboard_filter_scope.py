from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DashboardFilterScope:
    facility_id: str | None = None
    customer_id: str | None = None
    carrier_id: str | None = None
    appointment_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None

    @property
    def start_datetime(self) -> datetime | None:
        return (
            datetime.combine(self.date_from, time.min)
            if self.date_from
            else None
        )

    @property
    def end_datetime(self) -> datetime | None:
        # date_to is an exclusive boundary. The frontend sends:
        # Today => date_from=today, date_to=tomorrow.
        return (
            datetime.combine(self.date_to, time.min)
            if self.date_to
            else None
        )


@contextmanager
def scoped_appointments(
    db: Session,
    filters: DashboardFilterScope,
) -> Iterator[None]:
    """Create a request-local filtered appointments table.

    A temporary table safely shadows public.appointments for the dashboard
    repository and all downstream dashboard services. PostgreSQL does not
    support bind parameters inside CREATE VIEW definitions, so the table is
    created first and populated with a normal parameterized INSERT ... SELECT.
    """
    db.execute(text("DROP VIEW IF EXISTS pg_temp.appointments;"))
    db.execute(text("DROP TABLE IF EXISTS pg_temp.appointments;"))

    db.execute(
        text(
            """
            CREATE TEMP TABLE appointments AS
            SELECT *
            FROM public.appointments
            WHERE FALSE;
            """
        )
    )

    conditions = ["source.appt_id LIKE 'DEMO%'"]
    parameters: dict[str, object] = {}

    if filters.facility_id:
        conditions.append("source.facility_id = :facility_id")
        parameters["facility_id"] = filters.facility_id

    if filters.customer_id:
        conditions.append("source.customer_id = :customer_id")
        parameters["customer_id"] = filters.customer_id

    if filters.carrier_id:
        conditions.append("source.carrier_id = :carrier_id")
        parameters["carrier_id"] = filters.carrier_id

    if filters.appointment_type:
        conditions.append(
            "LOWER(source.appointment_type) = LOWER(:appointment_type)"
        )
        parameters["appointment_type"] = filters.appointment_type

    if filters.start_datetime is not None:
        conditions.append("source.scheduled_time >= :date_from")
        parameters["date_from"] = filters.start_datetime

    if filters.end_datetime is not None:
        conditions.append("source.scheduled_time < :date_to")
        parameters["date_to"] = filters.end_datetime

    where_clause = "\n              AND ".join(conditions)
    db.execute(
        text(
            f"""
            INSERT INTO appointments
            SELECT *
            FROM public.appointments AS source
            WHERE {where_clause};
            """
        ),
        parameters,
    )

    try:
        yield
    finally:
        db.execute(text("DROP TABLE IF EXISTS pg_temp.appointments;"))
