# syntax=docker/dockerfile:1

# --- Base image ---
# Slim Python 3.12: small, stable (avoids local 3.14 pydantic warnings).
FROM python:3.12-slim AS runtime

# --- Metadata ---
LABEL org.opencontainers.image.title="deep-research-agent"
LABEL org.opencontainers.image.description="Research question → Deep Agent → S3 report"

# --- Environment ---
# PYTHONDONTWRITEBYTECODE: no .pyc clutter
# PYTHONUNBUFFERED: logs show up immediately in `docker logs`
# PIP_NO_CACHE_DIR: smaller image
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# --- System deps (minimal) ---
# ca-certificates: HTTPS to Gemini / Tavily / AWS
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --- Install Python deps first (better layer cache) ---
COPY pyproject.toml README.md ./
COPY src ./src
COPY helpers ./helpers
COPY tools ./tools
COPY api ./api

RUN pip install --upgrade pip \
    && pip install .

# --- Runtime dirs ---
RUN mkdir -p /app/reports \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

# Staging only; durable reports go to S3
VOLUME ["/app/reports"]

# Flexible entry: `python -m <module> ...`
# Agent one-shot:  docker run ... src.agent --secrets-overwrite "question"
# Worker:          docker run ... src.worker --secrets-overwrite
ENTRYPOINT ["python", "-m"]
CMD ["src.agent", "--secrets-overwrite", "--help"]
