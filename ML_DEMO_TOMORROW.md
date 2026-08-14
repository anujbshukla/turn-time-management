# ML Demo Setup

This release trains two real scikit-learn models from completed appointments:

- `HistGradientBoostingRegressor` predicts turn time.
- `HistGradientBoostingClassifier` predicts SLA-miss probability.

The dataset is synthetic, so present this as a trained proof-of-concept model.

## Run once before the demo

From `backend` with PostgreSQL and the virtual environment active:

```powershell
python scripts/train_and_score_ml.py
```

Or use Swagger:

```text
POST /api/ml/train-and-score
```

Verify:

```text
GET /api/ml/status
```

The scoring process writes a new latest row for active appointments into
`appointment_predictions`. Existing dashboard, table, drawer, prediction center,
What-If engine and Copilots already read the latest prediction row, so they use
ML outputs without frontend changes.

## Demo proof query

```sql
SELECT
    appt_id,
    predicted_duration_minutes,
    sla_miss_probability,
    turn_risk_score,
    predicted_missed,
    model_version,
    generated_at
FROM appointment_predictions
WHERE model_version LIKE 'warehouse-ml-v1-%'
ORDER BY generated_at DESC
LIMIT 20;
```

## Model metrics

Metrics and provenance are stored in:

```text
backend/model_artifacts/model_metadata.json
```
