from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment
from app.repositories.appointment_repository import (
    AppointmentRepository,
)
from app.schemas import (
    AppointmentCreate,
    AppointmentCreatedResponse,
    AppointmentReferenceData,
    AppointmentResponse,
    AppointmentUpdate,
    AppointmentUpdatedResponse,
    WhatIfRequest,
    WhatIfResponse,
)
from app.services.appointment_service import (
    AppointmentService,
)


router = APIRouter(
    prefix="/api/appointments",
    tags=["Appointments"],
)


def get_appointment_service(
    db: Session = Depends(get_db),
) -> AppointmentService:
    repository = AppointmentRepository(db)

    return AppointmentService(repository)


@router.get(
    "",
    response_model=list[AppointmentResponse],
)
def get_appointments(
    service: AppointmentService = Depends(
        get_appointment_service
    ),
) -> list[Appointment]:
    return service.get_all()


@router.get("/paged")
def get_paginated_appointments(
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=10,
        ge=10,
        le=50,
    ),
    facility_id: str | None = Query(
        default=None,
    ),
    customer_id: str | None = Query(default=None),
    carrier_id: str | None = Query(default=None),
    appointment_type: str | None = Query(
        default=None,
        pattern="^(Inbound|Outbound)$",
    ),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    status: str | None = Query(
        default=None,
    ),
    risk_level: str | None = Query(
        default=None,
    ),
    outcome: str | None = Query(
        default=None,
    ),
    search: str | None = Query(
        default=None,
    ),
    sort_by: str | None = Query(
        default=None,
    ),
    sort_direction: str | None = Query(
        default=None,
        pattern="^(asc|desc)$",
    ),
    service: AppointmentService = Depends(
        get_appointment_service
    ),
) -> dict[str, Any]:
    allowed_page_sizes = {
        10,
        20,
        30,
        40,
        50,
    }

    if page_size not in allowed_page_sizes:
        page_size = 10

    return service.get_paginated(
        page=page,
        page_size=page_size,
        facility_id=facility_id,
        customer_id=customer_id,
        carrier_id=carrier_id,
        appointment_type=appointment_type,
        date_from=date_from,
        date_to=date_to,
        status=status,
        risk_level=risk_level,
        outcome=outcome,
        search=search,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )


@router.get(
    "/reference-data/options",
    response_model=AppointmentReferenceData,
)
def get_appointment_reference_data(
    service: AppointmentService = Depends(get_appointment_service),
) -> dict[str, Any]:
    return service.get_reference_data()

@router.get("/reference-data/filter-options")
def get_appointment_filter_options(
    facility_id: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    carrier_id: str | None = Query(default=None),
    appointment_type: str | None = Query(
        default=None,
        pattern="^(Inbound|Outbound)$",
    ),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    service: AppointmentService = Depends(get_appointment_service),
) -> dict[str, Any]:
    return service.get_filter_reference_data(
        facility_id=facility_id,
        customer_id=customer_id,
        carrier_id=carrier_id,
        appointment_type=appointment_type,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/{appt_id}/details")
def get_appointment_details(
    appt_id: str,
    service: AppointmentService = Depends(
        get_appointment_service
    ),
) -> dict[str, Any]:
    return service.get_details(appt_id)


@router.post(
    "/{appt_id}/what-if",
    response_model=WhatIfResponse,
)
def run_appointment_what_if(
    appt_id: str,
    payload: WhatIfRequest,
    service: AppointmentService = Depends(
        get_appointment_service
    ),
) -> WhatIfResponse:
    return service.run_what_if(
        appt_id=appt_id,
        payload=payload,
    )


@router.get(
    "/{appt_id}",
    response_model=AppointmentResponse,
)
def get_appointment(
    appt_id: str,
    service: AppointmentService = Depends(
        get_appointment_service
    ),
) -> Appointment:
    return service.get_by_id(appt_id)


@router.patch(
    "/{appt_id}",
    response_model=AppointmentUpdatedResponse,
)
def update_appointment(
    appt_id: str,
    payload: AppointmentUpdate,
    service: AppointmentService = Depends(get_appointment_service),
) -> dict[str, Any]:
    return service.update(appt_id, payload)


@router.post(
    "",
    response_model=AppointmentCreatedResponse,
    status_code=201,
)
def create_appointment(
    payload: AppointmentCreate,
    service: AppointmentService = Depends(
        get_appointment_service
    ),
) -> dict[str, Any]:
    return service.create(payload)