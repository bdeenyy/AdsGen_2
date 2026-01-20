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
COPY services/api/requirements.txt .

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

# Copy API code
COPY services/api /app/services/api/

# Set Python path and ensure user-installed packages are in PATH
ENV PYTHONPATH=/app \
    PATH=/root/.local/bin:$PATH

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run FastAPI
CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
