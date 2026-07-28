# Build context is the repository root:
#   docker build -f services/station-api/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

COPY packages/pulsefm-models /app/packages/pulsefm-models
COPY services/station-api /app/services/station-api

RUN pip install --no-cache-dir /app/packages/pulsefm-models \
 && pip install --no-cache-dir /app/services/station-api

EXPOSE 8080

CMD exec uvicorn pulsefm_station_api.main:app --host 0.0.0.0 --port ${PORT}
