# Cybervehicare — Phase 9 Monolithic Baseline and Benchmark Testing

## Purpose

This phase compares the Cybervehicare microservices architecture against a monolithic baseline.

## Services

- Microservices endpoint: `http://localhost:8001/telemetry/ingest`
- Monolith endpoint: `http://localhost:8010/ingest`

## Start all services

```bash
docker compose down --remove-orphans
docker compose up --build -d
docker compose ps
curl http://localhost:8001/health
curl http://localhost:8010/health
