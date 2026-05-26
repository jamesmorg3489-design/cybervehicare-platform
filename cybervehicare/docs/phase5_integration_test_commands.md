# Cybervehicare — Phase 5 Integration Test Commands

**Phase 5: Microservices Integration**  
Complete commands to start, test, and validate all Phase 5 services in GitHub Codespaces.

---

## Architecture Overview

```
Telemetry Simulator  (scripts/telemetry_simulator.py)
        │
        ▼  POST /telemetry/ingest
┌─────────────────────┐
│  Telemetry Service  │  port 8001   (services/telemetry/main.py)
└──────────┬──────────┘
           │
     ┌─────┼─────────────────────┐
     ▼     ▼                     ▼
  POST   POST                  POST
/predict  /diagnostics/evaluate  (combined)
     │     │                     │
     ▼     ▼                     ▼
┌──────────┐  ┌──────────────┐  ┌─────────────┐
│Prediction│  │  Diagnostics │  │    Alert    │
│   API    │  │   Service    │  │   Service   │
│ port 8000│  │  port 8002   │  │  port 8003  │
└──────────┘  └──────────────┘  └─────────────┘
```

---

## Step 0 — Install Dependencies

Run once from the project root:

```bash
# Phase 4 (Prediction API) dependencies — already installed if Phase 4 is working
pip install -r ml/requirements.txt

# Phase 5 services
pip install -r services/telemetry/requirements.txt
pip install -r services/diagnostics/requirements.txt
pip install -r services/alert/requirements.txt
pip install -r scripts/requirements.txt
```

Or install everything at once:

```bash
pip install fastapi "uvicorn[standard]" requests pydantic pandas
```

---

## Step 1 — Start Prediction API (Phase 4)

Open **Terminal 1**:

```bash
python3 -m uvicorn ml.serve_model:app --host 0.0.0.0 --port 8000 --reload
```

Expected output:
```
CYBERVEHICARE · PHASE 4 — PREDICTION API
Phase 4 Prediction API is running ✓
```

Verify:
```bash
curl http://localhost:8000/health
```

---

## Step 2 — Start Diagnostics Service

Open **Terminal 2**:

```bash
python3 -m uvicorn services.diagnostics.main:app --host 0.0.0.0 --port 8002 --reload
```

Expected output:
```
CYBERVEHICARE · PHASE 5 — DIAGNOSTICS SERVICE
Diagnostics Service running on port 8002 ✓
```

Verify:
```bash
curl http://localhost:8002/health
```

---

## Step 3 — Start Alert Service

Open **Terminal 3**:

```bash
python3 -m uvicorn services.alert.main:app --host 0.0.0.0 --port 8003 --reload
```

Expected output:
```
CYBERVEHICARE · PHASE 5 — ALERT SERVICE
Alert Service running on port 8003 ✓
```

Verify:
```bash
curl http://localhost:8003/health
```

---

## Step 4 — Start Telemetry Service

Open **Terminal 4**:

```bash
python3 -m uvicorn services.telemetry.main:app --host 0.0.0.0 --port 8001 --reload
```

Expected output:
```
CYBERVEHICARE · PHASE 5 — TELEMETRY SERVICE
Telemetry Service running on port 8001 ✓
Pipeline: Telemetry → Prediction → Diagnostics → Alert
```

Verify:
```bash
curl http://localhost:8001/health
```

---

## Step 5 — Run Telemetry Simulator

Open **Terminal 5** (or reuse any terminal):

```bash
python3 scripts/telemetry_simulator.py --limit 25
```

With custom delay:
```bash
python3 scripts/telemetry_simulator.py --limit 50 --delay 1.0
```

Expected output per record:
```
────────────────────────────────────────────────────────────────
  Record   1/25  │  Vehicle: VEH0033
────────────────────────────────────────────────────────────────
  Prediction       : ✅ NORMAL  (confidence: 0.8800)
  Diagnostics      : ⚠️  WARNING  (1 rule(s) triggered)
    • [WARNING] Engine temperature high
  Alert Created    : ⚠️  YES — severity: WARNING
    Message: Vehicle VEH0033: Diagnostics: Engine temperature high.
```

---

## Step 6 — API Verification Commands

### Health Checks

```bash
curl http://localhost:8000/health   # Prediction API
curl http://localhost:8001/health   # Telemetry Service
curl http://localhost:8002/health   # Diagnostics Service
curl http://localhost:8003/health   # Alert Service
```

### Manual Single Telemetry Ingest

```bash
curl -X POST http://localhost:8001/telemetry/ingest \
  -H "Content-Type: application/json" \
  -d @ml/sample_prediction_payload.json
```

### View All Alerts

```bash
curl http://localhost:8003/alerts
```

Pretty-printed:
```bash
curl http://localhost:8003/alerts | python3 -m json.tool
```

### Alerts for a Specific Vehicle

```bash
curl http://localhost:8003/alerts/VEH0033
```

### Latest Telemetry Records

```bash
curl http://localhost:8001/telemetry/latest
```

### Telemetry for a Specific Vehicle

```bash
curl http://localhost:8001/telemetry/VEH0033
```

### Run Diagnostics Directly

```bash
curl -X POST http://localhost:8002/diagnostics/evaluate \
  -H "Content-Type: application/json" \
  -d '{"vehicle_id":"TEST001","engine_temp_c":115,"battery_voltage_v":11.0,"fuel_level_percent":8,"tyre_pressure_psi":27}'
```

Expected: CRITICAL status with multiple rule triggers.

### Clear All Alerts (Reset for Testing)

```bash
curl -X DELETE http://localhost:8003/alerts/clear
```

---

## Swagger UI Docs (interactive)

| Service             | URL                           |
|---------------------|-------------------------------|
| Prediction API      | http://localhost:8000/docs    |
| Telemetry Service   | http://localhost:8001/docs    |
| Diagnostics Service | http://localhost:8002/docs    |
| Alert Service       | http://localhost:8003/docs    |

In GitHub Codespaces, open the **PORTS** tab and click the globe icon next to each port to open in browser.

---

## Expected System Behaviour

| Condition                                    | Prediction | Diagnostics | Alert     |
|----------------------------------------------|------------|-------------|-----------|
| All sensors normal                           | NORMAL     | NORMAL      | Not created |
| engine_temp_c > 100                          | varies     | WARNING     | Created   |
| engine_temp_c > 110                          | varies     | CRITICAL    | Created   |
| battery_voltage_v < 11.5                     | varies     | CRITICAL    | Created   |
| fuel_level_percent < 10                      | varies     | WARNING     | Created   |
| fault_indicator == 1                         | varies     | CRITICAL    | Created   |
| ML model predicts WARNING/CRITICAL           | WARNING+   | any         | Created   |

---

## Screenshot Checklist — Dissertation Evidence

For your dissertation, capture screenshots of:

- [ ] **Terminal 1–4**: All four services starting cleanly (banner + "running ✓" message)
- [ ] **Simulator output**: `python3 scripts/telemetry_simulator.py --limit 25` — at least 3 records with different labels/statuses
- [ ] **Alerts list**: `curl http://localhost:8003/alerts | python3 -m json.tool` — shows alert objects with severity, message, vehicle_id
- [ ] **Swagger UI** for each service (browser: ports 8001, 8002, 8003)
- [ ] **Manual CRITICAL test**: POST to diagnostics with engine_temp_c=115 — shows CRITICAL response
- [ ] **Health endpoints**: All four services returning `"status": "healthy"`
- [ ] **Latest telemetry**: `curl http://localhost:8001/telemetry/latest` — showing stored records
- [ ] **Vehicle filter**: `curl http://localhost:8003/alerts/VEH0033` — vehicle-specific alert retrieval

---

## Troubleshooting

**"Connection refused" on port 8001/8002/8003**
→ Make sure the corresponding service terminal is running.

**Prediction API error in Telemetry Service logs**
→ Make sure `python3 -m uvicorn ml.serve_model:app ...` is running on port 8000 first.

**CSV not found in simulator**
→ Run from the project root directory. The CSV must exist at `data/processed/vehicle_telemetry_cleaned.csv`.

**ModuleNotFoundError for services**
→ Always run commands from the project root (where `ml/`, `services/`, `scripts/` folders live).
