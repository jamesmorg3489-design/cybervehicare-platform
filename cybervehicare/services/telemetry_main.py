"""
=============================================================
Cybervehicare — Vehicle Health Monitoring Framework
Telemetry Service
=============================================================
File path  : services/telemetry/main.py

Orchestrates the full ingest pipeline:
    POST /telemetry/ingest
        → Prediction API   (http://localhost:8000/predict)
        → Diagnostics Svc  (http://localhost:8002/diagnostics/evaluate)
        → Alert Service    (http://localhost:8003/alerts)

Telemetry endpoints
-------------------
  GET  /telemetry/latest?limit=N   Latest N records  (default 20)
  GET  /telemetry/all              All stored records
  GET  /telemetry/count            Record count summary
  GET  /telemetry/{vehicle_id}     Records for a specific vehicle
=============================================================
"""

from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────

app = FastAPI(
    title="Cybervehicare Telemetry Service",
    description="Ingests vehicle telemetry and orchestrates prediction, diagnostics, and alerting.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# IN-MEMORY STORE  (increased to 20 000 records)
# ─────────────────────────────────────────────

_telemetry_store: deque[dict] = deque(maxlen=20_000)

# ─────────────────────────────────────────────
# SERVICE URLS
# ─────────────────────────────────────────────

PREDICTION_URL  = "http://localhost:8000/predict"
DIAGNOSTICS_URL = "http://localhost:8002/diagnostics/evaluate"
ALERT_URL       = "http://localhost:8003/alerts/create"
TIMEOUT = 5.0   # seconds per downstream call

# ─────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────

class TelemetryRecord(BaseModel):
    vehicle_id:           Optional[str]   = None
    timestamp:            Optional[str]   = None
    engine_temp_c:        Optional[float] = None
    battery_voltage_v:    Optional[float] = None
    fuel_level_percent:   Optional[float] = None
    tyre_pressure_psi:    Optional[float] = None
    oil_pressure_psi:     Optional[float] = None
    fault_indicator:      Optional[int]   = None
    maintenance_status:   Optional[str]   = None
    model_class:          Optional[Any]   = None   # extra columns are absorbed

    class Config:
        extra = "allow"


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
        return {"error": str(exc), "diagnostics_status": "UNKNOWN", "rules_triggered": []}


async def _call_alert(record: dict, prediction: dict, diagnostics: dict) -> dict:
    """POST to Alert Service; returns full response dict or error stub."""
    payload = {
        **record,
        "prediction":  prediction,
        "diagnostics": diagnostics,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(ALERT_URL, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        return {"error": str(exc), "alert_created": False}


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "Cybervehicare Telemetry Service",
        "version": "1.0.0",
        "status":  "running",
        "endpoints": [
            "GET  /health",
            "POST /telemetry/ingest",
            "GET  /telemetry/latest?limit=N",
            "GET  /telemetry/all",
            "GET  /telemetry/count",
            "GET  /telemetry/{vehicle_id}",
        ],
    }


@app.get("/health")
async def health():
    return {
        "status":        "healthy",
        "service":       "telemetry",
        "total_stored":  len(_telemetry_store),
        "timestamp":     datetime.now(timezone.utc).isoformat(),
    }


# ── POST /telemetry/ingest ───────────────────

@app.post("/telemetry/ingest")
async def ingest(record: TelemetryRecord):
    """
    Ingest a single telemetry record, run the full pipeline, and return results.
    """
    raw: dict = record.model_dump()

    # Stamp ingestion time
    raw["_ingested_at"] = datetime.now(timezone.utc).isoformat()

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

    # ── Flat fields for simulator compatibility ──
    pred_label  = (
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
        "vehicle_id":         raw.get("vehicle_id"),
        "ingested_at":        raw["_ingested_at"],
        "total_stored":       len(_telemetry_store),
    }


# ── GET /telemetry/latest ────────────────────

@app.get("/telemetry/latest")
async def latest_telemetry(
    limit: int = Query(default=20, ge=1, description="Number of most-recent records to return"),
):
    """
    Return the most-recent *limit* records.

    Examples
    --------
      GET /telemetry/latest          → last 20 records
      GET /telemetry/latest?limit=100 → last 100 records
      GET /telemetry/latest?limit=500 → last 500 records
    """
    records = list(_telemetry_store)
    sliced  = records[-limit:]          # most-recent limit rows

    return {
        "total_stored": len(_telemetry_store),
        "returned":     len(sliced),
        "limit":        limit,
        "records":      sliced,
    }


# ── GET /telemetry/all ───────────────────────

@app.get("/telemetry/all")
async def all_telemetry():
    """Return every record currently in the in-memory store."""
    records = list(_telemetry_store)
    return {
        "total_stored": len(_telemetry_store),
        "returned":     len(records),
        "records":      records,
    }


# ── GET /telemetry/count ─────────────────────

@app.get("/telemetry/count")
async def telemetry_count():
    """Return a lightweight record-count summary (no records payload)."""
    return {
        "total_stored": len(_telemetry_store),
        "timestamp":    datetime.now(timezone.utc).isoformat(),
    }


# ── GET /telemetry/{vehicle_id} ──────────────

@app.get("/telemetry/{vehicle_id}")
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
