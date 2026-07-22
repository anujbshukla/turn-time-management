from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Appointment
from app.schemas import AppointmentCreate, AppointmentResponse
from app.services.appointment_service import AppointmentService


router = APIRouter(
    prefix="/api/appointments",
    tags=["Appointments"],
)


@router.get(
    "",
    response_model=list[AppointmentResponse],
)
def get_appointments(
    db: Session = Depends(get_db),
) -> list[Appointment]:
    service = AppointmentService(db)
    return service.get_all()


@router.get(
    "/{appt_id}",
    response_model=AppointmentResponse,
)
def get_appointment(
    appt_id: str,
    db: Session = Depends(get_db),
) -> Appointment:
    service = AppointmentService(db)
    return service.get_by_id(appt_id)


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=201,
)
def create_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
) -> Appointment:
    service = AppointmentService(db)
    return service.create(payload)