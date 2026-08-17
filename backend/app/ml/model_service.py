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
        self.arrival_model = None
        self.turn_model = None
        self.sla_model = None
        self.metadata: dict[str, Any] | None = None
        self.reload()

    @property
    def is_ready(self) -> bool:
        return (
            self.arrival_model is not None
            and self.turn_model is not None
            and self.sla_model is not None
            and self.metadata is not None
        )

    def reload(self) -> None:
        arrival_path = (
            self.artifact_dir
            / "arrival_delay_pipeline.joblib"
        )
        turn_path = (
            self.artifact_dir
            / "turn_time_pipeline.joblib"
        )
        sla_path = (
            self.artifact_dir
            / "sla_miss_pipeline.joblib"
        )
        metadata_path = (
            self.artifact_dir
            / "model_metadata.json"
        )

        if not (
            arrival_path.exists()
            and turn_path.exists()
            and sla_path.exists()
            and metadata_path.exists()
        ):
            self.arrival_model = None
            self.turn_model = None
            self.sla_model = None
            self.metadata = None
            return

        self.arrival_model = joblib.load(arrival_path)
        self.turn_model = joblib.load(turn_path)
        self.sla_model = joblib.load(sla_path)
        self.metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )

    def status(self) -> dict[str, Any]:
        return {
            "ready": self.is_ready,
            "artifact_directory": str(self.artifact_dir),
            "metadata": self.metadata,
        }

    def predict(
        self,
        raw_frame: pd.DataFrame,
    ) -> pd.DataFrame:
        if not self.is_ready:
            raise RuntimeError(
                "ML-v2 model artifacts are not available. "
                "Run the training command first."
            )

        features = prepare_features(raw_frame)

        predicted_signed_delay = np.clip(
            np.rint(
                self.arrival_model.predict(features)
            ),
            -120,
            720,
        ).astype(int)

        predicted_duration = np.maximum(
            1,
            np.rint(
                self.turn_model.predict(features)
            ),
        ).astype(int)

        miss_probability = np.clip(
            self.sla_model.predict_proba(features)[:, 1],
            0.001,
            0.999,
        )

        threshold = float(
            self.metadata.get(
                "sla_decision_threshold",
                0.50,
            )
        )

        scheduled = pd.to_datetime(
            raw_frame["scheduled_time"],
            errors="coerce",
        )
        predicted_arrival = scheduled + pd.to_timedelta(
            predicted_signed_delay,
            unit="m",
        )

        # Downstream operational code interprets delay as
        # "minutes late", so preserve only the late portion here.
        predicted_late_minutes = np.maximum(
            0,
            predicted_signed_delay,
        ).astype(int)

        sla_minutes = pd.to_numeric(
            raw_frame["sla_minutes"],
            errors="coerce",
        ).fillna(120.0).to_numpy(dtype=float)

        congestion = (
            pd.to_numeric(
                raw_frame.get(
                    "dock_congestion_percent",
                    0,
                ),
                errors="coerce",
            )
            .fillna(0.0)
            .clip(0, 100)
            .to_numpy(dtype=float)
            / 100.0
        )

        lateness_pressure = np.clip(
            predicted_late_minutes / 45.0,
            0.0,
            1.0,
        )

        duration_pressure = np.clip(
            predicted_duration
            / np.maximum(sla_minutes, 1.0),
            0.0,
            1.5,
        ) / 1.5

        # Combined risk is intentionally not just probability * 100.
        # SLA probability remains dominant, while predicted lateness,
        # service pressure and congestion add operational context.
        risk_score = np.rint(
            100
            * np.clip(
                (0.65 * miss_probability)
                + (0.15 * lateness_pressure)
                + (0.15 * duration_pressure)
                + (0.05 * congestion),
                0.0,
                1.0,
            )
        ).astype(int)

        result = raw_frame[
            [
                "appt_id",
                "scheduled_time",
                "estimated_arrival_time",
            ]
        ].copy()

        result["predicted_arrival_time"] = (
            predicted_arrival
        )
        result["predicted_signed_arrival_delta_minutes"] = (
            predicted_signed_delay
        )
        result["predicted_delay_minutes"] = (
            predicted_late_minutes
        )
        result["predicted_duration_minutes"] = (
            predicted_duration
        )
        result["sla_miss_probability"] = miss_probability
        result["sla_recovery_probability"] = np.clip(
            1.0 - miss_probability,
            0.001,
            0.999,
        )
        result["turn_risk_score"] = risk_score
        result["predicted_missed"] = (
            miss_probability >= threshold
        )
        result["model_version"] = self.metadata[
            "model_version"
        ]

        return result
