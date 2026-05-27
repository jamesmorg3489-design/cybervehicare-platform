"""
=============================================================
Cybervehicare — Vehicle Health Monitoring Framework
Telemetry Service
=============================================================
File path  : services/telemetry/main.py
Port       : 8001
Run command (local):
    python3 -m uvicorn services.telemetry.main:app \
        --host 0.0.0.0 --port 8001 --reload

Run command (Docker):
    Handled by docker-compose.yml — environment variables
    PREDICTION_URL, DIAGNOSTICS_URL, ALERT_URL are injected
    automatically.

Flow for POST /telemetry/ingest:
  1. Store telemetry in memory
  2. POST <PREDICTION_URL>   (Prediction API)
  3. POST <DIAGNOSTICS_URL>  (Diagnostics Service)
  4. POST <ALERT_URL>        (Alert Service)
  5. Return combined response

Telemetry endpoints
-------------------
  GET  /telemetry/latest?limit=N   Latest N records  (default 20)
  GET  /telemetry/all              All stored records
  GET  /telemetry/count            Record count summary
  GET  /telemetry/{vehicle_id}     Records for a specific vehicle
=============================================================
"""

from __future__ import annotations

import os
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("cybervehicare.telemetry")

# ─────────────────────────────────────────────
# SERVICE URLS
# Environment variables are used when running inside Docker
# (injected by docker-compose.yml).  Localhost defaults are used
# for plain local development so existing Phase 5 commands still work.
# ─────────────────────────────────────────────

PREDICTION_URL  = os.getenv("PREDICTION_URL",  "http://localhost:8000/predict")
DIAGNOSTICS_URL = os.getenv("DIAGNOSTICS_URL", "http://localhost:8002/diagnostics/evaluate")
ALERT_URL       = os.getenv("ALERT_URL",       "http://localhost:8003/alerts/create")

TIMEOUT = 5.0   # seconds per downstream call

# ─────────────────────────────────────────────
# IN-MEMORY STORE  (20 000 records, oldest dropped first)
# ─────────────────────────────────────────────

_telemetry_store: deque[dict[str, Any]] = deque(maxlen=20_000)

# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────

app = FastAPI(
    title="Cybervehicare Telemetry Service",
    description=(
        "Ingests vehicle telemetry and orchestrates prediction, "
        "diagnostics, and alerting."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# SCHEMAS
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
# STARTUP BANNER
# ─────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    print()
    print("═" * 62)
    print("  CYBERVEHICARE · TELEMETRY SERVICE")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("═" * 62)
    print()
    print("  Telemetry Service running on port 8001 ✓")
    print()
    print("  Downstream URLs (env-var overridable):")
    print(f"    PREDICTION_URL  = {PREDICTION_URL}")
    print(f"    DIAGNOSTICS_URL = {DIAGNOSTICS_URL}")
    print(f"    ALERT_URL       = {ALERT_URL}")
    print()
    print("  Pipeline: Telemetry → Prediction → Diagnostics → Alert")
    print()
    print("  Endpoints:")
    print("    GET  /                          → service info")
    print("    GET  /health                    → health check")
    print("    POST /telemetry/ingest          → ingest + full pipeline")
    print("    GET  /telemetry/latest?limit=N  → last N records (default 20)")
    print("    GET  /telemetry/all             → all stored records")
    print("    GET  /telemetry/count           → record count only")
    print("    GET  /telemetry/{vehicle_id}    → records by vehicle")
    print()
    print("  Docs: http://localhost:8001/docs")
    print("═" * 62)
    print()


# ─────────────────────────────────────────────
# DOWNSTREAM HELPERS
# ─────────────────────────────────────────────

async def _call_prediction(record: dict) -> dict:
    """POST to Prediction API; returns full response dict or error stub."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(PREDICTION_URL, json=record)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        log.error(f"[TELEMETRY] Prediction API error: {exc}")
        return {"error": str(exc), "prediction_label": "UNKNOWN", "confidence": None}


async def _call_diagnostics(record: dict, prediction: dict) -> dict:
    """POST to Diagnostics Service; returns full response dict or error stub."""
    payload = {**record, "prediction": prediction}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(DIAGNOSTICS_URL, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        log.error(f"[TELEMETRY] Diagnostics Service error: {exc}")
        return {"error": str(exc), "diagnostics_status": "UNKNOWN", "rules_triggered": []}


async def _call_alert(record: dict, prediction: dict, diagnostics: dict) -> dict:
    """POST to Alert Service; returns full response dict or error stub."""
    payload = {
        "telemetry":   record,
        "prediction":  prediction,
        "diagnostics": diagnostics,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(ALERT_URL, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        log.error(f"[TELEMETRY] Alert Service error: {exc}")
        return {"error": str(exc), "alert_created": False}


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.get("/", summary="Service Information")
async def root():
    return {
        "service":        "Cybervehicare Telemetry Service",
        "version":        "1.0.0",
        "status":         "running",
        "total_stored":   len(_telemetry_store),
        "downstream": {
            "prediction":  PREDICTION_URL,
            "diagnostics": DIAGNOSTICS_URL,
            "alert":       ALERT_URL,
        },
        "endpoints": [
            "GET  /health",
            "POST /telemetry/ingest",
            "GET  /telemetry/latest?limit=N",
            "GET  /telemetry/all",
            "GET  /telemetry/count",
            "GET  /telemetry/{vehicle_id}",
        ],
    }


@app.get("/health", summary="Health Check")
async def health():
    return {
        "status":        "healthy",
        "service":       "telemetry",
        "total_stored":  len(_telemetry_store),
        "timestamp":     datetime.now(timezone.utc).isoformat(),
    }


# ── POST /telemetry/ingest ───────────────────

@app.post("/telemetry/ingest", summary="Ingest Telemetry Record (Full Pipeline)")
async def ingest(record: TelemetryRecord):
    """
    Ingest a single telemetry record, run the full pipeline, and return results.
    """
    raw: dict = record.model_dump()
    raw["_ingested_at"] = datetime.now(timezone.utc).isoformat()

    vehicle_id = raw.get("vehicle_id", "UNKNOWN")

    # ── Pipeline ─────────────────────────────
    prediction  = await _call_prediction(raw)
    diagnostics = await _call_diagnostics(raw, prediction)
    alert       = await _call_alert(raw, prediction, diagnostics)

    # ── Persist ───────────────────────────────
    stored_record = {
        **raw,
        "prediction":  prediction,
        "diagnostics": diagnostics,
        "alert":       alert,
    }
    _telemetry_store.append(stored_record)

    log.info(
        f"[TELEMETRY] Ingested vehicle={vehicle_id}  "
        f"prediction={prediction.get('prediction_label')}  "
        f"diagnostics={diagnostics.get('diagnostics_status')}  "
        f"store_size={len(_telemetry_store)}"
    )

    # ── Flat convenience fields for simulator compatibility ──
    pred_label = (
        prediction.get("prediction_label")
        or (prediction.get("prediction") or {}).get("prediction_label")
        or "UNKNOWN"
    )
    diag_status = (
        diagnostics.get("diagnostics_status")
        or (diagnostics.get("diagnostics") or {}).get("diagnostics_status")
        or "UNKNOWN"
    )
    alert_created = bool(
        alert.get("alert_created", False)
        or alert.get("alert_raised", False)
    )

    return {
        # Nested objects (for dashboard)
        "prediction":         prediction,
        "diagnostics":        diagnostics,
        "alert":              alert,
        # Flat convenience fields (for simulator)
        "prediction_label":   pred_label,
        "diagnostics_status": diag_status,
        "alert_raised":       alert_created,
        "alert_created":      alert_created,
        # Meta
        "vehicle_id":         vehicle_id,
        "ingested_at":        raw["_ingested_at"],
        "total_stored":       len(_telemetry_store),
    }


# ── GET /telemetry/latest ────────────────────

@app.get("/telemetry/latest", summary="Latest N Telemetry Records")
async def latest_telemetry(
    limit: int = Query(
        default=20,
        ge=1,
        description="Number of most-recent records to return",
    ),
):
    """
    Return the most-recent *limit* records.

    Examples
    --------
      GET /telemetry/latest            → last 20 records
      GET /telemetry/latest?limit=100  → last 100 records
      GET /telemetry/latest?limit=500  → last 500 records
    """
    records = list(_telemetry_store)
    sliced  = records[-limit:]

    return {
        "total_stored": len(_telemetry_store),
        "returned":     len(sliced),
        "limit":        limit,
        "records":      sliced,
    }


# ── GET /telemetry/all ───────────────────────

@app.get("/telemetry/all", summary="All Stored Telemetry Records")
async def all_telemetry():
    """Return every record currently in the in-memory store."""
    records = list(_telemetry_store)
    return {
        "total_stored": len(_telemetry_store),
        "returned":     len(records),
        "records":      records,
    }


# ── GET /telemetry/count ─────────────────────

@app.get("/telemetry/count", summary="Record Count (no payload)")
async def telemetry_count():
    """Return a lightweight record-count summary (no records payload)."""
    return {
        "total_stored": len(_telemetry_store),
        "timestamp":    datetime.now(timezone.utc).isoformat(),
    }


# ── GET /telemetry/{vehicle_id} ──────────────

@app.get("/telemetry/{vehicle_id}", summary="Telemetry for a Specific Vehicle")
async def vehicle_telemetry(vehicle_id: str):
    """Return all stored records for a specific vehicle_id."""
    matched = [
        r for r in _telemetry_store
        if r.get("vehicle_id") == vehicle_id
    ]
    if not matched:
        raise HTTPException(
            status_code=404,
            detail=f"No telemetry records found for vehicle_id='{vehicle_id}'",
        )
    return {
        "vehicle_id":   vehicle_id,
        "total_stored": len(_telemetry_store),
        "returned":     len(matched),
        "records":      matched,
    }

# ─────────────────────────────────────────────
# PROMETHEUS METRICS
# ─────────────────────────────────────────────
try:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except Exception as exc:
    print(f"Prometheus metrics setup skipped: {exc}")

