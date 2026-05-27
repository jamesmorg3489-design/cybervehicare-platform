"""
=============================================================
Cybervehicare — Vehicle Health Monitoring Framework
Telemetry Simulator
=============================================================
File path  : scripts/telemetry_simulator.py

Reads the processed telemetry CSV and sends each row to the
Telemetry Service ingest endpoint.  The Telemetry Service
internally orchestrates the full pipeline:

    Telemetry Service  →  Prediction API
                       →  Diagnostics Service
                       →  Alert Service

This script does NOT call Prediction, Diagnostics, or Alert
APIs directly.  It only POSTs to:

    POST http://localhost:8001/telemetry/ingest

The per-record response from the Telemetry Service is expected
to contain:
    {
        "prediction_label":   "NORMAL" | "WARNING" | "CRITICAL",
        "diagnostics_status": "NORMAL" | "WARNING" | "CRITICAL",
        "alert_raised":       true | false,
        ...
    }
These fields are used to build the final summary breakdown.

Usage
-----
  # Default — first 25 rows (original behaviour)
  python3 scripts/telemetry_simulator.py --limit 25

  # All rows, no limit
  python3 scripts/telemetry_simulator.py --limit 0

  # Shuffle rows so many vehicle IDs appear throughout the run
  python3 scripts/telemetry_simulator.py --limit 500 --delay 0.05 --shuffle

  # Balanced: ~equal records per vehicle ID
  python3 scripts/telemetry_simulator.py --limit 500 --delay 0.05 --balanced-vehicles

  # All rows, shuffled
  python3 scripts/telemetry_simulator.py --limit 0 --delay 0.01 --shuffle

  # Custom ingest URL
  python3 scripts/telemetry_simulator.py --limit 25 --url http://localhost:8001/telemetry/ingest
=============================================================
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests

# ─────────────────────────────────────────────
# DEFAULTS
# ─────────────────────────────────────────────

DEFAULT_CSV     = Path("data/processed/vehicle_telemetry_cleaned.csv")
DEFAULT_URL     = "http://localhost:8001/telemetry/ingest"
DEFAULT_LIMIT   = 25
DEFAULT_DELAY   = 0.5
TIMEOUT         = 10   # seconds per HTTP request


# ─────────────────────────────────────────────
# ARGUMENT PARSING
# ─────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="telemetry_simulator.py",
        description="Cybervehicare Telemetry Simulator — streams vehicle records to the Telemetry Service.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
  # Original behaviour — send first 25 rows
  python3 scripts/telemetry_simulator.py --limit 25

  # Send all rows
  python3 scripts/telemetry_simulator.py --limit 0

  # Shuffle rows before sending (mixed vehicle IDs throughout)
  python3 scripts/telemetry_simulator.py --limit 500 --delay 0.05 --shuffle

  # Balanced: roughly equal records per vehicle ID
  python3 scripts/telemetry_simulator.py --limit 500 --delay 0.05 --balanced-vehicles

  # All rows, shuffled
  python3 scripts/telemetry_simulator.py --limit 0 --delay 0.01 --shuffle

  # Both flags (shuffle within each vehicle group, then interleave)
  python3 scripts/telemetry_simulator.py --limit 200 --shuffle --balanced-vehicles

  # Custom ingest endpoint
  python3 scripts/telemetry_simulator.py --limit 25 --url http://localhost:8001/telemetry/ingest
        """,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        metavar="N",
        help=(
            "Number of records to send. "
            "Use 0 to send ALL rows in the CSV. "
            f"(default: {DEFAULT_LIMIT})"
        ),
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        metavar="SECONDS",
        help=(
            "Sleep time in seconds between records. "
            "Use 0 for no delay. "
            f"(default: {DEFAULT_DELAY})"
        ),
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        metavar="PATH",
        help=f"Path to the processed telemetry CSV. (default: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=DEFAULT_URL,
        metavar="URL",
        help=f"Telemetry Service ingest endpoint. (default: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--shuffle",
        action="store_true",
        default=False,
        help=(
            "Shuffle the dataset before selecting records. "
            "Ensures many different vehicle IDs appear throughout the run "
            "rather than whichever vehicles sort first in the CSV. "
            "Uses random_state=42 for reproducibility."
        ),
    )
    parser.add_argument(
        "--balanced-vehicles",
        action="store_true",
        default=False,
        dest="balanced_vehicles",
        help=(
            "Select records evenly across all vehicle_id values. "
            "Example: --limit 500 with 50 vehicles → ~10 records per vehicle. "
            "If a vehicle has fewer records than its quota, all its rows are used. "
            "Records are interleaved in round-robin order across vehicle IDs."
        ),
    )

    return parser


# ─────────────────────────────────────────────
# RECORD SELECTION
# ─────────────────────────────────────────────

def _select_records(
    df: pd.DataFrame,
    limit: int,
    shuffle: bool,
    balanced_vehicles: bool,
) -> pd.DataFrame:
    """
    Return the ordered DataFrame that will be sent row-by-row.

    Selection priority:
      1. --balanced-vehicles  → even sample across vehicle_id values,
                                 optionally shuffled within each group.
      2. --shuffle only       → shuffle whole DataFrame, then head(limit).
      3. Neither flag         → original behaviour: df.head(limit).

    limit=0 means "use all rows" in every path.
    """
    if balanced_vehicles:
        return _balanced_sample(df, limit, shuffle)

    if shuffle:
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    if limit > 0:
        df = df.head(limit)

    return df.reset_index(drop=True)


def _balanced_sample(
    df: pd.DataFrame,
    limit: int,
    shuffle: bool,
) -> pd.DataFrame:
    """
    Return a DataFrame with records spread evenly across vehicle_id values.

    Algorithm
    ---------
    1. Group by vehicle_id.
    2. Calculate quota per vehicle:
           per_vehicle = ceil(effective_limit / num_vehicles)
       where effective_limit = len(df) when limit == 0.
    3. For each vehicle group, optionally shuffle then take up to quota rows.
    4. Interleave groups in round-robin order so vehicle IDs alternate
       throughout the run (better for live dashboard visualisation).
    5. Hard-trim to exactly limit rows (ceil may overshoot by a few).
    """
    vid_col = "vehicle_id"

    if vid_col not in df.columns:
        print(
            f"[WARN] Column '{vid_col}' not found — "
            "falling back to shuffle/sequential selection.",
            file=sys.stderr,
        )
        if shuffle:
            df = df.sample(frac=1, random_state=42).reset_index(drop=True)
        return df.head(limit).reset_index(drop=True) if limit > 0 else df.reset_index(drop=True)

    groups: dict[str, pd.DataFrame] = {
        vid: grp.copy()
        for vid, grp in df.groupby(vid_col, sort=True)   # sort=True → deterministic order
    }
    num_vehicles   = len(groups)
    effective_limit = limit if limit > 0 else len(df)
    per_vehicle    = math.ceil(effective_limit / num_vehicles)

    # Build per-vehicle slices
    slices: list[list[dict]] = []
    for vid in sorted(groups.keys()):
        grp = groups[vid]
        if shuffle:
            grp = grp.sample(frac=1, random_state=42).reset_index(drop=True)
        slices.append(grp.head(per_vehicle).to_dict(orient="records"))

    # Round-robin interleave
    interleaved: list[dict] = []
    max_depth = max(len(s) for s in slices)
    for depth in range(max_depth):
        for s in slices:
            if depth < len(s):
                interleaved.append(s[depth])
            if effective_limit > 0 and len(interleaved) >= effective_limit:
                break
        if effective_limit > 0 and len(interleaved) >= effective_limit:
            break

    result = pd.DataFrame(interleaved)
    if limit > 0:
        result = result.head(limit)

    return result.reset_index(drop=True)


# ─────────────────────────────────────────────
# JSON SAFETY HELPER
# ─────────────────────────────────────────────

def _json_safe(value):
    """Convert pandas/numpy values to JSON-serialisable Python scalars."""
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    return value


# ─────────────────────────────────────────────
# HTTP HELPER
# ─────────────────────────────────────────────

def _post_record(url: str, payload: dict) -> tuple[bool, dict]:
    """POST a single record; return (success, response_dict)."""
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        return True, resp.json()
    except requests.exceptions.ConnectionError:
        return False, {"error": f"Connection refused — is the Telemetry Service running at {url}?"}
    except requests.exceptions.Timeout:
        return False, {"error": "Request timed out"}
    except Exception as exc:
        return False, {"error": str(exc)}


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:

    # ── Load CSV ──────────────────────────────
    csv_path: Path = args.csv
    if not csv_path.exists():
        print(f"[ERROR] CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] Loading CSV : {csv_path}")
    df = pd.read_csv(csv_path)
    total_rows = len(df)
    print(f"[INFO] Rows in CSV : {total_rows}")

    # ── Select records ────────────────────────
    df = _select_records(
        df,
        limit=args.limit,
        shuffle=args.shuffle,
        balanced_vehicles=args.balanced_vehicles,
    )
    n_records = len(df)

    vid_col = "vehicle_id"
    unique_vehicles = (
        df[vid_col].nunique() if vid_col in df.columns else "?"
    )

    # ── Header ───────────────────────────────
    strategy_parts: list[str] = []
    if args.balanced_vehicles:
        strategy_parts.append("balanced-vehicles")
    if args.shuffle:
        strategy_parts.append("shuffled")
    if not strategy_parts:
        strategy_parts.append("sequential (default)")

    print(f"[INFO] Records to send  : {n_records}  "
          f"(limit={'all' if args.limit == 0 else args.limit})")
    print(f"[INFO] Unique vehicles  : {unique_vehicles}")
    print(f"[INFO] Selection mode   : {' + '.join(strategy_parts)}")
    print(f"[INFO] Delay per record : {args.delay}s")
    print(f"[INFO] Ingest endpoint  : {args.url}")
    print("-" * 60)

    # ── Per-record counters ───────────────────
    sent          = 0
    errors        = 0
    alerts_raised = 0
    pred_counts:  dict[str, int] = defaultdict(int)
    diag_counts:  dict[str, int] = defaultdict(int)
    seen_vehicles: set[str]      = set()

    # ── Send loop ─────────────────────────────
    for i, row in df.iterrows():
        # Convert NaN / numpy scalars so JSON serialisation is clean
        record: dict = {k: _json_safe(v) for k, v in row.items()}

        vehicle_id = str(record.get(vid_col, "?"))
        seen_vehicles.add(vehicle_id)
        seq = sent + errors + 1   # 1-based display counter

        print(f"[{seq}/{n_records}] Sending vehicle={vehicle_id} ...", end="  ")

        ok, resp = _post_record(args.url, record)

        if not ok:
            errors += 1
            print(f"ERROR — {resp.get('error', 'unknown')}")
        else:
            sent += 1

            # Read pipeline results — supports both flat and nested responses
            prediction  = resp.get("prediction",  {}) or {}
            diagnostics = resp.get("diagnostics", {}) or {}
            alert_obj   = resp.get("alert",        {}) or {}

            pred_label = str(
                resp.get("prediction_label")
                or prediction.get("prediction_label")
                or "UNKNOWN"
            ).upper()
            diag_status = str(
                resp.get("diagnostics_status")
                or diagnostics.get("diagnostics_status")
                or "UNKNOWN"
            ).upper()
            alert = bool(
                resp.get("alert_raised")
                if "alert_raised" in resp
                else alert_obj.get("alert_created", False)
            )

            pred_counts[pred_label]  += 1
            diag_counts[diag_status] += 1
            if alert:
                alerts_raised += 1

            alert_flag = "🔔 ALERT" if alert else ""
            print(f"OK  pred={pred_label:<8} diag={diag_status:<8} {alert_flag}")

        if args.delay > 0:
            time.sleep(args.delay)

    # ── Final summary ─────────────────────────
    print("\n" + "=" * 60)
    print("  Simulator complete")
    print("=" * 60)
    print(f"  Records sent             : {sent}")
    print(f"  Errors                   : {errors}")
    print(f"  Alerts raised            : {alerts_raised}")
    print(f"  Unique vehicles in run   : {len(seen_vehicles)}")

    if pred_counts:
        print("\n  Prediction Label Breakdown")
        for label in sorted(pred_counts):
            print(f"    {label:<12} : {pred_counts[label]}")

    if diag_counts:
        print("\n  Diagnostics Status Breakdown")
        for status in sorted(diag_counts):
            print(f"    {status:<12} : {diag_counts[status]}")

    print("=" * 60)


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = _build_parser()
    args   = parser.parse_args()
    run(args)
