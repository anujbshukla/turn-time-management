from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Appointment


class AppointmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Appointment]:
        statement = (
            select(Appointment)
            .order_by(Appointment.scheduled_time)
            .limit(limit)
            .offset(offset)
        )

        return list(self.db.scalars(statement).all())

    def count_all(self) -> int:
        statement = select(
            func.count(Appointment.appt_id)
        )

        return int(
            self.db.scalar(statement) or 0
        )

    def get_by_id(
        self,
        appt_id: str,
    ) -> Appointment | None:
        return self.db.get(
            Appointment,
            appt_id,
        )

    def create(
        self,
        appointment: Appointment,
    ) -> Appointment:
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)

        return appointment

    def rollback(self) -> None:
        self.db.rollback()