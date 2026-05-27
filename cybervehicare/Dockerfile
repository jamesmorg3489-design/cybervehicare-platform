# =============================================================
# Cybervehicare — Shared Dockerfile
# =============================================================
# One image, five services — the running command is supplied by
# docker-compose.yml so the same layer cache is reused for all
# containers.  The full repository is bind-mounted at /app at
# runtime, so ml/models/ and data/processed/ are always present.
# =============================================================

FROM python:3.11-slim

# ── System packages ───────────────────────────────────────────
# curl  : used by Docker healthchecks
# gcc / g++ : needed by some scikit-learn / numpy wheel builds
#             on non-amd64 platforms (arm64 Macs, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────
WORKDIR /app

# ── Python dependencies ───────────────────────────────────────
# Copy only the requirements files first so Docker can cache this
# layer independently of source-code changes.
COPY requirements*.txt ./

# Install ML / API core requirements
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
        # ── Core ML & data ──
        "scikit-learn>=1.3.0" \
        "pandas>=2.0.0" \
        "numpy>=1.24.0" \
        "joblib>=1.3.0" \
        # ── API serving ──
        "fastapi>=0.111.0" \
        "uvicorn[standard]>=0.29.0" \
        "pydantic>=2.6.0" \
        "httpx>=0.27.0" \
        "requests>=2.31.0" \
        # ── Dashboard ──
        "streamlit>=1.35.0" \
        "plotly>=5.22.0" \
        # ── Utilities ──
        "python-multipart>=0.0.9"

# ── Source code ───────────────────────────────────────────────
# The full repo is bind-mounted at runtime via docker-compose
# volumes, so COPY . . here only matters for plain `docker build`
# / `docker run` usage without compose.
COPY . .

# ── Default port (overridden per-service in docker-compose) ──
EXPOSE 8000 8001 8002 8003 8501

# ── Default command (overridden per-service in docker-compose) ─
CMD ["python3", "-m", "uvicorn", "ml.serve_model:app", "--host", "0.0.0.0", "--port", "8000"]
