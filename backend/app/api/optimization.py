from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    OptimizationMissionAcceptRequest,
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


@router.post("/scenario")
def simulate_optimization_scenario(
    payload: OptimizationWindowRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Re-optimize a mission window under operator-defined resource limits."""
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


@router.post("/missions/accept")
def accept_optimization_mission(
    payload: OptimizationMissionAcceptRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return MultiAppointmentOptimizerService(db).accept_preview(
            **payload.model_dump()
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
        message = str(exc)
        status_code = 404 if "does not exist" in message else 409
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.post("/missions/{mission_id}/outcomes/refresh")
def refresh_mission_outcomes(
    mission_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return MultiAppointmentOptimizerService(db).refresh_realized_outcomes(mission_id)
    except ValueError as exc:
        message = str(exc)
        raise HTTPException(
            status_code=404 if "does not exist" in message else 409,
            detail=message,
        ) from exc



@router.get("/learning/action-effectiveness")
def action_effectiveness(
    facility_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return MultiAppointmentOptimizerService(
        db
    ).action_effectiveness_summary(
        facility_id=facility_id,
        limit=limit,
    )
