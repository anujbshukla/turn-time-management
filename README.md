# Completed outcome consistency fix

This update makes all completed-outcome views use one canonical rule:

- Recovered: `actual_turn_time_minutes <= sla_minutes`
- Missed SLA: `actual_turn_time_minutes > sla_minutes`
- Recovered with recommendations additionally requires an accepted/completed recommendation or an accepted recommendation action.

Updated files:

- `backend/app/repositories/appointment_repository.py`
- `backend/app/repositories/dashboard_repository.py`
- `database/scripts/synchronize_demo_sla_outcomes.sql`

After copying the files, run the SQL script once, restart FastAPI, and hard-refresh the frontend.
