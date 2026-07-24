from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.dashboard_repository import (
    DashboardRepository,
)
from app.services.dashboard_service import (
    DashboardService,
)


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


@router.get("")
def get_dashboard(
    facility_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    repository = DashboardRepository(db)
    service = DashboardService(repository)

    return service.get_dashboard(facility_id)