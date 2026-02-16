#!/usr/bin/env bash
set -euo pipefail

REGION="${REGION:-SOM}"
FROM="${FROM:-}"
TO="${TO:-}"
PARAMS="${PARAMS:-level,flow}"
MAX_STATIONS="${MAX_STATIONS:-}"
MAX_MEASURES="${MAX_MEASURES:-}"

if [[ -z "${FROM}" || -z "${TO}" ]]; then
  echo "FROM and TO are required (YYYY-MM). Example: FROM=2025-12 TO=2026-01 REGION=SOM ./scripts/run-collector.sh"
  exit 1
fi

docker compose up -d lake-worker

set -x
docker compose exec -T lake-worker bash -lc "\
python -m ingestion.cli backfill-ea-region \
  --region ${REGION} \
  --parameters ${PARAMS} \
  --from ${FROM} \
  --to ${TO} \
  ${MAX_STATIONS:+--max-stations ${MAX_STATIONS}} \
  ${MAX_MEASURES:+--max-measures ${MAX_MEASURES}} \
"
