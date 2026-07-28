# Build context is the repository root so the workspace package is available:
#   docker build -f services/radio-service/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PATH="/app/.venv/bin:${PATH}"

# uv itself, copied from Astral's distroless image rather than `pip install
# uv` — keeps the tool that resolves/installs pinned to a known build, not
# whatever pip resolves that day. Bump alongside the uv version pinned for
# local dev (see `uv --version`) when upgrading.
COPY --from=ghcr.io/astral-sh/uv:0.9.30 /uv /uvx /bin/

WORKDIR /app

# uv.lock records the full workspace graph, but `--frozen --package` doesn't
# need every workspace member on disk to make sense of it — only the lock,
# this service, and its actual dependencies. Verified: `uv sync --frozen
# --no-dev --package pulsefm-radio-service` succeeds with
# services/station-api absent, so it isn't copied in.
COPY pyproject.toml uv.lock /app/
COPY packages/pulsefm-models /app/packages/pulsefm-models
COPY services/radio-service /app/services/radio-service

# --frozen: install exactly what uv.lock pins, the same lock the test suite
# ran against — no fresh dependency resolution at build time. This project
# has history with a transitive major-version break slipping in that way
# (see docs/adr on the google-auth-library pin); this is how it's prevented
# going forward. --no-dev skips pytest/httpx — test-only, not runtime.
RUN uv sync --frozen --no-dev --package pulsefm-radio-service

EXPOSE 8080

CMD exec uvicorn pulsefm_radio_service.main:app --host 0.0.0.0 --port ${PORT}
