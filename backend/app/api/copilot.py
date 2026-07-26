from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.appointment_repository import (
    AppointmentRepository,
)
from app.schemas import (
    AppointmentCopilotRequest,
    AppointmentCopilotResponse,
)
from app.services.copilot_service import (
    CopilotService,
)


router = APIRouter(
    prefix="/api/appointments",
    tags=["Appointment Copilot"],
)


def get_copilot_service(
    db: Session = Depends(get_db),
) -> CopilotService:
    repository = AppointmentRepository(db)

    return CopilotService(repository)


@router.post(
    "/{appt_id}/copilot",
    response_model=AppointmentCopilotResponse,
)
def ask_appointment_copilot(
    appt_id: str,
    payload: AppointmentCopilotRequest,
    service: CopilotService = Depends(
        get_copilot_service
    ),
):
    return service.answer(
        appt_id=appt_id,
        payload=payload,
    )