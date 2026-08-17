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

BASE_NUMERIC_FEATURES: Final[list[str]] = [
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

RESOURCE_FEATURES: Final[list[str]] = [
    "planned_loaders",
    "planned_forklifts",
    "planned_staging_labor",
    "queue_depth_at_arrival",
    "dock_congestion_percent",
    "labor_utilization_percent",
    "forklift_utilization_percent",
]

FACILITY_FEATURES: Final[list[str]] = [
    "facility_weekday_base_volume",
    "facility_weekend_volume_factor",
    "facility_dock_efficiency_factor",
    "facility_labor_efficiency_factor",
    "facility_congestion_sensitivity",
    "facility_base_loader_capacity",
    "facility_base_forklift_capacity",
]

CARRIER_FEATURES: Final[list[str]] = [
    "carrier_baseline_on_time_rate",
    "carrier_mean_delay_minutes",
    "carrier_delay_stddev_minutes",
    "carrier_long_haul_penalty_minutes",
]

CUSTOMER_FEATURES: Final[list[str]] = [
    "customer_handling_complexity_factor",
    "customer_typical_pallets",
    "customer_typical_skus",
    "customer_inbound_share",
    "customer_priority_bias",
]

PRODUCT_HISTORY_FEATURES: Final[list[str]] = [
    "product_hist_minutes_per_pallet",
    "product_hist_sla_success_rate",
    "product_hist_avg_loaders",
    "product_hist_avg_forklifts",
    "product_complexity_factor",
    "product_forklift_intensity",
    "product_staging_intensity",
]

NUMERIC_FEATURES: Final[list[str]] = (
    BASE_NUMERIC_FEATURES
    + RESOURCE_FEATURES
    + FACILITY_FEATURES
    + CARRIER_FEATURES
    + CUSTOMER_FEATURES
    + PRODUCT_HISTORY_FEATURES
)

MODEL_FEATURES: Final[list[str]] = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def prepare_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Create the leakage-free feature matrix used by all ML-v2 models.

    Only fields known before or during operational planning are used here.
    Actual completion outcomes are targets and never become model inputs.
    """
    result = frame.copy()

    scheduled = pd.to_datetime(result["scheduled_time"], errors="coerce")
    estimated_arrival = pd.to_datetime(
        result.get("estimated_arrival_time"),
        errors="coerce",
    )

    result["estimated_delay_minutes"] = (
        (estimated_arrival - scheduled).dt.total_seconds() / 60.0
    ).fillna(0.0).clip(lower=-120, upper=720)

    result["scheduled_hour"] = scheduled.dt.hour.fillna(0).astype(int)
    result["scheduled_day_of_week"] = (
        scheduled.dt.dayofweek.fillna(0).astype(int)
    )
    result["scheduled_month"] = scheduled.dt.month.fillna(1).astype(int)
    result["is_weekend"] = (
        result["scheduled_day_of_week"] >= 5
    ).astype(int)
    result["surge_indicator"] = (
        result["surge_indicator"].fillna(False).astype(int)
    )

    for column in CATEGORICAL_FEATURES:
        if column not in result:
            result[column] = "UNKNOWN"
        result[column] = result[column].fillna("UNKNOWN").astype(str)

    for column in NUMERIC_FEATURES:
        if column not in result:
            result[column] = 0.0
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    return result[MODEL_FEATURES]
