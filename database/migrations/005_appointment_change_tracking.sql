BEGIN;

ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS original_scheduled_time TIMESTAMP,
    ADD COLUMN IF NOT EXISTS is_rescheduled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS reschedule_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS rescheduled_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS edit_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_edited_at TIMESTAMP;

UPDATE appointments
SET original_scheduled_time = scheduled_time
WHERE original_scheduled_time IS NULL;

COMMIT;
