"""
=============================================================
Cybervehicare — Vehicle Health Monitoring Framework
Phase 5: Telemetry Service  (Orchestrator)
=============================================================
File path  : services/telemetry/main.py
Port       : 8001
Run command: python3 -m uvicorn services.telemetry.main:app --host 0.0.0.0 --port 8001 --reload

Flow for POST /telemetry/ingest:
  1. Store telemetry in memory
  2. POST http://localhost:8000/predict          (Prediction API)
  3. POST http://localhost:8002/diagnostics/evaluate  (Diagnostics Service)
  4. POST http://localhost:8003/alerts/create    (Alert Service)
  5. Return combined response
=============================================================
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("cybervehicare.telemetry")

# ─────────────────────────────────────────────
# SERVICE URLS
# ─────────────────────────────────────────────

PREDICTION_API_URL  = "http://localhost:8000/predict"
DIAGNOSTICS_API_URL = "http://localhost:8002/diagnostics/evaluate"
ALERT_API_URL       = "http://localhost:8003/alerts/create"

# ─────────────────────────────────────────────
# IN-MEMORY STORE
# ─────────────────────────────────────────────

_telemetry_store: deque[dict[str, Any]] = deque(maxlen=500)   # newest at right


# ─────────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────────

class TelemetryRecord(BaseModel):
    vehicle_id:              str   = "UNKNOWN"
    timestamp:               str   = ""
    odometer_reading:        float = 0.0
    engine_temp_c:           float = 90.0
    engine_rpm:              float = 1000.0
    oil_pressure_psi:        float = 40.0
    coolant_temp_c:          float = 85.0
    fuel_level_percent:      float = 50.0
    fuel_consumption_lph:    float = 6.0
    vibration_level:         float = 0.5
    engine_hours:            float = 1000.0
    brake_fluid_level_psi:   float = 900.0
    brake_pad_wear_mm:       float = 5.0
    brake_temp_c:            float = 80.0
    abs_fault_indicator:     float = 0.0
    battery_voltage_v:       float = 12.5
    battery_current_a:       float = 10.0
    battery_temp_c:          float = 25.0
    battery_charge_percent:  float = 80.0
    battery_health_percent:  float = 90.0
    vehicle_speed_kph:       float = 0.0
    gps_latitude:            float = 0.0
    gps_longitude:           float = 0.0
    engine_failure_imminent: float = 0.0
    brake_issue_imminent:    float = 0.0
    battery_issue_imminent:  float = 0.0
    failure_type:            str   = "No Failure"
    organisation_type:       str   = "Government Agency"
    vehicle_type:            str   = "Community Outreach Vehicle"
    tyre_pressure_psi:       float = 30.0
    fault_indicator:         float = 0.0
    maintenance_status:      str   = ""

    model_config = {"extra": "allow"}


# ─────────────────────────────────────────────
# DOWNSTREAM CALL HELPERS
# ─────────────────────────────────────────────

_TIMEOUT = 10   # seconds


def _call_prediction(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        r = requests.post(PREDICTION_API_URL, json=payload, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        log.error("[TELEMETRY] Prediction API unreachable (is port 8000 running?)")
        return {"error": "Prediction API unreachable", "prediction_label": "UNKNOWN"}
    except Exception as exc:
        log.error(f"[TELEMETRY] Prediction API error: {exc}")
        return {"error": str(exc), "prediction_label": "UNKNOWN"}


def _call_diagnostics(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        r = requests.post(DIAGNOSTICS_API_URL, json=payload, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        log.error("[TELEMETRY] Diagnostics Service unreachable (is port 8002 running?)")
        return {"error": "Diagnostics Service unreachable", "diagnostics_status": "UNKNOWN"}
    except Exception as exc:
        log.error(f"[TELEMETRY] Diagnostics Service error: {exc}")
        return {"error": str(exc), "diagnostics_status": "UNKNOWN"}


def _call_alert(
    telemetry: dict[str, Any],
    prediction: dict[str, Any],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    body = {
        "telemetry":   telemetry,
        "prediction":  prediction,
        "diagnostics": diagnostics,
    }
    try:
        r = requests.post(ALERT_API_URL, json=body, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        log.error("[TELEMETRY] Alert Service unreachable (is port 8003 running?)")
        return {"error": "Alert Service unreachable", "alert_created": False}
    except Exception as exc:
        log.error(f"[TELEMETRY] Alert Service error: {exc}")
        return {"error": str(exc), "alert_created": False}


# ─────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────

app = FastAPI(
    title       ="Cybervehicare — Telemetry Service",
    description ="Phase 5: Ingests telemetry, orchestrates Prediction → Diagnostics → Alert pipeline.",
    version     ="1.0.0",
    docs_url    ="/docs",
    redoc_url   ="/redoc",
)


@app.on_event("startup")
async def startup_event():
    print()
    print("═" * 62)
    print("  CYBERVEHICARE · PHASE 5 — TELEMETRY SERVICE")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("═" * 62)
    print()
    print("  Telemetry Service running on port 8001 ✓")
    print()
    print("  Pipeline: Telemetry → Prediction → Diagnostics → Alert")
    print()
    print("  Endpoints:")
    print("    GET  /                         → service info")
    print("    GET  /health                   → health check")
    print("    POST /telemetry/ingest         → ingest + full pipeline")
    print("    GET  /telemetry/latest         → last 20 records")
    print("    GET  /telemetry/{vehicle_id}   → records by vehicle")
    print()
    print("  Docs: http://localhost:8001/docs")
    print("═" * 62)
    print()


@app.get("/", summary="Service Information")
def root():
    return {
        "service":         "Cybervehicare Telemetry Service",
        "phase":           "Phase 5 — Microservices Integration",
        "version":         "1.0.0",
        "port":            8001,
        "records_stored":  len(_telemetry_store),
        "pipeline": {
            "step_1": f"POST {PREDICTION_API_URL}",
            "step_2": f"POST {DIAGNOSTICS_API_URL}",
            "step_3": f"POST {ALERT_API_URL}",
        },
        "endpoints": {
            "GET  /":                       "Service information",
            "GET  /health":                 "Health check",
            "POST /telemetry/ingest":       "Ingest one telemetry record (full pipeline)",
            "GET  /telemetry/latest":       "Last 20 telemetry records",
            "GET  /telemetry/{vehicle_id}": "Records for a specific vehicle",
        },
    }


@app.get("/health", summary="Health Check")
def health():
    return {
        "status":         "healthy",
        "service":        "telemetry",
        "records_stored": len(_telemetry_store),
        "timestamp":      datetime.now(timezone.utc).isoformat(),
    }


@app.post("/telemetry/ingest", summary="Ingest Telemetry Record (Full Pipeline)")
def ingest(record: TelemetryRecord):
    payload    = record.model_dump()
    vehicle_id = payload.get("vehicle_id", "UNKNOWN")
    ts         = datetime.now(timezone.utc).isoformat()

    # ── Step 1: Store ──
    _telemetry_store.append({**payload, "_ingested_at": ts})
    log.info(f"[TELEMETRY] Ingested vehicle={vehicle_id}  store_size={len(_telemetry_store)}")

    # ── Step 2: Prediction API ──
    prediction = _call_prediction(payload)
    log.info(
        f"[TELEMETRY] Prediction → vehicle={vehicle_id}  "
        f"label={prediction.get('prediction_label')}  "
        f"confidence={prediction.get('confidence_score')}"
    )

    # ── Step 3: Diagnostics Service ──
    diagnostics = _call_diagnostics(payload)
    log.info(
        f"[TELEMETRY] Diagnostics → vehicle={vehicle_id}  "
        f"status={diagnostics.get('diagnostics_status')}  "
        f"rules={diagnostics.get('rule_count', 0)}"
    )

    # ── Step 4: Alert Service ──
    alert = _call_alert(payload, prediction, diagnostics)
    log.info(
        f"[TELEMETRY] Alert → vehicle={vehicle_id}  "
        f"created={alert.get('alert_created')}  "
        f"severity={alert.get('severity')}"
    )

    return {
        "vehicle_id":        vehicle_id,
        "telemetry_received": True,
        "prediction":        prediction,
        "diagnostics":       diagnostics,
        "alert":             alert,
        "timestamp":         ts,
    }


@app.get("/telemetry/latest", summary="Last 20 Telemetry Records")
def latest():
    records = list(_telemetry_store)[-20:]
    records.reverse()   # newest first
    return {
        "total_stored": len(_telemetry_store),
        "returned":     len(records),
        "records":      records,
    }


@app.get("/telemetry/{vehicle_id}", summary="Telemetry Records for a Specific Vehicle")
def by_vehicle(vehicle_id: str):
    matched = [r for r in _telemetry_store if r.get("vehicle_id") == vehicle_id]
    if not matched:
        raise HTTPException(
            status_code=404,
            detail=f"No telemetry records found for vehicle '{vehicle_id}'.",
        )
    matched.reverse()   # newest first
    return {
        "vehicle_id":   vehicle_id,
        "total_records": len(matched),
        "records":      matched,
    }
