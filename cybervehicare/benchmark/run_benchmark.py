"""
Cybervehicare Phase 9 Benchmark Runner

Compares:
- Microservices endpoint: http://localhost:8001/telemetry/ingest
- Monolithic endpoint:   http://localhost:8010/ingest
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

DATASET_PATH = Path("data/processed/vehicle_telemetry_cleaned.csv")
RESULTS_DIR = Path("benchmark/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

LOADS = [10, 50, 100, 500, 1000]

ENDPOINTS = {
    "microservices": "http://localhost:8001/telemetry/ingest",
    "monolith": "http://localhost:8010/ingest",
}


def json_safe(value: Any):
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def load_records() -> list[dict[str, Any]]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")

    df = pd.read_csv(DATASET_PATH)

    if "vehicle_id" not in df.columns:
        df["vehicle_id"] = [f"VEH{i:04d}" for i in range(len(df))]

    records = []
    for _, row in df.iterrows():
        record = {str(k): json_safe(v) for k, v in row.to_dict().items()}
        records.append(record)

    return records


def health_check() -> None:
    checks = {
        "microservices_telemetry": "http://localhost:8001/health",
        "monolith": "http://localhost:8010/health",
    }

    for name, url in checks.items():
        try:
            r = requests.get(url, timeout=5)
            print(f"{name:25s} {r.status_code} {r.text[:80]}")
        except Exception as exc:
            print(f"{name:25s} ERROR {exc}")


def run_test(architecture: str, endpoint: str, records: list[dict[str, Any]], load: int):
    latencies_ms = []
    status_codes = []
    errors = 0
    success = 0

    start_all = time.perf_counter()

    for i in range(load):
        payload = records[i % len(records)]

        start = time.perf_counter()
        try:
            response = requests.post(endpoint, json=payload, timeout=15)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies_ms.append(elapsed_ms)
            status_codes.append(response.status_code)

            if 200 <= response.status_code < 300:
                success += 1
            else:
                errors += 1

        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies_ms.append(elapsed_ms)
            status_codes.append("ERROR")
            errors += 1

    total_time = time.perf_counter() - start_all
    throughput = load / total_time if total_time > 0 else 0

    arr = np.array(latencies_ms, dtype=float)

    return {
        "architecture": architecture,
        "endpoint": endpoint,
        "request_load": load,
        "total_requests": load,
        "successful_requests": success,
        "error_count": errors,
        "success_rate_percent": round((success / load) * 100, 2),
        "avg_latency_ms": round(float(np.mean(arr)), 3),
        "p95_latency_ms": round(float(np.percentile(arr, 95)), 3),
        "min_latency_ms": round(float(np.min(arr)), 3),
        "max_latency_ms": round(float(np.max(arr)), 3),
        "throughput_requests_per_second": round(float(throughput), 3),
        "total_time_seconds": round(float(total_time), 3),
    }


def main():
    print("Cybervehicare Phase 9 Benchmark Runner")
    print("=" * 60)

    records = load_records()
    print(f"Loaded records: {len(records)} from {DATASET_PATH}")

    print("\nHealth checks:")
    health_check()
    print()

    all_summaries = []

    for architecture, endpoint in ENDPOINTS.items():
        rows = []

        for load in LOADS:
            print(f"Running {architecture} benchmark: {load} requests")
            result = run_test(architecture, endpoint, records, load)
            print(json.dumps(result, indent=2))
            rows.append(result)
            all_summaries.append(result)

        out_file = RESULTS_DIR / f"{architecture}_benchmark.csv"
        pd.DataFrame(rows).to_csv(out_file, index=False)
        print(f"Saved: {out_file}")

    summary_file = RESULTS_DIR / "benchmark_summary.csv"
    pd.DataFrame(all_summaries).to_csv(summary_file, index=False)

    print("\nBenchmark complete.")
    print(f"Saved summary: {summary_file}")


if __name__ == "__main__":
    main()
