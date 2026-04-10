# ============================================
# Stage 1: Builder
# ============================================
FROM python:3.9-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================
# Stage 2: Runtime
# ============================================
FROM python:3.9-slim AS runtime

WORKDIR /app

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY --chown=appuser:appgroup . .

RUN mkdir -p /app/data /app/logs && \
    chown -R appuser:appgroup /app/data /app/logs

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" || exit 1

LABEL org.opencontainers.image.title="Idle-Accelerator" \
      org.opencontainers.image.description="Distributed computing platform utilizing idle computer resources" \
      org.opencontainers.image.version="2.0.0" \
      org.opencontainers.image.licenses="MIT"

CMD ["python", "-m", "legacy.scheduler.simple_server"]
