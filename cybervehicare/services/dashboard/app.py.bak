"""
=============================================================
Cybervehicare — Vehicle Health Monitoring Framework
Phase 6: Streamlit Dashboard
=============================================================
File path  : services/dashboard/app.py
Run command: streamlit run services/dashboard/app.py \
             --server.port 8501 --server.address 0.0.0.0

Fetches live data from:
  Prediction API    → http://localhost:8000
  Telemetry Service → http://localhost:8001
  Diagnostics Svc   → http://localhost:8002
  Alert Service     → http://localhost:8003
=============================================================
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ─────────────────────────────────────────────
# PAGE CONFIG  (must be first Streamlit call)
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Cybervehicare Dashboard",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

SERVICES = {
    "Prediction API":    {"url": "http://localhost:8000", "health": "/health", "port": 8000},
    "Telemetry Service": {"url": "http://localhost:8001", "health": "/health", "port": 8001},
    "Diagnostics Svc":   {"url": "http://localhost:8002", "health": "/health", "port": 8002},
    "Alert Service":     {"url": "http://localhost:8003", "health": "/health", "port": 8003},
}

SEVERITY_COLOURS = {
    "CRITICAL": "#c0392b",
    "WARNING":  "#e67e22",
    "NORMAL":   "#27ae60",
    "UNKNOWN":  "#7f8c8d",
}

PRED_COLOURS = {
    "CRITICAL": "#c0392b",
    "WARNING":  "#e67e22",
    "NORMAL":   "#27ae60",
}

TIMEOUT = 4   # seconds per API call

# Data view mode → (label, telemetry URL)
DATA_VIEW_MODES: dict[str, str] = {
    "Latest 20":          "http://localhost:8001/telemetry/latest?limit=20",
    "Latest 100":         "http://localhost:8001/telemetry/latest?limit=100",
    "Latest 500":         "http://localhost:8001/telemetry/latest?limit=500",
    "All stored records": "http://localhost:8001/telemetry/all",
}

# ─────────────────────────────────────────────
# CUSTOM CSS  — clean academic style
# ─────────────────────────────────────────────

st.markdown(
    """
    <style>
    /* ── Typography ── */
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    /* ── Header ── */
    .cv-header {
        background: linear-gradient(135deg, #0d1b2a 0%, #1b2d45 100%);
        border-left: 5px solid #2980b9;
        padding: 24px 32px 20px 32px;
        border-radius: 6px;
        margin-bottom: 24px;
    }
    .cv-header h1 {
        color: #ecf0f1;
        font-size: 1.85rem;
        font-weight: 600;
        margin: 0 0 4px 0;
        letter-spacing: -0.5px;
    }
    .cv-header p {
        color: #95a5a6;
        font-size: 0.88rem;
        margin: 0;
        font-weight: 300;
    }

    /* ── Section labels ── */
    .cv-section {
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: #7f8c8d;
        border-bottom: 1px solid #ecf0f1;
        padding-bottom: 4px;
        margin: 24px 0 14px 0;
    }

    /* ── Service health card ── */
    .svc-card {
        padding: 14px 18px;
        border-radius: 6px;
        border-left: 4px solid #ccc;
        background: #f8f9fa;
        margin-bottom: 8px;
    }
    .svc-card.healthy  { border-left-color: #27ae60; background: #f0faf4; }
    .svc-card.unhealthy{ border-left-color: #c0392b; background: #fdf4f3; }
    .svc-name  { font-size: 0.82rem; font-weight: 600; color: #2c3e50; }
    .svc-status{ font-size: 0.75rem; font-weight: 500; }
    .svc-url   { font-size: 0.72rem; color: #7f8c8d; font-family: 'IBM Plex Mono', monospace; }
    .status-ok { color: #27ae60; }
    .status-err{ color: #c0392b; }

    /* ── KPI card ── */
    .kpi-card {
        background: #ffffff;
        border: 1px solid #e8ecef;
        border-top: 3px solid #2980b9;
        border-radius: 6px;
        padding: 16px 20px 14px;
        text-align: center;
    }
    .kpi-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1.5px;
                 color: #7f8c8d; font-weight: 500; margin-bottom: 6px; }
    .kpi-value { font-size: 2rem; font-weight: 600; color: #2c3e50; line-height: 1; }
    .kpi-card.red   { border-top-color: #c0392b; }
    .kpi-card.amber { border-top-color: #e67e22; }
    .kpi-card.green { border-top-color: #27ae60; }

    /* ── Warning banner ── */
    .warn-banner {
        background: #fef9e7;
        border: 1px solid #f0ca4d;
        border-left: 4px solid #e67e22;
        border-radius: 4px;
        padding: 10px 16px;
        font-size: 0.82rem;
        color: #7d6608;
        margin-bottom: 10px;
    }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background: #f0f3f7;
    }

    /* ── Tables ── */
    .dataframe thead th {
        background: #0d1b2a !important;
        color: white !important;
        font-size: 0.78rem !important;
        font-weight: 500 !important;
    }
    .dataframe tbody td {
        font-size: 0.78rem !important;
    }

    /* ── Footer ── */
    .cv-footer {
        margin-top: 40px;
        padding-top: 16px;
        border-top: 1px solid #ecf0f1;
        font-size: 0.72rem;
        color: #bdc3c7;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────
# HELPERS — API CALLS
# ─────────────────────────────────────────────

def _get(url: str) -> tuple[bool, Any]:
    """GET request → (success, data|error_str)."""
    try:
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return True, r.json()
    except requests.exceptions.ConnectionError:
        return False, "Service unreachable"
    except requests.exceptions.Timeout:
        return False, "Request timed out"
    except Exception as exc:
        return False, str(exc)


def _check_health(base_url: str, path: str) -> tuple[bool, str]:
    ok, data = _get(base_url + path)
    if ok:
        status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
        return status == "healthy", status
    return False, data


# ─────────────────────────────────────────────
# HELPERS — DATA PROCESSING
# ─────────────────────────────────────────────

def _alerts_df(alerts: list[dict]) -> pd.DataFrame:
    rows = []
    for a in alerts:
        pred = a.get("prediction", {}) or {}
        diag = a.get("diagnostics", {}) or {}
        rows.append({
            "alert_id":           a.get("alert_id", "")[:8] + "…",
            "vehicle_id":         a.get("vehicle_id", ""),
            "severity":           a.get("severity", ""),
            "message":            a.get("message", ""),
            "prediction_label":   pred.get("label", ""),
            "confidence":         pred.get("confidence"),
            "diagnostics_status": diag.get("status", ""),
            "rule_count":         diag.get("rule_count", 0),
            "timestamp":          a.get("timestamp", ""),
        })
    return pd.DataFrame(rows)


def _telemetry_df(records: list[dict]) -> pd.DataFrame:
    COLS = [
        "vehicle_id", "timestamp", "engine_temp_c", "battery_voltage_v",
        "fuel_level_percent", "tyre_pressure_psi", "oil_pressure_psi",
        "fault_indicator", "maintenance_status", "_ingested_at",
    ]
    df = pd.DataFrame(records)
    if df.empty:
        return df
    present = [c for c in COLS if c in df.columns]
    return df[present]


def _severity_colour_map(df: pd.DataFrame, col: str) -> list[str]:
    return [SEVERITY_COLOURS.get(str(v).upper(), "#7f8c8d") for v in df[col]]


# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────

st.markdown(
    """
    <div class="cv-header">
        <h1>Cybervehicare Dashboard</h1>
        <p>Microservices-Based Vehicle Health Monitoring for NGOs and Government Agencies</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Filters & Controls")

    refresh = st.button("⟳  Refresh Data", use_container_width=True, type="primary")

    st.markdown("---")

    # ── Data view mode ────────────────────────
    st.markdown("**Data View Mode**")
    data_view_mode = st.selectbox(
        "Telemetry records to load",
        options=list(DATA_VIEW_MODES.keys()),
        index=0,
        help=(
            "Latest 20 / 100 / 500 — fetch only the most-recent N records.\n"
            "All stored records — fetch everything (may be slower for large datasets)."
        ),
    )

    st.markdown("---")

    # Filters populated after data fetch
    veh_placeholder = st.empty()
    sev_placeholder = st.empty()

    st.markdown("---")
    st.markdown("**Service Ports**")
    for name, cfg in SERVICES.items():
        st.markdown(f"`{cfg['port']}` {name}")

    st.markdown("---")
    st.markdown("**Swagger / API Docs**")
    for name, cfg in SERVICES.items():
        docs_url = f"{cfg['url']}/docs"
        st.markdown(f"[{name} docs]({docs_url})", unsafe_allow_html=False)

    st.markdown("---")
    st.caption(
        "Run the simulator to populate data:\n\n"
        "```\npython3 scripts/telemetry_simulator.py --limit 25\n```"
    )

# ─────────────────────────────────────────────
# FETCH ALL DATA
# ─────────────────────────────────────────────

telemetry_url = DATA_VIEW_MODES[data_view_mode]

with st.spinner("Fetching live data from microservices…"):
    # — Health checks —
    health_results: dict[str, dict] = {}
    for name, cfg in SERVICES.items():
        ok, status = _check_health(cfg["url"], cfg["health"])
        health_results[name] = {
            "healthy": ok,
            "status":  status,
            "url":     cfg["url"],
            "checked": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
        }

    # — Telemetry (respects selected data view mode) —
    tel_ok, tel_data = _get(telemetry_url)
    telemetry_records: list[dict] = []
    total_stored = 0
    if tel_ok and isinstance(tel_data, dict):
        telemetry_records = tel_data.get("records", [])
        total_stored      = tel_data.get("total_stored", len(telemetry_records))

    # — Alerts —
    alt_ok, alt_data = _get("http://localhost:8003/alerts")
    all_alerts: list[dict] = []
    if alt_ok and isinstance(alt_data, dict):
        all_alerts = alt_data.get("alerts", [])

# ─────────────────────────────────────────────
# SERVICE HEALTH PANEL
# ─────────────────────────────────────────────

st.markdown('<div class="cv-section">Service Health</div>', unsafe_allow_html=True)

h_cols = st.columns(4)
for idx, (name, info) in enumerate(health_results.items()):
    cls    = "healthy" if info["healthy"] else "unhealthy"
    symbol = "● Healthy" if info["healthy"] else "● Unreachable"
    s_cls  = "status-ok" if info["healthy"] else "status-err"
    with h_cols[idx]:
        st.markdown(
            f"""
            <div class="svc-card {cls}">
                <div class="svc-name">{name}</div>
                <div class="svc-status {s_cls}">{symbol}</div>
                <div class="svc-url">{info['url']}</div>
                <div class="svc-url">checked {info['checked']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# Warn if critical services are down
if not health_results["Telemetry Service"]["healthy"]:
    st.markdown(
        '<div class="warn-banner">⚠ Telemetry Service (port 8001) is not reachable. '
        "Start it with: <code>python3 -m uvicorn services.telemetry.main:app "
        "--host 0.0.0.0 --port 8001 --reload</code></div>",
        unsafe_allow_html=True,
    )
if not health_results["Alert Service"]["healthy"]:
    st.markdown(
        '<div class="warn-banner">⚠ Alert Service (port 8003) is not reachable. '
        "Start it with: <code>python3 -m uvicorn services.alert.main:app "
        "--host 0.0.0.0 --port 8003 --reload</code></div>",
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────
# SIDEBAR VEHICLE + SEVERITY FILTERS
# (populated after data is fetched)
# ─────────────────────────────────────────────

all_vehicle_ids: list[str] = sorted(set(
    [r.get("vehicle_id", "") for r in telemetry_records if r.get("vehicle_id")]
    + [a.get("vehicle_id", "") for a in all_alerts if a.get("vehicle_id")]
))

with veh_placeholder:
    veh_filter = st.selectbox(
        "Vehicle ID",
        options=["ALL"] + all_vehicle_ids,
        index=0,
    )

with sev_placeholder:
    sev_filter = st.selectbox(
        "Alert Severity",
        options=["ALL", "CRITICAL", "WARNING", "NORMAL"],
        index=0,
    )

# ── Apply filters ─────────────────────────────
filtered_alerts = all_alerts
if veh_filter != "ALL":
    filtered_alerts = [a for a in filtered_alerts if a.get("vehicle_id") == veh_filter]
if sev_filter != "ALL":
    filtered_alerts = [a for a in filtered_alerts if a.get("severity", "").upper() == sev_filter]

filtered_telemetry = telemetry_records
if veh_filter != "ALL":
    filtered_telemetry = [r for r in filtered_telemetry if r.get("vehicle_id") == veh_filter]

# ─────────────────────────────────────────────
# KPI CARDS
# ─────────────────────────────────────────────

st.markdown('<div class="cv-section">Key Performance Indicators</div>', unsafe_allow_html=True)

total_alerts    = len(all_alerts)
critical_alerts = sum(1 for a in all_alerts if a.get("severity", "").upper() == "CRITICAL")
warning_alerts  = sum(1 for a in all_alerts if a.get("severity", "").upper() == "WARNING")

kpi_cols = st.columns(6)

kpis = [
    ("Total Stored",     total_stored,                                             "blue",  ""),
    ("Latest Records",   len(telemetry_records),                                  "blue",  ""),
    ("Total Alerts",     total_alerts,                                             "blue",  ""),
    ("Critical Alerts",  critical_alerts,                                          "red",   ""),
    ("Warning Alerts",   warning_alerts,                                           "amber", ""),
    ("Normal Alerts",    total_alerts - critical_alerts - warning_alerts,          "green", ""),
]

for col, (label, value, colour, _) in zip(kpi_cols, kpis):
    with col:
        st.markdown(
            f"""
            <div class="kpi-card {colour}">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ─────────────────────────────────────────────
# CHARTS
# (all four charts use filtered_alerts so they
#  respond to the Vehicle ID and Severity filters)
# ─────────────────────────────────────────────

st.markdown('<div class="cv-section">Analytics</div>', unsafe_allow_html=True)

# Build prediction / diagnostics counts from FILTERED alerts
pred_counts: dict[str, int] = {}
diag_counts: dict[str, int] = {}
for a in filtered_alerts:
    lbl  = (a.get("prediction", {}) or {}).get("label", "")
    dsts = (a.get("diagnostics", {}) or {}).get("status", "")
    if lbl:  pred_counts[lbl]  = pred_counts.get(lbl, 0) + 1
    if dsts: diag_counts[dsts] = diag_counts.get(dsts, 0) + 1

# Shown when a filter is active but produces no results
_no_data_msg = "No alert data available for the selected filter."

chart_col1, chart_col2 = st.columns(2)

# ── Chart 1: Alert severity distribution ──
with chart_col1:
    st.markdown("**Alert Severity Distribution**")
    if filtered_alerts:
        sev_series = pd.Series(
            [a.get("severity", "UNKNOWN").upper() for a in filtered_alerts]
        ).value_counts().reset_index()
        sev_series.columns = ["Severity", "Count"]
        fig1 = px.bar(
            sev_series,
            x="Severity",
            y="Count",
            color="Severity",
            color_discrete_map=SEVERITY_COLOURS,
            template="plotly_white",
            height=300,
        )
        fig1.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=False,
            font=dict(family="IBM Plex Sans, sans-serif", size=12),
            xaxis_title="",
            yaxis_title="Count",
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
        )
        fig1.update_traces(marker_line_width=0)
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info(_no_data_msg if (veh_filter != "ALL" or sev_filter != "ALL") else
                "No alert data available. Run the simulator to generate alerts.")

# ── Chart 2: Vehicle-wise alert count ──
with chart_col2:
    st.markdown("**Vehicle-wise Alert Count**")
    if filtered_alerts:
        veh_series = pd.Series(
            [a.get("vehicle_id", "UNKNOWN") for a in filtered_alerts]
        ).value_counts().head(15).reset_index()
        veh_series.columns = ["Vehicle ID", "Alerts"]
        fig2 = px.bar(
            veh_series,
            x="Vehicle ID",
            y="Alerts",
            color="Alerts",
            color_continuous_scale=["#3498db", "#e74c3c"],
            template="plotly_white",
            height=300,
        )
        fig2.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=False,
            font=dict(family="IBM Plex Sans, sans-serif", size=12),
            xaxis_title="",
            yaxis_title="Alert Count",
            coloraxis_showscale=False,
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
        )
        fig2.update_traces(marker_line_width=0)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info(_no_data_msg if (veh_filter != "ALL" or sev_filter != "ALL") else
                "No alert data available.")

chart_col3, chart_col4 = st.columns(2)

# ── Chart 3: Prediction label distribution ──
with chart_col3:
    st.markdown("**Prediction Label Distribution**")
    if pred_counts:
        pred_df = pd.DataFrame(
            list(pred_counts.items()), columns=["Label", "Count"]
        )
        fig3 = px.pie(
            pred_df,
            names="Label",
            values="Count",
            color="Label",
            color_discrete_map=PRED_COLOURS,
            hole=0.45,
            template="plotly_white",
            height=300,
        )
        fig3.update_layout(
            margin=dict(l=10, r=10, t=20, b=10),
            font=dict(family="IBM Plex Sans, sans-serif", size=12),
            paper_bgcolor="#ffffff",
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        )
        fig3.update_traces(textinfo="percent+label")
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info(_no_data_msg if (veh_filter != "ALL" or sev_filter != "ALL") else
                "No prediction data available yet.")

# ── Chart 4: Diagnostics status distribution ──
with chart_col4:
    st.markdown("**Diagnostics Status Distribution**")
    if diag_counts:
        diag_df = pd.DataFrame(
            list(diag_counts.items()), columns=["Status", "Count"]
        )
        fig4 = px.pie(
            diag_df,
            names="Status",
            values="Count",
            color="Status",
            color_discrete_map=SEVERITY_COLOURS,
            hole=0.45,
            template="plotly_white",
            height=300,
        )
        fig4.update_layout(
            margin=dict(l=10, r=10, t=20, b=10),
            font=dict(family="IBM Plex Sans, sans-serif", size=12),
            paper_bgcolor="#ffffff",
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        )
        fig4.update_traces(textinfo="percent+label")
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info(_no_data_msg if (veh_filter != "ALL" or sev_filter != "ALL") else
                "No diagnostics data available yet.")

# ─────────────────────────────────────────────
# LATEST TELEMETRY TABLE
# ─────────────────────────────────────────────

st.markdown('<div class="cv-section">Latest Telemetry Records</div>', unsafe_allow_html=True)

if not health_results["Telemetry Service"]["healthy"]:
    st.warning("Telemetry Service (port 8001) is not reachable. Start it first.")
elif filtered_telemetry:
    tel_df = _telemetry_df(filtered_telemetry)
    if not tel_df.empty:
        def _highlight_fault(val):
            if str(val) == "1" or val == 1:
                return "background-color: #fdf4f3; color: #c0392b; font-weight: 600;"
            return ""

        styled = tel_df.style.applymap(
            _highlight_fault, subset=["fault_indicator"] if "fault_indicator" in tel_df.columns else []
        ).format(
            {
                "engine_temp_c":      "{:.1f}",
                "battery_voltage_v":  "{:.2f}",
                "fuel_level_percent": "{:.1f}",
                "tyre_pressure_psi":  "{:.1f}",
                "oil_pressure_psi":   "{:.1f}",
            },
            na_rep="—",
        )
        st.dataframe(styled, use_container_width=True, height=320)
    else:
        st.info("No telemetry columns matched expected schema.")
else:
    st.info(
        "No telemetry records found. "
        "Run: `python3 scripts/telemetry_simulator.py --limit 25`"
    )

# ─────────────────────────────────────────────
# ALERTS TABLE
# ─────────────────────────────────────────────

st.markdown(
    f'<div class="cv-section">Alerts'
    f'{"  —  filtered: " + veh_filter if veh_filter != "ALL" else ""}'
    f'{"  |  severity: " + sev_filter if sev_filter != "ALL" else ""}'
    f"</div>",
    unsafe_allow_html=True,
)

if not health_results["Alert Service"]["healthy"]:
    st.warning("Alert Service (port 8003) is not reachable. Start it first.")
elif filtered_alerts:
    alt_df = _alerts_df(filtered_alerts)

    def _colour_severity(val):
        colours = {
            "CRITICAL": "background-color:#fdf4f3;color:#c0392b;font-weight:600;",
            "WARNING":  "background-color:#fef9e7;color:#9a6700;font-weight:600;",
            "NORMAL":   "background-color:#f0faf4;color:#1e8449;",
        }
        return colours.get(str(val).upper(), "")

    styled_alt = alt_df.style.applymap(
        _colour_severity,
        subset=["severity", "diagnostics_status", "prediction_label"]
        if all(c in alt_df.columns for c in ["severity", "diagnostics_status", "prediction_label"])
        else ["severity"],
    ).format({"confidence": "{:.4f}"}, na_rep="—")

    st.dataframe(styled_alt, use_container_width=True, height=360)
    st.caption(f"{len(filtered_alerts)} alert(s) shown")
else:
    if veh_filter != "ALL" or sev_filter != "ALL":
        st.info("No alerts match the current filter.")
    else:
        st.info(
            "No alerts yet. Run the simulator to generate data:\n\n"
            "`python3 scripts/telemetry_simulator.py --limit 25`"
        )

# ─────────────────────────────────────────────
# MANUAL API TESTING PANEL
# ─────────────────────────────────────────────

with st.expander("🔧 API Reference & Test Commands", expanded=False):
    st.markdown("#### Service Endpoints")

    endpoints = {
        "Prediction API (8000)": [
            ("GET",  "/health",          "Health check"),
            ("GET",  "/metadata",        "Model metadata"),
            ("POST", "/predict",         "Single prediction"),
            ("POST", "/predict/batch",   "Batch prediction"),
        ],
        "Telemetry Service (8001)": [
            ("GET",  "/health",                       "Health check"),
            ("POST", "/telemetry/ingest",             "Ingest record"),
            ("GET",  "/telemetry/latest?limit=20",    "Latest 20 records (default)"),
            ("GET",  "/telemetry/latest?limit=100",   "Latest 100 records"),
            ("GET",  "/telemetry/latest?limit=500",   "Latest 500 records"),
            ("GET",  "/telemetry/all",                "All stored records"),
            ("GET",  "/telemetry/count",              "Record count only"),
            ("GET",  "/telemetry/{vehicle_id}",       "Vehicle records"),
        ],
        "Diagnostics Service (8002)": [
            ("GET",  "/health",                  "Health check"),
            ("POST", "/diagnostics/evaluate",    "Evaluate telemetry"),
        ],
        "Alert Service (8003)": [
            ("GET",    "/health",               "Health check"),
            ("GET",    "/alerts",               "All alerts"),
            ("GET",    "/alerts/{vehicle_id}",  "Vehicle alerts"),
            ("DELETE", "/alerts/clear",         "Clear alerts"),
        ],
    }

    col_a, col_b = st.columns(2)
    for idx, (service, eps) in enumerate(endpoints.items()):
        col = col_a if idx % 2 == 0 else col_b
        with col:
            st.markdown(f"**{service}**")
            for method, path, desc in eps:
                badge = f"`{method}`"
                st.markdown(f"{badge} `{path}` — {desc}")
            st.markdown("")

    st.markdown("#### Quick Test Commands")
    st.code(
        "# Health checks\n"
        "curl http://localhost:8000/health\n"
        "curl http://localhost:8001/health\n"
        "curl http://localhost:8002/health\n"
        "curl http://localhost:8003/health\n\n"
        "# View alerts\n"
        "curl http://localhost:8003/alerts | python3 -m json.tool\n\n"
        "# Latest telemetry (various limits)\n"
        "curl http://localhost:8001/telemetry/latest | python3 -m json.tool\n"
        "curl 'http://localhost:8001/telemetry/latest?limit=100' | python3 -m json.tool\n"
        "curl 'http://localhost:8001/telemetry/latest?limit=500' | python3 -m json.tool\n\n"
        "# All stored records\n"
        "curl http://localhost:8001/telemetry/all | python3 -m json.tool\n\n"
        "# Record count only\n"
        "curl http://localhost:8001/telemetry/count | python3 -m json.tool\n\n"
        "# Clear alerts\n"
        "curl -X DELETE http://localhost:8003/alerts/clear\n\n"
        "# Run simulator\n"
        "python3 scripts/telemetry_simulator.py --limit 25\n"
        "python3 scripts/telemetry_simulator.py --limit 500 --delay 0.05 --balanced-vehicles\n"
        "python3 scripts/telemetry_simulator.py --limit 0 --delay 0.01 --shuffle",
        language="bash",
    )

    st.markdown("#### Swagger UI Links")
    links_col = st.columns(4)
    for i, (name, cfg) in enumerate(SERVICES.items()):
        with links_col[i]:
            st.markdown(f"[{name}]({cfg['url']}/docs)")

# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────

st.markdown(
    f"""
    <div class="cv-footer">
        Cybervehicare · Phase 6 Dashboard &nbsp;|&nbsp;
        Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} &nbsp;|&nbsp;
        Data view: {data_view_mode} &nbsp;|&nbsp;
        Serving NGOs and Government Agencies
    </div>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# AUTO-REFRESH on button click
# ─────────────────────────────────────────────

if refresh:
    st.rerun()
