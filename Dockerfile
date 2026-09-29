# ─────────────────────────────────────────────────
# DiscoveryLab AI — Dockerfile
# Multi-stage build for Streamlit app
# ─────────────────────────────────────────────────

FROM python:3.11-slim AS base

# System deps
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Working dir
WORKDIR /app

# Install Python deps (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/
COPY configs/ ./configs/
COPY data/ ./data/
COPY reports/ ./reports/

# Create dirs
RUN mkdir -p data/papers data/hypotheses data/evidence reports logs

# Expose Streamlit port
EXPOSE 8501

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "src/serving/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]