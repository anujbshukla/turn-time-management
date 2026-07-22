CREATE TABLE IF NOT EXISTS appointments_temp (
    appt_id VARCHAR(50) PRIMARY KEY,
    appt_date TIMESTAMP NOT NULL,
    customer_name VARCHAR(100),
    customer_id VARCHAR(100),
    facility_name VARCHAR(100),
    facility_id VARCHAR(100),
    scheduled_time TIMESTAMP NOT NULL,
    carrier_name VARCHAR(100),
    status VARCHAR(30),
    estimated_arrival_time TIMESTAMP,
    actual_arrival_time TIMESTAMP,
    predicted_duration_minutes INTEGER DEFAULT 30,
    assigned_dock VARCHAR(50),
    sla_minutes INTEGER DEFAULT 120,
    detention_cost_per_hour NUMERIC(10,2) DEFAULT 100.00
);