from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine

from app.ml.model_service import WarehouseModelService
from app.ml.scoring import score_current_appointments
from app.ml.training import train_models


class MLService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.artifact_dir = Path(__file__).resolve().parents[2] / "model_artifacts"

    def status(self) -> dict[str, Any]:
        return WarehouseModelService(self.artifact_dir).status()

    def train(self) -> dict[str, Any]:
        return train_models(self.engine, self.artifact_dir)

    def score(self) -> dict[str, Any]:
        return score_current_appointments(self.engine, self.artifact_dir)

    def train_and_score(self) -> dict[str, Any]:
        metadata = self.train()
        scoring = self.score()
        return {"training": metadata, "scoring": scoring}
