from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models import Appointment
from app.schemas import AppointmentCreate, AppointmentResponse

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Turn Time Management API is running"
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
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
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
    existing = db.get(Appointment, payload.appt_id)

    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Appointment ID already exists",
        )

    appointment = Appointment(**payload.model_dump())

    try:
        db.add(appointment)
        db.commit()
        db.refresh(appointment)
    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="Unable to create appointment",
        ) from exc

    return appointment