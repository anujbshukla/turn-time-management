from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.ml.features import prepare_features


class WarehouseModelService:
    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.turn_model = None
        self.sla_model = None
        self.metadata: dict[str, Any] | None = None
        self.reload()

    @property
    def is_ready(self) -> bool:
        return self.turn_model is not None and self.sla_model is not None and self.metadata is not None

    def reload(self) -> None:
        turn_path = self.artifact_dir / "turn_time_pipeline.joblib"
        sla_path = self.artifact_dir / "sla_miss_pipeline.joblib"
        metadata_path = self.artifact_dir / "model_metadata.json"
        if not (turn_path.exists() and sla_path.exists() and metadata_path.exists()):
            self.turn_model = None
            self.sla_model = None
            self.metadata = None
            return
        self.turn_model = joblib.load(turn_path)
        self.sla_model = joblib.load(sla_path)
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    def status(self) -> dict[str, Any]:
        return {
            "ready": self.is_ready,
            "artifact_directory": str(self.artifact_dir),
            "metadata": self.metadata,
        }

    def predict(self, raw_frame: pd.DataFrame) -> pd.DataFrame:
        if not self.is_ready:
            raise RuntimeError("ML model artifacts are not available. Run the training command first.")
        features = prepare_features(raw_frame)
        predicted_turn = np.maximum(1, np.rint(self.turn_model.predict(features))).astype(int)
        miss_probability = self.sla_model.predict_proba(features)[:, 1]
        result = raw_frame[["appt_id", "scheduled_time", "estimated_arrival_time"]].copy()
        estimated_delay = (
            (pd.to_datetime(raw_frame["estimated_arrival_time"], errors="coerce") -
             pd.to_datetime(raw_frame["scheduled_time"], errors="coerce"))
            .dt.total_seconds().div(60).fillna(0).clip(lower=-120, upper=720)
        )
        result["predicted_delay_minutes"] = np.maximum(0, np.rint(estimated_delay)).astype(int)
        result["predicted_duration_minutes"] = predicted_turn
        result["sla_miss_probability"] = np.clip(miss_probability, 0.001, 0.999)
        result["sla_recovery_probability"] = np.clip(1.0 - miss_probability, 0.001, 0.999)
        result["turn_risk_score"] = np.rint(result["sla_miss_probability"] * 100).astype(int)
        result["predicted_missed"] = result["sla_miss_probability"] >= 0.50
        result["model_version"] = self.metadata["model_version"]
        return result
