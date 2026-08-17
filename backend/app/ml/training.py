from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    classification_report,
    confusion_matrix,
    fbeta_score,
    mean_absolute_error,
    mean_squared_error,
    median_absolute_error,
    precision_recall_curve,
    r2_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.ml.features import (
    CATEGORICAL_FEATURES,
    MODEL_FEATURES,
    NUMERIC_FEATURES,
    prepare_features,
)


# The product-history CTE is intentionally chronological. Each training day
# receives product/facility performance accumulated through PREVIOUS days only.
# That prevents the model from learning from the future.
TRAINING_QUERY = """
WITH completed AS (
    SELECT
        a.appt_id,
        a.scheduled_time,
        DATE(a.scheduled_time) AS operation_date,
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
        a.actual_arrival_delay_minutes,
        a.actual_loading_duration_minutes,
        a.actual_sla_missed
    FROM appointments a
    WHERE a.appt_id LIKE 'DEMO%'
      AND a.status = 'Completed'
      AND a.actual_arrival_delay_minutes IS NOT NULL
      AND a.actual_loading_duration_minutes IS NOT NULL
      AND a.actual_sla_missed IS NOT NULL
),
product_daily AS (
    SELECT
        a.facility_id,
        ap.product_id,
        DATE(a.scheduled_time) AS operation_date,
        COUNT(*)::numeric AS samples,
        SUM(
            (
                a.actual_loading_duration_minutes::numeric
                / NULLIF(a.pallet_count, 0)
            )
            * GREATEST(ap.pallet_count, 1)
        ) AS weighted_minutes_sum,
        SUM(GREATEST(ap.pallet_count, 1))::numeric AS pallet_weight,
        SUM(
            CASE
                WHEN a.actual_sla_missed = FALSE THEN 1
                ELSE 0
            END
        )::numeric AS sla_successes,
        SUM(r.actual_loaders)::numeric AS loaders_sum,
        SUM(r.actual_forklifts)::numeric AS forklifts_sum
    FROM appointment_products ap
    JOIN appointments a
      ON a.appt_id = ap.appt_id
    JOIN appointment_resource_allocations r
      ON r.appt_id = a.appt_id
    WHERE a.appt_id LIKE 'DEMO%'
      AND a.status = 'Completed'
      AND a.actual_loading_duration_minutes IS NOT NULL
      AND a.scheduled_time IS NOT NULL
    GROUP BY
        a.facility_id,
        ap.product_id,
        DATE(a.scheduled_time)
),
product_history AS (
    SELECT
        facility_id,
        product_id,
        operation_date,
        SUM(weighted_minutes_sum) OVER history_window
            / NULLIF(
                SUM(pallet_weight) OVER history_window,
                0
            ) AS hist_minutes_per_pallet,
        SUM(sla_successes) OVER history_window
            / NULLIF(
                SUM(samples) OVER history_window,
                0
            ) AS hist_sla_success_rate,
        SUM(loaders_sum) OVER history_window
            / NULLIF(
                SUM(samples) OVER history_window,
                0
            ) AS hist_avg_loaders,
        SUM(forklifts_sum) OVER history_window
            / NULLIF(
                SUM(samples) OVER history_window,
                0
            ) AS hist_avg_forklifts
    FROM product_daily
    WINDOW history_window AS (
        PARTITION BY facility_id, product_id
        ORDER BY operation_date
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    )
),
appointment_product_features AS (
    SELECT
        c.appt_id,
        SUM(
            COALESCE(ph.hist_minutes_per_pallet, pop.base_minutes_per_pallet)
            * GREATEST(ap.pallet_count, 1)
        )
            / NULLIF(
                SUM(GREATEST(ap.pallet_count, 1)),
                0
            ) AS product_hist_minutes_per_pallet,
        SUM(
            COALESCE(ph.hist_sla_success_rate, 0.95)
            * GREATEST(ap.pallet_count, 1)
        )
            / NULLIF(
                SUM(GREATEST(ap.pallet_count, 1)),
                0
            ) AS product_hist_sla_success_rate,
        SUM(
            COALESCE(ph.hist_avg_loaders, 1.5)
            * GREATEST(ap.pallet_count, 1)
        )
            / NULLIF(
                SUM(GREATEST(ap.pallet_count, 1)),
                0
            ) AS product_hist_avg_loaders,
        SUM(
            COALESCE(ph.hist_avg_forklifts, 1.0)
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
    FROM completed c
    JOIN appointment_products ap
      ON ap.appt_id = c.appt_id
    JOIN product_operational_profiles pop
      ON pop.product_id = ap.product_id
    LEFT JOIN product_history ph
      ON ph.facility_id = c.facility_id
     AND ph.product_id = ap.product_id
     AND ph.operation_date = c.operation_date
    GROUP BY c.appt_id
)
SELECT
    c.*,

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

    apf.product_hist_minutes_per_pallet,
    apf.product_hist_sla_success_rate,
    apf.product_hist_avg_loaders,
    apf.product_hist_avg_forklifts,
    apf.product_complexity_factor,
    apf.product_forklift_intensity,
    apf.product_staging_intensity

FROM completed c
JOIN appointment_resource_allocations r
  ON r.appt_id = c.appt_id
JOIN facility_operational_profiles fop
  ON fop.facility_id = c.facility_id
LEFT JOIN carrier_operational_profiles cop
  ON cop.carrier_id = c.carrier_id
LEFT JOIN customer_operational_profiles cup
  ON cup.customer_id = c.customer_id
LEFT JOIN appointment_product_features apf
  ON apf.appt_id = c.appt_id
ORDER BY c.scheduled_time, c.appt_id;
"""


def _preprocessor() -> ColumnTransformer:
    categorical = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="constant",
                    fill_value="UNKNOWN",
                ),
            ),
            (
                "encoder",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                ),
            ),
        ]
    )

    numeric = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy="median"),
            )
        ]
    )

    return ColumnTransformer(
        transformers=[
            (
                "categorical",
                categorical,
                CATEGORICAL_FEATURES,
            ),
            (
                "numeric",
                numeric,
                NUMERIC_FEATURES,
            ),
        ],
        remainder="drop",
    )


def _chronological_split(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame = frame.sort_values(
        ["scheduled_time", "appt_id"]
    ).reset_index(drop=True)

    count = len(frame)
    train_end = max(1, int(count * 0.70))
    validation_end = max(
        train_end + 1,
        int(count * 0.85),
    )
    validation_end = min(validation_end, count - 1)

    return (
        frame.iloc[:train_end],
        frame.iloc[train_end:validation_end],
        frame.iloc[validation_end:],
    )


def _regression_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocessor", _preprocessor()),
            (
                "model",
                HistGradientBoostingRegressor(
                    learning_rate=0.06,
                    max_iter=320,
                    max_leaf_nodes=31,
                    min_samples_leaf=35,
                    l2_regularization=0.35,
                    random_state=42,
                ),
            ),
        ]
    )


def _classification_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocessor", _preprocessor()),
            (
                "model",
                HistGradientBoostingClassifier(
                    learning_rate=0.055,
                    max_iter=340,
                    max_leaf_nodes=31,
                    min_samples_leaf=35,
                    l2_regularization=0.45,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )


def _regression_metrics(
    truth: pd.Series,
    prediction: np.ndarray,
    *,
    tolerances: tuple[int, ...],
) -> dict[str, Any]:
    truth_array = truth.to_numpy(dtype=float)
    error = np.abs(truth_array - prediction)

    metrics: dict[str, Any] = {
        "mae": round(
            float(mean_absolute_error(truth_array, prediction)),
            3,
        ),
        "median_absolute_error": round(
            float(median_absolute_error(truth_array, prediction)),
            3,
        ),
        "rmse": round(
            float(
                mean_squared_error(
                    truth_array,
                    prediction,
                )
                ** 0.5
            ),
            3,
        ),
        "r2": round(
            float(r2_score(truth_array, prediction)),
            4,
        ),
    }

    for tolerance in tolerances:
        metrics[f"within_{tolerance}_minutes_percent"] = round(
            float((error <= tolerance).mean() * 100),
            2,
        )

    return metrics


def _best_sla_threshold(
    truth: pd.Series,
    probability: np.ndarray,
) -> dict[str, float]:
    precision, recall, thresholds = precision_recall_curve(
        truth.astype(int),
        probability,
    )

    best_threshold = 0.50
    best_f2 = -1.0
    best_precision = 0.0
    best_recall = 0.0

    for index, threshold in enumerate(thresholds):
        p = float(precision[index])
        r = float(recall[index])

        if p <= 0 and r <= 0:
            continue

        denominator = (4.0 * p) + r
        f2 = (
            (5.0 * p * r) / denominator
            if denominator > 0
            else 0.0
        )

        # Operations favors recall, but avoid thresholds that
        # generate nearly indiscriminate alerts.
        if r >= 0.70 and p >= 0.08 and f2 > best_f2:
            best_threshold = float(threshold)
            best_f2 = f2
            best_precision = p
            best_recall = r

    if best_f2 < 0:
        scores = []
        for index, threshold in enumerate(thresholds):
            p = float(precision[index])
            r = float(recall[index])
            denominator = (4.0 * p) + r
            f2 = (
                (5.0 * p * r) / denominator
                if denominator > 0
                else 0.0
            )
            scores.append((f2, float(threshold), p, r))

        if scores:
            (
                best_f2,
                best_threshold,
                best_precision,
                best_recall,
            ) = max(scores, key=lambda item: item[0])

    return {
        "threshold": round(best_threshold, 4),
        "validation_f2": round(best_f2, 4),
        "validation_precision": round(best_precision, 4),
        "validation_recall": round(best_recall, 4),
    }


def _classification_metrics(
    truth: pd.Series,
    probability: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    truth_int = truth.astype(int)
    prediction = (probability >= threshold).astype(int)

    return {
        "roc_auc": round(
            float(roc_auc_score(truth_int, probability)),
            4,
        ),
        "pr_auc": round(
            float(
                average_precision_score(
                    truth_int,
                    probability,
                )
            ),
            4,
        ),
        "brier_score": round(
            float(
                brier_score_loss(
                    truth_int,
                    probability,
                )
            ),
            5,
        ),
        "threshold": round(float(threshold), 4),
        "f2": round(
            float(
                fbeta_score(
                    truth_int,
                    prediction,
                    beta=2,
                    zero_division=0,
                )
            ),
            4,
        ),
        "confusion_matrix": confusion_matrix(
            truth_int,
            prediction,
        ).tolist(),
        "classification_report": classification_report(
            truth_int,
            prediction,
            output_dict=True,
            zero_division=0,
        ),
    }


def train_models(
    engine: Engine,
    artifact_dir: Path,
) -> dict[str, Any]:
    artifact_dir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_sql_query(
        text(TRAINING_QUERY),
        engine,
    )

    if len(raw) < 1000:
        raise RuntimeError(
            f"Only {len(raw)} completed appointments are available. "
            "ML-v2 requires at least 1,000."
        )

    if raw["actual_sla_missed"].nunique(dropna=True) < 2:
        raise RuntimeError(
            "The SLA target contains only one class."
        )

    train, validation, test = _chronological_split(raw)

    X_train = prepare_features(train)
    X_validation = prepare_features(validation)
    X_test = prepare_features(test)

    y_arrival_train = (
        train["actual_arrival_delay_minutes"].astype(float)
    )
    y_arrival_validation = (
        validation["actual_arrival_delay_minutes"].astype(float)
    )
    y_arrival_test = (
        test["actual_arrival_delay_minutes"].astype(float)
    )

    y_duration_train = (
        train["actual_loading_duration_minutes"].astype(float)
    )
    y_duration_validation = (
        validation["actual_loading_duration_minutes"].astype(float)
    )
    y_duration_test = (
        test["actual_loading_duration_minutes"].astype(float)
    )

    y_sla_train = train["actual_sla_missed"].astype(int)
    y_sla_validation = (
        validation["actual_sla_missed"].astype(int)
    )
    y_sla_test = test["actual_sla_missed"].astype(int)

    arrival_pipeline = _regression_pipeline()
    duration_pipeline = _regression_pipeline()
    sla_pipeline = _classification_pipeline()

    arrival_pipeline.fit(X_train, y_arrival_train)
    duration_pipeline.fit(X_train, y_duration_train)
    sla_pipeline.fit(X_train, y_sla_train)

    arrival_validation_predictions = np.clip(
        arrival_pipeline.predict(X_validation),
        -120.0,
        720.0,
    )
    duration_validation_predictions = np.maximum(
        1.0,
        duration_pipeline.predict(X_validation),
    )
    sla_validation_probabilities = np.clip(
        sla_pipeline.predict_proba(X_validation)[:, 1],
        0.0001,
        0.9999,
    )

    threshold_info = _best_sla_threshold(
        y_sla_validation,
        sla_validation_probabilities,
    )
    sla_threshold = float(threshold_info["threshold"])

    arrival_test_predictions = np.clip(
        arrival_pipeline.predict(X_test),
        -120.0,
        720.0,
    )
    duration_test_predictions = np.maximum(
        1.0,
        duration_pipeline.predict(X_test),
    )
    sla_test_probabilities = np.clip(
        sla_pipeline.predict_proba(X_test)[:, 1],
        0.0001,
        0.9999,
    )

    # Baselines must be beaten before we call v2 an improvement.
    eta_baseline = (
        (
            pd.to_datetime(
                test["estimated_arrival_time"],
                errors="coerce",
            )
            - pd.to_datetime(
                test["scheduled_time"],
                errors="coerce",
            )
        )
        .dt.total_seconds()
        .div(60)
        .fillna(0.0)
        .clip(-120, 720)
        .to_numpy(dtype=float)
    )

    duration_baseline_value = float(
        y_duration_train.median()
    )
    duration_baseline = np.full(
        len(y_duration_test),
        duration_baseline_value,
        dtype=float,
    )

    arrival_metrics = _regression_metrics(
        y_arrival_test,
        arrival_test_predictions,
        tolerances=(5, 10, 15),
    )
    duration_metrics = _regression_metrics(
        y_duration_test,
        duration_test_predictions,
        tolerances=(10, 15, 20),
    )
    sla_metrics = _classification_metrics(
        y_sla_test,
        sla_test_probabilities,
        sla_threshold,
    )

    arrival_baseline_metrics = _regression_metrics(
        y_arrival_test,
        eta_baseline,
        tolerances=(5, 10, 15),
    )
    duration_baseline_metrics = _regression_metrics(
        y_duration_test,
        duration_baseline,
        tolerances=(10, 15, 20),
    )

    test_prevalence = float(y_sla_test.mean())

    promotion_checks = {
        "arrival_beats_eta_mae": (
            arrival_metrics["mae"]
            < arrival_baseline_metrics["mae"]
        ),
        "duration_beats_median_mae": (
            duration_metrics["mae"]
            < duration_baseline_metrics["mae"]
        ),
        "sla_pr_auc_above_prevalence_3x": (
            sla_metrics["pr_auc"]
            >= max(0.10, test_prevalence * 3.0)
        ),
        "sla_positive_recall_at_least_70_percent": (
            sla_metrics["classification_report"]
            .get("1", {})
            .get("recall", 0.0)
            >= 0.70
        ),
    }
    promotion_checks["recommended_for_promotion"] = all(
        promotion_checks.values()
    )

    model_version = (
        "warehouse-ml-v2-"
        + datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    )

    joblib.dump(
        arrival_pipeline,
        artifact_dir / "arrival_delay_pipeline.joblib",
    )
    joblib.dump(
        duration_pipeline,
        artifact_dir / "turn_time_pipeline.joblib",
    )
    joblib.dump(
        sla_pipeline,
        artifact_dir / "sla_miss_pipeline.joblib",
    )

    metadata: dict[str, Any] = {
        "model_version": model_version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_scope": (
            "ML Dataset v2.0; chronological warehouse history; "
            "pre-arrival/planning features only"
        ),
        "algorithm": {
            "arrival_delay": "HistGradientBoostingRegressor",
            "turn_duration": "HistGradientBoostingRegressor",
            "sla_miss": "HistGradientBoostingClassifier",
        },
        "rows": {
            "total": len(raw),
            "train": len(train),
            "validation": len(validation),
            "test": len(test),
        },
        "date_ranges": {
            "train": [
                str(train["scheduled_time"].min()),
                str(train["scheduled_time"].max()),
            ],
            "validation": [
                str(validation["scheduled_time"].min()),
                str(validation["scheduled_time"].max()),
            ],
            "test": [
                str(test["scheduled_time"].min()),
                str(test["scheduled_time"].max()),
            ],
        },
        "targets": {
            "arrival_delay": "actual_arrival_delay_minutes",
            "turn_duration": "actual_loading_duration_minutes",
            "sla_miss": "actual_sla_missed",
        },
        "features": MODEL_FEATURES,
        "sla_decision_threshold": sla_threshold,
        "threshold_selection": threshold_info,
        "metrics": {
            "arrival_delay": arrival_metrics,
            "turn_duration": duration_metrics,
            "sla_miss": sla_metrics,
        },
        "baselines": {
            "arrival_eta": arrival_baseline_metrics,
            "turn_duration_train_median": {
                "median_minutes": round(
                    duration_baseline_value,
                    2,
                ),
                **duration_baseline_metrics,
            },
            "sla_test_prevalence_percent": round(
                test_prevalence * 100,
                3,
            ),
        },
        "class_balance": {
            "overall_sla_miss_rate_percent": round(
                float(
                    raw["actual_sla_missed"]
                    .astype(int)
                    .mean()
                    * 100
                ),
                3,
            )
        },
        "promotion_checks": promotion_checks,
    }

    (
        artifact_dir / "model_metadata.json"
    ).write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    return metadata
