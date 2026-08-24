BEGIN;

ALTER TABLE appointments
    ADD COLUMN IF NOT EXISTS origin_name VARCHAR(150),
    ADD COLUMN IF NOT EXISTS origin_city VARCHAR(100),
    ADD COLUMN IF NOT EXISTS origin_state VARCHAR(50),
    ADD COLUMN IF NOT EXISTS destination_name VARCHAR(150),
    ADD COLUMN IF NOT EXISTS destination_city VARCHAR(100),
    ADD COLUMN IF NOT EXISTS destination_state VARCHAR(50);

CREATE TABLE IF NOT EXISTS appointment_drivers (
    appt_id VARCHAR(50) PRIMARY KEY REFERENCES appointments(appt_id) ON DELETE CASCADE,
    driver_name VARCHAR(120),
    license_number VARCHAR(80),
    license_state VARCHAR(20),
    phone_number VARCHAR(40),
    tractor_number VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Demo-safe route defaults. Existing production values are never overwritten.
UPDATE appointments a
SET
    origin_name = COALESCE(a.origin_name, CASE WHEN a.appointment_type = 'Inbound' THEN COALESCE(a.customer_name, 'Supplier') ELSE 'Warehouse Facility' END),
    origin_city = COALESCE(a.origin_city, CASE WHEN a.appointment_type = 'Inbound' THEN 'Regional Origin' ELSE 'Local Facility' END),
    origin_state = COALESCE(a.origin_state, '—'),
    destination_name = COALESCE(a.destination_name, CASE WHEN a.appointment_type = 'Inbound' THEN 'Warehouse Facility' ELSE COALESCE(a.customer_name, 'Customer Destination') END),
    destination_city = COALESCE(a.destination_city, CASE WHEN a.appointment_type = 'Inbound' THEN 'Local Facility' ELSE 'Regional Destination' END),
    destination_state = COALESCE(a.destination_state, '—')
WHERE a.appt_id LIKE 'DEMO%';

-- Deterministic demo driver records; replace with TMS/YMS integration later.
INSERT INTO appointment_drivers (
    appt_id, driver_name, license_number, license_state, phone_number, tractor_number
)
SELECT
    a.appt_id,
    'Demo Driver ' || RIGHT(a.appt_id, 3),
    'DL-' || RIGHT(a.appt_id, 6),
    'GA',
    '(404) 555-' || LPAD((1000 + (ABS(HASHTEXT(a.appt_id)) % 8999))::TEXT, 4, '0'),
    'TR-' || RIGHT(a.appt_id, 4)
FROM appointments a
WHERE a.appt_id LIKE 'DEMO%'
ON CONFLICT (appt_id) DO NOTHING;

COMMIT;
