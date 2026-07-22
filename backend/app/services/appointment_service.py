from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Appointment
from app.repositories.appointment_repository import (
    AppointmentRepository,
)
from app.schemas import AppointmentCreate


class AppointmentService:
    def __init__(self, db: Session) -> None:
        self.repository = AppointmentRepository(db)

    def get_all(self) -> list[Appointment]:
        return self.repository.get_all()

    def get_by_id(self, appt_id: str) -> Appointment:
        appointment = self.repository.get_by_id(appt_id)

        if appointment is None:
            raise AppError(
                message="Appointment not found",
                code="APPOINTMENT_NOT_FOUND",
                status_code=404,
                details={"appt_id": appt_id},
            )

        return appointment

    def create(
        self,
        payload: AppointmentCreate,
    ) -> Appointment:
        existing = self.repository.get_by_id(payload.appt_id)

        if existing is not None:
            raise AppError(
                message="Appointment ID already exists",
                code="APPOINTMENT_ALREADY_EXISTS",
                status_code=409,
                details={"appt_id": payload.appt_id},
            )

        appointment = Appointment(**payload.model_dump())

        try:
            return self.repository.create(appointment)
        except IntegrityError as exc:
            self.repository.rollback()

            raise AppError(
                message="Unable to create appointment",
                code="APPOINTMENT_CREATE_FAILED",
                status_code=400,
                details={"appt_id": payload.appt_id},
            ) from exc