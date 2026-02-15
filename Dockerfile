FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps kept minimal for JSON/APIs; heavier libs (GDAL/NetCDF) can be added later
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps (minimal set for early data gathering; expand later as needed)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt

# Copy project
COPY . /app

# Non-root user
RUN useradd -u 10001 -m appuser && chown -R appuser:appuser /app
USER appuser

# Default: keep container alive for interactive development; replace with entrypoint when jobs exist
CMD ["bash", "-lc", "echo 'Data lake ingestion container ready'; sleep infinity"]

