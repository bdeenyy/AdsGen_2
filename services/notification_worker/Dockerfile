FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY services/notification_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/services/shared/
COPY services/notification_worker /app/services/notification_worker/

ENV PYTHONPATH=/app

CMD ["celery", "-A", "services.notification_worker.tasks", "worker", "-l", "info", "-Q", "notification"]
