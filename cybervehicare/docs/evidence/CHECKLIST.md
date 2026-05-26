# CyberVehicare — Evidence Checklist

This file tracks all screenshots and artefacts required for the dissertation appendix.

## Platform Running Evidence
- [ ] `01_docker_ps.png` — `docker ps` showing all containers running
- [ ] `02_docker_compose_up.png` — Terminal output of `docker compose up --build`
- [ ] `03_dashboard_home.png` — Dashboard homepage (http://localhost:8501)
- [ ] `04_dashboard_health_status.png` — Health status distribution pie chart
- [ ] `05_dashboard_latest_telemetry.png` — Latest telemetry data table
- [ ] `06_dashboard_alerts.png` — Active alerts panel

## API / Gateway Evidence
- [ ] `07_gateway_health.png` — GET http://localhost:8000/health
- [ ] `08_telemetry_ingest.png` — POST to telemetry service (Postman or curl)
- [ ] `09_prediction_response.png` — POST to prediction service with JSON body
- [ ] `10_alert_list.png` — GET alerts endpoint response

## ML Model Evidence
- [ ] `11_model_training_output.png` — Training accuracy, precision, recall printout
- [ ] `12_confusion_matrix.png` — Model confusion matrix (generated graph)
- [ ] `13_feature_importance.png` — Feature importance bar chart

## Prometheus Evidence
- [ ] `14_prometheus_targets.png` — http://localhost:9090/targets showing all services
- [ ] `15_prometheus_metrics.png` — Sample metric query in Prometheus UI

## Benchmark Evidence
- [ ] `16_benchmark_latency_csv.png` — benchmark/results/latency_results.csv
- [ ] `17_latency_comparison_graph.png` — Micro vs monolith latency chart
- [ ] `18_throughput_graph.png` — Requests/sec comparison
- [ ] `19_scalability_graph.png` — Latency vs concurrent users
- [ ] `20_recovery_time_graph.png` — Recovery time comparison
- [ ] `21_fault_detection_graph.png` — Fault detection responsiveness

## Fault Injection Evidence
- [ ] `22_fault_injection_terminal.png` — Fault injection test output
- [ ] `23_fault_recovery_log.png` — Service recovery log

## Database Evidence
- [ ] `24_db_schema.png` — PostgreSQL schema (pgAdmin or psql \dt)
- [ ] `25_db_records.png` — Sample records in vehicle_telemetry table

## Files to Include in Appendix
- `ml/model/training_report.txt` — Full classification report
- `benchmark/results/latency_results.csv`
- `benchmark/results/throughput_results.csv`
- `benchmark/results/scalability_results.csv`
- `benchmark/results/recovery_results.csv`
- `benchmark/results/fault_detection_results.csv`
