from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
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
        return datetime.combine(self.date_from, time.min) if self.date_from else None

    @property
    def end_datetime(self) -> datetime | None:
        # The frontend sends date_to as an exclusive boundary:
        # Today => [today 00:00, tomorrow 00:00).
        return datetime.combine(self.date_to, time.min) if self.date_to else None

    @property
    def is_single_day(self) -> bool:
        return (
            self.date_from is not None
            and self.date_to is not None
            and self.date_to == self.date_from + timedelta(days=1)
        )

    def shifted(self, days: int) -> "DashboardFilterScope":
        return DashboardFilterScope(
            facility_id=self.facility_id,
            customer_id=self.customer_id,
            carrier_id=self.carrier_id,
            appointment_type=self.appointment_type,
            date_from=self.date_from + timedelta(days=days) if self.date_from else None,
            date_to=self.date_to + timedelta(days=days) if self.date_to else None,
        )


@contextmanager
def scoped_appointments(
    db: Session,
    filters: DashboardFilterScope,
) -> Iterator[None]:
    """Shadow public.appointments with a request-local filtered temp table.

    PostgreSQL does not allow bind parameters inside a CREATE VIEW definition.
    Create the temporary table first, then populate it with a parameterized
    INSERT ... SELECT, where normal SQL bind parameters are supported.
    """
    db.execute(text("DROP VIEW IF EXISTS pg_temp.appointments;"))
    db.execute(text("DROP TABLE IF EXISTS pg_temp.appointments;"))

    db.execute(
        text(
            """
            CREATE TEMP TABLE appointments
            (LIKE public.appointments INCLUDING DEFAULTS)
            ON COMMIT DROP;
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
        conditions.append("LOWER(source.appointment_type) = LOWER(:appointment_type)")
        parameters["appointment_type"] = filters.appointment_type

    if filters.start_datetime is not None:
        conditions.append("source.scheduled_time >= :date_from")
        parameters["date_from"] = filters.start_datetime

    if filters.end_datetime is not None:
        conditions.append("source.scheduled_time < :date_to")
        parameters["date_to"] = filters.end_datetime

    where_clause = "\n              AND ".join(conditions)
    insert_statement = text(
        f"""
        INSERT INTO appointments
        SELECT *
        FROM public.appointments AS source
        WHERE {where_clause};
        """
    )

    db.execute(insert_statement, parameters)

    try:
        yield
    finally:
        db.execute(text("DROP TABLE IF EXISTS pg_temp.appointments;"))
