-- =============================================================
-- CyberVehicare Database Schema
-- =============================================================

CREATE TABLE IF NOT EXISTS vehicle_telemetry (
    id                      SERIAL PRIMARY KEY,
    vehicle_id              VARCHAR(20) NOT NULL,
    timestamp               TIMESTAMP NOT NULL,
    odometer_reading        FLOAT,
    engine_temp_c           FLOAT,
    engine_rpm              FLOAT,
    oil_pressure_psi        FLOAT,
    coolant_temp_c          FLOAT,
    fuel_level_percent      FLOAT,
    fuel_consumption_lph    FLOAT,
    vibration_level         FLOAT,
    engine_hours            FLOAT,
    brake_fluid_level_psi   FLOAT,
    brake_pad_wear_mm       FLOAT,
    brake_temp_c            FLOAT,
    abs_fault_indicator     FLOAT,
    battery_voltage_v       FLOAT,
    battery_current_a       FLOAT,
    battery_temp_c          FLOAT,
    battery_charge_percent  FLOAT,
    battery_health_percent  FLOAT,
    vehicle_speed_kph       FLOAT,
    gps_latitude            FLOAT,
    gps_longitude           FLOAT,
    engine_failure_imminent FLOAT,
    brake_issue_imminent    FLOAT,
    battery_issue_imminent  FLOAT,
    failure_type            VARCHAR(50),
    organisation_type       VARCHAR(50),
    vehicle_type            VARCHAR(50),
    tyre_pressure_psi       FLOAT,
    fault_indicator         INTEGER DEFAULT 0,
    maintenance_status      VARCHAR(20),
    ingested_at             TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS diagnostics_results (
    id                  SERIAL PRIMARY KEY,
    vehicle_id          VARCHAR(20) NOT NULL,
    evaluated_at        TIMESTAMP DEFAULT NOW(),
    health_score        FLOAT,
    engine_status       VARCHAR(20),
    battery_status      VARCHAR(20),
    brake_status        VARCHAR(20),
    tyre_status         VARCHAR(20),
    overall_status      VARCHAR(20),
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS predictions (
    id                  SERIAL PRIMARY KEY,
    vehicle_id          VARCHAR(20) NOT NULL,
    predicted_at        TIMESTAMP DEFAULT NOW(),
    predicted_status    VARCHAR(20),
    confidence          FLOAT,
    model_version       VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS alerts (
    id                  SERIAL PRIMARY KEY,
    vehicle_id          VARCHAR(20) NOT NULL,
    alert_type          VARCHAR(50),
    severity            VARCHAR(20),
    message             TEXT,
    triggered_at        TIMESTAMP DEFAULT NOW(),
    resolved            BOOLEAN DEFAULT FALSE,
    resolved_at         TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_telemetry_vehicle ON vehicle_telemetry(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON vehicle_telemetry(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_vehicle ON alerts(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_predictions_vehicle ON predictions(vehicle_id);
