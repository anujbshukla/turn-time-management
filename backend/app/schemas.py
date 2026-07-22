from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AppointmentCreate(BaseModel):
    appt_id: str
    appt_date: datetime
    customer_name: str | None = None
    customer_id: str | None = None
    facility_name: str | None = None
    facility_id: str | None = None
    scheduled_time: datetime
    carrier_name: str | None = None
    status: str | None = "Scheduled"


class AppointmentResponse(AppointmentCreate):
    model_config = ConfigDict(from_attributes=True)