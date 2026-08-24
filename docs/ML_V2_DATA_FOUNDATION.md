# ML v2 — Realistic Data Foundation

This phase replaces the old synthetic appointment population with a correlated operational dataset designed for ML training and multi-appointment optimization.

## Dataset horizon

Default generation anchored to the day the script is run:

- 150,000 historical appointments across the previous 365 days.
- Today plus the next 45 full future days (46 planning dates total).
- Approximately 22,000 scheduled/current appointments across the 10 facilities with the current default capacity profiles.
- 500 products, 100 customers, and 50 carriers.

The exact future appointment count varies because weekday/weekend, month-end, quarter-end, facility volume and random daily variability are modeled.

## Realism built into the generator

Values are correlated rather than sampled independently.

- Carrier reliability, distance, traffic and weather influence arrival delay.
- Product mix has product-specific handling time, complexity, staging intensity and forklift intensity.
- Customer history influences typical pallets, SKU count, SLA and handling complexity.
- Facility profiles influence daily volume, dock efficiency, labor efficiency and congestion sensitivity.
- Weekday/weekend, seasonal and period-end patterns affect appointment volumes.
- Appointment type influences scheduling distribution.
- Pallet volume, SKU complexity, load type, loaders, forklifts, staging labor, dock congestion and queue depth drive loading/turn duration.
- Labor/equipment shortages become more likely when utilization is high.
- SLA outcomes are calculated from the resulting operational timeline; they are not assigned independently.
- Historical recovery actions are generated only for a realistic subset of completed at-risk appointments and are correlated with outcome.
- Future appointments intentionally do not receive individual seeded recovery plans; the upcoming multi-appointment optimizer will create coordinated missions instead.

## New schema foundation

Migration `c7f2a6d9b210` adds:

- `facility_operational_profiles`
- `carrier_operational_profiles`
- `customer_operational_profiles`
- `product_operational_profiles`
- `appointment_resource_allocations`
- `product_handling_history`
- `optimization_missions`
- `optimization_mission_appointments`

`appointment_resource_allocations` captures the resource state that is essential for both ML and optimization: planned/actual loaders, planned/actual forklifts, staging labor, queue depth, dock congestion and resource utilization.

`product_handling_history` is rebuilt from completed historical turns so the ML-v2 feature pipeline can use previous product/facility handling behavior without using future outcomes.

## Safe execution

Create a branch and back up the current database before replacing data.

```powershell
git checkout -b feature/ml-v2-optimization

docker exec turn-time-postgres pg_dump -U turntime -d turn_time -Fc -f /tmp/turn_time_pre_mlv2.dump
docker cp turn-time-postgres:/tmp/turn_time_pre_mlv2.dump .\turn_time_pre_mlv2.dump
```

Activate the backend environment and migrate:

```powershell
cd C:\turn-time-management\backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

Preview the planned volumes without changing PostgreSQL:

```powershell
cd C:\turn-time-management
python database\seed\generate_demo_data.py --dry-run --anchor-date 2026-08-14
```

Expected default horizon for an August 14, 2026 anchor:

- historical: 2025-08-14 through 2026-08-13
- current/planning: 2026-08-14 through 2026-09-28

After reviewing the dry-run output, replace the current data:

```powershell
python database\seed\generate_demo_data.py --reset --anchor-date 2026-08-14
```

The script prints a validation report after generation, including historical/current/future row counts, average turn time, SLA miss rate, arrival delay, product-history profile count and historical recovery-plan count.

## Important ML rule

The temporary future predictions are written with model version `synthetic-baseline-v2` only so the existing application remains usable immediately after reseeding. They are not the final ML-v2 predictions. The next phase trains the Arrival, Turn Duration and SLA models on the newly generated historical outcomes and then writes new predictions with a separately versioned model identifier.

