from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.ml.features import CATEGORICAL_FEATURES, MODEL_FEATURES, NUMERIC_FEATURES, prepare_features

TRAINING_QUERY = """
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
    a.actual_turn_time_minutes,
    a.actual_sla_missed
FROM appointments a
WHERE a.status = 'Completed'
  AND a.actual_turn_time_minutes IS NOT NULL
  AND a.actual_sla_missed IS NOT NULL
ORDER BY a.scheduled_time, a.appt_id;
"""


def _preprocessor() -> ColumnTransformer:
    categorical = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "encoder",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
            ),
        ]
    )
    numeric = Pipeline(
        steps=[("imputer", SimpleImputer(strategy="median"))]
    )
    return ColumnTransformer(
        transformers=[
            ("categorical", categorical, CATEGORICAL_FEATURES),
            ("numeric", numeric, NUMERIC_FEATURES),
        ],
        remainder="drop",
    )


def _chronological_split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame = frame.sort_values(["scheduled_time", "appt_id"]).reset_index(drop=True)
    count = len(frame)
    train_end = max(1, int(count * 0.70))
    validation_end = max(train_end + 1, int(count * 0.85))
    validation_end = min(validation_end, count - 1)
    return frame.iloc[:train_end], frame.iloc[train_end:validation_end], frame.iloc[validation_end:]


def train_models(engine: Engine, artifact_dir: Path) -> dict[str, Any]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    raw = pd.read_sql_query(text(TRAINING_QUERY), engine)

    if len(raw) < 100:
        raise RuntimeError(
            f"Only {len(raw)} completed appointments are available. At least 100 are required."
        )
    if raw["actual_sla_missed"].nunique(dropna=True) < 2:
        raise RuntimeError("The SLA target contains only one class; both misses and non-misses are required.")

    train, validation, test = _chronological_split(raw)
    if test.empty or validation.empty:
        raise RuntimeError("The chronological split produced an empty validation or test set.")

    X_train = prepare_features(train)
    X_validation = prepare_features(validation)
    X_test = prepare_features(test)

    y_turn_train = train["actual_turn_time_minutes"].astype(float)
    y_turn_test = test["actual_turn_time_minutes"].astype(float)
    y_sla_train = train["actual_sla_missed"].astype(int)
    y_sla_test = test["actual_sla_missed"].astype(int)

    turn_pipeline = Pipeline(
        steps=[
            ("preprocessor", _preprocessor()),
            (
                "model",
                HistGradientBoostingRegressor(
                    learning_rate=0.08,
                    max_iter=220,
                    max_leaf_nodes=31,
                    l2_regularization=0.2,
                    random_state=42,
                ),
            ),
        ]
    )
    sla_pipeline = Pipeline(
        steps=[
            ("preprocessor", _preprocessor()),
            (
                "model",
                HistGradientBoostingClassifier(
                    learning_rate=0.08,
                    max_iter=220,
                    max_leaf_nodes=31,
                    l2_regularization=0.2,
                    random_state=42,
                ),
            ),
        ]
    )

    turn_pipeline.fit(X_train, y_turn_train)
    sla_pipeline.fit(X_train, y_sla_train)

    turn_predictions = np.maximum(1.0, turn_pipeline.predict(X_test))
    sla_probabilities = sla_pipeline.predict_proba(X_test)[:, 1]
    sla_predictions = (sla_probabilities >= 0.50).astype(int)

    regression_metrics = {
        "mae": round(float(mean_absolute_error(y_turn_test, turn_predictions)), 3),
        "rmse": round(float(mean_squared_error(y_turn_test, turn_predictions) ** 0.5), 3),
        "r2": round(float(r2_score(y_turn_test, turn_predictions)), 4),
        "within_15_minutes_percent": round(
            float((np.abs(y_turn_test.to_numpy() - turn_predictions) <= 15).mean() * 100), 2
        ),
    }
    classification_metrics = {
        "roc_auc": round(float(roc_auc_score(y_sla_test, sla_probabilities)), 4),
        "pr_auc": round(float(average_precision_score(y_sla_test, sla_probabilities)), 4),
        "confusion_matrix": confusion_matrix(y_sla_test, sla_predictions).tolist(),
        "classification_report": classification_report(
            y_sla_test, sla_predictions, output_dict=True, zero_division=0
        ),
    }

    model_version = f"warehouse-ml-v1-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    joblib.dump(turn_pipeline, artifact_dir / "turn_time_pipeline.joblib")
    joblib.dump(sla_pipeline, artifact_dir / "sla_miss_pipeline.joblib")

    metadata: dict[str, Any] = {
        "model_version": model_version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_scope": "synthetic warehouse appointments; pre-arrival features",
        "algorithm": {
            "turn_time": "HistGradientBoostingRegressor",
            "sla_miss": "HistGradientBoostingClassifier",
        },
        "rows": {
            "total": len(raw),
            "train": len(train),
            "validation": len(validation),
            "test": len(test),
        },
        "targets": {
            "turn_time": "actual_turn_time_minutes",
            "sla_miss": "actual_sla_missed",
        },
        "features": MODEL_FEATURES,
        "metrics": {
            "turn_time": regression_metrics,
            "sla_miss": classification_metrics,
        },
        "class_balance": {
            "sla_miss_rate_percent": round(float(raw["actual_sla_missed"].astype(int).mean() * 100), 2)
        },
    }
    (artifact_dir / "model_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata
