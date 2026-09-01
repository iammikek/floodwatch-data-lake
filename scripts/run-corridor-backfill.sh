#!/usr/bin/env bash
set -euo pipefail

# Backfill EA hydrology for prediction corridor gauges (A361 Muchelney slice).
# Ref: docs/prediction-corridor-backfill.md

CORRIDOR="${CORRIDOR:-a361-muchelney}"
FROM="${FROM:-}"
TO="${TO:-}"
RESUME="${RESUME:-1}"
TOTAL_TIMEOUT="${TOTAL_TIMEOUT:-30}"
RETRIES="${RETRIES:-5}"

if [[ -z "${FROM}" ]]; then
  FROM="$(python - <<'PY'
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
print(f"{now.year - 2:04d}-01")
PY
)"
fi

if [[ -z "${TO}" ]]; then
  TO="$(python - <<'PY'
from ingestion.corridor_backfill import default_to_month
print(default_to_month())
PY
)"
fi

docker compose up -d lake-worker

RESUME_FLAG=""
if [[ "${RESUME}" == "1" ]]; then
  RESUME_FLAG="--resume"
fi

set -x
docker compose exec -T lake-worker bash -lc "\
TOTAL_TIMEOUT=${TOTAL_TIMEOUT} RETRIES=${RETRIES} \
python -m ingestion.cli backfill-ea-corridor \
  --corridor ${CORRIDOR} \
  --from ${FROM} \
  --to ${TO} \
  ${RESUME_FLAG} \
"

docker compose exec -T lake-worker bash -lc "\
python -m ingestion.cli check-corridor-coverage \
  --corridor ${CORRIDOR} \
  --from ${FROM} \
  --to ${TO} \
  --min-months 24 \
"
