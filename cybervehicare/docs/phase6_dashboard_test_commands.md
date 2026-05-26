# Cybervehicare — Phase 6 Dashboard Test Commands

**Phase 6: Dashboard / Visual Interface**  
Complete commands to install, run, and validate the Streamlit dashboard in GitHub Codespaces.

---

## Architecture

```
Browser  →  Streamlit Dashboard (port 8501)
               │
               ├── GET http://localhost:8000/health          (Prediction API)
               ├── GET http://localhost:8001/telemetry/latest (Telemetry Service)
               ├── GET http://localhost:8001/health
               ├── GET http://localhost:8002/health          (Diagnostics Service)
               ├── GET http://localhost:8003/alerts          (Alert Service)
               └── GET http://localhost:8003/health
```

---

## Step 0 — Install Dashboard Requirements

```bash
python3 -m pip install -r services/dashboard/requirements.txt
```

---

## Step 1 — Start All Backend Services

Open **four separate terminals** and run one command in each:

**Terminal 1 — Prediction API (Phase 4)**
```bash
python3 -m uvicorn ml.serve_model:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Diagnostics Service**
```bash
python3 -m uvicorn services.diagnostics.main:app --host 0.0.0.0 --port 8002 --reload
```

**Terminal 3 — Alert Service**
```bash
python3 -m uvicorn services.alert.main:app --host 0.0.0.0 --port 8003 --reload
```

**Terminal 4 — Telemetry Service**
```bash
python3 -m uvicorn services.telemetry.main:app --host 0.0.0.0 --port 8001 --reload
```

Verify all four are healthy:
```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

---

## Step 2 — Populate Data with Simulator

**Terminal 5:**
```bash
python3 scripts/telemetry_simulator.py --limit 25
```

To generate more data for richer charts:
```bash
python3 scripts/telemetry_simulator.py --limit 50 --delay 0.2
```

---

## Step 3 — Start the Dashboard

**Terminal 6:**
```bash
streamlit run services/dashboard/app.py --server.port 8501 --server.address 0.0.0.0
```

Expected startup output:
```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://0.0.0.0:8501
```

---

## Step 4 — Open Dashboard in GitHub Codespaces

1. Click the **PORTS** tab at the bottom of VS Code.
2. Find port **8501**.
3. Click the **globe icon** (Open in Browser).
4. The dashboard opens in a new browser tab.

> If port 8501 is not listed, click **Add Port** and enter `8501`.

---

## Step 5 — Dashboard Verification

### What you should see

| Section | Expected Content |
|---------|-----------------|
| Header | "Cybervehicare Dashboard" title with subtitle |
| Service Health | 4 cards — all showing "● Healthy" with green border |
| KPI Cards | Non-zero values for records, alerts, critical/warning counts |
| Analytics | 4 charts: severity bar, vehicle bar, prediction pie, diagnostics pie |
| Telemetry Table | Rows with vehicle_id, sensor readings, colour-coded fault_indicator |
| Alerts Table | Rows colour-coded by severity (red=CRITICAL, amber=WARNING, green=NORMAL) |
| Sidebar | Vehicle dropdown populated with real vehicle IDs |

### Test the filters

1. Select a specific **Vehicle ID** from the sidebar dropdown.
2. Both the Alerts table and Telemetry table should filter to that vehicle.
3. Select **CRITICAL** from the severity filter — only critical alerts shown.
4. Click **⟳ Refresh Data** to re-fetch live data from all services.

---

## Step 6 — Additional Test Commands

```bash
# Check alerts directly
curl http://localhost:8003/alerts | python3 -m json.tool

# Check latest telemetry
curl http://localhost:8001/telemetry/latest | python3 -m json.tool

# Filter alerts by vehicle (replace VEH0033 with actual ID)
curl http://localhost:8003/alerts/VEH0033 | python3 -m json.tool

# Clear all alerts and re-run simulator for a fresh demo
curl -X DELETE http://localhost:8003/alerts/clear
python3 scripts/telemetry_simulator.py --limit 25
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Service card shows "Unreachable" | Start the corresponding service terminal |
| Charts are empty | Run the simulator: `python3 scripts/telemetry_simulator.py --limit 25` |
| Dashboard crashes on start | Install requirements: `pip install -r services/dashboard/requirements.txt` |
| Port 8501 not accessible in Codespaces | Go to PORTS tab → Add Port → 8501 → Open in Browser |
| `ModuleNotFoundError: streamlit` | Run `pip install streamlit plotly pandas requests` |
| Tables show "No data" after simulator | Refresh the dashboard (button in sidebar or F5) |

---

## Screenshot Checklist — Dissertation Evidence

Capture screenshots of the following for your dissertation:

- [ ] **Full dashboard overview** — header, health cards, KPI cards all visible
- [ ] **Service health panel** — all 4 cards showing green "● Healthy"
- [ ] **KPI cards** — non-zero values for total records, alerts, critical/warning counts
- [ ] **Alert severity bar chart** — CRITICAL / WARNING / NORMAL bars
- [ ] **Vehicle-wise alert count chart** — multiple vehicle IDs visible
- [ ] **Prediction label pie chart** — NORMAL / WARNING / CRITICAL distribution
- [ ] **Diagnostics status pie chart** — status distribution
- [ ] **Latest telemetry table** — sensor readings, fault_indicator highlighted red where = 1
- [ ] **Alerts table** — colour-coded rows (red CRITICAL, amber WARNING, green NORMAL)
- [ ] **Sidebar vehicle filter** — dropdown showing real vehicle IDs (e.g. VEH0033)
- [ ] **Filtered view** — dashboard filtered to a single vehicle, showing only its data
- [ ] **API Reference panel** — expanded, showing endpoint table and curl commands
- [ ] **Swagger UI** — open http://localhost:8001/docs in browser (Telemetry Service docs)
- [ ] **Terminal output** — simulator running, showing prediction/diagnostics/alert per record

---

## File Reference

| File | Purpose |
|------|---------|
| `services/dashboard/app.py` | Main Streamlit dashboard |
| `services/dashboard/requirements.txt` | streamlit, pandas, requests, plotly |
| `docs/phase6_dashboard_test_commands.md` | This file |
