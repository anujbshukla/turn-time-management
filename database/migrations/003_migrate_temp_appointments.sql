INSERT INTO appointments (
    appt_id,
    appt_date,
    customer_id,
    customer_name,
    facility_id,
    carrier_id,
    scheduled_time,
    estimated_arrival_time,
    actual_arrival_time,
    assigned_dock_id,
    status,
    appointment_type,
    load_type,
    pallet_count,
    sku_count,
    priority,
    sla_minutes,
    detention_cost_per_hour
)
SELECT
    old.appt_id,
    old.appt_date,
    old.customer_id,
    old.customer_name,

    CASE
        WHEN old.facility_id = 'FAC001'
            THEN 'FAC001'
        WHEN old.facility_name = 'Atlanta Distribution Center'
            THEN 'FAC001'
        ELSE 'FAC001'
    END AS facility_id,

    CASE
        WHEN old.carrier_name = 'Carrier A'
            THEN 'CAR001'
        WHEN old.carrier_name = 'Carrier B'
            THEN 'CAR002'
        WHEN old.carrier_name = 'Carrier C'
            THEN 'CAR003'
        ELSE NULL
    END AS carrier_id,

    old.scheduled_time,
    old.estimated_arrival_time,
    old.actual_arrival_time,

    CASE
        WHEN old.assigned_dock = 'Dock 3'
            THEN 'DOCK003'
        WHEN old.assigned_dock = 'Dock 5'
            THEN 'DOCK005'
        WHEN old.assigned_dock = 'Dock 6'
            THEN 'DOCK006'
        WHEN old.assigned_dock = 'Dock 8'
            THEN 'DOCK008'
        ELSE NULL
    END AS assigned_dock_id,

    COALESCE(old.status, 'Scheduled'),
    'Inbound',
    'Palletized',
    0,
    0,
    1,
    COALESCE(old.sla_minutes, 120),
    COALESCE(old.detention_cost_per_hour, 100.00)

FROM appointments_temp AS old

ON CONFLICT (appt_id) DO NOTHING;