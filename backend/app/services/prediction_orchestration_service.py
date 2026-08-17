from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.ml.model_service import WarehouseModelService
from app.ml.scoring import load_scoring_frame
from app.repositories.appointment_repository import AppointmentRepository
from app.services.resource_planning_service import ResourcePlanningService


class PredictionOrchestrationService:
    """Single production entry point for ML-v2 appointment scoring."""

    def __init__(
        self,
        db: Session,
        repository: AppointmentRepository | None = None,
    ) -> None:
        self.db = db
        self.repository = (
            repository
            if repository is not None
            else AppointmentRepository(db)
        )
        self.artifact_dir = (
            Path(__file__).resolve().parents[2]
            / "model_artifacts"
        )

    def _model(self) -> WarehouseModelService:
        model = WarehouseModelService(
            self.artifact_dir
        )
        if not model.is_ready:
            raise RuntimeError(
                "ML-v2 model artifacts are unavailable."
            )
        return model

    @staticmethod
    def _prediction_payload(
        appt_id: str,
        scored: dict[str, Any],
    ) -> dict[str, Any]:
        predicted_arrival = scored.get(
            "predicted_arrival_time"
        )

        if pd.isna(predicted_arrival):
            predicted_arrival = None

        return {
            "appt_id": appt_id,
            "predicted_arrival_time":
                predicted_arrival,
            "predicted_delay_minutes": int(
                scored["predicted_delay_minutes"]
            ),
            "predicted_duration_minutes": int(
                scored["predicted_duration_minutes"]
            ),
            "sla_miss_probability": round(
                float(scored["sla_miss_probability"]),
                4,
            ),
            "sla_recovery_probability": round(
                float(
                    scored[
                        "sla_recovery_probability"
                    ]
                ),
                4,
            ),
            "turn_risk_score": int(
                scored["turn_risk_score"]
            ),
            "predicted_missed": bool(
                scored["predicted_missed"]
            ),
            "model_version": str(
                scored["model_version"]
            ),
        }

    def score_and_persist(
        self,
        appt_id: str,
    ) -> dict[str, Any]:
        ResourcePlanningService(
            self.db
        ).ensure_allocation(appt_id)

        frame = load_scoring_frame(
            self.db.get_bind(),
            appointment_id=appt_id,
            active_only=False,
        )

        if frame.empty:
            raise RuntimeError(
                f"Unable to build an ML-v2 scoring row "
                f"for {appt_id}."
            )

        scored = (
            self._model()
            .predict(frame)
            .iloc[0]
            .to_dict()
        )

        payload = self._prediction_payload(
            appt_id,
            scored,
        )
        self.repository.save_prediction(payload)
        return payload

    def predict_scenario(
        self,
        *,
        appt_id: str,
        actions: list[dict[str, Any]],
        selected_action_ids: list[int],
        extra_loaders: int = 0,
        extra_forklifts: int = 0,
        pre_stage_products: bool = False,
    ) -> dict[str, Any]:
        ResourcePlanningService(
            self.db
        ).ensure_allocation(appt_id)

        frame = load_scoring_frame(
            self.db.get_bind(),
            appointment_id=appt_id,
            active_only=False,
        )

        if frame.empty:
            raise RuntimeError(
                f"Unable to build an ML-v2 What-If row "
                f"for {appt_id}."
            )

        selected_ids = set(selected_action_ids)
        selected_actions = [
            action
            for action in actions
            if action["recommendation_action_id"]
            in selected_ids
        ]

        action_loaders = sum(
            int(
                action.get(
                    "additional_loaders",
                    0,
                )
                or 0
            )
            for action in selected_actions
        )
        action_forklifts = sum(
            int(
                action.get(
                    "additional_forklifts",
                    0,
                )
                or 0
            )
            for action in selected_actions
        )

        action_pre_stage = any(
            str(
                action.get("action_code") or ""
            ).upper()
            in {
                "PRE_STAGE_PRODUCTS",
                "PRESTAGE_PRODUCTS",
                "PRE_STAGE",
            }
            for action in selected_actions
        )

        dock_actions = [
            action.get("required_dock_id")
            for action in selected_actions
            if action.get("required_dock_id")
        ]

        scenario = frame.copy()

        scenario.loc[
            :,
            "planned_loaders",
        ] = (
            pd.to_numeric(
                scenario["planned_loaders"],
                errors="coerce",
            ).fillna(1)
            + action_loaders
            + extra_loaders
        ).clip(lower=1, upper=6)

        scenario.loc[
            :,
            "planned_forklifts",
        ] = (
            pd.to_numeric(
                scenario["planned_forklifts"],
                errors="coerce",
            ).fillna(1)
            + action_forklifts
            + extra_forklifts
        ).clip(lower=1, upper=4)

        if pre_stage_products or action_pre_stage:
            scenario.loc[
                :,
                "planned_staging_labor",
            ] = (
                pd.to_numeric(
                    scenario[
                        "planned_staging_labor"
                    ],
                    errors="coerce",
                ).fillna(0)
                + 1
            ).clip(lower=0, upper=3)

        if dock_actions:
            scenario.loc[
                :,
                "assigned_dock_id",
            ] = str(dock_actions[-1])

        scored = (
            self._model()
            .predict(scenario)
            .iloc[0]
            .to_dict()
        )

        return self._prediction_payload(
            appt_id,
            scored,
        )
