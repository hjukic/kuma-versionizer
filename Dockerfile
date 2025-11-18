FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY src/kuma-versionizer.py /app/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir requests uptime-kuma-api

CMD ["python", "/app/kuma-versionizer.py"]

