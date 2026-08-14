# Release 2.0 — Sprint 2: Predictive Intelligence

## Added

- AI Prediction Center with six explainable forecast cards.
- 60-minute SLA-miss forecast.
- Dock-congestion and carrier-delay forecasts.
- Recovery-probability, detention-cost, and turn-time forecasts.
- Confidence indicators, trend direction, primary factor, and mitigation for every forecast.
- Clickable portfolio risk matrix integrated with appointment filters.
- Compact predicted-versus-actual forecast history.
- Live What-If integration: scenario results regenerate executive and predictive intelligence.

## Backend

- Added `app/services/prediction_service.py`.
- Added `prediction_center` to `GET /api/dashboard`.
- Added dock context to high-risk appointment data.
- Rebuilds predictions after dashboard What-If simulations.

## Frontend

- Added `components/PredictionCenter/PredictionCenter.tsx`.
- Added Prediction Center TypeScript contracts.
- Integrated the Prediction Center below Executive Intelligence.
- Added responsive enterprise styling.

## Validation

- `python -m compileall -q backend/app`
- `npx tsc --noEmit`

No database migration is required.
