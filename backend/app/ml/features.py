from __future__ import annotations

from typing import Final

import pandas as pd

CATEGORICAL_FEATURES: Final[list[str]] = [
    "facility_id",
    "carrier_id",
    "customer_id",
    "assigned_dock_id",
    "appointment_type",
    "load_type",
    "distance_band",
]

NUMERIC_FEATURES: Final[list[str]] = [
    "pallet_count",
    "sku_count",
    "total_weight",
    "total_cube",
    "priority",
    "sla_minutes",
    "detention_cost_per_hour",
    "estimated_delay_minutes",
    "traffic_severity",
    "weather_severity",
    "surge_indicator",
    "scheduled_hour",
    "scheduled_day_of_week",
    "scheduled_month",
    "is_weekend",
]

MODEL_FEATURES: Final[list[str]] = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def prepare_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a stable, leakage-free feature frame for training or inference."""
    result = frame.copy()

    scheduled = pd.to_datetime(result["scheduled_time"], errors="coerce")
    estimated_arrival = pd.to_datetime(
        result.get("estimated_arrival_time"), errors="coerce"
    )

    result["estimated_delay_minutes"] = (
        (estimated_arrival - scheduled).dt.total_seconds() / 60.0
    ).fillna(0.0).clip(lower=-120, upper=720)

    result["scheduled_hour"] = scheduled.dt.hour.fillna(0).astype(int)
    result["scheduled_day_of_week"] = scheduled.dt.dayofweek.fillna(0).astype(int)
    result["scheduled_month"] = scheduled.dt.month.fillna(1).astype(int)
    result["is_weekend"] = (result["scheduled_day_of_week"] >= 5).astype(int)
    result["surge_indicator"] = result["surge_indicator"].fillna(False).astype(int)

    for column in CATEGORICAL_FEATURES:
        if column not in result:
            result[column] = "UNKNOWN"
        result[column] = result[column].fillna("UNKNOWN").astype(str)

    for column in NUMERIC_FEATURES:
        if column not in result:
            result[column] = 0
        result[column] = pd.to_numeric(result[column], errors="coerce")

    return result[MODEL_FEATURES]
