from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.ml.model_service import WarehouseModelService

SCORING_QUERY = """
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
    a.surge_indicator
FROM appointments a
WHERE a.status IN ('Scheduled', 'Arrived', 'Waiting', 'In Progress')
ORDER BY a.scheduled_time, a.appt_id;
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


def score_current_appointments(engine: Engine, artifact_dir: Path) -> dict[str, Any]:
    raw = pd.read_sql_query(text(SCORING_QUERY), engine)
    if raw.empty:
        return {"scored": 0, "message": "No active appointments were available to score."}
    service = WarehouseModelService(artifact_dir)
    scored = service.predict(raw)
    records = []
    for row in scored.to_dict(orient="records"):
        predicted_arrival = row.get("estimated_arrival_time")
        if pd.isna(predicted_arrival):
            predicted_arrival = None
        records.append({
            "appt_id": row["appt_id"],
            "predicted_arrival_time": predicted_arrival,
            "predicted_delay_minutes": int(row["predicted_delay_minutes"]),
            "predicted_duration_minutes": int(row["predicted_duration_minutes"]),
            "sla_miss_probability": round(float(row["sla_miss_probability"]), 4),
            "sla_recovery_probability": round(float(row["sla_recovery_probability"]), 4),
            "turn_risk_score": int(row["turn_risk_score"]),
            "predicted_missed": bool(row["predicted_missed"]),
            "model_version": row["model_version"],
        })
    with engine.begin() as connection:
        connection.execute(text(INSERT_QUERY), records)
    return {
        "scored": len(records),
        "model_version": records[0]["model_version"],
        "predicted_misses": sum(1 for row in records if row["predicted_missed"]),
    }
