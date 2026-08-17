from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


class MLMonitoringService:
    """Production model monitoring and retraining governance.

    Monitoring is based only on appointments that have actual outcomes.
    The latest prediction for each appointment is compared with the observed
    turn time / SLA result, and recent operating features are compared with
    the preceding equally-sized period for drift.
    """

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

    def _artifact_metadata(self) -> dict[str, Any] | None:
        path = self.artifact_dir / "model_metadata.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def register_current_model(
        self,
        metadata: dict[str, Any] | None = None,
        *,
        status: str = "Production",
    ) -> dict[str, Any]:
        metadata = metadata or self._artifact_metadata()
        if not metadata:
            raise RuntimeError("Model metadata is unavailable.")

        model_version = str(
            metadata.get("model_version") or "unknown-model"
        )
        trained_at = metadata.get("trained_at")
        rows = metadata.get("rows") or {}
        date_ranges = metadata.get("date_ranges") or {}
        training_range = date_ranges.get("train") or [None, None]

        with self.engine.begin() as connection:
            if status == "Production":
                connection.execute(
                    text(
                        """
                        UPDATE ml_model_registry
                        SET status = 'Retired'
                        WHERE status = 'Production'
                          AND model_version <> :model_version;
                        """
                    ),
                    {"model_version": model_version},
                )

            row = connection.execute(
                text(
                    """
                    INSERT INTO ml_model_registry (
                        model_version,
                        status,
                        trained_at,
                        promoted_at,
                        training_window_start,
                        training_window_end,
                        training_rows,
                        algorithm,
                        training_metrics,
                        promotion_checks,
                        metadata
                    ) VALUES (
                        :model_version,
                        CAST(:status AS VARCHAR),
                        CAST(:trained_at AS TIMESTAMPTZ),
                        CASE
                            WHEN CAST(:status AS VARCHAR) = 'Production'
                            THEN NOW()
                            ELSE NULL
                        END,
                        CAST(:training_window_start AS TIMESTAMPTZ),
                        CAST(:training_window_end AS TIMESTAMPTZ),
                        :training_rows,
                        CAST(:algorithm AS JSONB),
                        CAST(:training_metrics AS JSONB),
                        CAST(:promotion_checks AS JSONB),
                        CAST(:metadata AS JSONB)
                    )
                    ON CONFLICT (model_version)
                    DO UPDATE SET
                        status = EXCLUDED.status,
                        trained_at = COALESCE(
                            EXCLUDED.trained_at,
                            ml_model_registry.trained_at
                        ),
                        promoted_at = CASE
                            WHEN EXCLUDED.status = 'Production'
                            THEN COALESCE(
                                ml_model_registry.promoted_at,
                                NOW()
                            )
                            ELSE ml_model_registry.promoted_at
                        END,
                        training_window_start =
                            EXCLUDED.training_window_start,
                        training_window_end =
                            EXCLUDED.training_window_end,
                        training_rows = EXCLUDED.training_rows,
                        algorithm = EXCLUDED.algorithm,
                        training_metrics = EXCLUDED.training_metrics,
                        promotion_checks = EXCLUDED.promotion_checks,
                        metadata = EXCLUDED.metadata
                    RETURNING
                        registry_id,
                        model_version,
                        status,
                        trained_at,
                        registered_at,
                        promoted_at,
                        training_rows;
                    """
                ),
                {
                    "model_version": model_version,
                    "status": status,
                    "trained_at": trained_at,
                    "training_window_start": (
                        training_range[0]
                        if len(training_range) > 0
                        else None
                    ),
                    "training_window_end": (
                        training_range[1]
                        if len(training_range) > 1
                        else None
                    ),
                    "training_rows": int(rows.get("total") or 0) or None,
                    "algorithm": json.dumps(
                        metadata.get("algorithm") or {}
                    ),
                    "training_metrics": json.dumps(
                        metadata.get("metrics") or {}
                    ),
                    "promotion_checks": json.dumps(
                        metadata.get("promotion_checks") or {}
                    ),
                    "metadata": json.dumps(metadata),
                },
            ).mappings().one()

        return dict(row)

    def registry(
        self,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        registry_id,
                        model_version,
                        status,
                        trained_at,
                        registered_at,
                        promoted_at,
                        training_window_start,
                        training_window_end,
                        training_rows,
                        algorithm,
                        training_metrics,
                        promotion_checks,
                        notes
                    FROM ml_model_registry
                    ORDER BY
                        CASE status
                            WHEN 'Production' THEN 0
                            WHEN 'Candidate' THEN 1
                            ELSE 2
                        END,
                        COALESCE(promoted_at, trained_at, registered_at) DESC
                    LIMIT :limit;
                    """
                ),
                {"limit": limit},
            ).mappings().all()
        return [dict(row) for row in rows]

    def _current_model_version(self) -> str:
        metadata = self._artifact_metadata()
        if metadata and metadata.get("model_version"):
            return str(metadata["model_version"])

        with self.engine.connect() as connection:
            version = connection.execute(
                text(
                    """
                    SELECT model_version
                    FROM appointment_predictions
                    WHERE model_version IS NOT NULL
                    ORDER BY generated_at DESC, prediction_id DESC
                    LIMIT 1;
                    """
                )
            ).scalar_one_or_none()
        return str(version or "unknown-model")

    def _performance_metrics(
        self,
        *,
        model_version: str,
        window_start: datetime,
        window_end: datetime,
        facility_id: str | None = None,
    ) -> dict[str, Any]:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    WITH latest_prediction AS (
                        SELECT DISTINCT ON (prediction.appt_id)
                            prediction.appt_id,
                            prediction.predicted_arrival_time,
                            prediction.predicted_duration_minutes,
                            prediction.predicted_missed,
                            prediction.sla_miss_probability,
                            prediction.model_version,
                            prediction.generated_at
                        FROM appointment_predictions prediction
                        WHERE prediction.model_version = :model_version
                        ORDER BY
                            prediction.appt_id,
                            prediction.generated_at DESC,
                            prediction.prediction_id DESC
                    ),
                    sample AS (
                        SELECT
                            appointment.appt_id,
                            appointment.facility_id,
                            appointment.scheduled_time,
                            appointment.actual_arrival_time,
                            appointment.actual_turn_time_minutes,
                            appointment.actual_sla_missed,
                            prediction.predicted_arrival_time,
                            prediction.predicted_duration_minutes,
                            prediction.predicted_missed,
                            prediction.sla_miss_probability
                        FROM appointments appointment
                        JOIN latest_prediction prediction
                          ON prediction.appt_id = appointment.appt_id
                        WHERE appointment.status = 'Completed'
                          AND appointment.actual_turn_time_minutes IS NOT NULL
                          AND appointment.actual_sla_missed IS NOT NULL
                          AND appointment.scheduled_time >= :window_start
                          AND appointment.scheduled_time < :window_end
                          AND (
                              CAST(:facility_id AS VARCHAR) IS NULL
                              OR appointment.facility_id =
                                 CAST(:facility_id AS VARCHAR)
                          )
                    )
                    SELECT
                        COUNT(*)::INTEGER AS sample_size,
                        AVG(
                            ABS(
                                actual_turn_time_minutes
                                - predicted_duration_minutes
                            )
                        ) AS duration_mae,
                        SQRT(
                            AVG(
                                POWER(
                                    actual_turn_time_minutes
                                    - predicted_duration_minutes,
                                    2
                                )
                            )
                        ) AS duration_rmse,
                        AVG(
                            ABS(
                                EXTRACT(
                                    EPOCH FROM (
                                        actual_arrival_time
                                        - predicted_arrival_time
                                    )
                                ) / 60.0
                            )
                        ) FILTER (
                            WHERE actual_arrival_time IS NOT NULL
                              AND predicted_arrival_time IS NOT NULL
                        ) AS arrival_mae,
                        COUNT(*) FILTER (
                            WHERE predicted_missed = TRUE
                              AND actual_sla_missed = TRUE
                        )::INTEGER AS true_positive,
                        COUNT(*) FILTER (
                            WHERE predicted_missed = TRUE
                              AND actual_sla_missed = FALSE
                        )::INTEGER AS false_positive,
                        COUNT(*) FILTER (
                            WHERE predicted_missed = FALSE
                              AND actual_sla_missed = TRUE
                        )::INTEGER AS false_negative,
                        COUNT(*) FILTER (
                            WHERE predicted_missed = FALSE
                              AND actual_sla_missed = FALSE
                        )::INTEGER AS true_negative,
                        AVG(sla_miss_probability)
                            FILTER (WHERE actual_sla_missed = TRUE)
                            AS avg_probability_on_misses,
                        AVG(sla_miss_probability)
                            FILTER (WHERE actual_sla_missed = FALSE)
                            AS avg_probability_on_successes
                    FROM sample;
                    """
                ),
                {
                    "model_version": model_version,
                    "window_start": window_start,
                    "window_end": window_end,
                    "facility_id": facility_id,
                },
            ).mappings().one()

        result = dict(row)
        tp = int(result.get("true_positive") or 0)
        fp = int(result.get("false_positive") or 0)
        fn = int(result.get("false_negative") or 0)

        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        if precision is not None and recall is not None:
            beta2 = 4.0
            denominator = beta2 * precision + recall
            f2 = (
                (1 + beta2) * precision * recall / denominator
                if denominator
                else 0.0
            )
        else:
            f2 = None

        result.update(
            {
                "sla_precision": precision,
                "sla_recall": recall,
                "sla_f2": f2,
            }
        )
        return result

    def _facility_metrics(
        self,
        *,
        model_version: str,
        window_start: datetime,
        window_end: datetime,
    ) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    WITH latest_prediction AS (
                        SELECT DISTINCT ON (prediction.appt_id)
                            prediction.appt_id,
                            prediction.predicted_duration_minutes,
                            prediction.predicted_missed
                        FROM appointment_predictions prediction
                        WHERE prediction.model_version = :model_version
                        ORDER BY
                            prediction.appt_id,
                            prediction.generated_at DESC,
                            prediction.prediction_id DESC
                    )
                    SELECT
                        appointment.facility_id,
                        facility.facility_name,
                        COUNT(*)::INTEGER AS sample_size,
                        AVG(
                            ABS(
                                appointment.actual_turn_time_minutes
                                - prediction.predicted_duration_minutes
                            )
                        ) AS duration_mae,
                        COUNT(*) FILTER (
                            WHERE prediction.predicted_missed = TRUE
                              AND appointment.actual_sla_missed = TRUE
                        )::INTEGER AS tp,
                        COUNT(*) FILTER (
                            WHERE prediction.predicted_missed = TRUE
                              AND appointment.actual_sla_missed = FALSE
                        )::INTEGER AS fp,
                        COUNT(*) FILTER (
                            WHERE prediction.predicted_missed = FALSE
                              AND appointment.actual_sla_missed = TRUE
                        )::INTEGER AS fn
                    FROM appointments appointment
                    JOIN latest_prediction prediction
                      ON prediction.appt_id = appointment.appt_id
                    JOIN facilities facility
                      ON facility.facility_id = appointment.facility_id
                    WHERE appointment.status = 'Completed'
                      AND appointment.actual_turn_time_minutes IS NOT NULL
                      AND appointment.actual_sla_missed IS NOT NULL
                      AND appointment.scheduled_time >= :window_start
                      AND appointment.scheduled_time < :window_end
                    GROUP BY
                        appointment.facility_id,
                        facility.facility_name
                    ORDER BY appointment.facility_id;
                    """
                ),
                {
                    "model_version": model_version,
                    "window_start": window_start,
                    "window_end": window_end,
                },
            ).mappings().all()

        output = []
        for row in rows:
            item = dict(row)
            tp = int(item.pop("tp") or 0)
            fp = int(item.pop("fp") or 0)
            fn = int(item.pop("fn") or 0)
            item["sla_precision"] = (
                tp / (tp + fp)
                if tp + fp
                else None
            )
            item["sla_recall"] = (
                tp / (tp + fn)
                if tp + fn
                else None
            )
            output.append(item)
        return output

    def _feature_drift(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
        facility_id: str | None = None,
    ) -> dict[str, Any]:
        period = window_end - window_start
        prior_start = window_start - period
        feature_sql = {
            "pallet_count": "appointment.pallet_count",
            "sku_count": "appointment.sku_count",
            "total_weight": "appointment.total_weight",
            "total_cube": "appointment.total_cube",
            "traffic_severity": "appointment.traffic_severity",
            "weather_severity": "appointment.weather_severity",
            "dock_congestion_percent": "allocation.dock_congestion_percent",
            "labor_utilization_percent": "allocation.labor_utilization_percent",
            "forklift_utilization_percent": "allocation.forklift_utilization_percent",
        }

        expressions = []
        for name, expression in feature_sql.items():
            expressions.extend(
                [
                    f"AVG({expression}) FILTER (WHERE appointment.scheduled_time >= :window_start AND appointment.scheduled_time < :window_end) AS recent_{name}_mean",
                    f"AVG({expression}) FILTER (WHERE appointment.scheduled_time >= :prior_start AND appointment.scheduled_time < :window_start) AS prior_{name}_mean",
                    f"STDDEV_POP({expression}) FILTER (WHERE appointment.scheduled_time >= :prior_start AND appointment.scheduled_time < :window_start) AS prior_{name}_std",
                ]
            )

        query = f"""
            SELECT
                {", ".join(expressions)}
            FROM appointments appointment
            LEFT JOIN appointment_resource_allocations allocation
              ON allocation.appt_id = appointment.appt_id
            WHERE appointment.status = 'Completed'
              AND appointment.scheduled_time >= :prior_start
              AND appointment.scheduled_time < :window_end
              AND (
                  CAST(:facility_id AS VARCHAR) IS NULL
                  OR appointment.facility_id =
                     CAST(:facility_id AS VARCHAR)
              );
        """

        with self.engine.connect() as connection:
            row = dict(
                connection.execute(
                    text(query),
                    {
                        "prior_start": prior_start,
                        "window_start": window_start,
                        "window_end": window_end,
                        "facility_id": facility_id,
                    },
                ).mappings().one()
            )

        features = []
        scores = []
        for name in feature_sql:
            recent = row.get(f"recent_{name}_mean")
            prior = row.get(f"prior_{name}_mean")
            std = row.get(f"prior_{name}_std")
            if recent is None or prior is None:
                continue
            denominator = max(
                abs(float(std or 0)),
                abs(float(prior)) * 0.10,
                1.0,
            )
            score = abs(float(recent) - float(prior)) / denominator
            score = min(score, 3.0)
            scores.append(score)
            features.append(
                {
                    "feature": name,
                    "recent_mean": round(float(recent), 3),
                    "prior_mean": round(float(prior), 3),
                    "standardized_shift": round(score, 3),
                    "status": (
                        "High"
                        if score >= 1.0
                        else "Watch"
                        if score >= 0.5
                        else "Stable"
                    ),
                }
            )

        overall = (
            sum(scores) / len(scores)
            if scores
            else 0.0
        )
        return {
            "score": round(overall, 4),
            "features": sorted(
                features,
                key=lambda item: item["standardized_shift"],
                reverse=True,
            ),
        }

    def _optimizer_effectiveness(
        self,
        *,
        window_start: datetime,
        window_end: datetime,
        facility_id: str | None = None,
    ) -> dict[str, Any]:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        COUNT(*)::INTEGER AS mission_count,
                        COALESCE(
                            SUM(outcome_sample_size),
                            0
                        )::INTEGER AS appointment_sample_size,
                        AVG(
                            ABS(
                                realized_net_savings
                                - estimated_net_savings
                            )
                            / NULLIF(
                                ABS(estimated_net_savings),
                                0
                            )
                            * 100.0
                        ) FILTER (
                            WHERE realized_net_savings IS NOT NULL
                              AND estimated_net_savings IS NOT NULL
                              AND ABS(estimated_net_savings) > 1
                        ) AS savings_error_percent,
                        AVG(realized_net_savings)
                            FILTER (
                                WHERE realized_net_savings IS NOT NULL
                            ) AS avg_realized_net_savings,
                        AVG(estimated_net_savings)
                            FILTER (
                                WHERE realized_net_savings IS NOT NULL
                            ) AS avg_projected_net_savings
                    FROM optimization_missions
                    WHERE status = 'Completed'
                      AND outcome_captured_at >= :window_start
                      AND outcome_captured_at < :window_end
                      AND (
                          CAST(:facility_id AS VARCHAR) IS NULL
                          OR facility_id =
                             CAST(:facility_id AS VARCHAR)
                      );
                    """
                ),
                {
                    "window_start": window_start,
                    "window_end": window_end,
                    "facility_id": facility_id,
                },
            ).mappings().one()
        return dict(row)

    @staticmethod
    def _governance(
        *,
        sample_size: int,
        duration_mae: float | None,
        sla_precision: float | None,
        sla_recall: float | None,
        drift_score: float,
        optimizer_error: float | None,
    ) -> dict[str, Any]:
        reasons: list[str] = []
        severe = 0
        watch = 0

        if sample_size < 100:
            reasons.append(
                f"Only {sample_size} completed prediction outcomes are available; at least 100 are preferred."
            )
            watch += 1

        if duration_mae is not None:
            if duration_mae > 10:
                reasons.append(
                    f"Turn-duration MAE is {duration_mae:.1f} minutes (>10 minute retraining threshold)."
                )
                severe += 1
            elif duration_mae > 8:
                reasons.append(
                    f"Turn-duration MAE is {duration_mae:.1f} minutes (>8 minute watch threshold)."
                )
                watch += 1

        if sla_recall is not None:
            if sla_recall < 0.60:
                reasons.append(
                    f"SLA-miss recall is {sla_recall:.1%} (<60% retraining threshold)."
                )
                severe += 1
            elif sla_recall < 0.70:
                reasons.append(
                    f"SLA-miss recall is {sla_recall:.1%} (<70% watch threshold)."
                )
                watch += 1

        if sla_precision is not None and sla_precision < 0.30:
            reasons.append(
                f"SLA-miss precision is {sla_precision:.1%} (<30% watch threshold)."
            )
            watch += 1

        if drift_score >= 1.0:
            reasons.append(
                f"Feature drift score is {drift_score:.2f} (>=1.00 retraining threshold)."
            )
            severe += 1
        elif drift_score >= 0.50:
            reasons.append(
                f"Feature drift score is {drift_score:.2f} (>=0.50 watch threshold)."
            )
            watch += 1

        if optimizer_error is not None:
            if optimizer_error > 75:
                reasons.append(
                    f"Optimizer savings projection error is {optimizer_error:.1f}% (>75%)."
                )
                severe += 1
            elif optimizer_error > 50:
                reasons.append(
                    f"Optimizer savings projection error is {optimizer_error:.1f}% (>50%)."
                )
                watch += 1

        retrain = severe >= 1 or watch >= 3
        health = (
            "Retrain Recommended"
            if retrain
            else "Watch"
            if watch > 0
            else "Healthy"
        )

        if not reasons:
            reasons.append(
                "Current accuracy, drift and optimizer-effectiveness signals are within governance thresholds."
            )

        return {
            "health_status": health,
            "retrain_recommended": retrain,
            "reasons": reasons,
        }

    def monitor(
        self,
        *,
        window_days: int = 30,
        facility_id: str | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        window_end = datetime.now(timezone.utc)
        window_start = window_end - timedelta(days=window_days)
        model_version = self._current_model_version()

        performance = self._performance_metrics(
            model_version=model_version,
            window_start=window_start,
            window_end=window_end,
            facility_id=facility_id,
        )
        drift = self._feature_drift(
            window_start=window_start,
            window_end=window_end,
            facility_id=facility_id,
        )
        optimizer = self._optimizer_effectiveness(
            window_start=window_start,
            window_end=window_end,
            facility_id=facility_id,
        )
        governance = self._governance(
            sample_size=int(performance.get("sample_size") or 0),
            duration_mae=(
                float(performance["duration_mae"])
                if performance.get("duration_mae") is not None
                else None
            ),
            sla_precision=performance.get("sla_precision"),
            sla_recall=performance.get("sla_recall"),
            drift_score=float(drift["score"]),
            optimizer_error=(
                float(optimizer["savings_error_percent"])
                if optimizer.get("savings_error_percent") is not None
                else None
            ),
        )

        result = {
            "model_version": model_version,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "window_days": window_days,
            "facility_id": facility_id,
            "health_status": governance["health_status"],
            "retrain_recommended": governance["retrain_recommended"],
            "reasons": governance["reasons"],
            "performance": performance,
            "feature_drift": drift,
            "optimizer_effectiveness": optimizer,
            "facility_performance": (
                self._facility_metrics(
                    model_version=model_version,
                    window_start=window_start,
                    window_end=window_end,
                )
                if facility_id is None
                else []
            ),
            "governance_thresholds": {
                "duration_mae_watch": 8,
                "duration_mae_retrain": 10,
                "sla_recall_watch": 0.70,
                "sla_recall_retrain": 0.60,
                "sla_precision_watch": 0.30,
                "feature_drift_watch": 0.50,
                "feature_drift_retrain": 1.00,
                "optimizer_error_watch_percent": 50,
                "optimizer_error_retrain_percent": 75,
                "minimum_preferred_sample": 100,
            },
        }

        if persist:
            self._persist_snapshot(result)

        # Bootstrap the current production registry lazily.
        try:
            self.register_current_model(status="Production")
        except RuntimeError:
            pass

        return result

    def _persist_snapshot(
        self,
        result: dict[str, Any],
    ) -> None:
        performance = result["performance"]
        optimizer = result["optimizer_effectiveness"]
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO ml_monitoring_snapshots (
                        model_version,
                        window_start,
                        window_end,
                        sample_size,
                        health_status,
                        retrain_recommended,
                        turn_duration_mae,
                        turn_duration_rmse,
                        arrival_mae,
                        sla_precision,
                        sla_recall,
                        sla_f2,
                        false_positives,
                        false_negatives,
                        feature_drift_score,
                        optimizer_savings_error_percent,
                        reasons,
                        metrics
                    ) VALUES (
                        :model_version,
                        CAST(:window_start AS TIMESTAMPTZ),
                        CAST(:window_end AS TIMESTAMPTZ),
                        :sample_size,
                        :health_status,
                        :retrain_recommended,
                        :turn_duration_mae,
                        :turn_duration_rmse,
                        :arrival_mae,
                        :sla_precision,
                        :sla_recall,
                        :sla_f2,
                        :false_positives,
                        :false_negatives,
                        :feature_drift_score,
                        :optimizer_savings_error_percent,
                        CAST(:reasons AS JSONB),
                        CAST(:metrics AS JSONB)
                    );
                    """
                ),
                {
                    "model_version": result["model_version"],
                    "window_start": result["window_start"],
                    "window_end": result["window_end"],
                    "sample_size": int(
                        performance.get("sample_size") or 0
                    ),
                    "health_status": result["health_status"],
                    "retrain_recommended": result["retrain_recommended"],
                    "turn_duration_mae": performance.get("duration_mae"),
                    "turn_duration_rmse": performance.get("duration_rmse"),
                    "arrival_mae": performance.get("arrival_mae"),
                    "sla_precision": performance.get("sla_precision"),
                    "sla_recall": performance.get("sla_recall"),
                    "sla_f2": performance.get("sla_f2"),
                    "false_positives": int(
                        performance.get("false_positive") or 0
                    ),
                    "false_negatives": int(
                        performance.get("false_negative") or 0
                    ),
                    "feature_drift_score": result["feature_drift"]["score"],
                    "optimizer_savings_error_percent": optimizer.get(
                        "savings_error_percent"
                    ),
                    "reasons": json.dumps(result["reasons"]),
                    "metrics": json.dumps(result, default=str),
                },
            )

    def history(
        self,
        *,
        model_version: str | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        snapshot_id,
                        model_version,
                        window_start,
                        window_end,
                        sample_size,
                        health_status,
                        retrain_recommended,
                        turn_duration_mae,
                        arrival_mae,
                        sla_precision,
                        sla_recall,
                        feature_drift_score,
                        optimizer_savings_error_percent,
                        reasons,
                        created_at
                    FROM ml_monitoring_snapshots
                    WHERE (
                        CAST(:model_version AS VARCHAR) IS NULL
                        OR model_version =
                           CAST(:model_version AS VARCHAR)
                    )
                    ORDER BY created_at DESC
                    LIMIT :limit;
                    """
                ),
                {
                    "model_version": model_version,
                    "limit": limit,
                },
            ).mappings().all()
        return [dict(row) for row in rows]
