"""
Cybervehicare — Monolithic Baseline Application
Port: 8010

This baseline combines telemetry ingestion, prediction, diagnostics,
alerting, and in-memory storage inside one FastAPI application.
It is used for Phase 9 benchmarking against the microservices architecture.
"""

from __future__ import annotations

import os
import time
import json
import glob
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

import joblib
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from prometheus_fastapi_instrumentator import Instrumentator
except Exception:
    Instrumentator = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("cybervehicare.monolith")

app = FastAPI(
    title="Cybervehicare Monolithic Baseline",
    description="Single-application baseline for benchmarking against microservices.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if Instrumentator:
    try:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    except Exception as exc:
        print(f"Prometheus metrics skipped for monolith: {exc}")

_store: deque[dict[str, Any]] = deque(maxlen=20_000)
_alerts: deque[dict[str, Any]] = deque(maxlen=20_000)

MODEL_PATH = os.getenv("MODEL_PATH", "ml/models/maintenance_model.pkl")
_model = None
_feature_columns: list[str] = []


class TelemetryRecord(BaseModel):
    vehicle_id: Optional[str] = "UNKNOWN"
    timestamp: Optional[str] = None
    engine_temp_c: Optional[float] = None
    battery_voltage_v: Optional[float] = None
    fuel_level_percent: Optional[float] = None
    tyre_pressure_psi: Optional[float] = None
    oil_pressure_psi: Optional[float] = None
    fault_indicator: Optional[float] = None
    maintenance_status: Optional[str] = None

    model_config = {"extra": "allow"}


def _normalise_label(value: Any) -> str:
    text = str(value).strip().upper()
    if text in {"0", "NORMAL", "NO_FAILURE", "NO FAILURE", "HEALTHY"}:
        return "NORMAL"
    if text in {"1", "WARNING", "WARN", "MEDIUM"}:
        return "WARNING"
    if text in {"2", "CRITICAL", "CRIT", "HIGH", "FAILURE"}:
        return "CRITICAL"
    if "CRIT" in text or "FAIL" in text:
        return "CRITICAL"
    if "WARN" in text:
        return "WARNING"
    return "NORMAL"


def _load_feature_columns() -> list[str]:
    candidates = [
        "ml/models/feature_columns.json",
        "ml/models/model_metadata.json",
        "data/reports/feature_columns.json",
        "data/reports/model_metadata.json",
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            data = json.load(open(path, "r"))
            if isinstance(data, list):
                return [str(x) for x in data]
            if isinstance(data, dict):
                for key in ["feature_columns", "features", "model_features", "columns"]:
                    if key in data and isinstance(data[key], list):
                        return [str(x) for x in data[key]]
        except Exception:
            pass
    return []


def _load_model():
    global _model, _feature_columns
    if _model is not None:
        return _model

    possible = [MODEL_PATH] + glob.glob("ml/models/*.pkl")
    for path in possible:
        if os.path.exists(path):
            try:
                _model = joblib.load(path)
                _feature_columns = _load_feature_columns()
                if not _feature_columns and hasattr(_model, "feature_names_in_"):
                    _feature_columns = [str(x) for x in list(_model.feature_names_in_)]
                log.info(f"Loaded ML model from {path}")
                log.info(f"Feature columns: {len(_feature_columns)}")
                return _model
            except Exception as exc:
                log.warning(f"Could not load model {path}: {exc}")

    log.warning("No ML model loaded. Using rule-based fallback prediction.")
    return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _predict(record: dict[str, Any]) -> dict[str, Any]:
    model = _load_model()

    if model is not None:
        try:
            cols = _feature_columns
            if not cols:
                cols = [
                    k for k, v in record.items()
                    if isinstance(v, (int, float)) and not str(k).startswith("_")
                ]

            row = {col: _safe_float(record.get(col), 0.0) for col in cols}
            X = pd.DataFrame([row], columns=cols)

            raw_pred = model.predict(X)[0]
            label = _normalise_label(raw_pred)

            confidence = None
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(X)[0]
                confidence = float(max(probs))

            return {
                "prediction_label": label,
                "confidence": confidence,
                "model_source": "loaded_pickle_model",
            }
        except Exception as exc:
            log.warning(f"Model prediction failed, fallback used: {exc}")

    # fallback rule-based prediction
    engine_temp = _safe_float(record.get("engine_temp_c"), 90)
    battery_v = _safe_float(record.get("battery_voltage_v"), 12.5)
    fuel = _safe_float(record.get("fuel_level_percent"), 50)
    tyre = _safe_float(record.get("tyre_pressure_psi"), 32)
    fault = _safe_float(record.get("fault_indicator"), 0)

    if engine_temp >= 110 or battery_v <= 11.3 or fuel <= 8 or tyre <= 26 or fault >= 1:
        label = "CRITICAL"
        confidence = 0.90
    elif engine_temp >= 100 or battery_v <= 11.8 or fuel <= 15 or tyre <= 29:
        label = "WARNING"
        confidence = 0.75
    else:
        label = "NORMAL"
        confidence = 0.70

    return {
        "prediction_label": label,
        "confidence": confidence,
        "model_source": "rule_based_fallback",
    }


def _diagnostics(record: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    rules = []
    status = "NORMAL"

    engine_temp = _safe_float(record.get("engine_temp_c"), 90)
    battery_v = _safe_float(record.get("battery_voltage_v"), 12.5)
    fuel = _safe_float(record.get("fuel_level_percent"), 50)
    tyre = _safe_float(record.get("tyre_pressure_psi"), 32)
    oil = _safe_float(record.get("oil_pressure_psi"), 40)
    fault = _safe_float(record.get("fault_indicator"), 0)

    def mark(level: str, rule: str):
        nonlocal status
        rules.append({"severity": level, "rule": rule})
        if level == "CRITICAL":
            status = "CRITICAL"
        elif level == "WARNING" and status != "CRITICAL":
            status = "WARNING"

    if engine_temp >= 110:
        mark("CRITICAL", "Engine temperature critically high")
    elif engine_temp >= 100:
        mark("WARNING", "Engine temperature above safe range")

    if battery_v <= 11.3:
        mark("CRITICAL", "Battery voltage critically low")
    elif battery_v <= 11.8:
        mark("WARNING", "Battery voltage low")

    if fuel <= 8:
        mark("CRITICAL", "Fuel level critically low")
    elif fuel <= 15:
        mark("WARNING", "Fuel level low")

    if tyre <= 26:
        mark("CRITICAL", "Tyre pressure critically low")
    elif tyre <= 29:
        mark("WARNING", "Tyre pressure low")

    if oil and oil <= 20:
        mark("CRITICAL", "Oil pressure critically low")
    elif oil and oil <= 30:
        mark("WARNING", "Oil pressure low")

    if fault >= 1:
        mark("CRITICAL", "Fault indicator active")

    pred_label = prediction.get("prediction_label", "NORMAL")
    if pred_label == "CRITICAL":
        mark("CRITICAL", "ML prediction indicates critical maintenance risk")
    elif pred_label == "WARNING":
        mark("WARNING", "ML prediction indicates warning maintenance risk")

    return {
        "diagnostics_status": status,
        "rules_triggered": rules,
        "rule_count": len(rules),
    }


def _alert(record: dict[str, Any], prediction: dict[str, Any], diagnostics: dict[str, Any]) -> dict[str, Any]:
    severity = diagnostics.get("diagnostics_status") or prediction.get("prediction_label") or "NORMAL"

    if severity not in {"WARNING", "CRITICAL"}:
        return {
            "alert_created": False,
            "severity": "NORMAL",
            "message": "No alert generated for normal telemetry.",
        }

    alert = {
        "alert_id": f"ALT-{len(_alerts)+1:06d}",
        "vehicle_id": record.get("vehicle_id", "UNKNOWN"),
        "severity": severity,
        "message": f"{severity} vehicle health condition detected",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prediction_label": prediction.get("prediction_label"),
        "diagnostics_status": diagnostics.get("diagnostics_status"),
    }
    _alerts.append(alert)

    return {
        "alert_created": True,
        "severity": severity,
        "alert": alert,
    }


@app.get("/")
async def root():
    return {
        "service": "Cybervehicare Monolithic Baseline",
        "status": "running",
        "port": 8010,
        "records_stored": len(_store),
        "alerts_stored": len(_alerts),
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "monolith",
        "records_stored": len(_store),
        "alerts_stored": len(_alerts),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/ingest")
async def ingest(record: TelemetryRecord):
    start = time.perf_counter()
    raw = record.model_dump()
    raw["_ingested_at"] = datetime.now(timezone.utc).isoformat()

    prediction = _predict(raw)
    diagnostics = _diagnostics(raw, prediction)
    alert = _alert(raw, prediction, diagnostics)

    stored = {
        **raw,
        "prediction": prediction,
        "diagnostics": diagnostics,
        "alert": alert,
    }
    _store.append(stored)

    latency_ms = round((time.perf_counter() - start) * 1000, 3)

    return {
        "architecture": "monolithic",
        "vehicle_id": raw.get("vehicle_id"),
        "prediction": prediction,
        "diagnostics": diagnostics,
        "alert": alert,
        "prediction_label": prediction.get("prediction_label"),
        "diagnostics_status": diagnostics.get("diagnostics_status"),
        "alert_created": bool(alert.get("alert_created")),
        "latency_ms": latency_ms,
        "total_stored": len(_store),
    }


@app.get("/records/latest")
async def latest(limit: int = Query(default=20, ge=1)):
    records = list(_store)[-limit:]
    return {
        "total_stored": len(_store),
        "returned": len(records),
        "records": records,
    }


@app.get("/records/all")
async def all_records():
    records = list(_store)
    return {
        "total_stored": len(_store),
        "returned": len(records),
        "records": records,
    }


@app.get("/alerts")
async def alerts():
    return {
        "total_alerts": len(_alerts),
        "alerts": list(_alerts),
    }


@app.delete("/clear")
async def clear():
    _store.clear()
    _alerts.clear()
    return {"cleared": True}
