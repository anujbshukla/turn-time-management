from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.errors import (
    AppError,
    app_error_handler,
    validation_error_handler,
)
from app.logging_config import configure_logging
from app.middleware import RequestLoggingMiddleware
from app.models import Appointment
from app.schemas import AppointmentCreate, AppointmentResponse


# Configure application logging before the API starts.
configure_logging()

# Load centralized application settings from backend/.env.
settings = get_settings()


app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
)


# Allow the React development application to call FastAPI.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add request ID, response status, and request-duration logging.
app.add_middleware(RequestLoggingMiddleware)


# Register consistent application error responses.
app.add_exception_handler(
    AppError,
    app_error_handler,
)

app.add_exception_handler(
    RequestValidationError,
    validation_error_handler,
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": f"{settings.app_name} is running",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment": settings.environment,
        "version": settings.api_version,
    }


@app.get(
    "/api/appointments",
    response_model=list[AppointmentResponse],
)
def get_appointments(
    db: Session = Depends(get_db),
) -> list[Appointment]:
    statement = select(Appointment).order_by(
        Appointment.scheduled_time
    )

    return list(db.scalars(statement).all())


@app.get(
    "/api/appointments/{appt_id}",
    response_model=AppointmentResponse,
)
def get_appointment(
    appt_id: str,
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = db.get(Appointment, appt_id)

    if appointment is None:
        raise AppError(
            message="Appointment not found",
            code="APPOINTMENT_NOT_FOUND",
            status_code=404,
            details={
                "appt_id": appt_id,
            },
        )

    return appointment


@app.post(
    "/api/appointments",
    response_model=AppointmentResponse,
    status_code=201,
)
def create_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
) -> Appointment:
    existing_appointment = db.get(
        Appointment,
        payload.appt_id,
    )

    if existing_appointment is not None:
        raise AppError(
            message="Appointment ID already exists",
            code="APPOINTMENT_ALREADY_EXISTS",
            status_code=409,
            details={
                "appt_id": payload.appt_id,
            },
        )

    appointment = Appointment(
        **payload.model_dump()
    )

    try:
        db.add(appointment)
        db.commit()
        db.refresh(appointment)

    except IntegrityError as exc:
        db.rollback()

        raise AppError(
            message="Unable to create appointment",
            code="APPOINTMENT_CREATE_FAILED",
            status_code=400,
            details={
                "appt_id": payload.appt_id,
            },
        ) from exc

    return appointment