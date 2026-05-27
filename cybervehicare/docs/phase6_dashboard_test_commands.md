python3 scripts/telemetry_simulator.py --limit 500 --delay 0.05 --balanced-vehicles# Cybervehicare — Phase 6 Dashboard Test Commands

**Phase 6: Dashboard / Visual Interface**  
Complete commands to install, run, and validate the Streamlit dashboard in GitHub Codespaces.

---

## Architecture

```
Browser  →  Streamlit Dashboard (port 8501)
               │
               ├── GET http://localhost:8000/health              (Prediction API)
               ├── GET http://localhost:8001/telemetry/latest    (Telemetry Service — variable limit)
               ├── GET http://localhost:8001/telemetry/all       (Telemetry Service — all records)
               ├── GET http://localhost:8001/telemetry/count     (Telemetry Service — count only)
               ├── GET http://localhost:8001/health
               ├── GET http://localhost:8002/health              (Diagnostics Service)
               ├── GET http://localhost:8003/alerts              (Alert Service)
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

**Terminal 5 — Basic (25 records):**
```bash
python3 scripts/telemetry_simulator.py --limit 25
```

**Richer charts (50 records with a small delay):**
```bash
python3 scripts/telemetry_simulator.py --limit 50 --delay 0.2
```

**Large dataset — balanced across vehicle IDs (500 records):**
```bash
python3 scripts/telemetry_simulator.py --limit 500 --delay 0.05 --balanced-vehicles
```
> Use this when testing the **Latest 500** or **All stored records** data view modes.
> `--balanced-vehicles` distributes records evenly across all vehicle IDs so that
> vehicle-level charts show multiple vehicles rather than skewing to the first few.

**Maximum dataset — all rows, shuffled:**
```bash
python3 scripts/telemetry_simulator.py --limit 0 --delay 0.01 --shuffle
```
> Sends every row in the CSV in random order. Good for stress-testing the **All stored records**
> view. Note: the Telemetry Service store is capped at 20 000 records (oldest are dropped first).

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
| Sidebar | Vehicle dropdown, severity dropdown, **Data View Mode** dropdown |

### Data View Mode (sidebar)

The **Data View Mode** dropdown controls how many telemetry records the dashboard fetches
and displays in the Latest Telemetry Records table and the KPI "Latest Records" counter.

| Mode | Endpoint called | Notes |
|------|----------------|-------|
| Latest 20 | `GET /telemetry/latest?limit=20` | Default; fast |
| Latest 100 | `GET /telemetry/latest?limit=100` | Good for most demos |
| Latest 500 | `GET /telemetry/latest?limit=500` | Requires ≥500 ingested records |
| All stored records | `GET /telemetry/all` | May be slower for large datasets |

> **"Total Stored"** KPI always reflects the total number of records in the Telemetry
> Service store, regardless of the selected view mode.
> **"Latest Records"** KPI shows how many records were returned by the selected mode.

### Graph filtering behaviour

All four analytics charts (**Alert Severity Distribution**, **Vehicle-wise Alert Count**,
**Prediction Label Distribution**, **Diagnostics Status Distribution**) now respond to the
**Vehicle ID** and **Alert Severity** sidebar filters.

- Select a specific **Vehicle ID** → all charts narrow to that vehicle's alerts only.
- Select a severity level (e.g. **CRITICAL**) → charts show only critical alerts.
- Both filters can be combined.
- When a filter produces no results, charts are hidden and a message is shown:
  *"No alert data available for the selected filter."*
- Select **ALL** in both dropdowns to return to the full unfiltered view.

### Test the filters

1. Select a specific **Vehicle ID** from the sidebar dropdown.
2. All four charts, the Alerts table, and the Telemetry table should update to that vehicle.
3. Select **CRITICAL** from the severity filter — only critical alerts are shown in charts and table.
4. Click **⟳ Refresh Data** to re-fetch live data from all services.

---

## Step 6 — Additional Test Commands

```bash
# Check alerts directly
curl http://localhost:8003/alerts | python3 -m json.tool

# Check latest telemetry (default 20)
curl http://localhost:8001/telemetry/latest | python3 -m json.tool

# Check latest 100 records
curl 'http://localhost:8001/telemetry/latest?limit=100' | python3 -m json.tool

# Check latest 500 records
curl 'http://localhost:8001/telemetry/latest?limit=500' | python3 -m json.tool

# All stored records
curl http://localhost:8001/telemetry/all | python3 -m json.tool

# Record count only (lightweight)
curl http://localhost:8001/telemetry/count | python3 -m json.tool

# Filter alerts by vehicle (replace VEH0033 with actual ID)
curl http://localhost:8003/alerts/VEH0033 | python3 -m json.tool

# Clear all alerts and re-run simulator for a fresh demo
curl -X DELETE http://localhost:8003/alerts/clear
python3 scripts/telemetry_simulator.py --limit 25

# Large balanced dataset (good for testing Latest 500 / All stored records)
python3 scripts/telemetry_simulator.py --limit 500 --delay 0.05 --balanced-vehicles

# All rows, shuffled (stress-test for All stored records mode)
python3 scripts/telemetry_simulator.py --limit 0 --delay 0.01 --shuffle
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Service card shows "Unreachable" | Start the corresponding service terminal |
| Charts are empty | Run the simulator: `python3 scripts/telemetry_simulator.py --limit 25` |
| Charts do not change when filtering | Ensure you are on the latest `app.py` (Phase 6 fix); charts now use `filtered_alerts` |
| Dashboard crashes on start | Install requirements: `pip install -r services/dashboard/requirements.txt` |
| "Latest Records" stuck at 20 after 500 sent | Change **Data View Mode** in sidebar to "Latest 500" or "All stored records" |
| "All stored records" is slow | Expected for large datasets; use "Latest 500" for faster loads |
| Port 8501 not accessible in Codespaces | Go to PORTS tab → Add Port → 8501 → Open in Browser |
| `ModuleNotFoundError: streamlit` | Run `pip install streamlit plotly pandas requests` |
| Tables show "No data" after simulator | Refresh the dashboard (button in sidebar or F5) |

---

## Screenshot Checklist — Dissertation Evidence

Capture screenshots of the following for your dissertation:

- [ ] **Full dashboard overview** — header, health cards, KPI cards all visible
- [ ] **Service health panel** — all 4 cards showing green "● Healthy"
- [ ] **KPI cards** — non-zero values for total records, alerts, critical/warning counts
- [ ] **Data View Mode** — sidebar showing "Latest 500" or "All stored records" selected
- [ ] **KPI "Latest Records"** — showing >20 after selecting a larger data view mode
- [ ] **Alert severity bar chart** — CRITICAL / WARNING / NORMAL bars
- [ ] **Vehicle-wise alert count chart** — multiple vehicle IDs visible
- [ ] **Prediction label pie chart** — NORMAL / WARNING / CRITICAL distribution
- [ ] **Diagnostics status pie chart** — status distribution
- [ ] **Latest telemetry table** — sensor readings, fault_indicator highlighted red where = 1
- [ ] **Alerts table** — colour-coded rows (red CRITICAL, amber WARNING, green NORMAL)
- [ ] **Sidebar vehicle filter** — dropdown showing real vehicle IDs (e.g. VEH0033)
- [ ] **Filtered view** — dashboard filtered to a single vehicle; all four charts updated
- [ ] **Filtered charts empty state** — filter to a vehicle with no alerts; message shown
- [ ] **API Reference panel** — expanded, showing endpoint table and curl commands
- [ ] **Swagger UI** — open http://localhost:8001/docs in browser (Telemetry Service docs)
- [ ] **Terminal output** — simulator running, showing prediction/diagnostics/alert per record

---

## File Reference

| File | Purpose |
|------|---------|
| `services/dashboard/app.py` | Main Streamlit dashboard |
| `services/telemetry/main.py` | Telemetry Service — ingest, store, query endpoints |
| `services/dashboard/requirements.txt` | streamlit, pandas, requests, plotly |
| `docs/phase6_dashboard_test_commands.md` | This file |
