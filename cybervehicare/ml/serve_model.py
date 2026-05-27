"""
=============================================================
Cybervehicare - Vehicle Health Monitoring Framework
Phase 4: Prediction API / Model Serving
=============================================================
File path  : cybervehicare/ml/serve_model.py
Run command: uvicorn ml.serve_model:app --host 0.0.0.0 --port 8000 --reload
             OR: python ml/serve_model.py
=============================================================

GitHub Codespaces instructions:
  1. Open a terminal in your Codespace.
  2. From the project root, run:
       pip install -r ml/requirements.txt
       uvicorn ml.serve_model:app --host 0.0.0.0 --port 8000 --reload
  3. Codespaces will auto-forward port 8000.
  4. Click "Open in Browser" when prompted, or visit the PORTS tab.

Test commands:
  # Health check
  curl http://localhost:8000/health

  # Metadata
  curl http://localhost:8000/metadata

  # Single prediction
  curl -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" \
    -d @ml/sample_prediction_payload.json

  # Batch prediction
  curl -X POST http://localhost:8000/predict/batch \
    -H "Content-Type: application/json" \
    -d '{"records": [<paste payload here>]}'
=============================================================
"""

from __future__ import annotations

import json
import warnings
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("cybervehicare.serve")

# ─────────────────────────────────────────────
# PATHS  (relative to project root)
# ─────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent.parent   # project root
MODELS_DIR    = BASE_DIR / "ml" / "models"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

MODEL_PATH        = MODELS_DIR    / "maintenance_model.pkl"
FEAT_COLS_PATH    = MODELS_DIR    / "feature_columns.json"
MODEL_META_PATH   = MODELS_DIR    / "model_metadata.json"
PIPE_META_PATH    = PROCESSED_DIR / "pipeline_metadata.json"
SCALER_PATH       = PROCESSED_DIR / "scaler_params.json"

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
LABEL_NAMES = {0: "NORMAL", 1: "WARNING", 2: "CRITICAL"}

RECOMMENDED_ACTIONS = {
    "NORMAL"  : "Vehicle condition is stable. Continue routine monitoring.",
    "WARNING" : "Vehicle requires attention. Schedule inspection soon.",
    "CRITICAL": "High maintenance risk detected. Immediate inspection recommended.",
}

# ─────────────────────────────────────────────
# GLOBAL MODEL STATE
# ─────────────────────────────────────────────
_state: dict[str, Any] = {
    "model"         : None,
    "feature_cols"  : None,
    "model_meta"    : None,
    "pipe_meta"     : None,
    "scaler_params" : None,
    "loaded"        : False,
    "load_error"    : None,
}


# ─────────────────────────────────────────────
# STARTUP LOADER
# ─────────────────────────────────────────────
def _load_artifacts() -> None:
    """Load all model artifacts into global state at startup."""
    try:
        log.info("Loading model artifacts …")

        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model not found at '{MODEL_PATH}'. "
                "Run Phase 3 (ml/train_model.py) first."
            )

        _state["model"]         = joblib.load(MODEL_PATH)
        log.info(f"  ✓ Model loaded            : {MODEL_PATH}")

        with open(FEAT_COLS_PATH)  as f: _state["feature_cols"]  = json.load(f)["feature_columns"]
        log.info(f"  ✓ Feature columns loaded  : {len(_state['feature_cols'])} features")

        with open(MODEL_META_PATH) as f: _state["model_meta"]    = json.load(f)
        log.info(f"  ✓ Model metadata loaded   : {MODEL_META_PATH}")

        if PIPE_META_PATH.exists():
            with open(PIPE_META_PATH)  as f: _state["pipe_meta"]    = json.load(f)
            log.info(f"  ✓ Pipeline metadata loaded: {PIPE_META_PATH}")
        else:
            log.warning(f"  ⚠ pipeline_metadata.json not found at {PIPE_META_PATH} — using defaults")

        if SCALER_PATH.exists():
            with open(SCALER_PATH) as f: _state["scaler_params"] = json.load(f)
            log.info(f"  ✓ Scaler params loaded    : {SCALER_PATH}")
        else:
            log.warning(f"  ⚠ scaler_params.json not found at {SCALER_PATH} — scaling will be skipped")

        _state["loaded"] = True

    except Exception as exc:
        _state["load_error"] = str(exc)
        log.error(f"  ✗ Artifact loading failed : {exc}")
        raise


# ─────────────────────────────────────────────
# FEATURE ENGINEERING
# ─────────────────────────────────────────────
def _engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Recreate the same engineered features used in Phase 2 (exact formulas)."""
    df = df.copy()

    # Exact Phase 2 formulas — epsilon constants prevent division by zero
    df["engine_temp_rpm_ratio"] = (
        df["engine_temp_c"] / (df["engine_rpm"] + 1)
    )
    df["battery_stress_index"] = (
        (df["battery_current_a"].abs() / (df["battery_voltage_v"] + 0.001))
        * (1 - df["battery_health_percent"] / 100)
    )
    df["brake_wear_heat_ratio"] = (
        df["brake_pad_wear_mm"] * df["brake_temp_c"] / 100
    )
    df["fuel_efficiency_score"] = (
        df["vehicle_speed_kph"] / (df["fuel_consumption_lph"] + 0.001)
    )
    df["combined_failure_risk"] = (
        df["engine_failure_imminent"].fillna(0)
        + df["brake_issue_imminent"].fillna(0)
        + df["battery_issue_imminent"].fillna(0)
    )

    df = df.fillna(0)
    return df


def _encode_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """Label-encode categoricals using the same mapping as Phase 2."""
    df = df.copy()

    # Default encoding maps (fallback if pipeline_metadata.json is missing)
    default_maps = {
        "organisation_type": {
            "Government Agency": 0,
            "Emergency Service": 1,
            "NGO"              : 2,
        },
        "vehicle_type": {
            "Community Outreach Vehicle" : 0,
            "Emergency Response Vehicle" : 1,
            "Ambulance"                  : 2,
            "Field Inspection Vehicle"   : 3,
        },
        "failure_type": {
            "No Failure"     : 0,
            "Engine Failure" : 1,
            "Brake Failure"  : 2,
            "Battery Failure": 3,
        },
    }

    # Try to use metadata-sourced maps if available
    # Phase 2 pipeline_metadata.json uses key "categorical_encoders"
    pipe_meta = _state.get("pipe_meta") or {}
    label_encoders = pipe_meta.get("categorical_encoders", {})

    for col, fallback_map in default_maps.items():
        if col not in df.columns:
            df[col] = 0
            continue

        enc_map = label_encoders.get(col, fallback_map)
        # enc_map may be {class_name: index} or list of classes
        if isinstance(enc_map, list):
            enc_map = {v: i for i, v in enumerate(enc_map)}

        df[col] = df[col].map(enc_map).fillna(0).astype(int)

    return df


def _apply_scaler(df: pd.DataFrame) -> pd.DataFrame:
    """Apply StandardScaler using saved mean/scale params from Phase 2.

    Phase 2 scaler_params.json format:
        {
          "feature_names": [...],
          "mean":          [...],
          "scale":         [...]
        }
    """
    scaler_params = _state.get("scaler_params")
    if not scaler_params:
        return df  # skip silently if params not available

    df = df.copy()

    try:
        # ── Phase 2 canonical format ──────────────────────────────────
        if "feature_names" in scaler_params:
            cols   = scaler_params["feature_names"]
            means  = np.array(scaler_params["mean"],  dtype=float)
            scales = np.array(scaler_params["scale"], dtype=float)
            for col, mean, scale in zip(cols, means, scales):
                if col in df.columns and scale != 0:
                    df[col] = (df[col] - mean) / scale

        # ── Legacy fallback: {"columns": [...], "mean_": [...], "scale_": [...]} ──
        elif "columns" in scaler_params:
            cols   = scaler_params["columns"]
            means  = np.array(scaler_params["mean_"],  dtype=float)
            scales = np.array(scaler_params["scale_"], dtype=float)
            for col, mean, scale in zip(cols, means, scales):
                if col in df.columns and scale != 0:
                    df[col] = (df[col] - mean) / scale

        # ── Legacy fallback: {"feature_name": {"mean": x, "scale": y}} ──
        else:
            for col, params in scaler_params.items():
                if col in df.columns:
                    mean  = float(params.get("mean",  0))
                    scale = float(params.get("scale", 1)) or 1.0
                    df[col] = (df[col] - mean) / scale

    except Exception as exc:
        log.warning(f"Scaler application warning (proceeding anyway): {exc}")

    return df


# ─────────────────────────────────────────────
# FULL PREPROCESSING PIPELINE
# ─────────────────────────────────────────────
def _preprocess(raw: dict) -> pd.DataFrame:
    """
    Convert a raw telemetry dict → feature-aligned DataFrame
    ready for model.predict().
    """
    df = pd.DataFrame([raw])

    # ── Drop non-feature columns ──
    drop_cols = ["vehicle_id", "timestamp", "label", "maintenance_status"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

    # ── Fill numeric defaults ──
    numeric_defaults = {
        "odometer_reading"      : 0.0,
        "engine_temp_c"         : 90.0,
        "engine_rpm"            : 1500.0,
        "oil_pressure_psi"      : 50.0,
        "coolant_temp_c"        : 90.0,
        "fuel_level_percent"    : 50.0,
        "fuel_consumption_lph"  : 6.0,
        "vibration_level"       : 0.5,
        "engine_hours"          : 1000.0,
        "brake_fluid_level_psi" : 900.0,
        "brake_pad_wear_mm"     : 5.0,
        "brake_temp_c"          : 80.0,
        "abs_fault_indicator"   : 0.0,
        "battery_voltage_v"     : 12.5,
        "battery_current_a"     : 10.0,
        "battery_temp_c"        : 25.0,
        "battery_charge_percent": 80.0,
        "battery_health_percent": 90.0,
        "vehicle_speed_kph"     : 0.0,
        "gps_latitude"          : 0.0,
        "gps_longitude"         : 0.0,
        "engine_failure_imminent": 0.0,
        "brake_issue_imminent"  : 0.0,
        "battery_issue_imminent": 0.0,
        "tyre_pressure_psi"     : 30.0,
        "fault_indicator"       : 0.0,
    }
    for col, default in numeric_defaults.items():
        if col not in df.columns:
            df[col] = default
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(default)

    # ── Fill categorical defaults ──
    for col, default in [
        ("organisation_type", "Government Agency"),
        ("vehicle_type",      "Community Outreach Vehicle"),
        ("failure_type",      "No Failure"),
    ]:
        if col not in df.columns:
            df[col] = default

    # ── Feature engineering ──
    df = _engineer_features(df)

    # ── Encode categoricals ──
    df = _encode_categoricals(df)

    # ── Apply scaler ──
    df = _apply_scaler(df)

    # ── Align to model feature columns ──
    feature_cols = _state["feature_cols"]
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0.0
    df = df[feature_cols]

    # ── Final numeric cast ──
    df = df.apply(pd.to_numeric, errors="coerce").fillna(0.0)

    return df


# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────
class TelemetryRecord(BaseModel):
    vehicle_id             : str   = Field(default="UNKNOWN")
    timestamp              : str   = Field(default="")
    odometer_reading       : float = Field(default=0.0)
    engine_temp_c          : float = Field(default=90.0)
    engine_rpm             : float = Field(default=1500.0)
    oil_pressure_psi       : float = Field(default=50.0)
    coolant_temp_c         : float = Field(default=90.0)
    fuel_level_percent     : float = Field(default=50.0)
    fuel_consumption_lph   : float = Field(default=6.0)
    vibration_level        : float = Field(default=0.5)
    engine_hours           : float = Field(default=1000.0)
    brake_fluid_level_psi  : float = Field(default=900.0)
    brake_pad_wear_mm      : float = Field(default=5.0)
    brake_temp_c           : float = Field(default=80.0)
    abs_fault_indicator    : float = Field(default=0.0)
    battery_voltage_v      : float = Field(default=12.5)
    battery_current_a      : float = Field(default=10.0)
    battery_temp_c         : float = Field(default=25.0)
    battery_charge_percent : float = Field(default=80.0)
    battery_health_percent : float = Field(default=90.0)
    vehicle_speed_kph      : float = Field(default=0.0)
    gps_latitude           : float = Field(default=0.0)
    gps_longitude          : float = Field(default=0.0)
    engine_failure_imminent: float = Field(default=0.0)
    brake_issue_imminent   : float = Field(default=0.0)
    battery_issue_imminent : float = Field(default=0.0)
    failure_type           : str   = Field(default="No Failure")
    organisation_type      : str   = Field(default="Government Agency")
    vehicle_type           : str   = Field(default="Community Outreach Vehicle")
    tyre_pressure_psi      : float = Field(default=30.0)
    fault_indicator        : float = Field(default=0.0)
    maintenance_status     : str   = Field(default="")

    model_config = {"extra": "allow"}


class BatchRequest(BaseModel):
    records: list[TelemetryRecord]


# ─────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────
app = FastAPI(
    title       ="Cybervehicare — Predictive Maintenance API",
    description ="Phase 4: Serves the trained RandomForest model for vehicle health classification.",
    version     ="1.0.0",
    docs_url    ="/docs",
    redoc_url   ="/redoc",
)


@app.on_event("startup")
async def startup_event():
    print()
    print("═" * 62)
    print("  CYBERVEHICARE · PHASE 4 — PREDICTION API")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("═" * 62)
    _load_artifacts()
    print()
    print("  Phase 4 Prediction API is running ✓")
    print()
    print("  Endpoints:")
    print("    GET  /           → service info")
    print("    GET  /health     → model health check")
    print("    GET  /metadata   → model + feature metadata")
    print("    POST /predict    → single vehicle prediction")
    print("    POST /predict/batch → batch predictions")
    print()
    print("  Docs: http://localhost:8000/docs")
    print("═" * 62)
    print()


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────
@app.get("/", summary="Service Information")
def root():
    return {
        "service"          : "Cybervehicare Predictive Maintenance API",
        "phase"            : "Phase 4 — Model Serving",
        "version"          : "1.0.0",
        "model_status"     : "loaded" if _state["loaded"] else "unavailable",
        "available_endpoints": {
            "GET  /"              : "Service information (this response)",
            "GET  /health"        : "Health check and model status",
            "GET  /metadata"      : "Model metadata and feature columns",
            "POST /predict"       : "Single vehicle telemetry prediction",
            "POST /predict/batch" : "Batch vehicle telemetry predictions",
            "GET  /docs"          : "Interactive Swagger UI",
            "GET  /redoc"         : "ReDoc API documentation",
        },
    }


@app.get("/health", summary="Health Check")
def health():
    if not _state["loaded"]:
        return {
            "status"      : "unhealthy",
            "model_loaded": False,
            "error"       : _state.get("load_error", "Unknown error"),
            "timestamp"   : datetime.now(timezone.utc).isoformat(),
        }

    meta = _state["model_meta"] or {}
    return {
        "status"          : "healthy",
        "model_loaded"    : True,
        "model_path"      : str(MODEL_PATH),
        "model_class"     : meta.get("model_class", "RandomForestClassifier"),
        "n_features"      : len(_state["feature_cols"] or []),
        "n_estimators"    : meta.get("n_estimators"),
        "scaler_available": _state["scaler_params"] is not None,
        "timestamp"       : datetime.now(timezone.utc).isoformat(),
    }


@app.get("/metadata", summary="Model Metadata")
def metadata():
    if not _state["loaded"]:
        raise HTTPException(status_code=503, detail="Model not loaded.")

    return {
        "model_metadata" : _state["model_meta"],
        "label_mapping"  : LABEL_NAMES,
        "feature_columns": _state["feature_cols"],
        "n_features"     : len(_state["feature_cols"] or []),
    }


@app.post("/predict", summary="Single Vehicle Prediction")
def predict(record: TelemetryRecord):
    if not _state["loaded"]:
        raise HTTPException(status_code=503, detail="Model not loaded. Run Phase 3 first.")

    vehicle_id = record.vehicle_id
    raw        = record.model_dump()

    try:
        X = _preprocess(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Preprocessing failed: {exc}")

    clf   = _state["model"]
    proba = clf.predict_proba(X)[0]
    pred_class = int(np.argmax(proba))
    pred_label = LABEL_NAMES[pred_class]
    confidence = float(round(proba[pred_class], 4))

    class_probs = {
        LABEL_NAMES[i]: float(round(p, 4)) for i, p in enumerate(proba)
    }

    log.info(
        f"[PREDICT] vehicle={vehicle_id}  "
        f"label={pred_label}  confidence={confidence:.4f}"
    )

    return {
        "vehicle_id"          : vehicle_id,
        "prediction_label"    : pred_label,
        "prediction_class"    : pred_class,
        "confidence_score"    : confidence,
        "class_probabilities" : class_probs,
        "recommended_action"  : RECOMMENDED_ACTIONS[pred_label],
        "timestamp"           : datetime.now(timezone.utc).isoformat(),
    }


@app.post("/predict/batch", summary="Batch Vehicle Predictions")
def predict_batch(batch: BatchRequest):
    if not _state["loaded"]:
        raise HTTPException(status_code=503, detail="Model not loaded. Run Phase 3 first.")

    if not batch.records:
        raise HTTPException(status_code=422, detail="'records' list is empty.")

    results    = []
    clf        = _state["model"]

    for record in batch.records:
        vehicle_id = record.vehicle_id
        raw        = record.model_dump()

        try:
            X          = _preprocess(raw)
            proba      = clf.predict_proba(X)[0]
            pred_class = int(np.argmax(proba))
            pred_label = LABEL_NAMES[pred_class]
            confidence = float(round(proba[pred_class], 4))
            class_probs = {LABEL_NAMES[i]: float(round(p, 4)) for i, p in enumerate(proba)}

            results.append({
                "vehicle_id"         : vehicle_id,
                "prediction_label"   : pred_label,
                "prediction_class"   : pred_class,
                "confidence_score"   : confidence,
                "class_probabilities": class_probs,
                "recommended_action" : RECOMMENDED_ACTIONS[pred_label],
                "error"              : None,
            })

        except Exception as exc:
            results.append({
                "vehicle_id"         : vehicle_id,
                "prediction_label"   : None,
                "prediction_class"   : None,
                "confidence_score"   : None,
                "class_probabilities": None,
                "recommended_action" : None,
                "error"              : str(exc),
            })

    log.info(f"[BATCH] Processed {len(results)} records.")

    return {
        "total_records": len(results),
        "predictions"  : results,
        "timestamp"    : datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "ml.serve_model:app",
        host    ="0.0.0.0",
        port    =8000,
        reload  =True,
        log_level="info",
    )

# ─────────────────────────────────────────────
# PROMETHEUS METRICS
# ─────────────────────────────────────────────
try:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except Exception as exc:
    print(f"Prometheus metrics setup skipped: {exc}")

