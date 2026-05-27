"""
=============================================================
Cybervehicare — Vehicle Health Monitoring Framework
Phase 5: Alert Service
=============================================================
File path  : services/alert/main.py
Port       : 8003
Run command: python3 -m uvicorn services.alert.main:app --host 0.0.0.0 --port 8003 --reload
=============================================================
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("cybervehicare.alert")

# ─────────────────────────────────────────────
# IN-MEMORY ALERT STORE
# ─────────────────────────────────────────────

_alerts: list[dict[str, Any]] = []   # all alerts in insertion order


# ─────────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────────

class AlertRequest(BaseModel):
    telemetry:   dict[str, Any]
    prediction:  dict[str, Any]
    diagnostics: dict[str, Any]


# ─────────────────────────────────────────────
# SEVERITY HELPERS
# ─────────────────────────────────────────────

_SEVERITY_RANK = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}


def _resolve_severity(prediction_label: str, diagnostics_status: str) -> str:
    """Return the higher of prediction vs diagnostics severity."""
    p_rank = _SEVERITY_RANK.get(prediction_label.upper(), 0)
    d_rank = _SEVERITY_RANK.get(diagnostics_status.upper(), 0)
    if max(p_rank, d_rank) == 2:
        return "CRITICAL"
    if max(p_rank, d_rank) == 1:
        return "WARNING"
    return "NORMAL"


def _build_message(
    vehicle_id: str,
    prediction_label: str,
    diagnostics_status: str,
    diag_messages: list[dict[str, str]],
) -> str:
    parts = [f"Vehicle {vehicle_id}:"]
    if prediction_label in ("WARNING", "CRITICAL"):
        parts.append(f"ML model predicts {prediction_label}.")
    if diagnostics_status in ("WARNING", "CRITICAL"):
        rule_texts = [m["message"] for m in diag_messages]
        parts.append(f"Diagnostics: {'; '.join(rule_texts)}.")
    return " ".join(parts)


# ─────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────

app = FastAPI(
    title       ="Cybervehicare — Alert Service",
    description ="Phase 5: Creates and stores vehicle health alerts.",
    version     ="1.0.0",
    docs_url    ="/docs",
    redoc_url   ="/redoc",
)


@app.on_event("startup")
async def startup_event():
    print()
    print("═" * 62)
    print("  CYBERVEHICARE · PHASE 5 — ALERT SERVICE")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("═" * 62)
    print()
    print("  Alert Service running on port 8003 ✓")
    print()
    print("  Endpoints:")
    print("    GET    /                    → service info")
    print("    GET    /health              → health check")
    print("    POST   /alerts/create       → create alert")
    print("    GET    /alerts              → list all alerts")
    print("    GET    /alerts/{vehicle_id} → alerts by vehicle")
    print("    DELETE /alerts/clear        → clear all alerts")
    print()
    print("  Docs: http://localhost:8003/docs")
    print("═" * 62)
    print()


@app.get("/", summary="Service Information")
def root():
    return {
        "service":       "Cybervehicare Alert Service",
        "phase":         "Phase 5 — Microservices Integration",
        "version":       "1.0.0",
        "port":          8003,
        "total_alerts":  len(_alerts),
        "endpoints": {
            "GET    /":                    "Service information",
            "GET    /health":              "Health check",
            "POST   /alerts/create":       "Create alert from telemetry + prediction + diagnostics",
            "GET    /alerts":              "List all alerts",
            "GET    /alerts/{vehicle_id}": "Alerts for a specific vehicle",
            "DELETE /alerts/clear":        "Clear all alerts (testing)",
        },
    }


@app.get("/health", summary="Health Check")
def health():
    return {
        "status":       "healthy",
        "service":      "alert",
        "total_alerts": len(_alerts),
        "timestamp":    datetime.now(timezone.utc).isoformat(),
    }


@app.post("/alerts/create", summary="Create Alert")
def create_alert(request: AlertRequest):
    telemetry   = request.telemetry
    prediction  = request.prediction
    diagnostics = request.diagnostics

    vehicle_id        = str(telemetry.get("vehicle_id", "UNKNOWN"))
    prediction_label  = str(prediction.get("prediction_label", "NORMAL")).upper()
    diagnostics_status = str(diagnostics.get("diagnostics_status", "NORMAL")).upper()
    diag_messages     = diagnostics.get("messages", [])

    # Only create alert if something is not NORMAL
    needs_alert = (
        prediction_label  in ("WARNING", "CRITICAL") or
        diagnostics_status in ("WARNING", "CRITICAL")
    )

    if not needs_alert:
        log.info(f"[ALERT] vehicle={vehicle_id}  → no alert (all NORMAL)")
        return {
            "alert_created": False,
            "alert_id":      None,
            "vehicle_id":    vehicle_id,
            "severity":      "NORMAL",
            "message":       f"Vehicle {vehicle_id}: All systems NORMAL.",
            "timestamp":     datetime.now(timezone.utc).isoformat(),
        }

    severity = _resolve_severity(prediction_label, diagnostics_status)
    message  = _build_message(vehicle_id, prediction_label, diagnostics_status, diag_messages)
    alert_id = str(uuid.uuid4())
    ts       = datetime.now(timezone.utc).isoformat()

    alert = {
        "alert_id":    alert_id,
        "vehicle_id":  vehicle_id,
        "severity":    severity,
        "message":     message,
        "prediction":  {
            "label":      prediction_label,
            "confidence": prediction.get("confidence_score"),
        },
        "diagnostics": {
            "status":    diagnostics_status,
            "rule_count": diagnostics.get("rule_count", 0),
            "messages":  diag_messages,
        },
        "timestamp":   ts,
    }

    _alerts.append(alert)

    log.info(
        f"[ALERT] vehicle={vehicle_id}  severity={severity}  "
        f"alert_id={alert_id[:8]}…"
    )

    return {
        "alert_created": True,
        "alert_id":      alert_id,
        "vehicle_id":    vehicle_id,
        "severity":      severity,
        "message":       message,
        "timestamp":     ts,
    }


@app.get("/alerts", summary="List All Alerts")
def list_alerts():
    return {
        "total_alerts": len(_alerts),
        "alerts":       _alerts,
    }


@app.get("/alerts/{vehicle_id}", summary="Alerts for a Specific Vehicle")
def alerts_by_vehicle(vehicle_id: str):
    matched = [a for a in _alerts if a["vehicle_id"] == vehicle_id]
    if not matched:
        raise HTTPException(
            status_code=404,
            detail=f"No alerts found for vehicle '{vehicle_id}'.",
        )
    return {
        "vehicle_id":   vehicle_id,
        "total_alerts": len(matched),
        "alerts":       matched,
    }


@app.delete("/alerts/clear", summary="Clear All Alerts")
def clear_alerts():
    count = len(_alerts)
    _alerts.clear()
    log.info(f"[ALERT] Cleared {count} alerts from memory.")
    return {
        "cleared":   count,
        "message":   f"Cleared {count} alert(s) from in-memory store.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

# ─────────────────────────────────────────────
# PROMETHEUS METRICS
# ─────────────────────────────────────────────
try:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except Exception as exc:
    print(f"Prometheus metrics setup skipped: {exc}")

