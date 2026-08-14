# Release 2.0 — Sprint 1: Executive Intelligence

## Added
- Executive AI briefing grounded in the current dashboard response.
- Explainable Warehouse Health Score (0–100).
- Live operating-status banner.
- Top-priority appointment panel with appointment drawer navigation.
- Critical-appointment focus action.
- Responsive enterprise styling.

## Backend
- Added `ExecutiveIntelligenceService`.
- Extended `GET /api/dashboard` with `executive_intelligence`.
- No database migration is required.

## Validation
- Python module compilation passed.
- TypeScript project compilation passed.

## Run
```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

```powershell
cd frontend
npm run dev
```
