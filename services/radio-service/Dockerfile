# Build context is the repository root so the workspace package is available:
#   docker build -f services/radio-service/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

COPY packages/pulsefm-models /app/packages/pulsefm-models
COPY services/radio-service /app/services/radio-service

RUN pip install --no-cache-dir /app/packages/pulsefm-models \
 && pip install --no-cache-dir /app/services/radio-service

EXPOSE 8080

CMD exec uvicorn pulsefm_radio_service.main:app --host 0.0.0.0 --port ${PORT}
