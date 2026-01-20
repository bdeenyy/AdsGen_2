# Multi-stage build for smaller final image
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements
COPY services/import_worker/requirements.txt .

# Install dependencies to a temporary directory
RUN pip install --no-cache-dir --user -r requirements.txt


# Final stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy shared modules
COPY services/shared /app/services/shared/

# Copy worker code
COPY services/import_worker /app/services/import_worker/

# Set Python path and ensure user-installed packages are in PATH
ENV PYTHONPATH=/app \
    PATH=/root/.local/bin:$PATH

# Health check for Celery worker
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD celery -A services.import_worker.tasks inspect ping -d import_worker@$HOSTNAME || exit 1

# Default command (overridden by docker-compose)
CMD ["celery", "-A", "services.import_worker.tasks", "worker", "-l", "info", "-Q", "import", "-n", "import_worker@%h"]
