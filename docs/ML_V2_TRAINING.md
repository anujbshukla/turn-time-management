# ML v2 — Training and Scoring

This phase replaces the original two-model baseline with three independently
trained models:

1. Arrival Delay v2 — regression of signed arrival delta in minutes.
2. Turn Duration v2 — regression of actual loading/service duration.
3. SLA Miss v2 — classification of the probability that the appointment misses SLA.

## What is different from v1

ML-v2 uses the new operational foundation:

- appointment pallets / SKUs / weight / cube
- planned loaders / forklifts / staging labor
- dock congestion and queue depth
- labor and forklift utilization
- facility efficiency and capacity profiles
- carrier reliability / delay profiles
- customer handling profiles
- previous product/facility handling performance
- product complexity / forklift / staging intensity
- traffic, weather, distance, appointment type and time features

The product handling feature used during historical training is calculated
chronologically. A training appointment can see previous days, not future
days. This avoids target leakage.

## Chronological split

Rows are sorted by scheduled time:

- oldest 70%: train
- next 15%: validation
- newest 15%: test

The validation period selects the operational SLA decision threshold. The test
period remains untouched until final evaluation.

## Promotion checks

A v2 model is not considered ready just because classification accuracy is
high. The metadata explicitly checks:

- Arrival Delay MAE beats the ETA-delay baseline.
- Turn Duration MAE beats the train-median baseline.
- SLA PR-AUC materially exceeds the positive-class prevalence.
- SLA-miss recall is at least 70%.

With a low SLA-miss prevalence, PR-AUC, recall, precision, F2 and the confusion
matrix are more useful than raw accuracy.

## Run

From the backend directory with the venv active:

```powershell
cd C:\turn-time-management\backend
python scripts\train_and_score_ml.py
```

Artifacts are written under:

```text
backend/model_artifacts/
```

Expected v2 artifacts:

```text
arrival_delay_pipeline.joblib
turn_time_pipeline.joblib
sla_miss_pipeline.joblib
model_metadata.json
```

The scoring step then writes a new prediction for every non-completed,
non-cancelled DEMO appointment, including the entire 45-day planning horizon.

## Important

Do not delete old model artifacts before the first v2 run. The training command
writes the new artifacts in place only after the models are successfully fit.
The Git branch and database backup remain the recovery path.
