# Cybervehicare — Phase 8 Prometheus Monitoring Test Commands

## Purpose

This phase adds observability evidence to the Cybervehicare prototype using Prometheus.

Prometheus monitors:
- Prediction API: `prediction:8000/metrics`
- Telemetry Service: `telemetry:8001/metrics`
- Diagnostics Service: `diagnostics:8002/metrics`
- Alert Service: `alert:8003/metrics`

## Start Docker System

```bash
docker compose down --remove-orphans
docker compose up --build -d
docker compose ps
