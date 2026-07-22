# Database Migrations

Migration files are applied in numeric order.

## Current migrations

- `001_add_operational_columns.sql`
  - Adds ETA and actual-arrival timestamps
  - Adds predicted processing duration
  - Adds dock assignment
  - Adds appointment SLA duration
  - Adds detention cost per hour

## Apply a migration

From the project root:

```powershell
Get-Content .\database\migrations\<migration-file>.sql |
    docker exec -i turn-time-postgres `
    psql -U turntime -d turn_time