# Live Appointment Queue Sorting

This update adds server-side sorting across the complete filtered appointment queue.

## Supported columns

- Appointment
- Customer
- Facility
- Carrier
- Scheduled
- Status (operational workflow order)
- Risk (numeric ML risk score)

## Interaction

Click a column header to cycle through:

1. Ascending
2. Descending
3. Default operational priority order

Sorting resets pagination to page 1 and remains active when moving between pages.

## Run

Restart the backend after merging the files:

```powershell
cd C:\turn-time-management\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Restart or refresh the frontend:

```powershell
cd C:\turn-time-management\frontend
npm run dev
```
