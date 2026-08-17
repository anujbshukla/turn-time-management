# Final Release Validation

Run this validation before merging `feature/ml-v2-optimization` into `master`.

## Prerequisites

1. PostgreSQL/Docker is running.
2. The backend virtual environment is activated.
3. FastAPI is running on `http://127.0.0.1:8000`.
4. Vite is running on `http://localhost:5173` unless the frontend HTTP check is skipped.

## Run

From the repository root:

```powershell
.\scripts\final_release_validation.ps1
```

If Vite is not currently running, the production build is still validated and the HTTP smoke can be skipped:

```powershell
.\scripts\final_release_validation.ps1 -SkipFrontendHttp
```

A successful run validates:

- Git branch safety.
- Complete backend pytest suite.
- Alembic schema head.
- TypeScript + Vite production build.
- `/health`.
- `/health/readiness`.
- Live Appointment Queue and appointment details.
- ML model status and registry.
- ML monitoring/governance.
- Multi-appointment optimization preview.
- Mission-level What-If re-optimization.
- Action-effectiveness learning endpoint.
- Running frontend HTTP response.

The optimizer calls used by this script are preview/scenario calls only. The validation does **not** accept, start, complete, dismiss, or otherwise mutate a recovery mission.

## Release Gate

Do not merge to `master` until the script prints:

```text
FINAL RELEASE VALIDATION PASSED
```

A `Watch` ML governance state due solely to insufficient realized production outcomes is acceptable for the demo environment. A `Retrain Recommended` state should be reviewed before promotion.
