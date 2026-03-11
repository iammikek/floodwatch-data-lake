#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
