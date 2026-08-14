from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.database import engine
from app.services.ml_service import MLService

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
