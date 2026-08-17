from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    OptimizationMissionStatusRequest,
    OptimizationWindowRequest,
)
from app.services.multi_appointment_optimizer import (
    MultiAppointmentOptimizerService,
)


router = APIRouter(
    prefix="/api/optimization",
    tags=["Optimization"],
)


@router.post("/preview")
def preview_optimization(
    payload: OptimizationWindowRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return MultiAppointmentOptimizerService(db).preview(
        **payload.model_dump()
    )


@router.post("/missions/run")
def run_optimization(
    payload: OptimizationWindowRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return MultiAppointmentOptimizerService(db).run_and_persist(
        **payload.model_dump()
    )


@router.get("/missions/latest")
def latest_missions(
    facility_id: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return MultiAppointmentOptimizerService(db).latest(
        facility_id=facility_id,
        limit=limit,
    )


@router.patch("/missions/{mission_id}/status")
def update_mission_status(
    mission_id: int,
    payload: OptimizationMissionStatusRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return MultiAppointmentOptimizerService(db).update_status(
            mission_id,
            payload.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
