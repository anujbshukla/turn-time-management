from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.dashboard_repository import DashboardRepository
from app.services.dashboard_service import DashboardService
from app.services.dashboard_filter_scope import (
    DashboardFilterScope,
    scoped_appointments,
)
from app.services.global_copilot_service import GlobalCopilotService
from app.schemas import (
    DashboardWhatIfRequest,
    GlobalCopilotRequest,
    GlobalCopilotResponse,
)


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


def _filters(
    facility_id: str | None,
    customer_id: str | None,
    carrier_id: str | None,
    appointment_type: str | None,
    date_from: date | None,
    date_to: date | None,
) -> DashboardFilterScope:
    return DashboardFilterScope(
        facility_id=facility_id,
        customer_id=customer_id,
        carrier_id=carrier_id,
        appointment_type=appointment_type,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("")
def get_dashboard(
    facility_id: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    carrier_id: str | None = Query(default=None),
    appointment_type: str | None = Query(
        default=None,
        pattern="^(Inbound|Outbound)$",
    ),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repository = DashboardRepository(db)
    service = DashboardService(repository)

    filters = _filters(
        facility_id,
        customer_id,
        carrier_id,
        appointment_type,
        date_from,
        date_to,
    )

    with scoped_appointments(db, filters):
        # The temporary table applies customer/carrier/type/date scope.
        # Keep facility_id for facility-aware components such as dock heatmaps.
        return service.get_dashboard(
            facility_id,
            customer_id=customer_id,
            carrier_id=carrier_id,
            appointment_type=appointment_type,
            date_from=date_from,
            date_to=date_to,
        )


@router.get("/intelligence/filter-options")
def get_dashboard_intelligence_filter_options(
    facility_id: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    carrier_id: str | None = Query(default=None),
    appointment_type: str | None = Query(
        default=None,
        pattern="^(Inbound|Outbound)$",
    ),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repository = DashboardRepository(db)
    service = DashboardService(repository)
    return service.get_intelligence_filter_reference_data(
        facility_id=facility_id,
        customer_id=customer_id,
        carrier_id=carrier_id,
        appointment_type=appointment_type,
        date_from=date_from,
        date_to=date_to + timedelta(days=1) if date_to else None,
    )



@router.get("/intelligence")
def get_dashboard_intelligence(
    facility_id: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    carrier_id: str | None = Query(default=None),
    appointment_type: str | None = Query(
        default=None,
        pattern="^(Inbound|Outbound)$",
    ),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Independent Root Cause / Recovery analysis filters."""
    repository = DashboardRepository(db)
    service = DashboardService(repository)

    filters = _filters(
        facility_id,
        customer_id,
        carrier_id,
        appointment_type,
        date_from,
        date_to + timedelta(days=1) if date_to else None,
    )

    with scoped_appointments(db, filters):
        return service.get_intelligence(facility_id)


@router.post("/what-if")
def run_dashboard_what_if(
    payload: DashboardWhatIfRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repository = DashboardRepository(db)
    service = DashboardService(repository)
    return service.run_what_if(payload)


@router.post("/copilot", response_model=GlobalCopilotResponse)
def ask_global_copilot(
    payload: GlobalCopilotRequest,
    db: Session = Depends(get_db),
) -> GlobalCopilotResponse:
    repository = DashboardRepository(db)
    service = GlobalCopilotService(repository)
    return GlobalCopilotResponse(**service.answer(payload))
