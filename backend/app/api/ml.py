from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.database import engine
from app.services.ml_service import MLService
from app.services.ml_monitoring_service import MLMonitoringService

router = APIRouter(prefix="/api/ml", tags=["Machine Learning"])


@router.get("/status")
def model_status() -> dict[str, Any]:
    return MLService(engine).status()


@router.post("/train")
def train_models() -> dict[str, Any]:
    return MLService(engine).train()


@router.post("/score")
def score_appointments() -> dict[str, Any]:
    return MLService(engine).score()


@router.post("/train-and-score")
def train_and_score() -> dict[str, Any]:
    return MLService(engine).train_and_score()



@router.get("/monitoring")
def model_monitoring(
    window_days: int = Query(default=30, ge=7, le=180),
    facility_id: str | None = Query(default=None),
    persist: bool = Query(default=True),
) -> dict[str, Any]:
    return MLMonitoringService(engine).monitor(
        window_days=window_days,
        facility_id=facility_id,
        persist=persist,
    )


@router.get("/monitoring/history")
def model_monitoring_history(
    model_version: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
) -> list[dict[str, Any]]:
    return MLMonitoringService(engine).history(
        model_version=model_version,
        limit=limit,
    )


@router.get("/registry")
def model_registry(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    return MLMonitoringService(engine).registry(limit=limit)


@router.post("/registry/register-current")
def register_current_model() -> dict[str, Any]:
    return MLMonitoringService(engine).register_current_model(
        status="Production"
    )
