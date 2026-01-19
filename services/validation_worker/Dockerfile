FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY services/validation_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/services/shared/
COPY services/validation_worker /app/services/validation_worker/

ENV PYTHONPATH=/app

CMD ["celery", "-A", "services.validation_worker.tasks", "worker", "-l", "info", "-Q", "validation"]
