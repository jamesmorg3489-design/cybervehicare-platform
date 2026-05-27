# Cybervehicare — Phase 7 Docker / Containerisation Test Commands

**Phase 7: Docker Containerisation**  
Complete commands to build, run, verify, and demonstrate the fully-Dockerised
Cybervehicare system in GitHub Codespaces (or any Docker host).

---

## Architecture — Containerised

```
Host Browser  →  Streamlit Dashboard  (localhost:8501)
                        │
               Docker network: cybervehicare_default
                        │
          ┌─────────────┼─────────────────────┐
          ▼             ▼                     ▼
  http://prediction:8000  http://diagnostics:8002  http://alert:8003
  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
  │  prediction      │  │  diagnostics     │  │  alert           │
  │  port 8000       │  │  port 8002       │  │  port 8003       │
  └──────────────────┘  └──────────────────┘  └──────────────────┘
          ▲
          │  http://telemetry:8001
  ┌──────────────────┐
  │  telemetry       │
  │  port 8001       │
  └──────────────────┘
```

All five containers share one Docker image built from the project root `Dockerfile`.
The full repository is bind-mounted at `/app` inside every container, so
`ml/models/`, `data/processed/`, and `scripts/` are always accessible.

---

## New / Changed Files — Phase 7

| File | Purpose |
|------|---------|
| `Dockerfile` | Single shared image for all services |
| `docker-compose.yml` | Wires all 5 services with env-vars, health-checks, depends_on |
| `.dockerignore` | Keeps build context lean |
| `services/telemetry/main.py` | **Updated** — reads `PREDICTION_URL`, `DIAGNOSTICS_URL`, `ALERT_URL` from env (localhost defaults kept for local dev) |
| `services/dashboard/app.py` | **Updated** — reads `*_API_URL` env vars (localhost defaults kept) |
| `docs/phase7_docker_test_commands.md` | This file |

> **No existing application logic was changed.** Only URL constants were made
> env-var-overridable. All Phase 5 / Phase 6 local commands continue to work.

---

## Prerequisites

```bash
# Verify Docker is available
docker --version
docker compose version
```

> In GitHub Codespaces, Docker is available by default via the Dev Container.
> If `docker compose` is not found, try `docker-compose` (older hyphenated form).

---

## Step 0 — Apply the env-var patch to app.py

Before building, open `services/dashboard/app.py` and replace the hardcoded
URL constants near the top with the env-var-aware block below.

**Find this (exact wording may vary):**
```python
PREDICTION_API  = "http://localhost:8000"
TELEMETRY_API   = "http://localhost:8001"
DIAGNOSTICS_API = "http://localhost:8002"
ALERT_API       = "http://localhost:8003"
```

**Replace with:**
```python
import os

PREDICTION_API  = os.getenv("PREDICTION_API_URL",  "http://localhost:8000")
TELEMETRY_API   = os.getenv("TELEMETRY_API_URL",   "http://localhost:8001")
DIAGNOSTICS_API = os.getenv("DIAGNOSTICS_API_URL", "http://localhost:8002")
ALERT_API       = os.getenv("ALERT_API_URL",       "http://localhost:8003")
```

And apply the same pattern to `services/telemetry/main.py` URL constants:

```python
import os

PREDICTION_URL  = os.getenv("PREDICTION_URL",  "http://localhost:8000/predict")
DIAGNOSTICS_URL = os.getenv("DIAGNOSTICS_URL", "http://localhost:8002/diagnostics/evaluate")
ALERT_URL       = os.getenv("ALERT_URL",       "http://localhost:8003/alerts/create")
```

> **Local dev still works** — when the env vars are not set, the localhost URLs
> are used automatically. Nothing breaks for Phase 5 / Phase 6.

---

## Step 1 — Build and Start All Containers

Run from the **project root** (where `docker-compose.yml` lives):

```bash
docker compose up --build
```

What happens:
1. Docker builds one shared image from `Dockerfile`.
2. Five containers start: `prediction`, `diagnostics`, `alert`, `telemetry`, `dashboard`.
3. Health-checks gate startup order: Telemetry waits for Prediction / Diagnostics / Alert;
   Dashboard waits for all four.
4. Stream logs appear for all services.

**Detached (background) mode:**
```bash
docker compose up --build -d
```

Expected terminal output (detached):
```
[+] Building ...
[+] Running 5/5
 ✔ Container cybervehicare_prediction   Healthy
 ✔ Container cybervehicare_diagnostics  Healthy
 ✔ Container cybervehicare_alert        Healthy
 ✔ Container cybervehicare_telemetry    Healthy
 ✔ Container cybervehicare_dashboard    Started
```

---

## Step 2 — Verify All Containers Are Running

```bash
docker compose ps
```

Expected output:
```
NAME                        IMAGE                  COMMAND                  SERVICE      STATUS          PORTS
cybervehicare_alert         cybervehicare-alert    "python3 -m uvicorn …"   alert        Up (healthy)    0.0.0.0:8003->8003/tcp
cybervehicare_dashboard     cybervehicare-dash…    "streamlit run servi…"   dashboard    Up (healthy)    0.0.0.0:8501->8501/tcp
cybervehicare_diagnostics   cybervehicare-diag…    "python3 -m uvicorn …"   diagnostics  Up (healthy)    0.0.0.0:8002->8002/tcp
cybervehicare_prediction    cybervehicare-pred…    "python3 -m uvicorn …"   prediction   Up (healthy)    0.0.0.0:8000->8000/tcp
cybervehicare_telemetry     cybervehicare-tele…    "python3 -m uvicorn …"   telemetry    Up (healthy)    0.0.0.0:8001->8001/tcp
```

---

## Step 3 — Health-Check All Services

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

Each should return `"status": "healthy"`.

Pretty-printed:
```bash
for port in 8000 8001 8002 8003; do
  echo "── Port $port ──"
  curl -s http://localhost:$port/health | python3 -m json.tool
done
```

---

## Step 4 — Run the Telemetry Simulator Against Docker

The simulator posts to `http://localhost:8001/telemetry/ingest`, which is the
Telemetry container's exposed port.  Run it from the **host** terminal
(not inside a container) exactly as in Phase 5 / Phase 6:

**Quick test (25 records):**
```bash
python3 scripts/telemetry_simulator.py --limit 25
```

**Richer charts (50 records):**
```bash
python3 scripts/telemetry_simulator.py --limit 50 --delay 0.2
```

**Balanced 500-record dataset:**
```bash
python3 scripts/telemetry_simulator.py --limit 500 --delay 0.05 --balanced-vehicles
```

**All rows, shuffled (stress test):**
```bash
python3 scripts/telemetry_simulator.py --limit 0 --delay 0.01 --shuffle
```

You can also run the simulator **inside** the telemetry container:
```bash
docker compose exec telemetry \
    python3 scripts/telemetry_simulator.py --limit 25
```

---

## Step 5 — Open the Dashboard

In GitHub Codespaces:
1. Click the **PORTS** tab.
2. Find port **8501**.
3. Click the **globe icon** → dashboard opens in your browser.

Locally:
```
http://localhost:8501
```

---

## Step 6 — View Service Logs

```bash
# All services, follow mode
docker compose logs -f

# Single service
docker compose logs telemetry
docker compose logs prediction
docker compose logs diagnostics
docker compose logs alert
docker compose logs dashboard

# Last 50 lines for telemetry
docker compose logs --tail=50 telemetry
```

---

## Step 7 — Manual API Tests Against Docker

```bash
# Single manual ingest
curl -X POST http://localhost:8001/telemetry/ingest \
  -H "Content-Type: application/json" \
  -d @ml/sample_prediction_payload.json | python3 -m json.tool

# All alerts
curl http://localhost:8003/alerts | python3 -m json.tool

# Latest 100 telemetry records
curl 'http://localhost:8001/telemetry/latest?limit=100' | python3 -m json.tool

# All stored records
curl http://localhost:8001/telemetry/all | python3 -m json.tool

# Record count only
curl http://localhost:8001/telemetry/count | python3 -m json.tool

# Alerts for a specific vehicle
curl http://localhost:8003/alerts/VEH0033 | python3 -m json.tool

# Direct diagnostics test (CRITICAL scenario)
curl -X POST http://localhost:8002/diagnostics/evaluate \
  -H "Content-Type: application/json" \
  -d '{"vehicle_id":"TEST001","engine_temp_c":115,"battery_voltage_v":11.0,"fuel_level_percent":8,"tyre_pressure_psi":27}' \
  | python3 -m json.tool

# Clear all alerts
curl -X DELETE http://localhost:8003/alerts/clear
```

---

## Step 8 — Swagger UI (Interactive Docs)

| Service | URL |
|---------|-----|
| Prediction API | http://localhost:8000/docs |
| Telemetry Service | http://localhost:8001/docs |
| Diagnostics Service | http://localhost:8002/docs |
| Alert Service | http://localhost:8003/docs |

In Codespaces: PORTS tab → click globe icon next to each port → append `/docs` to the URL.

---

## Step 9 — Stop / Restart / Rebuild

```bash
# Stop and remove all containers (data in memory is lost — expected)
docker compose down

# Rebuild image and restart (after code changes)
docker compose up --build

# Restart a single service without rebuild
docker compose restart telemetry

# Stop without removing containers (keeps state)
docker compose stop

# Start previously stopped containers
docker compose start
```

---

## Environment Variables Reference

These are injected by `docker-compose.yml` and override the localhost defaults:

| Container | Variable | Value in Docker | Default (local dev) |
|-----------|----------|-----------------|---------------------|
| `telemetry` | `PREDICTION_URL` | `http://prediction:8000/predict` | `http://localhost:8000/predict` |
| `telemetry` | `DIAGNOSTICS_URL` | `http://diagnostics:8002/diagnostics/evaluate` | `http://localhost:8002/diagnostics/evaluate` |
| `telemetry` | `ALERT_URL` | `http://alert:8003/alerts/create` | `http://localhost:8003/alerts/create` |
| `dashboard` | `PREDICTION_API_URL` | `http://prediction:8000` | `http://localhost:8000` |
| `dashboard` | `TELEMETRY_API_URL` | `http://telemetry:8001` | `http://localhost:8001` |
| `dashboard` | `DIAGNOSTICS_API_URL` | `http://diagnostics:8002` | `http://localhost:8002` |
| `dashboard` | `ALERT_API_URL` | `http://alert:8003` | `http://localhost:8003` |

---

## Local Development (unchanged from Phase 5 / Phase 6)

All existing local commands still work exactly as before:

```bash
# Terminal 1
python3 -m uvicorn ml.serve_model:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2
python3 -m uvicorn services.diagnostics.main:app --host 0.0.0.0 --port 8002 --reload

# Terminal 3
python3 -m uvicorn services.alert.main:app --host 0.0.0.0 --port 8003 --reload

# Terminal 4
python3 -m uvicorn services.telemetry.main:app --host 0.0.0.0 --port 8001 --reload

# Terminal 5
streamlit run services/dashboard/app.py --server.port 8501 --server.address 0.0.0.0

# Terminal 6
python3 scripts/telemetry_simulator.py --limit 25
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `docker compose` not found | Try `docker-compose` (hyphenated) or update Docker |
| Build fails on `pip install` | Check internet access; in Codespaces use a Dev Container with network |
| Container exits immediately | `docker compose logs <service>` to see the error |
| Port already in use | Stop local services first, or change host port in `docker-compose.yml` |
| Health-check failing for telemetry | Ensure prediction / diagnostics / alert are healthy first |
| Dashboard shows "Unreachable" | Verify all four backend containers are running: `docker compose ps` |
| Dashboard shows stale data | Click **⟳ Refresh Data** in the sidebar |
| Simulator CSV not found | Run simulator from the project root; CSV must be at `data/processed/vehicle_telemetry_cleaned.csv` |
| `ModuleNotFoundError` inside container | Rebuild: `docker compose up --build` |
| Changes to Python files not reflected | With bind-mount the change is immediate; restart container if uvicorn `--reload` is not set |

---

## Screenshot Checklist — Dissertation Evidence (Phase 7)

Capture screenshots of the following:

- [ ] **`docker compose up --build` output** — terminal showing all 5 services building and starting
- [ ] **`docker compose ps` output** — all 5 containers showing `Up (healthy)`
- [ ] **Health curl loop** — `for port in 8000 8001 8002 8003; do curl ...` showing all healthy
- [ ] **`docker compose logs telemetry`** — showing ingestion pipeline log lines
- [ ] **Simulator running against Docker** — `python3 scripts/telemetry_simulator.py --limit 25` output
- [ ] **Dashboard in browser (via Docker)** — full view with health cards all green
- [ ] **KPI cards** — non-zero values confirming data flowed through the Docker pipeline
- [ ] **Alert severity chart** — bars for CRITICAL / WARNING / NORMAL
- [ ] **Vehicle-wise chart** — multiple vehicle IDs (use `--balanced-vehicles` simulator flag)
- [ ] **`docker compose down` output** — clean shutdown of all 5 containers
- [ ] **`docker-compose.yml` open in editor** — showing service definitions and env vars
- [ ] **`Dockerfile` open in editor** — showing the single shared image definition
- [ ] **Swagger UI** — `http://localhost:8001/docs` in browser showing Telemetry Service API

---

## File Reference

| File | Purpose |
|------|---------|
| `Dockerfile` | Shared Python 3.11-slim image with all dependencies |
| `docker-compose.yml` | Five-service orchestration with health-checks and env vars |
| `.dockerignore` | Excludes cache, notebooks, git, raw data from build context |
| `services/telemetry/main.py` | Telemetry orchestrator — Phase 6 endpoints + env-var URLs |
| `services/dashboard/app.py` | Streamlit dashboard — env-var backend URLs |
| `docs/phase7_docker_test_commands.md` | This file |
