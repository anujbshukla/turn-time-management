from datetime import date, datetime
from decimal import Decimal
from typing import Any
from app.engines.what_if_engine import WhatIfEngine
from app.schemas import WhatIfRequest
from sqlalchemy.exc import IntegrityError

from app.errors import AppError
from app.models import Appointment
from app.repositories.appointment_repository import (
    AppointmentRepository,
)
from app.schemas import AppointmentCreate


def normalize_database_value(
    value: Any,
) -> Any:
    """
    Convert PostgreSQL-specific types into JSON-serializable values.
    """

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            key: normalize_database_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            normalize_database_value(item)
            for item in value
        ]

    return value


class AppointmentService:
    def run_what_if(
        self,
        *,
        appt_id: str,
        payload: WhatIfRequest,
    ) -> dict[str, Any]:
        details = self.repository.get_details(
            appt_id
        )

        if details is None:
            raise AppError(
                message="Appointment not found",
                code="APPOINTMENT_NOT_FOUND",
                status_code=404,
                details={"appt_id": appt_id},
            )

        engine = WhatIfEngine()

        try:
            result = engine.simulate(
                appointment=details["appointment"],
                prediction=details["prediction"],
                actions=details[
                    "recommendation_actions"
                ],
                selected_action_ids=(
                    payload.selected_action_ids
                ),
                extra_loaders=payload.extra_loaders,
                extra_forklifts=(
                    payload.extra_forklifts
                ),
                pre_stage_products=(
                    payload.pre_stage_products
                ),
            )
        except ValueError as exc:
            raise AppError(
                message=str(exc),
                code="WHAT_IF_SIMULATION_FAILED",
                status_code=400,
                details={"appt_id": appt_id},
            ) from exc

        return normalize_database_value(
            {
                "appt_id": appt_id,
                "selected_action_ids":
                    payload.selected_action_ids,
                **result,
            }
        )
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

    def get_by_id(
        self,
        appt_id: str,
    ) -> Appointment:
        appointment = self.repository.get_by_id(
            appt_id
        )

        if appointment is None:
            raise AppError(
                message="Appointment not found",
                code="APPOINTMENT_NOT_FOUND",
                status_code=404,
                details={"appt_id": appt_id},
            )

        return appointment

    def get_details(
        self,
        appt_id: str,
    ) -> dict[str, Any]:
        details = self.repository.get_details(
            appt_id
        )

        if details is None:
            raise AppError(
                message="Appointment not found",
                code="APPOINTMENT_NOT_FOUND",
                status_code=404,
                details={"appt_id": appt_id},
            )

        return normalize_database_value(details)

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
            return self.repository.create(
                appointment
            )

        except IntegrityError as exc:
            self.repository.rollback()

            raise AppError(
                message="Unable to create appointment",
                code="APPOINTMENT_CREATE_FAILED",
                status_code=400,
                details={"appt_id": payload.appt_id},
            ) from exc