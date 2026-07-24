from typing import Any

from sqlalchemy.exc import IntegrityError

from app.errors import AppError
from app.models import Appointment
from app.repositories.appointment_repository import (
    AppointmentRepository,
)
from app.schemas import AppointmentCreate


class AppointmentService:
    def __init__(
        self,
        repository: AppointmentRepository,
    ) -> None:
        self.repository = repository

    def get_paginated(
        self,
        *,
        page: int,
        page_size: int,
        facility_id: str | None,
        status: str | None,
        risk_level: str | None,
        outcome: str | None,
        search: str | None,
    ) -> dict[str, Any]:
        return self.repository.get_paginated(
            page=page,
            page_size=page_size,
            facility_id=facility_id,
            status=status,
            risk_level=risk_level,
            outcome=outcome,
            search=search,
        )

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
        existing = self.repository.get_by_id(
            payload.appt_id
        )

        if existing is not None:
            raise AppError(
                message="Appointment ID already exists",
                code="APPOINTMENT_ALREADY_EXISTS",
                status_code=409,
                details={"appt_id": payload.appt_id},
            )

        appointment = Appointment(
            **payload.model_dump()
        )

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