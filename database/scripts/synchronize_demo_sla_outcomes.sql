-- Synchronize stored SLA flags with the canonical completed-outcome rule.
-- Run once after deploying the repository changes.

BEGIN;

UPDATE appointments
SET actual_sla_missed = (actual_turn_time_minutes > sla_minutes)
WHERE appt_id LIKE 'DEMO%'
  AND status = 'Completed'
  AND actual_turn_time_minutes IS NOT NULL;

COMMIT;

-- Verification: these should both return zero.
SELECT COUNT(*) AS false_recoveries
FROM appointments
WHERE appt_id LIKE 'DEMO%'
  AND status = 'Completed'
  AND actual_turn_time_minutes > sla_minutes
  AND actual_sla_missed = FALSE;

SELECT COUNT(*) AS false_misses
FROM appointments
WHERE appt_id LIKE 'DEMO%'
  AND status = 'Completed'
  AND actual_turn_time_minutes <= sla_minutes
  AND actual_sla_missed = TRUE;
