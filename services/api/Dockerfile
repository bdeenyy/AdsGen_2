FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY services/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY services/shared /app/services/shared/

# Copy API code
COPY services/api /app/services/api/

# Set Python path
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run FastAPI
CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
