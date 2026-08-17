from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


EXPECTED_ALEMBIC_HEAD = "h5f2c8a7d630"


class ReadinessService:
    """Runtime readiness checks for the warehouse control tower."""

    def __init__(
        self,
        engine: Engine,
        artifact_dir: Path | None = None,
    ) -> None:
        self.engine = engine
        self.artifact_dir = (
            artifact_dir
            or Path(__file__).resolve().parents[2] / "model_artifacts"
        )

    @staticmethod
    def _overall_status(
        checks: dict[str, dict[str, Any]],
    ) -> tuple[bool, str]:
        failed = [
            item
            for item in checks.values()
            if item.get("required", True)
            and item.get("status") != "ready"
        ]
        return (False, "not_ready") if failed else (True, "ready")

    def _database_check(self) -> dict[str, Any]:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return {
                "status": "ready",
                "required": True,
                "message": "Database connection is healthy.",
            }
        except Exception as exc:
            return {
                "status": "failed",
                "required": True,
                "message": f"Database connection failed: {exc}",
            }

    def _migration_check(self) -> dict[str, Any]:
        try:
            with self.engine.connect() as connection:
                current = connection.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                ).scalar_one_or_none()
            ready = str(current or "") == EXPECTED_ALEMBIC_HEAD
            return {
                "status": "ready" if ready else "failed",
                "required": True,
                "current": current,
                "expected": EXPECTED_ALEMBIC_HEAD,
                "message": (
                    "Database migration is current."
                    if ready
                    else (
                        f"Database migration is {current}; "
                        f"expected {EXPECTED_ALEMBIC_HEAD}."
                    )
                ),
            }
        except Exception as exc:
            return {
                "status": "failed",
                "required": True,
                "current": None,
                "expected": EXPECTED_ALEMBIC_HEAD,
                "message": f"Unable to determine migration state: {exc}",
            }

    def _model_check(self) -> dict[str, Any]:
        required_files = [
            "model_metadata.json",
            "turn_time_pipeline.joblib",
            "sla_miss_pipeline.joblib",
        ]
        missing = [
            name
            for name in required_files
            if not (self.artifact_dir / name).exists()
        ]
        metadata: dict[str, Any] = {}
        metadata_path = self.artifact_dir / "model_metadata.json"
        if metadata_path.exists():
            try:
                metadata = json.loads(
                    metadata_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                missing.append("valid model_metadata.json")

        ready = not missing and bool(metadata.get("model_version"))
        return {
            "status": "ready" if ready else "failed",
            "required": True,
            "model_version": metadata.get("model_version"),
            "missing": missing,
            "message": (
                "Production ML artifacts are available."
                if ready
                else "Production ML artifacts are incomplete."
            ),
        }

    def _data_foundation_check(self) -> dict[str, Any]:
        required_tables = [
            "appointments",
            "appointment_predictions",
            "appointment_resource_allocations",
            "labor_shifts",
            "equipment",
            "optimization_missions",
            "optimization_mission_actions",
            "ml_model_registry",
            "ml_monitoring_snapshots",
            "optimization_action_effectiveness",
        ]
        try:
            with self.engine.connect() as connection:
                rows = connection.execute(
                    text(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name = ANY(:table_names)
                        """
                    ),
                    {"table_names": required_tables},
                ).scalars().all()
            found = set(rows)
            missing = [
                name for name in required_tables if name not in found
            ]
            return {
                "status": "ready" if not missing else "failed",
                "required": True,
                "checked": len(required_tables),
                "missing": missing,
                "message": (
                    "Operational and AI data foundation is available."
                    if not missing
                    else "Required operational tables are missing."
                ),
            }
        except Exception as exc:
            return {
                "status": "failed",
                "required": True,
                "missing": required_tables,
                "message": f"Unable to inspect data foundation: {exc}",
            }

    def check(self) -> dict[str, Any]:
        checks = {
            "database": self._database_check(),
            "migration": self._migration_check(),
            "ml_artifacts": self._model_check(),
            "data_foundation": self._data_foundation_check(),
        }
        ready, status = self._overall_status(checks)
        return {
            "ready": ready,
            "status": status,
            "checks": checks,
        }
