"""
=============================================================
Cybervehicare — Vehicle Health Monitoring Framework
Phase 5: Diagnostics Service
=============================================================
File path  : services/diagnostics/main.py
Port       : 8002
Run command: python3 -m uvicorn services.diagnostics.main:app --host 0.0.0.0 --port 8002 --reload
=============================================================
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("cybervehicare.diagnostics")

# ─────────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────────

class TelemetryPayload(BaseModel):
    vehicle_id:              str   = "UNKNOWN"
    engine_temp_c:           float = 90.0
    battery_voltage_v:       float = 12.5
    fuel_level_percent:      float = 50.0
    tyre_pressure_psi:       float = 32.0
    oil_pressure_psi:        float = 40.0
    vibration_level:         float = 0.5
    fault_indicator:         float = 0.0

    model_config = {"extra": "allow"}


# ─────────────────────────────────────────────
# DIAGNOSTIC RULES ENGINE
# ─────────────────────────────────────────────

def _run_rules(data: dict[str, Any]) -> dict[str, Any]:
    """
    Apply rule-based diagnostics and return structured result.
    Priority: CRITICAL > WARNING > NORMAL
    """
    messages: list[dict[str, str]] = []

    def get(key: str, default: float = 0.0) -> float:
        try:
            return float(data.get(key, default))
        except (TypeError, ValueError):
            return default

    engine_temp       = get("engine_temp_c",         90.0)
    battery_voltage   = get("battery_voltage_v",     12.5)
    fuel_level        = get("fuel_level_percent",    50.0)
    tyre_pressure     = get("tyre_pressure_psi",     32.0)
    oil_pressure      = get("oil_pressure_psi",      40.0)
    vibration         = get("vibration_level",         0.5)
    fault_indicator   = get("fault_indicator",         0.0)

    # ── Engine Temperature ──
    if engine_temp > 110:
        messages.append({"severity": "CRITICAL", "message": "Engine overheating"})
    elif engine_temp > 100:
        messages.append({"severity": "WARNING",  "message": "Engine temperature high"})

    # ── Battery Voltage ──
    if battery_voltage < 11.5:
        messages.append({"severity": "CRITICAL", "message": "Battery voltage critically low"})
    elif battery_voltage < 12.0:
        messages.append({"severity": "WARNING",  "message": "Battery voltage low"})

    # ── Fuel Level ──
    if fuel_level < 10:
        messages.append({"severity": "WARNING",  "message": "Low fuel"})

    # ── Tyre Pressure ──
    if tyre_pressure < 28:
        messages.append({"severity": "CRITICAL", "message": "Tyre pressure critically low"})
    elif tyre_pressure < 30:
        messages.append({"severity": "WARNING",  "message": "Tyre pressure low"})

    # ── Oil Pressure ──
    if oil_pressure < 25:
        messages.append({"severity": "CRITICAL", "message": "Oil pressure critically low"})
    elif oil_pressure < 35:
        messages.append({"severity": "WARNING",  "message": "Oil pressure low"})

    # ── Vibration ──
    if vibration > 2.5:
        messages.append({"severity": "WARNING",  "message": "High vibration detected"})

    # ── Fault Indicator ──
    if fault_indicator == 1:
        messages.append({"severity": "CRITICAL", "message": "Fault indicator triggered"})

    # ── Overall Status ──
    severities = {m["severity"] for m in messages}
    if "CRITICAL" in severities:
        status = "CRITICAL"
    elif "WARNING" in severities:
        status = "WARNING"
    else:
        status = "NORMAL"

    return {
        "diagnostics_status": status,
        "rule_count":         len(messages),
        "messages":           messages,
    }


# ─────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────

app = FastAPI(
    title       ="Cybervehicare — Diagnostics Service",
    description ="Phase 5: Rule-based vehicle diagnostics engine.",
    version     ="1.0.0",
    docs_url    ="/docs",
    redoc_url   ="/redoc",
)


@app.on_event("startup")
async def startup_event():
    print()
    print("═" * 62)
    print("  CYBERVEHICARE · PHASE 5 — DIAGNOSTICS SERVICE")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("═" * 62)
    print()
    print("  Diagnostics Service running on port 8002 ✓")
    print()
    print("  Endpoints:")
    print("    GET  /                      → service info")
    print("    GET  /health                → health check")
    print("    POST /diagnostics/evaluate  → rule-based evaluation")
    print()
    print("  Docs: http://localhost:8002/docs")
    print("═" * 62)
    print()


@app.get("/", summary="Service Information")
def root():
    return {
        "service":   "Cybervehicare Diagnostics Service",
        "phase":     "Phase 5 — Microservices Integration",
        "version":   "1.0.0",
        "port":      8002,
        "endpoints": {
            "GET  /":                     "Service information",
            "GET  /health":               "Health check",
            "POST /diagnostics/evaluate": "Apply rule-based diagnostics to telemetry",
        },
    }


@app.get("/health", summary="Health Check")
def health():
    return {
        "status":    "healthy",
        "service":   "diagnostics",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/diagnostics/evaluate", summary="Evaluate Telemetry with Rule-Based Diagnostics")
def evaluate(payload: TelemetryPayload):
    data       = payload.model_dump()
    vehicle_id = data.get("vehicle_id", "UNKNOWN")

    result = _run_rules(data)

    log.info(
        f"[DIAGNOSTICS] vehicle={vehicle_id}  "
        f"status={result['diagnostics_status']}  "
        f"rules_triggered={result['rule_count']}"
    )

    return {
        "vehicle_id":        vehicle_id,
        "diagnostics_status": result["diagnostics_status"],
        "rule_count":         result["rule_count"],
        "messages":           result["messages"],
        "timestamp":          datetime.now(timezone.utc).isoformat(),
    }

# ─────────────────────────────────────────────
# PROMETHEUS METRICS
# ─────────────────────────────────────────────
try:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except Exception as exc:
    print(f"Prometheus metrics setup skipped: {exc}")

