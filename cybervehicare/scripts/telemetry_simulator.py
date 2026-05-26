"""
=============================================================
Cybervehicare — Vehicle Health Monitoring Framework
Phase 5: Telemetry Simulator
=============================================================
File path  : scripts/telemetry_simulator.py
Run command: python3 scripts/telemetry_simulator.py --limit 25

Description:
  Reads data/processed/vehicle_telemetry_cleaned.csv and sends
  records one by one to the Telemetry Service (port 8001).
  Prints a clean summary for each record.

Arguments:
  --limit N      Number of records to send (default: 25)
  --delay N      Seconds between records (default: 0.5)
  --csv PATH     Path to CSV file (default: data/processed/vehicle_telemetry_cleaned.csv)
  --url URL      Telemetry service URL (default: http://localhost:8001/telemetry/ingest)
=============================================================
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import requests

# ─────────────────────────────────────────────
# DEFAULTS
# ─────────────────────────────────────────────

DEFAULT_CSV   = "data/processed/vehicle_telemetry_cleaned.csv"
DEFAULT_URL   = "http://localhost:8001/telemetry/ingest"
DEFAULT_LIMIT = 25
DEFAULT_DELAY = 0.5

# ─────────────────────────────────────────────
# COLUMN DTYPES  (ensure correct JSON types)
# ─────────────────────────────────────────────

FLOAT_COLS = [
    "odometer_reading", "engine_temp_c", "engine_rpm", "oil_pressure_psi",
    "coolant_temp_c", "fuel_level_percent", "fuel_consumption_lph",
    "vibration_level", "engine_hours", "brake_fluid_level_psi",
    "brake_pad_wear_mm", "brake_temp_c", "abs_fault_indicator",
    "battery_voltage_v", "battery_current_a", "battery_temp_c",
    "battery_charge_percent", "battery_health_percent",
    "vehicle_speed_kph", "gps_latitude", "gps_longitude",
    "engine_failure_imminent", "brake_issue_imminent",
    "battery_issue_imminent", "tyre_pressure_psi", "fault_indicator",
]

STR_COLS = [
    "vehicle_id", "timestamp", "failure_type",
    "organisation_type", "vehicle_type", "maintenance_status",
]


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

DIVIDER      = "─" * 64
BOLD_DIVIDER = "═" * 64

SEVERITY_ICON = {
    "NORMAL":   "✅",
    "WARNING":  "⚠️ ",
    "CRITICAL": "🚨",
    "UNKNOWN":  "❓",
}


def _icon(label: str) -> str:
    return SEVERITY_ICON.get(str(label).upper(), "❓")


def _load_csv(path: str) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        print(f"\n  ✗ CSV file not found: {csv_path}")
        print(
            "    Make sure you have run Phase 2 (data pipeline) and the file exists at:\n"
            f"    {csv_path.resolve()}\n"
        )
        sys.exit(1)

    df = pd.read_csv(csv_path, low_memory=False)
    print(f"  ✓ Loaded {len(df):,} rows from {csv_path}")
    return df


def _json_safe(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _record_to_dict(row: pd.Series) -> dict:
    record: dict = {}
    for col in FLOAT_COLS:
        if col in row.index:
            try:
                record[col] = float(row[col]) if pd.notna(row[col]) else 0.0
            except (TypeError, ValueError):
                record[col] = 0.0
    for col in STR_COLS:
        if col in row.index:
            record[col] = str(row[col]) if pd.notna(row[col]) else ""
    # Include any extra columns
    for col in row.index:
        if col not in record:
            val = row[col]
            record[col] = _json_safe(val)
    return record


def _send_record(url: str, record: dict) -> dict | None:
    try:
        response = requests.post(url, json=record, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.HTTPError as exc:
        print(f"    ✗ HTTP error: {exc}")
        return None
    except Exception as exc:
        print(f"    ✗ Unexpected error: {exc}")
        return None


def _print_result(i: int, total: int, result: dict):
    vehicle_id         = result.get("vehicle_id", "UNKNOWN")
    prediction         = result.get("prediction", {})
    diagnostics        = result.get("diagnostics", {})
    alert              = result.get("alert", {})

    pred_label         = str(prediction.get("prediction_label", "UNKNOWN")).upper()
    confidence         = prediction.get("confidence_score", 0.0)
    diag_status        = str(diagnostics.get("diagnostics_status", "UNKNOWN")).upper()
    alert_created      = alert.get("alert_created", False)
    alert_severity     = str(alert.get("severity", "")).upper()
    diag_rule_count    = diagnostics.get("rule_count", 0)
    diag_messages      = diagnostics.get("messages", [])

    print(DIVIDER)
    print(f"  Record {i:>3}/{total}  │  Vehicle: {vehicle_id}")
    print(DIVIDER)
    print(f"  Prediction       : {_icon(pred_label)} {pred_label}  (confidence: {confidence:.4f})")
    print(f"  Diagnostics      : {_icon(diag_status)} {diag_status}  ({diag_rule_count} rule(s) triggered)")
    if diag_messages:
        for msg in diag_messages:
            sev = msg.get("severity", "")
            txt = msg.get("message", "")
            print(f"    • [{sev}] {txt}")
    if alert_created:
        print(f"  Alert Created    : {_icon(alert_severity)} YES — severity: {alert_severity}")
        print(f"    Message: {alert.get('message', '')}")
    else:
        print(f"  Alert Created    : — No  (all systems NORMAL)")
    print()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Cybervehicare Phase 5 — Telemetry Simulator",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT,
        help=f"Number of records to send (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--delay", type=float, default=DEFAULT_DELAY,
        help=f"Seconds between records (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--csv", type=str, default=DEFAULT_CSV,
        help=f"Path to telemetry CSV (default: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--url", type=str, default=DEFAULT_URL,
        help=f"Telemetry Service ingest URL (default: {DEFAULT_URL})",
    )
    args = parser.parse_args()

    print()
    print(BOLD_DIVIDER)
    print("  CYBERVEHICARE · PHASE 5 — TELEMETRY SIMULATOR")
    print(BOLD_DIVIDER)
    print()
    print(f"  Target URL : {args.url}")
    print(f"  CSV file   : {args.csv}")
    print(f"  Records    : {args.limit}")
    print(f"  Delay      : {args.delay}s between records")
    print()

    # ── Load CSV ──
    df = _load_csv(args.csv)
    df = df.head(args.limit)
    total = len(df)
    print(f"  Sending {total} record(s) …")
    print()

    # ── Check connectivity ──
    try:
        r = requests.get("http://localhost:8001/health", timeout=5)
        r.raise_for_status()
        print("  ✓ Telemetry Service (port 8001) is reachable")
    except Exception:
        print("  ✗ Cannot reach Telemetry Service at http://localhost:8001")
        print("    → Start it first: python3 -m uvicorn services.telemetry.main:app --host 0.0.0.0 --port 8001 --reload")
        print()
        sys.exit(1)

    print()

    # ── Stats ──
    sent          = 0
    errors        = 0
    alerts_raised = 0
    labels        : dict[str, int] = {}
    diag_statuses : dict[str, int] = {}

    # ── Send loop ──
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        record = _record_to_dict(row)
        result = _send_record(args.url, record)

        if result is None:
            print(f"  Record {i:>3}/{total}  │  ✗ Connection error — is the Telemetry Service running?")
            errors += 1
        else:
            sent += 1
            pred_label   = str(result.get("prediction", {}).get("prediction_label", "UNKNOWN")).upper()
            diag_status  = str(result.get("diagnostics", {}).get("diagnostics_status", "UNKNOWN")).upper()
            alert_created = result.get("alert", {}).get("alert_created", False)
            if alert_created:
                alerts_raised += 1
            labels[pred_label]         = labels.get(pred_label, 0) + 1
            diag_statuses[diag_status] = diag_statuses.get(diag_status, 0) + 1
            _print_result(i, total, result)

        if i < total:
            time.sleep(args.delay)

    # ── Summary ──
    print()
    print(BOLD_DIVIDER)
    print("  SIMULATION COMPLETE — SUMMARY")
    print(BOLD_DIVIDER)
    print(f"  Records sent    : {sent}")
    print(f"  Errors          : {errors}")
    print(f"  Alerts raised   : {alerts_raised}")
    print()
    print("  Prediction Label Breakdown:")
    for label, count in sorted(labels.items()):
        print(f"    {_icon(label)} {label:<10} : {count}")
    print()
    print("  Diagnostics Status Breakdown:")
    for status, count in sorted(diag_statuses.items()):
        print(f"    {_icon(status)} {status:<10} : {count}")
    print()
    print("  Useful follow-up commands:")
    print("    curl http://localhost:8003/alerts             # view all alerts")
    print("    curl http://localhost:8001/telemetry/latest   # latest 20 records")
    print(BOLD_DIVIDER)
    print()


if __name__ == "__main__":
    main()
