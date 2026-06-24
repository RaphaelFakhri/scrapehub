# syntax=docker/dockerfile:1

# ---- Stage 1: build wheel ----------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir build hatchling \
    && python -m build --wheel --outdir /dist

# ---- Stage 2: runtime --------------------------------------------------------
# Use the official Playwright image so Chromium + all system libs are present.
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SCRAPEHUB_LOG_FORMAT=json \
    SCRAPEHUB_OUTPUT_DIR=/data

WORKDIR /app

COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

# Chromium is preinstalled in the base image; ensure it is available for our pin.
RUN python -m playwright install chromium

RUN mkdir -p /data
VOLUME ["/data"]

ENTRYPOINT ["scrapehub"]
CMD ["--help"]
