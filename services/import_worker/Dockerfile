FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY services/import_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY services/shared /app/services/shared/

# Copy worker code
COPY services/import_worker /app/services/import_worker/

# Set Python path
ENV PYTHONPATH=/app

# Default command (overridden by docker-compose)
CMD ["celery", "-A", "services.import_worker.tasks", "worker", "-l", "info", "-Q", "import"]
