INSERT INTO facilities (
    facility_id,
    facility_name,
    timezone,
    active
)
VALUES (
    'FAC001',
    'Atlanta Distribution Center',
    'America/New_York',
    TRUE
)
ON CONFLICT (facility_id) DO NOTHING;


INSERT INTO carriers (
    carrier_id,
    carrier_name,
    active
)
VALUES
    ('CAR001', 'Carrier A', TRUE),
    ('CAR002', 'Carrier B', TRUE),
    ('CAR003', 'Carrier C', TRUE)
ON CONFLICT (carrier_id) DO NOTHING;


INSERT INTO docks (
    dock_id,
    facility_id,
    dock_name,
    dock_type,
    temperature_zone,
    active
)
VALUES
    (
        'DOCK003',
        'FAC001',
        'Dock 3',
        'Standard',
        'Ambient',
        TRUE
    ),
    (
        'DOCK005',
        'FAC001',
        'Dock 5',
        'Standard',
        'Ambient',
        TRUE
    ),
    (
        'DOCK006',
        'FAC001',
        'Dock 6',
        'Standard',
        'Ambient',
        TRUE
    ),
    (
        'DOCK008',
        'FAC001',
        'Dock 8',
        'Standard',
        'Ambient',
        TRUE
    )
ON CONFLICT (dock_id) DO NOTHING;