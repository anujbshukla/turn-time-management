from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.ml.model_service import WarehouseModelService


SCORING_QUERY = """
WITH product_mix AS (
    SELECT
        a.appt_id,
        SUM(
            COALESCE(
                ph.avg_minutes_per_pallet,
                pop.base_minutes_per_pallet
            )
            * GREATEST(ap.pallet_count, 1)
        )
            / NULLIF(
                SUM(GREATEST(ap.pallet_count, 1)),
                0
            ) AS product_hist_minutes_per_pallet,
        SUM(
            COALESCE(ph.sla_success_rate, 0.95)
            * GREATEST(ap.pallet_count, 1)
        )
            / NULLIF(
                SUM(GREATEST(ap.pallet_count, 1)),
                0
            ) AS product_hist_sla_success_rate,
        SUM(
            COALESCE(ph.avg_loaders, 1.5)
            * GREATEST(ap.pallet_count, 1)
        )
            / NULLIF(
                SUM(GREATEST(ap.pallet_count, 1)),
                0
            ) AS product_hist_avg_loaders,
        SUM(
            COALESCE(ph.avg_forklifts, 1.0)
            * GREATEST(ap.pallet_count, 1)
        )
            / NULLIF(
                SUM(GREATEST(ap.pallet_count, 1)),
                0
            ) AS product_hist_avg_forklifts,
        SUM(
            pop.handling_complexity_factor
            * GREATEST(ap.pallet_count, 1)
        )
            / NULLIF(
                SUM(GREATEST(ap.pallet_count, 1)),
                0
            ) AS product_complexity_factor,
        SUM(
            pop.forklift_intensity
            * GREATEST(ap.pallet_count, 1)
        )
            / NULLIF(
                SUM(GREATEST(ap.pallet_count, 1)),
                0
            ) AS product_forklift_intensity,
        SUM(
            pop.staging_intensity
            * GREATEST(ap.pallet_count, 1)
        )
            / NULLIF(
                SUM(GREATEST(ap.pallet_count, 1)),
                0
            ) AS product_staging_intensity
    FROM appointments a
    JOIN appointment_products ap
      ON ap.appt_id = a.appt_id
    JOIN product_operational_profiles pop
      ON pop.product_id = ap.product_id
    LEFT JOIN LATERAL (
        SELECT
            history.avg_minutes_per_pallet,
            history.avg_loaders,
            history.avg_forklifts,
            history.sla_success_rate
        FROM product_handling_history history
        WHERE history.product_id = ap.product_id
          AND history.facility_id = a.facility_id
          AND history.as_of_date <= DATE(a.scheduled_time)
        ORDER BY history.as_of_date DESC
        LIMIT 1
    ) ph ON TRUE
    WHERE a.appt_id LIKE 'DEMO%'
      AND (
          CAST(:appointment_id AS VARCHAR) IS NULL
          OR a.appt_id = CAST(:appointment_id AS VARCHAR)
      )
      AND (
          CAST(:facility_id AS VARCHAR) IS NULL
          OR a.facility_id = CAST(:facility_id AS VARCHAR)
      )
      AND (
          CAST(:active_only AS BOOLEAN) = FALSE
          OR a.status NOT IN ('Completed', 'Cancelled')
      )
    GROUP BY a.appt_id
)
SELECT
    a.appt_id,
    a.scheduled_time,
    a.estimated_arrival_time,
    a.facility_id,
    a.carrier_id,
    a.customer_id,
    a.assigned_dock_id,
    a.appointment_type,
    a.load_type,
    a.pallet_count,
    a.sku_count,
    a.total_weight,
    a.total_cube,
    a.priority,
    a.sla_minutes,
    a.detention_cost_per_hour,
    a.distance_band,
    a.traffic_severity,
    a.weather_severity,
    a.surge_indicator,

    r.planned_loaders,
    r.planned_forklifts,
    r.planned_staging_labor,
    r.queue_depth_at_arrival,
    r.dock_congestion_percent,
    r.labor_utilization_percent,
    r.forklift_utilization_percent,

    fop.weekday_base_volume
        AS facility_weekday_base_volume,
    fop.weekend_volume_factor
        AS facility_weekend_volume_factor,
    fop.dock_efficiency_factor
        AS facility_dock_efficiency_factor,
    fop.labor_efficiency_factor
        AS facility_labor_efficiency_factor,
    fop.congestion_sensitivity
        AS facility_congestion_sensitivity,
    fop.base_loader_capacity
        AS facility_base_loader_capacity,
    fop.base_forklift_capacity
        AS facility_base_forklift_capacity,

    cop.baseline_on_time_rate
        AS carrier_baseline_on_time_rate,
    cop.mean_delay_minutes
        AS carrier_mean_delay_minutes,
    cop.delay_stddev_minutes
        AS carrier_delay_stddev_minutes,
    cop.long_haul_penalty_minutes
        AS carrier_long_haul_penalty_minutes,

    cup.handling_complexity_factor
        AS customer_handling_complexity_factor,
    cup.typical_pallets
        AS customer_typical_pallets,
    cup.typical_skus
        AS customer_typical_skus,
    cup.inbound_share
        AS customer_inbound_share,
    cup.priority_bias
        AS customer_priority_bias,

    pm.product_hist_minutes_per_pallet,
    pm.product_hist_sla_success_rate,
    pm.product_hist_avg_loaders,
    pm.product_hist_avg_forklifts,
    pm.product_complexity_factor,
    pm.product_forklift_intensity,
    pm.product_staging_intensity

FROM appointments a
JOIN appointment_resource_allocations r
  ON r.appt_id = a.appt_id
JOIN facility_operational_profiles fop
  ON fop.facility_id = a.facility_id
LEFT JOIN carrier_operational_profiles cop
  ON cop.carrier_id = a.carrier_id
LEFT JOIN customer_operational_profiles cup
  ON cup.customer_id = a.customer_id
LEFT JOIN product_mix pm
  ON pm.appt_id = a.appt_id

WHERE a.appt_id LIKE 'DEMO%'
  AND (
      CAST(:appointment_id AS VARCHAR) IS NULL
      OR a.appt_id = CAST(:appointment_id AS VARCHAR)
  )
  AND (
      CAST(:facility_id AS VARCHAR) IS NULL
      OR a.facility_id = CAST(:facility_id AS VARCHAR)
  )
  AND (
      CAST(:active_only AS BOOLEAN) = FALSE
      OR a.status NOT IN ('Completed', 'Cancelled')
  )
ORDER BY a.scheduled_time, a.appt_id;
"""


DELETE_EXISTING_VERSION_QUERY = """
DELETE FROM appointment_predictions
WHERE model_version = :model_version
  AND appt_id = ANY(:appt_ids);
"""


INSERT_QUERY = """
INSERT INTO appointment_predictions (
    appt_id,
    predicted_arrival_time,
    predicted_delay_minutes,
    predicted_duration_minutes,
    sla_miss_probability,
    sla_recovery_probability,
    turn_risk_score,
    predicted_missed,
    model_version,
    generated_at
) VALUES (
    :appt_id,
    :predicted_arrival_time,
    :predicted_delay_minutes,
    :predicted_duration_minutes,
    :sla_miss_probability,
    :sla_recovery_probability,
    :turn_risk_score,
    :predicted_missed,
    :model_version,
    NOW()
);
"""


def load_scoring_frame(
    engine: Engine,
    *,
    appointment_id: str | None = None,
    facility_id: str | None = None,
    active_only: bool = True,
) -> pd.DataFrame:
    """Load the exact ML-v2 feature row(s) used by production scoring.

    Reusing this query for batch scoring, appointment create/update and
    What-If prevents feature skew between training-time integration paths.
    """
    return pd.read_sql_query(
        text(SCORING_QUERY),
        engine,
        params={
            "appointment_id": appointment_id,
            "facility_id": facility_id,
            "active_only": active_only,
        },
    )


def score_current_appointments(
    engine: Engine,
    artifact_dir: Path,
) -> dict[str, Any]:
    raw = load_scoring_frame(
        engine,
        active_only=True,
    )

    if raw.empty:
        return {
            "scored": 0,
            "message": (
                "No active/future appointments were "
                "available to score."
            ),
        }

    service = WarehouseModelService(artifact_dir)
    scored = service.predict(raw)

    records = []
    for row in scored.to_dict(orient="records"):
        predicted_arrival = row.get(
            "predicted_arrival_time"
        )

        if pd.isna(predicted_arrival):
            predicted_arrival = None

        records.append(
            {
                "appt_id": row["appt_id"],
                "predicted_arrival_time": predicted_arrival,
                "predicted_delay_minutes": int(
                    row["predicted_delay_minutes"]
                ),
                "predicted_duration_minutes": int(
                    row["predicted_duration_minutes"]
                ),
                "sla_miss_probability": round(
                    float(row["sla_miss_probability"]),
                    4,
                ),
                "sla_recovery_probability": round(
                    float(
                        row[
                            "sla_recovery_probability"
                        ]
                    ),
                    4,
                ),
                "turn_risk_score": int(
                    row["turn_risk_score"]
                ),
                "predicted_missed": bool(
                    row["predicted_missed"]
                ),
                "model_version": row["model_version"],
            }
        )

    model_version = records[0]["model_version"]
    appointment_ids = [
        row["appt_id"] for row in records
    ]

    with engine.begin() as connection:
        # Keep historical model versions, but make scoring
        # idempotent for the current version.
        connection.execute(
            text(DELETE_EXISTING_VERSION_QUERY),
            {
                "model_version": model_version,
                "appt_ids": appointment_ids,
            },
        )
        connection.execute(
            text(INSERT_QUERY),
            records,
        )

    risk_counts = {
        "low": 0,
        "medium": 0,
        "high": 0,
        "critical": 0,
    }

    for row in records:
        score = row["turn_risk_score"]
        if score < 30:
            risk_counts["low"] += 1
        elif score < 60:
            risk_counts["medium"] += 1
        elif score < 80:
            risk_counts["high"] += 1
        else:
            risk_counts["critical"] += 1

    return {
        "scored": len(records),
        "model_version": model_version,
        "predicted_misses": sum(
            1
            for row in records
            if row["predicted_missed"]
        ),
        "risk_distribution": risk_counts,
    }
